"""Process-backed locks and leases for page and session transitions."""

import functools
import hashlib
import sys
from pathlib import Path

from leaf.event_log import (
    EventRefused,
    flocked,
    names_locked,
    require_cross_process_locking,
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
    holds the lease; closing it, or exiting, releases it. The lease's directory
    must already exist, so a stop naming a page that is gone cannot create it.

    A lease file removed between the open and the lock is taken again on the path's
    new file, as `flocked` does (`names_locked`).
    """
    require_cross_process_locking()
    while True:
        record = open(path, "a+b")  # noqa: SIM115 - returned and held by the caller
        try:
            fcntl.flock(record, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            record.close()
            return None
        if names_locked(path, record):
            return record
        record.close()


def retire_lock(path: Path) -> None:
    """Remove this lock or lease file if no process holds it.

    Its lock is taken, without waiting, before the file goes, so a holder keeps
    it; the file goes while that lock is held, so a process that opened it
    meanwhile finds it unnamed once its own lock succeeds, and takes the lock
    again on a new file (`names_locked`). A leaf too old to ask that could hold
    the removed file beside a new holder of its successor, but only by opening
    the file inside the few microseconds between this lock and the removal.
    Those same microseconds are the one moment a `take_lease` or a
    `lock_is_held` meets this lock rather than a holder's."""
    require_cross_process_locking()
    try:
        record = open(path, "r+b")  # noqa: SIM115 - closed by the with below
    except FileNotFoundError:
        return
    with record:
        try:
            fcntl.flock(record, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        if names_locked(path, record):
            path.unlink()


def page_lock(page_dir: Path, purpose: str) -> Path:
    """A stable lock for one page, outside the page it guards.

    `page init` must reject a package input without writing into it, so
    locks that can meet init cannot live in the prospective page directory. The
    resolved path gives every process the same lock while the purpose keeps the
    contract transition independent from the page's current session claim.
    One is minted for every page path a command transitions, so `sweep`
    removes each while nothing holds it.
    """
    locks = state_home() / "page-locks"
    locks.mkdir(exist_ok=True)
    key = hashlib.sha256(str(page_dir.resolve()).encode()).hexdigest()[:32]
    return locks / f"{key}.{purpose}.lock"


def transition_lock(page_dir: Path) -> Path:
    """Serialize service changes, re-vendoring, and contract-bearing writes."""
    return page_lock(page_dir, "transition")


def contract_writer(function):
    """Keep a CLI event's validation and append on one vendored contract, and
    report the append door's refusal the way these writers report their own.

    The door raises, because it is shared with the browser endpoint, which owes
    its caller a status rather than an exit. Every writer this decorates already
    answers its own refusals with `sys.exit`, so a refusal from the door reaches
    the agent as one more line of the same kind."""

    @functools.wraps(function)
    def locked(page_dir: Path, *args, **kwargs):
        with flocked(transition_lock(page_dir)):
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
        return _session_lease(session_id, "wait")
    return page_dir / WAITER_LOCK if page_dir is not None else None


def adapter_lease_path(session_id: str) -> Path:
    """The live proof for a detached host delivery adapter.

    A wait lease says only that some process can read page events.  The Codex
    Stop hook needs the narrower fact that the process can durably hand those
    events to a later turn after the foreground turn ends, so the adapter holds
    a second lease for exactly that capability.
    """
    return _session_lease(session_id, "adapter")


def _session_lease(session_id: str, purpose: str) -> Path:
    sessions = state_home() / "sessions"
    sessions.mkdir(exist_ok=True)
    return sessions / f"{session_id}.{purpose}"


def adapter_is_live(session_id: str) -> bool:
    """Whether this session has a detached delivery carrier right now."""
    return lock_is_held(adapter_lease_path(session_id))


def started_wait(session_id: str) -> str | None:
    """The start of the wait holding this session's lease, or None while none does.

    Only the wait knows it started: a shell command that runs one can spell the
    launcher any way the shell allows (`$LEAF wait`, `uv run leaf wait`), so a
    reader that needs to know one began asks the lease rather than the command."""
    path = waiter_lease_path(None, session_id)
    if not lock_is_held(path):
        return None
    try:
        return path.read_text() or None
    except OSError:
        return None


def wait_is_live(page_dir: Path, session_id: str | None) -> bool:
    """Whether this ownership scope's exact wait lease is held now."""
    lease_path = waiter_lease_path(page_dir, session_id)
    return bool(lease_path and lock_is_held(lease_path))
