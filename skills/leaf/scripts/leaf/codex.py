"""Detached Leaf delivery into the active and later turns of one Codex task."""

import hashlib
import json
import os
import select
import shutil
import subprocess
import sys
import time
import uuid
from contextlib import ExitStack, contextmanager
from pathlib import Path
from xml.etree import ElementTree

from .event_log import flocked, read_cursor
from .files import read_json, write_json
from .host import host_identity, state_home
from .leases import adapter_is_live, adapter_lease_path, take_waiter_lease
from .schema import EVENTS_FILE
from .server import running_server
from .service import (
    PageTransaction,
    owned_pages,
    page_claim,
    restore_page_claim,
    take_page_claim,
    unacknowledged,
)
from .session import Watch, acknowledge, batch_data, read_watch_pass, record_pickup

QUEUE_TIMEOUT = 20
START_TIMEOUT = 20
ACTIVE_DELIVERY_RECOVERY_TIMEOUT = 15 * 60
DELIVERY_EPOCH_FORMAT = "leaf-codex-delivery-v1"


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


def delivery_dir(session_id: str) -> Path:
    return state_home() / "sessions" / f"{_session_key(session_id)}.deliveries"


def delivery_lock_path(session_id: str) -> Path:
    return state_home() / "sessions" / f"{_session_key(session_id)}.delivery.lock"


def delivery_epoch_path(session_id: str, delivery_id: str) -> Path:
    return delivery_dir(session_id) / f"{delivery_id}.json"


def _archive_epoch(epoch_path: Path, epoch: dict) -> None:
    """Move finished history out of the adapter's hot scan."""
    if epoch["phase"] == "closed" and all(
        batch["receipted"] for batch in epoch["batches"]
    ):
        history_path = epoch_path.parent / "history" / epoch_path.name
        history_path.parent.mkdir(parents=True, exist_ok=True)
        epoch_path.replace(history_path)


def _write_epoch(epoch_path: Path, epoch: dict) -> None:
    write_json(epoch_path, epoch)
    _archive_epoch(epoch_path, epoch)


def adapter_start_lock_path(session_id: str) -> Path:
    return state_home() / "sessions" / f"{_session_key(session_id)}.start"


def _prompt(epoch_path: Path) -> str:
    delivery = ElementTree.Element(
        "leaf-delivery",
        {"skill": "$leaf", "id": epoch_path.stem, "path": str(epoch_path)},
    )
    pointer = ElementTree.tostring(delivery, encoding="unicode")
    return f"```xml\n{pointer}\n```"


def _offer_epoch(epoch_path: Path, epoch: dict) -> str:
    """Persist one current URL per page before offering an epoch pointer."""
    urls = {}
    for batch in epoch["batches"]:
        page = batch["page"]
        if page not in urls:
            server = running_server(Path(page))
            urls[page] = server["url"] if server else None
        batch["url"] = urls[page]
    _write_epoch(epoch_path, epoch)
    return _prompt(epoch_path)


def _epochs(session_id: str) -> list[tuple[Path, dict]]:
    directory = delivery_dir(session_id)
    if not directory.is_dir():
        return []
    return [
        (path, epoch)
        for path in sorted(directory.glob("*.json"))
        if (epoch := read_json(path)) is not None
        # Earlier adapters stored their already-delivered batch records in this
        # directory. A missing format is a delivery epoch written before epochs
        # became self-describing; every other explicit format is a different record.
        and epoch.get("format") in {None, DELIVERY_EPOCH_FORMAT}
    ]


def _current_epoch(
    session_id: str,
    epochs: list[tuple[Path, dict]] | None = None,
) -> tuple[Path, dict] | None:
    records = _epochs(session_id) if epochs is None else epochs
    current = [(path, epoch) for path, epoch in records if epoch["phase"] != "closed"]
    if len(current) > 1:
        raise RuntimeError(f"Codex task {session_id} has multiple open Leaf deliveries")
    return current[0] if current else None


def _append_batch(
    session_id: str,
    page_dir: Path,
    transaction: PageTransaction,
    batch: list[dict],
    *,
    queue_if_new: bool,
) -> tuple[Path, int, dict] | None:
    """Append fresh events to the task's open epoch under its delivery lock."""
    current = _current_epoch(session_id)
    if current is not None:
        current_path, current_epoch = current
        if queue_if_new and current_epoch["phase"] == "entered":
            current_epoch["phase"] = "closed"
            if current_epoch["queue"] == "pending":
                current_epoch["queue"] = "none"
            _write_epoch(current_path, current_epoch)
            current = None
    if current is None:
        epoch_path = delivery_epoch_path(session_id, str(uuid.uuid4()))
        epoch_path.parent.mkdir(parents=True, exist_ok=True)
        epoch = {
            "format": DELIVERY_EPOCH_FORMAT,
            "queue": "pending" if queue_if_new else "none",
            "queued": 0,
            "stop_offered": 0,
            "phase": "waiting" if queue_if_new else "entered",
            "updated_at": time.time(),
            "batches": [],
        }
    else:
        epoch_path, epoch = current
        if not queue_if_new:
            epoch["phase"] = "entered"

    delivered = {
        (entry["page"], event["seq"], event["id"])
        for entry in epoch["batches"]
        for event in entry["events"]
    }
    fresh = [
        event
        for event in batch
        if (str(page_dir), event["seq"], event["id"]) not in delivered
    ]
    if not fresh:
        return None

    server = running_server(page_dir)
    url = server["url"] if server else None
    data = batch_data(page_dir, transaction, fresh)
    entry = {
        "page": data["page"],
        "url": url,
        "threads": data["threads"],
        "events": data["events"],
        "receipted": False,
    }
    epoch["batches"].append(entry)
    epoch["updated_at"] = time.time()
    _write_epoch(epoch_path, epoch)
    return epoch_path, len(epoch["batches"]) - 1, entry


