"""Detached Leaf delivery into the active and later turns of one Codex task."""

import hashlib
import json
import os
import queue
import select
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from contextlib import ExitStack, contextmanager
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree

from websockets.exceptions import WebSocketException
from websockets.sync.client import connect, unix_connect

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
APP_SERVER_ENV = "LEAF_CODEX_APP_SERVER"
STREAM_UPDATE_INTERVAL = 0.2
STREAM_TEXT_METHODS = {
    "item/agentMessage/delta",
    "item/reasoning/summaryTextDelta",
}
STREAM_HEARTBEAT_METHODS = {
    "item/commandExecution/outputDelta",
    "item/fileChange/outputDelta",
    "item/mcpToolCall/progress",
}
STREAM_THROTTLED_METHODS = STREAM_TEXT_METHODS | STREAM_HEARTBEAT_METHODS


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


def queue_delivery(
    codex_path: str,
    thread_id: str,
    prompt: str,
    app_server: str | None = None,
) -> None:
    """Hand one pointer prompt to Codex's durable same-task queue."""
    arguments = ["queue"]
    if app_server is not None:
        arguments.extend(["--remote", app_server])
    arguments.extend(["--thread", thread_id, "--message", prompt])
    _run_codex(codex_path, *arguments)


def app_server_socket_path(endpoint: str) -> Path | None:
    """Validate a local App Server endpoint and return its Unix socket path."""
    try:
        parsed = urlsplit(endpoint)
        hostname = parsed.hostname
    except ValueError as error:
        raise RuntimeError("--app-server needs a valid local endpoint") from error
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise RuntimeError("--app-server needs a local WebSocket or Unix endpoint")
    if parsed.scheme == "ws" and hostname in {"127.0.0.1", "::1", "localhost"}:
        return None
    if parsed.scheme == "unix" and not parsed.netloc and parsed.path:
        path = Path(parsed.path)
        if path.is_absolute():
            return path
    raise RuntimeError(
        "--app-server needs a local loopback ws:// endpoint or an absolute "
        "unix:/// socket"
    )


def check_app_server_endpoint(endpoint: str) -> None:
    """Keep the experimental unauthenticated transport on this machine."""
    app_server_socket_path(endpoint)


def _app_server_connect(endpoint: str):
    socket_path = app_server_socket_path(endpoint)
    options = {
        "open_timeout": START_TIMEOUT,
        "close_timeout": 1,
        "compression": None,
    }
    if socket_path is not None:
        return unix_connect(str(socket_path), uri="ws://localhost/rpc", **options)
    return connect(endpoint, **options)


def _head(text: str, limit: int = 180) -> str:
    line = " ".join(text.split())
    return line if len(line) <= limit else line[: limit - 1] + "…"


def _tail(text: str, limit: int = 240) -> str:
    line = " ".join(text.split())
    return line if len(line) <= limit else "…" + line[-(limit - 1) :]


