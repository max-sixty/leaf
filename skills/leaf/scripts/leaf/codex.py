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
from xml.etree import ElementTree

from .event_log import flocked
from .files import read_json, write_json
from .host import host_identity, state_home
from .leases import adapter_is_live, adapter_lease_path, take_waiter_lease
from .server import running_server
from .service import (
    PageTransaction,
    close_session_turn,
    owned_pages,
    restore_page_claim,
    take_page_claim,
    unacknowledged,
)
from .session import (
    PageTick,
    Watch,
    acknowledge,
    batch_jsonl,
    read_watch_pass,
    record_pickup,
)

QUEUE_TIMEOUT = 20
START_TIMEOUT = 20
TURN_DELIVERY_RECOVERY_TIMEOUT = 15 * 60
DELIVERY_CONTRACT = (
    Path(__file__).resolve().parents[2] / "references" / "event-batches.md"
)
DELIVERY_INSTRUCTION = (
    "Process every JSONL record in batch_jsonl under contract, including its "
    "pre-action refresh after through. Do not run leaf wait or leaf ack; the "
    "detached carrier owns them. Include url in every user-facing update."
)


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


def adapter_log_path(session_id: str) -> Path:
    return state_home() / "sessions" / f"{_session_key(session_id)}.codex.log"


def delivery_path(session_id: str) -> Path:
    return state_home() / "sessions" / f"{_session_key(session_id)}.delivery.json"


def wake_path(session_id: str) -> Path:
    return state_home() / "sessions" / f"{_session_key(session_id)}.wake.json"


def turn_path(session_id: str) -> Path:
    return state_home() / "sessions" / f"{_session_key(session_id)}.turn.json"


def turn_delivery_path(session_id: str) -> Path:
    return state_home() / "sessions" / f"{_session_key(session_id)}.turn-delivery.json"


def delivery_payload_path(session_id: str, delivery_id: str) -> Path:
    return (
        state_home()
        / "sessions"
        / f"{_session_key(session_id)}.deliveries"
        / f"{delivery_id}.json"
    )


def adapter_start_lock_path(session_id: str) -> Path:
    return state_home() / "sessions" / f"{_session_key(session_id)}.start"


def _turn_lock_path(session_id: str) -> Path:
    return state_home() / "sessions" / f"{_session_key(session_id)}.turn.lock"


def _turn_delivery_lock_path(session_id: str) -> Path:
    return state_home() / "sessions" / f"{_session_key(session_id)}.turn-delivery.lock"


def turn_generation(session_id: str) -> int:
    state = read_json(turn_path(session_id)) or {}
    return int(state.get("generation", 0))


def record_turn_boundary(session_id: str) -> None:
    """Persist a hook boundary the detached adapter may be too late to observe."""
    path = turn_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with flocked(_turn_lock_path(session_id)):
        write_json(path, {"generation": turn_generation(session_id) + 1})


def _delivery_prompt(delivery_id: str, payload_path: Path) -> str:
    delivery = ElementTree.Element(
        "leaf-delivery",
        {"skill": "$leaf", "id": delivery_id, "path": str(payload_path)},
    )
    pointer = ElementTree.tostring(delivery, encoding="unicode")
    return f"```xml\n{pointer}\n```"


def _persist_payload(
    session_id: str, reading: PageTick
) -> tuple[str, Path, str | None]:
    """Persist one exact batch with its current model-facing page location."""
    events = [(event["seq"], event["id"]) for event in reading.batch]
    identity = json.dumps(
        [session_id, str(reading.page_dir), events],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    delivery_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "leaf-delivery-v3:" + identity))
    server = running_server(reading.page_dir)
    url = server["url"] if server else None
    payload_path = delivery_payload_path(session_id, delivery_id)
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format": "leaf-delivery-v3",
        "delivery_id": delivery_id,
        "page": str(reading.page_dir),
        "url": url,
        "contract": str(DELIVERY_CONTRACT),
        "instruction": DELIVERY_INSTRUCTION,
        "through": reading.batch[-1]["seq"],
        "batch_jsonl": batch_jsonl(reading),
    }
    existing_payload = read_json(payload_path)
    if existing_payload is None:
        write_json(payload_path, payload)
    else:
        immutable = {key: value for key, value in payload.items() if key != "url"}
        existing_immutable = {
            key: value for key, value in existing_payload.items() if key != "url"
        }
        if existing_immutable != immutable:
            raise RuntimeError(f"Codex delivery payload changed at {payload_path}")
        if existing_payload.get("url") != url:
            write_json(payload_path, payload)
    return delivery_id, payload_path, url


def _batch_receipt(reading: PageTick) -> dict:
    return {
        "page": str(reading.page_dir),
        "first_seq": reading.batch[0]["seq"],
        "last_seq": reading.batch[-1]["seq"],
        "sequences": [event["seq"] for event in reading.batch],
        "event_ids": [event["id"] for event in reading.batch],
    }


