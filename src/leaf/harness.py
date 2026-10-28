"""The agent harnesses Leaf runs under, and the Claude Code messaging socket
behind one of them.

A harness is the program an agent session runs in, such as Claude Code or Codex, as
Leaf meets it. `Harness` collects everything that
differs between them — session lifetime, watcher and transports, the hook's remedies,
the way out of its sandbox, the way to reach a session with nothing watching — so
that every module below this one dispatches on what a harness declares rather than
on which harness it is: behaviour one harness needs is a method here, which the
others answer by default, and no module outside this one compares a harness's name
or reads its environment variables. `session_harness` reads the one running this command out of the
environment; `claim_harness` rebuilds the one a page's claim recorded.

The machine facts a harness rests on live elsewhere: `machine` reads the
processes running above this one, and `leases` holds the leases a watcher
proves itself with."""

from __future__ import annotations

import itertools
import json
import mmap
import os
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import ClassVar

from leaf.files import read_json
from leaf.leases import (
    adapter_is_live,
    hooks_ran,
    wait_is_live,
)
from leaf.machine import ancestry, pid_alive, process_argv
from leaf.page_memory import Slot
from leaf.refusals import Refused


@dataclass(frozen=True)
class Harness:
    """One agent harness, and everything Leaf's harness-neutral code differs on.

    `session` is the harness's own stable id for this session and `agent` the
    display name the page shows for it. Both are per-session; the rest of a
    harness is fixed for the program, and stated on its class.

    `name` is the one fact the claim writes down: `claim_harness` reads it back
    to rebuild this object, and a reader meeting that claim later — the page
    server, the append door, the Stop hook — asks the object rather than
    re-deriving anything from an environment that may not be the claimant's.
    Nothing compares the name outside this module and a harness's own code.

    What differs between harnesses is how a leaf's input reaches the session.
    Two things carry it. The *watcher* holds the session's wait lease between
    turns and brings the page's input to a turn; it is one of four kinds:

    - a hook watch, which the harness itself starts as each turn ends
      (`watches_between_turns`);
    - a model wait, `leaf wait`, which the model runs directly or in a watcher
      task;
    - the adapter, a detached process proven by a lease of its own
      (`adapter_is_live`);
    - the host, a program that drives App Server and starts every turn itself.

    The *transport* is how one delivery enters a turn's context: the hooks
    (`hook_delivers`, or Codex's tool hook, `offer_at_step`),
    the wait's output, Codex's queue, or a turn Leaf starts over App Server. The
    envelope states what the transport decides (`../../skills/leaf/references/event-batches.md`).
    The methods below answer for each harness's watcher and transports:

    - Claude Code runs Leaf's Stop hooks as each turn ends: one watches the
      session's pages in the background and wakes the session when input arrives
      (`watches_between_turns`), and the prompt hook, which runs as the turn the
      wake opens begins, and the tool-batch hook within a turn put the input in
      the turn's context (`hook_delivers`), which its transcript confirms
      (`commits_hook_context`); the other Stop hook does only under plain
      `--print`, where no watch follows the turn (`hook_transport`). The prompt
      hook starts a watch too, which waits while its turn runs, so a turn an
      interrupt ends without its Stop hooks still has one, unless the session
      held no page when that turn's prompt came. Then nothing watches, as when a
      watch fails, reaches its hook's timeout or loses a background job's retired
      worker, while the session lives on, which is why this is the harness with a
      `nudge` (`presence.nudge_interrupted`).
    - Pi runs Leaf's extension in its own process, which calls the same hooks at
      the same points of a run and starts the same watch as each run settles, and
      starts the turn the watch wakes itself.
    - Codex has a detached adapter that outlives the turn and proves itself by
      holding the adapter lease. It queues each delivery with `codex queue`, or
      starts its turn over the task's App Server when Leaf can reach one, and
      only that start takes the input that arrives as a turn ends
      (`later_turn_takes_input`).
    - An embedded harness drives Codex App Server itself and starts the turns;
      nothing outside it carries input in.
    """

    session: str
    agent: str

    name: ClassVar[str]
    # Whether the harness's hooks can carry input into the turn: they freeze and
    # hand over the whole delivery. Explicit waits carry their own envelope.
    # `hooks_carry` says whether they do for this session.
    hook_delivers: ClassVar[bool] = False
    # Whether the context a hook hands over is in the session once the hook
    # returns, so the hook confirms what it hands over. Where it is not, the hand-
    # over waits for the harness's record of the model's context to show it
    # (`entered_context`, `delivery.confirm_entered`), and is offered again if its
    # turn ends without it.
    commits_hook_context: ClassVar[bool] = True
    # The most UTF-8 bytes of hook context the harness shows the model whole, or
    # None where it shows any size.
    hook_context_bytes: ClassVar[int | None] = None

    @classmethod
    def fits_hook_context(cls, context: str) -> bool:
        """Whether the harness shows `context`, a hook's whole output to the turn,
        to the model whole. Every hook hands a delivery whose context doesn't fit
        over as its pointer (`delivery.delivery_pointer_prompt`)."""
        return (
            cls.hook_context_bytes is None
            or len(context.encode("utf-8")) <= cls.hook_context_bytes
        )

    @classmethod
    def from_claim(cls, claim: dict) -> Harness:
        """Rebuild the claimant's harness from the record it wrote."""
        return cls(session=claim["id"], agent=claim["agent"])

    def lifetime(self) -> dict:
        """The claim fields naming what this session's lifetime is, which is what
        the claim records and its readers act on: a lifetime that has ended makes
        ownership inactive, and a session-managed server retires
        ORPHAN_GRACE_SECS after it (`stop_when_service_ends`). `claim_is_active`
        consumes these fields without knowing which harness wrote them."""
        raise NotImplementedError

    def escape_sandbox(self) -> None:
        """Open the road out of this harness's sandbox that this session's `leaf`
        commands take, for as long as the session lives (`lifetime`). The hook
        before a command naming `leaf` calls it, outside the sandbox. A harness
        whose sandbox leaves no road out, as Codex's does, opens none; Codex's
        agent runs a confined command through Leaf's MCP server instead
        (`codex_tool.py`)."""

    def watcher_live(self, *, listening: bool) -> bool:
        """Whether this session's watcher can still take the page's input into a
        turn — the Stop hook's watch question, and its reason to believe a draft
        reply will be committed.

        `listening` is the session's wait lease: some process is reading this
        page's events for it. That is the whole proof for a watcher that is one
        process holding one lease. Where the session's own hooks carry its input,
        the watch is started again as every turn ends, so the watcher stands
        across the turn as well as between turns. Where the harness runs no watch
        between turns (`watches_between_turns`), as under Claude Code's plain
        `--print`, the session ends with its run and its claims with it, so no
        page is left owed a watcher. A watcher that has to prove more overrides
        this."""
        return listening or self.hooks_carry()

    def ensure_delivery(self) -> None:
        """Prepare this harness's watcher before handing over a served page.

        Harnesses whose hooks or host own delivery need no separate process.
        The adapter starts or joins its task-wide watch here.
        """

    @contextmanager
    def preparing_delivery(self):
        """Prepare delivery and retain it until the caller publishes its page.

        The adapter is kept from no-page retirement throughout this boundary.
        A failed preparation therefore precedes any page ownership transition.
        """
        self.ensure_delivery()
        yield

    def hooks_carry(self) -> bool:
        """Whether the harness supports hook delivery and a hook has run here.

        This is capability evidence for hook transport and turn activity, not
        proof that a future hook will succeed. Explicit waits deliver directly.
        """
        return self.hook_delivers and hooks_ran(self.session)

    def turn_takes_input(self) -> bool:
        """Whether an open turn of this session takes new input before it ends: its
        hooks hand pending input into the turn between steps and as it would end.
        The page's status reads such a turn as listening between two waits
        (`activity.takes_input`)."""
        return self.hooks_carry()

    def receive_pointer(self, payload: dict) -> list[Path]:
        """Confirm the reader's complete-reading attestation for a pointer whose
        original `acknowledge` names nobody, the receipt its hooks left to the reader.

        Explicit reader confirmation is strict: a transferred page or ended turn
        reports refusal rather than silently accepting a partial receipt."""
        from .delivery import receive

        return receive(payload, self.session)

    def input_unpicked(self, page_dir: Path, *, listening: bool) -> str:
        """What to do about events past this page's cursor that nothing will
        carry."""
        raise NotImplementedError

    def nothing_listening(self, page_dir: Path, *, listening: bool) -> str:
        """What to do about a live page this session owes a watcher. A harness whose
        hooks carry input never owes one inside a hook, since the hook's own run is
        the watcher's proof (`watcher_live`), so it leaves this unimplemented."""
        raise NotImplementedError

    def watches_between_turns(self) -> bool:
        """Whether this session's harness starts Leaf's watch as each turn ends, from
        a hook or extension, which wakes the session when input arrives
        (`session.watch_between_turns`); the model then starts no `leaf wait`."""
        return False

    def later_turn_takes_input(self) -> bool:
        """Whether input that arrives as this session's turn ends goes to a turn of
        its own rather than into the ending one, where the Stop hook would hand it
        (`hook_transport`). That turn must open without the agent asking, and must
        show the user less than continuing the ending turn would: a watch between
        turns wakes one (`watches_between_turns`), and Codex's adapter starts one
        over App Server."""
        return self.watches_between_turns()

    def process_runs(self) -> bool:
        """Whether the harness process whose hook started this watch still runs. A
        watch it has orphaned can wake nobody, and would hold the session's lease
        over the input a `nudge` could still deliver."""
        return True

    @classmethod
    def run_ack(cls, command: str) -> str:
        """How the reader of this session's printed delivery runs `command`, which
        confirms it and goes on waiting: the verb phrase the delivery's
        `acknowledge` ends with. A wait held in a background task is the
        default."""
        return f"start `{command}` as the next background task"

    @classmethod
    def hook_context(cls, event: str, message: str) -> dict:
        """The output of hook `event` that puts `message` in the turn's context:
        at a prompt, before the turn's work; at Stop, as new context that keeps
        the ending turn going.

        Every harness Leaf's hooks run under reads `additionalContext` at a prompt.
        At Stop, Claude Code continues a turn on it as it does on a block, and
        labels it "Stop hook additional context" rather than "Stop hook error":
        its schema calls that field non-error feedback after which the
        conversation continues, and a probe at 2.1.284 saw the turn go on and the
        next Stop arrive with `stop_hook_active`. Nothing Leaf's Stop hook says is
        an error, so it takes this channel where the harness has one."""
        return {
            "hookSpecificOutput": {"hookEventName": event, "additionalContext": message}
        }

    @classmethod
    def hook_payload(cls, payload: dict) -> dict:
        """A hook's payload as `hooks` reads it, with the harness's own name for the
        turn under `turn_id`, where it names one."""
        return payload

    def reconcile_turn(self, payload: dict, expected: dict | None) -> dict | None:
        """The session's lifecycle as a hook goes on to read it, from `expected`, the
        record as the hook found it. A harness that records turns its hooks never
        see applies them here. A prompt hook reconciles after recording its own
        turn, every other hook before checking the turn its payload names."""
        return expected

    def entered_context(self, payload: dict) -> set[str]:
        """The ids of the inputs this session's hooks handed over inline that the
        harness's own record, named in hook `payload`, shows in the model's context.
        Only a harness whose hooks don't commit their context
        (`commits_hook_context`) is asked (`delivery.confirm_entered`)."""
        return set()

    def offer_at_step(
        self, event: str, payload: dict, expected: dict | None
    ) -> tuple[str | None, dict | None]:
        """Offer the session's pending page input through hook `event` ahead of the
        hook transport (`hook_transport.carry_turn`), where this harness's hooks do.

        Returns what the hook puts in the turn's context, which ends the hook, and
        the lifecycle the hook goes on with otherwise: `expected`, or the renewal
        an offer made under it. Where the hook transport carries every input,
        nothing is offered here."""
        return None, expected

    def nudge(self, page_dir: Path) -> bool:
        """Put this page's new input in front of the session, and say whether
        anything took it.

        Only a watcher the session's own turns start stops between turns while
        its session stands, so only such a harness has anywhere to put this. A
        watcher that is a process of its own is either running, and needs no
        telling, or gone along with the session it served."""
        return False

    def input_wakes(self) -> bool:
        """Whether `nudge` would now start a turn of this session's for the page's
        next input, so the page reads its agent as taking input while no watch
        holds the lease (`activity.canonical_activity`). Only a nudge whose
        recipient takes the message says so; one it may hold or drop doesn't."""
        return False

    def inference_generator(self) -> Callable[..., dict] | None:
        """Tool-free structured inference using this harness's login, if supported."""
        return None

    def title_generator(self) -> Callable[[str, Path], dict] | None:
        """Name threads through this harness's structured inference, if supported."""
        from leaf.thread_titles import title_generator

        infer = self.inference_generator()
        return title_generator(infer) if infer is not None else None

    def live_turn(self) -> dict | None:
        """What the harness itself says about this session right now, or None where it
        says nothing a reader can take.

        `{"state": "busy" | "waiting" | "idle", "since": <iso>}`, dated by the
        harness's own last change: `idle` once no turn runs, `waiting` while a turn
        holds a dialog open in the session's own window. `activity.claimant_turn`
        weighs it by that date against the claim's turn stamps, which the hooks
        write and so cannot see a turn end that runs no hook."""
        return None

    def session_name(self) -> str | None:
        """The name the harness shows for this session now, such as one the user gave
        it, or None where it shows none. Read live rather than kept in the claim,
        since a harness names a session after its first prompt and renames it when
        the user asks."""
        return None


