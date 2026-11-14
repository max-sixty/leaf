"""The native file watch a wait sleeps on: subscribing to what a pass read,
following claim and lifecycle publications, and re-arming roots that are created or
replaced."""

import contextlib
import errno
import json
import os
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from interact_support import (
    STATED_TIMEOUT,
    append_carried_log_record,
    record_claim,
    write_record,
)

from leaf import event_log as events_model
from leaf import harness as harness_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as cleanup_model


@pytest.fixture
def native(monkeypatch):
    """Observers of this test's own, so what it counts, inspects or breaks meets no
    subscription an earlier test left open in the process."""
    from leaf import file_changes

    owned = file_changes._Native()
    monkeypatch.setattr(file_changes, "_native", owned)
    yield owned
    with owned.subscribing:
        while owned.watches:
            owned.watches.popitem()[1].stop()
    for observer in owned.observers.values():
        observer.stop()
        observer.join(STATED_TIMEOUT)


def _inotify_instances():
    """The inotify instances this process holds, read from its descriptors."""
    instances = 0
    for descriptor in os.listdir("/proc/self/fd"):
        with contextlib.suppress(OSError):
            instances += (
                os.readlink(f"/proc/self/fd/{descriptor}") == "anon_inode:inotify"
            )
    return instances


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


def test_a_page_reading_moves_on_exactly_the_writes_its_watchers_wake_on(page_dir):
    """The page's reading, which a tab polls, and its subscription, which its event
    followers wake on, derive from one declaration of its inputs. An authored edit
    moves both; `user-views.json`, which the server rewrites as a tab reports its
    view, moves neither, and nor does reading an input, which inotify reports as the
    server serves it.

    Where the volume ignores letter case, the page is named in a spelling other than
    the one on disk, which notifications report: an edit must still wake the
    watchers."""
    from leaf.cli import resolve_dir
    from leaf.file_changes import FileChanges, page_changes
    from leaf.served_state.reading import page_reading

    (page_dir / "page").mkdir(exist_ok=True)
    respelled = page_dir.with_name(page_dir.name.swapcase())
    page = resolve_dir(str(respelled if respelled.exists() else page_dir), renew=False)
    changes, _generation = page_changes(page)
    # macOS reports some of the setup's writes well after a watcher starts, but in
    # order, so the page's subscription has heard them once the process's watcher
    # reports a write made now.
    settled = page_dir / "page" / "settled.css"
    heard = FileChanges({settled.parent: False}, settled.__eq__, collect=True)
    try:
        settled.write_text("")
        deadline = time.monotonic() + STATED_TIMEOUT
        while str(settled) not in heard.batch(STATED_TIMEOUT):
            assert time.monotonic() < deadline, "the watcher never reported the write"
    finally:
        heard.close()
    while changes.wait(changes.mark(), DIAGNOSTIC_QUIET_WINDOW_S):
        pass

    def classified(write, timeout):
        reading = page_reading(page)
        mark = changes.mark()
        write()
        return changes.wait(mark, timeout), page_reading(page) != reading

    assert classified(
        lambda: write_record(page_dir / "user-views.json", {"sessions": {}}),
        DIAGNOSTIC_QUIET_WINDOW_S,
    ) == (False, False)
    assert classified(settled.read_text, DIAGNOSTIC_QUIET_WINDOW_S) == (False, False)
    assert classified(
        lambda: (page_dir / "page" / "extra.css").write_text("p {}"), STATED_TIMEOUT
    ) == (True, True)


@contextlib.contextmanager
def _subscriber(kind, page_dir):
    """How each owner of a page's subscription takes it and a generation to wait
    from: the shared page subscription, or a session's watch between passes."""
    from leaf.file_changes import page_changes

    if kind == "page":
        yield lambda: page_changes(page_dir)
        return
    watch = session_model.Watch(None, pages=(page_dir,))
    assert watch.acquire()
    try:
        list(watch.tick())

        def subscribe():
            mark = watch.mark()
            return watch.changes, mark[2]

        yield subscribe
    finally:
        watch.release()


@pytest.mark.parametrize("owner", ["page", "session"])
def test_a_page_subscription_takes_in_a_directory_made_while_it_installs(
    page_dir, monkeypatch, native, owner
):
    """A page's roots follow its subdirectories, so one made after they are listed
    and before the subscription is handed over is subscribed in it: an entry added
    to it later wakes the owner without the owner connecting again."""
    made = page_dir / "made-while-installing"
    schedule = native.schedule

    def installing(path, recursive):
        made.mkdir(exist_ok=True)
        return schedule(path, recursive)

    with _subscriber(owner, page_dir) as subscribe:
        with monkeypatch.context() as installation:
            installation.setattr(native, "schedule", installing)
            changes, _generation = subscribe()
        assert changes.roots[made] is False
        while changes.wait(changes.mark(), DIAGNOSTIC_QUIET_WINDOW_S):
            pass
        generation = changes.mark()
        (made / "entry").write_text("moves its stamp")
        assert changes.wait(generation, STATED_TIMEOUT)


