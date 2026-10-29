"""Leaf's side of one Codex task: the delivery records every transport shares, and
the App Server connection Leaf uses where it can reach one, which the desktop app
never offers (`session-lifetime.md`, "Watchers", says which tasks offer one).

Two programs connect to a Codex task's App Server for Leaf: the detached
`codex_adapter.py`, which watches a task the user owns, and `leaf_website`
(`worker/`), which owns the tasks it starts. Both use this module's App Server
connection, `start_app_server_delivery` to start a delivery's turn, `TurnFold` to
turn a turn's notifications into page activity, a reply and an ending, and
`CarriedTurn` to follow a turn on the connection that started it. Each client's
header says how notifications reach its folds and what it does when a start or a
connection fails.

A delivery carries a batch of the user's updates to the task. Its content is an
immutable envelope (`delivery.freeze_delivery`, read with `leaf delivery read <id>`).
Its progress is one mutable record per delivery under the state home, whose class
says how far it has got: `Collecting` while `append_batch` adds events, `Offering`
once `offer_delivery` freezes the envelope and hands out a pointer to it,
`HookOffer` when the envelope went to a hook's running turn, `StartingOffer` while an
App Server start is unconfirmed, then `Accepted` (the queue took it), `Opened` (a
known turn took it) or `Abandoned`. Every transport shares the record, writing it
under the session's delivery lock: an App Server turn, the `codex queue` command, and
Codex's tool and Stop hooks. A record is offered once, accepted once
(`accept_codex_delivery`), and receipted on each page (`finish_codex_batch`).

`append_batch` adds only events no live record holds, offered or not, and events
that arrive after a record freezes go into the next delivery. A record holds at most
one thread reply, so the turn it starts writes one reply. Page receipts are
idempotent, and `recover_codex_receipt` repeats a batch's page writes before marking
it done, because the page cursor alone can't show the pickup was written. A record
with no pending receipts moves under `history/`, where `leaf delivery read` still
finds its envelope. A batch whose page is gone, or whose events no longer match the
page, is retired without writing (`delivery.receive_batch`).

While Codex's tool hook can reach the running turn, `offer_hook_delivery` offers the
complete envelope as one line of JSON, or its pointer where Codex wouldn't show it
whole, and records the turn in a `HookOffer`. `leaf delivery ack` in that turn accepts it
(`codex_state.confirm_codex_pointer`). A hook never re-offers input or takes one
another transport holds. The Stop hook offers nothing while an App Server adapter
runs (`Harness.later_turn_takes_input`): the turn ends on its own answer, and the
adapter starts a turn of its own for what arrived as it ended. Elsewhere, as with the
queue adapter, whose turn would open on a pointer Codex shows as the user's own
message, or a task that waits with `leaf wait`, Stop offers the input into the turn it
continues, even a resumed turn that ran no tool. Once Stop or Interrupt closes the turn, or the turn no longer reads
as running, the adapter's `_offer_queued_delivery` offers the pending input, or the
unread pointer, itself. Without an App Server connection it hands the pointer to
`codex queue`, retrying the same pointer while the session owns a page, and never
calls `turn/start`. With a connection it waits until the task is idle and starts the
turn. A delivery offered by a hook or the queue asks the agent for a plain reply; one
started over App Server takes the turn's final message as its reply.

When a session loses its last page, its `Collecting` or `Offering` record waits until
the same session claims a page again. The adapter finishes an accepted record's
remaining receipts before it checks ownership and exits. When the website gives up
starting a delivery, `abandon_codex_delivery` removes the unaccepted record and keeps
the envelope, in case a turn took it after all.

`start_app_server_delivery` reserves the delivery's reply, sends `turn/start` with the
delivery id as `clientUserMessageId`, and raises `AppServerDeliveryUncertain` when a
failed start may have left a turn running. Its docstring says what each failure does
to the reservation, and each client decides what an uncertain start means. A
`TurnFold` writes activity only while its session generation and turn are current
(`TurnFold.activity_epoch`), so a fold from an older generation never touches a
newer one's activity. `delivery`'s header owns the reply reservation, and
`../../skills/leaf/references/harness-codex.md`, "Replies", is the agent's side of it.

A delivery enters its turn as a `leaf_delivery` tool output, so it adds no user
message to the user's Codex transcript or queue. Its start can still land in a turn
another client started: `turn/start` on a running turn steers into it and answers
with its id, and a follow-up the user queued in the Codex TUI starts just after the
turn before it ends, while App Server still reads idle. No reading closes that gap,
since the TUI holds its queued follow-ups itself, out of `thread/queue/list`'s
sight, and App Server's one start-if-idle, `thread/queue/start`, takes only user
input. A user can also steer into Leaf's turn. So the turn's items decide whether
its answer is the delivery's: a turn Leaf starts opens with the delivery's tool
output and holds no user message, and a turn that holds one, ahead of the delivery
or after it (`carries_user_message`), is joined. Once a fold sees the user's
message it posts no more of the reply, neither opening nor draft, and marks the
draft withheld, so Stop lets the turn end on its own answer rather than continuing
it over the update. As the turn ends it releases the reservation,
and a completed joined turn's final message is refused, so `TurnFold.commit`
offers the update again as a correction (`prepare_reply_correction`), answered in
a turn of its own. Rejected: queueing each delivery with `thread/queue/add`
(#3357, reverted), which put every delivery in the transcript as a user message.

Codex's hooks import this module between steps and before Stop
(`offer_hook_delivery`), so `thread`, which brings the page model and its validators,
is imported inside the functions that need it.
"""

import atexit
import json
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path
from typing import ClassVar, Literal, TypedDict
from urllib.parse import urlsplit
from xml.etree import ElementTree

from .codex_state import (
    delivery_dir,
    delivery_lock_path,
    hook_turn,
)
from .delivery import (
    DELIVERY,
    DeliveryIdConflict,
    ReceiptRefused,
    batch_data,
    batch_refs,
    current_responses,
    deliverable,
    delivery_path,
    delivery_pointer_prompt,
    freeze_delivery,
    new_delivery_id,
    read_delivery,
    reader_envelope,
    receive_batch,
    record_pickup,
    stored_delivery,
    stream_reply_target,
    validate_delivery_id,
)
from .harness import CodexHarness, Harness
from .refusals import Refused
from .service import (
    PageTransaction,
    delivery_reply_attempt,
    owned_pages,
    restore_page_claim,
)
from .state import (
    Record,
    close_session_turn,
    flocked,
    renew_turn,
    retire_if_gone,
    session_live,
    session_lock_path,
    session_record,
    sessions_home,
    start_session_turn,
    turn_open,
)

START_TIMEOUT = 20
# Names the App Server a task runs on to the `leaf` commands it runs, so they hand
# its pages to that server (`private_app_server`, `leaf page claim`).
APP_SERVER_ENV = "LEAF_CODEX_APP_SERVER"
STREAM_UPDATE_INTERVAL = 0.2
STREAM_TEXT_METHODS = {"item/reasoning/summaryTextDelta"}
STREAM_MESSAGE_METHOD = "item/agentMessage/delta"
# The items a turn's opening may follow: its input, and the model's reasoning.
OPENING_PRELUDE_ITEM_TYPES = {"userMessage", "functionCallOutput", "reasoning"}
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


class JoinedTurn(RuntimeError):
    """A delivery's turn carried a user message too, so its final answer is not the
    delivery's reply (`carries_user_message`)."""


class AppServerDeliveryUncertain(RuntimeError):
    """A delivery may have started, but its acknowledgement was lost."""


def app_server_socket_path(endpoint: str) -> Path | None:
    """Validate a local App Server endpoint and return its Unix socket path."""
    try:
        parsed = urlsplit(endpoint)
        hostname = parsed.hostname
    except ValueError as error:
        raise Refused("--app-server needs a valid local endpoint") from error
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise Refused("--app-server needs a local WebSocket or Unix endpoint")
    if parsed.scheme == "ws" and hostname in {"127.0.0.1", "::1", "localhost"}:
        return None
    if parsed.scheme == "unix" and not parsed.netloc and parsed.path:
        path = Path(parsed.path)
        if path.is_absolute():
            return path
    raise Refused(
        "--app-server needs a local loopback ws:// endpoint or an absolute "
        "unix:/// socket"
    )


# The functional form keeps schema fields out of vulture's variable scan.
_ConnectionOptions = TypedDict(  # noqa: UP013
    "_ConnectionOptions",
    {
        "open_timeout": float,
        "close_timeout": float,
        "compression": None,
        "max_size": None,
    },
)


