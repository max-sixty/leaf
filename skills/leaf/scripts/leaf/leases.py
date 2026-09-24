"""Process-backed locks and leases for page and session transitions."""

import functools
import hashlib
import sys
from pathlib import Path

from leaf.event_log import (
    EventRefused,
    flocked,
    label_locked,
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


def take_lease(path: Path, label: str | None = None):
    """Take the exclusive lease on this file and return it held, or None when
    another process holds it.

    The one way a lease is taken without waiting: a wait's, a server's, an
    adapter's, a preview slot's, and the barrier a stop takes once the server it
    disabled has exited. The caller holds the returned file for as long as it
    holds the lease; closing it, or exiting, releases it. The lease's directory
    must already exist, so a stop naming a page that is gone cannot create it.

    A refused exclusive lock means a lease or a `lock_is_held` question, whose
    shared lock is momentary. A shared lock of its own tells them apart, since
    only a lease refuses one, so a question asked at the instant a lease is taken
    does not turn that lease away.

    A lease file removed between the open and the lock is taken again on the path's
    new file, and a `label` is written once held, as `flocked` does.
    """
    require_cross_process_locking()
    while True:
        record = open(path, "a+b")  # noqa: SIM115 - returned and held by the caller
        while True:
            try:
                fcntl.flock(record, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                try:
                    fcntl.flock(record, fcntl.LOCK_SH | fcntl.LOCK_NB)
                except BlockingIOError:
                    record.close()
                    return None
                fcntl.flock(record, fcntl.LOCK_UN)
        if names_locked(path, record):
            label_locked(record, label)
            return record
        record.close()


def retire_lock(path: Path) -> None:
    """Remove this lock or lease file if no process holds it.

    Its lock is taken, without waiting, before the file goes, so a holder keeps
    it; the file goes while that lock is held, so a process that opened it
    meanwhile finds it unnamed once its own lock succeeds, and takes the lock
    again on a new file (`names_locked`). A leaf too old to ask that would hold
    the removed file beside a new holder of its successor if it opened the file
    between this lock and the removal, so a caller removes only a lock no such
    leaf has reason to open (`sweep`)."""
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

    The key says nothing about which page, so a lock is held through
    `page_locked` or `take_page_lease`, which write the page's path into it for
    `sweep` to tell when that page is gone.
    """
    locks = state_home() / "page-locks"
    locks.mkdir(exist_ok=True)
    key = hashlib.sha256(str(page_dir.resolve()).encode()).hexdigest()[:32]
    return locks / f"{key}.{purpose}.lock"


def page_locked(page_dir: Path, purpose: str = "transition"):
    """Hold one of this page's locks while the block runs (`page_lock`)."""
    return flocked(page_lock(page_dir, purpose), label=str(page_dir.resolve()))


def take_page_lease(page_dir: Path, purpose: str):
    """Take one of this page's locks as a lease (`take_lease`, `page_lock`)."""
    return take_lease(page_lock(page_dir, purpose), label=str(page_dir.resolve()))


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


def take_session_wait(session_id: str):
    """Take this session's wait lease and mark the wait started, returning both
    held, or None when another wait holds the lease.

    The mark is a lock on `sessions/<id>.started`, held for the wait's life and
    removed when a tool hook names the start (`name_wait_start`). Lease and mark
    are taken under the lock naming takes, so a reader sees a wait either not yet
    started or started and marked, never the lease without its mark."""
    lease_path = waiter_lease_path(None, session_id)
    mark_path = _session_lease(session_id, "started")
    with flocked(_session_lease(session_id, "started.lock")):
        lease = take_lease(lease_path)
        if lease is None:
            return None
        mark = open(mark_path, "a+b")  # noqa: SIM115 - held by the wait
        # Readers ask about the mark only under the lock held here, and a wait
        # lets its mark go before its lease, so this never waits.
        fcntl.flock(mark, fcntl.LOCK_EX)
        return lease, mark


def name_wait_start(session_id: str) -> bool | None:
    """Whether a wait has started for this session that nothing has named yet,
    naming it if so; None when the wait holding the lease is already named, so no
    other can start while it runs.

    Naming removes the mark, which the wait goes on holding, so a start is named
    once. The question and the removal share one lock across readers: two
    unlinks of one name can both succeed on macOS, so a removal alone does not
    say which reader named it."""
    mark_path = _session_lease(session_id, "started")
    with flocked(_session_lease(session_id, "started.lock")):
        if lock_is_held(mark_path):
            mark_path.unlink()
            return True
        if lock_is_held(waiter_lease_path(None, session_id)):
            return None
        return False


def retire_start_mark(mark: Path) -> None:
    """Remove a wait's start mark once no wait holds it.

    A wait that ends before any tool hook names its start (a foreground wait,
    which returns before its hook runs) leaves the file behind, and a mark no wait
    holds already reads as no mark (`name_wait_start`). Every writer and reader of
    a mark takes its naming lock first, so removing it under that lock meets none
    of them halfway, whichever version they run."""
    with flocked(mark.with_name(f"{mark.name}.lock")):
        if not lock_is_held(mark):
            mark.unlink(missing_ok=True)


def wait_is_live(page_dir: Path, session_id: str | None) -> bool:
    """Whether this ownership scope's exact wait lease is held now."""
    lease_path = waiter_lease_path(page_dir, session_id)
    return bool(lease_path and lock_is_held(lease_path))