class EnvironmentHarness(Harness):
    """A harness the environment implies, by the variable its session id arrives
    in. It also names the display default a launch that set no LEAF_AGENT gets.
    A harness that declares itself, as an embedded harness does, states neither.

    `identity_variables` is every variable the harness reads to know which
    session this is and how long it lives: its session variables, then the ones
    `lifetime` reads."""

    default_agent: ClassVar[str]
    session_variables: ClassVar[tuple[str, ...]]
    identity_variables: ClassVar[tuple[str, ...]]

    @classmethod
    def process_pid(cls) -> int | None:
        """The harness process this environment says the session runs in, or None
        where it says none: what `session_harness` ranks a nested harness by."""
        raise NotImplementedError


# What Leaf's nudge to a Claude Code session says after the page's path, through
# its socket or as a resumed job's prompt; the hooks module draws it by these words.
NUDGE_WORDS = "has new input, which arrives with this message."


@dataclass(frozen=True)
class ClaudeCodeHarness(EnvironmentHarness):
    """Claude Code: a Stop hook that watches between turns and wakes the session,
    hooks that carry input into the turn, and a socket to reach it with.

    `job` is the background job directory a claim rests on (`lifetime`), which
    `nudge` resumes when no worker hosts the job; None for a session the user sits
    at, and for the harness the environment implies."""

    job: str | None = None

    name = "claude-code"
    default_agent = "Claude"
    session_variables = ("CLAUDE_CODE_SESSION_ID",)
    identity_variables = (
        *session_variables,
        "CLAUDE_PID",
        "CLAUDE_JOB_DIR",
        "CLAUDE_CODE_HOST_SESSION_ID",
    )
    # Claude Code runs the prompt hook on every turn a background task's end
    # opens, idle or mid-turn, and adds what it returns to that turn's context.
    hook_delivers = True
    # It reads a hook's output only once every hook of that event has exited, and
    # Escape before then drops the whole prompt, Leaf's context with it (measured
    # at 2.1.304 with a second prompt hook sleeping 6 s). No hook says the output
    # was taken; the transcript does (`entered_context`).
    commits_hook_context = False
    # It writes a larger hook context to a file and hands the turn a 2 KB preview
    # and the path instead: measured at 2.1.283 with ASCII, 9,990 characters
    # arrived whole and 10,010 did not. Which unit it counts is unmeasured, so the
    # limit counts UTF-8 bytes, the strictest reading.
    hook_context_bytes = 9_990

    def lifetime(self) -> dict:
        """A session the user sits at is a process, and Claude Code states it
        outright as CLAUDE_PID.

        A background job (`claude --bg`, the agents view) has no such process.
        Its turns run on daemon workers, and CLAUDE_PID names the worker hosting
        the current sitting. The daemon retires that worker about an hour after
        the job goes idle and claims a fresh one at the next wake — measured at
        Claude Code 2.1.241 from its daemon log, `bg settled … (done)` then `bg
        claimed-spare …` — while the job, the session every wake resumes, stands
        until it is deleted. So a job's lifetime is `job`, the directory
        CLAUDE_JOB_DIR names, and a page held by one stays served until the job
        is deleted or `leaf server stop` ends it. The fact read there is the job
        record, `state.json`, which the daemon writes as it creates the job and
        takes with it; the directory alone can stand empty, for a spare never
        assigned or a job an older daemon cleaned. The record's `sessionId` has
        to be this session's, because the variable is inherited: a session
        started under the job's own shell tool carries the job's directory and
        is a process of its own.

        A session in the Claude desktop app is a process the app treats as
        disposable: it stops every session to install an update once its
        window has been unfocused for ten minutes, and resumes one, as a new
        process, only when the user next opens it (measured at app 3.6556.1
        from its `main.log`). The session the user sees is the app's record of
        it, which CLAUDE_CODE_HOST_SESSION_ID names (`desktop_session_record`),
        so its lifetime is `app`, that record's path, for as long as the record
        names this session (`service.lifetime_is_live`). The variable is
        inherited too, so the record's `cliSessionId` has to be this session's.
        Where the app keeps no such record, the session lives as its process."""
        if job := os.environ.get("CLAUDE_JOB_DIR"):
            record = read_json(Path(job) / "state.json")
            if record is None:
                raise Refused(
                    f"CLAUDE_JOB_DIR names no job record ({job}/state.json); "
                    "leaf takes a background job's lifetime from it"
                )
            if record["sessionId"] == self.session:
                return {"job": str(Path(job).resolve())}
        if (
            (host := os.environ.get("CLAUDE_CODE_HOST_SESSION_ID"))
            and (path := desktop_session_record(host))
            and read_json(path)["cliSessionId"] == self.session
        ):
            return {"app": str(path)}
        return {"pid": int(os.environ["CLAUDE_PID"])}

    @classmethod
    def process_pid(cls) -> int | None:
        return int(pid) if (pid := os.environ.get("CLAUDE_PID")) else None

    @classmethod
    def hook_payload(cls, payload: dict) -> dict:
        """Claude Code names the turn by its prompt, `prompt_id`, in every hook but
        SessionStart, and a prompt Escape dropped is submitted again under a new one
        (measured at 2.1.310), so a handover into a dropped prompt belongs to a turn
        that never ran. Releases before 2.1.196 send no `prompt_id` (found in each
        npm release's hook input), so their turns are Leaf's, and a resubmitted
        prompt renews the dropped one's; receipt then stops short of its handover
        (`delivery.confirm_entered`), which is input again once the turn ends."""
        prompt = payload.get("prompt_id")
        return {**payload, "turn_id": prompt} if prompt else payload

    def reconcile_turn(self, payload: dict, expected: dict | None) -> dict | None:
        """Claude Code runs some turns under a prompt no prompt hook named: a prompt
        the user types while a turn runs gets its prompt hook at once, under the
        running turn's `prompt_id`, and when Escape then ends that turn Claude Code
        submits the typed prompt as a turn of its own under a new one (measured at
        2.1.310). Nor does a claim's new lifetime know Claude Code's turn. Claude
        Code runs a session's hooks in order, so a step naming a prompt the record
        does not hold is that turn starting, never a late callback, and it opens
        it."""
        turn = payload.get("turn_id")
        if (
            not turn
            or payload.get("hook_event_name") == "UserPromptSubmit"
            or (expected is not None and expected["turn"] == turn)
        ):
            return expected
        from .state import advance_turn, flocked, session_lock_path, session_record

        with flocked(session_lock_path(self.session)):
            record = session_record(self.session)
            if record is None or record["ended"] is not None or record["turn"] == turn:
                return record
            return advance_turn(self.session, turn, running=True)

    def entered_context(self, payload: dict) -> set[str]:
        """What the session's transcript, which every hook's payload names, shows
        entered the model's context (`claude_code_entered`)."""
        path = payload.get("transcript_path")
        return claude_code_entered(Path(path)) if path else set()

    def escape_sandbox(self) -> None:
        """Leaf's bridge (`bridge.py`), which Claude Code's network proxy reaches."""
        from .bridge import ensure

        ensure(self.session, self.lifetime())

    @classmethod
    def from_claim(cls, claim: dict) -> ClaudeCodeHarness:
        return cls(session=claim["id"], agent=claim["agent"], job=claim.get("job"))

    def watches_between_turns(self) -> bool:
        """Claude Code keeps an `asyncRewake` hook in the background and wakes the
        session when it exits 2, except under plain `--print`, where it waits on
        the hook as on any other and the turn would hold until input came
        (measured at 2.1.286). A print session fed `--input-format stream-json`
        backgrounds it like an interactive one; `--output-format stream-json`
        alone does not. Only the process's own argv tells the two apart: the
        hook's input and environment are the same."""
        argv = process_argv(int(os.environ["CLAUDE_PID"])) or []
        printing = "-p" in argv or "--print" in argv
        streaming = "--input-format=stream-json" in argv or (
            ("--input-format", "stream-json") in itertools.pairwise(argv)
        )
        return not printing or streaming

    def process_runs(self) -> bool:
        """The process the hook ran under is CLAUDE_PID. A background job's daemon
        retires the job's worker about an hour after it goes idle whether or not a
        hook runs, and the hook outlives it (measured at 2.1.286: retired at 61
        minutes, the hook still running)."""
        return pid_alive(int(os.environ["CLAUDE_PID"]))

    def input_unpicked(self, page_dir: Path, *, listening: bool) -> str:
        return "Leaf's hook puts them in your context at your next turn."

    def live_turn(self) -> dict | None:
        """The session's live status (`claude_code_live_turn`) in the registry
        listing (`claude_code_session_records`)."""
        return claude_code_live_turn(claude_code_session_records(self.session))

    def session_name(self) -> str | None:
        """The `name` of the session's current registry record
        (`claude_code_current_record`): Claude Code's own after the first prompt,
        or the user's after `/rename`."""
        name = claude_code_current_record(
            claude_code_session_records(self.session)
        ).get("name")
        return name if isinstance(name, str) and name else None

    def inference_generator(self) -> Callable[..., dict]:
        from leaf.inference import claude_code_generate

        return claude_code_generate

    def nudge(self, page_dir: Path) -> bool:
        """The session's socket, or, for a background job no worker hosts, the job
        itself, resumed with the message as its prompt."""
        text = f"leaf: {page_dir} {NUDGE_WORDS}"
        return message_claude_code_session(self.session, text) or (
            self.job is not None and resume_claude_code_job(self.session, text)
        )

    def input_wakes(self) -> bool:
        """A live session takes the nudge through its socket as a turn where its
        settings accept other sessions' messages (`claude_code_accepts_peers`);
        otherwise it may hold the message behind a dialog or let it expire
        (`message_claude_code_session`), so it promises nothing. A background job no
        worker hosts is resumed with the input as its prompt
        (`resume_claude_code_job`)."""
        if claude_code_worker_runs(self.session):
            return any(
                pid_alive(record["pid"])
                and claude_code_accepts_peers(record.get("cwd"))
                for record, _address, _token in claude_code_peers(self.session)
            )
        return self.job is not None


