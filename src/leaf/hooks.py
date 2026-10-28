"""The agent-harness hooks Leaf registers, and the part of each that reads no page.

Every hook marks that it ran for its session (`leases.mark_hooks`), evidence
that its harness supports hook delivery (`Harness.hooks_carry`) and, by when it last
ran, that an open turn still works (`activity.claimant_turn`). An explicit
`leaf wait` always prints the envelope; it does not depend on another hook
running after it. SessionEnd retires the harness instance without reading pages;
persisted desktop chats retain their generation across instance unloads.

Codex's startup hook captures its validated native source even when the first
input is a dispatched tool message rather than a user prompt. Its synchronous
prompt hook records the provider turn even before the session claims a page. Its native transcript also records turns resumed without input,
which run no prompt hook. Hooks reconcile that provider evidence before checking
their turn identity (`Harness.reconcile_turn`), then offer input between steps
or before Stop (`Harness.offer_at_step`) and leave receipt to the agent's explicit
confirmation of complete input.
An accepted TurnStart opens the same lifecycle as UserPromptSubmit without
reading or receiving page input. Pi calls it after its SDK reserves the run;
accepted message finalization or a live turn boundary confirms the receipt.

The payload names the session and turn: hook subprocesses need not have the tool
process's environment. Stop or Interrupt closes that observed turn, including a
turn not yet claimed by any page; a newer prompt protects its own epoch. A payload
that names no turn can state when the turn ended (`ended_at`, in POSIX seconds),
as the Interrupt from Pi's extension does, and then leaves a turn opened or
renewed since open.

Most sessions with the plugin installed never claim a page, so in a session
holding no claim the launcher answers each hook registered `--if-claimed`
without starting uv (`bin/leaf`): Codex's tool hook, and every Claude Code hook
but PreToolUse. Codex's other hooks record the provider turn a later claim rests
on, so they always run. Claude Code's PreToolUse runs before each `leaf`
command, and in such a session opens the turn the skipped prompt hook would have,
so a claim that command makes joins it; of its runs for one tool call, one per
registration the command matches, only the first does its work
(`leases.first_hook_for_tool`). Hooks
that do run with no retained claim avoid page reading, and import the harness
declarations only once the payload names a session. Page-owning prompt and Stop
hooks reach `hook_transport`; Codex's tool and Stop hooks reach its delivery
records in `codex`. Claude Code's background Stop hook and Pi's extension watch
between turns (`cmd_watch`), and Leaf's Claude Code hooks module follows the
session's pages (`cmd_pages`) to draw them beside the prompt. `leaf hook`
(`cli.hook`) dispatches here.

Claude Code's PostToolBatch carries pending input before the next model call,
after successful or failed tools, using the same envelope and receipt as its
prompt hook. A boundary with nothing pending adds no response-debt reminders.
Claude Code may still drop what a hook hands over, so each of its hooks first
records the receipt of what its transcript shows entered the model's context
(`delivery.confirm_entered`). Its hooks name the turn by `prompt_id`
(`ClaudeCodeHarness.hook_payload`).

Session-start and prompt hooks also inspect retained claims for disconnected pages
(`reconnect`), including inactive ownership. That notice does not reclaim a
page or reopen a turn at SessionStart, and it persists across session generations.
A SessionStart after a compaction also has an agent holding a page read the leaf
skill again (`reload_skill`).

Each harness's registrations name it (`--harness`) and its payload names the
session; `harness.hook_harness` says why neither comes from the environment. A
developer-selected session runtime (`session_runtime`) owns the entire hook;
`main` execs it before this module publishes lifecycle or reads pages."""

import json
import time

from .leases import first_hook_for_tool, mark_hooks
from .refusals import Refused
from .service import claim_records, owned_pages
from .state import (
    advance_turn,
    close_session_turn,
    flocked,
    held_claims,
    prompt_turn,
    session_lock_path,
    session_record,
)


def cmd_hook(harness: str, payload: dict) -> None:
    """Answer one hook of `harness`, the name its registration passes."""
    started = time.monotonic()
    event, sid = payload.get("hook_event_name"), payload.get("session_id") or ""
    if not sid:
        return
    # Capability evidence for hook transport, and evidence that an open turn still
    # works, a worker's steps included. An explicit wait carries its own input even
    # if later hooks fail.
    mark_hooks(sid)
    if (
        harness == "claude-code"
        and event == "PostToolBatch"
        and payload.get("agent_id")
    ):
        # Claude Code's tool hooks name the parent session even inside a worker;
        # agent_id is its native subagent/teammate identity. Only the parent
        # receives the input its session claimed.
        return
    if event == "PreToolUse" and not first_hook_for_tool(
        sid, payload.get("tool_use_id")
    ):
        return
    from .harness import hook_harness

    hooked = hook_harness(harness, sid)
    payload = hooked.hook_payload(payload)
    turn_id = payload.get("turn_id")
    if event == "PreToolUse":
        # Hooks run outside the harness's sandbox and shell commands inside it.
        # Claude Code's registration runs this only before a command naming
        # `leaf`, so a session that never runs one opens no road out.
        hooked.escape_sandbox()
        if not held_claims(sid):
            # The launcher skipped this turn's prompt hook (`bin/leaf`),
            # so the turn a claim joins opens here, before the command.
            prompt_turn(sid, turn_id)
        elif not hooked.commits_hook_context:
            from .delivery import confirm_entered

            confirm_entered(hooked, payload)
        return
    if event in {"UserPromptSubmit", "TurnStart"}:
        expected = prompt_turn(sid, turn_id)
        if expected is None or event == "TurnStart":
            return
    else:
        expected = session_record(sid)
    expected = hooked.reconcile_turn(payload, expected)
    if event == "SessionStart":
        from .reconnect import notices

        context = notices(harness, sid, expected)
        if context is not None and payload.get("source") == "compact":
            context += reload_skill(sid)
        if context:
            print(
                json.dumps(hooked.hook_context(event, "\n\n".join(context))),
                flush=True,
            )
        return
    if turn_id and event != "UserPromptSubmit":
        # A first trusted step can identify an unknown session-scoped turn.
        # Once a prompt/provider named it, late callbacks cannot replace it; a
        # harness whose steps can start a turn opens it first (`reconcile_turn`).
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
    if (
        event in {"UserPromptSubmit", "PostToolBatch", "Stop"}
        and not hooked.commits_hook_context
    ):
        from .delivery import confirm_entered

        confirm_entered(hooked, payload)
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


