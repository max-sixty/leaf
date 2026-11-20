"""The agent-harness hooks Leaf registers, and the part of each that reads no page.

Every hook marks that it ran for its session (`leases.mark_hooks`), evidence
that its harness supports hook delivery (`Harness.hooks_carry`). An explicit
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
registration the command matches, only the first does the turn's work
(`leases.first_hook_for_tool`). Hooks that do run with no retained claim avoid page
reading, and import the harness
declarations only once the payload names a session. Page-owning prompt and Stop
hooks reach `hook_transport`; Codex's tool and Stop hooks reach its delivery
records in `codex`. Claude Code's background Stop hook and Pi's extension watch
between turns (`cmd_watch`), and Leaf's Claude Code hooks module follows the
session's pages (`cmd_pages`) to draw them beside the prompt and to take the
instructions Leaf lists for it, and reports what each came to with `--fork`
(`carrier.step`, whose header holds that contract). The follower records the process
it runs in, so a Stop can tell the user where Claude Code didn't load the module
(`Harness.unloaded_module`). `leaf hook` (`cli.hook`) dispatches here.

Claude Code's PostToolBatch carries pending input before the next model call,
after successful or failed tools, using the same envelope and receipt as its
prompt hook. A boundary with nothing pending adds no response-debt reminders.
Claude Code may still drop what a hook hands over, so each of its hooks first
records the receipt of what its transcript shows entered the model's context
(`delivery.confirm_entered`). Its hooks name the turn by `prompt_id`
(`ClaudeCodeHarness.hook_payload`).

Before it opens its turn, the prompt hook serves again each page the session still
means to serve whose ownership or server is down, as a resumed session's are, and the
turn hears only of a page that did not start (`reconnect`). A SessionStart opens no
turn and claims nothing; after a compaction it tells an agent holding a page which of
Leaf's instructions the compaction removed (`reload_skill`). Claude Code runs Leaf's
start hook only then (`hooks.json`), since a resumed session's first reply waits for
its start hooks.

Each harness's registrations name it (`--harness`) and its payload names the
session; `harness.hook_harness` says why neither comes from the environment. A
developer-selected session runtime (`session_runtime`) owns the entire hook;
`main` execs it before this module publishes lifecycle or reads pages."""

import json
import os
import time

from .leases import first_hook_for_tool, mark_hooks
from .refusals import Refused
from .service import owned_pages
from .state import (
    advance_turn,
    close_session_turn,
    flocked,
    held_claims,
    prompt_turn,
    session_lock_path,
    session_record,
    still_named,
    turn_closed,
    worker_tool_batch,
)


def cmd_hook(harness: str, payload: dict) -> None:
    """Answer one hook of `harness`, the name its registration passes."""
    started = time.monotonic()
    event, sid = payload.get("hook_event_name"), payload.get("session_id") or ""
    if worker_tool_batch(harness, payload):
        return
    if sid:
        # Capability evidence for hook transport and open-turn activity. An
        # explicit wait carries its own input even if later hooks fail.
        mark_hooks(sid)
    if not sid:
        return
    assert isinstance(event, str)
    if event == "PostToolBatch" and (agent := payload.get("agent_id")):
        # A boundary of an agent running a turn of the session's own
        # (`state.worker_tool_batch`), which carries only that turn's input.
        from .harness import hook_harness
        from .hook_transport import carry_agent_turn

        carry_agent_turn(hook_harness(harness, sid), sid, agent, started=started)
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
        if not held_claims(sid):
            # The launcher skipped this turn's prompt hook (`bin/leaf`),
            # so the turn a claim joins opens here, before the command.
            prompt_turn(sid, turn_id)
            return
        if not hooked.commits_hook_context:
            from .delivery import confirm_entered

            confirm_entered(hooked, payload)
        return
    # What kept a page the session still means to serve from serving again.
    unserved = []
    if event in {"UserPromptSubmit", "TurnStart"}:
        if event == "UserPromptSubmit":
            # Before the turn opens, which then joins the generation a claim
            # starts where the session's last one ended or names another process.
            from .reconnect import serve_again

            unserved = serve_again(hooked, started)
        expected = prompt_turn(sid, turn_id)
        if expected is None or event == "TurnStart":
            return
    else:
        expected = session_record(sid)
    expected = hooked.reconcile_turn(payload, expected)
    if event == "SessionStart":
        if payload.get("source") == "compact" and (context := reload_skill(sid)):
            print(json.dumps(hooked.hook_context(event, context)), flush=True)
        return
    if turn_id and event != "UserPromptSubmit":
        # A first trusted step can identify an unknown session-scoped turn.
        # Once a prompt/provider named it, late callbacks cannot replace it; a
        # harness whose steps can start a turn opens it first (`reconcile_turn`).
        with flocked(session_lock_path(sid)):
            record = session_record(sid)
            if record is None or turn_closed(record):
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
    if not unserved and not owned_pages(sid):
        if event == "Stop":
            close_session_turn(sid, turn_id, expected=expected)
        return
    # Prompt and Stop debt and delivery reading belongs to the hook transport.
    from .hook_transport import carry_turn

    ended = carry_turn(
        hooked, event, sid, payload, expected, started=started, unserved=unserved
    )
    if ended:
        close_session_turn(sid, turn_id, expected=expected)
        # A Stop that ends the turn printed nothing, so its output can tell the user.
        if notice := hooked.unloaded_module():
            print(json.dumps(notice), flush=True)


