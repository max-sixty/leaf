"""The agent harnesses Leaf runs under, and the Claude Code messaging socket
behind one of them.

A harness is the program an agent session runs in, such as Claude Code or Codex, as
Leaf meets it. `Harness` collects everything that
differs between them — session lifetime, delivery carrier, the hook's remedies,
the way to reach a session with nothing watching — so that every module below
this one dispatches on what a harness declares rather than on which harness it
is. `session_harness` reads the one running this command out of the
environment; `claim_harness` rebuilds the one a page's claim recorded.

The machine facts a harness rests on live elsewhere: `machine` reads the
processes running above this one, and `leases` holds the lease a detached
carrier proves itself with."""

import json
import os
import socket
import subprocess
import sys
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import ClassVar

from leaf.files import read_json
from leaf.leases import adapter_is_live, hooks_ran, wait_is_live
from leaf.machine import ancestry, pid_alive, process_argv


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

    What differs between harnesses is how a leaf's input reaches the session
    between its turns, and the methods below answer for that carrier:

    - Claude Code runs Leaf's Stop hooks as each turn ends: one watches the
      session's pages in the background and wakes the session when input arrives
      (`watches_between_turns`), and the prompt hook, which runs as the turn the
      wake opens begins, and the other Stop hook put the input in the turn's
      context for its reader to confirm (`hook_delivers`). A turn that ends without its Stop
      hooks, as an interrupt does, leaves nothing watching while the session lives
      on, which is why this is the harness with a `nudge`.
    - Pi runs Leaf's extension in its own process, which calls the same hooks at
      the same points of a run and starts the same watch as each run settles, and
      starts the turn the watch wakes itself.
    - Codex has a detached adapter that outlives the turn and proves itself by
      holding the adapter lease. It queues each delivery with `codex queue`, or
      starts its turn over the task's App Server when Leaf can reach one.
    - An embedded harness drives Codex App Server itself and starts the turns;
      nothing outside it carries input in.
    """

    session: str
    agent: str

    name: ClassVar[str]
    # Whether the harness's hooks can carry input into the turn: they freeze and
    # hand over the whole delivery, and `leaf wait` only wakes the session.
    # `hooks_carry` says whether they do for this session.
    hook_delivers: ClassVar[bool] = False

    @classmethod
    def from_claim(cls, claim: dict) -> "Harness":
        """Rebuild the claimant's harness from the record it wrote."""
        return cls(session=claim["id"], agent=claim["agent"])

    def lifetime(self) -> dict:
        """The claim fields naming what this session's lifetime is, which is what
        the claim records and its readers act on: a lifetime that has ended makes
        ownership inactive, and a session-managed server retires
        ORPHAN_GRACE_SECS after it (`stop_when_service_ends`). `claim_is_active`
        consumes these fields without knowing which harness wrote them."""
        raise NotImplementedError

    def carrier_live(self, *, listening: bool) -> bool:
        """Whether this session's carrier can still take the page's input into a
        turn — the Stop hook's watch question, and its reason to believe a draft
        reply will be committed.

        `listening` is the session's wait lease: some process is reading this
        page's events for it. That is the whole proof for a carrier that is one
        process holding one lease. Where the session's own hooks carry its input,
        the watch is started again as every turn ends, so the carrier stands
        across the turn as well as between turns. A carrier that has to prove
        more overrides this."""
        return listening or self.hooks_carry()

    def ensure_delivery(self) -> None:
        """Prepare this harness's input route before handing over a served page.

        Harnesses whose hooks or embedding own delivery need no separate process.
        A detached carrier starts or joins its task-wide watch here.
        """

    @contextmanager
    def preparing_delivery(self):
        """Prepare delivery and retain it until the caller publishes its page.

        Detached carriers prevent no-page retirement throughout this boundary.
        A failed preparation therefore precedes any page ownership transition.
        """
        self.ensure_delivery()
        yield

    def hooks_carry(self) -> bool:
        """Whether this session's hooks carry its input: its harness runs hooks that
        can, and one has run for this session. Until one has, `leaf wait` prints
        the delivery for its reader to confirm, so a session whose hooks never run
        still reads its input rather than being woken to an empty turn."""
        return self.hook_delivers and hooks_ran(self.session)

    def input_unpicked(self, page_dir: Path, *, listening: bool) -> str:
        """What to do about events past this page's cursor that nothing will
        carry."""
        raise NotImplementedError

    def nothing_listening(self, page_dir: Path, *, listening: bool) -> str:
        """What to do about a live page this session owes a watcher."""
        raise NotImplementedError

    def watches_between_turns(self) -> bool:
        """Whether this session's harness runs Leaf's watch as a Stop hook it keeps in
        the background, which wakes the session when input arrives
        (`session.watch_between_turns`); the model then starts no `leaf wait`."""
        return False

    def process_runs(self) -> bool:
        """Whether the harness process whose hook started this watch still runs. A
        watch it has orphaned can wake nobody, and would hold the session's lease
        over the input a `nudge` could still deliver."""
        return True

    @classmethod
    def run_ack(cls, delivery_id: str) -> str:
        """How the reader of this session's printed delivery runs the `leaf wait
        --ack` that confirms it and goes on waiting: the verb phrase the
        delivery's `acknowledge` ends with. Hook context names its separate
        `leaf delivery ack` route; a wait held in a background task is the default."""
        return f"start `leaf wait --ack {delivery_id}` as the next background task"

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

    def nudge(self, page_dir: Path) -> bool:
        """Put this page's new input in front of the session, and say whether
        anything took it.

        Only a carrier the session's own turns start stops between turns while
        its session stands, so only such a harness has anywhere to put this. A
        carrier that is a process of its own is either running, and needs no
        telling, or gone along with the session it served."""
        return False

    def title_generator(self) -> Callable[[str, Path], dict] | None:
        """How the page server names a thread a user opens on this session's page,
        as the comment is admitted (`thread_titles`), or None where it cannot.

        Only a harness whose model any process on the machine can ask has one. An App
        Server carrier names the thread instead, as it starts the turn answering
        it, since the page server cannot reach that server."""
        return None

    def live_turn(self) -> dict | None:
        """What the harness itself says about this session right now, or None where it
        says nothing a reader can take.

        `{"state": "busy" | "waiting" | "idle", "since": <iso>}`, dated by the
        harness's own last change: `idle` once no turn runs, `waiting` while a turn
        holds a dialog open in the session's own window. `activity.claimant_turn`
        weighs it by that date against the claim's turn stamps, which the hooks
        write and so cannot see a turn end that runs no hook."""
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
    identity_variables = (*session_variables, "CLAUDE_PID", "CLAUDE_JOB_DIR")
    # Claude Code runs the prompt hook on every turn a background task's end
    # opens, idle or mid-turn, and adds what it returns to that turn's context.
    hook_delivers = True

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
        is a process of its own."""
        if job := os.environ.get("CLAUDE_JOB_DIR"):
            record = read_json(Path(job) / "state.json")
            if record is None:
                sys.exit(
                    f"CLAUDE_JOB_DIR names no job record ({job}/state.json); "
                    "leaf takes a background job's lifetime from it"
                )
            if record["sessionId"] == self.session:
                return {"job": str(Path(job).resolve())}
        return {"pid": int(os.environ["CLAUDE_PID"])}

    @classmethod
    def process_pid(cls) -> int | None:
        return int(pid) if (pid := os.environ.get("CLAUDE_PID")) else None

    @classmethod
    def from_claim(cls, claim: dict) -> "ClaudeCodeHarness":
        return cls(session=claim["id"], agent=claim["agent"], job=claim.get("job"))

    def watches_between_turns(self) -> bool:
        """Claude Code keeps an `asyncRewake` hook in the background and wakes the
        session when it exits 2, except under plain `--print`, where it waits on
        the hook as on any other and the turn would hold until input came
        (measured at 2.1.286). A print session fed `--input-format stream-json`
        backgrounds it like an interactive one. Only the process's own argv
        tells the two apart: the hook's input and environment are the same."""
        argv = process_argv(int(os.environ["CLAUDE_PID"])) or []
        printing = "-p" in argv or "--print" in argv
        streaming = "stream-json" in argv or "--input-format=stream-json" in argv
        return not printing or streaming

    def process_runs(self) -> bool:
        """The process the hook ran under is CLAUDE_PID. A background job's daemon
        retires the job's worker about an hour after it goes idle whether or not a
        hook runs, and the hook outlives it (measured at 2.1.286: retired at 61
        minutes, the hook still running)."""
        return pid_alive(int(os.environ["CLAUDE_PID"]))

    def input_unpicked(self, page_dir: Path, *, listening: bool) -> str:
        return "Leaf's hook puts them in your context at your next turn."

    def nothing_listening(self, page_dir: Path, *, listening: bool) -> str:
        return (
            "no watcher: Leaf's Stop hook watches this session's pages between "
            "turns, and has not run for this session."
        )

    def live_turn(self) -> dict | None:
        """The session's live status in Claude Code's session registry
        (`claude_code_session_records`), from the newest record whose process
        still runs: `waiting` while a turn holds a dialog open (a permission
        prompt, a question), `idle` once no turn runs (`shell` too, which is idle
        with a background command running), and `busy` otherwise.

        Its `idle` is the one reading of a turn's end that an interrupt moves:
        Escape ends a turn without running the Stop hook, and the record turns
        `idle` at that moment (measured at Claude Code 2.1.283). `busy` is weaker:
        a background job's record stays `busy` across turn endings while its
        background work runs, so it does not prove a turn is running. The record
        belongs to the worker hosting the session's current sitting, so a
        background job whose worker has retired has none."""
        stamped = [
            record
            for record in claude_code_session_records(self.session)
            if isinstance(record.get("statusUpdatedAt"), int | float)
            and isinstance(record.get("pid"), int)
            and pid_alive(record["pid"])
        ]
        record = max(stamped, key=lambda item: item["statusUpdatedAt"], default={})
        state = {"busy": "busy", "waiting": "waiting", "idle": "idle", "shell": "idle"}
        if record.get("status") not in state:
            return None
        return {
            "state": state[record["status"]],
            "since": datetime.fromtimestamp(record["statusUpdatedAt"] / 1000)
            .astimezone()
            .isoformat(),
        }

    def title_generator(self) -> Callable[[str, Path], dict]:
        from leaf.thread_titles import claude_code_title

        return claude_code_title

    def nudge(self, page_dir: Path) -> bool:
        """The session's socket, or, for a background job no worker hosts, the job
        itself, resumed with the message as its prompt."""
        text = f"leaf: {page_dir} has new input, which arrives with this message."
        return message_claude_code_session(self.session, text) or (
            self.job is not None and resume_claude_code_job(self.session, text)
        )


