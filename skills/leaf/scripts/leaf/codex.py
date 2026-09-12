"""Detached Leaf delivery into later turns of one Codex task."""

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
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree

from websockets.sync.client import connect, unix_connect

from .conversation import cmd_reply
from .delivery import batch_data, delivery_path, freeze_delivery
from .event_log import flocked, read_cursor
from .files import read_json, write_json
from .host import host_identity, state_home
from .leases import adapter_is_live, adapter_lease_path, take_waiter_lease
from .schema import EVENTS_FILE
from .service import (
    PageTransaction,
    owned_pages,
    restore_page_claim,
    stream_reply_attempt,
    take_page_claim,
    unacknowledged,
)
from .session import Watch, acknowledge, read_watch_pass, record_pickup

QUEUE_TIMEOUT = 20
START_TIMEOUT = 20
QUEUE_FORMAT = "leaf-codex-queue-v1"
APP_SERVER_ENV = "LEAF_CODEX_APP_SERVER"
STREAM_UPDATE_INTERVAL = 0.2
STREAM_TEXT_METHODS = {"item/reasoning/summaryTextDelta"}
STREAM_MESSAGE_METHOD = "item/agentMessage/delta"
STREAM_HEARTBEAT_METHODS = {
    "item/commandExecution/outputDelta",
    "item/fileChange/outputDelta",
    "item/mcpToolCall/progress",
}
STREAM_THROTTLED_METHODS = (
    STREAM_TEXT_METHODS | STREAM_HEARTBEAT_METHODS | {STREAM_MESSAGE_METHOD}
)


@dataclass(frozen=True)
class PreparedDelivery:
    """One immutable delivery in pointer and structured forms."""

    prompt: str
    payload: dict


def stream_reply_target(payload: dict) -> dict | None:
    """Return the one plain reply address a provider message may answer."""
    responses = [
        (batch["page"], obligation["response"])
        for batch in payload["batches"]
        for event in batch["events"]
        if (obligation := event.get("obligation")) is not None
    ]
    if len(responses) != 1:
        return None
    [(page, response)] = responses
    if response["kind"] != "reply":
        return None
    return {
        "page": page,
        "reply_to": response["to"],
        "responds": response["for"],
    }


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
        # App Server completion items include complete command output. A page read can
        # therefore exceed websockets' 1 MiB message default even though the local
        # protocol and the command both completed normally.
        "max_size": None,
    }
    connection = (
        unix_connect(str(socket_path), uri="ws://localhost/rpc", **options)
        if socket_path is not None
        else connect(endpoint, **options)
    )
    # Website delivery transfers this connection to its turn-following thread, so its
    # owner closes it explicitly rather than retaining the context manager here. Enter
    # it before transfer: this is a no-op in websockets 15-16 and the supported direct
    # connection path in 17, without splitting Leaf by dependency version.
    return connection.__enter__()


def _head(text: str, limit: int = 180) -> str:
    line = " ".join(text.split())
    return line if len(line) <= limit else line[: limit - 1] + "…"


def _tail(text: str, limit: int = 240) -> str:
    line = " ".join(text.split())
    return line if len(line) <= limit else "…" + line[-(limit - 1) :]