def reload_skill(session_id: str) -> str | None:
    """What a compaction tells an agent holding pages: which of Leaf's instructions
    it removed, and to read the skill again and, through it, what the work in progress
    needs.

    Claude Code keeps a model-written summary, the last few files read and the skills
    loaded through its Skill tool. The rest of what the agent read is gone, which takes
    the skill when it was read as a file, the references, and every widget's
    instructions, which only `leaf page instructions` prints. The summary paraphrases
    those rules, as in "settle the lf-options with `settled`", and the page's own markup
    offers a pattern to copy, so an agent can believe it still has them. Sending the
    agent back to the skill alone isn't enough: agents reread the skill after most
    compactions, yet the `lf-options` written after a compaction often lack that
    widget's instructions in context, where those written before one have them. Restating a rule on every prompt weighs on every turn and covers only
    that rule, so this message names what the compaction removed and
    leaves the rules to the skill and its routes."""
    from .schema import SKILL_FILE

    pages = owned_pages(session_id)
    if not pages:
        return None
    return (
        f"This session holds the Leaf page {', '.join(map(str, pages))}. The "
        "compaction kept a summary of the Leaf instructions you had read, not their "
        "text: the leaf skill's references and the widget instructions `leaf page "
        "instructions` printed are gone, and the skill may be too. Before you next "
        f"reply or run a leaf command, read {SKILL_FILE} again, then the references "
        "and widget instructions your work in progress needs."
    )


def cmd_watch(harness: str, payload: dict) -> str | None:
    """The watch `harness`'s Stop hook or extension starts as a turn ends, or Claude
    Code's prompt hook as a turn starts, watching the session's pages until input,
    and what it wakes the session with, or None where it ends without waking it
    (`session.watch_between_turns`). A prompt's watch takes the turn it starts with
    as a later one: it waits while that turn runs and wakes only once Escape ends it
    with no Stop hook, since a Stop starts the watch that supersedes it, as does a
    prompt Escape dropped that Claude Code submits again.

    It watches only while the session holds a page, and only where its harness
    watches between turns. Pi's extension starts one with an Interrupt payload
    when the user stops a run: it answers the Interrupt hook first, closing the
    turn, and then watches from an interrupted ending. So that ending is one call,
    and the turn closes only once the watch from before has exited, which would
    read the closed turn as the Stop hook's ending."""
    if payload.get("hook_event_name") == "Interrupt":
        cmd_hook(harness, payload)
    sid = payload.get("session_id") or ""
    if not owned_pages(sid):
        return None
    from .harness import hook_harness

    watching = hook_harness(harness, sid)
    if not watching.watches_between_turns():
        return None
    from .session import watch_between_turns

    return watch_between_turns(watching, payload)


# What `cmd_pages` prints of each page, so a change to anything else stays quiet.
SHOWN_FIELDS = ("page_key", "url", "title", "on_user", "threads", "activity")