def capture_batch(session_id: str, reading) -> bool:
    """Persist one watcher batch in the session's current delivery epoch."""
    lock = delivery_lock_path(session_id)
    lock.parent.mkdir(parents=True, exist_ok=True)
    with flocked(lock):
        captured = _append_batch(
            session_id,
            reading.page_dir,
            reading.transaction,
            reading.batch,
            queue_if_new=any(
                (claim := page_claim(page_dir)) is not None
                and claim["host"] == "codex"
                and claim.get("turn_closed")
                for page_dir in owned_pages(session_id)
            ),
        )
    return captured is not None


def _finish_batch(batch: dict) -> None:
    """Take receipt for one persisted batch, preserving a successor's claim."""
    page_dir = Path(batch["page"])
    expected = {event["seq"]: event["id"] for event in batch["events"]}
    try:
        with PageTransaction(page_dir) as page:
            delivered = {
                event["seq"]: event
                for event in page.events
                if min(expected) <= event["seq"] <= max(expected)
            }
            if not all(
                delivered.get(seq, {}).get("id") == event_id
                for seq, event_id in expected.items()
            ):
                return
            record_pickup(page, [delivered[seq] for seq in expected])
            acknowledge(page, max(expected))
    except FileNotFoundError:
        pass


def _page_acknowledged(batch: dict) -> bool:
    page_dir = Path(batch["page"])
    if not (page_dir / EVENTS_FILE).is_file():
        return True
    return read_cursor(page_dir) >= max(event["seq"] for event in batch["events"])


def _sync_receipts(epoch_path: Path, epoch: dict) -> None:
    """Preserve page receipts in history before their paths can be reused."""
    changed = False
    for batch in epoch["batches"]:
        if not batch["receipted"] and _page_acknowledged(batch):
            batch["receipted"] = True
            changed = True
    if changed:
        _write_epoch(epoch_path, epoch)
    else:
        _archive_epoch(epoch_path, epoch)


def _record_receipt(epoch_path: Path, batch_index: int) -> None:
    epoch = read_json(epoch_path)
    if epoch is not None and not epoch["batches"][batch_index]["receipted"]:
        epoch["batches"][batch_index]["receipted"] = True
        _write_epoch(epoch_path, epoch)


def _recover_delivery(codex_path: str, session_id: str) -> bool:
    """Advance one durable queue or page-receipt transition."""
    lock = delivery_lock_path(session_id)
    lock.parent.mkdir(parents=True, exist_ok=True)
    with flocked(lock):
        epochs = _epochs(session_id)
        current = _current_epoch(session_id, epochs)
        if current is not None:
            path, epoch = current
            if (
                epoch["phase"] == "entered"
                and len(epoch["batches"]) > epoch["queued"]
                and time.time() - epoch["updated_at"]
                >= ACTIVE_DELIVERY_RECOVERY_TIMEOUT
            ):
                epoch["phase"] = "waiting"
                epoch["queue"] = "pending"
                _write_epoch(path, epoch)
        for path, epoch in epochs:
            _sync_receipts(path, epoch)
        queued_epoch = next(
            ((path, epoch) for path, epoch in epochs if epoch["queue"] == "pending"),
            None,
        )
        queued = None
        if queued_epoch is not None:
            epoch_path, epoch = queued_epoch
            queued = epoch_path, len(epoch["batches"]), _offer_epoch(epoch_path, epoch)
    if queued is not None:
        epoch_path, queued_count, prompt = queued
        queue_delivery(codex_path, session_id, prompt)
        with flocked(lock):
            epoch = read_json(epoch_path)
            if epoch is not None and epoch["queue"] == "pending":
                epoch["queue"] = "accepted"
                epoch["queued"] = queued_count
                _write_epoch(epoch_path, epoch)
        return True

    with flocked(lock):
        pending = min(
            (
                (path, index, dict(batch))
                for path, epoch in _epochs(session_id)
                if epoch["queue"] != "pending"
                for index, batch in enumerate(epoch["batches"])
                if not batch["receipted"]
            ),
            key=lambda pending: (
                pending[2]["page"],
                min(event["seq"] for event in pending[2]["events"]),
            ),
            default=None,
        )
    if pending is None:
        return False
    epoch_path, batch_index, batch = pending
    _finish_batch(batch)
    with flocked(lock):
        _record_receipt(epoch_path, batch_index)
    return True