class AppServerEvents:
    """Fold one task's notifications into activity and terminal readings."""

    def __init__(self, thread_id: str):
        self.thread_id = thread_id
        self.turn_id: str | None = None
        self.details: dict[str, str] = {}
        self.text: dict[str, str] = {}
        self.message_phases: dict[str, str | None] = {}
        self.message_order: list[str] = []
        self.item_started_at: dict[str, int] = {}

    def read(self, message: dict) -> dict | None:
        """Return one transient activity or turn-completion update."""
        method = message.get("method")
        params = message.get("params") or {}
        message_thread = params.get("threadId")
        if message_thread is not None and message_thread != self.thread_id:
            return None

        if method == "turn/started":
            self.turn_id = params["turn"]["id"]
            self.details.clear()
            self.text.clear()
            self.message_phases.clear()
            self.message_order.clear()
            self.item_started_at.clear()
            return {"turn": self.turn_id, "activity": "Starting"}

        turn_id = params.get("turnId") or self.turn_id
        if method == "turn/completed":
            turn = params["turn"]
            completed = turn["id"]
            final = self.final_text(turn)
            if self.turn_id == completed:
                self.turn_id = None
                self.details.clear()
                self.item_started_at.clear()
            return {
                "turn": completed,
                "completed": turn.get("status", "completed"),
                "text": final,
            }
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
            return {"turn": turn_id, "activity": _head(current)} if current else None

        if method == "item/started":
            item = params["item"]
            lifecycle = self._item_lifecycle(params, "started")
            if item["type"] == "agentMessage":
                self._record_message(item)
                if item.get("phase") == "commentary":
                    return {"turn": turn_id, "item": lifecycle}
                if item.get("text"):
                    return {
                        "turn": turn_id,
                        "item": lifecycle,
                        "message": self._message_update(item["id"], complete=False),
                    }
                return {"turn": turn_id, "item": lifecycle}
            detail = self._item_detail(item)
            if detail:
                self.details[item["id"]] = detail
            return {
                "turn": turn_id,
                "item": lifecycle,
                **({"activity": detail} if detail else {}),
            }

        if method == "item/completed":
            item = params["item"]
            lifecycle = self._item_lifecycle(params, "completed")
            self.details.pop(item["id"], None)
            if item["type"] == "agentMessage":
                self._record_message(item)
                if item.get("phase") == "commentary":
                    return {"turn": turn_id, "item": lifecycle}
                return {
                    "turn": turn_id,
                    "item": lifecycle,
                    "message": self._message_update(item["id"], complete=True),
                }
            return {"turn": turn_id, "item": lifecycle}

        if method == STREAM_MESSAGE_METHOD:
            item_id = params["itemId"]
            combined = self.text.get(item_id, "") + params["delta"]
            self.text[item_id] = combined
            if item_id not in self.message_order:
                self.message_order.append(item_id)
                self.message_phases[item_id] = None
            if self.message_phases.get(item_id) == "commentary":
                return None
            return {
                "turn": turn_id,
                "message": self._message_update(item_id, complete=False),
            }

        if method in STREAM_TEXT_METHODS:
            item_id = params["itemId"]
            combined = self.text.get(item_id, "") + params["delta"]
            self.text[item_id] = combined
            return {"turn": turn_id, "activity": "Thinking — " + _tail(combined)}

        if method in STREAM_HEARTBEAT_METHODS:
            detail = self.details.get(params["itemId"])
            return {"turn": turn_id, "activity": detail} if detail else None

        if method in {
            "item/commandExecution/requestApproval",
            "item/fileChange/requestApproval",
            "item/permissions/requestApproval",
            "item/tool/requestUserInput",
        }:
            return {"turn": turn_id, "activity": "Waiting for input in Codex"}

        if method == "thread/status/changed":
            flags = params.get("status", {}).get("activeFlags", [])
            if "waitingOnApproval" in flags or "waitingOnUserInput" in flags:
                return {"turn": turn_id, "activity": "Waiting for input in Codex"}
        return None

    def _record_message(self, item: dict) -> None:
        item_id = item["id"]
        if item_id not in self.message_order:
            self.message_order.append(item_id)
        self.message_phases[item_id] = item.get("phase")
        self.text[item_id] = item.get("text", "")

    def _visible_text(self) -> str:
        final = [
            self.text[item_id]
            for item_id in self.message_order
            if self.message_phases.get(item_id) == "final_answer"
            and self.text.get(item_id)
        ]
        if final:
            return "\n\n".join(final)
        unknown = [
            self.text[item_id]
            for item_id in self.message_order
            if self.message_phases.get(item_id) is None and self.text.get(item_id)
        ]
        return unknown[-1] if unknown else ""

    def final_text(self, turn: dict) -> str:
        """Return only completed final-answer content suitable for publication."""
        items = [
            item for item in turn.get("items", []) if item.get("type") == "agentMessage"
        ]
        for item in items:
            self._record_message(item)
        return "\n\n".join(
            item.get("text", "")
            for item in items
            if item.get("phase") == "final_answer" and item.get("text")
        )

    def _message_update(self, item_id: str, *, complete: bool) -> dict:
        return {
            "item": item_id,
            "phase": self.message_phases.get(item_id),
            "text": self._visible_text(),
            "complete": complete,
        }

    def _item_lifecycle(self, params: dict, state: str) -> dict:
        """Return the App Server's content-free item timing vocabulary."""
        item = params["item"]
        item_id = item["id"]
        if state == "started":
            at = params["startedAtMs"]
            self.item_started_at[item_id] = at
            return {
                "id": item_id,
                "type": item["type"],
                "state": state,
                "atMs": at,
            }
        at = params["completedAtMs"]
        started_at = self.item_started_at.pop(item_id, None)
        return {
            "id": item_id,
            "type": item["type"],
            "state": state,
            "atMs": at,
            **({"durationMs": at - started_at} if started_at is not None else {}),
            **({"status": item["status"]} if item.get("status") else {}),
            **(
                {"exitCode": item["exitCode"]}
                if item.get("exitCode") is not None
                else {}
            ),
        }

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


