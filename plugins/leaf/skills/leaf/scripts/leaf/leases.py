"""Process-backed locks and leases for page and session transitions."""

import functools
import hashlib
from pathlib import Path

from leaf.event_log import flocked, require_cross_process_locking
from leaf.host import state_home
from leaf.locations import page_key

try:
    import fcntl
except ImportError:  # pragma: no cover - rejected before a lease is read or taken
    fcntl = None


def lock_is_held(path: Path) -> bool:
    """Whether an exclusive lease is held on this file.

    The kernel releases the lease on exit, crash, or reboot. A durable record
    can therefore outlive its writer without being mistaken for a live process.
    """
    require_cross_process_locking()
    try:
        with open(path, "r+b") as probe:
            try:
                fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return True
            fcntl.flock(probe, fcntl.LOCK_UN)
            return False
    except OSError:
        return False


def page_lock(page_dir: Path, purpose: str) -> Path:
    """A stable lock for one page, outside the page it guards.

    `page init` must reject a package input without writing into it, so
    locks that can meet init cannot live in the prospective page directory. The
    resolved path gives every process the same lock while the purpose keeps the
    contract transition independent from the page's current session claim.
    """
    locks = state_home() / "page-locks"
    locks.mkdir(exist_ok=True)
    key = hashlib.sha256(str(page_dir.resolve()).encode()).hexdigest()[:32]
    return locks / f"{key}.{purpose}.lock"


def transition_lock(page_dir: Path) -> Path:
    """Serialize service changes, re-vendoring, and contract-bearing writes."""
    return page_lock(page_dir, "transition")


def init_lock_path(page_dir: Path) -> Path:
    """The lease serializing creation before a page has its own transaction."""
    return state_home() / "init" / f"{page_key(page_dir)}.lock"


def contract_writer(function):
    """Keep a CLI event's validation and append on one vendored contract."""

    @functools.wraps(function)
    def locked(page_dir: Path, *args, **kwargs):
        with flocked(transition_lock(page_dir)):
            return function(page_dir, *args, **kwargs)

    return locked


def waiter_lease_path(page_dir: Path | None, session: dict | None) -> Path | None:
    """The one lease a wait holds for its watch set.

    A host wait covers every page its session owns, so its lease belongs to the
    session. Outside a host, a named page is the entire watch set and holds a
    page-local lease. An unnamed bare-shell wait has no watch set and no lease.
    """
    if session:
        return state_home() / "sessions" / f"{session['id']}.wait"
    return page_dir / "waiter.lock" if page_dir is not None else None


def adapter_lease_path(session_id: str) -> Path:
    """The live proof for a detached host delivery adapter.

    A wait lease says only that some process can read page events.  The Codex
    Stop hook needs the narrower fact that the process can durably hand those
    events to a later turn after the foreground turn ends, so the adapter holds
    a second lease for exactly that capability.
    """
    return state_home() / "sessions" / f"{session_id}.adapter"


def adapter_is_live(session_id: str) -> bool:
    """Whether this session has a detached delivery carrier right now."""
    return lock_is_held(adapter_lease_path(session_id))


def take_waiter_lease(path: Path):
    """Take and return a wait lease, or None when another wait already holds it."""
    require_cross_process_locking()
    path.parent.mkdir(parents=True, exist_ok=True)
    record = open(path, "a+b")  # noqa: SIM115 - returned and held for the wait's life
    try:
        fcntl.flock(record, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        record.close()
        return None
    return record


def wait_is_live(page_dir: Path, session: dict | None) -> bool:
    """Whether this ownership scope's exact wait lease is held now."""
    lease_path = waiter_lease_path(page_dir, session)
    return bool(lease_path and lock_is_held(lease_path))
