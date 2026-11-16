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
session's pages (`cmd_pages`) to draw them beside the prompt and to fork for each
thread Leaf keeps back and to make each completion a page server asks of it, and at
each turn's end asks the clerk what to fork the conversation with; `--fork` asks for
each fork's prompt and hands back its answer (`clerk.cmd_fork`, `forks.cmd_fork`),
or a completion's (`completions.cmd_reply`). The follower records the process it
runs in, so a Stop can tell the user where Claude Code didn't load the module
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

    Claude Code keeps a model-written summary, the last few files read and the
    skills loaded through its Skill tool. The rest of what the agent read is gone,
    which takes the skill when it was read as a file, the references, and every
    widget's instructions, which only `leaf page instructions` prints. The summary
    paraphrases those rules, as in "settle the lf-options with `settled`", and the
    page's own markup offers a pattern to copy, so an agent can believe it still has
    them. Sending the agent back to the skill alone isn't enough: agents reread the
    skill after most compactions, yet `lf-options` groups written after a compaction
    often lack that widget's instructions in context, which every group written
    before one has. Restating a rule on every prompt weighs on every turn and covers
    only that rule, so this message names what the compaction removed and
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
    and the model completions page servers ask of it (`completions.pending`), as one
    JSON object, `{"pages": [...], "completions": [...]}`, then again each time
    either changes, until the session holds no page. Leaf's Claude Code hooks module
    draws the pages beside the prompt, and makes each completion, given as the `id`
    and `request` it answers with `$.model.complete`.

    Read the pages every presence interval: a dead server leaves its row behind, so
    native notifications cannot replace this timer. It waits on the session's
    requests (`completions.watch`), so it lists one as it is written.

    A payload asking for `forks`, from a hooks module this Leaf ships (its `module`,
    the digest of the module's source as it loaded, `session_runtime.module_current`),
    makes the follower the session's forks lane
    (`forks.take_lane`) while it runs, and gives each page the threads Leaf keeps back
    (`kept_back`), each as the `thread` and `inputs` the module asks a line fork about,
    handing to the session those whose bound has passed (`forks.look`). Between presence reads it waits on each
    page's subscription (`file_changes.page_changes`) and on the lane's name, so it
    looks again as a message is admitted, as a later follower takes the lane, or as
    the earliest bound runs out. It reads a page again only once its reading has
    moved or a bound has run out, since Leaf starts keeping a thread back as its
    message is admitted.

    It exits with `EX_TEMPFAIL`, without a last line, once the session's delivery
    runs another Leaf than its own (`_moved_on`), and the module starts it again,
    under that Leaf. A follower runs as long as its session, while the session's
    hooks hand themselves at each call to the Leaf delivering for it: a newer copy
    Claude Code installed, a checkout the session selected, or the same checkout
    moved past a protocol bump. That newer Leaf reads an older follower's lane as no
    one's. On 8 November one follower, four days old, kept back messages that the
    line fork's step, under the newer Leaf, refused as not kept back, so each waited
    out its bound with no line.

    The module that reads the list stays the one the session loaded until
    `/reload-plugins`, so a follower under a newer Leaf may print it to a module
    that reads kept-back threads by an older contract. From 10 to 11 November a
    session running a checkout's Leaf under the installed copy's module, which read
    them under another name, kept back every thread message for the whole bound with
    no line fork asked. So a follower whose module isn't this Leaf's keeps nothing
    back, and the session's messages reach it as they would without forks.

    The follower notes its verdict once in each page it holds
    (`interaction_log.record_follower`): whether the module asked for forks, the
    module's digest, and whether that module is this Leaf's. So a message admission
    found with no lane (`forks.kept_from_main_at_admission`) says whether forks were
    off, the module stale, or the follower that held the lane gone
    (`leaf-dev logs timeline`)."""
    sid = payload.get("session_id") or ""
    from .harness import ClaudeCodeHarness
    from .leases import mark_module

    # Only Leaf's Claude Code module starts a follower, so one running shows the
    # module loaded in this process (`ClaudeCodeHarness.unloaded_module`).
    if (pid := ClaudeCodeHarness.process_pid()) is not None:
        mark_module(sid, pid)
    if not owned_pages(sid):
        print(json.dumps({"pages": [], "completions": []}), flush=True)
        return

    from .completions import pending, watch
    from .file_changes import FileChanges, wait
    from .interaction_log import record_follower
    from .presence import PRESENCE_CACHE_S, live_leaves
    from .session_runtime import module_current

    queued = watch(sid)
    asked, current = bool(payload.get("forks")), module_current(payload.get("module"))
    forking = asked and current
    # The pages this follower has noted its verdict in, each once.
    noted: set = set()
    if forking:
        from .file_changes import page_changes
        from .forks import lane_path, take_lane
        from .leases import release_lease
        from .page_memory import memory_of

        lane = take_lane(sid)
        # Resolved, as notifications name it.
        named = lane_path(sid).resolve()
        renamed = FileChanges({named.parent: False}, lambda path: path == named)
    looked: dict = {}
    shown = None
    try:
        while True:
            if _moved_on(sid):
                # EX_TEMPFAIL: the module starts it again, under that Leaf.
                raise SystemExit(os.EX_TEMPFAIL)
            held = {page.resolve() for page in owned_pages(sid)}
            record_follower(
                sorted(held - noted),
                sid,
                module=payload.get("module"),
                forks=asked,
                current=current,
            )
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
                    # A later follower took the lane, which let go what this one
                    # kept back, and forks what this one would.
                    forking = False
                    renamed.close()
                    _let_go(sid, looked)
                # Every page the session holds keeps its bounds, listed or not, as
                # one whose server stopped is not.
                kept = (
                    {page: _kept_back(sid, page, looked) for page in held}
                    if forking
                    else {}
                )
                listed = json.dumps(
                    {
                        "pages": [
                            {
                                **{field: leaf[field] for field in SHOWN_FIELDS},
                                **({"kept_back": kept[page]} if forking else {}),
                            }
                            for page, leaf in leaves
                        ],
                        "completions": pending(sid),
                    }
                )
                if listed != shown:
                    print(listed, flush=True)
                    shown = listed
                if not held:
                    return
                bound = min(
                    (looked[page][1] for page in held if page in looked),
                    default=float("inf"),
                )
                remaining = presence_due - time.monotonic()
                wait(marks, max(0.0, min(remaining, bound - time.time())))
                if time.monotonic() >= presence_due:
                    break
    finally:
        queued.close()
        if forking:
            release_lease(lane)
            renamed.close()
            _let_go(sid, looked)


def _moved_on(sid: str) -> bool:
    """Whether the session's delivery now runs another Leaf than this process: one
    selected or installed since it started, which its hooks hand themselves to as
    `main` does (`session_runtime.delivering_launcher`), or its own install moved
    under it to another page protocol (`registry.kernel.installed_protocol`), or
    removed, as a selected checkout's is when its worktree goes: the module starts
    the follower again from its own launcher, which hands it to the Leaf delivering
    now. A registry read mid-write reads as unmoved until it settles."""
    from .registry.kernel import installed_protocol, kernel_protocol
    from .session_runtime import delivering_launcher, own_launcher

    own = own_launcher()
    if not os.access(own, os.X_OK):
        return True
    try:
        return (
            delivering_launcher(sid) != own or installed_protocol() != kernel_protocol()
        )
    except (OSError, ValueError, KeyError):
        return False


def _let_go(sid: str, looked: dict) -> None:
    """Nudge what a lane this follower gave up kept back, as a watch giving up its
    lease nudges what it held back (`session.nudge_pending`): only where the follower
    last listed a kept-back thread, since a nudge as a Stop hook's watch starts would
    wake the session a second time."""
    from .session import nudge_pending

    keeping = any(requests for _stamp, _until, requests in looked.values())
    looked.clear()
    if keeping:
        nudge_pending(sid)


def _kept_back(sid: str, page_dir, looked: dict) -> list[dict]:
    """The page's kept-back threads (`forks.look`), read again only once the page's
    reading has moved or the earliest bound `looked` kept for it has run out."""
    from .forks import look
    from .served_state.reading import page_reading

    try:
        stamp = page_reading(page_dir)
        kept = looked.get(page_dir)
        if kept is not None and kept[0] == stamp and time.time() < kept[1]:
            return kept[2]
        threads = look(sid, page_dir)
    except FileNotFoundError:
        # A page that is gone keeps nothing back, and no bound to wake for.
        looked.pop(page_dir, None)
        return []
    requests = [thread.basis(page_dir) for thread in threads]
    until = min((thread.until for thread in threads), default=float("inf"))
    looked[page_dir] = (stamp, until, requests)
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
        # the hook passes through opens it before handing the hook on, the copy
        # the harness loaded among them (`bridge.py`).
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
        # A completion's reply (`completions`), a kept-back thread's forks or the
        # end of an agent's run (`forks`), or else the clerk's.
        if "completion" in payload:
            from .completions import cmd_reply as cmd_fork
        elif "thread" in payload or "ended" in payload:
            from .forks import cmd_fork
        else:
            from .clerk import cmd_fork

        answered = cmd_fork(payload.get("session_id") or "", payload)
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