def app_server_connect(endpoint: str):
    """Open one connection to a local App Server, by socket or by loopback."""
    from websockets.sync.client import connect, unix_connect

    socket_path = app_server_socket_path(endpoint)
    options: _ConnectionOptions = {
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


def _wait_for_app_server(path: Path, process: subprocess.Popen, log) -> None:
    deadline = time.monotonic() + START_TIMEOUT
    while time.monotonic() < deadline:
        if path.exists():
            return
        if process.poll() is not None:
            log.seek(0)
            detail = log.read().decode(errors="replace").strip()
            raise Refused(detail or "Codex App Server exited before it was ready")
        time.sleep(0.05)
    raise Refused("Codex App Server did not become ready")


@contextmanager
def private_app_server(
    executable: str,
    *,
    env: dict[str, str] | None = None,
    arguments: tuple[str, ...] = (),
    cwd: str | None = None,
    log_path: Path | None = None,
) -> Generator[tuple[str, subprocess.Popen]]:
    """Run one App Server on a Unix socket only this user can reach, and yield its
    endpoint and process until the block ends or this process exits. The server stops
    at either boundary.

    The server's environment names that endpoint as `LEAF_CODEX_APP_SERVER`, so a
    task it runs hands its pages to this server when it serves them.
    An eval may supply an isolated child environment without mutating this process,
    and a caller `arguments` that follow `app-server` on its command line. The website
    sets its working directory and keeps a log; other callers use a temporary log.

    The server runs in a session of its own and never exits by itself, and a block
    on a daemon thread, as a page server's title request is, never reaches its
    `finally` when the process exits. So each running server is also stopped at
    exit (`stop_private_app_servers`), on a SIGTERM or SIGHUP in a process that
    turns them into an exit (`leases.release_on_termination`), and as a page server
    ends itself (`server.exit_serving`). A SIGKILL leaves one running.
    """
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="leaf-codex-", dir="/tmp") as directory:
        path = Path(directory) / "app-server.sock"
        endpoint = f"unix://{path}"
        with log_path.open("a+b") if log_path else tempfile.TemporaryFile() as log:
            server = subprocess.Popen(
                [executable, "app-server", "--listen", endpoint, *arguments],
                env=(os.environ if env is None else env) | {APP_SERVER_ENV: endpoint},
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            _private_app_servers.add(server)
            try:
                _wait_for_app_server(path, server, log)
                yield endpoint, server
            finally:
                stop_app_server(server)
                _private_app_servers.discard(server)


_private_app_servers: set[subprocess.Popen] = set()


@atexit.register
def stop_private_app_servers() -> None:
    """Stop every App Server `private_app_server` started in this process."""
    for server in list(_private_app_servers):
        stop_app_server(server)


def retry_delay(failures: int) -> int:
    """Seconds to hold off after this many consecutive failures, the first being 1.

    Every client retries the same kinds of failure — a connection that dropped, a
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
                from .registry.schema import json_value

                raise AppServerRequestRejected(
                    error.get("message") or json_value(error)
                )
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


def start_app_server_delivery(send, thread_id: str, payload: dict) -> dict:
    """Start one delivery's turn on an idle thread with its reply reserved.

    `send(method, params)` is the client's request on its own connection, under
    its own request ids. The task thread id is the Leaf session id. Immediately
    before the request, this boundary captures its epoch; the returned identity
    is adopted only against that epoch or its own synchronous provider prompt.
    A newer different prompt leaves the start uncertain and its reply reserved.
    Return the admitted lifecycle publication, whose turn names the provider ID;
    every follower retains this authority instead of rereading it after other work.

    The reply is reserved before `turn/start` goes out, so no other writer answers
    the delivery its turn is about to answer. What happens to the reply reservation
    when the start fails depends on what the failure says. A definitive refusal
    (`AppServerRequestRejected`) means no turn exists, so the reservation is
    released before this raises. A successful answer missing the turn identity is
    uncertain too. A request that went out with no answer
    raises `AppServerDeliveryUncertain` with the reply still reserved: a turn carrying
    this delivery may be running, and until something sees it, no other writer may
    answer for the delivery. Each client decides what an uncertain start means for
    the turn it may have made.
    """
    from .thread import release_delivery_reply, reserve_delivery_reply

    reply_target = stream_reply_target(payload)
    if reply_target is not None:
        try:
            reserve_delivery_reply(
                thread_id,
                payload["id"],
                reply_target,
                expected_claim=payload.get("correction", {}).get("claim"),
            )
        except ReceiptRefused:
            abandon_uncertain_delivery(thread_id, payload)
            raise
    try:
        expected = session_record(thread_id)
        started = send("turn/start", app_server_turn_start_params(thread_id, payload))
    except AppServerRequestRejected:
        if reply_target is not None:
            release_delivery_reply(thread_id, payload["id"], reply_target)
        raise
    # An interrupt mid-request leaves the same uncertainty and keeps the reply
    # reservation too, but it passes through unwrapped so it ends the process
    # rather than reading as a start to retry.
    except Exception as error:
        raise AppServerDeliveryUncertain(
            f"the Codex App Server turn was not acknowledged: {error}"
        ) from error
    turn_id = (started.get("turn") or {}).get("id")
    if not turn_id:
        raise AppServerDeliveryUncertain("Codex App Server returned no turn id")
    admitted = start_session_turn(thread_id, turn_id, expected)
    if admitted is None:
        raise AppServerDeliveryUncertain(
            "a newer session epoch superseded the provider start"
        )
    return admitted


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
    found = {identity for item in items if (identity := _item_delivery_id(item))}
    return next(iter(found)) if len(found) == 1 else None


def _item_delivery_id(item: dict) -> str | None:
    """The Leaf delivery one transcript item carries: a `leaf_delivery` tool output,
    or a user message that is only a `leaf-delivery` pointer."""

    def valid(identity) -> str | None:
        try:
            return validate_delivery_id(identity)
        except ValueError:
            return None

    if (
        item.get("type") == "functionCallOutput"
        and item.get("name") == "leaf_delivery"
        and isinstance(item.get("output"), str)
    ):
        try:
            payload = json.loads(item["output"])
        except json.JSONDecodeError:
            return None
        if (
            isinstance(payload, dict)
            and payload.get("format") == DELIVERY.format
            and isinstance(payload.get("id"), str)
        ):
            return valid(payload["id"])
        return None
    if item.get("type") != "userMessage":
        return None
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
            and pointer.attrib["operation"] == "delivery read"
        ):
            return valid(pointer.attrib["id"])
    return None


def _user_input(item: dict) -> bool:
    """Whether a transcript item is a message from the user rather than Leaf's."""
    return item.get("type") == "userMessage" and _item_delivery_id(item) is None


def _head(text: str, limit: int = 180) -> str:
    line = " ".join(text.split())
    return line if len(line) <= limit else line[: limit - 1] + "…"


def _tail(text: str, limit: int = 240) -> str:
    line = " ".join(text.split())
    return line if len(line) <= limit else "…" + line[-(limit - 1) :]


def recv_notification(
    socket, silent_since: float, silence: float | None
) -> dict | None:
    """Read one App Server notification, or nothing while the stream is only quiet.

    `socket.recv` raises `TimeoutError` every second a subscription has nothing to
    say, and a turn that is thinking or running a command says nothing for a while.
    A client that gives a silence bound lets that timeout through once the quiet
    outlasts it, which ends the turn on the same path a dropped socket takes rather
    than waiting on it for the client's life. A client whose task can sit waiting
    on a person gives none: a terminal approval is silent for as long as nobody
    answers it, and the turn is still running.
    """
    try:
        return json.loads(socket.recv(timeout=1))
    except TimeoutError:
        if silence is None or time.monotonic() - silent_since < silence:
            return None
        raise


class TurnStream:
    """The notifications one subscribed connection carries, in order.

    `thread/start` and `thread/resume` subscribe the connection that asked, for as
    long as that connection lives, so the socket a turn was started on already
    carries everything the turn will say. Nothing here reconnects: a connection
    that drops takes its turn's remaining notifications with it, and the follower
    treats that as the turn's ending rather than a gap to read across.

    Notifications buffered behind a request arrive first. They were sent before the
    response that carried them was read, so a turn's own `turn/started` is routinely
    among them.
    """

    def __init__(self, socket, buffered=(), *, silence: float | None = None):
        self.socket = socket
        self.pending = list(buffered)
        self.silence = silence
        self.quiet_since = time.monotonic()
        self.buffered = False

    def next(self) -> dict | None:
        """Take the next notification, or None while the stream is only quiet."""
        if self.pending:
            self.buffered = True
            message = self.pending.pop(0)
        else:
            self.buffered = False
            message = recv_notification(self.socket, self.quiet_since, self.silence)
            if message is None:
                return None
        self.quiet_since = time.monotonic()
        return message

    def close(self) -> None:
        self.socket.close()


class AppServerEvents:
    """Fold one turn's notifications into activity and terminal readings.

    The turn is fixed when the fold is made, and a notification naming any other
    turn reads as nothing: which turn a notification belongs to is the client's
    routing, not something this fold follows.

    A turn's reply is its final answer. Its opening is a `commentary` agent message
    that is the turn's first, written before any item but the turn's input and
    reasoning: the agent writes it to the user before its first tool call, saying what
    it is about to do. That is the line every harness's agent posts first
    (`conversation-loop.md`, "When to write"), so once complete it posts as the turn's
    progress (`AppServerReplyStream.open`): the thread shows it at once as its working
    message, where it was said, and the answer folds it away. An update carries it as
    `opening` once, when its completion arrives or, where that was missed, as the next
    item begins. Every other commentary is
    the agent's working narration and stays in Codex, including narration written
    after a tool call by an agent that skipped the opening.
    Rejected: streaming the opening as the head of the reply, which held words said at
    the turn's start in a draft at the thread's end until the answer committed, so a
    message the user sent meanwhile stood above them.

    `joined` says a user message shares the turn (`carries_user_message`), so its
    answer is not a delivery's alone (`TurnFold`).
    """

    def __init__(self, thread_id: str, turn_id: str):
        self.thread_id = thread_id
        self.turn_id = turn_id
        self.text: dict[str, str] = {}
        self.message_phases: dict[str, str | None] = {}
        self.message_order: list[str] = []
        self.opening: str | None = None
        self.opening_open = True
        # Whether the opening is complete, and whether an update has said it.
        self.opening_ended = False
        self.opening_told = False
        self.item_started_at: dict[str, int] = {}
        self.active_items: dict[str, dict] = {}
        self.waiting_kind: str | None = None
        self.joined = False

    def restore_turn(self, turn: dict) -> None:
        """Replace transient message state with a snapshot of this turn."""
        self.text.clear()
        self.message_phases.clear()
        self.message_order.clear()
        self.opening = None
        self.opening_open = True
        self.opening_ended = False
        self.opening_told = False
        self.item_started_at.clear()
        self.active_items.clear()
        self.waiting_kind = None
        self.joined = self.joined or carries_user_message(turn)
        for item in turn.get("items", []):
            if item.get("type") == "agentMessage":
                self._record_message(item)
            else:
                self._close_opening(item)

    def read(self, message: dict) -> dict | None:
        """Return one transient activity or turn-completion update, carrying the
        turn's `opening` where this notification shows it complete."""
        update = self._read(message)
        opening = self.said_opening()
        if not opening:
            return update
        return {**(update or {"turn": self.turn_id}), "opening": opening}

    def said_opening(self) -> str:
        """The opening's words, once it is complete and no update has said them."""
        if (
            self.opening_told
            or not self.opening_ended
            or self.opening is None
            or not self._is_opening(self.opening)
            or not self.text.get(self.opening)
        ):
            return ""
        self.opening_told = True
        return self.text[self.opening]

    def _read(self, message: dict) -> dict | None:
        method = message.get("method")
        params = message.get("params") or {}
        message_thread = params.get("threadId")
        if message_thread is not None and message_thread != self.thread_id:
            return None

        if method in {"turn/started", "turn/completed"}:
            turn = params["turn"]
            if turn["id"] != self.turn_id:
                return None
            if method == "turn/started":
                self.restore_turn(turn)
                return {"turn": self.turn_id, "activity": {"kind": "working"}}
            return {"turn": self.turn_id, "completed": turn.get("status", "completed")}
        turn_id = params.get("turnId") or self.turn_id
        if turn_id != self.turn_id:
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
            if current is None:
                return None
            planned = {"kind": "working", "detail": _head(current)}
            return {
                "turn": turn_id,
                "activity": (
                    self._running_activity()
                    if self.waiting_kind is not None or self.active_items
                    else planned
                ),
            }

        if method == "item/started":
            item = params["item"]
            lifecycle = self._item_lifecycle(params, "started")
            if item["type"] == "agentMessage":
                self._record_message(item)
                if not self._in_reply(item["id"]):
                    return {"turn": turn_id, "item": lifecycle}
                self._set_active(item["id"], {"kind": "replying"})
                if item.get("text"):
                    return {
                        "turn": turn_id,
                        "item": lifecycle,
                        "activity": self._running_activity(),
                        "message": self._message_update(item["id"], complete=False),
                    }
                return {
                    "turn": turn_id,
                    "item": lifecycle,
                    "activity": self._running_activity(),
                }
            self._close_opening(item)
            self.joined = self.joined or _user_input(item)
            detail = self._item_detail(item)
            if detail:
                self._set_active(item["id"], {"kind": "tool", "detail": detail})
            return {
                "turn": turn_id,
                "item": lifecycle,
                **({"activity": self._running_activity()} if detail else {}),
            }

        if method == "item/completed":
            item = params["item"]
            lifecycle = self._item_lifecycle(params, "completed")
            self.joined = self.joined or _user_input(item)
            self.active_items.pop(item["id"], None)
            if item["type"] == "agentMessage":
                self._record_message(item)
                if item["id"] == self.opening:
                    self.opening_ended = True
                if not self._in_reply(item["id"]):
                    return {"turn": turn_id, "item": lifecycle}
                return {
                    "turn": turn_id,
                    "item": lifecycle,
                    "activity": self._running_activity(),
                    "message": self._message_update(item["id"], complete=True),
                }
            return {
                "turn": turn_id,
                "item": lifecycle,
                "activity": self._running_activity(),
            }

        if method == STREAM_MESSAGE_METHOD:
            item_id = params["itemId"]
            combined = self.text.get(item_id, "") + params["delta"]
            self.text[item_id] = combined
            if item_id not in self.message_order:
                self._note_message(item_id)
                self.message_phases[item_id] = None
            if self.message_phases.get(item_id) == "commentary" and not self._in_reply(
                item_id
            ):
                return None
            self._set_active(item_id, {"kind": "replying"})
            return {
                "turn": turn_id,
                "activity": self._running_activity(),
                "message": self._message_update(item_id, complete=False),
            }

        if method in STREAM_TEXT_METHODS:
            item_id = params["itemId"]
            combined = self.text.get(item_id, "") + params["delta"]
            self.text[item_id] = combined
            activity = {"kind": "thinking", "detail": _tail(combined)}
            self._set_active(item_id, activity)
            return {"turn": turn_id, "activity": self._running_activity()}

        if method in STREAM_HEARTBEAT_METHODS:
            item_id = params["itemId"]
            activity = self.active_items.get(item_id)
            if activity and activity["kind"] == "tool":
                self._set_active(item_id, activity)
            return (
                {
                    "turn": turn_id,
                    "activity": self._running_activity(),
                }
                if activity and activity["kind"] == "tool"
                else None
            )

        if method in {
            "item/commandExecution/requestApproval",
            "item/fileChange/requestApproval",
            "item/permissions/requestApproval",
        }:
            self.waiting_kind = "awaiting_approval"
            return {"turn": turn_id, "activity": self._running_activity()}
        if method == "item/tool/requestUserInput":
            self.waiting_kind = "awaiting_input"
            return {"turn": turn_id, "activity": self._running_activity()}

        if method == "thread/status/changed":
            flags = params.get("status", {}).get("activeFlags", [])
            if "waitingOnApproval" in flags:
                self.waiting_kind = "awaiting_approval"
            elif "waitingOnUserInput" in flags:
                self.waiting_kind = "awaiting_input"
            else:
                self.waiting_kind = None
            return {"turn": turn_id, "activity": self._running_activity()}
        return None

    def _running_activity(self) -> dict:
        """Return the newest observation whose provider item is still running."""
        if self.waiting_kind is not None:
            return {"kind": self.waiting_kind}
        return next(reversed(self.active_items.values()), {"kind": "working"})

    def _set_active(self, item_id: str, activity: dict) -> None:
        """Make one live provider item the most recently observed item."""
        self.active_items.pop(item_id, None)
        self.active_items[item_id] = activity

    def _note_message(self, item_id: str) -> None:
        self.message_order.append(item_id)
        if self.opening is None and self.opening_open:
            self.opening = item_id
        elif self.opening is not None:
            self.opening_ended = True
        self.opening_open = False

    def _close_opening(self, item: dict) -> None:
        if item["type"] not in OPENING_PRELUDE_ITEM_TYPES:
            self.opening_open = False
            self.opening_ended = self.opening is not None

    def _record_message(self, item: dict) -> None:
        item_id = item["id"]
        if item_id not in self.message_order:
            self._note_message(item_id)
        self.message_phases[item_id] = item.get("phase")
        self.text[item_id] = item.get("text", "")

    def _in_reply(self, item_id: str) -> bool:
        """Whether one agent message is part of the turn's reply."""
        phase = self.message_phases.get(item_id)
        return phase != "commentary" or item_id == self.opening

    def _is_opening(self, item_id: str) -> bool:
        return (
            item_id == self.opening and self.message_phases.get(item_id) == "commentary"
        )

    def _visible_text(self) -> str:
        final = [
            self.text[item_id]
            for item_id in self.message_order
            if self.message_phases.get(item_id) == "final_answer"
            and self.text.get(item_id)
        ]
        if not final:
            unknown = [
                self.text[item_id]
                for item_id in self.message_order
                if self.message_phases.get(item_id) is None and self.text.get(item_id)
            ]
            final = unknown[-1:]
        return "\n\n".join(final)

    @staticmethod
    def final_text(turn: dict) -> str:
        """Return a completed turn's reply: its final answer, or nothing for a turn
        with none, whatever its opening said."""
        return "\n\n".join(_final_answer(turn))

    @staticmethod
    def reply_so_far(turn: dict) -> str:
        """Return the reply a still-running turn has written."""
        return "\n\n".join(_final_answer(turn))

    def _message_update(self, item_id: str, *, complete: bool) -> dict:
        """One reply message's update: the opening's own words, or the answer so far."""
        return {
            "item": item_id,
            "phase": self.message_phases.get(item_id),
            "text": self.text.get(item_id, "")
            if self._is_opening(item_id)
            else self._visible_text(),
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


def carries_user_message(turn: dict) -> bool:
    """Whether a message from the user shares this turn. A turn Leaf starts opens
    with its delivery's tool output and holds no user message, and a `leaf-delivery`
    pointer is Leaf's input, so a user message there came from another client: a
    turn Leaf's start steered into, or a message the user steered into Leaf's turn."""
    return any(_user_input(item) for item in turn.get("items", []))


def _final_answer(turn: dict) -> list[str]:
    """One turn's final-answer texts."""
    return [
        item["text"]
        for item in turn.get("items", [])
        if item["type"] == "agentMessage"
        and item.get("phase") == "final_answer"
        and item.get("text")
    ]


class AppServerReplyStream:
    """Post one App Server turn's opening as progress, project its provisional reply
    and commit its final answer.

    The provider owns this lifecycle; `thread.post_response` owns admission of the
    opening and the durable answer, both under the delivery's reply reservation.
    Partial answer text survives interruption and disconnect without becoming thread
    history.
    """

    def __init__(
        self,
        session_id: str,
        turn_id: str,
        delivery_id: str,
        target: dict,
    ):
        self.session_id = session_id
        self.turn_id = turn_id
        self.target = dict(target)
        self.delivery_id = delivery_id
        self.attempt = delivery_reply_attempt(delivery_id)
        self.text = ""
        self.withheld = False
        self._replace(None, "")
        self.last_update = 0.0

    def update(self, update: dict | None) -> bool:
        """Publish a reply message's update, throttling only partial deltas.

        The opening posts once an update says it; only the final answer streams, and
        only its completion settles the reply.
        """
        if update is None:
            return False
        opened = self.open(update.get("opening", ""))
        message = update.get("message")
        if message is None or message["phase"] != "final_answer":
            return opened
        now = time.monotonic()
        if not message["complete"] and now - self.last_update < STREAM_UPDATE_INTERVAL:
            return opened
        published = self._replace(
            message["item"],
            message["text"],
            settles=message["complete"] and bool(message["text"]),
        )
        self.last_update = now
        return published or opened

    def restore(self, text: str) -> bool:
        """Restore a still-running reply after reconnecting."""
        return self._replace(None, text)

    def open(self, text: str) -> bool:
        """Post the turn's opening as its progress at the reserved address, once: a
        repeat names the same attempt and returns the first. An update another writer
        answered, or another delivery holds, takes none (`ProviderFinal`).

        Progress is one line, the update's Working line, so the opening's paragraphs
        join into one. A refusal, such as a page whose saved source is mid-edit, costs
        the user only the line: the turn goes on to its answer, so it is reported and
        not raised into the notification loop, which would end the turn."""
        if not text:
            return False
        from .thread import post_response

        try:
            posted = post_response(
                self.target["ref"],
                " ".join(text.split()),
                reservation=self.attempt,
                ephemeral=True,
                identity={"session": self.session_id},
                claimed_session=self.session_id,
            )
        except FileNotFoundError:
            return False
        except Refused as error:
            print(f"Codex opening not posted: {error}", file=sys.stderr, flush=True)
            return False
        return posted is not None

    def _replace(
        self,
        item_id: str | None,
        text: str,
        *,
        settles: bool = False,
    ) -> bool:
        """Replace the visible text without appending thread history."""
        self.text = text
        try:
            with PageTransaction(Path(self.target["page"])) as page:
                claim = page.active_claim
                if (
                    claim is None
                    or claim["id"] != self.session_id
                    or not turn_open(claim, self.turn_id)
                ):
                    return False
                page.set_stream_reply(
                    self.session_id,
                    self.turn_id,
                    self.target,
                    self.attempt,
                    item_id,
                    text,
                    "active",
                    settles=settles,
                )
                return True
        except FileNotFoundError:
            return False

    def finish(
        self,
        state: str,
        completed_text: str | None = None,
    ) -> BaseException | None:
        """Commit only a completed final, retaining rejected or partial text.

        A completed answer retains its delivered response address even when that
        update was settled during the turn. The reply reopens the thread.

        A commit appends the reply, then clears its reply reservation and draft in a
        separate transaction. Every other way out releases the reservation,
        including when recording the draft's last state fails. An abandoned
        reservation would block the harness from recording that no answer is coming.
        """
        from .thread import release_delivery_reply

        committed = False
        try:
            if state == "completed" and completed_text:
                try:
                    self._commit(completed_text)
                    committed = True
                    return None
                except (OSError, Refused) as error:
                    self._set_state("failed", completed_text)
                    return error
            self._set_state(
                state if state != "completed" else "partial",
                self.text,
            )
            return None
        finally:
            if not committed:
                release_delivery_reply(self.session_id, self.delivery_id, self.target)

    def withhold(self) -> None:
        """Empty the draft and mark it `withheld`, once, for a turn whose answer is
        not this delivery's alone. The reservation stands until the turn ends
        (`withdraw`), and the Stop hook reads the turn as done with the update
        (`activity._turn_wrote`), since the correction offered as it ends answers
        it."""
        if not self.withheld:
            self.withheld = True
            self.text = ""
            self._set_state("withheld", "")

    def withdraw(self) -> None:
        """Take the draft down and give up the reply reservation as a joined turn
        ends. The update stays owed."""
        from .thread import release_delivery_reply

        try:
            with PageTransaction(Path(self.target["page"])) as page:
                page.clear_stream_reply(self.session_id, self.turn_id)
        except FileNotFoundError:
            pass
        release_delivery_reply(self.session_id, self.delivery_id, self.target)

    def disconnect(self) -> None:
        """Keep partial text visible while its provider connection recovers. A
        withheld draft stays withheld: it has no text to keep."""
        if not self.withheld:
            self._set_state("disconnected", self.text)

    def _set_state(self, state: str, text: str) -> None:
        try:
            with PageTransaction(Path(self.target["page"])) as page:
                page.set_stream_reply_state(
                    self.session_id,
                    self.turn_id,
                    self.attempt,
                    text,
                    state,
                )
        except FileNotFoundError:
            pass

    def _commit(self, text: str) -> dict | None:
        from .thread import post_response

        page_dir = Path(self.target["page"])
        try:
            accepted = post_response(
                self.target["ref"],
                text,
                reservation=self.attempt,
                identity={"session": self.session_id},
                claimed_session=self.session_id,
            )
            with PageTransaction(page_dir) as page:
                page.clear_delivery_reply_reservation(
                    self.session_id,
                    self.target["responds"],
                    self.attempt,
                )
                page.clear_stream_reply(self.session_id, self.turn_id)
            return accepted
        except FileNotFoundError:
            return None


@contextmanager
def _locked_task_pages(session_id: str, *, expected: dict | None):
    """Lock this task's current page set in its stable path order.

    Ownership is the whole test. Both clients that reach here — the detached
    adapter and an embedded harness — write App Server readings onto the pages
    their own session holds, and the claim's session id says which those are.
    Discovery is only a candidate read, so each claim is checked again under
    its lock. A provider writer supplies its admitted lifecycle publication;
    page→session locks retain that epoch through the activity write."""
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
        stack.enter_context(flocked(session_lock_path(session_id)))
        if expected is None or session_record(session_id) != expected:
            pages = []
        yield pages


def set_stream_activity(
    session_id: str,
    turn_id: str,
    activity: dict,
    *,
    expected: dict | None,
) -> None:
    """Publish a running turn's activity under its admitted lifecycle epoch."""
    if not turn_open(expected, turn_id):
        return
    with _locked_task_pages(session_id, expected=expected) as pages:
        for page in pages:
            page.set_stream_activity(session_id, turn_id, activity)


def clear_stream_activity(
    session_id: str,
    turn_id: str | None = None,
    *,
    expected: dict | None,
) -> None:
    """Clear activity only while the supplied lifecycle publication still owns it."""
    with _locked_task_pages(session_id, expected=expected) as pages:
        for page in pages:
            page.clear_stream_activity(session_id, turn_id)


class TurnFold:
    """One Codex turn, folded onto the pages its task claims from its first
    notification to its ending.

    Every client that watches a turn does this same work with what the turn says.
    Each notification folds into the turn's activity and final-answer readings,
    and the activity reaches every page the task claims. When the delivery the turn
    carries owes a `turn` answer, the reply streams under that delivery's reply
    reservation, and the completion commits the answer or releases the reservation
    before it closes the turn on the page.

    The fold observes the session lifecycle under the provider turn id, which
    Codex's hooks name too. Its producer passes the publication it admitted;
    `open` follows that generation and identity without introducing another one. Live activity and cleanup retain the captured
    session generation; an old fold cannot clear or close a newer lifetime that
    reuses the provider ID. Historical answer settlement borrows no live authority.
    `close` closes only that generation and id; delivery acceptance only records which turn
    took the updates. A client opens a fold's turn only while it runs, so a turn
    read back from a snapshot after it ended is committed without reopening it.

    What differs between clients is only how notifications reach the fold.
    `CarriedTurn` reads a connection the turn owns, from the start that made the
    turn to its end. The adapter's `TaskConnection` reads one subscription the whole
    task shares and routes each notification to the fold of the turn it names.
    That is also why the ways a read can stop other than a completion — a lost
    connection, a silence, an adapter going — belong to each client rather than
    to the fold.

    `close` runs whatever the answer did. Committing the answer re-reads a page
    the turn's own work may have left unopenable, and the turn has ended either
    way: until the client's account of it is written, the page goes on telling
    its user the agent is working, with nothing but the claim's fifteen-minute
    grace to correct it.
    """

    def __init__(
        self,
        session_id: str,
        turn_id: str,
        delivery_id: str | None = None,
        reply_target: dict | None = None,
        *,
        lifecycle: dict | None,
    ):
        self.generation = lifecycle["generation"] if lifecycle is not None else None
        self.session_id = session_id
        self.turn_id = turn_id
        self.delivery_id = delivery_id
        self.reply_target = reply_target
        self.events = AppServerEvents(session_id, turn_id)
        self.reply_stream: AppServerReplyStream | None = None
        self.last_activity_update = 0.0
        self.correction: dict | None = None

    def open(self) -> bool:
        """Follow the admitted provider identity without introducing another one."""
        return turn_open(self.activity_epoch())

    def bind(self, delivery_id: str, reply_target: dict | None) -> None:
        """Name the delivery this turn carries, and open the reply it owes."""
        self.delivery_id = delivery_id
        self.reply_target = reply_target
        self.open_reply()

    def open_reply(self) -> None:
        """Open the draft this turn's final answer commits from, under its delivery's
        reply reservation."""
        if self.reply_target is not None:
            assert self.delivery_id is not None
            self.reply_stream = AppServerReplyStream(
                self.session_id,
                self.turn_id,
                self.delivery_id,
                self.reply_target,
            )
            if self.events.joined:
                self.reply_stream.withhold()

    def restore(self, turn: dict) -> None:
        """Take up a still-running turn from a snapshot of what it has said."""
        self.events.restore_turn(turn)
        if self.reply_stream is not None and self.events.joined:
            self.reply_stream.withhold()
        elif self.reply_stream is not None:
            # An opening the turn completed while nobody was reading posts now.
            self.reply_stream.open(self.events.said_opening())
            self.reply_stream.restore(self.events.reply_so_far(turn))

    def absorb(self, message: dict) -> dict | None:
        """Fold one notification into this turn's readings, and put them on the page."""
        update = self.events.read(message)
        self.observe(message, update)
        self._project(message, update)
        published = False
        if self.reply_stream is not None and self.events.joined:
            self.reply_stream.withhold()
        elif self.reply_stream is not None:
            published = self.reply_stream.update(update)
        self.observe_reply(update, published)
        return update

    def activity_epoch(self) -> dict | None:
        """Authorize live projection only for this fold's generation and turn."""
        current = session_record(self.session_id)
        if (
            session_live(current)
            and current["generation"] == self.generation
            and current["turn"] == self.turn_id
        ):
            return current
        return None

    def set_activity(self, activity: dict) -> None:
        """Publish only within this fold's current open provider identity."""
        set_stream_activity(
            self.session_id, self.turn_id, activity, expected=self.activity_epoch()
        )

    def clear_activity(self) -> None:
        """Clear only this fold's matching lifecycle publication."""
        clear_stream_activity(
            self.session_id, self.turn_id, expected=self.activity_epoch()
        )

    def _project(self, message: dict, update: dict | None) -> None:
        """Show one update's activity, throttling only streamed deltas.

        A completion carries none: `close` takes the reading off, since it runs on
        every way a turn ends and a completion is only one of them.
        """
        activity = update.get("activity") if update is not None else None
        if activity is None:
            return
        now = time.monotonic()
        if (
            message.get("method") in STREAM_THROTTLED_METHODS
            and now - self.last_activity_update < STREAM_UPDATE_INTERVAL
        ):
            return
        self.set_activity(activity)
        self.last_activity_update = now

    def finished(self, message: dict, update: dict | None) -> dict | None:
        """Return the terminal turn when this notification is its completion."""
        if update is not None and update.get("completed"):
            return message["params"]["turn"]
        return None

    def commit(self, terminal: dict) -> None:
        """Write what the turn answered, then close Leaf's account of it."""
        reply_error = None
        try:
            reply_error = self.settle_reply(terminal)
            if (
                reply_error is not None
                and self.correction is None
                and self.reply_target is not None
            ):
                assert self.delivery_id is not None
                self.correction = prepare_reply_correction(
                    self.session_id,
                    self.turn_id,
                    self.delivery_id,
                    self.reply_target,
                    reply_error,
                    generation=self.generation,
                )
        finally:
            self.close(terminal, reply_error)

    def settle_reply(self, terminal: dict) -> BaseException | None:
        """Commit the turn's final answer, or release the reply reservation held
        for one. A completed joined turn's answer is refused, so `commit` offers a
        correction; one that ended otherwise leaves the update owed, as any turn
        that ends without an answer does."""
        if self.reply_stream is not None and (
            self.events.joined or carries_user_message(terminal)
        ):
            if terminal.get("status") != "completed":
                # Ended as any unanswered turn does, its condition shown.
                self.reply_stream.withhold()
                return self.reply_stream.finish(terminal.get("status") or "failed")
            self.reply_stream.withdraw()
            return JoinedTurn(
                "a message the user sent in Codex shared the turn, so its final "
                "message was not posted as the reply to this input"
            )
        if self.reply_stream is not None:
            return self.reply_stream.finish(
                terminal.get("status") or "failed",
                self.events.final_text(terminal),
            )
        if self.reply_target is not None:
            from .thread import release_delivery_reply

            assert self.delivery_id is not None
            release_delivery_reply(self.session_id, self.delivery_id, self.reply_target)
        return None

    def close(self, terminal: dict, reply_error: BaseException | None) -> None:
        """Close the ended turn on every page the task claims, and take its reading off."""
        if reply_error is not None:
            print(
                f"Codex final reply rejected: {reply_error}",
                file=sys.stderr,
                flush=True,
            )
        current = self.activity_epoch()
        if current is not None and close_session_turn(
            self.session_id, self.turn_id, expected=current
        ):
            self.clear_activity()

    def disconnect(self) -> None:
        """Stop reading a turn that may still be running, its text left on the page."""
        try:
            if self.reply_stream is not None:
                self.reply_stream.disconnect()
        finally:
            self.clear_activity()

    def observe(self, message: dict, update: dict | None) -> None:
        """Record one notification, before its readings reach a page."""

    def observe_reply(self, update: dict | None, published: bool) -> None:
        """Record what one notification put in the user's reply."""


class CarriedTurn(TurnFold):
    """One delivery's Codex turn, read on the connection that started it.

    The turn exists because `turn/start` answered with it, so a client knows
    which turn is its own before reading a notification and nothing recovers the
    binding off the stream. The connection belongs to the turn for the turn's
    whole life: `thread/start` and `thread/resume` subscribe it, `turn/start`
    neither subscribes nor unsubscribes, and losing it is the turn ending.

    Every way the read can stop other than the completion composes a terminal of
    its own in `ended`, so a turn ends exactly once however it ended. What each
    client adds is what Leaf calls the turn — the page turn it opens and the reply
    reservation its answer commits under — which it opens in `begin`, and any
    account beyond the fold's that it owes in `close`.
    """

    silence: float | None = None

    def __init__(
        self,
        session_id: str,
        socket,
        turn_id: str,
        delivery_id: str,
        reply_target: dict | None,
        buffered=(),
        *,
        lifecycle: dict | None,
    ):
        super().__init__(
            session_id, turn_id, delivery_id, reply_target, lifecycle=lifecycle
        )
        self.socket = socket
        self.stream = TurnStream(socket, buffered, silence=self.silence)

    def follow(self) -> None:
        """Read this turn's connection to its end, and account for how it ended."""
        terminal = None
        try:
            self.begin()
            while True:
                message = self.stream.next()
                if message is None:
                    continue
                update = self.absorb(message)
                terminal = self.finished(message, update)
                if terminal is not None:
                    break
        except Exception as error:  # noqa: BLE001 - the turn's outcome, any fault
            terminal = self.ended(error)
        finally:
            self.stream.close()
        if terminal is not None:
            self.commit(terminal)

    def ended(self, error: BaseException) -> dict | None:
        """Compose the terminal of a turn whose stream ended it.

        A client returns None instead to leave the provider turn running and
        account for nothing, which is only honest where somebody else is watching
        it. Where nobody is, the client ends the turn before it composes this:
        closing a connection ends no turn, and App Server runs it either way.
        """
        fault = type(error).__name__
        detail = f"{fault}: {error}" if str(error) else fault
        return {
            "id": self.turn_id,
            "status": "failed",
            "error": {"message": f"App Server turn stream failed: {detail}"},
        }

    def begin(self) -> None:
        """Open Leaf's names for this turn, in whatever a client writes them."""
        raise NotImplementedError


def prepare_reply_correction(
    session_id: str,
    turn_id: str,
    delivery_id: str,
    target: dict,
    error: BaseException,
    *,
    generation: str | None,
) -> dict | None:
    """Return a durable repair offer for a rejected final's exact obligation.

    The rejected final wrote no answer. Reuse its immutable response address and
    captured input, with the admission diagnostic, instead of asking the user to
    send it again. Its accepted immutable delivery, current ownership, generation
    and still-current input authorize this retry even after Stop closed its turn.
    Newer input or a successor never inherits a stale repair. Each failed
    delivery owns at most one correction, including duplicate terminal callbacks.
    """
    if generation is None:
        return None
    page_dir = Path(target["page"])
    accepted = read_task_delivery(session_id, delivery_id)
    try:
        with (
            PageTransaction(page_dir) as page,
            flocked(delivery_lock_path(session_id)),
        ):
            claim = page.active_claim
            observed = session_record(session_id)
            if (
                claim is None
                or claim["id"] != session_id
                or observed is None
                or observed["generation"] != generation
                or not isinstance(accepted, Opened)
                or accepted.turn != turn_id
                or target["responds"] not in current_responses(page_dir, page.events)
            ):
                return None
            for directory in (
                delivery_dir(session_id),
                delivery_dir(session_id) / "history",
            ):
                for path in directory.glob("*.json"):
                    if read_record(path) is not None:
                        candidate = read_delivery(path.stem)
                        if (
                            candidate.get("correction", {}).get("delivery")
                            == delivery_id
                        ):
                            return candidate
            original = read_delivery(delivery_id)
            batch = next(
                batch for batch in original["batches"] if batch["page"] == str(page_dir)
            )
            captured = {
                **batch,
                "events": [
                    event
                    for event in batch["events"]
                    if event["id"] == target["responds"]
                ],
            }
            payload = freeze_delivery(
                [captured],
                turn_replies=True,
                correction={
                    "delivery": delivery_id,
                    "turn": turn_id,
                    "claim": {
                        key: claim[key] for key in ("id", "generation", "acquisition")
                    },
                    "diagnostic": str(error),
                    "instruction": "The previous final message was not posted as this input's reply, for the reason in `diagnostic`; fix that reason where it is a fault in your work. Then answer this same input. Retain completed work; do not repeat edits or external actions already performed.",
                },
            )
            record = Offering(
                payload["created_at"],
                (
                    {
                        "page": str(page_dir),
                        "session": session_id,
                        "events": [
                            {"seq": event["seq"], "id": event["id"]}
                            for event in captured["events"]
                        ],
                    },
                ),
            )
            write_record(record_path(session_id, payload["id"]), record)
            return payload
    except FileNotFoundError:
        return None


def record_path(session_id: str, delivery_id: str) -> Path:
    validate_delivery_id(delivery_id)
    return delivery_dir(session_id) / f"{delivery_id}.json"


@dataclass(frozen=True)
class DeliveryRecord:
    """Task-owned capture. A transition replaces the record under its task lock.

    Offering states carry immutable input references. Only accepted or abandoned
    outcomes carry pending page receipts; archiving is the empty-receipts outcome.
    Provider turn lifetime remains with TurnFold, independent of delivery receipt.
    """

    created_at: float
    batches: tuple[dict, ...]
    state: ClassVar[str]


@dataclass(frozen=True)
class Collecting(DeliveryRecord):
    state: ClassVar[str] = "collecting"


@dataclass(frozen=True)
class Offering(DeliveryRecord):
    state: ClassVar[str] = "offering"


@dataclass(frozen=True)
class HookOffer(Offering):
    turn: str
    state: ClassVar[str] = "hook"


@dataclass(frozen=True)
class StartingOffer(Offering):
    state: ClassVar[str] = "starting"


@dataclass(frozen=True)
class ReceiptOutcome(DeliveryRecord):
    pending: tuple[int, ...]


@dataclass(frozen=True)
class Accepted(ReceiptOutcome):
    state: ClassVar[str] = "queued"


@dataclass(frozen=True)
class Opened(Accepted):
    turn: str
    state: ClassVar[str] = "opened"


@dataclass(frozen=True)
class Abandoned(ReceiptOutcome):
    state: ClassVar[str] = "abandoned"


RECORD_VARIANTS = {
    variant.state: variant
    for variant in (
        Collecting,
        Offering,
        HookOffer,
        StartingOffer,
        Accepted,
        Opened,
        Abandoned,
    )
}
_STRING = {"type": "string"}
_ANSWER_FIELDS = {"reply": ("parent", "responds"), "markup": ("action",)}
_ANSWER = {
    "type": "object",
    "properties": {"kind": {"enum": list(_ANSWER_FIELDS)}},
    "required": ["kind"],
    "allOf": [
        {
            "if": {"properties": {"kind": {"const": kind}}},
            "then": {
                "properties": dict.fromkeys(names, _STRING),
                "required": list(names),
            },
        }
        for kind, names in _ANSWER_FIELDS.items()
    ],
}
# A collecting record holds the captured events themselves; every other state
# holds references into its immutable payload.
_COLLECTED_BATCH = {
    "properties": {
        "through_seq": {"type": "integer"},
        "threads": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": _STRING, "title": {"type": ["string", "null"]}},
                "required": ["id", "title"],
            },
        },
        "events": {
            "items": {
                "properties": {
                    "kind": _STRING,
                    "threads": {"type": "array", "items": _STRING},
                    "answer": _ANSWER,
                },
                "required": ["kind", "threads"],
            }
        },
    },
    "required": ["through_seq", "threads"],
}
_BATCH = {
    "type": "object",
    "properties": {
        "page": {"description": "The page directory.", **_STRING},
        "session": _STRING,
        "events": {
            "description": "The captured events, by id and `seq`.",
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {"id": _STRING, "seq": {"type": "integer"}},
                "required": ["id", "seq"],
            },
        },
    },
    "required": ["page", "session", "events"],
}