class AppServerEvents:
    """Fold one task's event notifications into its latest readable activity."""

    # TODO(2026-09-08): Project agent-message deltas into a task-response reading
    # outside the event log, and retain the final text until the next turn.

    def __init__(self, thread_id: str):
        self.thread_id = thread_id
        self.turn_id: str | None = None
        self.details: dict[str, str] = {}
        self.text: dict[str, str] = {}

    def read(self, message: dict) -> tuple[str, str | None] | None:
        """Return (turn, detail); a None detail clears the completed turn."""
        method = message.get("method")
        params = message.get("params") or {}
        message_thread = params.get("threadId")
        if message_thread is not None and message_thread != self.thread_id:
            return None

        if method == "turn/started":
            self.turn_id = params["turn"]["id"]
            self.details.clear()
            self.text.clear()
            return self.turn_id, "Starting"

        turn_id = params.get("turnId") or self.turn_id
        if method == "turn/completed":
            completed = params["turn"]["id"]
            if self.turn_id == completed:
                self.turn_id = None
                self.details.clear()
                self.text.clear()
            return completed, None
        if turn_id is None:
            return None

        if method == "turn/plan/updated":
            steps = params.get("plan", [])
            current = next(
                (step["step"] for step in steps if step["status"] == "inProgress"),
                None,
            )
            if current is None:
                current = next(
                    (step["step"] for step in steps if step["status"] == "pending"),
                    None,
                )
            return (turn_id, _head(current)) if current else None

        if method == "item/started":
            item = params["item"]
            detail = self._item_detail(item)
            if detail:
                self.details[item["id"]] = detail
            return (turn_id, detail) if detail else None

        if method == "item/completed":
            item = params["item"]
            self.details.pop(item["id"], None)
            if item["type"] == "agentMessage" and item.get("text"):
                return turn_id, _tail(item["text"])
            return None

        if method in STREAM_TEXT_METHODS:
            item_id = params["itemId"]
            combined = self.text.get(item_id, "") + params["delta"]
            self.text[item_id] = combined
            prefix = "Thinking — " if method.endswith("summaryTextDelta") else ""
            return turn_id, prefix + _tail(combined)

        if method in STREAM_HEARTBEAT_METHODS:
            detail = self.details.get(params["itemId"])
            return (turn_id, detail) if detail else None

        if method in {
            "item/commandExecution/requestApproval",
            "item/fileChange/requestApproval",
            "item/permissions/requestApproval",
            "item/tool/requestUserInput",
        }:
            return turn_id, "Waiting for input in Codex"

        if method == "thread/status/changed":
            flags = params.get("status", {}).get("activeFlags", [])
            if "waitingOnApproval" in flags or "waitingOnUserInput" in flags:
                return turn_id, "Waiting for input in Codex"
        return None

    @staticmethod
    def _item_detail(item: dict) -> str | None:
        kind = item["type"]
        if kind == "commandExecution":
            return "Running " + _head(item["command"])
        if kind == "fileChange":
            paths = [change["path"] for change in item.get("changes", [])]
            return "Editing " + _head(", ".join(paths)) if paths else "Editing files"
        if kind == "mcpToolCall":
            app = item.get("appContext") or {}
            name = app.get("appName") or item.get("server")
            return "Using " + _head(f"{name}: {item['tool']}")
        if kind == "dynamicToolCall":
            return "Using " + _head(item["tool"])
        if kind == "collabAgentToolCall":
            return "Coordinating " + _head(item["tool"])
        if kind == "webSearch":
            return "Searching the web" + (
                " — " + _head(item["query"]) if item.get("query") else ""
            )
        if kind == "imageView":
            return "Inspecting " + _head(item["path"])
        if kind == "contextCompaction":
            return "Compacting the conversation"
        if kind == "imageGeneration":
            return "Generating an image"
        if kind == "enteredReviewMode":
            return "Reviewing " + _head(item["review"])
        return None


