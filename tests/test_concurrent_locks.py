"""A lock names one shared path even when its inode changes before acquisition."""

import fcntl
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from leaf import leases, session_cleanup


def test_a_waiting_purpose_lock_follows_a_removed_holder(tmp_path, monkeypatch):
    path = tmp_path / "purpose.lock"
    waiting, entered, release = Event(), Event(), Event()
    lock = fcntl.flock

    def observed(stream, operation):
        if operation == fcntl.LOCK_EX:
            waiting.set()
        return lock(stream, operation)

    def wait():
        with session_cleanup.flocked(path) as stream:
            assert session_cleanup.still_named(stream.fileno(), path)
            entered.set()
            assert release.wait(10)

    with ThreadPoolExecutor(max_workers=1) as executor:
        with path.open("a+b") as prior:
            lock(prior, fcntl.LOCK_EX)
            monkeypatch.setattr(fcntl, "flock", observed)
            waiter = executor.submit(wait)
            assert waiting.wait(10), "waiter did not open the prior holder's inode"
            path.unlink()
        try:
            assert entered.wait(10), "waiter did not acquire the currently named lock"
            assert leases.take_lease(path) is None
        finally:
            release.set()
        waiter.result(timeout=10)
    assert path.exists()
    assert not leases.lock_is_held(path)


def test_a_lease_follows_a_path_replaced_before_acquisition(tmp_path, monkeypatch):
    path = tmp_path / "lease"
    lock = fcntl.flock
    replaced = False

    def replace_before_acquisition(stream, operation):
        nonlocal replaced
        if not replaced and operation == fcntl.LOCK_EX | fcntl.LOCK_NB:
            replaced = True
            path.unlink()
            path.touch()
        return lock(stream, operation)

    monkeypatch.setattr(fcntl, "flock", replace_before_acquisition)
    lease = leases.take_lease(path)
    assert lease is not None
    try:
        assert session_cleanup.still_named(lease.fileno(), path)
        assert leases.take_lease(path) is None
    finally:
        leases.release_lease(lease)
    assert replaced
    assert path.exists()
