"""Native filesystem subscriptions for session delivery and authored-file followers.

The files remain authority; notifications only schedule another canonical read.
Latency-sensitive followers wait on a subscription from here. A subscription is
installed before its constructor returns, and a generation taken before an
observation retains writes arriving during it. Clock-only lifetime and activity
transitions still have bounded timed reads. A page's subscription watches the
directories that report the inputs its reading stamps, and accepts exactly those
inputs (`served_state.reading`), so diagnostics never wake it and the history under
`revisions/` costs it nothing.

A process holds one watchdog observer. Each directory its subscriptions want is
scheduled on it once per recursion mode, however many subscriptions want it, and
the observer hands each event to every subscription that accepts a path it names.
Directories join and leave the observer while it runs, so subscribing disturbs no
other subscription. On Linux the observer holds one inotify instance, and each
directory takes one watch, each directory of a recursive tree included. The
per-user instance limit (`fs.inotify.max_user_instances`, 128 unless raised) is
the one that ran out when Leaf held a watcher per page (issue #4812); the watch
limit is far larger. Each scheduled directory costs the process an idle
thread.

Page subscriptions take no tree. The page's reading stamps every directory in its
trees, so a new one moves the reading, its owner subscribes again, and the
directory joins the observer. watchdog's recursive watch on Linux skips without
raising a directory beneath its root that the kernel refuses a watch, so nothing
falls back to polling and that directory's changes go unheard. A recursive
subscription suits only an owner that can afford to stop hearing changes and whose
trees can be too large for a thread per directory, such as a developer's
preview.

An event reaches a subscription as the platform reports it: at once from inotify,
but for a file moved out of a watched directory, which watchdog holds up to 500 ms
to pair with its arrival elsewhere, and within watchdog's 10 ms FSEvents latency on
macOS. watchfiles, which this replaced, polled for the events its Rust side had
already received: it slept a step between looks and ended a batch a step after its
last change, so a wake waited one to two steps, and a shorter step bought speed with
idle wakes in every process. It also fixed a watcher's directories when the watcher
started, so a subscription needing a new directory restarted the process's watcher
over every subscription and woke them all. Calling inotify and FSEvents through
ctypes would avoid the thread per directory and the repairs to watchdog, but Leaf
would own the foreign-function code and its hazards: a prototype came to half again
this module's length, and crashed at exit until it stopped its FSEvents streams
first.

A subscription hears what changes a file's content, metadata, name or presence.
Opening and closing a file change none of those. watchdog also reports a directory
as modified whenever an entry in it changes, beside the entry's own event; a page's
directory is one of its inputs, so hearing that report would let every diagnostic
the server writes wake the page's followers.

A page server is a process per page, so a subscription there would still be one
per retained page; its maintenance keeps its liveness timers (`server_rows`,
`server.stop_when_service_ends`) instead.

The kernel's inotify limits are per user and shared with every program the user
runs, so Leaf can't count on a native watch however few it holds. When the kernel
refuses one because a limit ran out, that directory is polled instead, and a note
names the limit, so the process notices its changes later rather than exiting.
"""

import errno
import os
import sys
import threading
import weakref
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from .findings import Finding, note
from .page_memory import memo
from .served_state.reading import outside_inputs, page_input, page_roots

if TYPE_CHECKING:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers.api import BaseObserver


class FileChanges:
    """One owner's requested directories, watched through its process's observer.

    Missing directories subscribe their nearest existing ancestor, without its
    tree; if a selected root disappears while installing, the subscription
    replans before it is returned. An owner whose roots can change takes a new
    subscription when `matches` says the installed one no longer fits, and closes
    the old one after it, so the directories both want stay scheduled across the
    swap.
    """

    def __init__(self, roots: dict[Path, bool], accepts, *, collect: bool = False):
        self.native = _native
        self.accepts = accepts
        self.generation = 0
        self.error: BaseException | None = None
        self.closed = False
        self.pending: set[str] | None = set() if collect else None
        self.roots: dict[Path, bool] = {}
        self.native.subscribe(self, roots)

    def matches(self, roots: dict[Path, bool]) -> bool:
        """Whether this open subscription has these roots, and its process still
        watches the directories now at their paths."""
        roots = _existing_roots(roots)
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
        self.native.sweep()

    def batch(self, timeout: float) -> set[str]:
        """Consume retained paths for a single batch reader, or the empty set after
        an idle timeout."""
        if self.pending is None:
            raise RuntimeError("path batches require a collecting subscription")
        with self.native.condition:
            self.native.condition.wait_for(
                lambda: self.error is not None or self.closed or self.pending,
                timeout=timeout,
            )
            if self.error:
                raise self.error
            paths = self.pending.copy()
            self.pending.clear()
            return paths


