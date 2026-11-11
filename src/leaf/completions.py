"""Model completions a page server asks of a Claude Code session, which Leaf's hooks
module (`hooks/claude-code.ts`) makes with `$.model.complete` on the session's own
model client and credentials, and hands back.

A page server can't reach the module directly, so each request is a record among
the session's own files in the state home (`session_file`). The page server writes
the record, reads it again every `POLL_S` until the module's reply is in it or its
deadline passes, and then removes it (`ask`). It polls because a page server holds
no native filesystem subscription (`file_changes`), and a request lasts only as long
as the model takes, a median 1.5 s for a title.

The session's pages follower (`hooks.cmd_pages`) waits on the session's records
(`watch`), and lists each request as soon as it is written (`pending`), apart from
the pages it lists: a page the agent closed is left off that list, yet its claim
still names the session, whose model titles the page's new threads. The module
makes the completion and hands the reply to Leaf
with `leaf hook --fork`, which writes it into the record (`cmd_reply`). Python
writes the whole request, its model, system prompt and limits included, and reads
the reply; the module only carries both.

The follower stops listing a request once its deadline passes. A reply that arrives
after its page server stopped waiting finds no record and is dropped, under the
session's completions lock. A record outlives its request only when its page server
died while waiting, and goes with the session's other files once the session has
ended and no claim names it (`state.end_session`). A session whose Claude Code
process isn't running answers nothing, and its requests fail at their deadline.
"""

import fnmatch
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from .state import (
    Record,
    described,
    flocked,
    object_schema,
    session_file,
)

if TYPE_CHECKING:
    from .file_changes import FileChanges

# How often a waiting page server reads its request again.
POLL_S = 0.05
# How much of a request's time limit is left after the model's own, for the relay
# through the pages follower, the module and the step that writes the reply.
GRACE_S = 5.0

COMPLETION = Record(
    "completion",
    described(
        "A model completion a page server asks of a Claude Code session, in the state "
        "home's `sessions/<digest>.completion.<id>`, which Leaf's hooks module makes "
        "and replies to (`completions`).",
        object_schema(
            {
                "request": described(
                    "What the module passes to `$.model.complete` as it stands.",
                    {"type": "object"},
                ),
                "deadline": described(
                    "When the page server stops waiting, in POSIX seconds.",
                    {"type": "number"},
                ),
            },
            {
                "reply": described(
                    "What the model call came to, as the module reports it: the "
                    "answer's `text`, or why there is none (`failed`, with the HTTP "
                    "`status` of an API error), its `usage` and `elapsed_ms`.",
                    {"type": "object"},
                )
            },
        ),
    ),
    since=43,
)


def _path(session_id: str, completion: str) -> Path:
    return session_file(session_id, f"completion.{completion}")


def _lock_path(session_id: str) -> Path:
    # Outside `completion.*`, which names the requests.
    return session_file(session_id, "completions.lock")


def ask(session_id: str, request: dict, *, timeout: float) -> dict:
    """Ask `session_id`'s module for the completion `request`, and return its reply,
    or raise `TimeoutError` once `timeout` seconds pass without one."""
    path = _path(session_id, uuid.uuid4().hex)
    deadline = time.time() + timeout
    COMPLETION.write(path, {"request": request, "deadline": deadline})
    try:
        while True:
            asked = COMPLETION.read(path)
            if asked is not None and "reply" in asked:
                return asked["reply"]
            if time.time() >= deadline:
                raise TimeoutError(
                    f"the Claude Code session replied to no completion within "
                    f"{timeout:g} s"
                )
            time.sleep(POLL_S)
    finally:
        with flocked(_lock_path(session_id)):
            path.unlink(missing_ok=True)


def watch(session_id: str) -> "FileChanges":
    """A subscription that hears each of `session_id`'s requests written, answered
    or removed."""
    # Here, so the step that hands a reply over (`cmd_reply`) never imports it.
    from .file_changes import FileChanges

    pattern = _path(session_id, "*")
    # Resolved, as notifications name it.
    directory = pattern.parent.resolve()
    return FileChanges(
        {directory: False},
        lambda path: (
            path.parent == directory and fnmatch.fnmatch(path.name, pattern.name)
        ),
    )


def pending(session_id: str) -> list[dict]:
    """`session_id`'s requests still waiting for a reply, each as the module takes
    it: its `id` and `request`."""
    now = time.time()
    found = []
    pattern = _path(session_id, "*")
    for path in sorted(pattern.parent.glob(pattern.name)):
        asked = COMPLETION.read(path)
        if asked is not None and "reply" not in asked and asked["deadline"] > now:
            found.append(
                {"id": path.name.rsplit(".", 1)[1], "request": asked["request"]}
            )
    return found


def cmd_reply(session_id: str, payload: dict) -> None:
    """Write the module's reply to the request `payload["completion"]` names, as
    `leaf hook --fork` hands it over, unless its page server has stopped waiting."""
    path = _path(session_id, payload["completion"])
    reply = {
        name: value
        for name, value in payload.items()
        if name in {"text", "failed", "status", "error", "usage", "elapsed_ms"}
    }
    with flocked(_lock_path(session_id)):
        asked = COMPLETION.read(path)
        if asked is not None and "reply" not in asked:
            COMPLETION.write(path, {**asked, "reply": reply})