def cmd_pages(payload: dict) -> None:
    """Print the live pages the payload's session holds (`presence.live_leaves`)
    and the instructions Leaf has for its hooks module (`carrier.py`), as one JSON
    object, `{"pages": [...], "do": [...]}`, then again each time either changes,
    until the session holds no page. The module draws the pages beside the prompt
    and runs each instruction once: a completion each page server asks of the
    session (`completions.listed`) and each thread a line turn keeps back
    (`forks.listed`).

    Read the pages every presence interval: a dead server leaves its row behind, so
    native notifications cannot replace this timer. It waits on the session's
    requests (`completions.watch`), so it lists one as it is written.

    The follower is the session's forks lane (`forks.take_lane`) while it runs,
    and lists each thread a line turn holds (`forks.look`). Between presence reads
    it waits on each page's subscription
    (`file_changes.page_changes`) and on the lane's name, so it looks again as a
    message is admitted or as a later follower takes the lane. It reads a page again
    only once its reading has moved, since admission opens the line turn.

    It exits with `EX_TEMPFAIL`, without a last line, once the session's delivery
    runs another Leaf than its own (`_moved_on`), and the module starts it again,
    under that Leaf. A follower runs as long as its session, while the session's
    hooks hand themselves at each call to the Leaf delivering for it: a newer copy
    Claude Code installed, a checkout the session selected, or the same checkout
    moved past a protocol bump. That newer Leaf reads an older follower's lane as no
    one's: its line fork's step refuses the messages that follower keeps back, so
    each would wait out a line turn's grace (`activity.STARTING_GRACE`) with no
    line.

    The module that reads the list stays the one the session loaded until
    `/reload-plugins`, so a follower under a newer Leaf may print it to an older
    module, which runs its instructions as any (`carrier.py`).

    The follower notes once in each page it holds that it runs
    (`interaction_log.record_follower`), so a message admission found with no lane
    (`forks.kept_from_main_at_admission`) says whether no follower had run or the
    one that held the lane had gone (`leaf-dev logs timeline`)."""
    sid = payload.get("session_id") or ""
    from .harness import ClaudeCodeHarness
    from .leases import mark_module

    # Only Leaf's Claude Code module starts a follower, so one running shows the
    # module loaded in this process (`ClaudeCodeHarness.unloaded_module`).
    if (pid := ClaudeCodeHarness.process_pid()) is not None:
        mark_module(sid, pid)
    if not owned_pages(sid):
        print(json.dumps({"pages": [], "do": []}), flush=True)
        return

    from .completions import listed as completions_listed
    from .completions import watch
    from .file_changes import FileChanges, page_changes, wait
    from .forks import lane_path, take_lane
    from .interaction_log import record_follower
    from .leases import release_lease
    from .page_memory import memory_of
    from .presence import PRESENCE_CACHE_S, live_leaves
    from .session_runtime import replaced

    queued = watch(sid)
    # Whether this follower still holds the lane, which a later one takes.
    forking = True
    # The pages this follower has made its note in (`record_follower`), each once.
    noted: set = set()
    lane = take_lane(sid)
    # Resolved, as notifications name it.
    named = lane_path(sid).resolve()
    renamed = FileChanges({named.parent: False}, lambda path: path == named)
    looked: dict = {}
    shown = None
    # A copy already marked as this follower starts is one its launcher ran anyway,
    # until Claude Code's sweep clears that mark (`_moved_on`).
    marked_at_start = replaced()
    try:
        while True:
            marked = replaced()
            marked_at_start = marked_at_start and marked
            if _moved_on(sid, marked and not marked_at_start):
                # EX_TEMPFAIL: the module starts it again, under that Leaf.
                raise SystemExit(os.EX_TEMPFAIL)
            held = {page.resolve() for page in owned_pages(sid)}
            record_follower(sorted(held - noted), sid)
            noted |= held
            leaves = live_leaves(held) if held else []
            # Each page's subscription lives in its memory, which the process
            # keeps only for its most recent pages unless held.
            _memories = [memory_of(page) for page in held] if forking else []
            presence_due = time.monotonic() + PRESENCE_CACHE_S
            while True:
                # Taken before the pass reads, so a message admitted or a request
                # asked during it ends the wait below.
                marks = [
                    (queued, queued.mark()),
                    *(
                        [*map(page_changes, held), (renamed, renamed.mark())]
                        if forking
                        else []
                    ),
                ]
                if forking and not still_named(lane.fileno(), named):
                    # A later follower took the lane, and lists what this one would.
                    forking = False
                    renamed.close()
                kept = (
                    {page: _kept_back(sid, page, looked) for page in held}
                    if forking
                    else {}
                )
                listed = json.dumps(
                    {
                        "pages": [
                            {field: leaf[field] for field in SHOWN_FIELDS}
                            for _, leaf in leaves
                        ],
                        "do": [
                            *completions_listed(sid),
                            *(item for items in kept.values() for item in items),
                        ],
                    }
                )
                if listed != shown:
                    print(listed, flush=True)
                    shown = listed
                if not held:
                    return
                wait(marks, max(0.0, presence_due - time.monotonic()))
                if time.monotonic() >= presence_due:
                    break
    finally:
        queued.close()
        if forking:
            release_lease(lane)
            renamed.close()


