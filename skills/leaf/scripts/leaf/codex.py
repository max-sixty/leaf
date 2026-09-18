"""Leaf's side of one Codex task, shared by every carrier that holds one open.

A carrier is whatever keeps a Codex task reachable on Leaf's behalf: the detached
process in `codex_adapter.py`, which observes a task it does not own, and the
website's embedded host in `worker/server.py`, which owns the tasks it starts.
What both need is here — the App Server connection and the request shapes one Leaf
turn is opened with, the fold from a task's notifications into activity and
final-answer readings, the writers that put those readings on a claimed page, and
the durable records a delivery passes through.

A delivery record under the state home is the handoff between Leaf capturing a
reader's moves and a carrier taking them. One record is offered once, accepted once,
and receipted per page batch, whichever transport carried it — an App Server turn or
the `codex queue` command — so preparing, accepting, opening and abandoning one live
here rather than beside either carrier. The immutable payload itself belongs to
`delivery`; what this module keeps is which task holds it and how far it has got.

Which delivery is offered, and when, is a carrier's own policy: the adapter's queue
loop and the website's turn follower each keep theirs.
"""

import hashlib
import json
import subprocess
import time
import uuid
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree

from websockets.sync.client import connect, unix_connect

from .conversation import DeliveryReply
from .delivery import (
    DELIVERY_FORMAT,
    batch_data,
    current_responses,
    delivery_path,
    freeze_delivery,
)
from .event_log import flocked
from .files import read_json, write_json
from .host import Harness, state_home
from .service import (
    PageTransaction,
    owned_pages,
    restore_page_claim,
    unacknowledged,
)
from .session import acknowledge, record_pickup

START_TIMEOUT = 20
QUEUE_FORMAT = "leaf-codex-queue-v1"
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


class AppServerRequestRejected(RuntimeError):
    """The App Server definitively rejected a request before executing it."""


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


def app_server_connect(endpoint: str):
    """Open one connection to a local App Server, by socket or by loopback."""
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


def stop_app_server(process: subprocess.Popen) -> None:
    """Stop an App Server this process spawned, killing one that will not exit."""
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def retry_delay(failures: int) -> int:
    """Seconds to hold off after this many consecutive failures, the first being 1.

    Every carrier retries the same kinds of failure — a connection that dropped, a
    turn the provider refused, a delivery that could not be offered — so they hold
    off on one ladder: a second after the first, doubling to a half-minute ceiling.
    The first retry is prompt because the common failure is a provider restart that
    is already over by the time anything noticed.
    """
    return min(30, 2 ** min(failures - 1, 5))


def app_server_request(
    socket,
    method: str,
    request_id: int,
    params: dict,
    on_notification=None,
    *,
    stopped=None,
) -> dict:
    """Make one request on an App Server connection and return its result.

    A notification read while waiting is not a stray: App Server sends a turn's own
    `turn/started` behind the response that started it, and dropping it would lose
    the binding a caller is watching for. Each caller says what to do with those
    messages — buffer them to replay in arrival order, or fold them immediately —
    because that choice is what separates a stream it is following from a snapshot
    request whose answer outranks everything sent before it.

    `stopped` lets a client being shut down stop waiting on a peer that is still
    talking.
    """
    socket.send(json.dumps({"method": method, "id": request_id, "params": params}))
    while stopped is None or not stopped():
        message = json.loads(socket.recv(timeout=START_TIMEOUT))
        if message.get("id") == request_id and "method" not in message:
            if error := message.get("error"):
                raise AppServerRequestRejected(error.get("message") or str(error))
            return message.get("result") or {}
        if on_notification is not None:
            on_notification(message)
    raise RuntimeError("Codex App Server client stopped")


def app_server_handshake(
    socket,
    request_id: int,
    name: str,
    title: str,
    on_notification=None,
) -> None:
    """Complete the exchange every Leaf App Server connection opens with."""
    app_server_request(
        socket,
        "initialize",
        request_id,
        _initialize_params(name, title),
        on_notification,
    )
    socket.send(json.dumps({"method": "initialized", "params": {}}))


def app_server_turn_start_params(thread_id: str, payload: dict) -> dict:
    """Build the one App Server request shape for a Leaf delivery turn."""
    return {
        "threadId": thread_id,
        "clientUserMessageId": payload["id"],
        "input": [],
        "toolOutput": {
            "name": "leaf_delivery",
            "output": json.dumps(payload, separators=(",", ":")),
        },
        "turnTrigger": "leaf",
    }


