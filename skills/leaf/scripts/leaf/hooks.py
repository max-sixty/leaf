"""The agent-harness hooks Leaf registers, and the part of each that reads no page.

Every hook marks that it ran for its session (`leases.mark_hooks`), and a wait
only wakes a session so marked (`Harness.hooks_carry`): a session launched
without these hooks still gets the envelope printed, rather than waking to an
empty turn. SessionEnd invalidates the session generation without reading pages.

Codex's synchronous prompt hook records the provider turn even before the session
claims a page. Its async tool hook can identify an unknown session turn once, offer a pointer
between steps, and leave receipt to the agent's actual delivery read.
The payload names the session and turn: hook subprocesses need not have the tool
process's environment. Stop or Interrupt closes that observed turn, including a
turn not yet claimed by any page; a newer prompt protects its own epoch.

Hooks with no owned page avoid page reading. Page-owning prompt and Stop hooks
reach `hook_carrier`; Codex's tool hook reaches the delivery records in `codex`;
and a second Claude Code Stop hook watches between turns (`cmd_watch`). The
application entry routes `leaf hook` here before loading the CLI.

Each harness's registrations name it (`--harness`) and its payload names the
session; `harness.hook_harness` says why neither comes from the environment."""

from .leases import mark_hooks, mark_step_hook
from .service import owned_pages
from .state import (
    advance_turn,
    close_session_turn,
    end_session,
    flocked,
    prompt_turn,
    session_lock_path,
    session_record,
)


def cmd_hook(harness: str, payload: dict) -> None:
    """Answer one hook of `harness`, the name its registration passes."""
    event, sid = payload.get("hook_event_name"), payload.get("session_id") or ""
    if sid:
        # Evidence that this harness runs Leaf's hooks for the session, which is what
        # lets its `leaf wait` only wake it (`Harness.hooks_carry`).
        mark_hooks(sid)
    if event == "SessionEnd":
        end_session(sid)
        return
    if not sid:
        return
    expected = session_record(sid)
    turn_id = payload.get("turn_id")
    if event == "UserPromptSubmit":
        expected = prompt_turn(sid, turn_id)
        if expected is None:
            return
    elif turn_id:
        # A first trusted step can identify an unknown session-scoped turn.
        # Once a prompt/provider named it, late callbacks cannot replace it.
        with flocked(session_lock_path(sid)):
            record = session_record(sid)
            if (
                not record
                or record["ended"] is not None
                or record["turn_closed"] is not None
            ):
                return
            if record["turn"] != turn_id:
                if record["provider"] or event != "PostToolUse":
                    return
                expected = advance_turn(sid, turn_id, running=True)
            else:
                expected = record
    if event == "Interrupt":
        close_session_turn(sid, turn_id, expected=expected)
        return
    if event == "PostToolUse":
        # Only Codex registers this hook (`hooks/codex.json`). Its output can
        # enter an active turn, but it cannot wake an idle one.
        if not turn_id:
            return
        mark_step_hook(sid)
        if not owned_pages(sid):
            return
        from .codex import offer_hook_delivery

        prompt = offer_hook_delivery(sid, turn_id)
        if prompt:
            import json

            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PostToolUse",
                            "additionalContext": prompt,
                        }
                    }
                )
            )
        return
    # A session holding no page has no turn to open or close on one, no input to
    # carry, and nothing owed, so its prompt and Stop hooks end here.
    if not owned_pages(sid):
        if event == "Stop":
            close_session_turn(sid, turn_id, expected=expected)
        return
    # Prompt and Stop debt and delivery reading belongs to their carrier.
    from .harness import HOOK_HARNESSES
    from .hook_carrier import carry_turn

    ended = carry_turn(HOOK_HARNESSES[harness], event, sid, payload, expected)
    if ended:
        close_session_turn(sid, turn_id, expected=expected)


def cmd_watch(harness: str, payload: dict) -> str | None:
    """The Stop hook `harness` runs in the background as a turn ends, watching the
    session's pages until input, and what it wakes the session with, or None
    where it ends without waking it (`session.watch_between_turns`).

    It watches only while the session holds a page, and only where its harness
    watches between turns. A watch started with an Interrupt payload, as Pi's
    extension starts one when an Escape settles a run, is a watch at an
    interrupted ending."""
    sid = payload.get("session_id") or ""
    if not owned_pages(sid):
        return None
    from .harness import hook_harness

    watching = hook_harness(harness, sid)
    if not watching.watches_between_turns():
        return None
    from .session import watch_between_turns

    return watch_between_turns(
        watching, interrupted=payload.get("hook_event_name") == "Interrupt"
    )


def main(harness: str, *, watch: bool = False) -> None:
    """Read one harness payload and dispatch it, without importing the CLI.

    Both the application entry and the Click command enter here.
    A watch owns leases, so it releases them when the harness terminates it.
    """
    import json
    import sys

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as error:
        sys.exit(f"hook expects the harness's JSON payload on stdin ({error.msg})")
    if watch:
        from .leases import release_on_termination

        release_on_termination()
        if woke := cmd_watch(harness, payload):
            print(woke, flush=True)
        return
    cmd_hook(harness, payload)
