"""Starting a delivery's turn in a chat the Codex desktop app holds, with no message in
the user's name.

The app runs its chats on an App Server of its own, a child process it speaks to over
stdio, so no other process can connect to that server. `codex app-server proxy` and the
local daemon it reaches are a separate server, which reads the same history, holds none
of the app's chats and can't resume one, since Codex keeps one writer per chat. What
reaches a chat is the router the app's own clients share, at
`$CODEX_HOME/ipc/ipc.sock`, a socket only this user can open: a client asks it which
client owns a chat, then asks that owner to start a turn. The owner sends `turn/start`
on its App Server with the chat's own settings, so the request is the one every Leaf
delivery turn takes (`codex.app_server_turn_start_params`). The delivery enters as a
tool output, which the app doesn't draw, and the app runs the turn as it runs any other.
A start on a running turn steers into it and answers with that turn's id, as
`turn/start` does.

A client owns a chat once a window has opened it, and keeps it when the window moves to
another chat, until the app quits. A chat the app only resumed for a queued message has
no owner, so it stays on the queue until a window opens it. An owner answers within
milliseconds, and the router answers for a chat nobody owns only after waiting out its
ten-second discovery timeout on a client that doesn't reply. So `OWNER_TIMEOUT` reads
silence as no owner, and the adapter's queue carries that delivery without the wait.

The start keeps the App Server delivery contract (`codex.start_app_server_delivery`),
so the same input never runs twice. Leaf reserves the start (`codex.StartingOffer`)
only once the app has named the chat's owner, and only a refusal made before the owner
ran the request releases it: the router's `no-client-found`, which a version it doesn't
know also gives, and the owner's `no-handler-for-request` and
`request-version-mismatch` (`REFUSALS`). Any other answer, a lost or unreadable one
included, may follow a started turn, even the owner's own five-second
`thread-follower-start-turn-timeout`, after which its start runs on. The chat's
transcript settles such a start (`settle_desktop_start`), since the app records each
turn's `leaf_delivery` tool output there (`codex.transcript_delivery_turn`). Leaf
accepts the delivery in the turn that took it, or, once no turn of the chat is running
and `SETTLE_WINDOW` has passed with none, abandons it as unconfirmed
(`codex.abandon_uncertain_delivery`) and doesn't send it again. A reservation's record
is written once, as the start is reserved, so its file's modification time dates it.

This is the app's private protocol, and each request names the version the app's table
gives its method. A message is a little-endian 32-bit length and then that much JSON.
A connected client also receives broadcasts and a discovery request for each request
another client makes. This one stays connected for a single start, so it reads past them
and answers none, which delays only another client's no-owner answer, and only while
this one is connected. Whatever a later app changes before the start goes out, a frame
that isn't a JSON object included, raises `DesktopUnavailable`, whose message the
adapter logs as it queues the delivery instead.

Rejected: running the app on a server Leaf can also reach, through its
`CODEX_APP_SERVER_WS_URL`, which `notes/codex-integration.md` weighs. It reaches every
chat and lets Leaf follow each turn, but only for an app launched that way.
"""

import json
import socket
import time
import uuid
from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from pathlib import Path

from .codex import (
    START_TIMEOUT,
    AppServerRequestRejected,
    StartingOffer,
    abandon_uncertain_delivery,
    accept_codex_delivery,
    begin_delivery_start,
    delivery_records,
    release_delivery_start,
    start_app_server_delivery,
    transcript_delivery_turn,
)
from .codex_state import delivery_lock_path
from .delivery import read_delivery
from .harness import codex_home
from .state import flocked, session_record, turn_open

OWNER_TIMEOUT = 1
# Longer than the router waits on a start (`START_TIMEOUT`), with room for the app to
# load the chat first.
SETTLE_WINDOW = 60
REFUSALS = {"no-client-found", "no-handler-for-request", "request-version-mismatch"}


class DesktopUnavailable(RuntimeError):
    """The app can't start the delivery's turn, and Leaf sent nothing that could."""


def _text(message: dict, *keys: str) -> str:
    """The non-empty string at `keys` in a router message, which a later app may move."""
    value = message
    for key in keys:
        value = value.get(key) if isinstance(value, dict) else None
    if not isinstance(value, str) or not value:
        raise ValueError(f"the app's router answered without {'.'.join(keys)}")
    return value