def _when_variant(holds, then: dict) -> dict:
    """Apply `then` to the records of every variant `holds` is true of."""
    states = [state for state, variant in RECORD_VARIANTS.items() if holds(variant)]
    return {"if": {"properties": {"state": {"enum": states}}}, "then": then}


RECORD_SCHEMA = {
    "description": "One delivery a Codex task is handing to its agent "
    "(`DeliveryRecord`), in the state home's `sessions/<digest>.deliveries/<id>.json` "
    "and, once nothing is owed on it, that directory's `history/`. A record at "
    "another format is ignored, and the events its page has not acknowledged are "
    "captured afresh.",
    "type": "object",
    "properties": {
        "state": {
            "description": "How far the handoff has gone (`RECORD_VARIANTS`).",
            "enum": list(RECORD_VARIANTS),
        },
        "created_at": {
            "description": "When it was captured, in seconds since the epoch.",
            "type": "number",
        },
        "batches": {
            "description": "One per page.",
            "type": "array",
            "minItems": 1,
            "items": _BATCH,
        },
    },
    "required": ["state", "created_at", "batches"],
    "allOf": [
        _when_variant(
            lambda variant: variant is Collecting,
            {"properties": {"batches": {"items": _COLLECTED_BATCH}}},
        ),
        _when_variant(
            lambda variant: issubclass(variant, ReceiptOutcome),
            {
                "properties": {
                    "pending": {
                        "description": "The indexes into `batches` whose page "
                        "receipts are still to be written.",
                        "type": "array",
                        "items": {"type": "integer", "minimum": 0},
                    }
                },
                "required": ["pending"],
            },
        ),
        _when_variant(
            lambda variant: "turn" in {item.name for item in fields(variant)},
            {
                "properties": {
                    "turn": {
                        "description": "The Codex turn that carries the delivery: "
                        "the one its hook ran in, or the one its App Server "
                        "delivery entered.",
                        "type": "string",
                        "minLength": 1,
                    }
                },
                "required": ["turn"],
            },
        ),
    ],
}
RECORD = Record("codex-delivery", RECORD_SCHEMA, since=14)


