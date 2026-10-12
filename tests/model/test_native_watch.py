"""The native file watch a wait sleeps on: subscribing to what a pass read,
following claim and lifecycle publications, and re-arming roots that are created or
replaced."""

import os
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from interact_support import STATED_TIMEOUT, append_carried_log_record, record_claim
from leaf import event_log as events_model
from leaf import harness as harness_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as cleanup_model


def test_a_watch_wakes_on_what_its_pass_read_moving(page_dir):
    """Between passes a watch follows the stamps of what the last pass read, so an
    append wakes it in a look rather than on a timer; with nothing moved it wakes
    on its timeout, for what a pass owes the clock.

    The first pass finds a page the mark before it did not know, so it returns at
    once: that mark stamped the old set."""
    watch = session_model.Watch(None, pages=(page_dir,))
    assert watch.acquire()
    try:
        mark = watch.mark()
        list(watch.tick())
        assert watch.await_news(mark, timeout=STATED_TIMEOUT), (
            "the watch never woke on the page its mark had not read"
        )

        # With nothing moved, the watch wakes on its timeout: that expiry is the
        # subject, and how long it is changes nothing a slower machine could see.
        quiet = 0.2
        mark = watch.mark()
        list(watch.tick())
        assert not watch.await_news(mark, timeout=quiet)

        mark = watch.mark()
        list(watch.tick())
        appending = threading.Timer(
            0.2,
            append_carried_log_record,
            (page_dir, {"kind": "comment", "author": "user", "text": "hi"}),
        )
        appending.start()
        assert watch.await_news(mark, timeout=STATED_TIMEOUT), (
            "the watch never woke on the append"
        )
        appending.join()
        assert events_model.read_events(page_dir)[-1]["text"] == "hi"
    finally:
        watch.release()


# This interval is the subject of diagnostic absence assertions, not a deadline
# for native scheduling; their later positive write is bounded by STATED_TIMEOUT.
DIAGNOSTIC_QUIET_WINDOW_S = 0.2


def test_a_quiet_native_watch_discovers_claim_transfer_and_nested_source_edits(
    page_dir, monkeypatch
):
    """Subscriptions cover ownership replacement and in-place authored writes.

    Atomic diagnostics are excluded, so a tab's housekeeping cannot wake the
    delivery loop. Transfer is published outside this adapter's process, under
    the same page lease as an ordinary acquisition.
    """
    record_claim(page_dir, id="native-owner")
    watch = session_model.Watch(
        harness_model.ClaudeCodeHarness("native-owner", "Claude")
    )
    assert watch.acquire()
    try:
        list(watch.tick())
        mark = watch.mark()
        cleanup_model.write_json(page_dir / "user-views.json", {"diagnostic": True})
        assert not watch.await_news(mark, timeout=DIAGNOSTIC_QUIET_WINDOW_S)
        source = page_dir / "page" / "nested"
        source.mkdir(parents=True)
        module = source / "state.js"
        _write_during_native_wait(
            watch, lambda: module.write_text("export const n = 1;"), monkeypatch
        )
        _write_during_native_wait(
            watch, lambda: module.write_text("export const n = 2;"), monkeypatch
        )
        _write_during_native_wait(
            watch, lambda: record_claim(page_dir, id="native-successor"), monkeypatch
        )
        assert list(watch.tick()) == []
        assert service_model.claim_records("native-owner") == []
    finally:
        watch.release()


def _write_during_native_wait(watch, write, monkeypatch):
    """Publish after the watch's comparison has completed and native waiting begins."""
    mark = watch.mark()
    entered = threading.Event()
    original = watch.changes.wait

    def waiting(*args):
        entered.set()
        return original(*args)

    with monkeypatch.context() as observation:
        observation.setattr(watch.changes, "wait", waiting)
        with ThreadPoolExecutor(max_workers=1) as executor:
            waiting_result = executor.submit(watch.await_news, mark, STATED_TIMEOUT)
            assert entered.wait(STATED_TIMEOUT), (
                "the page watch never entered native waiting"
            )
            write()
            assert waiting_result.result(timeout=STATED_TIMEOUT), (
                "the publication did not wake the native watch"
            )


