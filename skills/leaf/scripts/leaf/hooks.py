"""The agent-host hooks Leaf registers, and the part of each that reads no page.

Every hook marks that it ran for its session (`leases.mark_hooks`), and a wait
only wakes a session so marked (`Harness.hooks_carry`): a session launched
without these hooks still gets the envelope printed, rather than waking to an
empty turn. SessionEnd releases the session's claims.

The prompt and Stop hooks read the session's pages, and reading one parses its
markup and its registry. A host runs these hooks at every turn of every session
the plugin is installed in, and most of those sessions hold no page, so this
module imports none of that reading, nor the servers: a session holding no page
is answered here, and one holding a page reaches `hook_carrier`, the prompt and
Stop hooks as its carrier, or `session`, the watch a second Stop hook runs
between turns (`cmd_watch`), through the imports below. The host runs this module
directly under uv; `main` also supplies the CLI hook entry, so dispatch has one
owner."""

from .leases import mark_hooks
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
    # A session holding no page has no turn to open or close on one, no input to
    # carry, and nothing owed, so its prompt and Stop hooks end here.
    if not owned_pages(sid):
        return
    # The one place a hook imports page reading (see the module docstring).
    from .hook_carrier import carry_turn

    carry_turn(event, sid, payload)


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

    Both the registered hook (`python -m leaf.hooks`) and `leaf hook` enter here.
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


if __name__ == "__main__":
    import sys

    main(watch="--watch" in sys.argv[1:])