def wait(marks: Iterable[tuple[FileChanges, int]], timeout: float | None) -> bool:
    """Whether any of these subscriptions, each paired with the generation to wait
    from, has heard a change since or was closed, waiting up to `timeout` for one.
    They share their process's observer, so one wait covers them all."""
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


class _Watch:
    """One directory scheduled in one recursion mode, pinned by an open
    descriptor."""

    def __init__(self, path: Path, recursive: bool, native: "_Native"):
        # Keep the directory object alive for exactly this watch. Linux can reuse a
        # deleted directory's inode after an inotify watch is revoked; an open
        # descriptor prevents that identity alias.
        self.descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            self.observer, self.watch, self.emitter = native.schedule(path, recursive)
        except BaseException:
            os.close(self.descriptor)
            raise

    def holds(self, path: Path) -> bool:
        """Whether this watch still covers the directory now at `path`."""
        if not self.emitter.is_alive():
            return False
        held = os.fstat(self.descriptor)
        try:
            current = path.stat()
        except FileNotFoundError:
            return False
        return (held.st_dev, held.st_ino) == (current.st_dev, current.st_ino)

    def stop(self) -> None:
        self.observer.unschedule(self.watch)
        os.close(self.descriptor)


class _Native:
    """A process's observers, the directories scheduled on them, and the
    subscriptions they serve.

    An observer's thread dispatches holding the observer's own lock and then takes
    `condition`, so nothing calls an observer while holding `condition`. Directories
    are scheduled and unscheduled holding `subscribing` instead, on the thread of an
    owner subscribing or closing. A subscription a finalizer releases leaves its
    directories scheduled for the next of those to unschedule, since a finalizer can
    run on any thread, the observer's own or one inside these locks included."""

    def __init__(self):
        self.subscribing = threading.Lock()
        # Guards the subscriptions and every subscription's generation. Reentrant,
        # since a finalizer can release a subscription on a thread that already
        # holds it.
        self.condition = threading.Condition(threading.RLock())
        self.subscriptions: list[FileChanges] = []
        self.watches: dict[tuple[Path, bool], _Watch] = {}
        # The native observer, and the polling one, each by whether it polls.
        self.observers: dict[bool, BaseObserver] = {}
        self.handler: FileSystemEventHandler | None = None

    def holds(self, roots: dict[Path, bool]) -> bool:
        """Whether a watch in each root's recursion mode covers the directory now at
        it."""
        with self.subscribing:
            return all(
                key in self.watches and self.watches[key].holds(key[0])
                for key in roots.items()
            )

    def subscribe(self, subscription: FileChanges, requested: dict[Path, bool]):
        with self.subscribing:
            try:
                while True:
                    roots = _existing_roots(requested)
                    try:
                        for key in roots.items():
                            self._ensure(*key)
                    except FileNotFoundError:
                        # Selecting, pinning and scheduling are one operation: a
                        # rename can retire a root between any two steps, so plan
                        # again.
                        continue
                    with self.condition:
                        subscription.roots = roots
                        self.subscriptions.append(subscription)
                    return
            finally:
                self._sweep()

    def _ensure(self, path: Path, recursive: bool) -> None:
        """Schedule `path` unless a watch already covers the directory now there.
        Called holding `subscribing`."""
        key = (path, recursive)
        watch = self.watches.get(key)
        if watch is not None and watch.holds(path):
            return
        if watch is not None:
            # The directory at this path was replaced, and the watch follows the
            # one it replaced. watchdog keys a watch by its path, so the old one
            # leaves before the new one is scheduled.
            del self.watches[key]
            watch.stop()
        self.watches[key] = _Watch(path, recursive, self)

    def schedule(self, path: Path, recursive: bool):
        """Schedule a directory on the native observer, or on the polling one when
        the kernel has no native watch left to give."""
        try:
            return self._schedule(path, recursive, polling=False)
        except OSError as error:
            limit = _LIMITS.get(error.errno)
            if limit is None:
                raise
        note(
            Finding(
                "watch-limit",
                values={"limit": limit, "roots": [str(path)]},
                severity="advice",
            )
        )
        return self._schedule(path, recursive, polling=True)

    def _schedule(self, path: Path, recursive: bool, *, polling: bool):
        from watchdog import events

        observer = self.observers.get(polling)
        if observer is None:
            observer = _polling_observer() if polling else _native_observer()
            observer.start()
            self.observers[polling] = observer
        if self.handler is None:
            self.handler = _handler(self)
        watch = observer.schedule(
            self.handler,
            str(path),
            recursive=recursive,
            event_filter=[
                events.FileCreatedEvent,
                events.DirCreatedEvent,
                events.FileDeletedEvent,
                events.DirDeletedEvent,
                events.FileModifiedEvent,
                events.FileMovedEvent,
                events.DirMovedEvent,
                events.FileAttribEvent,
                events.DirAttribEvent,
            ],
        )
        emitter = next(each for each in observer.emitters if each.watch == watch)
        return observer, watch, emitter

    def unsubscribe(self, subscription: FileChanges) -> None:
        """Release a subscription, leaving its directories for the next sweep."""
        with self.condition:
            if subscription in self.subscriptions:
                self.subscriptions.remove(subscription)
            subscription.closed = True
            self.condition.notify_all()

    def sweep(self) -> None:
        with self.subscribing:
            self._sweep()

    def _sweep(self) -> None:
        """Unschedule the directories no open subscription wants. Called holding
        `subscribing`."""
        with self.condition:
            wanted = {key for each in self.subscriptions for key in each.roots.items()}
        for key in [key for key in self.watches if key not in wanted]:
            self.watches.pop(key).stop()

    def dispatch(self, event) -> None:
        """Hand one event to every subscription that accepts a path it names.
        watchdog calls this on its observer's thread."""
        names = [os.fsdecode(event.src_path)]
        if event.dest_path:
            names.append(os.fsdecode(event.dest_path))
        paths = [(Path(name), name) for name in names]
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