# One phrase, because the two remedies below name the same recovery: a `leaf
# wait` already running in the task's shell tool, which the model reads by
# writing to that session rather than by starting a second watcher.
_POLL_UNIFIED_EXEC = (
    "the existing shell session running `leaf wait`, alone or after "
    "`leaf delivery ack`, with `write_stdin`"
)


class CodexHarness(EnvironmentHarness):
    """Codex: one detached adapter carries every page the task holds, over
    `codex queue` or, when Leaf can reach the task's App Server, that server.

    LEAF_SESSION_ID outranks CODEX_THREAD_ID because a worker Codex launches
    with an id of its own means that id, and the thread it happens to run under
    is not it."""

    name = "codex"
    default_agent = "Codex"
    session_variables = ("LEAF_SESSION_ID", "CODEX_THREAD_ID")
    identity_variables = session_variables
    # Codex 0.160.0 spills hook context above 2,500 approximate tokens, counted as
    # ceil(UTF-8 bytes / 4), Stop continuations included, and the preview it
    # shows instead is incomplete JSON.
    # https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/hooks/src/output_spill.rs
    # https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/utils/string/src/truncate.rs
    hook_context_bytes = 10_000

    @classmethod
    def process_pid(cls) -> int | None:
        """The nearest ancestor running the `codex` program (`lifetime`)."""
        return next((pid for pid, program in ancestry() if program == "codex"), None)

    def inference_generator(self) -> Callable[..., dict]:
        from leaf.inference import codex_generate

        return codex_generate

    def session_name(self) -> str | None:
        """The thread's name in Codex's session index (`codex_thread_names`)."""
        return codex_thread_names().get(self.session)

    def ensure_delivery(self) -> None:
        with self.preparing_delivery():
            pass

    @contextmanager
    def preparing_delivery(self):
        from .codex_adapter import preparing_adapter

        # A model wait already selected by this task remains its watcher.
        if wait_is_live(None, self.session) and not adapter_is_live(self.session):
            yield
            return
        with preparing_adapter(self):
            yield

    def lifetime(self) -> dict:
        """CLI sessions live with their nearest Codex ancestor, not the shell
        running a tool command, which can exit before the session does.

        Desktop chats share an App Server process and its writer locks, so neither
        identifies one chat's lifetime. Its native transcript, validated by hooks
        and published in the session record, survives idle instance unloading.
        Archive moves that file and delete removes it. Starting a desktop page
        requires that validated source to exist."""
        if (pid := self.process_pid()) is not None:
            if "app-server" in (process_argv(pid) or []):
                from .state import chat_exists, session_record

                if not chat_exists(session_record(self.session)):
                    raise Refused(
                        "Leaf cannot establish this desktop Codex chat's lifetime: "
                        "its validated native transcript is unavailable. Run a new "
                        "prompt with Leaf's Codex hooks enabled, then retry."
                    )
                return {"chat": True}
            return {"pid": pid}
        # Nothing to fall back to: any pid guessed here is a claim that expires
        # on its own, and the states that follow from one are silent.
        # LEAF_SESSION_ID with no codex above it is a hand-built environment, so
        # say what was walked.
        chain = " → ".join(program for _, program in ancestry())
        raise Refused(
            "LEAF_SESSION_ID names a Codex session but no codex process runs "
            f"above this one ({chain}); leaf takes the session's lifetime from it"
        )

    def turn_takes_input(self) -> bool:
        """Codex's tool hook offers input between steps (`codex.offer_hook_delivery`),
        and its Stop hook keeps the turn going over input nothing else will carry.
        Any Leaf hook run in this task instance, such as the turn's prompt hook,
        proves Codex runs them, so a turn takes input from its start; the queue
        adapter leaves such a turn's input to it (`codex_adapter`)."""
        return hooks_ran(self.session)

    def later_turn_takes_input(self) -> bool:
        """An adapter that starts turns over App Server opens one on a
        `leaf_delivery` tool output, which adds no message to the user's
        conversation. Through `codex queue` the turn opens on a `leaf-delivery`
        pointer that Codex shows as a message from the user, which is noisier than
        the one more message the ending turn writes, so there Stop hands the input
        into the ending turn.

        An adapter takes its lease before it writes its transport there, and holds
        the start lock across that, so the record is read under the start lock."""
        if not adapter_is_live(self.session):
            return False
        from .codex_adapter import adapter_start_lock_path, running_adapter
        from .state import flocked

        with flocked(adapter_start_lock_path(self.session)):
            adapter = running_adapter(self.session)
        return adapter is not None and adapter["app_server"] is not None

    def receive_pointer(self, payload: dict) -> list[Path]:
        from .codex_state import confirm_codex_pointer

        return confirm_codex_pointer(self.session, payload)

    def watcher_live(self, *, listening: bool) -> bool:
        """A wait lease says only that some process can read page events. The
        adapter's second lease is the narrower fact this watcher rests on: that
        the process can durably hand those events to a turn after this one
        ends."""
        return listening and adapter_is_live(self.session)

    def input_unpicked(self, page_dir: Path, *, listening: bool) -> str:
        if listening:
            return f"Poll {_POLL_UNIFIED_EXEC}."
        return (
            f"Start `leaf page claim {page_dir}` so later updates reach this "
            "task in new turns."
        )

    @classmethod
    def hook_context(cls, event: str, message: str) -> dict:
        """Codex's Stop output schema (0.156) has no `hookSpecificOutput`, so its
        Stop hook keeps the turn going the one way it has: a block."""
        if event == "Stop":
            return {"decision": "block", "reason": message}
        return super().hook_context(event, message)

    def reconcile_turn(self, payload: dict, expected: dict | None) -> dict | None:
        """Codex's native transcript also records turns resumed without input,
        which run no prompt hook (`codex_state.sync_transcript_turn`)."""
        from .codex_state import sync_transcript_turn

        return sync_transcript_turn(self.session, payload.get("transcript_path"))

    def offer_at_step(
        self, event: str, payload: dict, expected: dict | None
    ) -> tuple[str | None, dict | None]:
        """Both the tool hook and Stop offer an envelope through Codex's one transport
        reservation (`codex.offer_hook_delivery`), since empty-input resume can
        reach Stop without running another tool. Stop offers only where no adapter
        will start a turn of its own for the input over App Server
        (`later_turn_takes_input`), and the turn would continue for it
        (`hook_transport.stop_continues`). The tool hook offers only input the
        cursor has not passed, and Stop also an update the session holds no usable
        reference for (`delivery.deliverable`). The tool hook also carries the
        reminder of a status line left standing (`hook_transport.status_reminders`).
        """
        if event not in {"PostToolUse", "Stop"} or not payload.get("turn_id"):
            return None, expected
        from .service import owned_pages

        if not owned_pages(self.session):
            return None, expected
        if event == "Stop":
            if self.later_turn_takes_input():
                return None, expected
            from .hook_transport import read_plans, stop_continues

            plans = read_plans(self.session)
            if not stop_continues(
                plans,
                [plan.batch for plan in plans if plan.batch],
                repeated=bool(payload.get("stop_hook_active")),
                reminds=self.watches_between_turns(),
            ):
                return None, expected
        from .codex import offer_hook_delivery
        from .state import status_check_due

        prompt, expected = offer_hook_delivery(
            self.session, expected, received=event == "Stop"
        )
        if event == "PostToolUse" and status_check_due(self.session):
            from .hook_transport import read_plans, status_reminders

            renewals = status_reminders(self.session, read_plans(self.session))
            prompt = "\n".join(filter(None, [prompt, *renewals])) or None
        return prompt, expected

    @classmethod
    def run_ack(cls, command: str) -> str:
        """A Codex task's own wait lives in unified exec, the same session a
        watcher task or a direct loop polls."""
        return f"run `{command}` in unified exec and poll it with `write_stdin`"

    def nothing_listening(self, page_dir: Path, *, listening: bool) -> str:
        if listening:
            return (
                "the Codex page is still live. Keep this turn active and poll "
                f"{_POLL_UNIFIED_EXEC}."
            )
        return (
            f"no delivery adapter. Start `leaf page claim {page_dir}` so this "
            "turn can finish and later updates start new turns; or run `leaf "
            "page close <page>` if the page is done."
        )