def _initialize_params(name: str, title: str) -> dict:
    """Name the Leaf client one connection introduces itself as."""
    return {
        "clientInfo": {"name": name, "title": title, "version": "0"},
        "capabilities": {"requestAttestation": False},
    }


def app_server_delivery_id(message: dict) -> str | None:
    """Read the exact Leaf delivery identity carried by one provider notification."""
    method = message.get("method")
    params = message.get("params") or {}
    if method == "turn/started":
        items = params.get("turn", {}).get("items", [])
    elif method in {"item/started", "item/completed"}:
        items = [params.get("item") or {}]
    else:
        return None

    found = set()
    for item in items:
        if (
            item.get("type") == "functionCallOutput"
            and item.get("name") == "leaf_delivery"
            and isinstance(item.get("output"), str)
        ):
            try:
                payload = json.loads(item["output"])
            except json.JSONDecodeError:
                continue
            if (
                isinstance(payload, dict)
                and payload.get("format") == DELIVERY_FORMAT
                and isinstance(payload.get("id"), str)
            ):
                found.add(payload["id"])
            continue
        if item.get("type") != "userMessage":
            continue
        for content in item.get("content", []):
            if content.get("type") != "text":
                continue
            lines = content.get("text", "").strip().splitlines()
            if len(lines) != 3 or lines[0] != "```xml" or lines[2] != "```":
                continue
            try:
                pointer = ElementTree.fromstring(lines[1])
            except ElementTree.ParseError:
                continue
            if (
                pointer.tag == "leaf-delivery"
                and set(pointer.attrib) == {"id", "operation"}
                and pointer.attrib["operation"] == "delivery claim"
            ):
                found.add(pointer.attrib["id"])
    return next(iter(found)) if len(found) == 1 else None


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

    def restore_turn(self, turn: dict) -> str:
        """Replace transient message state with one resumed provider turn."""
        self.turn_id = turn["id"]
        self.details.clear()
        self.text.clear()
        self.message_phases.clear()
        self.message_order.clear()
        self.item_started_at.clear()
        for item in turn.get("items", []):
            if item.get("type") == "agentMessage":
                self._record_message(item)
        return self.final_text(turn)

    def read(self, message: dict) -> dict | None:
        """Return one transient activity or turn-completion update."""
        method = message.get("method")
        params = message.get("params") or {}
        message_thread = params.get("threadId")
        if message_thread is not None and message_thread != self.thread_id:
            return None

        if method == "turn/started":
            self.restore_turn(params["turn"])
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
        delivery_id: str,
        target: dict,
    ):
        self.reply = DeliveryReply(session_id, turn_id, delivery_id, target)
        self.last_update = 0.0

    def update(self, update: dict | None) -> bool:
        """Publish a final-answer item update, throttling only partial deltas."""
        message = update.get("message") if update is not None else None
        if message is None or message["phase"] != "final_answer":
            return False
        now = time.monotonic()
        if not message["complete"] and now - self.last_update < STREAM_UPDATE_INTERVAL:
            return False
        published = self.reply.replace(
            message["item"],
            message["text"],
            settles=message["complete"] and bool(message["text"]),
        )
        self.last_update = now
        return published

    def restore(self, text: str) -> bool:
        """Restore a still-running final answer after reconnecting."""
        return self.reply.replace(None, text)

    def finish(
        self, state: str, completed_text: str | None = None
    ) -> BaseException | None:
        """Finish the delivery from completed provider evidence only."""
        return self.reply.finish(state, completed_text)

    def disconnect(self) -> None:
        """Keep partial text visible but mark its provider connection lost."""
        self.reply.disconnect()


def project_app_server_activity(
    events: AppServerEvents,
    message: dict,
    update: dict | None,
    last_stream_update: float,
) -> float:
    """Project one notification with the shared streamed-update throttle.

    The writers below are the only place a reader ever sees this, so a caller says
    when to project rather than where to: what it gets back is the throttle's clock,
    which is the one piece of this state a caller has to keep.
    """
    if update is None:
        return last_stream_update
    turn_id = update["turn"]
    if update.get("completed"):
        clear_stream_activity(events.thread_id, turn_id)
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
    set_stream_activity(events.thread_id, turn_id, detail)
    return now