def capture_intent(
    session_id: str, reading: PageTick, *, generation: int | None = None
) -> dict:
    """Persist one exact batch before its external acceptance attempt."""
    delivery_id, payload_path, url = _persist_payload(session_id, reading)
    intent = {
        "thread_id": session_id,
        **_batch_receipt(reading),
        "delivery_id": delivery_id,
        "accepted": False,
        "turn_generation": (
            turn_generation(session_id) if generation is None else generation
        ),
        "url": url,
        "payload": str(payload_path),
        "prompt": _delivery_prompt(delivery_id, payload_path),
    }
    path = delivery_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, intent)
    return intent


def _finish_batch(receipt: dict) -> None:
    """Acknowledge exactly the events named by one accepted delivery."""
    page_dir = Path(receipt["page"])
    try:
        with PageTransaction(page_dir) as page:
            delivered = {
                event["seq"]: event
                for event in page.events
                if receipt["first_seq"] <= event["seq"] <= receipt["last_seq"]
            }
            expected = dict(
                zip(
                    receipt["sequences"],
                    receipt["event_ids"],
                    strict=True,
                )
            )
            if all(
                delivered.get(seq, {}).get("id") == event_id
                for seq, event_id in expected.items()
            ):
                record_pickup(page, [delivered[seq] for seq in expected])
                acknowledge(page, receipt["last_seq"])
    except FileNotFoundError:
        pass


def finish_intent(identity: dict, intent: dict) -> None:
    """Take receipt for an accepted batch, preserving a successor's claim."""
    _finish_batch(intent)
    delivery_path(identity["id"]).unlink(missing_ok=True)


def _ensure_wake(session_id: str, intent: dict) -> None:
    """Keep one accepted wake standing until a later task turn opens."""
    path = wake_path(session_id)
    wake = {
        "delivery_id": intent.get("delivery_id"),
        "turn_generation": int(intent.get("turn_generation", 0)),
    }
    existing = read_json(path)
    if existing is None:
        write_json(path, wake)
    elif existing != wake:
        raise RuntimeError(f"Codex wake changed while outstanding at {path}")


def _session_turn_is_open(session_id: str) -> bool:
    """Whether any current claim proves this task is inside a turn."""
    for page_dir in owned_pages(session_id):
        try:
            with PageTransaction(page_dir) as page:
                claim = page.active_claim
                if (
                    claim
                    and claim["id"] == session_id
                    and claim["host"] == "codex"
                    and claim.get("turn_closed") is None
                ):
                    return True
        except FileNotFoundError:
            continue
    return False


def _capture_turn_delivery_unlocked(
    session_id: str, path: Path, *, require_open: bool
) -> dict | None:
    existing = read_json(path)
    if existing is not None:
        return existing
    deliveries = []
    for page_dir in owned_pages(session_id):
        try:
            with PageTransaction(page_dir) as page:
                claim = page.active_claim
                if not (
                    claim
                    and claim["id"] == session_id
                    and claim["host"] == "codex"
                    and (not require_open or claim.get("turn_closed") is None)
                ):
                    continue
                batch = unacknowledged(page.events, page.cursor)
                if not batch:
                    continue
                reading = PageTick(
                    page_dir,
                    page.status,
                    batch,
                    page.status["state"] != "idle",
                    "watching",
                    False,
                    None,
                    page,
                )
                delivery_id, payload_path, _ = _persist_payload(session_id, reading)
                deliveries.append(
                    {
                        **_batch_receipt(reading),
                        "delivery_id": delivery_id,
                        "payload": str(payload_path),
                    }
                )
        except FileNotFoundError:
            continue
    if not deliveries:
        return None
    manifest = {
        "format": "leaf-turn-delivery-v2",
        "session": session_id,
        "captured_at": time.time(),
        "deliveries": deliveries,
    }
    write_json(path, manifest)
    return manifest


def capture_turn_delivery(session_id: str) -> dict | None:
    """Snapshot input that arrived while this Codex turn was running.

    A prompt or Stop hook carries these pointers into the same turn. Receipt
    waits for the next Stop, which proves the hook output reached model context.
    """
    path = turn_delivery_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with flocked(_turn_delivery_lock_path(session_id)):
        return _capture_turn_delivery_unlocked(session_id, path, require_open=True)


def current_turn_delivery(session_id: str) -> dict | None:
    """Return a persisted in-turn snapshot without creating a new one."""
    return read_json(turn_delivery_path(session_id))


def _turn_delivery_suppression(session_id: str) -> str:
    """Hold a hidden delivery briefly, or release an abandoned continuation."""
    path = turn_delivery_path(session_id)
    with flocked(_turn_delivery_lock_path(session_id)):
        manifest = read_json(path)
        if manifest is None:
            return "none"
        captured_at = float(manifest.get("captured_at", 0))
        if time.time() - captured_at < TURN_DELIVERY_RECOVERY_TIMEOUT:
            return "pending"
        # Receipt still has not happened. Leave the events unacknowledged so
        # the ordinary adapter path can recover them through a visible wake.
        # The missing continuation is also the best available evidence that
        # the turn it would have continued is no longer open.
        close_session_turn(session_id)
        path.unlink(missing_ok=True)
        return "expired"