def read_record(path: Path) -> DeliveryRecord | None:
    """Decode one task record, live or archived, or None where this Leaf reads
    none, as for one in a state this Leaf does not know, or an offered record
    whose delivery this Leaf does not read. Only its pages being gone authorizes
    deleting a record (`state.retire_if_gone`)."""
    record = RECORD.read(path)
    if record is None:
        return None
    variant = RECORD_VARIANTS.get(record["state"])
    if variant is None:
        return None
    if variant is not Collecting and stored_delivery(path.stem) is None:
        return None
    values = {item.name: record[item.name] for item in fields(variant)}
    values["batches"] = tuple(values["batches"])
    if issubclass(variant, ReceiptOutcome):
        values["pending"] = tuple(values["pending"])
    return variant(**values)


def archive_record(path: Path, record: DeliveryRecord) -> bool:
    """Move completed delivery records out of the adapter's hot scan.

    `history/` is read one delivery at a time, so this, its one writer, is also
    where a readable archived record whose pages are all gone is removed."""
    if not isinstance(record, ReceiptOutcome) or record.pending:
        return False
    history = path.parent / "history"
    history.mkdir(parents=True, exist_ok=True)
    for archived in history.glob("*.json"):
        retire_if_gone(archived)
    path.replace(history / path.name)
    return True


