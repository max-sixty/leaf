"""The agent-harness hooks Leaf registers, and the part of each that reads no page.

Every hook marks that it ran for its session (`leases.mark_hooks`), evidence
that its harness supports hook delivery (`Harness.hooks_carry`), and the Leaf it
runs (`leases.mark_root`). The skill the agent read stays in its conversation as
the harness keeps it: when an update or a merge changes the skill under a running
session, Leaf tells the agent nothing, and the harness's own means, such as Claude
Code's `/reload-skills`, pick the change up. The maintainer chose that over a
notice each hook queued once the skill it ships differed from the previous
hook's: the skill changes often, so the notice fired on most updates, and it
needed a change for each way a copy of Leaf can change. An
explicit `leaf wait` always prints the envelope; it does not depend on another
hook running after it. SessionEnd retires the harness instance without reading pages;
persisted desktop chats retain their generation across instance unloads.

Codex's startup hook captures its validated native source even when the first
input is a dispatched tool message rather than a user prompt. Its synchronous
prompt hook records the provider turn even before the session claims a page. Its native transcript also records turns resumed without input,
which run no prompt hook. Hooks reconcile that provider evidence before checking
their turn identity (`Harness.reconcile_turn`), then offer input between steps
or before Stop (`offer_at_step`) and leave receipt to the agent's explicit
confirmation of complete input.
An accepted TurnStart opens the same lifecycle as UserPromptSubmit without
reading or receiving page input. Pi calls it after its SDK reserves the run;
accepted message finalization or a live turn boundary confirms the receipt.

The payload names the session and turn: hook subprocesses need not have the tool
process's environment. Stop or Interrupt closes that observed turn, including a
turn not yet claimed by any page; a newer prompt protects its own epoch. A payload
that names no turn can state when the turn ended (`ended_at`, in POSIX seconds),
as the Interrupt from Pi's extension does (`state.close_session_turn` says which
turns such a close leaves as they are).

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
(`cmd_fork`; `carrier.py`'s header holds that contract). The follower records the
process it runs in, so a Stop can tell the user where Claude Code didn't load the
module (`Harness.unloaded_module`). `leaf hook` (`cli.hook`) dispatches here.

Claude Code's PostToolBatch carries pending input before the next model call,
after successful or failed tools, using the same envelope and receipt as its
prompt hook. A boundary with nothing pending adds no response-debt reminders.
Claude Code may still drop what a hook hands over, so each of its hooks first
records the receipt of what its transcript shows entered the model's context
(`delivery.confirm_entered`). Its hooks name the turn by `prompt_id`
(`ClaudeCodeHarness.hook_payload`).

Before it opens its turn, the prompt hook serves again each page the session still
means to serve whose ownership or server is down, as a resumed session's are. The
turn hears only of a page that did not start (`reconnect`). A SessionStart opens no
turn and claims nothing; after a compaction it tells an agent holding a page which of
Leaf's instructions the compaction removed (`reload_skill`). Claude Code runs Leaf's
start hook only then (`hooks.json`), since a resumed session's first reply waits for
its start hooks.

Each harness's registrations name it (`--harness`) and its payload names the
session; `harness.hook_harness` says why neither comes from the environment. Every
hook runs the Leaf its harness loaded (`session-lifetime.md`, "Which Leaf runs a
session")."""

import json
import os
import sys
import tempfile
import time
from typing import TYPE_CHECKING, NoReturn

from leaf.base.leases import (
    end_if_terminated,
    first_hook_for_tool,
    lane_path,
    mark_hooks,
    mark_module,
    mark_root,
    release_lease,
    release_on_termination,
    take_lane,
)
from leaf.base.page_memory import memory_of
from leaf.base.refusals import Refused
from leaf.base.schema import SKILL_FILE
from leaf.base.state import (
    PLUGIN_ROOT,
    CopyReplaced,
    advance_turn,
    close_session_turn,
    flocked,
    held_claims,
    installed_protocol,
    kernel_protocol,
    prompt_turn,
    session_lock_path,
    session_record,
    status_check_due,
    still_named,
    turn_closed,
    worker_tool_batch,
)
from leaf.log.interaction_log import record_follower
from leaf.records.transaction import owned_pages