class PiHarness(EnvironmentHarness):
    """Pi (<https://pi.dev>): Leaf's extension (`hooks/pi.ts`) runs inside the Pi
    process and runs the watch and the hooks, the way Claude Code does. A highly
    experimental trial.

    Pi states the session in every shell-tool command as PI_SESSION_ID, and
    states no process. The extension exports its own, Pi's, as LEAF_PI_PID,
    since an extension's `process.env` reaches the shell tool's commands
    (measured at Pi 1.0.2); the process walk would find a `node` whose
    command line Pi has overwritten with its title.

    The extension calls the prompt hook as a user's prompt starts a run, the
    Stop hook as a run is about to settle (`agent_before_settle`, whose
    `continue` keeps it going). As the session starts and as each run settles
    it starts the watch (`leaf hook --harness pi --watch`), with the Interrupt
    payload, which closes the turn, after a run that settles without going on
    from there, which is what an Escape does. When the watch wakes an idle
    session, it sends a notification that starts a run, and the prompt hook
    completes that run's accepted message before its first model request. When
    it wakes during a run, the run's next turn end calls the prompt hook and
    adds its context to the session."""

    name = "pi"
    default_agent = "Pi"
    session_variables = ("PI_SESSION_ID",)
    identity_variables = (*session_variables, "LEAF_PI_PID")
    hook_delivers = True
    # The extension adds a hook's whole context to the session as text, at any
    # size, so `hook_context_bytes` stays None.

    @classmethod
    def process_pid(cls) -> int | None:
        return int(pid) if (pid := os.environ.get("LEAF_PI_PID")) else None

    def lifetime(self) -> dict:
        if (pid := self.process_pid()) is None:
            raise Refused(
                "PI_SESSION_ID names a Pi session but LEAF_PI_PID is unset: Leaf's "
                "Pi extension (hooks/pi.ts) is not loaded in it"
            )
        return {"pid": pid}

    def watches_between_turns(self) -> bool:
        """The extension starts the watch only in a Pi that can start a run, the
        TUI or RPC mode, and says so as LEAF_PI_WATCH. Under `--print` the
        session ends with its run, so the Stop hook hands input that arrives as
        the run ends into it."""
        return os.environ.get("LEAF_PI_WATCH") == "1"

    def process_runs(self) -> bool:
        return pid_alive(int(os.environ["LEAF_PI_PID"]))

    def inference_generator(self) -> Callable[..., dict]:
        from leaf.inference import pi_generate

        return pi_generate

    def input_unpicked(self, page_dir: Path, *, listening: bool) -> str:
        return "Leaf's Pi extension puts them in your context at your next turn."