class AppServerReplyStream:
    """Project and commit one App Server final answer as its Leaf reply."""

    def __init__(
        self,
        session_id: str,
        turn_id: str,
        target: dict,
    ):
        self.session_id = session_id
        self.turn_id = turn_id
        self.target = dict(target)
        self.text = ""
        self.last_update = 0.0
        _set_stream_reply(session_id, turn_id, self.target, None, "", "active")

    def update(self, update: dict | None) -> None:
        """Publish a final-answer item update, throttling only partial deltas."""
        message = update.get("message") if update is not None else None
        if message is None or message["phase"] != "final_answer":
            return
        self.text = message["text"]
        now = time.monotonic()
        if not message["complete"] and now - self.last_update < STREAM_UPDATE_INTERVAL:
            return
        _set_stream_reply(
            self.session_id,
            self.turn_id,
            self.target,
            message["item"],
            self.text,
            "active",
            settles=message["complete"] and bool(self.text),
        )
        self.last_update = now

    def restore(self, text: str) -> None:
        """Restore a still-running final answer after reconnecting."""
        self.text = text
        _set_stream_reply(
            self.session_id,
            self.turn_id,
            self.target,
            None,
            text,
            "active",
        )

    def finish(self, state: str, text: str = "") -> BaseException | None:
        """Commit completed text, returning a rejection after making it visible."""
        final = text or self.text
        if state == "completed" and final:
            try:
                _commit_stream_reply(
                    self.session_id,
                    self.turn_id,
                    self.target,
                    final,
                )
            except (OSError, RuntimeError, SystemExit, ValueError) as error:
                _set_stream_reply_state(
                    self.session_id,
                    self.turn_id,
                    {**self.target, "text": final},
                    "failed",
                )
                return error
            return None
        _set_stream_reply_state(
            self.session_id,
            self.turn_id,
            {**self.target, "text": final},
            state if state != "completed" else "partial",
        )
        return None

    def disconnect(self) -> None:
        """Keep partial text visible but mark its provider connection lost."""
        _set_stream_reply_state(
            self.session_id,
            self.turn_id,
            {**self.target, "text": self.text},
            "disconnected",
        )


def project_app_server_activity(
    events: AppServerEvents,
    message: dict,
    update: dict | None,
    last_stream_update: float,
    set_activity,
    clear_activity,
) -> float:
    """Project one notification with the shared streamed-update throttle."""
    if update is None:
        return last_stream_update
    turn_id = update["turn"]
    if update.get("completed"):
        clear_activity(events.thread_id, turn_id)
        return last_stream_update
    detail = update.get("activity")
    if detail is None and (message_update := update.get("message")):
        detail = _tail(message_update["text"])
    if detail is None:
        return last_stream_update
    now = time.monotonic()
    if (
        message.get("method") in STREAM_THROTTLED_METHODS
        and now - last_stream_update < STREAM_UPDATE_INTERVAL
    ):
        return last_stream_update
    set_activity(events.thread_id, turn_id, detail)
    return now