def _native_observer() -> "BaseObserver":
    """The platform's observer.

    On macOS watchdog 7.0 reports a directory made in a non-recursive watch's
    directory, removed from it or moved across it only as that directory being
    modified, which a subscription ignores, since its FSEvents emitter compares a
    directory event's own path with the watched directory rather than the path's
    parent. Its tests assert that. The macOS observer here keeps an event whose
    path, or whose path's parent, is the watched directory, as inotify reports
    it."""
    if sys.platform != "darwin":
        from watchdog.observers.inotify import InotifyObserver

        return InotifyObserver()
    from watchdog.observers.api import BaseObserver, EventEmitter
    from watchdog.observers.fsevents import FSEventsEmitter, FSEventsObserver

    class Emitter(FSEventsEmitter):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # Resolved once: the stream reports every event beneath the directory,
            # so this filter runs on each of them.
            self.watched = os.path.realpath(self.watch.path)

        def queue_event(self, event) -> None:
            paths = (
                [event.src_path, event.dest_path]
                if event.dest_path
                else [event.src_path]
            )
            if self.watch.is_recursive or any(
                self.watched in (path, os.path.dirname(path))
                for path in map(os.fsdecode, paths)
            ):
                EventEmitter.queue_event(self, event)

    class Fixed(FSEventsObserver):
        def __init__(self):
            BaseObserver.__init__(self, Emitter)

    return Fixed()


def _polling_observer() -> "BaseObserver":
    """watchdog's polling observer."""
    from watchdog.observers.polling import PollingObserver

    return PollingObserver()


def _handler(native: _Native) -> "FileSystemEventHandler":
    """The handler watchdog calls with each event, which hands it to `native`."""
    from watchdog.events import FileSystemEventHandler

    class Handler(FileSystemEventHandler):
        def dispatch(self, event) -> None:
            native.dispatch(event)

    return Handler()


_native = _Native()


# The limits each refusal can mean. watchdog raises the kernel's errno: inotify_init
# gives EMFILE for the per-user instance limit and the process's open-file limit
# alike, so that refusal names both, and inotify_add_watch gives ENOSPC for the
# watch limit.
_LIMITS = {
    errno.EMFILE: "fs.inotify.max_user_instances or RLIMIT_NOFILE",
    errno.ENOSPC: "fs.inotify.max_user_watches",
}


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
                # The roots follow the page's subdirectories, so a plan taken after
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
            changes.native.sweep()
        self.changes = changes
        # The process's observer retains FileChanges, never this memo owner.
        # Discarding an unheld page memory therefore releases its subscription.
        self.release = weakref.finalize(self, changes.native.unsubscribe, changes)
        self.targets = targets


def _page_plan(page: Path) -> tuple[set[Path], dict[Path, bool]]:
    targets = outside_inputs(page)
    roots = {target.parent for target in targets} | page_roots(page)
    return targets, dict.fromkeys(roots, False)


def page_changes(page: Path) -> tuple[FileChanges, int]:
    """The process's subscription for a page, refreshed when the page's
    subdirectories, its claim or its file grants move what it watches, and the
    generation to wait from. An owner reads the page after taking both, and takes
    them again after each wake, which is how a new subdirectory joins the watch."""
    return memo(page, _PageChanges).connect(page)
