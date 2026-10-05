"""A lock names one shared path even when its inode changes before acquisition."""

import fcntl
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from interact_support import STATED_TIMEOUT
from leaf import leases, state


def test_a_waiting_purpose_lock_follows_a_removed_holder(tmp_path, monkeypatch):
    path = tmp_path / "purpose.lock"
    waiting, entered, release = Event(), Event(), Event()
    lock = fcntl.flock

    def observed(stream, operation):
        if operation == fcntl.LOCK_EX:
            waiting.set()
        return lock(stream, operation)

    def wait():
        with state.flocked(path) as stream:
            assert state.still_named(stream.fileno(), path)
            entered.set()
            assert release.wait(STATED_TIMEOUT)

    with ThreadPoolExecutor(max_workers=1) as executor:
        with path.open("a+b") as prior:
            lock(prior, fcntl.LOCK_EX)
            monkeypatch.setattr(fcntl, "flock", observed)
            waiter = executor.submit(wait)
            assert waiting.wait(STATED_TIMEOUT), (
                "waiter did not open the prior holder's inode"
            )
            path.unlink()
        try:
            assert entered.wait(STATED_TIMEOUT), (
                "waiter did not acquire the currently named lock"
            )
            assert leases.take_lease(path) is None
        finally:
            release.set()
        waiter.result(timeout=STATED_TIMEOUT)
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
        assert state.still_named(lease.fileno(), path)
        assert leases.take_lease(path) is None
    finally:
        leases.release_lease(lease)
    assert replaced
    assert path.exists()


def test_a_released_lease_is_free_while_a_child_still_holds_its_descriptor(
    tmp_path, spawn
):
    """A holder that starts subprocesses lends each one its descriptors until the
    child's exec closes them, and a busy machine can hold a child there long after
    the holder lets go. A released lease must read free all the same: a page
    server's title subprocess outliving a `leaf wait` the test ran in-process left
    the wait reading live, so a user's comment messaged nobody. This child keeps the
    descriptor until the test ends."""
    path = tmp_path / "lease"
    lease = leases.take_lease(path)
    assert lease is not None
    child = spawn(
        [sys.executable, "-c", "import sys; sys.stdin.read()"],
        stdin=subprocess.PIPE,
        pass_fds=[lease.fileno()],
    )
    leases.release_lease(lease)
    assert not leases.lock_is_held(path)
    assert child.poll() is None
