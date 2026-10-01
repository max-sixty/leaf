"""The agent harnesses Leaf runs under, and the Claude Code messaging socket
behind one of them.

A harness is one agent host as Leaf meets it. `Harness` collects everything that
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
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import ClassVar

from leaf.files import read_json
from leaf.leases import adapter_is_live, hooks_ran
from leaf.machine import ancestry, pid_alive, process_argv


@dataclass(frozen=True)
class Harness:
    """One agent harness, and everything Leaf's harness-neutral code differs on.

    `session` is the host's own stable id for this session and `agent` the
    display name the page shows for it. Both are per-session; the rest of a
    harness is fixed for the program, and stated on its class.

    `name` is the one fact the claim writes down: `claim_harness` reads it back
    to rebuild this object, and a reader meeting that claim later — the page
    server, the append door, the Stop hook — asks the object rather than
    re-deriving anything from an environment that may not be the claimant's.
    Nothing compares the name outside this module and a harness's own code.

    What differs between harnesses is how a leaf's input reaches the session
    between its turns, and the methods below answer for that carrier:

    - Claude Code's model keeps a background `leaf wait` running, which ends when
      input arrives and so opens a turn; the host's prompt hook, which runs as that
      turn begins, and its Stop hook put the input in the turn's context and
      confirm it (`hook_delivers`). The wait is the one carrier part that stops
      while its session lives on, which is why this is the harness with a `nudge`.
    - Codex has a detached adapter that outlives the turn and proves itself by
      holding the adapter lease. It queues each delivery with `codex queue`, or
      starts its turn over the task's App Server when Leaf can reach one.
    - An embedded host drives Codex App Server itself and starts the turns;
      nothing outside it carries input in.
    """

    session: str
    agent: str

    name: ClassVar[str]
    # Whether the host's hooks can carry input into the turn: they freeze, confirm,
    # and hand over the whole delivery, and `leaf wait` only wakes the session.
    # `hooks_carry` says whether they do for this session.
    hook_delivers: ClassVar[bool] = False
    # How long a `leaf wait` under this harness watches before it ends itself with
    # `wait_lapsed`, or None where nothing but input and the page's end stops it.
    wait_lifetime: ClassVar[float | None] = None

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
        process holding one lease. A carrier that has to prove more overrides
        this."""
        return listening

    def hooks_carry(self) -> bool:
        """Whether this session's hooks carry its input: its host runs hooks that
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

    def wait_lapsed(self) -> str:
        """The line a wait prints as it ends at `wait_lifetime` with no input."""
        raise NotImplementedError

    @classmethod
    def run_ack(cls, delivery_id: str) -> str:
        """How the reader of this session's printed delivery runs the `leaf wait
        --ack` that confirms it and goes on waiting: the verb phrase the
        delivery's `acknowledge` ends with. A harness whose hook carries input
        prints no delivery; a wait held in a background task is the default."""
        return f"start `leaf wait --ack {delivery_id}` as the next background task"

    @classmethod
    def continue_turn(cls, message: str) -> dict:
        """The Stop hook output that keeps the ending turn going with `message` as
        new context: a block, which every host that runs Leaf's hooks honours. It
        is Codex's only way, since its Stop output schema (0.156) has no
        `hookSpecificOutput`."""
        return {"decision": "block", "reason": message}

    def nudge(self, page_dir: Path) -> bool:
        """Put this page's new input in front of the session, and say whether
        anything took it.

        Only a carrier the model runs stops between turns while its session
        stands, so only such a harness has anywhere to put this. A carrier that
        is a process of its own is either running, and needs no telling, or gone
        along with the session it served."""
        return False

    def title_generator(self) -> Callable[[str, Path], dict] | None:
        """How the page server names a thread a user opens on this session's page,
        as the comment is admitted (`thread_titles`), or None where it cannot.

        Only a host whose model any process on the machine can ask has one. An App
        Server carrier names the thread instead, as it starts the turn answering
        it, since the page server cannot reach that server."""
        return None

    def live_turn(self) -> dict | None:
        """What the host itself says about this session right now, or None where it
        says nothing a reader can take.

        `{"state": "busy" | "waiting" | "idle", "since": <iso>}`, dated by the
        host's own last change: `idle` once no turn runs, `waiting` while a turn
        holds a dialog open in the session's own window. `activity.claimant_turn`
        weighs it by that date against the claim's turn stamps, which the hooks
        write and so cannot see a turn end that runs no hook."""
        return None


class EnvironmentHarness(Harness):
    """A harness the environment implies, by the variable its session id arrives
    in. It also names the display default a launch that set no LEAF_AGENT gets.
    A harness that declares itself, as an embedded host does, states neither.

    `identity_variables` is every variable the harness reads to know which
    session this is and how long it lives: its session variables, then the ones
    `lifetime` reads."""

    default_agent: ClassVar[str]
    session_variables: ClassVar[tuple[str, ...]]
    identity_variables: ClassVar[tuple[str, ...]]


# Claude Code stops a background command once its Bash `timeout` runs out, and this
# is the longest it takes; left out, the timeout is 1,800,000. The stop reaches the
# model as "stopped after reaching its background time limit", beside Claude Code's
# advice not to restart a command that already had the longest timeout.
BACKGROUND_LIMIT_MS = 7_200_000

# How a Claude Code session starts the wait that wakes it. The timeout is the
# longest, since every end of a wait wakes the session, input or not.
START_WAIT = (
    "start an unnamed `leaf wait` as a background task with `timeout` "
    f"{BACKGROUND_LIMIT_MS} (milliseconds), the longest Claude Code allows"
)


class ClaudeCodeHarness(EnvironmentHarness):
    """Claude Code: a wait the model keeps running to wake it, hooks that carry
    input into the turn, and a socket to reach it with."""

    name = "claude-code"
    default_agent = "Claude"
    session_variables = ("CLAUDE_CODE_SESSION_ID",)
    identity_variables = (*session_variables, "CLAUDE_PID", "CLAUDE_JOB_DIR")
    # Claude Code runs the prompt hook on every turn a background task's end
    # opens, idle or mid-turn, and adds what it returns to that turn's context.
    hook_delivers = True
    # A wait ends itself two minutes short of the longest background timeout, room
    # for the launcher's start and the pass under way. Its end is then an ordinary
    # completion, and the prompt hook's "no watcher" asks for the next, where Claude
    # Code's stop would come with its advice not to restart. A wait started with a
    # shorter timeout is still stopped, and that notice says to give it a longer one.
    wait_lifetime = BACKGROUND_LIMIT_MS / 1000 - 120

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
    def continue_turn(cls, message: str) -> dict:
        """Claude Code continues a turn on a Stop hook's `additionalContext` as it
        does on a block, and labels it "Stop hook additional context" rather than
        "Stop hook error": its schema calls that field non-error feedback after
        which the conversation continues, and a probe at 2.1.284 saw the turn go
        on and the next Stop arrive with `stop_hook_active`. Nothing Leaf's Stop
        hook says is an error, so it takes this channel."""
        return {
            "hookSpecificOutput": {
                "hookEventName": "Stop",
                "additionalContext": message,
            }
        }

    @classmethod
    def run_ack(cls, delivery_id: str) -> str:
        return (
            f"start `leaf wait --ack {delivery_id}` as the next background task, "
            f"with `timeout` {BACKGROUND_LIMIT_MS} (milliseconds)"
        )

    def input_unpicked(self, page_dir: Path, *, listening: bool) -> str:
        return "Leaf's hook puts them in your context at your next turn."

    def nothing_listening(self, page_dir: Path, *, listening: bool) -> str:
        return (
            f"no watcher. To watch all this session's pages, {START_WAIT}; or run "
            "`leaf status <page> idle` if this page is done."
        )

    def wait_lapsed(self) -> str:
        return (
            f"no input in {self.wait_lifetime / 60:.0f} minutes, so this wait ended "
            "before Claude Code's background time limit could stop it. To go on "
            f"watching, {START_WAIT}."
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
        return message_claude_code_session(
            self.session,
            f"leaf: {page_dir} has new input, which arrives with this message, "
            "and no `leaf wait` is running for this session. So that later input "
            f"wakes you, {START_WAIT}.",
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
        walked = ancestry()
        for pid, program in walked:
            if program == "codex":
                if "app-server" in (process_argv(pid) or []):
                    return {"activity": "multiplexed"}
                return {"pid": pid}
        # Nothing to fall back to: any pid guessed here is a claim that expires
        # on its own, and the states that follow from one are silent.
        # LEAF_SESSION_ID with no codex above it is a hand-built environment, so
        # say what was walked.
        chain = " → ".join(program for _, program in walked)
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


@dataclass(frozen=True)
class EmbeddedHarness(Harness):
    """A host that drives Codex App Server in its own process and starts the
    turns itself — the shape <https://leaf.page/> runs in its per-user
    container.

    No environment implies this one: such a host knows what it is and declares
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
        return "The host holding this page starts its own turn for new input."

    def nothing_listening(self, page_dir: Path, *, listening: bool) -> str:
        return "no embedded host is holding this page."


# The harnesses an environment can imply, in the order `session_harness` reads
# them, and every harness a claim can name.
_ENVIRONMENT_HARNESSES: tuple[type[EnvironmentHarness], ...] = (
    ClaudeCodeHarness,
    CodexHarness,
)
HARNESSES: dict[str, type[Harness]] = {
    harness.name: harness for harness in (*_ENVIRONMENT_HARNESSES, EmbeddedHarness)
}
# The display name a launch gives its session, whichever harness it runs under.
AGENT_VARIABLE = "LEAF_AGENT"
# Every variable that makes a process a host session: each harness's identity and
# the display name. A process that must not act as the session it was started from
# scrubs the set: a build that publishes pages (`leaf-dev site`), an eval's child
# (`dev/leaf_dev/harness.py`), the test suite (`tests/conftest.py`).
IDENTITY_VARIABLES = (
    *(
        variable
        for harness in _ENVIRONMENT_HARNESSES
        for variable in harness.identity_variables
    ),
    AGENT_VARIABLE,
)


def session_harness() -> Harness | None:
    """The harness running this command, or None outside an agent host.

    Each host states its session id in a variable of its own, and LEAF_SESSION_ID
    is the door a launch opens to name a session neither of them started; a
    third host earns its own value when one arrives. The display name is
    LEAF_AGENT where the launch set one — naming a worker in its environment
    needs no cooperation from the agent, so every command it runs speaks as that
    voice — and the harness's own default otherwise. The name is a display
    choice and nothing may dispatch on it, which is why the harness is a
    separate fact. What outlives the command is `Harness.lifetime`'s to find."""
    for harness in _ENVIRONMENT_HARNESSES:
        for variable in harness.session_variables:
            if session := os.environ.get(variable):
                return harness(
                    session=session,
                    agent=os.environ.get(AGENT_VARIABLE) or harness.default_agent,
                )
    return None


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
    host session: the users' generic label covers an event with no voice, and
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
    moves the stamp at once."""
    sessions = claude_code_sessions()
    try:
        stamp = sessions.stat().st_mtime_ns
    except OSError:
        return []
    held = _registry_cache.get(sessions)
    if (
        held is None
        or held[1] != stamp
        or time.monotonic() - held[0] >= REGISTRY_READ_S
    ):
        held = (time.monotonic(), stamp, _registry_records(sessions))
        _registry_cache[sessions] = held
    return [record for record in held[2] if record.get("sessionId") == session_id]


REGISTRY_READ_S = 1.0
_registry_cache: dict[Path, tuple[float, int, list[dict]]] = {}


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