def write_record(path: Path, record: DeliveryRecord) -> None:
    """Store one delivery record, retiring it once nothing is owed on it."""
    RECORD.write(path, {"state": record.state, **asdict(record)})
    archive_record(path, record)


def retire_gone_task_records() -> None:
    """Remove every Codex task's delivery record whose pages are all gone, from
    every task on this machine, and each task directory that leaves empty.

    A task reads its own records, so a task that has ended leaves them unread and
    nothing else would find its pages gone. An adapter retiring is the reading that
    does: it enumerates every task's records, each under that task's lock, taken one
    at a time and never inside another task's, so two retiring adapters cannot wait
    on each other. A record whose page still stands stays, archived ones included,
    since a later adapter of its task may yet bind a turn that outlived the first to
    it (`TaskConnection._reconcile`)."""
    for directory in sessions_home().glob("*.deliveries"):
        with flocked(directory.with_suffix(".delivery.lock")):
            history = directory / "history"
            for path in (*directory.glob("*.json"), *history.glob("*.json")):
                retire_if_gone(path)
            for emptied in (history, directory):
                if emptied.is_dir() and not any(emptied.iterdir()):
                    emptied.rmdir()


def delivery_records(session_id: str) -> list[tuple[Path, DeliveryRecord]]:
    """Every current delivery record one task holds, oldest first, removing each
    whose pages are all gone (`state.retire_if_gone`). Every caller holds the
    task's delivery lock."""
    directory = delivery_dir(session_id)
    if not directory.is_dir():
        return []
    records = []
    for path in directory.glob("*.json"):
        try:
            validate_delivery_id(path.stem)
        except ValueError:
            continue
        if retire_if_gone(path):
            continue
        record = read_record(path)
        if record is None:
            continue
        if archive_record(path, record):
            continue
        records.append((path, record))
    return sorted(records, key=lambda item: (item[1].created_at, item[0].name))