@dataclass(frozen=True)
class EmbeddedHarness(Harness):
    """A harness that drives Codex App Server in its own process and starts the
    turns itself — the shape <https://leaf.page/> runs in its per-user
    container.

    No environment implies this one: such a harness knows what it is and declares
    itself, supplying its own display name and the App Server process its
    session lives and dies with.

    The host owns turn pickup and observes completion directly. It installs the
    ordinary Leaf plugin for the agent's skills and tools; its remedies describe
    host-owned delivery rather than asking the agent to start another watcher."""

    pid: int

    name = "embedded"

    @classmethod
    def from_claim(cls, claim: dict) -> EmbeddedHarness:
        return cls(session=claim["id"], agent=claim["agent"], pid=claim["pid"])

    def lifetime(self) -> dict:
        return {"pid": self.pid}

    def input_unpicked(self, page_dir: Path, *, listening: bool) -> str:
        return "The harness holding this page starts its own turn for new input."

    def nothing_listening(self, page_dir: Path, *, listening: bool) -> str:
        return "no embedded harness is holding this page."


# The harnesses an environment can imply, in the order that breaks a tie in
# `session_harness`, and every harness a claim can name.
_ENVIRONMENT_HARNESSES: tuple[type[EnvironmentHarness], ...] = (
    ClaudeCodeHarness,
    CodexHarness,
    PiHarness,
)
# The harnesses whose hooks Leaf registers, by the name a registration passes
# (`hook_harness`).
HOOK_HARNESSES = {harness.name: harness for harness in _ENVIRONMENT_HARNESSES}
HARNESSES: dict[str, type[Harness]] = {
    harness.name: harness for harness in (*_ENVIRONMENT_HARNESSES, EmbeddedHarness)
}
# The display name a launch gives its session, whichever harness it runs under.
AGENT_VARIABLE = "LEAF_AGENT"
# Every variable that makes a process a harness session: each harness's identity and
# the display name. A process that must not act as the session it was started from
# scrubs the set: a build that publishes pages (`leaf-dev site`), an eval's child
# (`dev/leaf_dev/arms.py`), the test suite (`tests/conftest.py`).
IDENTITY_VARIABLES = (
    *(
        variable
        for harness in _ENVIRONMENT_HARNESSES
        for variable in harness.identity_variables
    ),
    AGENT_VARIABLE,
)