class AppServerClient:
    """Observe one Codex task and open idle turns with Leaf deliveries."""

    def __init__(self, endpoint: str, thread_id: str):
        check_app_server_endpoint(endpoint)
        self.endpoint = endpoint
        self.thread_id = thread_id
        self.events = AppServerEvents(thread_id)
        self.stop_event = threading.Event()
        self.available = threading.Event()
        self.socket = None
        self.last_activity_update = 0.0
        self.started = False
        self.request_id = 2
        self.requests: queue.Queue[tuple[dict, queue.Queue]] = queue.Queue()
        self.bindings: dict[str, AppServerReplyStream] = {}
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
        for stream in self.bindings.values():
            stream.disconnect()

    def start_delivery(self, payload: dict) -> dict | None:
        """Open an idle turn; leave active tasks to the durable queue."""
        if not self.available.is_set():
            return None
        answer: queue.Queue[tuple[dict | None, Exception | None]] = queue.Queue(
            maxsize=1
        )
        self.requests.put((payload, answer))
        result = answer.get()
        result, error = result
        if error is not None:
            raise RuntimeError(str(error)) from error
        return result

    def _send(
        self,
        socket,
        method: str,
        request_id: int,
        params: dict,
        pending: list[dict] | None = None,
    ) -> dict:
        socket.send(json.dumps({"method": method, "id": request_id, "params": params}))
        while not self.stop_event.is_set():
            raw = socket.recv(timeout=START_TIMEOUT)
            message = json.loads(raw)
            if message.get("id") == request_id and "method" not in message:
                if error := message.get("error"):
                    raise RuntimeError(error.get("message") or str(error))
                return message.get("result") or {}
            if pending is None:
                self._read(message)
            else:
                pending.append(message)
        raise RuntimeError("Codex App Server client stopped")

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
                {"threadId": self.thread_id, "excludeTurns": False},
            )
            resumed = result.get("thread", {})
            self._restore_bindings(resumed)
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
                    request = self.requests.get_nowait()
                except queue.Empty:
                    request = None
                if request is not None:
                    try:
                        self._start_delivery(socket, *request)
                    except Exception as error:
                        request[1].put((None, error))
                        raise
                    continue
                try:
                    raw = socket.recv(timeout=0.1)
                except TimeoutError:
                    continue
                self._read(json.loads(raw))

    def _start_delivery(self, socket, payload: dict, answer: queue.Queue) -> None:
        if self.events.turn_id is not None:
            answer.put((None, None))
            return
        pending: list[dict] = []
        try:
            result = self._send(
                socket,
                "turn/start",
                self.request_id,
                {
                    "threadId": self.thread_id,
                    "input": [],
                    "toolOutput": {
                        "name": "leaf_delivery",
                        "output": json.dumps(payload, separators=(",", ":")),
                    },
                    "turnTrigger": "leaf",
                },
                pending,
            )
        except RuntimeError:
            answer.put((None, None))
            return
        self.request_id += 1
        turn = result.get("turn") or {}
        turn_id = turn.get("id")
        if not turn_id:
            raise RuntimeError("Codex App Server returned no turn id")
        if any(item.get("type") == "userMessage" for item in turn.get("items", [])):
            for message in pending:
                self._read(message)
            answer.put((None, None))
            return
        accept_codex_delivery(self.thread_id, turn=turn_id)
        if target := stream_reply_target(payload):
            self._bind(turn_id, target)
        for message in pending:
            self._read(message)
        answer.put(({"turn": turn_id}, None))

    def _bind(self, turn_id: str, target: dict) -> None:
        self.bindings[turn_id] = AppServerReplyStream(self.thread_id, turn_id, target)

    def _restore_bindings(self, thread: dict) -> None:
        turns = {turn["id"]: turn for turn in thread.get("turns", [])}
        for turn_id, stream in list(self.bindings.items()):
            turn = turns.get(turn_id)
            if turn is None:
                stream.disconnect()
                continue
            if turn.get("status") == "inProgress":
                stream.restore(self.events.final_text(turn))
            else:
                error = self._finish_binding(
                    turn_id,
                    turn.get("status", "failed"),
                    self.events.final_text(turn),
                )
                _close_stream_turn(self.thread_id, turn_id)
                if self.events.turn_id == turn_id:
                    self.events.turn_id = None
                if error is not None:
                    print(
                        f"Codex final reply rejected: {error}",
                        file=sys.stderr,
                        flush=True,
                    )

    def _read(self, message: dict) -> None:
        update = self.events.read(message)
        if update is None:
            return
        turn_id = update["turn"]
        if message.get("method") == "turn/started":
            _open_stream_turn(self.thread_id, turn_id)
        self.last_activity_update = project_app_server_activity(
            self.events,
            message,
            update,
            self.last_activity_update,
            _set_stream_activity,
            _clear_stream_activity,
        )
        if stream := self.bindings.get(turn_id):
            stream.update(update)
        if completed := update.get("completed"):
            error = self._finish_binding(turn_id, completed, update.get("text", ""))
            _close_stream_turn(self.thread_id, turn_id)
            if error is not None:
                print(
                    f"Codex final reply rejected: {error}",
                    file=sys.stderr,
                    flush=True,
                )

    def _finish_binding(
        self, turn_id: str, state: str, text: str
    ) -> BaseException | None:
        stream = self.bindings.pop(turn_id, None)
        if stream is None:
            return None
        return stream.finish(state, text)

    def _run(self) -> None:
        failures = 0
        while not self.stop_event.is_set():
            try:
                self._connect()
                failures = 0
            # This is the observer thread's recovery boundary: no connection or
            # notification failure may leave the adapter marked available.
            except Exception as error:  # noqa: BLE001
                self.available.clear()
                _clear_stream_activity(self.thread_id)
                for stream in self.bindings.values():
                    stream.disconnect()
                while True:
                    try:
                        _, answer = self.requests.get_nowait()
                    except queue.Empty:
                        break
                    answer.put((None, error))
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