def turn_delivery_reason(manifest: dict) -> str:
    pointers = "\n".join(
        _delivery_prompt(delivery["delivery_id"], Path(delivery["payload"]))
        for delivery in manifest["deliveries"]
    )
    return (
        "Reader input was coalesced into this Codex turn. Process every event in the "
        "following Leaf delivery payloads now, in this same turn. The detached adapter "
        "and Stop hook own wait and acknowledgement; do not run either.\n" + pointers
    )


def finish_turn_delivery(session_id: str) -> bool:
    """Receipt the exact in-turn snapshot after its hook continuation ends."""
    path = turn_delivery_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with flocked(_turn_delivery_lock_path(session_id)):
        manifest = read_json(path)
        if manifest is None:
            return False
        for delivery in manifest["deliveries"]:
            _finish_batch(delivery)
        path.unlink(missing_ok=True)
        return True


def roll_turn_delivery(session_id: str) -> dict | None:
    """Receipt the prior snapshot and replace it atomically with later input."""
    path = turn_delivery_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with flocked(_turn_delivery_lock_path(session_id)):
        manifest = read_json(path)
        if manifest is not None:
            for delivery in manifest["deliveries"]:
                _finish_batch(delivery)
            path.unlink(missing_ok=True)
        return _capture_turn_delivery_unlocked(session_id, path, require_open=False)


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
        if ready_fd is not None:
            os.write(ready_fd, b'{"ready":true}\n')
            os.close(ready_fd)
            ready_fd = None
        failures = 0
        while True:
            intent = read_json(delivery_path(identity["id"]))
            if intent is not None:
                current_generation = turn_generation(identity["id"])
                intent_generation = int(intent.get("turn_generation", 0))
                # A prompt won the race after this snapshot but before its queue
                # attempt. The running turn now owns the still-unacknowledged
                # events; its Stop hook will carry them without another message.
                if not intent.get("accepted", False) and (
                    current_generation > intent_generation
                    or _session_turn_is_open(identity["id"])
                ):
                    delivery_path(identity["id"]).unlink(missing_ok=True)
                    continue
                try:
                    if not intent.get("accepted", False):
                        queue_delivery(
                            codex_path,
                            identity["id"],
                            intent["prompt"],
                        )
                        intent = {**intent, "accepted": True}
                        write_json(delivery_path(identity["id"]), intent)
                    _ensure_wake(identity["id"], intent)
                    finish_intent(identity, intent)
                    failures = 0
                except (OSError, RuntimeError) as error:
                    failures += 1
                    if failures == 1:
                        print(
                            f"Codex delivery retry: {error}",
                            file=sys.stderr,
                            flush=True,
                        )
                    time.sleep(min(30, 2 ** min(failures, 5)))
                continue

            wake = read_json(wake_path(identity["id"]))
            if wake is not None:
                if turn_generation(identity["id"]) > int(wake["turn_generation"]):
                    wake_path(identity["id"]).unlink(missing_ok=True)
                    continue
                # SessionEnd or transfer leaves nobody who could open this wake.
                # The accepted queue item and immutable payload remain durable;
                # only this carrier's coalescing marker can retire with its owner.
                if not owned_pages(identity["id"]):
                    wake_path(identity["id"]).unlink(missing_ok=True)
                    continue
                time.sleep(1)
                continue

            # An event log is the mailbox; the queue is only its edge-triggered
            # wake. A current hidden delivery belongs to the Stop continuation.
            # If that continuation disappears, its bounded recovery hold expires
            # without receipt and the events return to the visible queue path.
            turn_delivery_state = _turn_delivery_suppression(identity["id"])
            if turn_delivery_state == "pending":
                time.sleep(1)
                continue
            generation = turn_generation(identity["id"])
            if turn_delivery_state != "expired" and _session_turn_is_open(
                identity["id"]
            ):
                time.sleep(1)
                continue

            captured = None

            def capture(reading, generation=generation) -> bool:
                """Persist the batch, and answer that no turn has opened.

                This carrier hands a pointer to Codex's durable same-task queue,
                and a queue item is started by the loaded client or by nobody:
                an unloaded task keeps it standing until Codex reopens the task,
                which the adapter never does. Even the queue acceptance this
                capture precedes by a loop iteration proves only that the item
                was taken. So clearing the turn-ended stamp here would put
                "Codex is working" over a task nobody has reopened, for the
                fifteen minutes until the claim's own age caught it, in place of
                a line dating the last turn's end truthfully. Leaving it standing
                costs the loaded case nothing the reader keeps: the turn that
                does start writes a status past the stamp, which is what carries
                a claim across a turn boundary the session cannot write over.
                """
                nonlocal captured
                captured = capture_intent(
                    identity["id"], reading, generation=generation
                )
                return False

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
        if ready_fd is not None:
            os.write(
                ready_fd,
                (json.dumps({"ready": False, "error": str(error)}) + "\n").encode(),
            )
            os.close(ready_fd)
        raise
    finally:
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
            log_path = adapter_log_path(session_id)
            with open(log_path, "ab", buffering=0) as log:
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "leaf",
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