def session_harness() -> Harness | None:
    """The harness running this command, or None outside an agent harness.

    Each harness states its session id in a variable of its own, and LEAF_SESSION_ID
    is the door a launch opens to name a Codex session Codex did not start. The
    display name is LEAF_AGENT where the launch set one — naming a worker in its
    environment needs no cooperation from the agent, so every command it runs
    speaks as that voice — and the harness's own default otherwise. The name is
    a display choice and nothing may dispatch on it, which is why the harness is
    a separate fact. What outlives the command is `Harness.lifetime`'s to find.

    A command inherits the identity of every harness above it: Pi run from a Claude
    Code shell, or Claude Code from Pi's, states both sessions. The harness running
    the command is the nearest one, so where more than one is implied they are
    ranked by how far above this process each one's `process_pid` runs, and the
    order below breaks a tie."""
    implied = [
        (harness, session)
        for harness in _ENVIRONMENT_HARNESSES
        if (
            session := next(
                filter(None, map(os.environ.get, harness.session_variables)), None
            )
        )
    ]
    if len(implied) > 1:
        depth = {pid: index for index, (pid, _) in enumerate(ancestry())}
        implied.sort(key=lambda pair: depth.get(pair[0].process_pid(), len(depth)))
    if not implied:
        return None
    harness, session = implied[0]
    return harness(
        session=session,
        agent=os.environ.get(AGENT_VARIABLE) or harness.default_agent,
    )


def hook_harness(name: str, session: str) -> EnvironmentHarness:
    """The harness a hook registration names, for the session its payload names.

    A hook's environment is no evidence of its harness: Codex states no thread
    to its hooks, and a hook inherits the variables of every harness above its
    own, so a Codex task started from a Claude Code shell carries that session's
    identity. So each harness registers its own hooks, each passing its name:
    `hooks/hooks.json` for Claude Code, `hooks/codex.json`, which Codex's
    manifest names in place of that default, and the Pi extension `hooks/pi.ts`."""
    harness = HOOK_HARNESSES[name]
    return harness(
        session=session,
        agent=os.environ.get(AGENT_VARIABLE) or harness.default_agent,
    )


def detached_environment(harness: Harness | None) -> dict[str, str]:
    """The environment for a process this one detaches on behalf of `harness`: its
    own, less the identity of every other harness.

    A detached process leaves the harnesses above this one behind, so it could not
    rank them by process again, and the tie order would choose for it: a server a
    Codex task under Claude Code starts would serve as the Claude Code session.
    Nor could a hook's child, whose environment never named its harness. So the
    starter settles the harness, the child inherits only that one's identity, and
    a child that acts for it is handed it whole (`harness_argument`)."""
    others = {
        variable
        for implied in _ENVIRONMENT_HARNESSES
        if not isinstance(harness, implied)
        for variable in implied.identity_variables
    }
    return {name: value for name, value in os.environ.items() if name not in others}