def queue_path(session_id: str, delivery_id: str) -> Path:
    return delivery_dir(session_id) / f"{delivery_id}.json"


def _archive_queue(path: Path, queue: dict) -> None:
    """Move completed queue state out of the adapter's hot scan."""
    if queue["state"] == "accepted" and all(
        batch["receipted"] for batch in queue["batches"]
    ):
        history_path = path.parent / "history" / path.name
        history_path.parent.mkdir(parents=True, exist_ok=True)
        path.replace(history_path)


def _write_queue(path: Path, queue: dict) -> None:
    write_json(path, queue)
    _archive_queue(path, queue)


def adapter_start_lock_path(session_id: str) -> Path:
    return state_home() / "sessions" / f"{_session_key(session_id)}.start"


def _prompt(delivery_id: str) -> str:
    delivery = ElementTree.Element(
        "leaf-delivery", {"id": delivery_id, "operation": "delivery read"}
    )
    pointer = ElementTree.tostring(delivery, encoding="unicode")
    return f"```xml\n{pointer}\n```"


def _offer_delivery(path: Path, queue: dict) -> PreparedDelivery:
    """Freeze one payload before offering its permanent pointer."""
    if queue["state"] == "offering":
        payload_path = delivery_path(path.stem)
        payload = read_json(payload_path)
        if payload is None:
            raise RuntimeError("the Codex delivery payload is missing")
        return PreparedDelivery(_prompt(path.stem), payload)

    payload = freeze_delivery(
        queue["batches"],
        delivery_id=path.stem,
        created_at=queue["created_at"],
    )
    queue["batches"] = [
        {
            "page": batch["page"],
            "session": batch["session"],
            "events": [
                {"seq": event["seq"], "id": event["id"]} for event in batch["events"]
            ],
            "receipted": False,
        }
        for batch in queue["batches"]
    ]
    queue["state"] = "offering"
    _write_queue(path, queue)
    return PreparedDelivery(_prompt(path.stem), payload)


def _queues(session_id: str) -> list[tuple[Path, dict]]:
    directory = delivery_dir(session_id)
    if not directory.is_dir():
        return []
    records = [
        (path, queue)
        for path in directory.glob("*.json")
        if (queue := read_json(path)) is not None
        and queue.get("format") == QUEUE_FORMAT
    ]
    return sorted(records, key=lambda item: (item[1]["created_at"], item[0].name))


def _collecting_queue(
    session_id: str,
    queues: list[tuple[Path, dict]] | None = None,
) -> tuple[Path, dict] | None:
    records = _queues(session_id) if queues is None else queues
    current = [
        (path, queue) for path, queue in records if queue["state"] == "collecting"
    ]
    if len(current) > 1:
        raise RuntimeError(
            f"Codex task {session_id} has multiple collecting Leaf deliveries"
        )
    return current[0] if current else None


