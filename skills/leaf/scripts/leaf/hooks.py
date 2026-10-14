"""The agent-harness hooks Leaf registers, and the part of each that reads no page.

Every hook marks that it ran for its session (`leases.mark_hooks`), evidence
that its harness supports hook delivery (`Harness.hooks_carry`). An explicit
`leaf wait` always prints the envelope; it does not depend on another hook
running after it. SessionEnd retires the harness instance without reading pages;
persisted desktop chats retain their generation across instance unloads.

Codex's synchronous prompt hook records the provider turn even before the session
claims a page. Its native transcript also records turns resumed without input,
which run no prompt hook. Hooks reconcile that provider evidence before checking
their turn identity (`Harness.reconcile_turn`), then offer a pointer between steps
or before Stop (`Harness.offer_at_step`) and leave receipt to the agent's explicit
confirmation of complete input.
An accepted TurnStart opens the same lifecycle as UserPromptSubmit without
reading or receiving page input. Pi calls it after its SDK reserves the run;
accepted message finalization or a live turn boundary confirms the receipt.

The payload names the session and turn: hook subprocesses need not have the tool
process's environment. Stop or Interrupt closes that observed turn, including a
turn not yet claimed by any page; a newer prompt protects its own epoch. A payload
that names no turn can state when the turn ended (`ended_at`, in POSIX seconds),
as the Interrupt from Pi's extension or Leaf's Claude Code hooks module does, and
then leaves a turn opened or renewed since open.

Hooks with no retained claim avoid page reading, and import the harness
declarations only once the payload names a session. Page-owning prompt and Stop
hooks reach `hook_transport`; Codex's tool and Stop hooks reach its delivery
records in `codex`; a second Claude Code Stop hook watches between turns (`cmd_watch`). The
application entry routes `leaf hook` here before loading the CLI.

Resume and prompt hooks also inspect retained claims for disconnected pages
(`reconnect`), including inactive ownership. That notice does not reclaim a
page or reopen a turn at SessionStart, and it persists across session generations.

Each harness's registrations name it (`--harness`) and its payload names the
session; `harness.hook_harness` says why neither comes from the environment."""

import json
import os
import time

from .leases import mark_hooks
from .refusals import Refused
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
    if payload.get("leaf_watch") == "module":
        # Claude Code's hooks module marks the Stop payload it passes to the
        # registrations beneath it, and runs this hook itself, unmarked, to read
        # the delivery its output names (`hooks/claude-code.ts`).
        return
    event, sid = payload.get("hook_event_name"), payload.get("session_id") or ""
    if sid:
        # Capability evidence for hook transport and open-turn activity. An
        # explicit wait carries its own input even if later hooks fail.
        mark_hooks(sid)
    if event == "SessionEnd":
        end_harness_instance(sid)
        return
    if (
        harness == "claude-code"
        and event in {"SessionStart", "UserPromptSubmit"}
        and (pid := os.environ.get("CLAUDE_PID"))
    ):
        # Claude Code runs hooks outside its sandbox and shell commands inside it.
        from .bridge import ensure

        ensure(int(pid))
    if not sid:
        return
    from .harness import hook_harness

    hooked = hook_harness(harness, sid)
    turn_id = payload.get("turn_id")
    if event in {"UserPromptSubmit", "TurnStart"}:
        expected = prompt_turn(sid, turn_id)
        if expected is None or event == "TurnStart":
            return
    else:
        expected = session_record(sid)
    expected = hooked.reconcile_turn(payload, expected)
    if event == "SessionStart":
        if payload.get("source") == "resume":
            from .reconnect import publishing_notices

            with publishing_notices(harness, sid, expected) as context:
                if context:
                    print(
                        json.dumps(hooked.hook_context(event, "\n\n".join(context))),
                        flush=True,
                    )
        return
    if turn_id and event != "UserPromptSubmit":
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
    prompt, expected = hooked.offer_at_step(event, payload, expected)
    if prompt:
        print(json.dumps(hooked.hook_context(event, prompt)))
        return
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
    from .hook_transport import carry_turn

    ended = carry_turn(
        hooked,
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

    The application entry is the only caller.
    A watch owns leases, so it releases them when the harness terminates it.
    """
    import sys

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as error:
        raise Refused(
            f"hook expects the harness's JSON payload on stdin ({error.msg})"
        ) from error
    if watch:
        from .leases import release_on_termination

        release_on_termination()
        if woke := cmd_watch(harness, payload):
            print(woke, flush=True)
        return
    cmd_hook(harness, payload)
