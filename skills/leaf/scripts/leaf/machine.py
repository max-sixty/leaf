"""This machine: the state home Leaf keeps on it, and the processes running on
it.

Everything here is bound to the machine rather than to a page. The state home
holds this machine's claims, leases, page records, packages, and serving key,
while the process readings say whether a pid a record names still runs and
which programs run above this one — the walk a Codex session's lifetime comes
from when its harness states no pid.

psutil owns the process readings. It asks the kernel directly, which is what
these need: the portable tool is `ps`, macOS ships it setuid root, and the
seatbelt sandbox Codex runs its shell tool under refuses to exec it (measured
inside `codex exec --sandbox workspace-write`: `/bin/ps: Operation not
permitted`). Only those readings import it, and `pid_alive` only for a refused
signal: paths need no third-party library, so ownership discovery need not
import process inspection."""

import errno
import os
from pathlib import Path

from .state import state_home_path


def pid_alive(pid: int) -> bool:
    """Whether `pid` is a running process of this user's, which every pid this
    module's records name is: servers and agent sessions.

    Signal 0 settles most pids, delivered or refused for want of a process. Its
    EPERM has two causes. Another user's process must read as gone: after a
    reboot the low pids are mostly root's, and counting them alive read a stale
    record as a live server for as long as the machine stayed up, which is why
    `psutil.pid_exists`, reading every EPERM as alive, does not own this. Or the
    process is this user's and a sandbox refuses to signal past itself, as
    Claude Code's and Codex's macOS sandboxes do for the session they run
    commands for. The owner tells the two apart, and those sandboxes let psutil
    read it."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        import psutil

        try:
            return psutil.Process(pid).uids().real == os.getuid()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    return True


# What a harness's sandbox sets in each command it confines: the sandbox runtime
# Claude Code runs its shell commands under (`SANDBOX_RUNTIME=1`), and Codex's
# (`CODEX_SANDBOX=seatbelt`). Each is the harness's own statement, as CLAUDE_PID
# is, rather than a guess from what a refusal looked like.
SANDBOX_VARIABLES = ("SANDBOX_RUNTIME", "CODEX_SANDBOX")


def sandbox_remedy() -> str | None:
    """Where an agent harness's sandbox confines this command, the clause a refusal
    the sandbox explains ends with, or None where no harness says so: the variable
    that says it, and to rerun the command outside the sandbox, so the agent does
    not read the refusal as the host's. It points at the README's settings that run
    `leaf` outside the sandbox without asking, for the agent to pass on."""
    for name in SANDBOX_VARIABLES:
        if value := os.environ.get(name):
            readme = Path(__file__).resolve().parents[4] / "README.md"
            return (
                f"this command runs in an agent's sandbox ({name}={value}), so rerun "
                f'it outside the sandbox; "Agent sandboxes" in {readme} gives the '
                "settings that run leaf outside it without asking"
            )
    return None


def sandbox_refusal(error: BaseException) -> str | None:
    """`error` worded with `sandbox_remedy`, where the OS error it is, or the one
    a refusal was raised from, is how an agent's sandbox refuses: EPERM from
    macOS's sandboxes, and EROFS from the read-only mount Claude Code's Linux
    sandbox makes of what a command may not write. None otherwise."""
    cause = error if isinstance(error, OSError) else error.__cause__
    if not isinstance(cause, OSError) or cause.errno not in (errno.EPERM, errno.EROFS):
        return None
    remedy = sandbox_remedy()
    return f"{error}: {remedy}" if remedy else None


def process_info(pid: int) -> tuple[int, str] | None:
    """Two facts about a live process — the pid above it, and the name of the
    program it is itself running — or None once it is gone.

    The name is the executable's own, not the words the command was written
    with: a process launched through a symlink or a `#!` script reports what the
    kernel loaded. That is the point — it answers which program a process *is*,
    which is what `CodexHarness.lifetime` asks of an ancestor. The kernel truncates
    it to 15 or 16 characters; psutil restores a truncated name from the program
    path the command line starts with."""
    import psutil

    try:
        process = psutil.Process(pid)
        return process.ppid(), process.name()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
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
    import psutil

    try:
        return psutil.Process(pid).cmdline()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def state_home() -> Path:
    """$XDG_STATE_HOME/leaf (~/.local/state/leaf/) — pages/ holds page
    directories by convention, claims/ the last claimant of every known page,
    sessions/ the live watcher leases, packages/ the packages `package install` copied here,
    screens/ the last render check's screens of each page, pictures/ the
    pictures `page picture` drew of its drawing comments, and access.json
    the one key every page here is served with (`host_key`). State, not config:
    claim records carry pids and absolute paths, while page service records
    carry ports, so this state is bound to this machine, as is the key that
    reaches it.

    Created here, owner-only: the key is what stands between another local user
    and a log that outranks the document, and a 0644 file under a traversable
    path hands it to anyone on a shared machine. One writer for the mode, since
    every path into the state home resolves through this call."""
    home = state_home_path()
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    return home


def package_store() -> Path:
    """~/.local/state/leaf/packages/ — where `package install` puts a package so
    that `--package NAME` reaches it.

    This store survives plugin updates that replace the install tree."""
    return state_home() / "packages"
