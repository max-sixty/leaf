"""This machine: the state home Leaf keeps on it, and the processes running on
it.

Everything here is bound to the machine rather than to a page. The state home
holds this machine's claims, leases, page records, packages, and serving key,
while the process readings say whether a pid a record names still runs and
which programs run above this one — the walk a Codex session's lifetime comes
from when its host states no pid.

psutil owns the process readings. It asks the kernel directly, which is what
these need: the portable tool is `ps`, macOS ships it setuid root, and the
seatbelt sandbox Codex runs its shell tool under refuses to exec it (measured
inside `codex exec --sandbox workspace-write`: `/bin/ps: Operation not
permitted`). psutil does not own `pid_alive`, whose comment records why."""

import os
from pathlib import Path

import psutil

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
    which is what `CodexHarness.lifetime` asks of an ancestor. The kernel truncates
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
    session from a `codex` hosting all of them (`CodexHarness.lifetime`)."""
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