def _has_delivery_work(session_id: str) -> bool:
    with flocked(delivery_lock_path(session_id)):
        return any(
            epoch["queue"] == "pending"
            or any(not batch["receipted"] for batch in epoch["batches"])
            for _, epoch in _epochs(session_id)
        )


@contextmanager
def _locked_codex_pages(session_id: str):
    """Lock the current Codex-owned page set in its stable path order."""
    with ExitStack() as stack:
        pages = []
        for page_dir in owned_pages(session_id):
            try:
                page = stack.enter_context(PageTransaction(page_dir))
            except FileNotFoundError:
                continue
            claim = page.active_claim
            if claim and claim["id"] == session_id and claim["host"] == "codex":
                pages.append(page)
        yield pages


def _capture_pages(session_id: str, pages: list[PageTransaction]) -> None:
    """Move every pending page event into the current in-turn mailbox."""
    for page in pages:
        batch = unacknowledged(page.events, page.cursor)
        if not batch:
            continue
        captured = _append_batch(
            session_id,
            page.page_dir,
            page,
            batch,
            queue_if_new=False,
        )
        if captured is None:
            continue
        epoch_path, batch_index, entry = captured
        # The epoch must survive before the page cursor advances.
        # A hook process may fail open after either write.
        events = {event["seq"]: event for event in page.events}
        delivered = [events[event["seq"]] for event in entry["events"]]
        record_pickup(page, delivered)
        acknowledge(page, max(event["seq"] for event in entry["events"]))
        _record_receipt(epoch_path, batch_index)


def open_turn(session_id: str) -> tuple[bool, str | None]:
    """Open a Codex turn and carry any waiting Leaf input into its context."""
    with _locked_codex_pages(session_id) as pages:
        if not pages:
            return False, None
        lock = delivery_lock_path(session_id)
        lock.parent.mkdir(parents=True, exist_ok=True)
        with flocked(lock):
            if adapter_is_live(session_id):
                _capture_pages(session_id, pages)
            current = _current_epoch(session_id)
            prompt = None
            if current is not None:
                epoch_path, epoch = current
                epoch["phase"] = "entered"
                epoch["updated_at"] = time.time()
                if epoch["queue"] == "pending":
                    epoch["queue"] = "none"
                prompt = _offer_epoch(epoch_path, epoch)
            for page in pages:
                page.open_turn(session_id)
        return True, prompt


def finish_turn(
    session_id: str,
    reasons: list[str],
    stop_hook_active: bool,
) -> list[str] | None:
    """Atomically deliver input that precedes this Stop or close the turn."""
    with _locked_codex_pages(session_id) as pages:
        if not pages:
            return None
        lock = delivery_lock_path(session_id)
        lock.parent.mkdir(parents=True, exist_ok=True)
        with flocked(lock):
            if adapter_is_live(session_id):
                _capture_pages(session_id, pages)
            current = _current_epoch(session_id)
            prompt = None
            if current is not None:
                epoch_path, epoch = current
                visible = epoch["stop_offered"] if stop_hook_active else epoch["queued"]
                if len(epoch["batches"]) > visible:
                    epoch["stop_offered"] = len(epoch["batches"])
                    epoch["updated_at"] = time.time()
                    prompt = _offer_epoch(epoch_path, epoch)
            should_block = prompt is not None or bool(reasons and not stop_hook_active)
            if should_block:
                for page in pages:
                    page.open_turn(session_id)
            else:
                for page in pages:
                    page.close_turn(session_id)
                if current is not None:
                    epoch_path, epoch = current
                    if epoch["queue"] == "pending":
                        epoch["queue"] = "none"
                    epoch["phase"] = "closed"
                    _write_epoch(epoch_path, epoch)

    if not should_block:
        return []
    delivery = (
        []
        if prompt is None
        else ["new Leaf input joined this turn. Process every batch in:\n" + prompt]
    )
    return delivery + reasons


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
            try:
                recovered = _recover_delivery(codex_path, identity["id"])
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
            if recovered:
                failures = 0
                continue

            captured = False

            def capture(reading) -> bool:
                """Persist the batch without claiming that a turn opened."""
                nonlocal captured
                captured = capture_batch(identity["id"], reading)
                return False

            reading = read_watch_pass(watch, None, deliver=capture)
            if captured:
                continue
            if reading.outcome is not None or not reading.live:
                start_lock = adapter_start_lock_path(identity["id"])
                start_lock.parent.mkdir(parents=True, exist_ok=True)
                with flocked(start_lock):
                    captured = False
                    reading = read_watch_pass(watch, None, deliver=capture)
                    if captured or reading.live:
                        continue
                    if _has_delivery_work(identity["id"]):
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