@pytest.mark.parametrize(
    ("owner", "arrival"), [("page", "moved in"), ("session", "made")]
)
def test_a_directory_arriving_deep_in_a_page_tree_joins_its_subscription(
    page_dir, tmp_path, owner, arrival
):
    """No page subscription watches a tree, so directories made deep in `page/`, or
    moved there from outside the page, move the page's reading, which is what sends
    its owner to subscribe again, and that subscription hears a file written in the
    innermost one."""
    from leaf.served_state.reading import page_reading

    shallow = page_dir / "page" / "modules"
    shallow.mkdir(parents=True, exist_ok=True)
    deep = shallow / "deep"
    inner = deep / "inner"
    outside = tmp_path / "outside"
    (outside / inner.name).mkdir(parents=True)
    with _subscriber(owner, page_dir) as subscribe:
        changes, generation = subscribe()
        before = page_reading(page_dir)
        if arrival == "made":
            inner.mkdir(parents=True)
        else:
            outside.rename(deep)
        assert changes.wait(generation, STATED_TIMEOUT)
        assert page_reading(page_dir) != before
        changes, generation = subscribe()
        assert changes.roots[inner] is False
        (inner / "module.js").write_text("export {};")
        assert changes.wait(generation, STATED_TIMEOUT)


def test_a_process_follows_every_page_through_one_observer(tmp_path, native):
    """However many pages a process follows, it holds one observer, which on Linux
    is one inotify instance, and schedules each directory they want once.
    Subscribing to another page wakes no subscription already open, and each
    subscription hears only its own page's writes."""
    from leaf.file_changes import page_changes

    pages = [tmp_path / name for name in ("first", "second", "third")]
    for page in pages:
        (page / "page" / "nested").mkdir(parents=True)
    # Counted before this test's observer exists: each watchdog observer holds an
    # instance of its own, so one another test left running counts here too.
    held = _inotify_instances() if Path("/proc/self/fd").is_dir() else 0
    first, _generation = page_changes(pages[0])
    while first.wait(first.mark(), DIAGNOSTIC_QUIET_WINDOW_S):
        pass
    generation = first.mark()
    second, third = (page_changes(page)[0] for page in pages[1:])
    assert not first.wait(generation, DIAGNOSTIC_QUIET_WINDOW_S), (
        "subscribing to a page woke another page's subscription"
    )
    assert len(native.observers) == 1
    assert set(native.watches) == {
        key for changes in (first, second, third) for key in changes.roots.items()
    }
    if Path("/proc/self/fd").is_dir():
        assert _inotify_instances() == held + 1
    for changes in (second, third):
        while changes.wait(changes.mark(), DIAGNOSTIC_QUIET_WINDOW_S):
            pass
    marks = [(changes, changes.mark()) for changes in (first, second, third)]
    (pages[1] / "page" / "nested" / "module.js").write_text("export {};")
    assert second.wait(marks[1][1], STATED_TIMEOUT)
    assert not first.wait(marks[0][1], DIAGNOSTIC_QUIET_WINDOW_S)
    assert not third.wait(marks[2][1], 0)


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
    write = service_model.CLAIM.write

    def held_commit(path, value):
        if path == service_model.claim_path(page_dir):
            commit_entered.set()
            assert allow_commit.wait(STATED_TIMEOUT), (
                "ownership commit was not released"
            )
        return write(path, value)

    try:
        list(watch.tick())
        with monkeypatch.context() as publication:
            publication.setattr(service_model.CLAIM, "write", held_commit)
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
                            if not publications:
                                publications.append(prepare())
                            return subscribed

                        with monkeypatch.context() as registration:
                            registration.setattr(
                                session_model, "FileChanges", subscribing
                            )
                            watch.mark()
                        (publishing,) = publications
                        # The mark planned again after subscribing, so the
                        # prepared claim is already among what it watches.
                        assert watch.change_pages is not None
                        assert service_model.claim_path(page_dir).name in {
                            target.name for target in watch.change_pages[1]
                        }
                    else:
                        mark = watch.mark()
                        publishing = prepare()
                        assert watch.await_news(mark, timeout=STATED_TIMEOUT)
                    assert (
                        partition / service_model.claim_path(page_dir).name
                    ).is_symlink()
                    assert service_model.owned_pages("successor") == []
                    assert list(watch.tick()) == []
                    # Reconnect to the prepared discovery set, then consume any
                    # preparation notifications before the later commit.
                    watch.mark()
                    assert watch.changes is not None
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
        assert watch.changes is not None
        assert watch.changes.wait(mark[2], STATED_TIMEOUT)
        # Consume creation before reconnecting; a delayed mkdir event must not
        # masquerade as notification of the later locator publication.
        while watch.changes.wait(watch.changes.mark(), 0.1):
            pass
        watch.mark()
        new_page = tmp_path / "later-acquisition"
        new_page.mkdir()
        (new_page / "events.jsonl").touch()
        assert watch.harness is not None
        prepared = service_model.prepare_claim(watch.harness, new_page)
        _write_during_native_wait(
            watch, lambda: service_model.publish_claim(new_page, prepared), monkeypatch
        )
        assert new_page in watch.pages()
    finally:
        watch.release()


