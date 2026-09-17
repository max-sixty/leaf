"""Local host paths, process readings, agent-session identity, and the Claude Code
messaging socket.

psutil owns the process readings. It asks the kernel directly, which is what
these need: the portable tool is `ps`, macOS ships it setuid root, and the
seatbelt sandbox Codex runs its shell tool under refuses to exec it (measured
inside `codex exec --sandbox workspace-write`: `/bin/ps: Operation not
permitted`). psutil does not own `pid_alive`, whose comment records why."""

import json
import os
import socket
import sys
from pathlib import Path

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


def host_identity() -> dict | None:
    """The identity the host session supplies through the environment, or None
    outside an agent host: `id`, the session's own stable id; `host`, which
    program is running it; `agent`, the display name the page shows for it.

    The name is LEAF_AGENT where the launch set one — naming a worker in its
    environment needs no cooperation from the agent, so every command it runs
    speaks as that voice — and the host's own name otherwise. `host` stays a
    separate fact because behavior keys on it (unattended_pages prescribes
    unified exec or background tasks by host) and a display name is anyone's to
    choose. Each host states its id in its own variable, and LEAF_SESSION_ID is
    the door a launch opens to name a session neither of them started; a third
    host earns its own value when one arrives — the id and the name, which are
    the whole of what a launch can state. What outlives the command is
    `session_lifetime`'s to find.

    LEAF_SESSION_ID outranks CODEX_THREAD_ID because a worker Codex launches
    with an id of its own means that id, and the thread it happens to run under
    is not it."""
    if sid := os.environ.get("CLAUDE_CODE_SESSION_ID"):
        agent = os.environ.get("LEAF_AGENT") or "Claude"
        return {"id": sid, "host": "claude-code", "agent": agent}
    if sid := os.environ.get("LEAF_SESSION_ID") or os.environ.get("CODEX_THREAD_ID"):
        agent = os.environ.get("LEAF_AGENT") or "Codex"
        return {"id": sid, "host": "codex", "agent": agent}
    return None


def message_identity() -> dict:
    """The voice an agent-authored event carries: the posting session's display
    name and session id, read from its own environment rather than the page's
    claim record — the claimant is whoever watches the page, and on a page
    several sessions report to, that is usually not the poster. Empty outside a
    host session: the readers' generic label covers an event with no voice, and
    a stored placeholder would only impersonate a name."""
    identity = host_identity()
    if identity is None:
        return {}
    return {"agent": identity["agent"], "session": identity["id"]}


def session_lifetime(identity: dict) -> dict:
    """The claim fields naming what the agent session's lifetime is, which is
    what the claim records and its readers act on: a lifetime that has ended
    makes ownership inactive, and a session-managed server retires
    ORPHAN_GRACE_SECS after it (`stop_when_service_ends`).

    A session the user sits at is a process, `pid`. Claude Code states it
    outright as CLAUDE_PID, and Codex states nothing, so the Codex half is
    discovered: the nearest ancestor running the `codex` program. The
    launcher cannot hand it over, because a shell tool's $PPID is a fact about
    the *shape* of the command rather than about the session. Measured through
    `codex exec` at 0.147.0: a bare command, an `&&` chain and a `bash -lc` all
    reported the codex process, because the shell it wraps them in can exec a
    last simple command in place; `leaf … | cat` reported the wrapping shell
    itself, which exits with the pipeline. Recording that one would have taken
    the page's server down a second after the command that started it, and the
    page would have told its reader no session holds it while the session sat
    there working.

    A Claude Code background job (`claude --bg`, the agents view) has no such
    process. Its turns run on daemon workers, and CLAUDE_PID names the worker
    hosting the current sitting. The daemon retires that worker about an hour
    after the job goes idle and claims a fresh one at the next wake — measured
    at Claude Code 2.1.241 from its daemon log, `bg settled … (done)` then `bg
    claimed-spare …` — while the job, the session every wake resumes, stands
    until it is deleted. So a job's lifetime is `job`, the directory
    CLAUDE_JOB_DIR names, and a page held by one stays served until the job is
    deleted or `leaf server stop` ends it. The fact read there is the job
    record, `state.json`, which the daemon writes as it creates the job and
    takes with it; the directory alone can stand empty, for a spare never
    assigned or a job an older daemon cleaned. The record's `sessionId` has to
    be this session's, because the variable is inherited: a session started
    under the job's own shell tool carries the job's directory and is a process
    of its own.

    Codex has a second shape with no session process at all. The ChatGPT app
    runs one `codex ... app-server` per app launch and multiplexes every
    conversation through it: its children are node, uv and zsh, never a
    per-conversation `codex`. The ancestry walk still reaches that process, so
    recording its pid gave every session in the app one shared lifetime, and one
    that ends only when the app quits — measured on a machine with 133 claims
    naming a single app-server pid and 49 session-managed servers that could
    never retire. Nothing else there is per-conversation either: the app holds
    every thread's writer lock under `~/.codex/thread-writer-locks` for its own
    lifetime rather than the thread's, so those are pinned the same way.

    With no process to name and no host fact to read, such a session's lifetime
    is its activity. `activity` records that the claim carries no liveness of
    its own, and names which host shape it met; `claim_is_active` judges it from
    when the page was last touched."""
    if identity["host"] == "claude-code":
        if job := os.environ.get("CLAUDE_JOB_DIR"):
            record = read_json(Path(job) / "state.json")
            if record is None:
                sys.exit(
                    f"CLAUDE_JOB_DIR names no job record ({job}/state.json); "
                    "leaf takes a background job's lifetime from it"
                )
            if record["sessionId"] == identity["id"]:
                return {"job": str(Path(job).resolve())}
        return {"pid": int(os.environ["CLAUDE_PID"])}
    walked = ancestry()
    for pid, program in walked:
        if program == "codex":
            if "app-server" in (process_argv(pid) or []):
                return {"activity": "codex-app-server"}
            return {"pid": pid}
    # Nothing to fall back to: any pid guessed here is a claim that expires on
    # its own, and the states that follow from one are silent. LEAF_SESSION_ID
    # with no codex above it is a hand-built environment, so say what was walked.
    chain = " → ".join(program for _, program in walked)
    sys.exit(
        "LEAF_SESSION_ID names a Codex session but no codex process runs above "
        f"this one ({chain}); leaf takes the session's lifetime from it"
    )


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
