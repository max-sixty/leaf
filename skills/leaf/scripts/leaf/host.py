"""Local host paths, process readings, and agent-session identity."""

import ctypes
import os
import sys
from pathlib import Path

from leaf.files import read_json


def pid_alive(pid: int) -> bool:
    # PermissionError is another user's process, and every pid this module
    # records — servers, agent sessions — runs as this user. After a reboot the
    # low pids are mostly root's, so counting EPERM alive read a stale record
    # as a live server for as long as the machine stayed up.
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
    which is what `session_lifetime` asks of an ancestor.

    Two platform doors because there is no portable one. `ps` reads this on
    both, and macOS ships it setuid root, which the seatbelt sandbox Codex runs
    its shell tool under refuses to exec — so the one door that looks portable
    is the one that fails exactly where this is needed (measured inside
    `codex exec --sandbox workspace-write`: `/bin/ps: Operation not
    permitted`)."""
    if sys.platform == "darwin":
        # proc_pidinfo's PROC_PIDT_SHORTBSDINFO, whose whole struct is the two
        # facts wanted; pbsi_comm is the executable's name, truncated to 16.
        class ProcBSDShortInfo(ctypes.Structure):
            _fields_ = [
                ("pbsi_pid", ctypes.c_uint32),
                ("pbsi_ppid", ctypes.c_uint32),
                ("pbsi_pgid", ctypes.c_uint32),
                ("pbsi_status", ctypes.c_uint32),
                ("pbsi_comm", ctypes.c_char * 16),
                ("pbsi_flags", ctypes.c_uint32),
                ("pbsi_uid", ctypes.c_uint32),
                ("pbsi_gid", ctypes.c_uint32),
                ("pbsi_ruid", ctypes.c_uint32),
                ("pbsi_rgid", ctypes.c_uint32),
                ("pbsi_svuid", ctypes.c_uint32),
                ("pbsi_svgid", ctypes.c_uint32),
                ("pbsi_rfu", ctypes.c_uint32),
            ]

        proc_pidt_shortbsdinfo = 13
        info = ProcBSDShortInfo()
        proc_pidinfo = ctypes.CDLL(None).proc_pidinfo
        if proc_pidinfo(
            ctypes.c_int(pid),
            ctypes.c_int(proc_pidt_shortbsdinfo),
            ctypes.c_uint64(0),
            ctypes.byref(info),
            ctypes.c_int(ctypes.sizeof(info)),
        ) != ctypes.sizeof(info):
            return None
        return info.pbsi_ppid, info.pbsi_comm.decode()

    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return None
    # The program's name is parenthesised and may hold spaces and parens of its
    # own, so the fields after it are read from past the last ')': state, ppid.
    program = stat[stat.index("(") + 1 : stat.rindex(")")]
    return int(stat[stat.rindex(")") + 1 :].split()[1]), program


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


def config_home() -> Path:
    """$XDG_CONFIG_HOME/leaf (~/.config/leaf/) — the user's implicit package."""
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "leaf"


def state_home() -> Path:
    """$XDG_STATE_HOME/leaf (~/.local/state/leaf/) — pages/ holds page
    directories by convention, claims/ the last claimant of every known page,
    sessions/ the live watcher leases, init/ the stable per-path creation
    leases, and access.json the one key every page here is served with
    (`host_key`). State, not config:
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
    of its own."""
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
            return {"pid": pid}
    # Nothing to fall back to: any pid guessed here is a claim that expires on
    # its own, and the states that follow from one are silent. LEAF_SESSION_ID
    # with no codex above it is a hand-built environment, so say what was walked.
    chain = " → ".join(program for _, program in walked)
    sys.exit(
        "LEAF_SESSION_ID names a Codex session but no codex process runs above "
        f"this one ({chain}); leaf takes the session's lifetime from it"
    )
