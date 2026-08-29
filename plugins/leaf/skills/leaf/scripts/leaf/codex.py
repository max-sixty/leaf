"""Detached Leaf delivery into later turns of one Codex task."""

import hashlib
import json
import os
import select
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

from .event_log import flocked, now_iso
from .files import read_json, write_json
from .host import host_identity, state_home
from .leases import adapter_is_live, adapter_lease_path, take_waiter_lease
from .server import running_server
from .service import PageTransaction, restore_page_claim, take_page_claim
from .session import Watch, acknowledge, batch_jsonl, read_watch_pass

QUEUE_TIMEOUT = 20
START_TIMEOUT = 20


def _run_codex(codex_path: str, *arguments: str) -> None:
    try:
        completed = subprocess.run(
            [codex_path, *arguments],
            capture_output=True,
            text=True,
            timeout=QUEUE_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("Codex queue command timed out") from error
    if completed.returncode == 0:
        return
    detail = completed.stderr.strip() or completed.stdout.strip()
    if not detail:
        detail = f"Codex exited with status {completed.returncode}"
    raise RuntimeError(detail)


def check_queue_command(codex_path: str) -> None:
    """Prove that this Codex installation provides durable task queueing."""
    _run_codex(codex_path, "queue", "--help")


def queue_delivery(codex_path: str, thread_id: str, prompt: str) -> None:
    """Hand one pointer prompt to Codex's durable same-task queue."""
    _run_codex(
        codex_path,
        "queue",
        "--thread",
        thread_id,
        "--message",
        prompt,
    )


def _session_key(session_id: str) -> str:
    return hashlib.sha256(session_id.encode()).hexdigest()[:32]


def adapter_record_path(session_id: str) -> Path:
    return state_home() / "sessions" / f"{_session_key(session_id)}.codex.json"


def delivery_path(session_id: str) -> Path:
    return state_home() / "sessions" / f"{_session_key(session_id)}.delivery.json"


def delivery_payload_path(session_id: str, delivery_id: str) -> Path:
    return (
        state_home()
        / "sessions"
        / f"{_session_key(session_id)}.deliveries"
        / f"{delivery_id}.json"
    )


def adapter_start_lock_path(session_id: str) -> Path:
    return state_home() / "sessions" / f"{_session_key(session_id)}.start"


def _write_record(session_id: str, **fields) -> None:
    path = adapter_record_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = read_json(path) or {}
    write_json(path, {**previous, **fields, "updated": now_iso()})


def _delivery_prompt(delivery_id: str, payload_path: Path, url: str | None) -> str:
    page = f" The live page is {url}." if url else ""
    return (
        "Leaf delivery "
        + delivery_id
        + " contains new reader input for this task."
        + page
        + " Read its exact JSONL batch from the `batch_jsonl` field in "
        + str(payload_path)
        + "."
        + " A delivery may appear again after an uncertain queue response; treat a "
        "page-and-sequence pair already handled in this task as a retry. "
        "The detached Leaf adapter owns only the `leaf wait`/`leaf ack` carrier; "
        "do not run either command. You still own page status, replies, revisions, "
        "and the handoff back to `waiting` or `idle`. Process every event in that "
        "batch using the Leaf conversation-loop contract, continue the page in this "
        "same task, and return the page's exact URL in every user-facing update."
    )


def capture_intent(session_id: str, reading) -> dict:
    """Persist one exact batch before its external acceptance attempt."""
    events = [(event["seq"], event["id"]) for event in reading.batch]
    identity = json.dumps(
        [session_id, str(reading.page_dir), events],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    delivery_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "leaf-delivery:" + identity))
    server = running_server(reading.page_dir)
    url = server["url"] if server else None
    payload_path = delivery_payload_path(session_id, delivery_id)
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format": "leaf-delivery-v1",
        "delivery_id": delivery_id,
        "page": str(reading.page_dir),
        "batch_jsonl": batch_jsonl(reading),
    }
    existing_payload = read_json(payload_path)
    if existing_payload is None:
        write_json(payload_path, payload)
    elif existing_payload != payload:
        raise RuntimeError(f"Codex delivery payload changed at {payload_path}")
    intent = {
        "thread_id": session_id,
        "page": str(reading.page_dir),
        "first_seq": reading.batch[0]["seq"],
        "last_seq": reading.batch[-1]["seq"],
        "sequences": [event["seq"] for event in reading.batch],
        "event_ids": [event["id"] for event in reading.batch],
        "delivery_id": delivery_id,
        "accepted": False,
        "url": url,
        "payload": str(payload_path),
        "prompt": _delivery_prompt(delivery_id, payload_path, url),
    }
    path = delivery_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, intent)
    return intent