if TYPE_CHECKING:
    from leaf.base.harness import Harness

if TYPE_CHECKING:
    from leaf.base.harness import Harness


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
    mark_root(sid, PLUGIN_ROOT)
    assert isinstance(event, str)
    if event == "PreToolUse" and not first_hook_for_tool(
        sid, payload.get("tool_use_id")
    ):
        return
    from leaf.base.harness import hook_harness

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
            from leaf.agents.delivery import confirm_entered

            confirm_entered(hooked, payload)
        return
    # What kept a page the session still means to serve from serving again.
    unserved = []
    if event in {"UserPromptSubmit", "TurnStart"}:
        if event == "UserPromptSubmit":
            # Before the turn opens, which then joins the generation a claim
            # starts where the session's last one ended or names another process.
            from leaf.commands.reconnect import serve_again

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
        from leaf.agents.delivery import confirm_entered

        confirm_entered(hooked, payload)
    prompt, expected = (
        offer_at_step(hooked, event, payload, expected)
        if hooked.adapter
        else (None, expected)
    )
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
    from leaf.commands.hook_transport import carry_turn

    ended = carry_turn(
        hooked, event, sid, payload, expected, started=started, unserved=unserved
    )
    if ended:
        close_session_turn(sid, turn_id, expected=expected)
        # A Stop that ends the turn printed nothing, so its output can tell the user.
        if notice := hooked.unloaded_module():
            print(json.dumps(notice), flush=True)


def offer_at_step(
    harness: "Harness", event: str, payload: dict, expected: dict | None
) -> tuple[str | None, dict | None]:
    """Offer the session's pending page input through hook `event` ahead of the hook
    transport (`hook_transport.carry_turn`), for a harness whose adapter's delivery
    record holds it (`Harness.adapter`). Returns what the hook puts in the turn's
    context, which ends the hook, and the lifecycle the hook goes on with otherwise:
    `expected`, or the renewal an offer made under it.

    Both the tool hook and Stop offer an envelope through Codex's one transport
    reservation (`codex.offer_hook_delivery`), since empty-input resume can reach
    Stop without running another tool. Stop offers only where no adapter will start
    a turn of its own for the input over App Server
    (`codex_adapter.later_turn_takes_input`), and the turn would continue for it
    (`hook_transport.stop_continues`). The tool hook offers input the cursor has not
    passed, and input the cursor passed that no pickup names, which a Codex
    session's receipts never leave, and Stop also an update the session holds no
    usable reference for (`delivery.deliverable`). The tool hook also carries the
    reminder of a status line left standing (`hook_transport.status_reminders`).

    Codex's tool hook runs after every tool call, so the adapter's module, which
    imports much that the tool hook doesn't need, loads only at Stop."""
    sid = harness.session
    if event not in {"PostToolUse", "Stop"} or not payload.get("turn_id"):
        return None, expected
    if not owned_pages(sid):
        return None, expected
    if event == "Stop":
        from leaf.agents.codex_adapter import later_turn_takes_input

        if later_turn_takes_input(sid):
            return None, expected
        from leaf.commands.hook_transport import read_plans, stop_continues

        plans = read_plans(sid)
        if not stop_continues(
            plans,
            [plan.batch for plan in plans if plan.batch],
            repeated=bool(payload.get("stop_hook_active")),
            reminds=harness.watches_between_turns(),
        ):
            return None, expected
    from leaf.agents.codex import offer_hook_delivery

    prompt, expected = offer_hook_delivery(sid, expected, received=event == "Stop")
    if event == "PostToolUse" and status_check_due(sid):
        from leaf.commands.hook_transport import read_plans, status_reminders

        renewals = status_reminders(sid, read_plans(sid))
        prompt = "\n".join(filter(None, [prompt, *renewals])) or None
    return prompt, expected


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
    from leaf.base.harness import hook_harness

    watching = hook_harness(harness, sid)
    if not watching.watches_between_turns():
        return None
    from leaf.commands.session import watch_between_turns

    return watch_between_turns(watching, payload)


