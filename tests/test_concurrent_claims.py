"""Ownership discovery must not mutate a claim that a new page has acquired."""

import fcntl
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

from interact_support import STATED_TIMEOUT, record_claim
from leaf.service import claim_path, claim_records, page_claim
from leaf.state import flocked


def test_a_scan_of_a_missing_page_preserves_its_concurrent_successor(
    tmp_path, monkeypatch
):
    page = tmp_path / "recreated"
    prior = record_claim(page, id="prior")
    assert claim_records() == []
    assert page_claim(page) == prior

    observed_missing = Event()
    successor_written = Event()
    is_dir = Path.is_dir

    def observe_before_recreation(path):
        exists = is_dir(path)
        if path == page and not exists:
            observed_missing.set()
            assert successor_written.wait(STATED_TIMEOUT), (
                "successor did not acquire the page"
            )
        return exists

    monkeypatch.setattr(Path, "is_dir", observe_before_recreation)
    with ThreadPoolExecutor(max_workers=1) as executor:
        scan = executor.submit(claim_records)
        try:
            assert observed_missing.wait(STATED_TIMEOUT), (
                "scan did not observe the missing page"
            )
            page.mkdir()
            successor = record_claim(page, id="successor")
        finally:
            successor_written.set()
        assert scan.result(timeout=STATED_TIMEOUT) == []

    assert claim_path(page).exists()
    assert page_claim(page) == successor
    assert claim_records("successor") == [successor]


def test_a_waiting_page_transaction_follows_a_recreated_page(tmp_path, monkeypatch):
    page = tmp_path / "page"
    page.mkdir()
    log = page / "events.jsonl"
    log.write_bytes(b"old")
    opened_old_log = Event()
    lock = fcntl.flock

    def observe_waiter(stream, operation):
        if operation == fcntl.LOCK_EX:
            opened_old_log.set()
        return lock(stream, operation)

    def read():
        with flocked(log) as stream:
            return stream.read()

    with ThreadPoolExecutor(max_workers=1) as executor:
        with log.open("r+b") as owner:
            lock(owner, fcntl.LOCK_EX)
            monkeypatch.setattr(fcntl, "flock", observe_waiter)
            waiter = executor.submit(read)
            assert opened_old_log.wait(STATED_TIMEOUT), (
                "waiter did not open the old page log"
            )
            page.rename(tmp_path / "previous-page")
            page.mkdir()
            log.write_bytes(b"new")
        assert waiter.result(timeout=STATED_TIMEOUT) == b"new"
    assert log.read_bytes() == b"new"