class AppServerObserver:
    """Subscribe to one running Codex task without taking control of it."""

    def __init__(self, endpoint: str, thread_id: str):
        check_app_server_endpoint(endpoint)
        self.endpoint = endpoint
        self.thread_id = thread_id
        self.events = AppServerEvents(thread_id)
        self.stop_event = threading.Event()
        self.available = threading.Event()
        self.socket = None
        self.last_stream_update = 0.0
        self.started = False
        self.ready: queue.Queue[BaseException | None] = queue.Queue(maxsize=1)
        self.thread = threading.Thread(
            target=self._run,
            name="leaf-codex-app-server",
            daemon=True,
        )

    def start(self) -> None:
        self.thread.start()
        try:
            outcome = self.ready.get(timeout=START_TIMEOUT)
        except queue.Empty as error:
            self.stop()
            raise RuntimeError("Codex App Server did not answer") from error
        if outcome is not None:
            self.stop()
            raise RuntimeError(f"Codex App Server connection failed: {outcome}")

    def stop(self) -> None:
        self.stop_event.set()
        self.available.clear()
        if self.socket is not None:
            self.socket.close()
        self.thread.join(timeout=3)
        _clear_stream_activity(self.thread_id)

    def _send(self, socket, method: str, request_id: int, params: dict) -> dict:
        socket.send(json.dumps({"method": method, "id": request_id, "params": params}))
        while not self.stop_event.is_set():
            raw = socket.recv(timeout=START_TIMEOUT)
            message = json.loads(raw)
            if message.get("id") == request_id and "method" not in message:
                if error := message.get("error"):
                    raise RuntimeError(error.get("message") or str(error))
                return message.get("result") or {}
            self._read(message)
        raise RuntimeError("Codex App Server observer stopped")

    def _connect(self) -> None:
        with _app_server_connect(self.endpoint) as socket:
            self.socket = socket
            self._send(
                socket,
                "initialize",
                0,
                {
                    "clientInfo": {
                        "name": "leaf",
                        "title": "Leaf",
                        "version": "0",
                    }
                },
            )
            socket.send(json.dumps({"method": "initialized", "params": {}}))
            result = self._send(
                socket,
                "thread/resume",
                1,
                {"threadId": self.thread_id, "excludeTurns": True},
            )
            resumed = result.get("thread", {})
            if resumed.get("status", {}).get("type") == "active":
                active = next(
                    (
                        turn["id"]
                        for turn in reversed(resumed.get("turns", []))
                        if turn.get("status") == "inProgress"
                    ),
                    "active",
                )
                self.events.turn_id = active
                _set_stream_activity(self.thread_id, active, "Working in Codex")
            self.available.set()
            if not self.started:
                self.started = True
                self.ready.put(None)
            while not self.stop_event.is_set():
                try:
                    raw = socket.recv(timeout=1)
                except TimeoutError:
                    continue
                self._read(json.loads(raw))

    def _read(self, message: dict) -> None:
        update = self.events.read(message)
        if update is None:
            return
        turn_id, detail = update
        if detail is None:
            _clear_stream_activity(self.thread_id)
        else:
            now = time.monotonic()
            if (
                message.get("method") in STREAM_THROTTLED_METHODS
                and now - self.last_stream_update < STREAM_UPDATE_INTERVAL
            ):
                return
            _set_stream_activity(self.thread_id, turn_id, detail)
            self.last_stream_update = now

    def _run(self) -> None:
        failures = 0
        while not self.stop_event.is_set():
            try:
                self._connect()
                failures = 0
            except (
                OSError,
                RuntimeError,
                WebSocketException,
                json.JSONDecodeError,
            ) as error:
                self.available.clear()
                _clear_stream_activity(self.thread_id)
                if not self.started:
                    self.ready.put(error)
                    return
                failures += 1
                if failures == 1:
                    print(
                        f"Codex App Server stream retry: {error}",
                        file=sys.stderr,
                        flush=True,
                    )
                self.stop_event.wait(min(30, 2 ** min(failures, 5)))


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
        "session": session_id,
        "url": url,
        "threads": data["threads"],
        "handling": data["handling"],
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
            record_pickup(
                page,
                [delivered[seq] for seq in expected],
                phase="queued",
                session=batch["session"],
                turn=None,
            )
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


def _recover_delivery(
    codex_path: str,
    session_id: str,
    app_server: str | None = None,
) -> bool:
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
        if app_server is None:
            queue_delivery(codex_path, session_id, prompt)
        else:
            queue_delivery(codex_path, session_id, prompt, app_server)
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


def _set_stream_activity(session_id: str, turn_id: str, detail: str) -> None:
    with _locked_codex_pages(session_id) as pages:
        for page in pages:
            page.set_stream_activity(session_id, turn_id, detail)