def test_a_directory_watched_with_and_without_its_tree_serves_each(tmp_path, native):
    """A directory one subscription watches with its tree and another without is
    scheduled in each mode, so closing one leaves the other hearing its writes."""
    from leaf import file_changes

    tree = tmp_path / "tree"
    (tree / "nested").mkdir(parents=True)
    deep = file_changes.FileChanges({tree: True}, lambda _path: True)
    shallow = file_changes.FileChanges({tree: False}, lambda _path: True)
    try:
        deep.close()
        while shallow.wait(shallow.mark(), DIAGNOSTIC_QUIET_WINDOW_S):
            pass
        generation = shallow.mark()
        (tree / "entry").write_text("x")
        assert shallow.wait(generation, STATED_TIMEOUT)
        assert set(native.watches) == {(tree, False)}
    finally:
        shallow.close()


def test_shared_page_native_owner_rearms_created_and_replaced_directories(
    tmp_path, monkeypatch, native
):
    from leaf.file_changes import _PageChanges

    page = tmp_path / "later-page"
    owner = _PageChanges()
    initial, _generation = owner.connect(page)
    page.mkdir()
    source = page / "page"
    source.mkdir()
    module = source / "index.html"
    module.write_text("initial authored input")
    changes, _generation = owner.connect(page)
    assert changes is not initial
    assert initial.closed
    try:
        while changes.wait(changes.mark(), 0.1):
            pass
        mark = changes.mark()
        with ThreadPoolExecutor(max_workers=1) as executor:
            waiting = executor.submit(changes.wait, mark, STATED_TIMEOUT)
            module.write_text("later authored input")
            assert waiting.result(timeout=STATED_TIMEOUT)
        descriptor = native.watches[page, False].descriptor
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
            replacement, _generation = owner.connect(page)
        assert replacement is not changes
        assert descriptor in closed
        assert changes.closed
        # A new subdirectory joins the watch when its owner connects again.
        source = page / "page"
        source.mkdir()
        subscribed, mark = owner.connect(page)
        with ThreadPoolExecutor(max_workers=1) as executor:
            waiting = executor.submit(subscribed.wait, mark, STATED_TIMEOUT)
            (source / "after-replacement.html").write_text("replacement authored input")
            assert waiting.result(timeout=STATED_TIMEOUT)
    finally:
        assert owner.release is not None
        owner.release()


@pytest.mark.parametrize("phase", ["opening", "native-installation"])
def test_shared_page_watch_replans_a_root_removed_during_subscription(
    tmp_path, monkeypatch, native, phase
):
    """A page removed during subscription stays observable through its parent."""
    from leaf import file_changes

    page = tmp_path / "retiring-page"
    page.mkdir()
    original_open = file_changes.os.open
    schedule = native.schedule
    removed = False

    def retire():
        nonlocal removed
        if not removed:
            page.rmdir()
            removed = True

    def opening(path, *args, **kwargs):
        if Path(path) == page and phase == "opening":
            retire()
        return original_open(path, *args, **kwargs)

    def installing(path, recursive):
        if path == page and phase == "native-installation":
            retire()
        return schedule(path, recursive)

    owner = file_changes._PageChanges()
    monkeypatch.setattr(file_changes.os, "open", opening)
    monkeypatch.setattr(native, "schedule", installing)
    try:
        changes, generation = owner.connect(page)
        assert removed
        page.mkdir()
        assert changes.wait(generation, STATED_TIMEOUT)
        source = page / "page"
        source.mkdir()
        replacement, generation = owner.connect(page)
        assert replacement is not changes
        (source / "index.html").write_text("back in service")
        assert replacement.wait(generation, STATED_TIMEOUT)
    finally:
        if owner.release is not None:
            owner.release()


def test_session_native_watch_pins_roots_until_replacement(page_dir, native):
    """The native provider holds an inode while the pathname is replaced."""
    watch = session_model.Watch(None, pages=(page_dir,))
    assert watch.acquire()
    try:
        list(watch.tick())
        watch.mark()
        previous = watch.changes
        assert previous is not None
        held = os.fstat(native.watches[page_dir, False].descriptor)
        shutil.rmtree(page_dir)
        page_dir.mkdir()
        current = page_dir.stat()
        assert (held.st_dev, held.st_ino) != (current.st_dev, current.st_ino)
        watch.mark()
        assert watch.changes is not previous
        assert previous.closed
    finally:
        watch.release()


