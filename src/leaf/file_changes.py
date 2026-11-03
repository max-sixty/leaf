"""Native filesystem subscriptions for session delivery and authored-file followers.

The files remain authority; notifications only schedule another canonical read.
Latency-sensitive followers wait on a subscription from here. A subscription is
installed before its constructor returns, and a generation taken before an
observation retains writes arriving during it. Clock-only lifetime and activity
transitions still have bounded timed reads. A page's subscription watches the
directories that report the inputs its reading stamps, and accepts exactly those
inputs (`served_state.reading`), so diagnostics never wake it and the history under
`revisions/` costs it nothing. watchfiles' public `watch` owns platform
notifications and polling.

A process holds one native watcher for each recursion mode its subscriptions use,
however many subscriptions it holds, and a directory a subscription wants in one
mode only that mode's watcher serves. Page subscriptions are all non-recursive, so a
process following any number of pages holds one watcher. The watcher hands each
batch to every subscription that accepts a path in it. On Linux a watcher is one
inotify instance and each directory it covers one watch. The per-user instance
limit (`fs.inotify.max_user_instances`, 128 unless raised) is the one that ran out
when Leaf held a watcher per page (issue #4812); the watch limit is far larger.

watchfiles fixes a watcher's directories when it starts. A subscription that needs
a directory its process's watcher lacks therefore starts a replacement covering
every open subscription, and every other subscription wakes once, since the retired
watcher drops any batch it had not yet reported. On macOS notify restarts its
FSEvents stream for each directory it adds, so the time to start a watcher grows
with the square of its directories beyond a few dozen: 0.1 s for 100 and 3.6 s for
1,000, measured on 2026-11-01. A directory made deep in a page's tree is one more
directory, so it starts a replacement.

A page server is a process per page, so a watcher there would still be one per
retained page; its maintenance keeps its liveness timers (`server_rows`,
`server.stop_when_service_ends`) instead.

The kernel's inotify limits are per user and shared with every program the user
runs, so Leaf can't count on a native watcher however few it holds. When the
kernel refuses one because a limit ran out, that watcher polls instead and names
the limit its refusal points to in a note, so the process notices changes later
rather than exiting.
"""

import errno
import os
import threading
import weakref
from collections.abc import Iterable
from pathlib import Path

from .findings import Finding, note
from .page_memory import memo
from .served_state.reading import outside_inputs, page_input, page_roots


class _Started:
    """The stop event a `watch` generator reads, which also says it has started.

    `watch` installs its native watcher when the generator first runs and only then
    looks up its stop event's `is_set`, so that first lookup marks the watcher
    installed, a step sooner than its first call would."""

    def __init__(self, stop: threading.Event):
        self.stop = stop
        self.installed = threading.Event()

    @property
    def is_set(self):
        self.installed.set()
        return self.stop.is_set


class FileChanges:
    """One owner's requested directories, watched by its process's native watchers.

    Missing directories subscribe their nearest existing ancestor, without its
    tree; if a selected root disappears while installing, the subscription
    replans before it is returned. An owner whose roots can change takes a new
    subscription when `matches` says the installed one no longer fits, and lets
    the old one go after it, so the process's watcher runs on across the swap.
    """

    def __init__(self, roots: dict[Path, bool], accepts, *, collect: bool = False):
        self.native = _native
        self.accepts = accepts
        self.generation = 0
        self.error: BaseException | None = None
        self.closed = False
        self.pending: set[str] | None = set() if collect else None
        # Whether a replaced watcher may have taken unreported paths with it.
        self.lost = False
        self.roots: dict[Path, bool] = {}
        self.native.subscribe(self, roots)

    def matches(self, roots: dict[Path, bool]) -> bool:
        """Whether this open subscription has these roots, and its process's
        watchers still hold the directories now at their paths."""
        roots = _existing_roots(roots)
        with self.native.condition:
            return not self.closed and roots == self.roots and self.native.holds(roots)

    def mark(self) -> int:
        with self.native.condition:
            if self.error:
                raise self.error
            return self.generation

    def wait(self, generation: int, timeout: float | None) -> bool:
        return wait([(self, generation)], timeout)

    def close(self) -> None:
        self.native.unsubscribe(self)

    def batch(self, timeout: float) -> set[str] | None:
        """Consume retained paths for a single batch reader, the empty set after an
        idle timeout, or None once a replaced watcher may have lost some, when the
        reader reads every input again."""
        if self.pending is None:
            raise RuntimeError("path batches require a collecting subscription")
        with self.native.condition:
            self.native.condition.wait_for(
                lambda: (
                    self.error is not None or self.closed or self.lost or self.pending
                ),
                timeout=timeout,
            )
            if self.error:
                raise self.error
            paths = None if self.lost else self.pending.copy()
            self.lost = False
            self.pending.clear()
            return paths