def reload_skill(session_id: str) -> list[str]:
    """What a compaction tells an agent holding pages: to read the leaf skill again,
    which the compaction may have dropped from its context.

    On 2026-10-25 five sessions left questions for the user only in their replies,
    so On me read empty and told the user nothing waited on them. Each had read the
    skill hours or days before, four of them before compacting, while their
    harness's own instructions for asking the user stayed in context. Restating one
    rule on every prompt weighed on every turn and covered only that rule; the
    skill is where every rule a page-holding agent follows lives."""
    from .schema import SKILL_FILE

    pages = owned_pages(session_id)
    if not pages:
        return []
    return [
        (
            f"This session holds the Leaf page {', '.join(map(str, pages))}. A "
            f"compaction may have dropped the leaf skill; read {SKILL_FILE} again "
            "before you next reply or run a leaf command."
        )
    ]


def cmd_watch(harness: str, payload: dict) -> str | None:
    """The watch `harness`'s Stop hook or extension starts as a turn ends, or Claude
    Code's prompt hook as a turn starts, watching the session's pages until input,
    and what it wakes the session with, or None where it ends without waking it
    (`session.watch_between_turns`). A prompt's watch takes the turn it starts with
    as a later one: it waits while that turn runs and wakes only once Escape ends it
    with no Stop hook, since a Stop starts the watch that supersedes it.

    It watches only while the session holds a page, and only where its harness
    watches between turns. Pi's extension starts one with an Interrupt payload
    when the user stops a run: it answers the Interrupt hook first, closing the
    turn, and then watches from an interrupted ending. So that ending is one call,
    and the turn closes only once the watch from before has exited, which would
    read the closed turn as the Stop hook's ending."""
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

    return watch_between_turns(
        watching,
        interrupted=interrupted,
        at_prompt=payload.get("hook_event_name") == "UserPromptSubmit",
    )


# What `cmd_pages` prints of each page, so a change to anything else stays quiet.
SHOWN_FIELDS = ("page_key", "url", "title", "on_user", "threads", "activity")


def cmd_pages(payload: dict) -> None:
    """Print the live pages the payload's session holds, as one JSON list
    (`presence.live_leaves`), then again each time that list changes, until the
    session holds no page. Leaf's Claude Code hooks module draws it beside the
    prompt.

    Rows and the session's claim locators wake the reading. A server that dies
    leaves its row until a reader finds its lease unheld, so the list is read
    again every presence interval too."""
    sid = payload.get("session_id") or ""
    if not owned_pages(sid):
        print("[]", flush=True)
        return

    from .file_changes import FileChanges
    from .presence import PRESENCE_CACHE_S, live_leaves
    from .state import session_claims, state_home

    rows, claims = state_home().resolve() / "rows", session_claims(sid)
    # A root above rows/ would hear its creation, not the rows written into it.
    rows.mkdir(exist_ok=True)
    roots = {rows: False, claims: False}
    changes = FileChanges(
        roots,
        lambda changed: changed.parent in (rows, claims) or changed in (rows, claims),
    )
    shown = None
    try:
        while True:
            mark = changes.mark()
            held = {page.resolve() for page in owned_pages(sid)}
            listed = json.dumps(
                [
                    {field: leaf[field] for field in SHOWN_FIELDS}
                    for _page, leaf in (live_leaves(held) if held else [])
                ]
            )
            if listed != shown:
                print(listed, flush=True)
                shown = listed
            if not held:
                return
            changes.wait(mark, PRESENCE_CACHE_S)
    finally:
        changes.close()


def main(harness: str, *, watch: bool = False, pages: bool = False) -> None:
    """Read one harness payload and dispatch it.

    The Click hook command is the caller.
    A watch owns leases, so it releases them when the harness terminates it.
    """
    import os
    import sys
    import tempfile

    from .session_runtime import own_launcher, selected_launcher

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as error:
        raise Refused(
            f"hook expects the harness's JSON payload on stdin ({error.msg})"
        ) from error
    launcher = selected_launcher(payload.get("session_id") or "")
    if launcher is not None and launcher != own_launcher():
        # Delegate the whole hook before publishing lifecycle or pickup. Keeping
        # the stdin as a file avoids a pipe-size limit on large tool payloads;
        # exec retains cancellation and the watch's exact lifetime.
        with tempfile.TemporaryFile() as incoming:
            incoming.write(json.dumps(payload).encode())
            incoming.seek(0)
            os.dup2(incoming.fileno(), 0)
        environment = dict(os.environ)
        environment.pop("LEAF_HOST_LAUNCHER", None)
        os.execve(
            launcher,
            [
                str(launcher),
                "hook",
                "--harness",
                harness,
                *(["--watch"] if watch else []),
                *(["--pages"] if pages else []),
            ],
            environment,
        )
    if pages:
        cmd_pages(payload)
        return
    if watch:
        from .leases import release_on_termination

        release_on_termination()
        if woke := cmd_watch(harness, payload):
            print(woke, flush=True)
        return
    cmd_hook(harness, payload)