@pytest.mark.parametrize("failure", ["directory", "provider"])
def test_native_subscription_releases_partial_startup_resources(
    tmp_path, monkeypatch, native, failure
):
    from leaf import file_changes

    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    opened, emitters = [], []
    real_open, schedule = os.open, native.schedule

    def opening(*args, **kwargs):
        if failure == "directory" and opened:
            raise RuntimeError("directory installation refused")
        descriptor = real_open(*args, **kwargs)
        opened.append(descriptor)
        return descriptor

    def installing(path, recursive):
        if failure == "provider" and emitters:
            raise RuntimeError("provider installation refused")
        scheduled = schedule(path, recursive)
        emitters.append(scheduled[2])
        return scheduled

    monkeypatch.setattr(file_changes.os, "open", opening)
    monkeypatch.setattr(native, "schedule", installing)
    with pytest.raises(RuntimeError, match="installation refused"):
        file_changes.FileChanges({first: False, second: True}, lambda _path: True)
    assert opened and emitters
    for descriptor in opened:
        with pytest.raises(OSError):
            os.fstat(descriptor)
    assert not any(emitter.is_alive() for emitter in emitters)
    assert native.watches == {}


def test_native_subscription_rearms_a_root_replaced_during_installation(
    tmp_path, monkeypatch, native
):
    """A replacement between pinning and scheduling invalidates the plan."""
    from leaf import file_changes

    page = tmp_path / "installing"
    page.mkdir()
    schedule = native.schedule
    installations = []

    def installing(path, recursive):
        if path == page:
            if not installations:
                page.rmdir()
                page.mkdir()
            installations.append(path)
        return schedule(path, recursive)

    owner = file_changes._PageChanges()
    monkeypatch.setattr(native, "schedule", installing)
    try:
        replacement, _generation = owner.connect(page)
        assert len(installations) == 2, "the stale installation was not replanned"
        descriptors = [watch.descriptor for watch in native.watches.values()]
        held = os.fstat(native.watches[page, False].descriptor)
        assert (held.st_dev, held.st_ino) == (page.stat().st_dev, page.stat().st_ino)
        roots = dict(replacement.roots)
        assert replacement.matches(roots)
        (page / "diagnostic.json").write_text("{}")
        assert owner.connect(page)[0] is replacement, (
            "a child edit must not rearm its root"
        )
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
    changes, _generation = page_changes(page_dir)
    try:
        for n in range(9):
            page_memory.memory_of(tmp_path / f"gallery-{n}")
        assert page_changes(page_dir)[0] is changes
        del retained
        for n in range(9):
            page_memory.memory_of(tmp_path / f"later-gallery-{n}")
        gc.collect()
        assert changes.closed
    finally:
        changes.close()


@pytest.mark.parametrize(
    ("code", "limit"),
    [
        (errno.EMFILE, "fs.inotify.max_user_instances or RLIMIT_NOFILE"),
        (errno.ENOSPC, "fs.inotify.max_user_watches"),
    ],
    ids=["instances", "watches"],
)
def test_an_exhausted_native_watcher_polls_instead(
    tmp_path, monkeypatch, capfd, native, code, limit
):
    """The kernel's inotify limits are shared with every program the user runs, so a
    directory it refuses a watch for want of one is polled instead, and a note names
    the limit, rather than ending the process that asked. watchdog raises the
    kernel's errno, which only a Linux host with a spent limit gives."""
    from leaf import file_changes

    schedule = native._schedule

    def kernel(path, recursive, *, polling):
        if not polling:
            raise OSError(code, os.strerror(code))
        return schedule(path, recursive, polling=polling)

    monkeypatch.setattr(native, "_schedule", kernel)
    changes = file_changes.FileChanges({tmp_path: False}, lambda _path: True)
    try:
        mark = changes.mark()
        (tmp_path / "written").write_text("x")
        assert changes.wait(mark, timeout=STATED_TIMEOUT)
    finally:
        changes.close()
    [said] = [json.loads(line) for line in capfd.readouterr().err.splitlines()]
    assert said["code"] == "watch-limit"
    assert said["values"] == {"limit": limit, "roots": [str(tmp_path)]}


def test_any_other_native_watcher_failure_reaches_its_owner(
    tmp_path, monkeypatch, native
):
    from leaf import file_changes

    def broken(*_args, **_kwargs):
        raise RuntimeError("the observer is broken")

    monkeypatch.setattr(native, "_schedule", broken)
    with pytest.raises(RuntimeError, match="broken"):
        file_changes.FileChanges({tmp_path: False}, lambda _path: True)