def wait(marks: Iterable[tuple[FileChanges, int]], timeout: float | None) -> bool:
    """Whether any of these subscriptions, each paired with the generation to wait
    from, has heard a change since or was closed, waiting up to `timeout` for one.
    They share their process's watchers, so one wait covers them all."""
    marks = list(marks)
    condition = marks[0][0].native.condition
    with condition:
        moved = condition.wait_for(
            lambda: any(
                changes.error is not None
                or changes.closed
                or changes.generation != generation
                for changes, generation in marks
            ),
            timeout=timeout,
        )
        for changes, _generation in marks:
            if changes.error:
                raise changes.error
        return moved


class _Watcher:
    """One native watcher over directories in one recursion mode, each pinned by an
    open descriptor, and the thread passing its batches to its process's
    subscriptions."""

    def __init__(self, paths: list[Path], recursive: bool, native: "_Native"):
        self.recursive = recursive
        self.error: BaseException | None = None
        self.stopping = threading.Event()
        self.roots: dict[Path, int] = {}
        self.thread: threading.Thread | None = None
        try:
            # Keep the directory objects alive for exactly this watcher. Linux can
            # reuse a deleted directory's inode after an inotify watch is revoked;
            # an open descriptor prevents that identity alias.
            for path in paths:
                self.roots[path] = os.open(
                    path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
                )
            started = _Started(self.stopping)
            self.thread = threading.Thread(
                target=self._run, args=(list(self.roots), native, started), daemon=True
            )
            self.thread.start()
            started.installed.wait()
            if self.error:  # ty: ignore[redundant-condition] -- the watcher thread may set it while installation waits
                raise self.error
        except BaseException:
            self.stop(join=True)
            raise

    def _run(self, paths, native, started):
        try:
            for changes in _changes(paths, self.recursive, started):
                native.dispatch(changes)
            if not self.stopping.is_set():
                raise RuntimeError("the filesystem subscription was interrupted")
        except Exception as error:
            self.error = error
            native.fail(self, error)
        finally:
            started.installed.set()

    def holds(self, path: Path) -> bool:
        """Whether this running watcher covers the directory now at `path`."""
        descriptor = self.roots.get(path)
        if descriptor is None or self.error is not None:
            return False
        held = os.fstat(descriptor)
        try:
            current = path.stat()
        except FileNotFoundError:
            return False
        return (held.st_dev, held.st_ino) == (current.st_dev, current.st_ino)

    def stop(self, *, join: bool = False) -> None:
        """Stop the watcher and unpin its directories. Its thread ends within a
        step; only a caller that can't be that thread, or hold what it waits on,
        joins it."""
        self.stopping.set()
        if join and self.thread is not None:
            self.thread.join()
        while self.roots:
            _path, descriptor = self.roots.popitem()
            os.close(descriptor)