def test_an_explicit_native_watch_follows_foreign_claim_and_lifecycle_publications(
    page_dir, monkeypatch
):
    """An explicit page's dependencies belong to its claimant, not its observer.

    A release replaces the canonical payload without changing the session locator;
    a transfer changes the discovery locator and referenced lifecycle. Subsequent
    marks must subscribe the new targets even though the watched page stays put.
    """
    record_claim(page_dir, id="foreign-owner")
    watch = session_model.Watch(None, pages=(page_dir,))
    assert watch.acquire()
    try:
        list(watch.tick())

        _write_during_native_wait(
            watch, lambda: cleanup_model.end_session("foreign-owner"), monkeypatch
        )
        _write_during_native_wait(
            watch, lambda: record_claim(page_dir, id="foreign-successor"), monkeypatch
        )
        _write_during_native_wait(
            watch,
            lambda: cleanup_model.close_session_turn("foreign-successor"),
            monkeypatch,
        )
        mark = watch.mark()
        cleanup_model.write_json(page_dir / "user-views.json", {"diagnostic": True})
        assert not watch.await_news(mark, timeout=DIAGNOSTIC_QUIET_WINDOW_S)
    finally:
        watch.release()


@pytest.mark.parametrize("previous_owner", [None, "previous-owner"])
def test_failed_claim_discovery_publication_preserves_ownership(
    page_dir, monkeypatch, previous_owner
):
    """A claim cannot commit before its owner can discover it."""
    if previous_owner:
        record_claim(page_dir, id=previous_owner)
    before = service_model.page_claim(page_dir)
    locator = (
        service_model.session_claims("successor")
        / service_model.claim_path(page_dir).name
    )
    replace = service_model.os.replace

    def unavailable_locator(source, target):
        if Path(target) == locator:
            raise OSError("discovery publication interrupted")
        return replace(source, target)

    with monkeypatch.context() as interrupted:
        interrupted.setattr(service_model.os, "replace", unavailable_locator)
        with pytest.raises(OSError, match="discovery publication interrupted"):
            record_claim(page_dir, id="successor")
    assert service_model.page_claim(page_dir) == before
    assert service_model.owned_pages("successor") == []
    if previous_owner:
        assert service_model.owned_pages(previous_owner) == [page_dir]


@pytest.mark.parametrize("preparation_phase", ["waiting", "subscribing"])
def test_native_watch_follows_a_prepared_claim_until_ownership_commits(
    page_dir, monkeypatch, preparation_phase
):
    """Discovery preparation and ownership commit can straddle a watch pass."""
    record_claim(page_dir, id="previous-owner")
    cleanup_model.ensure_session("successor", {"pid": os.getpid()})
    harness = harness_model.ClaudeCodeHarness("successor", "Claude")
    prepared = service_model.prepare_claim(harness, page_dir)
    partition = service_model.session_claims("successor")
    partition.mkdir(parents=True)
    watch = session_model.Watch(harness)
    assert watch.acquire()
    commit_entered = threading.Event()
    allow_commit = threading.Event()
    write_json = service_model.write_json

    def held_commit(path, value):
        if path == service_model.claim_path(page_dir):
            commit_entered.set()
            assert allow_commit.wait(STATED_TIMEOUT), (
                "ownership commit was not released"
            )
        return write_json(path, value)

    try:
        list(watch.tick())
        with monkeypatch.context() as publication:
            publication.setattr(service_model, "write_json", held_commit)
            with ThreadPoolExecutor(max_workers=1) as executor:
                try:

                    def prepare():
                        publishing = executor.submit(
                            service_model.publish_claim, page_dir, prepared
                        )
                        assert commit_entered.wait(STATED_TIMEOUT), (
                            "claim publisher did not reach the ownership commit"
                        )
                        return publishing

                    if preparation_phase == "subscribing":
                        changes = session_model.FileChanges
                        publications = []

                        def subscribing(*args):
                            subscribed = changes(*args)
                            publications.append(prepare())
                            return subscribed

                        with monkeypatch.context() as registration:
                            registration.setattr(
                                session_model, "FileChanges", subscribing
                            )
                            mark = watch.mark()
                        (publishing,) = publications
                    else:
                        mark = watch.mark()
                        publishing = prepare()
                    assert (
                        partition / service_model.claim_path(page_dir).name
                    ).is_symlink()
                    assert service_model.owned_pages("successor") == []
                    assert watch.await_news(mark, timeout=STATED_TIMEOUT)
                    assert list(watch.tick()) == []
                    # Reconnect to the prepared discovery set, then consume any
                    # preparation notifications before the later commit.
                    watch.mark()
                    while watch.changes.wait(watch.changes.mark(), 0.1):
                        pass
                    _write_during_native_wait(watch, allow_commit.set, monkeypatch)
                    publishing.result(timeout=STATED_TIMEOUT)
                    assert watch.pages() == [page_dir]
                finally:
                    allow_commit.set()
    finally:
        watch.release()


