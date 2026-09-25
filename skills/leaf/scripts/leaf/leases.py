"""Process-backed locks and leases for page and session transitions.

A lease or lock file is the lock and nothing more, so it exists only while it is
held or awaited, whoever it belongs to: its holder removes it on release, and a
taker that locks a file already removed takes the lock again on whatever the path
names now (`event_log.still_named`). That is what lets a session's files end with
the session: nothing reads them once they are released, so there is no later
reader to retire them, and no signal that a session which can be resumed is over.
A holder the kernel kills outright leaves its file behind, unheld; the next holder
of that name takes it and removes it on release.
"""

import contextlib
import functools
import hashlib
import os
import signal
import sys
from pathlib import Path

from leaf.event_log import (
    EventRefused,
    flocked,
    require_cross_process_locking,
    still_named,
)
from leaf.machine import state_home
from leaf.schema import WAITER_LOCK

try:
    import fcntl
except ImportError:  # pragma: no cover - rejected before a lease is read or taken
    fcntl = None


def lock_is_held(path: Path) -> bool:
    """Whether an exclusive lease is held on this file.

    The kernel releases the lease on exit, crash, or reboot. A durable record
    can therefore outlive its writer without being mistaken for a live process.

    The question is asked with a shared lock, which every lease here refuses and
    no reading takes for longer than the question. An exclusive probe would be
    answered by another reading's probe as readily as by a lease, so two
    processes asking at once would tell each other a lease was held.
    """
    require_cross_process_locking()
    try:
        with open(path, "r+b") as probe:
            try:
                fcntl.flock(probe, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except OSError:
                return True
            fcntl.flock(probe, fcntl.LOCK_UN)
            return False
    except OSError:
        return False


def take_lease(path: Path):
    """Take the exclusive lease on this file and return it held, or None when
    another process holds it.

    The one way a lease is taken without waiting: a wait's, a server's, an
    adapter's, a preview slot's, and the barrier a stop takes once the server it
    disabled has exited. The caller holds the returned file for as long as it
    holds the lease and gives it back with `release_lease`; exiting releases it
    too, leaving the file for the next holder to remove. The lease's directory
    must already exist, so a stop naming a page that is gone cannot create it.

    A refused exclusive lock means a lease or a `lock_is_held` question, whose
    shared lock is momentary. A shared lock of its own tells them apart, since
    only a lease refuses one, so a question asked at the instant a lease is taken
    does not turn that lease away.
    """
    require_cross_process_locking()
    path = path.absolute()
    while True:
        record = open(path, "a+b")  # noqa: SIM115 - returned and held by the caller
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


def release_lease(lease) -> None:
    """Give a lease back and remove its file, which only its holder may do.

    The path still names the held file, since nobody else removes a lease while it
    is held; it may already be gone when the state home was cleared by hand."""
    Path(lease.name).unlink(missing_ok=True)
    lease.close()


def release_on_termination() -> None:
    """Turn SIGTERM and SIGHUP into an ordinary exit for a process holding leases.

    Their default action ends the process without unwinding it, which leaves every
    lease file it held for a holder that may never come. Stopping a background
    command, logging out, and shutting down all send one of these, so a `leaf wait`
    or Codex adapter unwinds through the `finally` that releases its leases. Only
    SIGKILL still skips it."""
    for terminating in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(terminating, lambda signum, _frame: sys.exit(128 + signum))


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
    require_cross_process_locking()
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
        os.close(held)


def contract_writer(function):
    """Keep a CLI event's validation and append on one vendored contract, and
    report the append door's refusal the way these writers report their own.

    The door raises, because it is shared with the browser endpoint, which owes
    its caller a status rather than an exit. Every writer this decorates already
    answers its own refusals with `sys.exit`, so a refusal from the door reaches
    the agent as one more line of the same kind."""

    @functools.wraps(function)
    def locked(page_dir: Path, *args, **kwargs):
        with page_locked(page_dir):
            try:
                return function(page_dir, *args, **kwargs)
            except EventRefused as error:
                sys.exit(str(error))

    return locked


def waiter_lease_path(page_dir: Path | None, session_id: str | None) -> Path | None:
    """The one lease a wait holds for its watch set.

    A host wait covers every page its session owns, so its lease belongs to the
    session and takes only its id. Outside a host, a named page is the entire
    watch set and holds a page-local lease. An unnamed bare-shell wait has no
    watch set and no lease.
    """
    if session_id:
        return session_state_path(session_id, "wait")
    return page_dir / WAITER_LOCK if page_dir is not None else None


def adapter_lease_path(session_id: str) -> Path:
    """The live proof for a detached host delivery adapter.

    A wait lease says only that some process can read page events.  The Codex
    Stop hook needs the narrower fact that the process can durably hand those
    events to a later turn after the foreground turn ends, so the adapter holds
    a second lease for exactly that capability.
    """
    return session_state_path(session_id, "adapter")


def session_state_path(session_id: str, suffix: str) -> Path:
    """Address one state-home file belonging to a single host session.

    A host's session id is not a filename, so the session is named by a digest of
    it. Every file one session owns — its leases, their start mark and locks, and a
    Codex task's deliveries and adapter log — is that one name with a different
    suffix, in a directory this creates.
    """
    key = hashlib.sha256(session_id.encode()).hexdigest()[:32]
    return sessions_home() / f"{key}.{suffix}"


def sessions_home() -> Path:
    """The state home's directory of per-session files, created on first use."""
    sessions = state_home() / "sessions"
    sessions.mkdir(exist_ok=True)
    return sessions


def adapter_is_live(session_id: str) -> bool:
    """Whether this session has a detached delivery carrier right now."""
    return lock_is_held(adapter_lease_path(session_id))


def take_session_wait(session_id: str):
    """Take this session's wait lease and mark the wait started, returning both
    held, or None when another wait holds the lease.

    The mark is a lock on `sessions/<id>.started`, held for the wait's life and
    removed when a tool hook names the start (`name_wait_start`), or else when
    the wait ends (`release_session_wait`). Lease and mark
    are taken under the lock naming takes, so a reader sees a wait either not yet
    started or started and marked, never the lease without its mark."""
    lease_path = waiter_lease_path(None, session_id)
    mark_path = session_state_path(session_id, "started")
    with flocked(session_state_path(session_id, "started.lock")):
        lease = take_lease(lease_path)
        if lease is None:
            return None
        mark = open(mark_path, "a+b")  # noqa: SIM115 - held by the wait
        # Readers ask about the mark only under the lock held here, and a wait
        # lets its mark go before its lease, so this never waits.
        fcntl.flock(mark, fcntl.LOCK_EX)
        return lease, mark


def release_session_wait(session_id: str, mark) -> None:
    """Let a wait's start mark go, removing it if no tool hook named the start.

    A foreground wait returns before its hook runs, so nothing names it; the file
    is removed here, under the lock naming takes, rather than left for a later
    reader to find unheld. The wait still holds its lease, so no other wait's mark
    can stand at that name."""
    with flocked(session_state_path(session_id, "started.lock")):
        session_state_path(session_id, "started").unlink(missing_ok=True)
        mark.close()


def name_wait_start(session_id: str) -> bool | None:
    """Whether a wait has started for this session that nothing has named yet,
    naming it if so; None when the wait holding the lease is already named, so no
    other can start while it runs.

    Naming removes the mark, which the wait goes on holding, so a start is named
    once. The question and the removal share one lock across readers: two
    unlinks of one name can both succeed on macOS, so a removal alone does not
    say which reader named it."""
    mark_path = session_state_path(session_id, "started")
    with flocked(session_state_path(session_id, "started.lock")):
        if lock_is_held(mark_path):
            mark_path.unlink()
            return True
        if lock_is_held(waiter_lease_path(None, session_id)):
            return None
        return False


def wait_is_live(page_dir: Path, session_id: str | None) -> bool:
    """Whether this ownership scope's exact wait lease is held now."""
    lease_path = waiter_lease_path(page_dir, session_id)
    return bool(lease_path and lock_is_held(lease_path))
