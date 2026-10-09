"""The agent-harness hooks Leaf registers, and the part of each that reads no page.

Every hook marks that it ran for its session (`leases.mark_hooks`), and a wait
only wakes a session so marked (`Harness.hooks_carry`): a session launched
without these hooks still gets the envelope printed, rather than waking to an
empty turn. SessionEnd retires the harness instance without reading pages;
activity-backed desktop chats retain their generation across instance unloads.

Codex's synchronous prompt hook records the provider turn even before the session
claims a page. Its native transcript also records turns resumed without input,
which run no prompt hook. Hooks reconcile that provider evidence before checking
their turn identity, then offer a pointer between steps or before Stop and leave
receipt to the agent's actual delivery read.
An accepted TurnStart opens the same lifecycle as UserPromptSubmit without
reading or receiving page input. Pi calls it after its SDK reserves the run;
accepted message finalization or a live turn boundary confirms the receipt.

The payload names the session and turn: hook subprocesses need not have the tool
process's environment. Stop or Interrupt closes that observed turn, including a
turn not yet claimed by any page; a newer prompt protects its own epoch. A payload
that names no turn can state when the turn ended (`ended_at`, in POSIX seconds),
as the Interrupt from Pi's extension or Leaf's Claude Code hooks module does, and
then leaves a turn opened or renewed since open.

Hooks with no retained claim avoid page reading. Page-owning prompt and Stop hooks
reach `hook_transport`; Codex's tool and Stop hooks reach its delivery records
in `codex`; a second Claude Code Stop hook watches between turns (`cmd_watch`). The
application entry routes `leaf hook` here before loading the CLI.

Resume and prompt hooks also inspect retained claims for disconnected pages
(`reconnect`), including inactive ownership. That notice does not reclaim a
page or reopen a turn at SessionStart, and it persists across session generations.

Each harness's registrations name it (`--harness`) and its payload names the
session; `harness.hook_harness` says why neither comes from the environment."""

import time

from .leases import mark_hooks, mark_step_hook
from .service import claim_records, owned_pages
from .state import (
    advance_turn,
    close_session_turn,
    end_harness_instance,
    flocked,
    prompt_turn,
    session_lock_path,
    session_record,
)


def cmd_hook(harness: str, payload: dict) -> None:
    """Answer one hook of `harness`, the name its registration passes."""
    started = time.monotonic()
    event, sid = payload.get("hook_event_name"), payload.get("session_id") or ""
    if sid:
        # Evidence that this harness runs Leaf's hooks for the session, which is what
        # lets its `leaf wait` only wake it (`Harness.hooks_carry`).
        mark_hooks(sid)
    if event == "SessionEnd":
        end_harness_instance(sid)
        return
    if not sid:
        return
    expected = session_record(sid)
    if harness == "codex" and expected is not None and event != "UserPromptSubmit":
        from .codex_state import sync_transcript_turn

        expected = sync_transcript_turn(sid, payload.get("transcript_path"))
    if event == "SessionStart":
        if payload.get("source") == "resume":
            from .harness import HOOK_HARNESSES
            from .reconnect import publishing_notices

            with publishing_notices(harness, sid, expected) as context:
                if context:
                    import json

                    print(
                        json.dumps(
                            HOOK_HARNESSES[harness].hook_context(
                                event, "\n\n".join(context)
                            )
                        ),
                        flush=True,
                    )
        return
    turn_id = payload.get("turn_id")
    if event in {"UserPromptSubmit", "TurnStart"}:
        expected = prompt_turn(sid, turn_id)
        if expected is None or event == "TurnStart":
            return
        if harness == "codex":
            from .codex_state import sync_transcript_turn

            expected = sync_transcript_turn(sid, payload.get("transcript_path"))
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
        # An extension that names no turn states when it saw the ending, since the
        # watch that answers this runs after it, when a prompt may already have
        # renewed the turn (`cmd_watch`).
        close_session_turn(
            sid, turn_id, expected=expected, ended_at=payload.get("ended_at")
        )
        return
    if harness == "codex" and event in {"PostToolUse", "Stop"} and turn_id:
        # Both boundaries offer through Codex's one transport reservation.
        # Empty-input resume can reach Stop without executing another tool.
        if event == "PostToolUse":
            mark_step_hook(sid)
        if owned_pages(sid):
            from .codex import offer_hook_delivery
            from .harness import HOOK_HARNESSES

            if prompt := offer_hook_delivery(sid, turn_id):
                import json

                print(json.dumps(HOOK_HARNESSES[harness].hook_context(event, prompt)))
                return
            # Offering renews the observed turn even on a quiet page. Carry the
            # resulting revision into Stop's independent response-debt check.
            expected = session_record(sid)
    if event == "PostToolUse":
        return
    # Retained claims may need reconnecting after active ownership expired.
    retained = event == "UserPromptSubmit" and any(
        claim["harness"] == harness for claim in claim_records(sid)
    )
    if not retained and not owned_pages(sid):
        if event == "Stop":
            close_session_turn(sid, turn_id, expected=expected)
        return
    # Prompt and Stop debt and delivery reading belongs to the hook transport.
    from .harness import HOOK_HARNESSES
    from .hook_transport import carry_turn

    ended = carry_turn(
        HOOK_HARNESSES[harness],
        event,
        sid,
        payload,
        expected,
        started=started,
        reconnect_harness=harness if event == "UserPromptSubmit" else None,
    )
    if ended:
        close_session_turn(sid, turn_id, expected=expected)


def cmd_watch(harness: str, payload: dict) -> str | None:
    """The Stop hook `harness` runs in the background as a turn ends, watching the
    session's pages until input, and what it wakes the session with, or None
    where it ends without waking it (`session.watch_between_turns`).

    It watches only while the session holds a page, and only where its harness
    watches between turns. Pi's extension and Leaf's Claude Code hooks module start
    one with an Interrupt payload when the user stops a run: it answers the
    Interrupt hook first, closing the turn, and then watches from an interrupted
    ending. So that ending is one call, and the turn closes only once
    the watch from before has exited, which would read the closed turn as the
    Stop hook's ending."""
    interrupted = payload.get("hook_event_name") == "Interrupt"
    if interrupted:
        cmd_hook(harness, payload)
    sid = payload.get("session_id") or ""
    if not owned_pages(sid):
        return None
    from .harness import hook_harness

    watching = hook_harness(harness, sid)
    if not watching.watches_between_turns():
        return None
    from .session import watch_between_turns

    return watch_between_turns(watching, interrupted=interrupted)


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
