"""Local host paths, process readings, the agent harnesses Leaf runs under, and
the Claude Code messaging socket.

A harness is one agent host as Leaf meets it. `Harness` collects everything that
differs between them — session lifetime, delivery carrier, the hook's remedies,
the way to reach a session with nothing watching — so that every module below
this one dispatches on what a harness declares rather than on which harness it
is. `session_harness` reads the one running this command out of the
environment; `claim_harness` rebuilds the one a page's claim recorded.

psutil owns the process readings. It asks the kernel directly, which is what
these need: the portable tool is `ps`, macOS ships it setuid root, and the
seatbelt sandbox Codex runs its shell tool under refuses to exec it (measured
inside `codex exec --sandbox workspace-write`: `/bin/ps: Operation not
permitted`). psutil does not own `pid_alive`, whose comment records why."""

import json
import os
import socket
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import psutil

from leaf.files import read_json

# A process reading fails in two ways worth answering with None: the process is
# gone (NoSuchProcess, and ZombieProcess under it), or it belongs to another user
# and its command line is closed to us (AccessDenied). psutil's other errors come
# from calls this module does not make.
_UNREADABLE = (psutil.NoSuchProcess, psutil.AccessDenied)


def pid_alive(pid: int) -> bool:
    # PermissionError is another user's process, and every pid this module
    # records — servers, agent sessions — runs as this user. After a reboot the
    # low pids are mostly root's, so counting EPERM alive read a stale record
    # as a live server for as long as the machine stayed up. `psutil.pid_exists`
    # is the opposite reading: it takes EPERM as proof that a process is there.
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def process_info(pid: int) -> tuple[int, str] | None:
    """Two facts about a live process — the pid above it, and the name of the
    program it is itself running — or None once it is gone.

    The name is the executable's own, not the words the command was written
    with: a process launched through a symlink or a `#!` script reports what the
    kernel loaded. That is the point — it answers which program a process *is*,
    which is what `session_lifetime` asks of an ancestor. The kernel truncates
    it to 15 or 16 characters; psutil restores a truncated name from the program
    path the command line starts with."""
    try:
        process = psutil.Process(pid)
        return process.ppid(), process.name()
    except _UNREADABLE:
        return None


def ancestry() -> list[tuple[int, str]]:
    """This process and every process above it, nearest first: (pid, program).

    The walk ends at init, or at whichever ancestor exited while it ran — a
    parent that goes takes the rest of the chain with it, since what is left
    above a reparented process is init's."""
    walked = []
    pid = os.getpid()
    while pid > 1:
        info = process_info(pid)
        if info is None:
            break
        parent, program = info
        walked.append((pid, program))
        pid = parent
    return walked


def process_argv(pid: int) -> list[str] | None:
    """The words a live process was launched with, or None once it is gone or
    out of reach.

    `process_info` answers which program a process *is*; this answers what it
    was told to do, which is the only thing that separates a `codex` hosting one
    session from a `codex` hosting all of them (`session_lifetime`)."""
    try:
        return psutil.Process(pid).cmdline()
    except _UNREADABLE:
        return None


def state_home() -> Path:
    """$XDG_STATE_HOME/leaf (~/.local/state/leaf/) — pages/ holds page
    directories by convention, claims/ the last claimant of every known page,
    sessions/ the live watcher leases, page-locks/ the stable per-path transition
    leases, packages/ the packages `package install` copied here, and access.json
    the one key every page here is served with (`host_key`). State, not config:
    claim records carry pids and absolute paths, while page service records
    carry ports, so this state is bound to this machine, as is the key that
    reaches it.

    Created here, owner-only: the key is what stands between another local user
    and a log that outranks the document, and a 0644 file under a traversable
    path hands it to anyone on a shared machine. One writer for the mode, since
    every path into the state home resolves through this call."""
    home = (
        Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
        / "leaf"
    )
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    return home


def package_store() -> Path:
    """~/.local/state/leaf/packages/ — where `package install` puts a package so
    that `--package NAME` reaches it.

    This store survives plugin updates that replace the install tree."""
    return state_home() / "packages"


@dataclass(frozen=True)
class Harness:
    """One agent harness, and everything Leaf's harness-neutral code differs on.

    `session` is the host's own stable id for this session and `agent` the
    display name the page shows for it. Both are per-session; the rest of a
    harness is fixed for the program, and stated on its class.

    `name` is provenance and diagnostics. The claim writes it down and
    `claim_harness` reads it back to rebuild this object; nothing branches on
    it. `carrier` is what a reader does branch on — how a leaf's input reaches
    this session between its turns:

    - `wait`, a `leaf wait`/`leaf ack` loop the model itself runs, watched by
      the host's Stop and prompt hooks. It is the one carrier that stops while
      its session lives on, which is why it is the one with a `nudge`.
    - `adapter`, a detached process that outlives the turn and proves itself by
      holding the adapter lease.
    - `embedded`, a host process that drives Codex App Server itself and starts
      the turns; nothing outside it carries input in.

    The claim records the name and the carrier together, so a reader meeting
    that claim later — the page server, the append door, the Stop hook — acts on
    what the claimant wrote rather than re-deriving it from an environment that
    may not be the claimant's.

    A harness the environment can imply also states `default_agent` and the
    variables its session id arrives in. One that declares itself, as an
    embedded host does, states neither.
    """

    session: str
    agent: str

    name: ClassVar[str]
    carrier: ClassVar[str]
    default_agent: ClassVar[str]
    session_variables: ClassVar[tuple[str, ...]]

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

    def input_unpicked(self, page_dir: Path, *, listening: bool) -> str:
        """What to do about events past this page's cursor that nothing will
        carry."""
        raise NotImplementedError

    def nothing_listening(self, page_dir: Path, *, listening: bool) -> str:
        """What to do about a live page this session owes a watcher."""
        raise NotImplementedError

    def nudge(self, page_dir: Path) -> bool:
        """Put this page's new input in front of the session, and say whether
        anything took it.

        Only a carrier the model runs stops between turns while its session
        stands, so only such a harness has anywhere to put this. A carrier that
        is a process of its own is either running, and needs no telling, or gone
        along with the session it served."""
        return False


