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

This is the app's private protocol, and each request names the version the app's table
gives its method, which must match exactly. Whatever a later app changes reads here as
no owner or a failed start, which leaves delivery on the queue, as it was before this
route existed. A message is a little-endian 32-bit length and then that much JSON. A
connected client also receives broadcasts and a discovery request for each request
another client makes. This one stays connected for a single start, so it reads past them
and answers none, which delays only another client's no-owner answer, and only while
this one is connected.

Rejected: running the app on a server Leaf can also reach, through its
`CODEX_APP_SERVER_WS_URL`, which `notes/codex-integration.md` weighs. It reaches every
chat and lets Leaf follow each turn, but only for an app launched that way.
"""

import json
import socket
import time
import uuid
from typing import BinaryIO

from .codex import START_TIMEOUT, app_server_turn_start_params
from .harness import codex_home

OWNER_TIMEOUT = 1


class DesktopStartFailed(RuntimeError):
    """The app refused a start, or its answer never came, so a turn may have started."""


def _read_message(stream: BinaryIO) -> dict:
    header = stream.read(4)
    body = stream.read(int.from_bytes(header, "little"))
    if len(header) < 4:
        raise ConnectionError("the Codex desktop app closed its router connection")
    return json.loads(body)


def _request(
    connection: socket.socket,
    stream: BinaryIO,
    method: str,
    version: int,
    params: dict,
    timeout: float,
    client: str = "initializing-client",
    target: str | None = None,
) -> dict:
    """Make one request of the router and return its answer, reading past the rest."""
    request_id = str(uuid.uuid4())
    data = json.dumps(
        {
            "type": "request",
            "requestId": request_id,
            "sourceClientId": client,
            "version": version,
            "method": method,
            "params": params,
            "targetClientId": target,
            "timeoutMs": round(timeout * 1000),
        }
    ).encode()
    deadline = time.monotonic() + timeout
    connection.settimeout(timeout)
    connection.sendall(len(data).to_bytes(4, "little") + data)
    while True:
        connection.settimeout(max(deadline - time.monotonic(), 0.001))
        message = _read_message(stream)
        if message.get("type") == "response" and message.get("requestId") == request_id:
            return message


def start_desktop_turn(thread_id: str, payload: dict) -> str | None:
    """Start `payload`'s turn in the desktop chat `thread_id` and return its turn id, or
    None where no client owns that chat. Raise `DesktopStartFailed` where the attempt
    went wrong, the app not running included."""
    try:
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(OWNER_TIMEOUT)
            connection.connect(str(codex_home() / "ipc" / "ipc.sock"))
            with connection.makefile("rb") as stream:
                client = _request(
                    connection,
                    stream,
                    "initialize",
                    0,
                    {"clientType": "leaf"},
                    OWNER_TIMEOUT,
                )["result"]["clientId"]
                try:
                    owner = _request(
                        connection,
                        stream,
                        "thread-owner-discovery",
                        1,
                        {"hostId": "local", "conversationId": thread_id},
                        OWNER_TIMEOUT,
                        client,
                    )
                except TimeoutError:
                    return None
                if owner["resultType"] != "success":
                    return None
                started = _request(
                    connection,
                    stream,
                    "thread-follower-start-turn",
                    2,
                    {
                        "conversationId": thread_id,
                        "turnStart": {
                            "request": app_server_turn_start_params(thread_id, payload),
                            "context": {},
                        },
                    },
                    START_TIMEOUT,
                    client,
                    owner["handledByClientId"],
                )
        if started["resultType"] != "success":
            raise DesktopStartFailed(started.get("error"))
        return started["result"]["result"]["turn"]["id"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise DesktopStartFailed(repr(error)) from error