class _Native:
    """A process's native watchers, one per recursion mode, and the subscriptions
    they serve."""

    def __init__(self):
        # Held while a subscription is checked against the watchers or replaces
        # them, so two subscribers never start competing replacements.
        self.subscribing = threading.Lock()
        # Guards the watchers, the subscriptions and every subscription's
        # generation. Reentrant, since a finalizer can close a subscription on a
        # thread that already holds it.
        self.condition = threading.Condition(threading.RLock())
        self.subscriptions: list[FileChanges] = []
        self.watchers: dict[bool, _Watcher] = {}

    def holds(self, roots: dict[Path, bool]) -> bool:
        """Whether the watcher of each root's recursion mode holds the directory now
        at it. Called holding `condition`."""
        return all(
            recursive in self.watchers and self.watchers[recursive].holds(path)
            for path, recursive in roots.items()
        )

    def subscribe(self, subscription: FileChanges, requested: dict[Path, bool]):
        with self.subscribing:
            while True:
                roots = _existing_roots(requested)
                with self.condition:
                    if self.holds(roots):
                        subscription.roots = roots
                        self.subscriptions.append(subscription)
                        return
                    wanted = {False: set(), True: set()}
                    for held in (roots, *(other.roots for other in self.subscriptions)):
                        for path, recursive in held.items():
                            wanted[recursive].add(path)
                try:
                    self._replace(wanted)
                except FileNotFoundError:
                    # Selecting, pinning and watching are one operation: a rename
                    # can retire a root between any two steps, so plan again.
                    continue

    def _replace(self, wanted: dict[bool, set[Path]]) -> None:
        """Replace the watcher of each recursion mode that doesn't hold every
        directory wanted in that mode with one that does, then stop the old one.

        A directory another subscription wanted that is gone now is watched through
        its nearest existing ancestor in non-recursive mode, and not at all in
        recursive mode, where the ancestor's tree would be everything beneath it.
        Either way the wake below sends its owner to subscribe again."""
        with self.condition:
            modes = [
                recursive
                for recursive, paths in wanted.items()
                if not self.holds(dict.fromkeys(paths, recursive))
            ]
        started: dict[bool, _Watcher | None] = {}
        try:
            for recursive in modes:
                roots = _existing_roots(dict.fromkeys(wanted[recursive], recursive))
                paths = [path for path, nested in roots.items() if nested == recursive]
                started[recursive] = _Watcher(paths, recursive, self) if paths else None
        except BaseException:
            for watcher in started.values():
                if watcher is not None:
                    watcher.stop(join=True)
            raise
        with self.condition:
            for recursive, watcher in started.items():
                retired = self.watchers.pop(recursive, None)
                if retired is not None:
                    retired.stop()
                if watcher is not None:
                    self.watchers[recursive] = watcher
            for subscription in list(self.subscriptions):
                subscription.generation += 1
                subscription.lost = True
            self.condition.notify_all()

    def unsubscribe(self, subscription: FileChanges) -> None:
        with self.condition:
            if subscription in self.subscriptions:
                self.subscriptions.remove(subscription)
            subscription.closed = True
            if not self.subscriptions:
                for watcher in self.watchers.values():
                    watcher.stop()
                self.watchers.clear()
            self.condition.notify_all()

    def dispatch(self, changes: set[tuple[int, str]]) -> None:
        paths = [(Path(path), path) for _change, path in changes]
        with self.condition:
            for subscription in list(self.subscriptions):
                try:
                    accepted = {
                        name for path, name in paths if subscription.accepts(path)
                    }
                except Exception as error:
                    # One owner's broken filter fails its own subscription only.
                    subscription.error = error
                    continue
                if accepted:
                    subscription.generation += 1
                    if subscription.pending is not None:
                        subscription.pending.update(accepted)
            self.condition.notify_all()

    def fail(self, watcher: _Watcher, error: BaseException) -> None:
        """Hand a running watcher's failure to every subscription it served."""
        with self.condition:
            if self.watchers.get(watcher.recursive) is watcher:
                for subscription in list(self.subscriptions):
                    if watcher.recursive in subscription.roots.values():
                        subscription.error = error
                self.condition.notify_all()


_native = _Native()


# What watchfiles 1.3.0 (on notify 8) says when the kernel refuses a native watcher
# because a limit ran out, and the limits each can mean. It raises
# `WatchfilesRustInternalError` when the inotify instance can't be created (EMFILE)
# and a bare `OSError` when a watch can't be added (ENOSPC, which notify renames).
# Neither carries an errno, so these words are all a reader has. inotify_init gives
# EMFILE for the per-user instance limit and the process's open-file limit alike,
# so that refusal names both.
_LIMITS = {
    f"(os error {errno.EMFILE})": "fs.inotify.max_user_instances or RLIMIT_NOFILE",
    "OS file watch limit reached": "fs.inotify.max_user_watches",
}