def finish_intent(identity: dict, intent: dict) -> None:
    """Take receipt for an accepted batch, preserving a successor's claim."""
    page_dir = Path(intent["page"])
    try:
        with PageTransaction(page_dir) as page:
            delivered = {
                event["seq"]: event["id"]
                for event in page.events
                if intent["first_seq"] <= event["seq"] <= intent["last_seq"]
            }
            expected = dict(
                zip(
                    intent["sequences"],
                    intent["event_ids"],
                    strict=True,
                )
            )
            if all(
                delivered.get(seq) == event_id for seq, event_id in expected.items()
            ):
                if page.owned_by(identity):
                    count = len(intent["event_ids"])
                    status = page.status
                    if status["state"] != "working":
                        page.set_status(
                            "working",
                            f"picking up {count} update{'s' if count != 1 else ''}",
                            handoff=True,
                        )
                acknowledge(page, intent["last_seq"])
    except FileNotFoundError:
        pass
    delivery_path(identity["id"]).unlink(missing_ok=True)


def run_adapter(codex_path: str, ready_fd: int | None = None) -> int:
    """Own the session watch until every claimed page ends or transfers."""
    identity = host_identity()
    if identity is None or identity["host"] != "codex":
        raise RuntimeError("the Codex adapter needs a Codex task identity")
    lease = take_waiter_lease(adapter_lease_path(identity["id"]))
    if lease is None:
        raise RuntimeError("a Codex delivery adapter is already active")
    watch = Watch(identity)
    if not watch.acquire():
        lease.close()
        raise RuntimeError(
            "another `leaf wait` is already active; stop it before starting delivery"
        )
    leases_released = False
    try:
        check_queue_command(codex_path)
        _write_record(identity["id"], running=True, pid=os.getpid(), error=None)
        if ready_fd is not None:
            os.write(ready_fd, b'{"ready":true}\n')
            os.close(ready_fd)
            ready_fd = None
        failures = 0
        while True:
            intent = read_json(delivery_path(identity["id"]))
            if intent is not None:
                try:
                    if not intent.get("accepted", False):
                        queue_delivery(
                            codex_path,
                            identity["id"],
                            intent["prompt"],
                        )
                        intent = {**intent, "accepted": True}
                        write_json(delivery_path(identity["id"]), intent)
                    finish_intent(identity, intent)
                    failures = 0
                    _write_record(identity["id"], error=None)
                except (OSError, RuntimeError) as error:
                    failures += 1
                    _write_record(identity["id"], error=str(error))
                    time.sleep(min(30, 2 ** min(failures, 5)))
                continue

            captured = None

            def capture(reading) -> None:
                nonlocal captured
                captured = capture_intent(identity["id"], reading)

            reading = read_watch_pass(watch, None, deliver=capture)
            if captured is not None:
                continue
            if reading.outcome is not None or not reading.live:
                start_lock = adapter_start_lock_path(identity["id"])
                start_lock.parent.mkdir(parents=True, exist_ok=True)
                with flocked(start_lock):
                    captured = None
                    reading = read_watch_pass(watch, None, deliver=capture)
                    if captured is not None or reading.live:
                        continue
                    if delivery_path(identity["id"]).exists():
                        continue
                    watch.release()
                    lease.close()
                    leases_released = True
                    return reading.outcome or 0
            time.sleep(1)
    except BaseException as error:
        _write_record(identity["id"], running=False, error=str(error))
        if ready_fd is not None:
            os.write(
                ready_fd,
                (json.dumps({"ready": False, "error": str(error)}) + "\n").encode(),
            )
            os.close(ready_fd)
        raise
    finally:
        _write_record(identity["id"], running=False)
        if not leases_released:
            watch.release()
            lease.close()


def cmd_codex_start(page_dir: Path, codex_path: str | None = None) -> str:
    """Claim PAGE and start one detached delivery carrier for this task."""
    identity = host_identity()
    if identity is None or identity["host"] != "codex":
        raise RuntimeError("`leaf codex start` must run inside a Codex task")
    executable = codex_path or shutil.which("codex")
    if executable is None:
        raise RuntimeError("cannot find the `codex` executable on PATH")
    session_id = identity["id"]
    transition = take_page_claim(page_dir)
    launch_lock = adapter_start_lock_path(session_id)
    launch_lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        with flocked(launch_lock):
            if adapter_is_live(session_id):
                return f"Codex delivery is already active for task {session_id}"
            read_fd, write_fd = os.pipe()
            log_path = (
                state_home() / "sessions" / f"{_session_key(session_id)}.codex.log"
            )
            with open(log_path, "ab", buffering=0) as log:
                process = subprocess.Popen(
                    [
                        sys.executable,
                        str(Path(__file__).parent.parent / "interact.py"),
                        "codex",
                        "run",
                        "--codex-path",
                        executable,
                        "--ready-fd",
                        str(write_fd),
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=log,
                    start_new_session=True,
                    pass_fds=(write_fd,),
                )
            os.close(write_fd)
            try:
                ready, _, _ = select.select([read_fd], [], [], START_TIMEOUT)
                if not ready:
                    process.terminate()
                    process.wait(timeout=5)
                    raise RuntimeError("Codex delivery did not become ready")
                answer = json.loads(os.read(read_fd, 65536))
            finally:
                os.close(read_fd)
            if not answer.get("ready"):
                process.wait(timeout=5)
                raise RuntimeError(
                    answer.get("error") or "Codex delivery failed to start"
                )
    except BaseException:
        restore_page_claim(page_dir, transition)
        raise
    return f"Codex delivery started for task {session_id}"