class ClaudeCodeHarness(Harness):
    """Claude Code: a wait loop the model runs, and a socket to reach it with."""

    name = "claude-code"
    carrier = "wait"
    default_agent = "Claude"
    session_variables = ("CLAUDE_CODE_SESSION_ID",)

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

    def input_unpicked(self, page_dir: Path, *, listening: bool) -> str:
        return "`leaf wait` prints them."

    def nothing_listening(self, page_dir: Path, *, listening: bool) -> str:
        return (
            "no watcher. Start `leaf wait` as a background task — one wait "
            "covers every page this session holds — or run `leaf status <page> "
            "idle` if the page is done."
        )

    def nudge(self, page_dir: Path) -> bool:
        return message_claude_code_session(
            self.session,
            f"leaf: {page_dir} has new input and no `leaf wait` is running "
            "for this session to deliver it. Start an unnamed `leaf wait` "
            "as a background task.",
        )


# One phrase, because the two remedies below name the same recovery: a `leaf
# wait` already running in the task's shell tool, which the model reads by
# writing to that session rather than by starting a second watcher.
_POLL_UNIFIED_EXEC = (
    "the existing unified-exec session — `leaf wait` before the first batch or "
    "the rearmed `leaf ack` afterward — with `write_stdin`"
)


class CodexHarness(Harness):
    """Codex: one detached adapter carries every page the task holds.

    LEAF_SESSION_ID outranks CODEX_THREAD_ID because a worker Codex launches
    with an id of its own means that id, and the thread it happens to run under
    is not it."""

    name = "codex"
    carrier = "adapter"
    default_agent = "Codex"
    session_variables = ("LEAF_SESSION_ID", "CODEX_THREAD_ID")

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
        that started it, and the page would have told its reader no session
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
        the process can durably hand those events to a turn after this one ends.

        Imported here because `leases` reads the state home this module owns."""
        from leaf.leases import adapter_is_live

        return listening and adapter_is_live(self.session)

    def input_unpicked(self, page_dir: Path, *, listening: bool) -> str:
        if listening:
            return f"Poll {_POLL_UNIFIED_EXEC}."
        return (
            f"Start `leaf codex start {page_dir}` so later updates queue new "
            "turns in this task."
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
    turns itself — the shape <https://leaf.page/> runs in its per-reader
    container.

    No environment implies this one: such a host knows what it is and declares
    itself, supplying its own display name and the App Server process its
    session lives and dies with.

    The Stop hook never reaches a page this holds, because there is no model
    running `leaf` commands beside it; the two remedies say what is true rather
    than what to type."""

    pid: int

    name = "embedded"
    carrier = "embedded"

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
_ENVIRONMENT_HARNESSES = (ClaudeCodeHarness, CodexHarness)
_HARNESSES = {
    harness.name: harness for harness in (*_ENVIRONMENT_HARNESSES, EmbeddedHarness)
}
# Every variable a host session states its id in. A build that publishes pages
# scrubs the set so the builder's own session does not sign them
# (`scripts/site.py`).
SESSION_VARIABLES = tuple(
    variable
    for harness in _ENVIRONMENT_HARNESSES
    for variable in harness.session_variables
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
                    agent=os.environ.get("LEAF_AGENT") or harness.default_agent,
                )
    return None


def claim_harness(claim: dict) -> Harness:
    """The claimant's harness, rebuilt from the claim record.

    A page server, the append door and the Stop hook all run in processes that
    need not be the claimant's, so they read the harness the claim names instead
    of the one their own environment implies."""
    return _HARNESSES[claim["harness"]].from_claim(claim)


def message_identity() -> dict:
    """The voice an agent-authored event carries: the posting session's display
    name and session id, read from its own environment rather than the page's
    claim record — the claimant is whoever watches the page, and on a page
    several sessions report to, that is usually not the poster. Empty outside a
    host session: the readers' generic label covers an event with no voice, and
    a stored placeholder would only impersonate a name."""
    harness = session_harness()
    if harness is None:
        return {}
    return {"agent": harness.agent, "session": harness.session}


def message_claude_code_session(session_id: str, text: str) -> bool:
    """Put `text` into a Claude Code session as a user message, through the
    messaging socket every session binds, and say whether a socket took it.

    A session publishes itself as `sessions/<pid>.json` in its config directory,
    carrying `sessionId` and `messagingSocketPath`, beside a 0600
    `<pid>.<hash>.key` holding the `peerToken` the socket authenticates. The
    record is found by session id when the message is sent rather than written
    into the claim, because a background job's worker pid, and the socket with
    it, changes over the job's life. The socket reads newline JSON and answers
    nothing: an auth line, then a user frame whose `session_id` makes a socket
    that has since passed to another session drop it.

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
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    sessions = config / "sessions"
    for record_path in sessions.glob("*.json"):
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
            if record["sessionId"] != session_id:
                continue
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