@contextmanager
def _locked_task_pages(session_id: str):
    """Lock this task's current page set in its stable path order.

    Ownership is the whole test. Both carriers that reach here — the detached
    adapter and an embedded host — write App Server readings onto the pages
    their own session holds, and the claim's session id says which those are.
    Discovery is only a candidate read, so each claim is checked again under
    its lock."""
    with ExitStack() as stack:
        pages = []
        for page_dir in owned_pages(session_id):
            try:
                page = stack.enter_context(PageTransaction(page_dir))
            except FileNotFoundError:
                continue
            claim = page.active_claim
            if claim and claim["id"] == session_id:
                pages.append(page)
        yield pages


def set_stream_activity(session_id: str, turn_id: str, detail: str) -> None:
    """Show what one turn is doing on every page this task claims."""
    with _locked_task_pages(session_id) as pages:
        for page in pages:
            page.set_stream_activity(session_id, turn_id, detail)


def clear_stream_activity(session_id: str, turn_id: str | None = None) -> None:
    """Take a turn's activity reading back off the pages showing it."""
    with _locked_task_pages(session_id) as pages:
        for page in pages:
            page.clear_stream_activity(session_id, turn_id)


def open_stream_turn(session_id: str, turn_id: str) -> None:
    """Open one observed provider turn on every page this task claims."""
    with _locked_task_pages(session_id) as pages:
        for page in pages:
            page.open_turn(session_id, turn_id)


def close_stream_turn(session_id: str, turn_id: str) -> None:
    """Close one observed provider turn on the pages holding it open."""
    with _locked_task_pages(session_id) as pages:
        for page in pages:
            page.close_turn(session_id, turn_id)


def session_state_path(session_id: str, suffix: str) -> Path:
    """Address one state-home file belonging to a single Codex task.

    A provider thread id is not a filename, so the task is named by a digest of it.
    Every file one task owns — its deliveries, their lock, the adapter's log and
    start lock — is that one name with a different suffix.
    """
    key = hashlib.sha256(session_id.encode()).hexdigest()[:32]
    return state_home() / "sessions" / f"{key}.{suffix}"


def delivery_dir(session_id: str) -> Path:
    return session_state_path(session_id, "deliveries")


def delivery_lock_path(session_id: str) -> Path:
    return session_state_path(session_id, "delivery.lock")


def queue_path(session_id: str, delivery_id: str) -> Path:
    return delivery_dir(session_id) / f"{delivery_id}.json"


def archive_queue(path: Path, queue: dict) -> None:
    """Move completed queue state out of the adapter's hot scan."""
    if queue["state"] == "accepted" and all(
        batch["receipted"] for batch in queue["batches"]
    ):
        history_path = path.parent / "history" / path.name
        history_path.parent.mkdir(parents=True, exist_ok=True)
        path.replace(history_path)


def write_queue(path: Path, queue: dict) -> None:
    """Store one delivery record, retiring it once nothing is owed on it."""
    write_json(path, queue)
    archive_queue(path, queue)


def queue_records(session_id: str) -> list[tuple[Path, dict]]:
    """Every standing delivery record one task holds, oldest first."""
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
    """The one record still collecting events for this task, if it has one."""
    records = queue_records(session_id) if queues is None else queues
    current = [
        (path, queue) for path, queue in records if queue["state"] == "collecting"
    ]
    if len(current) > 1:
        raise RuntimeError(
            f"Codex task {session_id} has multiple collecting Leaf deliveries"
        )
    return current[0] if current else None


def delivery_pointer_prompt(delivery_id: str) -> str:
    delivery = ElementTree.Element(
        "leaf-delivery", {"id": delivery_id, "operation": "delivery claim"}
    )
    pointer = ElementTree.tostring(delivery, encoding="unicode")
    return f"```xml\n{pointer}\n```"


@dataclass(frozen=True)
class PreparedDelivery:
    """One immutable delivery in pointer and structured forms."""

    prompt: str
    payload: dict


def offer_delivery(path: Path, queue: dict) -> PreparedDelivery:
    """Freeze one payload before offering its permanent pointer."""
    if queue["state"] == "offering":
        payload_path = delivery_path(path.stem)
        payload = read_json(payload_path)
        if payload is None:
            raise RuntimeError("the Codex delivery payload is missing")
        return PreparedDelivery(delivery_pointer_prompt(path.stem), payload)

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
    write_queue(path, queue)
    return PreparedDelivery(delivery_pointer_prompt(path.stem), payload)