def _append_batch(
    session_id: str,
    page_dir: Path,
    transaction: PageTransaction,
    batch: list[dict],
) -> tuple[Path, int, dict] | None:
    """Append fresh events to the task's one collecting queue."""
    current = _collecting_queue(session_id)
    if current is None:
        path = queue_path(session_id, str(uuid.uuid4()))
        path.parent.mkdir(parents=True, exist_ok=True)
        queue = {
            "format": QUEUE_FORMAT,
            "state": "collecting",
            "created_at": time.time(),
            "batches": [],
        }
    else:
        path, queue = current

    delivered = {
        (entry["page"], event["seq"], event["id"])
        for entry in queue["batches"]
        for event in entry["events"]
    }
    fresh = [
        event
        for event in batch
        if (str(page_dir), event["seq"], event["id"]) not in delivered
    ]
    if not fresh:
        return None

    data = batch_data(page_dir, transaction, fresh)
    entry = {
        "page": data["page"],
        "session": session_id,
        "through_seq": data["through_seq"],
        "conversations": data["conversations"],
        "handling": data["handling"],
        "events": data["events"],
        "receipted": False,
    }
    queue["batches"].append(entry)
    _write_queue(path, queue)
    return path, len(queue["batches"]) - 1, entry


def capture_batch(session_id: str, reading) -> bool:
    """Persist one watcher batch in the session's collecting queue."""
    lock = delivery_lock_path(session_id)
    lock.parent.mkdir(parents=True, exist_ok=True)
    with flocked(lock):
        captured = _append_batch(
            session_id,
            reading.page_dir,
            reading.transaction,
            reading.batch,
        )
    return captured is not None


def _finish_batch(batch: dict, transport: dict | None = None) -> None:
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
                phase=(transport or {}).get("phase", "queued"),
                session=batch["session"],
                turn=(transport or {}).get("turn"),
            )
            acknowledge(page, max(expected))
    except FileNotFoundError:
        pass


def _page_acknowledged(batch: dict) -> bool:
    page_dir = Path(batch["page"])
    if not (page_dir / EVENTS_FILE).is_file():
        return True
    return read_cursor(page_dir) >= max(event["seq"] for event in batch["events"])


def _sync_receipts(path: Path, queue: dict) -> None:
    """Persist page receipts before archiving completed queue state."""
    changed = False
    for batch in queue["batches"]:
        if not batch["receipted"] and _page_acknowledged(batch):
            batch["receipted"] = True
            changed = True
    if changed:
        _write_queue(path, queue)
    else:
        _archive_queue(path, queue)


def _record_receipt(path: Path, batch_index: int) -> None:
    queue = read_json(path)
    if queue is not None and not queue["batches"][batch_index]["receipted"]:
        queue["batches"][batch_index]["receipted"] = True
        _write_queue(path, queue)