def harness_argument(harness: Harness | None) -> str:
    """`harness` as a detached child's argument, which `harness_from_argument`
    rebuilds, so the child acts for the harness its starter settled rather than
    one its environment implies."""
    return json.dumps(
        None if harness is None else {"name": harness.name, **asdict(harness)}
    )


def harness_from_argument(argument: str) -> Harness | None:
    record = json.loads(argument)
    return None if record is None else HARNESSES[record.pop("name")](**record)


def claim_harness(claim: dict) -> Harness:
    """The claimant's harness, rebuilt from the claim record.

    A page server, the append door and the Stop hook all run in processes that
    need not be the claimant's, so they read the harness the claim names instead
    of the one their own environment implies."""
    return HARNESSES[claim["harness"]].from_claim(claim)


def message_identity() -> dict:
    """The voice an agent-authored event carries: the posting session's display
    name and session id, read from its own environment rather than the page's
    claim record — the claimant is whoever watches the page, and on a page
    several sessions report to, that is usually not the poster. Empty outside a
    harness session: the users' generic label covers an event with no voice, and
    a stored placeholder would only impersonate a name."""
    harness = session_harness()
    if harness is None:
        return {}
    return {"agent": harness.agent, "session": harness.session}


def claude_code_entered(transcript: Path) -> set[str]:
    """The ids of the inputs Leaf's hooks handed inline into a Claude Code session,
    read from the session's transcript at `transcript`.

    Claude Code writes a `hook_additional_context` record once a hook's output joins
    the conversation, and none for a prompt Escape dropped with its hooks' output;
    Escape during a tool boundary's hooks keeps that boundary's context and its
    record (measured at 2.1.310). So the record, not a later hook running, says the
    model read a handover. A missing or unreadable transcript shows nothing.

    Every hook of a session holding a page reads it, and a long session's
    transcript runs to hundreds of MB, so this maps the file and parses only the
    lines holding Leaf's opening: 34 ms on a 200 MB transcript, where reading and
    splitting it took 105 ms and 500 MB of memory."""
    from .hook_transport import INLINE_OPENING

    marker = INLINE_OPENING.encode()
    lines = []
    try:
        with (
            transcript.open("rb") as file,
            mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as mapped,
        ):
            at = 0
            while (hit := mapped.find(marker, at)) != -1:
                start = mapped.rfind(b"\n", 0, hit) + 1
                end = mapped.find(b"\n", hit)
                end = len(mapped) if end == -1 else end
                lines.append(mapped[start:end])
                at = end
    except (OSError, ValueError):
        # mmap refuses an empty file with ValueError.
        return set()
    entered = set()
    for line in lines:
        if b'"hook_additional_context"' not in line:
            continue
        try:
            attachment = json.loads(line).get("attachment") or {}
        except ValueError:
            continue
        for content in attachment.get("content") or []:
            opening, _, rest = content.partition("\n")
            if opening != INLINE_OPENING:
                continue
            try:
                delivery = json.loads(rest.partition("\n")[0])
            except ValueError:
                continue
            entered.update(
                event["id"]
                for batch in delivery["batches"]
                for event in batch["events"]
            )
    return entered


def claude_code_config() -> Path:
    """Claude Code's configuration directory."""
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def claude_code_sessions() -> Path:
    """Claude Code's session registry: one `<pid>.json` per running session."""
    return claude_code_config() / "sessions"


def claude_code_accepts_peers(cwd: str | None) -> bool:
    """Whether Claude Code's settings for a session started in `cwd` deliver another
    process's message straight into it (`crossSessionInbound: accept`) rather than
    holding it behind a dialog, as they do in a session that bypasses permissions.

    In 2.1.310 only the user's settings grant `accept`, while a project's settings,
    which it finds from the session's directory up to its repository's root, can
    narrow it to `hold` or `refuse`. So the user's file has to say `accept`, and any
    other value in a project file on that path reads as no. Managed policy and
    `--settings` aren't read. Each file is another program's, so one caught
    mid-write reads as no."""
    if _claude_code_inbound(claude_code_config() / "settings.json") != "accept":
        return False
    directory = Path(cwd) if cwd else None
    while directory is not None and directory != Path.home():
        for name in ("settings.json", "settings.local.json"):
            if _claude_code_inbound(directory / ".claude" / name) not in (
                None,
                "accept",
            ):
                return False
        repository = (directory / ".git").exists()
        directory = (
            None if repository or directory == directory.parent else directory.parent
        )
    return True


def _claude_code_inbound(path: Path):
    """The `crossSessionInbound` a settings file sets: None where the file or the
    key is absent, and `False` where the file can't be read whole."""
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return False
    return settings.get("crossSessionInbound") if isinstance(settings, dict) else False


def claude_code_peers(session_id: str) -> list[tuple[dict, str, str]]:
    """The session's registry records a message can be addressed to, each with its
    socket and the `peerToken` its 0600 `<pid>.<hash>.key` holds. Each record and
    key is another program's live file, so one that vanished, was caught
    mid-write or lacks a field this reads is left out."""
    sessions = claude_code_sessions()
    peers = []
    for record in claude_code_session_records(session_id):
        try:
            key_path = next(sessions.glob(f"{record['pid']}.*.key"))
            token = json.loads(key_path.read_text(encoding="utf-8"))["peerToken"]
            peers.append((record, record["messagingSocketPath"], token))
        except (OSError, ValueError, KeyError, TypeError, StopIteration):
            continue
    return peers


def claude_code_current_record(records: list[dict]) -> dict:
    """The newest of a session's registry `records` whose process still runs, or
    `{}` where none does: a worker that died without removing its record leaves a
    second one beside the live worker's."""
    stamped = [
        record
        for record in records
        if isinstance(record.get("statusUpdatedAt"), int | float)
        and isinstance(record.get("pid"), int)
        and pid_alive(record["pid"])
    ]
    return max(stamped, key=lambda item: item["statusUpdatedAt"], default={})


def claude_code_live_turn(records: list[dict]) -> dict | None:
    """A session's live status from its current registry record
    (`claude_code_current_record`): `waiting` while a turn holds a dialog open (a
    permission prompt, a question), `idle` once no turn runs (`shell` too, which
    is idle with a background command running), and `busy` otherwise.

    Its `idle` is the one reading of a turn's end that an interrupt moves: Escape
    ends a turn without running the Stop hook, and the record turns `idle` at that
    moment (measured at Claude Code 2.1.283). `busy` is weaker: a background job's
    record stays `busy` across turn endings while its background work runs, so it
    does not prove a turn is running; after a turn ends, it says work continues
    (`activity.Turn.background`). The record belongs to the worker hosting the
    session's current sitting, so a background job whose worker has retired has
    none."""
    record = claude_code_current_record(records)
    state = {"busy": "busy", "waiting": "waiting", "idle": "idle", "shell": "idle"}
    if record.get("status") not in state:
        return None
    return {
        "state": state[record["status"]],
        "since": datetime.fromtimestamp(record["statusUpdatedAt"] / 1000)
        .astimezone()
        .isoformat(),
    }