def _changes(paths, recursive, started):
    """The batches `watch` reports for these roots, polled when the kernel has no
    native watcher left to give. Exhaustion arises only while the watcher is
    created, before `started` reports it installed (notify drops a later watch it
    can't add), so the polling watcher misses no change the native one reported."""
    from watchfiles import watch

    options: dict = {
        "watch_filter": None,
        "debounce": 25,
        "step": 50,
        "stop_event": started,
        "rust_timeout": 0,
        "raise_interrupt": False,
        "recursive": recursive,
    }
    try:
        yield from watch(*paths, **options)
    except Exception as error:
        limit = next(
            (name for words, name in _LIMITS.items() if words in str(error)), None
        )
        if limit is None:
            raise
        note(
            Finding(
                "watch-limit",
                values={"limit": limit, "roots": [str(path) for path in paths]},
                severity="advice",
            )
        )
        yield from watch(*paths, **options, force_polling=True)


def _existing_roots(requested: dict[Path, bool]) -> dict[Path, bool]:
    """Resolve missing directories to ancestors that can announce their return.

    An ancestor stands in without its tree: it reports the missing path's
    creation, and the owner's next subscription takes the path in, so recursing
    from it would only watch whatever else lies beneath, such as every page."""
    roots = {}
    for requested_path, recursive in requested.items():
        path = requested_path
        while not path.is_dir():
            path = path.parent
        roots[path] = roots.get(path, False) or (recursive and path == requested_path)
    return roots


def target_paths(targets: set[Path]) -> frozenset[Path]:
    """The notifications that can move a target file: its own, and those of each
    directory above it, which a rename, replacement or creation of that directory
    reports by the directory's path. Writes to a directory's other entries report
    those entries, so a target's neighbours stay quiet."""
    return frozenset(path for target in targets for path in (target, *target.parents))


class _PageChanges:
    """One process's subscription for a page, shared by its followers in the
    process, each of which holds its own generation."""

    def __init__(self):
        self.lock = threading.Lock()
        self.targets = None
        self.changes = None
        self.release = None

    def connect(self, page: Path) -> tuple[FileChanges, int]:
        with self.lock:
            while True:
                targets, roots = _page_plan(page)
                if not self._holds(targets, roots):
                    self._install(page, targets, roots)
                assert self.changes is not None
                generation = self.changes.mark()
                # The roots follow the page's directories, so a plan taken after
                # the generation must still match: one created before it is
                # subscribed now, and one created after it wakes the owner.
                if self._holds(*_page_plan(page)):
                    return self.changes, generation

    def _holds(self, targets: set[Path], roots: dict[Path, bool]) -> bool:
        return (
            self.changes is not None
            and self.targets == targets
            and self.changes.matches(roots)
        )

    def _install(self, page: Path, targets: set[Path], roots: dict[Path, bool]):
        watched = target_paths(targets)
        changes = FileChanges(
            roots,
            lambda changed: page_input(page, changed) or changed in watched,
        )
        if self.release is not None:
            self.release()
        self.changes = changes
        # The process's watchers retain FileChanges, never this memo owner.
        # Discarding an unheld page memory therefore closes its subscription.
        self.release = weakref.finalize(self, changes.close)
        self.targets = targets


def _page_plan(page: Path) -> tuple[set[Path], dict[Path, bool]]:
    targets = outside_inputs(page)
    roots = {target.parent for target in targets} | page_roots(page)
    return targets, dict.fromkeys(roots, False)


def page_changes(page: Path) -> tuple[FileChanges, int]:
    """The process's subscription for a page, refreshed when the page's
    directories, its claim or its file grants move what it watches, and the
    generation to wait from. An owner reads the page after taking both, and takes
    them again after each wake, which is how a new directory joins the watch."""
    return memo(page, _PageChanges).connect(page)