# One phrase, because the two remedies below name the same recovery: a `leaf
# wait` already running in the task's shell tool, which the model reads by
# writing to that session rather than by starting a second watcher.
_POLL_UNIFIED_EXEC = (
    "the existing shell session — `leaf wait` before the first batch or "
    "the rearmed `leaf wait --ack` afterward — with `write_stdin`"
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

    @classmethod
    def process_pid(cls) -> int | None:
        """The nearest ancestor running the `codex` program (`lifetime`)."""
        return next((pid for pid, program in ancestry() if program == "codex"), None)

    def ensure_delivery(self) -> None:
        with self.preparing_delivery():
            pass

    @contextmanager
    def preparing_delivery(self):
        from .codex_adapter import preparing_adapter

        # A direct wait already selected by this task remains its carrier.
        if wait_is_live(None, self.session) and not adapter_is_live(self.session):
            yield
            return
        with preparing_adapter():
            yield

    def lifetime(self) -> dict:
        """Codex states no process, so this one is discovered: the nearest
        ancestor running the `codex` program.

        The launcher cannot hand it over, because a shell tool's $PPID is a fact
        about the *shape* of the command rather than about the session. Measured
        through `codex exec` at 0.147.0: a bare command, an `&&` chain and a
        `bash -lc` all reported the codex process, because the shell it wraps
        them in can exec a last simple command in place; `leaf … | cat` reported
        the wrapping shell itself, which exits with the pipeline. Recording that
        one would have taken the page's server down a second after the command
        that started it, and the page would have told its user no session
        holds it while the session sat there working.

        Codex has a second shape with no session process at all. The ChatGPT app
        runs one `codex ... app-server` per app launch and multiplexes every
        conversation through it: its children are node, uv and zsh, never a
        per-conversation `codex`. The ancestry walk still reaches that process,
        so recording its pid gave every session in the app one shared lifetime,
        and one that ends only when the app quits — measured on a machine with
        133 claims naming a single app-server pid and 49 session-managed servers
        that could never retire. Nothing else there is per-conversation either:
        the app holds every thread's writer lock under
        `~/.codex/thread-writer-locks` for its own lifetime rather than the
        thread's, so those are pinned the same way.

        With no process to name, such a session's lifetime is its activity.
        `activity` says the claim carries no liveness of its own and why — the
        session is multiplexed into a process it does not own — and
        `claim_is_active` judges it from when the page was last touched. The
        value is a note for whoever reads the record; the key is the whole of
        what anything acts on."""
        if (pid := self.process_pid()) is not None:
            if "app-server" in (process_argv(pid) or []):
                return {"activity": "multiplexed"}
            return {"pid": pid}
        # Nothing to fall back to: any pid guessed here is a claim that expires
        # on its own, and the states that follow from one are silent.
        # LEAF_SESSION_ID with no codex above it is a hand-built environment, so
        # say what was walked.
        chain = " → ".join(program for _, program in ancestry())
        sys.exit(
            "LEAF_SESSION_ID names a Codex session but no codex process runs "
            f"above this one ({chain}); leaf takes the session's lifetime from it"
        )

    def carrier_live(self, *, listening: bool) -> bool:
        """A wait lease says only that some process can read page events. The
        adapter's second lease is the narrower fact this carrier rests on: that
        the process can durably hand those events to a turn after this one
        ends."""
        return listening and adapter_is_live(self.session)

    def input_unpicked(self, page_dir: Path, *, listening: bool) -> str:
        if listening:
            return f"Poll {_POLL_UNIFIED_EXEC}."
        return (
            f"Start `leaf codex start {page_dir}` so later updates reach this "
            "task in new turns."
        )

    @classmethod
    def hook_context(cls, event: str, message: str) -> dict:
        """Codex's Stop output schema (0.156) has no `hookSpecificOutput`, so its
        Stop hook keeps the turn going the one way it has: a block."""
        if event == "Stop":
            return {"decision": "block", "reason": message}
        return super().hook_context(event, message)

    @classmethod
    def run_ack(cls, delivery_id: str) -> str:
        """A Codex task's own wait lives in unified exec, the same session a
        watcher task or a direct loop polls."""
        return (
            f"run `leaf wait --ack {delivery_id}` in unified exec and poll it with "
            "`write_stdin`"
        )

    def nothing_listening(self, page_dir: Path, *, listening: bool) -> str:
        if listening:
            return (
                "the Codex page is still live. Keep this turn active and poll "
                f"{_POLL_UNIFIED_EXEC}."
            )
        return (
            f"no delivery adapter. Start `leaf codex start {page_dir}` so this "
            "turn can finish and later updates start new turns; or run `leaf "
            "status <page> idle` if the page is done."
        )


class PiHarness(EnvironmentHarness):
    """Pi (<https://pi.dev>): Leaf's extension (`hooks/pi.ts`) runs inside the Pi
    process and is the carrier, the way Claude Code's hooks are. A highly
    experimental trial.

    Pi states the session in every shell-tool command as PI_SESSION_ID, and
    states no process. The extension exports its own, Pi's, as LEAF_PI_PID,
    since an extension's `process.env` reaches the shell tool's commands
    (measured at Pi 1.0.2); the process walk would find a `node` whose
    command line Pi has overwritten with its title.

    The extension calls the prompt hook as a user's prompt starts a run, the
    Stop hook as a run is about to settle (`agent_before_settle`, whose
    `continue` keeps it going), and the Interrupt hook when a run settles
    without going on from there, which is what an Escape does. As the session
    starts and as each run settles it starts the watch (`leaf hook --watch`),
    with the Interrupt payload after an interrupted run. When the watch wakes
    it, it calls the prompt hook itself and sends what that returns: a message
    an extension sends to an idle Pi starts a run without its prompt events
    (measured at 1.0.2)."""

    name = "pi"
    default_agent = "Pi"
    session_variables = ("PI_SESSION_ID",)
    identity_variables = (*session_variables, "LEAF_PI_PID")
    hook_delivers = True

    @classmethod
    def process_pid(cls) -> int | None:
        return int(pid) if (pid := os.environ.get("LEAF_PI_PID")) else None

    def lifetime(self) -> dict:
        if (pid := self.process_pid()) is None:
            sys.exit(
                "PI_SESSION_ID names a Pi session but LEAF_PI_PID is unset: Leaf's "
                "Pi extension (hooks/pi.ts) is not loaded in it"
            )
        return {"pid": pid}

    def watches_between_turns(self) -> bool:
        """The extension starts the watch only in a Pi that can start a run, the
        TUI or RPC mode. Under `--print` the session ends with its run, which
        ends its claims, so no page is left that a watch would be owed."""
        return True

    def process_runs(self) -> bool:
        return pid_alive(int(os.environ["LEAF_PI_PID"]))

    def input_unpicked(self, page_dir: Path, *, listening: bool) -> str:
        return "Leaf's Pi extension puts them in your context at your next turn."

    def nothing_listening(self, page_dir: Path, *, listening: bool) -> str:
        return (
            "no watcher: Leaf's Pi extension watches this session's pages as each "
            "run settles, and has not run for this session."
        )


@dataclass(frozen=True)
class EmbeddedHarness(Harness):
    """A harness that drives Codex App Server in its own process and starts the
    turns itself — the shape <https://leaf.page/> runs in its per-user
    container.

    No environment implies this one: such a harness knows what it is and declares
    itself, supplying its own display name and the App Server process its
    session lives and dies with.

    The Stop hook never reaches a page this holds: the container's Codex runs
    with no Leaf plugin and so no Leaf hooks (`worker/codex-config.toml`), even
    though its agent does run `leaf` commands. The two remedies say what is true
    rather than what to type."""

    pid: int

    name = "embedded"

    @classmethod
    def from_claim(cls, claim: dict) -> "EmbeddedHarness":
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


def detached_environment() -> dict[str, str]:
    """The environment for a process this command detaches: its own, less the
    identity of every harness `session_harness` did not choose.

    A detached process leaves the harnesses above this one behind, so it could not
    rank them by process again, and the tie order would choose for it: a server a
    Codex task under Claude Code starts would serve as the Claude Code session.
    It inherits the one identity chosen here instead."""
    chosen = session_harness()
    others = {
        variable
        for harness in _ENVIRONMENT_HARNESSES
        if not isinstance(chosen, harness)
        for variable in harness.identity_variables
    }
    return {
        name: value
        for name, value in os.environ.items()
        if chosen is None or name not in others
    }


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


def claude_code_sessions() -> Path:
    """Claude Code's session registry: one `<pid>.json` per running session."""
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    return config / "sessions"


def claude_code_session_records(session_id: str) -> list[dict]:
    """The registry records Claude Code publishes for a session, found by id.

    Each session writes `sessions/<pid>.json` in its config directory, carrying
    `sessionId`, `pid`, its live `status` and when it last changed
    (`statusUpdatedAt`, epoch milliseconds), and `messagingSocketPath`. It is
    found by session id each time rather than written into the claim, because a
    background job's worker pid, and the record with it, changes over the job's
    life; a worker that died without removing its record leaves a second one.
    Each record is another program's live file, and a session can exit between
    listing and reading it, so a file that vanished or was caught mid-write is
    passed over.

    Every state read asks this of each claimed page, so a listing is reused for
    `REGISTRY_READ_S` while the directory's own stamp holds, well inside the
    presence cache's interval: a record added, removed or atomically replaced
    moves the stamp at once. The listing is the machine's rather than a page's, so
    the process keeps the last one, replaced whole."""
    global _registry_listing
    sessions = claude_code_sessions()
    try:
        stamp = sessions.stat().st_mtime_ns
    except OSError:
        return []
    held = _registry_listing
    if (
        held is None
        or held[:2] != (sessions, stamp)
        or time.monotonic() - held[2] >= REGISTRY_READ_S
    ):
        held = (sessions, stamp, time.monotonic(), _registry_records(sessions))
        _registry_listing = held
    return [record for record in held[3] if record.get("sessionId") == session_id]


REGISTRY_READ_S = 1.0
# (registry directory, its stamp, when it was listed, its records)
_registry_listing: tuple[Path, int, float, list[dict]] | None = None


def _registry_records(sessions: Path) -> list[dict]:
    records = []
    for record_path in sessions.glob("*.json"):
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


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
    if any(
        isinstance(record.get("pid"), int) and pid_alive(record["pid"])
        for record in claude_code_session_records(session_id)
    ):
        return False
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


def message_claude_code_session(session_id: str, text: str) -> bool:
    """Put `text` into a Claude Code session as a user message, through the
    messaging socket every session binds, and say whether a socket took it.

    Each registry record for the session (`claude_code_session_records`) names the
    socket, beside a 0600 `<pid>.<hash>.key` holding the `peerToken` it authenticates.
    The socket reads newline JSON and answers nothing: an auth line, then a user frame
    whose `session_id` makes a socket that has since passed to another session drop it.

    The recipient decides delivery. Measured on Claude Code 2.1.274: a session
    in a prompting permission mode queues the text as a user turn, which wakes
    it when idle and fires its UserPromptSubmit hook with the text as the
    prompt. A session that bypasses permissions holds a message from any process
    outside its own process tree behind a deliver-or-deny dialog, unless its
    user set `crossSessionInbound` to `accept`, and a headless session lets the
    held message expire. The server `leaf server start` spawns runs in a process
    session of its own, so it is outside that tree. Nothing reports the outcome
    to the sender, so True means only that a listening socket took the frames.

    Each record and key is another program's live file, and a session can exit
    between reading its record and connecting, so a file that vanished, was
    caught mid-write, lacks a field this reads, or names a socket nobody listens
    on skips that record."""
    sessions = claude_code_sessions()
    for record in claude_code_session_records(session_id):
        try:
            key_path = next(sessions.glob(f"{record['pid']}.*.key"))
            token = json.loads(key_path.read_text(encoding="utf-8"))["peerToken"]
            address = record["messagingSocketPath"]
            frames = (
                {"type": "auth", "token": token},
                {
                    "type": "user",
                    "session_id": session_id,
                    "message": {"role": "user", "content": text},
                },
            )
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
                peer.settimeout(1)
                peer.connect(address)
                peer.sendall("".join(json.dumps(f) + "\n" for f in frames).encode())
        except (OSError, ValueError, KeyError, TypeError, StopIteration):
            continue
        return True
    return False