def test_native_watch_rearms_a_session_partition_created_after_startup(
    page_dir, tmp_path, monkeypatch
):
    record_claim(page_dir, id="explicit-foreign")
    cleanup_model.ensure_session("new-partition", {"pid": os.getpid()})
    watch = session_model.Watch(
        harness_model.ClaudeCodeHarness("new-partition", "Claude"), pages=(page_dir,)
    )
    assert watch.acquire()
    try:
        list(watch.tick())
        mark = watch.mark()
        partition = service_model.session_claims("new-partition")
        assert not partition.exists()
        partition.mkdir()
        assert watch.changes.wait(mark[2], STATED_TIMEOUT)
        # Consume creation before reconnecting; a delayed mkdir event must not
        # masquerade as notification of the later locator publication.
        while watch.changes.wait(watch.changes.mark(), 0.1):
            pass
        watch.mark()
        new_page = tmp_path / "later-acquisition"
        new_page.mkdir()
        (new_page / "events.jsonl").touch()
        prepared = service_model.prepare_claim(watch.harness, new_page)
        _write_during_native_wait(
            watch, lambda: service_model.publish_claim(new_page, prepared), monkeypatch
        )
        assert new_page in watch.pages()
    finally:
        watch.release()


def test_shared_page_native_owner_rearms_created_and_replaced_directories(
    tmp_path, monkeypatch
):
    from leaf.file_changes import _PageChanges

    page = tmp_path / "later-page"
    owner = _PageChanges()
    initial = owner.connect(page)
    page.mkdir()
    source = page / "page"
    source.mkdir()
    module = source / "index.html"
    module.write_text("initial authored input")
    changes = owner.connect(page)
    assert changes is not initial
    assert all(not thread.is_alive() for thread in initial.threads)
    try:
        while changes.wait(changes.mark(), 0.1):
            pass
        mark = changes.mark()
        with ThreadPoolExecutor(max_workers=1) as executor:
            waiting = executor.submit(changes.wait, mark, STATED_TIMEOUT)
            module.write_text("later authored input")
            assert waiting.result(timeout=STATED_TIMEOUT)
        descriptor = changes.roots[page][1]
        previous_identity = os.fstat(descriptor)
        shutil.rmtree(page)
        page.mkdir()
        current_identity = page.stat()
        assert (previous_identity.st_dev, previous_identity.st_ino) != (
            current_identity.st_dev,
            current_identity.st_ino,
        ), "the subscribed directory descriptor must prevent inode reuse"
        closed = []
        real_close = os.close

        def closing(descriptor):
            closed.append(descriptor)
            real_close(descriptor)

        with monkeypatch.context() as observation:
            observation.setattr(os, "close", closing)
            replacement = owner.connect(page)
        assert replacement is not changes
        assert descriptor in closed
        assert all(not thread.is_alive() for thread in changes.threads)
        source = page / "page"
        source.mkdir()
        mark = replacement.mark()
        with ThreadPoolExecutor(max_workers=1) as executor:
            waiting = executor.submit(replacement.wait, mark, STATED_TIMEOUT)
            (source / "after-replacement.html").write_text("replacement authored input")
            assert waiting.result(timeout=STATED_TIMEOUT)
    finally:
        owner.release()


