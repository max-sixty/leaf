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
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree

from websockets.exceptions import WebSocketException
from websockets.sync.client import connect, unix_connect

from .event_log import flocked, read_cursor
from .events import build_threads, spoken_turns
from .files import read_json, write_json
from .host import host_identity, message_identity, state_home
from .leases import adapter_is_live, adapter_lease_path, take_waiter_lease
from .passages import active_enclosing
from .schema import EVENTS_FILE
from .served_state.page import full_state
from .server import running_server
from .service import (
    PageTransaction,
    owned_pages,
    restore_page_claim,
    stream_reply_attempt,
    take_page_claim,
    unacknowledged,
)
from .session import Watch, acknowledge, batch_data, read_watch_pass, record_pickup
from .thread_context import (
    thread_memberships,
    thread_roots,
    thread_structure,
    thread_widgets,
)

QUEUE_TIMEOUT = 20
START_TIMEOUT = 20
DELIVERY_FORMAT = "leaf-codex-delivery-v2"
QUEUE_FORMAT = "leaf-codex-queue-v1"
APP_SERVER_ENV = "LEAF_CODEX_APP_SERVER"
STREAM_UPDATE_INTERVAL = 0.2
STREAM_TEXT_METHODS = {"item/reasoning/summaryTextDelta"}
STREAM_REPLY_METHOD = "item/agentMessage/delta"
STREAM_HEARTBEAT_METHODS = {
    "item/commandExecution/outputDelta",
    "item/fileChange/outputDelta",
    "item/mcpToolCall/progress",
}
STREAM_THROTTLED_METHODS = (
    STREAM_TEXT_METHODS | STREAM_HEARTBEAT_METHODS | {STREAM_REPLY_METHOD}
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
    """Fold one task's notifications into separate activity and response readings."""

    def __init__(self, thread_id: str):
        self.thread_id = thread_id
        self.turn_id: str | None = None
        self.details: dict[str, str] = {}
        self.text: dict[str, str] = {}
        self.message_phases: dict[str, str | None] = {}
        self.message_order: list[str] = []

    def read(self, message: dict) -> dict | None:
        """Return one transient activity, reply, or turn-completion update."""
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
            return {"turn": self.turn_id, "activity": "Starting"}

        turn_id = params.get("turnId") or self.turn_id
        if method == "turn/completed":
            turn = params["turn"]
            completed = turn["id"]
            final = self._final_text(turn)
            if self.turn_id == completed:
                self.turn_id = None
                self.details.clear()
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
            if item["type"] == "agentMessage":
                self._record_message(item)
                if item.get("text"):
                    return {
                        "turn": turn_id,
                        "reply": self._reply_update(item["id"], complete=False),
                    }
                return None
            detail = self._item_detail(item)
            if detail:
                self.details[item["id"]] = detail
            return {"turn": turn_id, "activity": detail} if detail else None

        if method == "item/completed":
            item = params["item"]
            self.details.pop(item["id"], None)
            if item["type"] == "agentMessage":
                self._record_message(item)
                return {
                    "turn": turn_id,
                    "reply": self._reply_update(item["id"], complete=True),
                }
            return None

        if method == STREAM_REPLY_METHOD:
            item_id = params["itemId"]
            combined = self.text.get(item_id, "") + params["delta"]
            self.text[item_id] = combined
            if item_id not in self.message_order:
                self.message_order.append(item_id)
                self.message_phases[item_id] = None
            return {
                "turn": turn_id,
                "reply": self._reply_update(item_id, complete=False),
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
        public = [
            self.text[item_id]
            for item_id in self.message_order
            if self.message_phases.get(item_id) in {None, "commentary"}
            and self.text.get(item_id)
        ]
        return public[-1] if public else ""

    def _reply_update(self, item_id: str, *, complete: bool) -> dict:
        return {
            "item": item_id,
            "phase": self.message_phases.get(item_id),
            "text": self._visible_text(),
            "complete": complete,
        }

    def _final_text(self, turn: dict) -> str:
        items = [
            item for item in turn.get("items", []) if item["type"] == "agentMessage"
        ]
        for item in items:
            self._record_message(item)
        final = [
            item.get("text", "")
            for item in items
            if item.get("phase") == "final_answer" and item.get("text")
        ]
        if final:
            return "\n\n".join(final)
        unknown = [
            item.get("text", "")
            for item in items
            if item.get("phase") is None and item.get("text")
        ]
        if unknown:
            return unknown[-1]
        stored = [
            self.text[item_id]
            for item_id in self.message_order
            if self.message_phases.get(item_id) == "final_answer"
            and self.text.get(item_id)
        ]
        if stored:
            return "\n\n".join(stored)
        unknown_stored = [
            self.text[item_id]
            for item_id in self.message_order
            if self.message_phases.get(item_id) is None and self.text.get(item_id)
        ]
        return unknown_stored[-1] if unknown_stored else ""

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


def project_app_server_activity(
    events: AppServerEvents,
    message: dict,
    last_stream_update: float,
    set_activity,
    clear_activity,
) -> float:
    """Project one notification with the shared streamed-update throttle."""
    update = events.read(message)
    if update is None:
        return last_stream_update
    turn_id = update["turn"]
    if update.get("completed"):
        clear_activity(events.thread_id, turn_id)
        return last_stream_update
    detail = update.get("activity")
    if detail is None and (reply := update.get("reply")):
        detail = _tail(reply["text"])
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
    """Observe one Codex task and start turns for addressed Leaf feedback."""

    def __init__(self, endpoint: str, thread_id: str):
        check_app_server_endpoint(endpoint)
        self.endpoint = endpoint
        self.thread_id = thread_id
        self.events = AppServerEvents(thread_id)
        self.stop_event = threading.Event()
        self.available = threading.Event()
        self.socket = None
        self.last_activity_update = 0.0
        self.last_reply_update = 0.0
        self.started = False
        self.request_id = 2
        self.requests: queue.Queue[tuple[dict, queue.Queue]] = queue.Queue()
        self.bindings: dict[str, dict] = {}
        self.pending_updates: dict[str, list[dict]] = {}
        self.starting_delivery = False
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
        for turn_id in list(self.bindings):
            _clear_stream_reply(self.thread_id, turn_id)

    def start_delivery(self, delivery: dict, payload: dict) -> dict | None:
        """Start or steer one Leaf-owned turn and bind its response stream."""
        if not self.available.is_set():
            return None
        answer: queue.Queue[tuple[dict | None, Exception | None]] = queue.Queue(
            maxsize=1
        )
        self.requests.put(({"delivery": delivery, "payload": payload}, answer))
        try:
            result = answer.get(timeout=START_TIMEOUT)
        except queue.Empty as error:
            raise RuntimeError(
                "Codex App Server did not start the Leaf turn"
            ) from error
        result, error = result
        if error is not None:
            raise RuntimeError(str(error)) from error
        return result

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
                    self._start_delivery(socket, *request)
                    continue
                try:
                    raw = socket.recv(timeout=0.1)
                except TimeoutError:
                    continue
                self._read(json.loads(raw))

    def _start_delivery(self, socket, request: dict, answer: queue.Queue) -> None:
        delivery = request["delivery"]
        active = self.events.turn_id
        standing = self.bindings.get(active) if active is not None else None
        if active is not None and (
            standing is None
            or (standing["page"], standing["conversation"])
            != (delivery["page"], delivery["conversation"])
        ):
            answer.put((None, None))
            return
        pending_before = set(self.pending_updates)
        try:
            self.starting_delivery = True
            result = self._send(
                socket,
                "turn/start",
                self.request_id,
                {
                    "threadId": self.thread_id,
                    "input": [],
                    "toolOutput": {
                        "name": "leaf_feedback",
                        "output": json.dumps(request["payload"], separators=(",", ":")),
                    },
                    "turnTrigger": "leaf",
                },
            )
            self.request_id += 1
            turn = result.get("turn") or {}
            turn_id = turn.get("id")
            if not turn_id:
                raise RuntimeError("Codex App Server returned no turn id")
            if active is not None and turn_id != active:
                raise RuntimeError("Codex App Server steered a different turn")
            if active is None and any(
                item.get("type") == "userMessage" for item in turn.get("items", [])
            ):
                self.pending_updates.pop(turn_id, None)
                answer.put(({"turn": turn_id, "bound": False}, None))
                return
            self._bind(turn_id, delivery)
            answer.put(({"turn": turn_id, "bound": True}, None))
        except RuntimeError:
            for turn_id in set(self.pending_updates) - pending_before:
                self.pending_updates.pop(turn_id)
            answer.put((None, None))
        except (OSError, TimeoutError, WebSocketException) as error:
            for turn_id in set(self.pending_updates) - pending_before:
                self.pending_updates.pop(turn_id)
            answer.put((None, error))
        finally:
            self.starting_delivery = False

    def _bind(self, turn_id: str, delivery: dict) -> None:
        standing = self.bindings.get(turn_id)
        if standing is None:
            standing = {**delivery, "deliveries": [delivery["id"]], "text": ""}
            self.bindings[turn_id] = standing
        else:
            standing["deliveries"].append(delivery["id"])
            standing["reply_to"] = delivery["reply_to"]
        _set_stream_reply(
            self.thread_id,
            turn_id,
            standing,
            None,
            standing.get("text", ""),
            "active",
        )
        for update in self.pending_updates.pop(turn_id, []):
            self._project_bound_update(update)

    def _restore_bindings(self, thread: dict) -> None:
        turns = {turn["id"]: turn for turn in thread.get("turns", [])}
        for turn_id, binding in list(self.bindings.items()):
            turn = turns.get(turn_id)
            if turn is None:
                _set_stream_reply(
                    self.thread_id,
                    turn_id,
                    binding,
                    None,
                    binding.get("text", ""),
                    "disconnected",
                )
                continue
            for item in turn.get("items", []):
                if item.get("type") == "agentMessage":
                    self.events._record_message(item)
            if turn.get("status") == "inProgress":
                text = self.events._visible_text()
                binding["text"] = text
                _set_stream_reply(
                    self.thread_id, turn_id, binding, None, text, "active"
                )
            else:
                self._finish_binding(
                    turn_id,
                    turn.get("status", "failed"),
                    self.events._final_text(turn),
                )

    def _read(self, message: dict) -> None:
        update = self.events.read(message)
        if update is None:
            return
        turn_id = update["turn"]
        if message.get("method") == "turn/started":
            _open_stream_turn(self.thread_id, turn_id)
        if detail := update.get("activity"):
            now = time.monotonic()
            if (
                message.get("method") in STREAM_THROTTLED_METHODS
                and now - self.last_activity_update < STREAM_UPDATE_INTERVAL
            ):
                pass
            else:
                _set_stream_activity(self.thread_id, turn_id, detail)
                self.last_activity_update = now
        if update.get("reply") is not None:
            self._project_reply(update)
        if completed := update.get("completed"):
            if turn_id in self.bindings:
                self._finish_binding(turn_id, completed, update.get("text", ""))
            elif self.starting_delivery:
                self.pending_updates.setdefault(turn_id, []).append(update)
            _clear_stream_activity(self.thread_id, turn_id)
            _close_stream_turn(self.thread_id, turn_id)

    def _project_bound_update(self, update: dict) -> None:
        if update.get("reply") is not None:
            self._project_reply(update)
        if completed := update.get("completed"):
            self._finish_binding(update["turn"], completed, update.get("text", ""))

    def _project_reply(self, update: dict) -> None:
        turn_id = update["turn"]
        binding = self.bindings.get(turn_id)
        if binding is None:
            if self.starting_delivery:
                self.pending_updates.setdefault(turn_id, []).append(update)
            return
        reply = update["reply"]
        binding["text"] = reply["text"]
        now = time.monotonic()
        if (
            not reply["complete"]
            and now - self.last_reply_update < STREAM_UPDATE_INTERVAL
        ):
            return
        _set_stream_reply(
            self.thread_id,
            turn_id,
            binding,
            reply["item"],
            reply["text"],
            "active",
        )
        self.last_reply_update = now

    def _finish_binding(self, turn_id: str, state: str, text: str) -> None:
        binding = self.bindings.pop(turn_id, None)
        if binding is None:
            return
        final = text or binding.get("text", "")
        if state == "completed":
            _commit_stream_reply(self.thread_id, turn_id, binding, final)
        else:
            _set_stream_reply(
                self.thread_id,
                turn_id,
                binding,
                None,
                final,
                state,
            )

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
                for turn_id, binding in self.bindings.items():
                    _set_stream_reply(
                        self.thread_id,
                        turn_id,
                        binding,
                        None,
                        binding.get("text", ""),
                        "disconnected",
                    )
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


def _prompt(path: Path) -> str:
    delivery = ElementTree.Element(
        "leaf-delivery",
        {"skill": "$leaf", "id": path.stem, "path": str(path)},
    )
    pointer = ElementTree.tostring(delivery, encoding="unicode")
    return f"```xml\n{pointer}\n```"


def _offer_delivery(path: Path, queue: dict) -> str:
    """Freeze one payload before offering its permanent pointer."""
    if queue["state"] == "offering":
        return _prompt(Path(queue["payload"]))

    urls = {}
    for batch in queue["batches"]:
        page = batch["page"]
        if page not in urls:
            server = running_server(Path(page))
            urls[page] = server["url"] if server else None
        batch["url"] = urls[page]

    targets = {(batch["page"], batch.get("conversation")) for batch in queue["batches"]}
    target = None
    if len(targets) == 1 and all(batch.get("reply_to") for batch in queue["batches"]):
        page, conversation = targets.pop()
        reply_to = queue["batches"][-1]["reply_to"]
        if conversation is not None and reply_to is not None:
            target = {
                "page": page,
                "conversation": conversation,
                "reply_to": reply_to,
            }

    payload_path = path.parent / "payloads" / path.name
    payload = {
        "format": DELIVERY_FORMAT,
        "id": path.stem,
        "created_at": queue["created_at"],
        "reply": target,
        "batches": [
            {key: value for key, value in batch.items() if key != "receipted"}
            for batch in queue["batches"]
        ],
    }
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(payload_path, payload)
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
    queue["payload"] = str(payload_path)
    queue["reply"] = target
    queue["state"] = "offering"
    _write_queue(path, queue)
    return _prompt(payload_path)


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

    server = running_server(page_dir)
    url = server["url"] if server else None
    data = batch_data(page_dir, transaction, fresh)
    target = _stream_target(page_dir, transaction.events, fresh)
    entry = {
        "page": data["page"],
        "session": session_id,
        "url": url,
        "threads": data["threads"],
        "handling": data["handling"],
        "events": data["events"],
        "conversation": target and target["conversation"],
        "reply_to": target and target["reply_to"],
        "receipted": False,
    }
    queue["batches"].append(entry)
    _write_queue(path, queue)
    return path, len(queue["batches"]) - 1, entry


def _stream_target(
    page_dir: Path, events: list[dict], batch: list[dict]
) -> dict | None:
    """Return the one conversation a complete batch asks Codex to answer."""
    roots = thread_roots(events)
    structure = thread_structure(events)
    memberships = thread_memberships(
        events,
        roots,
        thread_widgets(structure, roots),
        active_enclosing(page_dir),
    )
    addressed = [memberships.get(event["id"], []) for event in batch]
    if not addressed or any(len(named) != 1 for named in addressed):
        return None
    conversations = {named[0] for named in addressed}
    if len(conversations) != 1:
        return None
    conversation = conversations.pop()
    thread = build_threads(events, active_enclosing(page_dir)).get(conversation)
    if (
        thread is None
        or (thread["root"].get("response") or {}).get("kind") == "version"
    ):
        return None
    reply_to = next(
        (
            event["id"]
            for event in reversed(batch)
            if event.get("author") == "user"
            and event["kind"] in {"comment", "reply"}
            and event.get("text")
        ),
        None,
    )
    if reply_to is None:
        return None
    return {
        "page": str(page_dir),
        "conversation": conversation,
        "reply_to": reply_to,
    }


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


def _recover_delivery(
    codex_path: str,
    session_id: str,
    app_server: str | None = None,
    app_client: AppServerClient | None = None,
) -> bool:
    """Advance one durable queue or page-receipt transition."""
    lock = delivery_lock_path(session_id)
    lock.parent.mkdir(parents=True, exist_ok=True)
    with flocked(lock):
        queues = _queues(session_id)
        for path, queue in queues:
            _sync_receipts(path, queue)
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
        path, offered, prompt = queued
        direct = None
        if app_client is not None and offered.get("reply") is not None:
            direct = app_client.start_delivery(
                {"id": path.stem, **offered["reply"]},
                read_json(Path(offered["payload"])),
            )
        if direct is None:
            if app_server is None:
                queue_delivery(codex_path, session_id, prompt)
            else:
                queue_delivery(codex_path, session_id, prompt, app_server)
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

    with flocked(lock):
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
    binding: dict,
    item_id: str | None,
    text: str,
    state: str,
) -> None:
    try:
        with PageTransaction(Path(binding["page"])) as page:
            claim = page.active_claim
            if claim is None or claim["id"] != session_id:
                return
            page.set_stream_reply(
                session_id,
                turn_id,
                binding["conversation"],
                binding["reply_to"],
                item_id,
                text,
                state,
            )
    except FileNotFoundError:
        pass


def _clear_stream_reply(session_id: str, turn_id: str | None = None) -> None:
    with _locked_codex_pages(session_id) as pages:
        for page in pages:
            page.clear_stream_reply(session_id, turn_id)


def _commit_stream_reply(
    session_id: str,
    turn_id: str,
    binding: dict,
    text: str,
) -> None:
    """Atomically complete one draft as a reply, prior settlement, or partial."""
    try:
        with PageTransaction(Path(binding["page"])) as page:
            claim = page.active_claim
            if claim is None or claim["id"] != session_id:
                return
            attempt = stream_reply_attempt(turn_id)
            existing = next(
                (event for event in page.events if event.get("attempt") == attempt),
                None,
            )
            thread = build_threads(page.events, active_enclosing(page.page_dir)).get(
                binding["conversation"]
            )
            turns = spoken_turns(thread) if thread else []
            pending = bool(
                turns
                and turns[-1]["author"] == "user"
                and turns[-1]["id"] == binding["reply_to"]
            )
            if existing is None and pending and text:
                page.append_event(
                    {
                        "kind": "reply",
                        "author": "claude",
                        **message_identity(),
                        "parent": binding["reply_to"],
                        "text": text,
                        "attempt": attempt,
                    }
                )
            elif existing is None and pending:
                page.set_stream_reply(
                    session_id,
                    turn_id,
                    binding["conversation"],
                    binding["reply_to"],
                    None,
                    "",
                    "partial",
                )
                return
            page.clear_stream_reply(session_id, turn_id)
    except FileNotFoundError:
        pass


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
                queue_server = (
                    app_server
                    if app_client is not None and app_client.available.is_set()
                    else None
                )
                recovered = _recover_delivery(
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
    streamed = f" with live replies from {app_server}" if app_server else ""
    return f"Codex delivery started for task {session_id}{streamed}"


def prepare_codex_delivery(
    page_dir: Path,
    identity: dict,
    lifetime: dict,
) -> str:
    """Claim PAGE and create the pointer that opens an embedded task's first turn."""
    session_id = identity["id"]
    transition = None
    try:
        with PageTransaction(page_dir) as page:
            transition = page.take_claim(identity, lifetime)
            outstanding = {
                item["event"]
                for item in full_state(page_dir, page.events)["activity"][
                    "interactions"
                ]
                if item.get("event") is not None
            }
            batch = [
                event
                for event in unacknowledged(page.events, page.cursor)
                if event["author"] != "user" or event["id"] in outstanding
            ]
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


def accept_codex_delivery(session_id: str) -> None:
    """Record that an embedded host put the current delivery in one Codex turn."""
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
            claim_turn = page.open_turn(session_id)
            record_pickup(
                page,
                [delivered[seq] for seq in expected],
                phase="opened",
                session=session_id,
                turn=claim_turn,
            )
            acknowledge(page, max(expected))

    with flocked(lock):
        queue = read_json(path)
        if queue is None or queue["state"] != "offering":
            raise RuntimeError("the Codex delivery changed before it was accepted")
        for batch in queue["batches"]:
            batch["receipted"] = True
        queue["state"] = "accepted"
        _write_queue(path, queue)


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