def _clear_stream_activity(session_id: str, turn_id: str | None = None) -> None:
    with _locked_codex_pages(session_id) as pages:
        for page in pages:
            page.clear_stream_activity(session_id, turn_id)


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
        record_pickup(
            page,
            delivered,
            phase="opened",
            session=session_id,
            turn=(page.claim or {}).get("turn"),
        )
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
            # Establish the turn before capturing input: every delivery recorded
            # below must name the turn it actually entered, never the one the
            # preceding Stop hook closed.
            for page in pages:
                page.open_turn(session_id)
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
                by_page = {str(page.page_dir): page for page in pages}
                for batch in epoch["batches"]:
                    page = by_page.get(batch["page"])
                    if page is None:
                        continue
                    wanted = {event["id"] for event in batch["events"]}
                    delivered = [
                        event for event in page.events if event.get("id") in wanted
                    ]
                    record_pickup(
                        page,
                        delivered,
                        phase="opened",
                        session=session_id,
                        turn=(page.claim or {}).get("turn"),
                    )
                prompt = _offer_epoch(epoch_path, epoch)
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


def run_adapter(
    codex_path: str,
    ready_fd: int | None = None,
    app_server: str | None = None,
) -> int:
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
    observer = None
    try:
        check_queue_command(codex_path)
        if app_server is not None:
            observer = AppServerObserver(app_server, identity["id"])
            observer.start()
        if ready_fd is not None:
            os.write(ready_fd, b'{"ready":true}\n')
            os.close(ready_fd)
            ready_fd = None
        failures = 0
        while True:
            try:
                queue_server = (
                    app_server
                    if observer is not None and observer.available.is_set()
                    else None
                )
                recovered = _recover_delivery(
                    codex_path,
                    identity["id"],
                    queue_server,
                )
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
                    if captured or (reading.outcome is None and reading.live):
                        continue
                    if _has_delivery_work(identity["id"]):
                        time.sleep(1)
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
        if observer is not None:
            observer.stop()
        if not leases_released:
            watch.release()
            lease.close()


def cmd_codex_start(
    page_dir: Path,
    codex_path: str | None = None,
    app_server: str | None = None,
) -> str:
    """Claim PAGE and start one detached delivery carrier for this task."""
    identity = host_identity()
    if identity is None or identity["host"] != "codex":
        raise RuntimeError("`leaf codex start` must run inside a Codex task")
    executable = codex_path or shutil.which("codex")
    if executable is None:
        raise RuntimeError("cannot find the `codex` executable on PATH")
    session_id = identity["id"]
    app_server = app_server or os.environ.get(APP_SERVER_ENV)
    if app_server is not None:
        check_app_server_endpoint(app_server)
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
                arguments = [
                    sys.executable,
                    "-m",
                    "leaf",
                    "codex",
                    "run",
                    "--codex-path",
                    executable,
                    "--ready-fd",
                    str(write_fd),
                ]
                if app_server is not None:
                    arguments.extend(["--app-server", app_server])
                process = subprocess.Popen(
                    arguments,
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
    streamed = f" with live activity from {app_server}" if app_server else ""
    return f"Codex delivery started for task {session_id}{streamed}"


def _wait_for_app_server(path: Path, process: subprocess.Popen, log) -> None:
    deadline = time.monotonic() + START_TIMEOUT
    while time.monotonic() < deadline:
        if path.exists():
            return
        if process.poll() is not None:
            log.seek(0)
            detail = log.read().decode(errors="replace").strip()
            raise RuntimeError(detail or "Codex App Server exited before it was ready")
        time.sleep(0.05)
    raise RuntimeError("Codex App Server did not become ready")


def _stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def cmd_codex_launch(codex_path: str | None = None) -> int:
    """Run one private App Server and its Codex terminal client."""
    executable = codex_path or shutil.which("codex")
    if executable is None:
        raise RuntimeError("cannot find the `codex` executable on PATH")
    with tempfile.TemporaryDirectory(prefix="leaf-codex-", dir="/tmp") as directory:
        path = Path(directory) / "app-server.sock"
        endpoint = f"unix://{path}"
        environment = os.environ | {APP_SERVER_ENV: endpoint}
        with tempfile.TemporaryFile() as log:
            server = subprocess.Popen(
                [executable, "app-server", "--listen", endpoint],
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                _wait_for_app_server(path, server, log)
                return subprocess.call(
                    [executable, "--remote", endpoint],
                    env=environment,
                )
            finally:
                _stop_process(server)