def test_session_native_watch_pins_roots_until_replacement(page_dir, monkeypatch):
    """The native provider holds an inode while the pathname is replaced."""
    watch = session_model.Watch(None, pages=(page_dir,))
    assert watch.acquire()
    try:
        list(watch.tick())
        watch.mark()
        previous = watch.changes
        descriptor = previous.roots[page_dir][1]
        held = os.fstat(descriptor)
        shutil.rmtree(page_dir)
        page_dir.mkdir()
        current = page_dir.stat()
        assert (held.st_dev, held.st_ino) != (current.st_dev, current.st_ino)
        watch.mark()
        assert watch.changes is not previous
        assert all(not thread.is_alive() for thread in previous.threads)
    finally:
        watch.release()


@pytest.mark.parametrize("failure", ["directory", "provider"])
def test_native_subscription_releases_partial_startup_resources(
    tmp_path, monkeypatch, failure
):
    from leaf import file_changes

    shallow, tree = tmp_path / "shallow", tmp_path / "tree"
    shallow.mkdir()
    tree.mkdir()
    opened, readers = [], []
    real_open, real_thread, real_native = (
        os.open,
        threading.Thread,
        file_changes.RustNotify,
    )

    def opening(*args, **kwargs):
        if failure == "directory" and opened:
            raise RuntimeError("directory installation refused")
        descriptor = real_open(*args, **kwargs)
        opened.append(descriptor)
        return descriptor

    def thread(*args, **kwargs):
        reader = real_thread(*args, **kwargs)
        readers.append(reader)
        return reader

    providers = []

    def installing(*args, **kwargs):
        if failure == "provider" and providers:
            raise RuntimeError("provider installation refused")
        provider = real_native(*args, **kwargs)
        providers.append(provider)
        return provider

    monkeypatch.setattr(os, "open", opening)
    monkeypatch.setattr(file_changes.threading, "Thread", thread)
    monkeypatch.setattr(file_changes, "RustNotify", installing)
    with pytest.raises(RuntimeError, match="installation refused"):
        file_changes.FileChanges({shallow: False, tree: True}, lambda _path: True)
    assert opened
    for descriptor in opened:
        with pytest.raises(OSError):
            os.fstat(descriptor)
    assert all(not reader.is_alive() for reader in readers)


def test_native_subscription_rearms_a_root_replaced_during_installation(
    tmp_path, monkeypatch
):
    """A replacement between pinning and native installation invalidates the plan."""
    from leaf import file_changes

    page = tmp_path / "installing"
    page.mkdir()
    real_native = file_changes.RustNotify
    installations = []

    def installing(*args, **kwargs):
        if not installations:
            page.rmdir()
            page.mkdir()
        installations.append(args)
        return real_native(*args, **kwargs)

    owner = file_changes._PageChanges()
    monkeypatch.setattr(file_changes, "RustNotify", installing)
    try:
        initial = owner.connect(page)
        assert not initial.matches(
            {path: nested for path, (nested, _fd) in initial.roots.items()}
        )
        replacement = owner.connect(page)
        assert replacement is not initial
        assert all(not reader.is_alive() for reader in initial.threads)
        roots = {path: nested for path, (nested, _fd) in replacement.roots.items()}
        assert replacement.matches(roots)
        (page / "diagnostic.json").write_text("{}")
        assert owner.connect(page) is replacement, (
            "a child edit must not rearm its root"
        )
        descriptors = [fd for _nested, fd in replacement.roots.values()]
        replacement.close()
        replacement.close()
        assert not replacement.matches(roots)
        for descriptor in descriptors:
            with pytest.raises(OSError):
                os.fstat(descriptor)
    finally:
        if owner.release is not None:
            owner.release()


def test_shared_native_page_owner_survives_held_memory_and_closes_on_eviction(
    page_dir, tmp_path, monkeypatch
):
    import gc

    from leaf import page_memory
    from leaf.file_changes import page_changes

    monkeypatch.setattr(page_memory, "_memories", page_memory.PageMemories())
    retained = page_memory.memory_of(page_dir)
    changes = page_changes(page_dir)
    try:
        for n in range(9):
            page_memory.memory_of(tmp_path / f"gallery-{n}")
        assert page_changes(page_dir) is changes
        del retained
        for n in range(9):
            page_memory.memory_of(tmp_path / f"later-gallery-{n}")
        gc.collect()
        assert all(not thread.is_alive() for thread in changes.threads)
    finally:
        changes.close()
