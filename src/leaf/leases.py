"""Process-backed locks and leases for page and session transitions.

Lease files are stable coordination points, created on first use and retained
after release. Only the descriptor's exclusive kernel lock proves a holder is
live; file existence says nothing. `release_lease` or process exit releases the
lease, including a crash. Holders never remove these files; `supersede_lease`
replaces one, to take its lease from a live holder, and a session's
end removes its unheld ones (`state.end_session`). A taker verifies the
acquired inode still has its name, since another process may have removed or
replaced the shared path while it was opening it, and a holder that can be
superseded asks the same of its own descriptor.
"""

import contextlib
import fcntl
import functools
import os
import signal
import sys
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO

from leaf.schema import WAITER_LOCK
from leaf.state import (
    HOOKS_SUFFIX,
    TOOLS_SUFFIX,
    flocked,
    session_file,
    still_named,
)


def lock_is_held(path: Path) -> bool:
    """Whether an exclusive lease is held on this file.

    The kernel releases the lease on exit, crash, or reboot. A durable record
    can therefore outlive its writer without being mistaken for a live process.

    The question is asked with a shared lock, which every lease here refuses and
    no reading takes for longer than the question. An exclusive probe would be
    answered by another reading's probe as readily as by a lease, so two
    processes asking at once would tell each other a lease was held. A file the
    name no longer reaches answers nothing either way: `supersede_lease` may have
    displaced it, its holder still running or gone, while the lease at the name
    began or ended. So the question is asked again of the file the name reaches.
    """
    while True:
        try:
            with open(path, "r+b") as probe:
                try:
                    fcntl.flock(probe, fcntl.LOCK_SH | fcntl.LOCK_NB)
                except OSError:
                    held = True
                else:
                    held = False
                    fcntl.flock(probe, fcntl.LOCK_UN)
                if still_named(probe.fileno(), path):
                    return held
        except OSError:
            return False


