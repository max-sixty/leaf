"""The agent-host hooks Leaf registers, and the part of each that reads no page.

Every hook marks that it ran for its session (`leases.mark_hooks`), and a wait
only wakes a session so marked (`Harness.hooks_carry`): a session launched
without these hooks still gets the envelope printed, rather than waking to an
empty turn. SessionEnd releases the session's claims.

Codex's synchronous prompt hook records the provider turn even before the session
claims a page. Its async tool hook can then bind a page acquired mid-turn, offer a
pointer between steps, and leave receipt to the agent's actual delivery read.
The payload names the session and turn: hook subprocesses need not have the tool
process's environment. Stop or Interrupt closes that observed turn, including a
page no tool hook has yet bound; a newer prompt protects its own claims.

Hooks with no owned page avoid page reading. Page-owning prompt and Stop hooks
reach `hook_carrier`; Codex's tool hook reaches the delivery records in `codex`;
and a second Claude Code Stop hook watches between turns (`cmd_watch`). The
application entry routes `leaf hook` here before loading the CLI."""

from .leases import mark_hooks, mark_step_hook
from .service import owned_pages
from .state_paths import end_session


def cmd_hook(payload: dict) -> None:
    event, sid = payload.get("hook_event_name"), payload.get("session_id") or ""
    if sid:
        # Evidence that this host runs Leaf's hooks for the session, which is what
        # lets its `leaf wait` only wake it (`Harness.hooks_carry`).
        mark_hooks(sid)
    if event == "SessionEnd":
        end_session(sid)
        return
    turn_id = payload.get("turn_id")
    if event == "UserPromptSubmit" and turn_id:
        from .codex_state import start_hook_turn

        start_hook_turn(sid, turn_id)
    if event == "Interrupt":
        if turn_id:
            from .codex_state import end_hook_turn

            end_hook_turn(sid, turn_id)
        return
    if event == "PostToolUse":
        # This registration is gated on Codex in hooks.json. Its output can
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
        if event == "Stop" and turn_id:
            from .codex_state import end_hook_turn

            end_hook_turn(sid, turn_id)
        return
    # Prompt and Stop debt and delivery reading belongs to their carrier.
    from .hook_carrier import carry_turn

    ended = carry_turn(event, sid, payload)
    if ended and turn_id:
        from .codex_state import end_hook_turn

        end_hook_turn(sid, turn_id)


def cmd_watch(payload: dict) -> str | None:
    """The Stop hook a host runs in the background as a turn ends, watching the
    session's pages until input, and what it wakes the session with, or None
    where it ends without waking it (`session.watch_between_turns`).

    It watches only where this process is the session the hook names and its
    harness watches between turns, and only while the session holds a page."""
    sid = payload.get("session_id") or ""
    if not owned_pages(sid):
        return None
    from .host import session_harness

    harness = session_harness()
    if harness is None or harness.session != sid or not harness.watches_between_turns():
        return None
    from .session import watch_between_turns

    return watch_between_turns(harness)


def main(*, watch: bool = False) -> None:
    """Read one host payload and dispatch it, without importing the CLI.

    Both the application entry and the Click command enter here.
    A watch owns leases, so it releases them when the host terminates it.
    """
    import json
    import sys

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as error:
        sys.exit(f"hook expects the host's JSON payload on stdin ({error.msg})")
    if watch:
        from .leases import release_on_termination

        release_on_termination()
        if woke := cmd_watch(payload):
            print(woke, flush=True)
        return
    cmd_hook(payload)