def _collecting_record(session_id: str) -> tuple[Path, Collecting] | None:
    """The one record still collecting events for this task, if it has one."""
    current = [
        (path, record)
        for path, record in delivery_records(session_id)
        if isinstance(record, Collecting)
    ]
    if len(current) > 1:
        raise RuntimeError(
            f"Codex task {session_id} has multiple collecting Leaf deliveries"
        )
    return current[0] if current else None


@dataclass(frozen=True)
class PreparedDelivery:
    """One immutable delivery and its claim transition for rollback."""

    prompt: str
    payload: dict
    claim_transition: tuple[dict | None, dict] | None = field(
        default=None, compare=False, repr=False
    )


def _readdress_record(path: Path) -> Path:
    """Give a collecting record a fresh identity after a delivery collision."""
    while True:
        candidate = new_delivery_id()
        replacement = path.with_name(f"{candidate}.json")
        if replacement.exists() or delivery_path(candidate).exists():
            continue
        path.replace(replacement)
        return replacement


@dataclass(frozen=True)
class HookTurn:
    turn: str


def offer_delivery(
    path: Path,
    record: Collecting | Offering,
    *,
    transport: Literal["app-server", "queue"] | HookTurn,
) -> PreparedDelivery:
    """Freeze a pointer and reserve its offer to a hook turn or the idle transport.

    Existing frozen input never changes. An uncertain provider start keeps its
    reservation; only provider evidence or a definitive refusal can move it.
    """
    if isinstance(record, StartingOffer) and transport != "app-server":
        raise AppServerDeliveryUncertain("the delivery is awaiting reconciliation")
    if isinstance(record, Offering):
        payload = read_delivery(path.stem)
        offered = record
    else:
        while True:
            try:
                payload = freeze_delivery(
                    record.batches,
                    turn_replies=transport == "app-server",
                    delivery_id=path.stem,
                    created_at=record.created_at,
                )
                break
            except DeliveryIdConflict:
                path = _readdress_record(path)
        batches = tuple(
            {
                "page": batch["page"],
                "session": batch["session"],
                "events": [
                    {"seq": event["seq"], "id": event["id"]}
                    for event in batch["events"]
                ],
            }
            for batch in record.batches
        )
        offered = Offering(record.created_at, batches)
    if not isinstance(offered, StartingOffer):
        offered = (
            HookOffer(offered.created_at, offered.batches, transport.turn)
            if isinstance(transport, HookTurn)
            else Offering(offered.created_at, offered.batches)
        )
    if offered != record:
        write_record(path, offered)
    return PreparedDelivery(delivery_pointer_prompt(path.stem), payload)


