"""The agent-host hooks Leaf registers, and the part of each that reads no page.

Every hook marks that it ran for its session (`leases.mark_hooks`), and a wait
only wakes a session so marked (`Harness.hooks_carry`): a session launched
without these hooks still gets the envelope printed, rather than waking to an
empty turn. The tool hook names a background `leaf wait` the command it follows
started, and SessionEnd releases the session's claims.

The prompt and Stop hooks read the session's pages, and reading one parses its
markup and its registry. A host runs these hooks at every turn of every session
the plugin is installed in, and most of those sessions hold no page, so this
module imports none of that reading, nor the servers: a session holding no page
is answered here, and one holding a page reaches `hook_carrier`, the prompt and
Stop hooks as its carrier, through the one import below."""

import json

from .files import next_reading
from .leases import mark_hooks, name_wait_start
from .service import owned_pages
from .state_paths import end_session

# How long a tool hook looks for a wait to start. The hook fires as soon as the host
# has spawned a background command, and a `leaf wait` takes its lease about 0.3s
# later warm, 2.5s after a plugin update leaves uv to sync first. While no wait runs,
# nothing but the clock says a command will start none, so one that starts none
# holds its result this long.
WAIT_START_S = 3

# Claude Code's session list reads a session's closing line, and a background wait
# holds the session at Working whatever that line says
# (`references/host-claude-code.md`, "Session list").
WAIT_STARTED = (
    "`leaf wait` is now watching your pages in the background. Claude Code's "
    "session list shows this session as Working while it runs, and groups it by "
    "the closing line of your reply. If this turn leaves anything only the user "
    "can give (an answer on the page, or a decision about other work), end your "
    "closing reply with a line `needs input: <what you want back>`. Only when "
    "nothing waits on the user or on work you still have running (this watcher "
    "aside), end it instead with a line `result: <what you delivered>`, which "
    "files the session under Completed. Keep either line to 200 characters or "
    "fewer, on its own line, not in a code block."
)


def announce_wait(session_id: str) -> bool:
    """Whether a wait has started for this session that no tool hook has named,
    naming it if so.

    The wait's own mark says so (`leases.name_wait_start`), not the command the
    hook follows. A wait already named settles it at once: a second wait is
    refused while one holds the lease. Otherwise the hook looks for
    `WAIT_START_S`, since the command it follows may be one still starting."""
    return (
        next_reading(lambda: name_wait_start(session_id), False, timeout=WAIT_START_S)
        is True
    )


def cmd_hook(payload: dict) -> None:
    event, sid = payload.get("hook_event_name"), payload.get("session_id") or ""
    if sid:
        # Evidence that this host runs Leaf's hooks for the session, which is what
        # lets its `leaf wait` only wake it (`Harness.hooks_carry`).
        mark_hooks(sid)
    if event == "PostToolUse":
        # A foreground wait has returned before the hook runs, so only a
        # background command can leave one running past the turn.
        if payload["tool_input"].get("run_in_background") and announce_wait(sid):
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PostToolUse",
                            "additionalContext": WAIT_STARTED,
                        }
                    }
                )
            )
        return
    if event == "SessionEnd":
        end_session(sid)
        return
    # A session holding no page has no turn to open or close on one, no input to
    # carry, and nothing owed, so its prompt and Stop hooks end here.
    if not owned_pages(sid):
        return
    # The one place a hook imports page reading (see the module docstring).
    from .hook_carrier import carry_turn

    carry_turn(event, sid, payload)