def append_batch(
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

    replies = sum(
        obligation["response"]["kind"] == "reply"
        for entry in queue["batches"]
        for event in entry["events"]
        if (obligation := event.get("obligation")) is not None
    )
    responses = current_responses(page_dir, transaction.events)
    selected = []
    for event in fresh:
        response = responses.get(event["id"])
        if response is not None and response["kind"] == "reply":
            if replies:
                break
            replies += 1
        selected.append(event)
    if not selected:
        return None

    data = batch_data(
        page_dir,
        transaction,
        selected,
        as_of_seq=max(event["seq"] for event in fresh),
    )
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
    write_queue(path, queue)
    return path, len(queue["batches"]) - 1, entry


def delivery_reply_targets(payload: dict) -> list[dict]:
    """Every plain reply address the moves in one delivery are owed.

    A move's response address is not the move: a widget gesture inside a frozen
    conversation is answered on the conversation that holds it. Reading both halves
    from the delivery keeps every writer — the provider's own final answer and a
    host receipt written when there will be no final answer — addressing the same
    place.
    """
    return [
        {
            "page": batch["page"],
            "reply_to": obligation["response"]["to"],
            "responds": obligation["response"]["for"],
        }
        for batch in payload["batches"]
        for event in batch["events"]
        if (obligation := event.get("obligation")) is not None
        and obligation["response"]["kind"] == "reply"
    ]


def stream_reply_target(payload: dict) -> dict | None:
    """Return the one plain reply address a provider message may answer."""
    targets = delivery_reply_targets(payload)
    return targets[0] if len(targets) == 1 else None


def delivery_stream_reply_target(session_id: str, delivery_id: str) -> dict | None:
    """Resolve one task-owned delivery identity to its plain reply address."""
    path = queue_path(session_id, delivery_id)
    records = (path, path.parent / "history" / path.name)
    if not any(
        (recorded := read_json(record)) is not None
        and recorded.get("format") == QUEUE_FORMAT
        for record in records
    ):
        return None
    try:
        payload = read_json(delivery_path(delivery_id))
    except ValueError:
        return None
    return stream_reply_target(payload) if payload is not None else None


def delivery_queue_state(session_id: str, delivery_id: str) -> str | None:
    """Read one delivery's transport state from its live or archived queue record."""
    path = queue_path(session_id, delivery_id)
    with flocked(delivery_lock_path(session_id)):
        record = read_json(path)
        if record is None:
            record = read_json(path.parent / "history" / path.name)
    return record.get("state") if record is not None else None


def prepare_codex_delivery(page_dir: Path, harness: Harness) -> PreparedDelivery:
    """Claim PAGE and freeze the input for an embedded task's first turn."""
    session_id = harness.session
    transition = None
    try:
        with PageTransaction(page_dir) as page:
            transition = page.take_claim(harness)
            batch = unacknowledged(page.events, page.cursor)
            if not batch:
                raise RuntimeError("the page has no Leaf input to deliver")
            lock = delivery_lock_path(session_id)
            lock.parent.mkdir(parents=True, exist_ok=True)
            with flocked(lock):
                pending = next(
                    (
                        (path, queue)
                        for path, queue in queue_records(session_id)
                        if queue["state"] in {"collecting", "offering"}
                    ),
                    None,
                )
                if pending is not None:
                    return offer_delivery(*pending)
                captured = append_batch(
                    session_id,
                    page_dir,
                    page,
                    batch,
                )
                if captured is None:
                    raise RuntimeError("the page input is already in a Codex delivery")
                path, _, _ = captured
                return offer_delivery(path, read_json(path))
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
            for path, queue in queue_records(session_id)
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
        write_queue(path, queue)
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


def open_app_server_delivery(
    page_dir: Path,
    session_id: str,
    delivery_id: str,
    event_ids: tuple[str, ...],
    turn: str,
) -> str:
    """Bind a provider-observed App Server delivery to its turn."""
    if delivery_queue_state(session_id, delivery_id) == "offering":
        accepted = accept_codex_delivery(session_id, turn=turn)
        matching = [
            delivery
            for delivery in accepted
            if delivery["page"] == page_dir and delivery["events"] == event_ids
        ]
        if len(matching) != 1:
            raise RuntimeError(
                "the recovered App Server turn accepted an unexpected page batch"
            )
        return matching[0]["turn"]
    return open_queued_codex_delivery(page_dir, session_id, event_ids, turn)


def abandon_codex_delivery(session_id: str, event_id: str) -> None:
    """Retire an unaccepted delivery after its triggering event was settled."""
    lock = delivery_lock_path(session_id)
    with flocked(lock):
        matching = [
            path
            for path, queue in queue_records(session_id)
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