def _moved_on(sid: str, replaced: bool) -> bool:
    """Whether the session's delivery now runs another Leaf than this process: a
    copy Claude Code installed in place of this one, which this copy's launcher
    runs instead (`replaced`), a checkout selected since the follower started,
    which its hooks hand themselves to as `main` does
    (`session_runtime.delivering_launcher`), or its own install moved under it to
    another page protocol (`registry.kernel.installed_protocol`), or removed, as a
    selected checkout's is when its worktree goes: the module starts the follower
    again from its own launcher, which hands it to the Leaf delivering now. A registry
    read mid-write reads as unmoved until it settles.

    `replaced` counts a mark Claude Code made on this copy (`session_runtime.replaced`)
    only once the follower has seen the copy unmarked: a copy marked as the follower
    starts is one its launcher ran all the same, as where Claude Code's record still
    names it, and ending there would have the module start the follower in it again
    and again. The sweep that clears such a mark lets a later one count."""
    from .registry.kernel import installed_protocol, kernel_protocol
    from .session_runtime import delivering_launcher, own_launcher

    own = own_launcher()
    if replaced or not os.access(own, os.X_OK):
        return True
    try:
        return (
            delivering_launcher(sid) != own or installed_protocol() != kernel_protocol()
        )
    except (OSError, ValueError, KeyError):
        return False


def _kept_back(sid: str, page_dir, looked: dict) -> list[dict]:
    """The instructions for the page's kept-back threads (`forks.look`,
    `forks.listed`), read again only once the page's reading has moved."""
    from .forks import listed, look
    from .served_state.reading import page_reading

    try:
        stamp = page_reading(page_dir)
        kept = looked.get(page_dir)
        if kept is not None and kept[0] == stamp:
            return kept[1]
        threads = look(sid, page_dir)
    except FileNotFoundError:
        looked.pop(page_dir, None)
        return []
    requests = [listed(thread, page_dir) for thread in threads]
    looked[page_dir] = (stamp, requests)
    return requests


def main(
    harness: str, *, watch: bool = False, pages: bool = False, fork: bool = False
) -> None:
    """Read one harness payload and dispatch it.

    The Click hook command is the caller.
    A watch owns leases, so it releases them when the harness terminates it.
    """
    import os
    import sys
    import tempfile

    from .session_runtime import delivering_launcher, own_launcher

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as error:
        raise Refused(
            f"hook expects the harness's JSON payload on stdin ({error.msg})"
        ) from error
    sid = payload.get("session_id") or ""
    if payload.get("hook_event_name") == "PreToolUse" and sid:
        # Hooks run outside the harness's sandbox and shell commands inside it.
        # Claude Code's registration runs this only before a command naming
        # `leaf`, so a session that never runs one opens no road out. Each Leaf
        # the hook passes through opens it before handing the hook on, the
        # installed copy among them (`bridge.py`).
        from .harness import hook_harness

        hook_harness(harness, sid).escape_sandbox()
    launcher = delivering_launcher(sid)
    if launcher != own_launcher():
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
                *(["--fork"] if fork else []),
            ],
            environment,
        )
    if pages:
        cmd_pages(payload)
        return
    if fork:
        from .carrier import step

        answered = step(payload.get("session_id") or "", payload)
        if answered is not None:
            print(json.dumps(answered, ensure_ascii=False), flush=True)
        return
    if watch:
        from .leases import release_on_termination

        release_on_termination()
        if woke := cmd_watch(harness, payload):
            print(woke, flush=True)
        return
    cmd_hook(harness, payload)