def _recover_receipt(session_id: str) -> bool:
    """Reconcile one accepted batch with its page, regardless of ownership."""
    lock = delivery_lock_path(session_id)
    lock.parent.mkdir(parents=True, exist_ok=True)
    with flocked(lock):
        queues = _queues(session_id)
        for path, queue in queues:
            _sync_receipts(path, queue)
        pending = min(
            (
                (path, index, dict(batch), queue.get("transport"))
                for path, queue in _queues(session_id)
                if queue["state"] == "accepted"
                for index, batch in enumerate(queue["batches"])
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
    path, batch_index, batch, transport = pending
    _finish_batch(batch, transport)
    with flocked(lock):
        _record_receipt(path, batch_index)
    return True


def _offer_queued_delivery(
    codex_path: str,
    session_id: str,
    app_server: str | None = None,
    app_client: AppServerClient | None = None,
) -> bool:
    """Offer one collecting delivery through the selected Codex transport."""
    lock = delivery_lock_path(session_id)
    lock.parent.mkdir(parents=True, exist_ok=True)
    with flocked(lock):
        queues = _queues(session_id)
        unoffered = next(
            (
                (path, queue)
                for path, queue in queues
                if queue["state"] in {"collecting", "offering"}
            ),
            None,
        )
        queued = None
        if unoffered is not None:
            path, queue = unoffered
            queued = path, queue, _offer_delivery(path, queue)
    if queued is not None:
        path, _offered, prepared = queued
        direct = None
        if app_client is not None:
            direct = app_client.start_delivery(prepared.payload)
        if direct is None:
            if app_server is None:
                queue_delivery(codex_path, session_id, prepared.prompt)
            else:
                queue_delivery(codex_path, session_id, prepared.prompt, app_server)
            transport = {"phase": "queued", "turn": None}
        else:
            transport = {"phase": "opened", "turn": direct["turn"]}
        with flocked(lock):
            queue = read_json(path)
            if queue is not None and queue["state"] == "offering":
                queue["state"] = "accepted"
                queue["transport"] = transport
                _write_queue(path, queue)
        return True
    return False


def _has_delivery_work(session_id: str) -> bool:
    with flocked(delivery_lock_path(session_id)):
        return any(
            queue["state"] != "accepted"
            or any(not batch["receipted"] for batch in queue["batches"])
            for _, queue in _queues(session_id)
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


def _set_stream_reply(
    session_id: str,
    turn_id: str,
    target: dict,
    item_id: str | None,
    text: str,
    state: str,
    *,
    settles: bool = False,
) -> None:
    try:
        with PageTransaction(Path(target["page"])) as page:
            claim = page.active_claim
            if (
                claim is None
                or claim["id"] != session_id
                or claim.get("turn") != turn_id
                or claim.get("turn_closed") is not None
            ):
                return
            page.set_stream_reply(
                session_id,
                turn_id,
                target["reply_to"],
                target["responds"],
                item_id,
                text,
                state,
                settles=settles,
            )
    except FileNotFoundError:
        pass


def _set_stream_reply_state(
    session_id: str, turn_id: str, target: dict, state: str
) -> None:
    _set_stream_reply(
        session_id,
        turn_id,
        target,
        None,
        target.get("text", ""),
        state,
    )


def _commit_stream_reply(
    session_id: str,
    turn_id: str,
    target: dict,
    text: str,
) -> dict | None:
    """Commit one completed provider message through Leaf's reply contract."""
    page_dir = Path(target["page"])
    try:
        with PageTransaction(page_dir) as page:
            claim = page.active_claim
            if (
                claim is None
                or claim["id"] != session_id
                or claim.get("turn") != turn_id
                or claim.get("turn_closed") is not None
            ):
                return None
            identity = {"agent": claim["agent"], "session": session_id}
        accepted = cmd_reply(
            page_dir,
            target["reply_to"],
            text,
            "",
            for_event=target["responds"],
            attempt=stream_reply_attempt(turn_id),
            skip_if_settled=True,
            identity=identity,
            validate_source=True,
        )
        with PageTransaction(page_dir) as page:
            page.clear_stream_reply(session_id, turn_id)
        return accepted
    except FileNotFoundError:
        return None


def _open_stream_turn(session_id: str, turn_id: str) -> None:
    with _locked_codex_pages(session_id) as pages:
        for page in pages:
            page.open_turn(session_id, turn_id)


def _close_stream_turn(session_id: str, turn_id: str) -> None:
    with _locked_codex_pages(session_id) as pages:
        for page in pages:
            page.close_turn(session_id, turn_id)


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
    app_client = None
    start_lock = adapter_start_lock_path(identity["id"])
    start_lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        check_queue_command(codex_path)
        if app_server is not None:
            app_client = AppServerClient(app_server, identity["id"])
            app_client.start()
        if ready_fd is not None:
            os.write(ready_fd, b'{"ready":true}\n')
            os.close(ready_fd)
            ready_fd = None
        failures = 0
        while True:
            try:
                recovered = _recover_receipt(identity["id"])
                if not recovered:
                    with flocked(start_lock):
                        if not owned_pages(identity["id"]):
                            watch.release()
                            lease.close()
                            leases_released = True
                            return 0
                    queue_server = (
                        app_server
                        if app_client is not None and app_client.available.is_set()
                        else None
                    )
                    recovered = _offer_queued_delivery(
                        codex_path,
                        identity["id"],
                        queue_server,
                        app_client if queue_server is not None else None,
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
                with flocked(start_lock):
                    captured = False
                    reading = read_watch_pass(watch, None, deliver=capture)
                    if captured or (reading.outcome is None and reading.live):
                        continue
                    if owned_pages(identity["id"]) and _has_delivery_work(
                        identity["id"]
                    ):
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
        if app_client is not None:
            app_client.stop()
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
    executable = str(Path(executable).absolute())
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
                    cwd=state_home(),
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
    connected = f" through App Server {app_server}" if app_server else ""
    return f"Codex delivery started for task {session_id}{connected}"


def prepare_codex_delivery(
    page_dir: Path,
    identity: dict,
    lifetime: dict,
) -> PreparedDelivery:
    """Claim PAGE and freeze the input for an embedded task's first turn."""
    session_id = identity["id"]
    transition = None
    try:
        with PageTransaction(page_dir) as page:
            transition = page.take_claim(identity, lifetime)
            batch = unacknowledged(page.events, page.cursor)
            if not batch:
                raise RuntimeError("the page has no Leaf input to deliver")
            lock = delivery_lock_path(session_id)
            lock.parent.mkdir(parents=True, exist_ok=True)
            with flocked(lock):
                pending = next(
                    (
                        (path, queue)
                        for path, queue in _queues(session_id)
                        if queue["state"] in {"collecting", "offering"}
                    ),
                    None,
                )
                if pending is not None:
                    return _offer_delivery(*pending)
                captured = _append_batch(
                    session_id,
                    page_dir,
                    page,
                    batch,
                )
                if captured is None:
                    raise RuntimeError("the page input is already in a Codex delivery")
                path, _, _ = captured
                return _offer_delivery(path, read_json(path))
    except BaseException:
        restore_page_claim(page_dir, transition)
        raise


def accept_codex_delivery(
    session_id: str,
    *,
    phase: str = "opened",
    turn: str | None = None,
) -> list[dict]:
    """Record and describe batches accepted by one Codex carrier."""
    if phase not in {"queued", "opened"}:
        raise ValueError(f"unknown delivery phase {phase!r}")
    lock = delivery_lock_path(session_id)
    with flocked(lock):
        offered = [
            (path, queue)
            for path, queue in _queues(session_id)
            if queue["state"] == "offering"
        ]
        if len(offered) != 1:
            raise RuntimeError("the Codex task has no delivery to accept")
        path, queue = offered[0]
        batches = [dict(batch) for batch in queue["batches"]]

    accepted = []
    for batch in batches:
        page_dir = Path(batch["page"])
        expected = {event["seq"]: event["id"] for event in batch["events"]}
        with PageTransaction(page_dir) as page:
            claim = page.active_claim
            if claim is None or claim["id"] != session_id:
                raise RuntimeError("the Codex delivery no longer owns its page")
            delivered = {
                event["seq"]: event
                for event in page.events
                if min(expected) <= event["seq"] <= max(expected)
            }
            if not all(
                delivered.get(seq, {}).get("id") == event_id
                for seq, event_id in expected.items()
            ):
                raise RuntimeError("the Codex delivery no longer matches its page log")
            claim_turn = page.open_turn(session_id, turn) if phase == "opened" else None
            record_pickup(
                page,
                [delivered[seq] for seq in expected],
                phase=phase,
                session=session_id,
                turn=claim_turn,
            )
            acknowledge(page, max(expected))
            accepted.append(
                {
                    "page": page_dir,
                    "events": tuple(expected.values()),
                    "turn": claim_turn,
                }
            )

    with flocked(lock):
        queue = read_json(path)
        if queue is None or queue["state"] != "offering":
            raise RuntimeError("the Codex delivery changed before it was accepted")
        for batch in queue["batches"]:
            batch["receipted"] = True
        queue["state"] = "accepted"
        queue["transport"] = {"phase": phase, "turn": turn}
        _write_queue(path, queue)
    return accepted


def open_queued_codex_delivery(
    page_dir: Path,
    session_id: str,
    event_ids: tuple[str, ...],
    turn: str,
) -> str:
    """Record when a durable queued delivery actually enters its Codex turn."""
    with PageTransaction(page_dir) as page:
        claim = page.active_claim
        if claim is None or claim["id"] != session_id:
            raise RuntimeError("the queued Codex delivery no longer owns its page")
        by_id = {event["id"]: event for event in page.events}
        if any(event_id not in by_id for event_id in event_ids):
            raise RuntimeError("the queued Codex delivery no longer matches its page")
        leaf_turn = page.open_turn(session_id, turn)
        if leaf_turn is None:
            raise RuntimeError("the queued Codex turn could not open its page claim")
        record_pickup(
            page,
            [by_id[event_id] for event_id in event_ids],
            phase="opened",
            session=session_id,
            turn=leaf_turn,
        )
        return leaf_turn


def abandon_codex_delivery(session_id: str, event_id: str) -> None:
    """Retire an unaccepted delivery after its triggering event was settled."""
    lock = delivery_lock_path(session_id)
    with flocked(lock):
        matching = [
            path
            for path, queue in _queues(session_id)
            if queue["state"] == "offering"
            and any(
                event["id"] == event_id
                for batch in queue["batches"]
                for event in batch["events"]
            )
        ]
        if len(matching) > 1:
            raise RuntimeError("the Codex task has duplicate offered deliveries")
        if matching:
            matching[0].unlink()


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