def begin_delivery_start(session_id: str, delivery_id: str) -> bool:
    """Reserve a provider start once, after its caller obtained fresh idle evidence."""
    path = record_path(session_id, delivery_id)
    with flocked(delivery_lock_path(session_id)):
        record = read_record(path)
        if isinstance(record, StartingOffer):
            raise AppServerDeliveryUncertain("the delivery is awaiting reconciliation")
        if not isinstance(record, Offering):
            return False
        write_record(path, StartingOffer(record.created_at, record.batches))
    return True


def release_delivery_start(session_id: str, delivery_id: str) -> None:
    """A definitive provider refusal makes only its pending start offerable again."""
    path = record_path(session_id, delivery_id)
    with flocked(delivery_lock_path(session_id)):
        record = read_record(path)
        if isinstance(record, StartingOffer):
            write_record(path, Offering(record.created_at, record.batches))


def append_batch(
    session_id: str,
    page_dir: Path,
    transaction: PageTransaction,
    batch: list[dict],
) -> tuple[Path, int, dict] | None:
    """Append fresh events to the task's one collecting record."""
    current = _collecting_record(session_id)
    if current is None:
        while True:
            delivery_id = new_delivery_id()
            path = record_path(session_id, delivery_id)
            if not path.exists() and not delivery_path(delivery_id).exists():
                break
        path.parent.mkdir(parents=True, exist_ok=True)
        record = Collecting(time.time(), ())
    else:
        path, record = current

    delivered = {
        (entry["page"], event["seq"], event["id"])
        for _, held in delivery_records(session_id)
        for entry in held.batches
        for event in entry["events"]
    }
    fresh = [
        event
        for event in batch
        if (str(page_dir), event["seq"], event["id"]) not in delivered
    ]
    if not fresh:
        return None

    # A record carries at most one thread reply, so the turn an App Server offer
    # starts has one reply to write with its messages.
    replies = sum(
        event["answer"]["kind"] == "reply"
        for entry in record.batches
        for event in entry["events"]
        if "answer" in event
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

    data = batch_data(page_dir, transaction, selected, responses=responses)
    entry = {
        **data,
        "session": session_id,
    }
    record = replace(record, batches=(*record.batches, entry))
    write_record(path, record)
    return path, len(record.batches) - 1, entry


def offer_hook_delivery(
    session_id: str, expected: dict | None, *, received: bool = True
) -> tuple[str | None, dict | None]:
    """Offer complete input inline, or by pointer where Codex wouldn't show it whole
    (`Harness.fits_hook_context`), without receipt.
    `received` is `delivery.deliverable`'s: the tool hook leaves it false.

    The agent's explicit `delivery ack` confirms complete input in its turn. If the
    hook output arrives after the turn ends, the adapter queues the same frozen
    pointer instead. An offering already owned by another transport is left alone.

    The caller's exact lifecycle owns every renewal and reservation. Return the
    supplied lifecycle or this operation's last renewal, even without input,
    so the caller cannot adopt a prompt that arrives during or after the offer.
    """
    lock = delivery_lock_path(session_id)
    if not turn_open(expected):
        return None, expected
    for page_dir in owned_pages(session_id):
        try:
            with PageTransaction(page_dir) as page:
                if page.active_claim is None or page.active_claim["id"] != session_id:
                    continue
                with flocked(lock):
                    if session_record(session_id) != expected:
                        return None, expected
                    expected = renew_turn(expected)
                    if batch := deliverable(page, received=received):
                        append_batch(session_id, page_dir, page, batch)
        except FileNotFoundError:
            continue
    with flocked(lock):
        records = delivery_records(session_id)
        if session_record(session_id) != expected:
            return None, expected
        if any(not isinstance(record, Collecting) for _, record in records):
            return None, expected
        pending = next(
            (
                (path, record)
                for path, record in records
                if isinstance(record, Collecting)
            ),
            None,
        )
        if pending is None:
            return None, expected
        path, record = pending
        prepared = offer_delivery(path, record, transport=HookTurn(expected["turn"]))
        context = json.dumps(
            reader_envelope(prepared.payload),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return (
            context if CodexHarness.fits_hook_context(context) else prepared.prompt
        ), expected


def finish_codex_batch(
    path: Path, batch_index: int, batch: dict, outcome: Accepted
) -> dict | None:
    """Receipt and retire one accepted batch without opening a session turn.

    Page validation, pickup and cursor writes share delivery.receive_batch.
    The durable accepted record survives interruption before its receipt mark;
    recovery retries this same operation. A gone or transferred page retires its
    batch without advancing a successor's cursor or proving provider binding.
    No page transaction is taken while holding the delivery lock.
    """
    received = None
    try:
        with (
            PageTransaction(Path(batch["page"])) as page,
            receive_batch(page, batch, session_id=batch["session"]) as events,
        ):
            record_pickup(
                page,
                events,
                phase="opened" if isinstance(outcome, Opened) else "queued",
                session=batch["session"],
                turn=outcome.turn if isinstance(outcome, Opened) else None,
                # The record keeps only the batch's identities; the envelope its
                # name addresses holds the refs.
                refs=batch_refs(read_delivery(path.stem)["batches"][batch_index]),
            )
            received = {
                "page": Path(batch["page"]),
                "events": tuple(event["id"] for event in batch["events"]),
            }
    except (FileNotFoundError, ReceiptRefused):
        pass
    with flocked(delivery_lock_path(batch["session"])):
        _receipt_completed(path, batch_index)
    return received


def _receipt_completed(path: Path, index: int) -> None:
    """Commit progress after idempotent page effects, with the task lock held."""
    record = read_record(path)
    if isinstance(record, ReceiptOutcome) and index in record.pending:
        write_record(
            path,
            replace(record, pending=tuple(i for i in record.pending if i != index)),
        )


def recover_codex_receipt(session_id: str) -> bool:
    """Retry the oldest outstanding page batch from its durable outcome.

    Page effects are idempotent, so a crash after pickup, cursor commit, progress
    commit or archive requires no cursor inference and cannot queue a new delivery.
    """
    settled = settle_answered_deliveries(session_id)
    with flocked(delivery_lock_path(session_id)):
        pending = min(
            (
                (path, index, record)
                for path, record in delivery_records(session_id)
                if isinstance(record, ReceiptOutcome)
                for index in record.pending
            ),
            key=lambda item: (
                item[2].batches[item[1]]["page"],
                min(event["seq"] for event in item[2].batches[item[1]]["events"]),
            ),
            default=None,
        )
    if pending is None:
        return settled
    path, index, record = pending
    batch = record.batches[index]
    if isinstance(record, Abandoned):
        finish_abandoned_batch(path, index, batch)
    else:
        assert isinstance(record, Accepted)
        finish_codex_batch(path, index, batch, record)
    return True


UNCONFIRMED_DELIVERY = "delivery_unconfirmed"
UNCONFIRMED_TEXT = (
    "Leaf could not confirm this delivery and will not retry it automatically. "
    "Send it again if I still need an answer."
)


def reply_target_answered(target: dict) -> bool | None:
    """Read exact reply completion, or None when its page no longer exists."""
    from .thread import successful_replies

    try:
        with PageTransaction(Path(target["page"])) as page:
            return bool(successful_replies(page.events, target["responds"]))
    except FileNotFoundError:
        return None


def settle_answered_deliveries(session_id: str) -> bool:
    """Retire unknown harness attempts already answered manually, even while offline."""
    with flocked(delivery_lock_path(session_id)):
        pending = [
            path.stem
            for path, record in delivery_records(session_id)
            if isinstance(record, StartingOffer)
        ]
    settled = False
    for delivery_id in pending:
        target = delivery_stream_reply_target(session_id, delivery_id)
        if target is None:
            continue
        if reply_target_answered(target):
            payload = stored_delivery(delivery_id)
            assert payload is not None
            abandon_uncertain_delivery(session_id, payload)
            settled = True
    return settled


def abandon_uncertain_delivery(session_id: str, payload: dict) -> None:
    """Return an unstartable or unknown offer without asserting a provider ending.

    The abandoned record is durable before page failure receipts, so recovery
    finishes an interrupted abandonment. Archiving retains correlation for late
    provider evidence, and complete page receipts prevent recapturing the attempt.
    """
    path = record_path(session_id, payload["id"])
    with flocked(delivery_lock_path(session_id)):
        record = read_record(path)
        if isinstance(record, Offering):
            record = Abandoned(
                record.created_at, record.batches, tuple(range(len(record.batches)))
            )
            write_record(path, record)
        if not isinstance(record, Abandoned):
            return
    for index in record.pending:
        finish_abandoned_batch(path, index, record.batches[index])


def finish_abandoned_batch(path: Path, batch_index: int, batch: dict) -> None:
    """Write honest failure receipts and retire this batch under current ownership."""
    from .thread import fail_answer, release_delivery_reply

    page_dir = Path(batch["page"])
    session_id = batch["session"]
    # Releasing the reply reservation is part of this resumable receipt, not just
    # its initiator, so a crash right after the durable abandonment cannot strand it.
    target = delivery_stream_reply_target(session_id, path.stem)
    if target is not None:
        release_delivery_reply(session_id, path.stem, target)
    try:
        # The durable abandoned record is this consumer's outcome. Validate its
        # exact captured page input before writing any failure to that page.
        with (
            PageTransaction(page_dir) as page,
            receive_batch(page, batch, session_id=session_id) as events,
        ):
            captured = list(events)
        for event in captured:
            fail_answer(
                page_dir,
                event["id"],
                UNCONFIRMED_DELIVERY,
                UNCONFIRMED_TEXT,
                attempt=f"unconfirmed-{path.stem}-{event['id']}",
                identity={"session": session_id},
                only_if_unclaimed=False,
                claimed_session=session_id,
            )
        with (
            PageTransaction(page_dir) as page,
            receive_batch(page, batch, session_id=session_id) as events,
        ):
            owed = current_responses(page_dir, page.events)
            record_pickup(
                page,
                [event for event in events if event["id"] in owed],
                phase="failed",
                session=session_id,
                failure=UNCONFIRMED_DELIVERY,
            )
    except (FileNotFoundError, ReceiptRefused):
        pass
    with flocked(delivery_lock_path(session_id)):
        _receipt_completed(path, batch_index)


def delivery_owed_updates(payload: dict) -> list[dict]:
    """Every update in one delivery that was owed an answer when it was captured,
    whatever answer it takes."""
    return [
        {"page": batch["page"], "responds": event["id"]}
        for batch in payload["batches"]
        for event in batch["events"]
        if "answer" in event
    ]


def delivery_stream_reply_target(session_id: str, delivery_id: str) -> dict | None:
    """Resolve one task-owned delivery identity to the reply its turn writes."""
    path = record_path(session_id, delivery_id)
    records = (path, path.parent / "history" / path.name)
    if not any(read_record(record) is not None for record in records):
        return None
    return stream_reply_target(read_delivery(delivery_id))


def read_task_delivery(session_id: str, delivery_id: str) -> DeliveryRecord | None:
    """Read one task-owned delivery variant, live or archived, under its lock."""
    path = record_path(session_id, delivery_id)
    with flocked(delivery_lock_path(session_id)):
        record = read_record(path)
        if record is None:
            record = read_record(path.parent / "history" / path.name)
    return record


def prepare_codex_delivery(page_dir: Path, harness: Harness) -> PreparedDelivery:
    """Reuse held input, or claim PAGE to capture an embedded task's first input.

    An immutable pending offer observes ownership; it never reacquires the page.
    A correction also retains the acquisition that authorized its rejected final.
    """
    session_id = harness.session
    transition = None
    pending_id = None
    try:
        with PageTransaction(page_dir) as page:
            lock = delivery_lock_path(session_id)
            with flocked(lock):
                pending = next(
                    (
                        (path, record)
                        for path, record in delivery_records(session_id)
                        if isinstance(record, (Collecting, Offering))
                    ),
                    None,
                )
                if pending is not None:
                    pending_id = pending[0].stem
                    claim = page.active_claim
                    if claim is None or claim["id"] != session_id:
                        raise ReceiptRefused(
                            "the pending delivery no longer owns its page"
                        )
                    offered = offer_delivery(*pending, transport="app-server")
                    return offered
            transition = page.take_claim(harness)
            batch = deliverable(page)
            with flocked(lock):
                if not batch:
                    raise RuntimeError("the page has no Leaf input to deliver")
                captured = append_batch(
                    session_id,
                    page_dir,
                    page,
                    batch,
                )
                if captured is None:
                    raise RuntimeError("the page input is already in a Codex delivery")
                path, _, _ = captured
                record = read_record(path)
                assert isinstance(record, (Collecting, Offering))
                offered = offer_delivery(path, record, transport="app-server")
                return replace(offered, claim_transition=transition)
    except BaseException as error:
        restore_page_claim(page_dir, transition)
        if isinstance(error, ReceiptRefused) and pending_id is not None:
            abandon_uncertain_delivery(session_id, read_delivery(pending_id))
        raise


def accept_codex_delivery(
    session_id: str,
    delivery_id: str,
    turn: str | None,
    *,
    hook_observation: dict | None = None,
) -> list[dict]:
    """Accept one exact delivery before completing its recoverable page receipts.

    A turn id proves entry into that provider turn; None proves durable queue
    acceptance. A hook pointer's confirmation also supplies the observation that must
    still stand under the delivery lock. All transports commit accepted state first,
    then receipt each batch through finish_codex_batch, which recovery also uses.

    A retry finishes only outstanding receipts, preserving its original acceptance
    evidence. Acceptance opens no turn: an App Server client observes that
    separately.
    Return successfully completed page/event addresses for binding verification.
    """
    path = record_path(session_id, delivery_id)
    with flocked(delivery_lock_path(session_id)):
        record = read_record(path)
        if not isinstance(record, (Offering, Accepted)):
            return []
        if hook_observation is not None and (
            hook_turn(session_id) != hook_observation
            or not hook_observation["running"]
            or hook_observation["turn"] != turn
            or not isinstance(record, (HookOffer, Opened))
            or record.turn != turn
        ):
            return []
        if isinstance(record, Offering):
            pending = tuple(range(len(record.batches)))
            record = (
                Opened(record.created_at, record.batches, pending, turn)
                if turn is not None
                else Accepted(record.created_at, record.batches, pending)
            )
            write_record(path, record)
    accepted = []
    for index in record.pending:
        received = finish_codex_batch(path, index, record.batches[index], record)
        if received is not None:
            accepted.append(received)
    return accepted


def open_app_server_delivery(
    page_dir: Path,
    session_id: str,
    delivery_id: str,
    event_ids: tuple[str, ...],
    turn: str,
) -> None:
    """Record a provider-observed App Server delivery as opened in its turn,
    accepting it when its record is still offering."""
    record = read_task_delivery(session_id, delivery_id)
    accepted = accept_codex_delivery(session_id, delivery_id, turn)
    if isinstance(record, Offering):
        if [
            delivery["events"] for delivery in accepted if delivery["page"] == page_dir
        ] != [event_ids]:
            raise RuntimeError(
                "the recovered App Server turn accepted an unexpected page batch"
            )
        return
    with PageTransaction(page_dir) as page:
        if page.claim_of(session_id) is None:
            raise RuntimeError("the App Server delivery no longer owns its page")
        by_id = {event["id"]: event for event in page.events}
        if any(event_id not in by_id for event_id in event_ids):
            raise RuntimeError("the App Server delivery no longer matches its page")
        record_pickup(
            page,
            [by_id[event_id] for event_id in event_ids],
            phase="opened",
            session=session_id,
            turn=turn,
        )


def abandon_codex_delivery(session_id: str, event_id: str) -> None:
    """Retire an unaccepted delivery after its triggering event was settled."""
    lock = delivery_lock_path(session_id)
    with flocked(lock):
        matching = [
            path
            for path, record in delivery_records(session_id)
            if isinstance(record, Offering)
            and any(
                event["id"] == event_id
                for batch in record.batches
                for event in batch["events"]
            )
        ]
        if len(matching) > 1:
            raise RuntimeError("the Codex task has duplicate offered deliveries")
        if matching:
            matching[0].unlink()