class _Router:
    """One client's connection to the app's router."""

    def __init__(self, connection: socket.socket):
        self.connection = connection
        self.stream = connection.makefile("rb")
        self.client = "initializing-client"

    def _read(self) -> dict:
        header = self.stream.read(4)
        if len(header) < 4:
            raise ConnectionError("the app closed its router connection")
        message = json.loads(self.stream.read(int.from_bytes(header, "little")))
        if not isinstance(message, dict):
            raise ValueError(f"the app's router sent a {type(message).__name__} frame")
        return message

    def request(
        self,
        method: str,
        version: int,
        params: dict,
        timeout: float,
        target: str | None = None,
    ) -> dict:
        """Make one request and return its answer, reading past the rest."""
        request_id = str(uuid.uuid4())
        data = json.dumps(
            {
                "type": "request",
                "requestId": request_id,
                "sourceClientId": self.client,
                "version": version,
                "method": method,
                "params": params,
                "targetClientId": target,
                "timeoutMs": round(timeout * 1000),
            }
        ).encode()
        deadline = time.monotonic() + timeout
        self.connection.settimeout(timeout)
        self.connection.sendall(len(data).to_bytes(4, "little") + data)
        while True:
            self.connection.settimeout(max(deadline - time.monotonic(), 0.001))
            message = self._read()
            if (
                message.get("type") == "response"
                and message.get("requestId") == request_id
            ):
                return message

    def owner(self, thread_id: str) -> str:
        """Join as a client and return the client that owns `thread_id`."""
        answer = self.request("initialize", 0, {"clientType": "leaf"}, OWNER_TIMEOUT)
        self.client = _text(answer, "result", "clientId")
        try:
            answer = self.request(
                "thread-owner-discovery",
                1,
                {"hostId": "local", "conversationId": thread_id},
                OWNER_TIMEOUT,
            )
        except TimeoutError as error:
            raise DesktopUnavailable(
                f"the app named no owner of this chat within {OWNER_TIMEOUT} s"
            ) from error
        if answer.get("resultType") != "success":
            raise DesktopUnavailable(
                f"the app named no owner of this chat: {answer.get('error')}"
            )
        return _text(answer, "handledByClientId")

    def start(self, owner: str, thread_id: str, request: dict) -> dict:
        """Ask `owner` for the `turn/start` `request`, and return its result."""
        answer = self.request(
            "thread-follower-start-turn",
            2,
            {
                "conversationId": thread_id,
                "turnStart": {"request": request, "context": {}},
            },
            START_TIMEOUT,
            owner,
        )
        if answer.get("resultType") == "success":
            result = answer.get("result")
            started = result.get("result") if isinstance(result, dict) else None
            return started if isinstance(started, dict) else {}
        if answer.get("error") in REFUSALS:
            raise AppServerRequestRejected(answer["error"])
        raise RuntimeError(f"the app answered the start with {answer.get('error')!r}")


@contextmanager
def _router() -> Generator[_Router]:
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(OWNER_TIMEOUT)
        connection.connect(str(codex_home() / "ipc" / "ipc.sock"))
        router = _Router(connection)
        with router.stream:
            yield router


def start_desktop_delivery(session_id: str, payload: dict) -> None:
    """Start `payload`'s turn in the desktop chat `session_id` and accept it there.

    Raise `DesktopUnavailable` where the app can't, leaving the offer for the queue,
    and `codex.AppServerDeliveryUncertain` where a turn may have started, leaving the
    start reserved for `settle_desktop_start`."""
    with ExitStack() as stack:
        try:
            router = stack.enter_context(_router())
            owner = router.owner(session_id)
        except (OSError, ValueError) as error:
            raise DesktopUnavailable(f"the app's router failed: {error!r}") from error
        if not begin_delivery_start(session_id, payload["id"]):
            return
        try:
            admitted = start_app_server_delivery(
                lambda _method, params: router.start(owner, session_id, params),
                session_id,
                payload,
            )
        except AppServerRequestRejected as error:
            release_delivery_start(session_id, payload["id"])
            raise DesktopUnavailable(f"the app refused the start: {error}") from error
    accept_codex_delivery(session_id, payload["id"], admitted["turn"])


def settle_desktop_start(session_id: str) -> bool:
    """Settle each start the chat reserved from its transcript, and return whether one
    still stands unsettled, before which nothing else is offered."""
    with flocked(delivery_lock_path(session_id)):
        starting = [
            (path, record)
            for path, record in delivery_records(session_id)
            if isinstance(record, StartingOffer)
        ]
    standing = False
    for path, record in starting:
        session = session_record(session_id)
        transcript = (session or {}).get("transcript_path")
        turn = (
            transcript_delivery_turn(Path(transcript), path.stem, record.created_at)
            if transcript
            else None
        )
        if turn is not None:
            accept_codex_delivery(session_id, path.stem, turn)
        elif not turn_open(session) and (
            time.time() - path.stat().st_mtime > SETTLE_WINDOW
        ):
            abandon_uncertain_delivery(session_id, read_delivery(path.stem))
        else:
            standing = True
    return standing