def claude_code_session_records(session_id: str) -> list[dict]:
    """The registry records Claude Code publishes for a session, found by id.

    A session is found by id each time rather than written into the claim,
    because a background job's worker pid, and the record with it, changes over
    the job's life; a worker that died without removing its record leaves a
    second one.

    Every state read asks this of each claimed page, so the registry listing
    (`claude_code_registry`) is reused for at most `REGISTRY_READ_S` while the
    directory's own stamp holds, well inside the presence cache's interval. A
    record added or removed moves the stamp at once. Claude Code rewrites a
    record's status in place, which leaves the stamp alone (measured at 2.1.309),
    so a status read here can be up to `REGISTRY_READ_S` old. The listing is the
    machine's rather than a page's, so the process keeps the last one, replaced
    whole."""
    sessions = claude_code_sessions()
    try:
        stamp = sessions.stat().st_mtime_ns
    except OSError:
        return []
    records = _registry_listing.get(
        (sessions, stamp, time.monotonic() // REGISTRY_READ_S),
        claude_code_registry,
    )
    return [record for record in records if record.get("sessionId") == session_id]


REGISTRY_READ_S = 1.0
# The machine's registry listing; one time bucket bounds in-place record staleness.
_registry_listing = Slot()


def claude_code_registry() -> list[dict]:
    """Every record in Claude Code's session registry, read now.

    Each session writes `sessions/<pid>.json` in its config directory, carrying
    `sessionId`, `pid`, its live `status` and when it last changed
    (`statusUpdatedAt`, epoch milliseconds), and `messagingSocketPath`. Each
    record is another program's live file, and a session can exit between
    listing and reading it, so a file that vanished or was caught mid-write is
    passed over."""
    records = []
    for record_path in claude_code_sessions().glob("*.json"):
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def codex_thread_names() -> dict[str, str]:
    """Each thread's latest name in Codex's session index,
    `$CODEX_HOME/session_index.jsonl`, by thread id.

    Codex appends a line `{"id", "thread_name", "updated_at"}` each time it names
    or renames a thread, so the last line for an id holds its current name. The
    index is the machine's and every state read of a Codex page asks it, so the
    process keeps the last reading until the file's stamp moves."""
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    index = home / "session_index.jsonl"
    try:
        stat = index.stat()
    except OSError:
        return {}
    return _codex_names.get(
        (index, stat.st_mtime_ns, stat.st_size), lambda: _read_thread_names(index)
    )


# The machine's Codex thread names, keyed by the index's path and stamp.
_codex_names = Slot()


def _read_thread_names(index: Path) -> dict[str, str]:
    """The index's names, later lines replacing earlier ones; a line caught
    mid-append, or one of another shape, is passed over."""
    names = {}
    try:
        lines = index.read_text(encoding="utf-8").splitlines()
    except OSError:
        return names
    for line in lines:
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if (
            isinstance(entry, dict)
            and isinstance(entry.get("id"), str)
            and isinstance(name := entry.get("thread_name"), str)
            and name
        ):
            names[entry["id"]] = name
    return names


def desktop_session_record(host_session: str) -> Path | None:
    """The Claude desktop app's record of the session it calls `host_session`
    (`local_<uuid>`), filed under the signed-in account and organization, or
    None where the app keeps none. It holds the session's `cliSessionId` and
    `isArchived`, which removing the session from the app's sidebar sets while
    the record stays (measured at app 3.6556.1)."""
    sessions = Path.home() / "Library/Application Support/Claude/claude-code-sessions"
    return next(sessions.glob(f"*/*/{host_session}.json"), None)


def resume_claude_code_job(session_id: str, text: str) -> bool:
    """Wake a background job whose worker has retired, with `text` as its next
    prompt, and say whether Claude Code took it.

    The daemon retires an idle job's worker after about an hour, and its socket
    goes with it. `claude --bg --resume <session> <prompt>` claims a fresh worker
    for the same job and session, with the options the job was started with, and
    runs the prompt there, which fires its prompt hook (measured at 2.1.286). With
    a worker still running, the same command would start a copy, so a job any live
    worker hosts is left alone.

    The command is started and not awaited: it takes about a second, the nudge
    runs under the page's lock, and the turn it starts takes that lock in its
    prompt hook. So True means only that it started, as a socket taking the frames
    is all `message_claude_code_session` can say."""
    if claude_code_worker_runs(session_id):
        return False
    import subprocess

    try:
        subprocess.Popen(
            ["claude", "--bg", "--resume", session_id, text],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return False
    return True


def claude_code_worker_runs(session_id: str) -> bool:
    """Whether a live process hosts the session: a registry record whose pid runs."""
    return any(
        isinstance(record.get("pid"), int) and pid_alive(record["pid"])
        for record in claude_code_session_records(session_id)
    )


def message_claude_code_session(session_id: str, text: str) -> bool:
    """Put `text` into a Claude Code session as a user message, through the
    messaging socket every session binds, and say whether a socket took it.

    Each of the session's peers (`claude_code_peers`) names a socket and the token
    it authenticates. The socket reads newline JSON and answers nothing: an auth
    line, then a user frame whose `session_id` makes a socket that has since passed
    to another session drop it.

    The recipient decides delivery. Measured on Claude Code 2.1.274: a session
    in a prompting permission mode queues the text as a user turn, which wakes
    it when idle and fires its UserPromptSubmit hook with the text as the
    prompt. A session that bypasses permissions holds a message from any process
    outside its own process tree behind a deliver-or-deny dialog, unless its
    user set `crossSessionInbound` to `accept`, and a headless session lets the
    held message expire. The server `leaf server start` spawns runs in a process
    session of its own, so it is outside that tree. Nothing reports the outcome
    to the sender, so True means only that a listening socket took the frames.
    A session can exit between reading its record and connecting, so a socket
    nobody listens on is skipped."""
    import socket

    for _record, address, token in claude_code_peers(session_id):
        frames = (
            {"type": "auth", "token": token},
            {
                "type": "user",
                "session_id": session_id,
                "message": {"role": "user", "content": text},
            },
        )
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
                peer.settimeout(1)
                peer.connect(address)
                peer.sendall("".join(json.dumps(f) + "\n" for f in frames).encode())
        except (OSError, TypeError):
            continue
        return True
    return False