# What `cmd_pages` prints of each page, so a change to anything else stays quiet.
SHOWN_FIELDS = ("page_key", "url", "title", "on_user", "threads", "activity")


def cmd_pages(payload: dict) -> None:
    """Print the live pages the payload's session holds (`presence.live_leaves`)
    and the instructions Leaf has for its hooks module (`carrier.py`), as one JSON
    object, `{"pages": [...], "do": [...]}`, then again each time either changes,
    until the session holds no page. The module draws the pages beside the prompt
    and runs each instruction once: a completion each page server asks of the
    session (`completions.listed`) and a line fork for each round of the user's that
    awaits the agent's working line (`forks.look`).

    Read the pages every presence interval: a dead server leaves its row behind, so
    native notifications cannot replace this timer. It waits on the session's
    requests (`completions.watch`), so it lists one as it is written.

    The follower is the session's forks lane (`leases.take_lane`) while it runs, and
    lists the line forks while it holds it. Between presence reads it waits on each
    page's subscription (`file_changes.page_changes`) and on the lane's name, so it
    looks again as a message is admitted or as a later follower takes the lane. It
    reads a page again only once its reading has moved. Its first look at a page
    takes the log as it stands, so it lists no round older than itself, and a
    follower started again lists none an earlier one listed.

    It runs the code it started with until it exits or the module that started it
    ends it, and Claude Code ends a module only to load another copy or the module's
    own changed code (`hooks/claude-code.ts`). So in a checkout Claude Code loads in
    place (`--plugin-dir`) it can run older Python than the session's hooks, as two
    versions of Leaf at one page protocol may run side by side. It exits with
    `EX_TEMPFAIL`, without a last line, once the tree it runs from has moved on under
    it (`_moved_on`), and the module starts it again from that tree as it then
    stands. A follower started again may print to an older module, which runs its
    instructions as any (`carrier.py`).

    The follower notes once in each page it holds that it runs
    (`interaction_log.record_follower`), so a round that got no line fork says
    whether a follower had run (`leaf-dev logs timeline`)."""
    sid = payload.get("session_id") or ""
    from leaf.base.harness import ClaudeCodeHarness

    # Only Leaf's Claude Code module starts a follower, so one running shows the
    # module loaded in this process (`ClaudeCodeHarness.unloaded_module`).
    if (pid := ClaudeCodeHarness.process_pid()) is not None:
        mark_module(sid, pid)
    if not owned_pages(sid):
        print(json.dumps({"pages": [], "do": []}), flush=True)
        return

    from leaf.agents.completions import listed as completions_listed
    from leaf.agents.completions import watch
    from leaf.agents.presence import PRESENCE_CACHE_S, live_leaves
    from leaf.log.file_changes import FileChanges, page_changes, wait

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
    try:
        while True:
            if _moved_on():
                # EX_TEMPFAIL: the module starts it again, from the tree as it is.
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
                    # A later follower took the lane, and lists the line forks now.
                    forking = False
                    renamed.close()
                lines = (
                    {page: _lines(sid, page, looked) for page in held}
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
                            *(item for items in lines.values() for item in items),
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


def _moved_on() -> bool:
    """Whether the tree this process runs from has moved on under it: a checkout
    moved to another page protocol (`state.installed_protocol`), or the
    tree removed, as Claude Code may remove a copy it replaced. The module then
    starts the follower again from the same launcher; where the tree is gone, none
    starts until `/reload-plugins`. A registry read mid-write reads as unmoved until
    it settles."""
    if not os.access(PLUGIN_ROOT / "bin" / "leaf", os.X_OK):
        return True
    try:
        return installed_protocol() != kernel_protocol()
    except (OSError, ValueError, KeyError):
        return False


def _lines(sid: str, page_dir, looked: dict) -> list[dict]:
    """The line forks to list for the page (`forks.look`), read again only once the
    page's reading has moved, from the seq the follower's first look took."""
    from leaf.agents.forks import look
    from leaf.source.page_inputs import page_reading

    try:
        stamp = page_reading(page_dir)
        kept = looked.get(page_dir)
        if kept is not None and kept[0] == stamp:
            return kept[2]
        requests, after = look(sid, page_dir, kept[1] if kept is not None else None)
    except FileNotFoundError:
        looked.pop(page_dir, None)
        return []
    looked[page_dir] = (stamp, after, requests)
    return requests


def cmd_fork(payload: dict) -> dict | None:
    """Leaf's answer to the hooks module's report `payload` (`carrier.py`): a turn's
    end goes to the turn-end check (`clerk.turn_ended`) with what its fork is shown of
    each page the session holds (`agent_state.turn_end_facts`), and an instruction's
    result to the step its basis's `kind` names: the turn-end check's fork (`check`),
    a completion (`completion`), or a thread's line fork or a fork beside it (`line`,
    `beside`). A kind no step takes answers with a line for the log, so the module
    stops reporting it."""
    sid = payload.get("session_id") or ""
    if not sid:
        return None
    if payload.get("turn_end"):
        from leaf.agents.clerk import turn_ended
        from leaf.commands.agent_state import turn_end_facts

        return turn_ended(sid, turn_end_facts(sid))
    kind = payload["basis"]["kind"]
    if kind == "check":
        from leaf.agents.clerk import checked as taken
    elif kind == "completion":
        from leaf.agents.completions import replied as taken
    elif kind in ("line", "beside"):
        from leaf.agents.forks import step as taken
    else:
        return {"log": f"no step of this Leaf takes a {kind!r} instruction's report"}
    return taken(sid, payload)


def main(
    harness: str, *, watch: bool = False, pages: bool = False, fork: bool = False
) -> None:
    """Read one harness payload and dispatch it.

    The Click hook command is the caller.
    A watch owns leases, so it releases them when the harness terminates it.

    A watch whose harness replaced the installed copy it loaded
    (`state.CopyReplaced`) goes on as the watch of the copy now at that path, which
    this process becomes through that copy's launcher, with the payload it started
    with; an Interrupt it answers again leaves the turn its predecessor closed as it
    was (`state.close_session_turn`). The harness started this process and waits on
    it: Pi's extension reads the line it prints and stops it by its pid, so the
    watch carries on under the new copy with no change to the extension. Exiting
    for the extension to start the watch again would need the extension to tell
    that exit from a watch with nothing to say. A new copy that can't start, as one whose environment can't be
    built, leaves the session unwatched until the extension starts the watch again
    after the next run, as any failed watch does; the session's hooks can't run
    until that copy can start either.
    """
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
        # `leaf`, so a session that never runs one opens no road out (`bridge.py`).
        from leaf.base.harness import hook_harness

        hook_harness(harness, sid).escape_sandbox()
    if pages:
        cmd_pages(payload)
        return
    if fork:
        answered = cmd_fork(payload)
        if answered is not None:
            print(json.dumps(answered, ensure_ascii=False), flush=True)
        return
    if watch:
        release_on_termination()
        try:
            woke = cmd_watch(harness, payload)
        except CopyReplaced:
            # A stop that arrived as the watch let go, whose raise a finalizer
            # discarded, ends it here rather than the successor never hearing it.
            end_if_terminated()
            _watch_from_new_copy(harness, payload)
        if woke:
            print(woke, flush=True)
        return
    cmd_hook(harness, payload)


def _watch_from_new_copy(harness: str, payload: dict) -> NoReturn:
    """Replace this process with the watch for `harness` of the copy now at this
    one's path, through its launcher, given `payload` on its stdin. The harness's
    process handle then reaches the new watch, so cancellation and the watch's
    lifetime hold. The stdin is a file rather than a pipe, which a large payload
    would fill. The environment drops the host's choice of launcher
    (`LEAF_HOST_LAUNCHER`, which `bin/leaf` reads), since that would send the call
    back to the host's."""
    with tempfile.TemporaryFile() as incoming:
        incoming.write(json.dumps(payload).encode())
        incoming.seek(0)
        os.dup2(incoming.fileno(), 0)
    launcher = PLUGIN_ROOT / "bin" / "leaf"
    environment = dict(os.environ)
    environment.pop("LEAF_HOST_LAUNCHER", None)
    os.execve(
        launcher,
        [str(launcher), "hook", "--harness", harness, "--watch"],
        environment,
    )