def take_lease(path: Path, *, prepare: Callable[[BinaryIO], None] | None = None):
    """Take the exclusive lease on this file and return it held, or None when
    another process holds it.

    The one way a lease is taken without waiting: a wait's, a server's, an
    adapter's, a preview slot's, and the barrier a stop takes once the server it
    disabled has exited. The caller holds the returned file for as long as it
    holds the lease and gives it back with `release_lease`; exiting releases it
    too. The stable file remains unheld for the next taker. The lease's directory
    must already exist, so a stop naming a page that is gone cannot create it.

    A refused exclusive lock means a lease or a `lock_is_held` question, whose
    shared lock is momentary. A shared lock of its own tells them apart, since
    only a lease refuses one, so a question asked at the instant a lease is taken
    does not turn that lease away.

    A producer that must prepare descriptor metadata supplies `prepare`. It runs
    under a shared lock before promotion to the live exclusive lease, so probes
    see preparation as unheld and can never pair old metadata with a new holder.
    The caller serializes those preparations; promotion waits for the momentary
    shared probes rather than refusing a legitimate lease.
    """
    while True:
        record = open(path, "a+b")  # noqa: SIM115 - returned and held by the caller
        if prepare is not None:
            try:
                fcntl.flock(record, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError:
                record.close()
                return None
            try:
                if still_named(record.fileno(), path):
                    prepare(record)
                    fcntl.flock(record, fcntl.LOCK_EX)
                    if still_named(record.fileno(), path):
                        return record
            except BaseException:
                record.close()
                raise
            record.close()
            continue
        try:
            fcntl.flock(record, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            try:
                fcntl.flock(record, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError:
                record.close()
                return None
        else:
            if still_named(record.fileno(), path):
                return record
        record.close()


def supersede_lease(path: Path):
    """Take the exclusive lease on this file whether or not another process holds
    it, and return it held, as `take_lease` does.

    The lease moves to a fresh file that takes the name with its lock already held,
    so a probe of the name never finds it unheld. A process it displaces still holds
    a lock, on a file the name no longer reaches, and learns it lost the lease from
    `still_named`."""
    staged = path.with_name(f"{path.name}.{os.getpid()}")
    record = open(staged, "w+b")  # noqa: SIM115 - returned and held by the caller
    try:
        fcntl.flock(record, fcntl.LOCK_EX)
        os.replace(staged, path)
    except BaseException:
        record.close()
        staged.unlink(missing_ok=True)
        raise
    return record


def release_lease(lease) -> None:
    """Release the descriptor's kernel lock, retaining its coordination file.

    The lock belongs to the open file, which every copy of the descriptor shares,
    and closing one copy leaves it held while another stands. A process that holds
    a lease and starts subprocesses lends its descriptors to each child from fork
    until exec closes them, so closing alone could leave a released lease held for
    as long as a child on a busy machine waits to run. Unlocking releases the open
    file itself, whichever copies remain."""
    fcntl.flock(lease, fcntl.LOCK_UN)
    lease.close()


# The terminating signal this process received, kept for `end_if_terminated`.
_terminated: list[int] = []


def release_on_termination() -> None:
    """Unwind process-owned resources when SIGTERM or SIGHUP ends a command.

    Kernel leases release even without unwinding, but a command may also own
    reply reservations and pending work that its `finally` blocks must retire.
    SIGKILL still skips that application cleanup.

    The handler raises the exit wherever the main thread is, since only a raise
    ends a blocked lock or condition wait; a handler that returns resumes it.
    Python discards a raise that lands in a weakref callback, `__del__` or a GC
    callback, such as a page memory's finalizer joining its watcher threads, so
    the handler also records the signal, and each loop that blocks under it calls
    `end_if_terminated` before it waits."""
    for terminating in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(terminating, _terminate)


def _terminate(signum: int, _frame) -> None:
    _terminated.append(signum)
    sys.exit(128 + signum)


def end_if_terminated() -> None:
    """Exit as `release_on_termination`'s handler would have, if its raise was
    lost."""
    if _terminated:
        sys.exit(128 + _terminated[0])


@contextlib.contextmanager
def page_locked(page_dir: Path):
    """Serialize one page's service changes, re-vendoring, and contract-bearing
    writes.

    The lock is the page directory itself, flocked through a descriptor on it,
    so it writes nothing into the page (`page init` refuses a package without
    touching it) and it ends with the directory: nothing is left behind to
    retire. The directory has to exist, which `page init` sees to before taking
    it. A page deleted and made again at its path while this waited is another
    directory, so the lock is taken again on whichever the path names once it is
    held; a page deleted for good raises FileNotFoundError."""
    while True:
        held = os.open(page_dir, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(held, fcntl.LOCK_EX)
            if still_named(held, page_dir):
                break
        except BaseException:
            os.close(held)
            raise
        os.close(held)
    try:
        yield
    finally:
        fcntl.flock(held, fcntl.LOCK_UN)
        os.close(held)


def contract_writer(function):
    """Keep a CLI event's validation and append on one vendored contract."""

    @functools.wraps(function)
    def locked(page_dir: Path, *args, **kwargs):
        with page_locked(page_dir):
            return function(page_dir, *args, **kwargs)

    return locked


def waiter_lease_path(page_dir: Path | None, session_id: str | None) -> Path | None:
    """The one lease a wait holds for its watch set.

    A harness wait covers every page its session owns, so its lease belongs to the
    session and takes only its id. Outside a harness, a named page is the entire
    watch set and holds a page-local lease. An unnamed bare-shell wait has no
    watch set and no lease.
    """
    if session_id:
        return session_file(session_id, "wait")
    return page_dir / WAITER_LOCK if page_dir is not None else None


def adapter_lease_path(session_id: str) -> Path:
    """The live proof for a detached harness delivery adapter.

    A wait lease says only that some process can read page events.  The Codex
    Stop hook needs the narrower fact that the process can durably hand those
    events to a later turn after the foreground turn ends, so the adapter holds
    a second lease for exactly that capability.
    """
    return session_file(session_id, "adapter")


def mark_hooks(session_id: str) -> None:
    """Record that the harness ran a Leaf hook for this session. The mark stands for
    the session's life, and its SessionEnd hook removes it."""
    session_file(session_id, HOOKS_SUFFIX).touch()


def first_hook_for_tool(session_id: str, tool_use_id: str | None) -> bool:
    """Whether this is the first of the session's hooks to run before the tool call
    `tool_use_id`, which it records if so; a hook that names no call is first.

    Claude Code runs a PreToolUse registration once for each of its `if` rules a
    command matches, all at once, and a command it cannot read matches all of
    them (`hooks/hooks.json`, measured at 2.1.310). It starts the call only once
    every one has exited, so the first does the hook's work for the others. The
    calls named last are kept, enough for a batch of calls whose hooks
    interleave. The hook marks that it ran (`mark_hooks`) before asking, which
    creates the session's directory."""
    if not tool_use_id:
        return True
    with flocked(session_file(session_id, TOOLS_SUFFIX)) as held:
        held.seek(0)
        seen = held.read().decode().split()
        if tool_use_id in seen:
            return False
        held.truncate(0)
        held.write("\n".join([*seen[-15:], tool_use_id]).encode())
    return True


def hooks_ran(session_id: str) -> bool:
    """Whether the harness has run a Leaf hook for this session. A harness whose hooks
    can carry input carries it only where they run: a session launched without the
    plugin's hooks, with hooks disabled, or whose hooks read another state home
    never marks this one."""
    return session_file(session_id, HOOKS_SUFFIX).exists()


def adapter_is_live(session_id: str) -> bool:
    """Whether this session's adapter is running right now."""
    return lock_is_held(adapter_lease_path(session_id))


def wait_is_live(page_dir: Path | None, session_id: str | None) -> bool:
    """Whether this ownership scope's exact wait lease is held now."""
    lease_path = waiter_lease_path(page_dir, session_id)
    return bool(lease_path and lock_is_held(lease_path))
