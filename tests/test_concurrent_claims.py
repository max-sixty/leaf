"""Ownership discovery must not mutate a claim that a new page has acquired."""

import fcntl
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

from interact_support import STATED_TIMEOUT, record_claim
from leaf import service
from leaf.service import claim_path, claim_records, page_claim
from leaf.state import flocked


def test_session_discovery_reads_only_its_canonical_claim_partition(
    tmp_path, monkeypatch
):
    """One idle adapter must not read the pages every other session acquired.

    The original flat discovery opened all 313 records per pass. Session lookup
    now opens only its own four, including after another session transfers one.
    """
    pages = []
    for n in range(313):
        page = tmp_path / str(n)
        page.mkdir()
        record_claim(page, id="own" if n < 4 else "other")
        if n < 4:
            pages.append(page)
    reads = []
    read_json = service.read_json

    def own_read(path):
        assert path.parent == service.session_claims("own"), path
        reads.append(path)
        return read_json(path)

    with monkeypatch.context() as measured:
        measured.setattr(service, "read_json", own_read)
        assert {Path(record["page"]) for record in claim_records("own")} == set(pages)
    assert len(reads) == 4
    record_claim(pages[0], id="successor")
    assert {Path(record["page"]) for record in claim_records("own")} == set(pages[1:])
    assert claim_records("successor")[0]["page"] == str(pages[0])


def test_resident_flat_claim_updates_preserve_session_discovery(page_dir):
    """Resident HTTP writers atomically replace the same canonical payload."""
    page = page_dir
    record_claim(page, id="prior")
    canonical = claim_path(page)
    prior_locator = service.session_claims("prior") / canonical.name
    assert canonical.is_file() and not canonical.is_symlink()
    assert prior_locator.is_symlink()
    with service.PageTransaction(page) as transaction:
        transaction.note_messaged("idle-turn-ending")
    assert claim_records("prior")[0]["messaged_ending"] == "idle-turn-ending"
    assert prior_locator.is_symlink()
    record_claim(page, id="successor")
    # A delayed old alias is only a locator, never successor ownership in prior.
    prior_locator.symlink_to(Path("..") / canonical.name)
    assert claim_records("prior") == []
    assert [claim["id"] for claim in claim_records()] == ["successor"]
    successor_locator = service.session_claims("successor") / canonical.name
    successor_locator.unlink()
    # Global observation reads the canonical facts even before locator refresh.
    assert [claim["id"] for claim in claim_records()] == ["successor"]


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
