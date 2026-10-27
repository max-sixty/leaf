"""Native filesystem subscriptions for quiet page and session maintenance.

The files remain authority; notifications only schedule another canonical read.
Every follower of page files waits on a subscription from here rather than
polling stamps. A subscription is installed before its constructor returns, and a
generation taken before an observation retains writes arriving during it.
Clock-only lifetime and activity transitions still have bounded timed reads. A
page's subscription watches the directories its reading reads and accepts exactly
the inputs it stamps (`served_state.reading`), so diagnostics never wake it and
the history under `revisions/` costs it nothing. watchfiles' public `watch` owns
platform notifications and polling.

The kernel's inotify limits are per user and shared with every program the user
runs, so Leaf can't count on a native watcher however few it holds. When the
kernel refuses one because a limit ran out, that subscription polls instead and
names the limit its refusal points to in a note, so the process notices changes
later rather than exiting.
"""

import errno
import os
import threading
import weakref
from pathlib import Path

from .findings import Finding, note
from .page_memory import memo
from .served_state.reading import outside_inputs, page_input, page_roots


class _Started:
    """The stop event a `watch` generator reads, which also says it has started.

    `watch` installs its native watcher when the generator first runs and only then
    looks up its stop event's `is_set`, so that first lookup marks the subscription
    installed, a step sooner than its first call would."""

    def __init__(self, stop: threading.Event):
        self.stop = stop
        self.installed = threading.Event()

    @property
    def is_set(self):
        self.installed.set()
        return self.stop.is_set


class FileChanges:
    """One owner's requested directories, pinned through native subscription.

    Missing directories subscribe their nearest existing ancestor, without its
    tree; if a selected root disappears while installing, the whole subscription
    replans before it is returned. An owner whose roots can change takes a new
    subscription when `matches` says the installed one no longer fits.
    """

    def __init__(self, roots: dict[Path, bool], accepts, *, collect: bool = False):
        while True:
            self.condition = threading.Condition()
            self.generation = 0
            self.error = None
            self.pending = set() if collect else None
            self.stop = threading.Event()
            self.threads = []
            self.roots = {}
            try:
                installed = _existing_roots(roots)
                # Keep the directory objects alive for exactly their subscription.
                # Linux can reuse a deleted directory's inode after an inotify watch
                # is revoked; an open descriptor prevents that identity alias.
                for path, recursive in installed.items():
                    self.roots[path] = (
                        recursive,
                        os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC),
                    )
                starts = []
                for recursive in (False, True):
                    paths = [
                        path
                        for path, nested in installed.items()
                        if nested == recursive
                    ]
                    if not paths:
                        continue
                    started = _Started(self.stop)
                    thread = threading.Thread(
                        target=self._run,
                        args=(paths, recursive, accepts, started),
                        daemon=True,
                    )
                    thread.start()
                    self.threads.append(thread)
                    starts.append(started)
                for started in starts:
                    started.installed.wait()
                if self.error:
                    raise self.error
            except FileNotFoundError:
                # Selecting, pinning and subscribing are one operation: a rename
                # can retire a root between any two steps, so plan again.
                self.close()
            except BaseException:
                self.close()
                raise
            else:
                return

    def matches(self, roots: dict[Path, bool]) -> bool:
        """Whether the installed, pinned directories still occupy these paths."""
        roots = _existing_roots(roots)
        if self.roots.keys() != roots.keys():
            return False
        for path, (recursive, descriptor) in self.roots.items():
            held = os.fstat(descriptor)
            if recursive != roots[path]:
                return False
            try:
                current = path.stat()
            except FileNotFoundError:
                return False
            if (held.st_dev, held.st_ino) != (current.st_dev, current.st_ino):
                return False
        return True

    def _run(self, paths, recursive, accepts, started):
        try:
            for changes in _changes(paths, recursive, accepts, started):
                with self.condition:
                    if self.pending is not None:
                        self.pending.update(path for _change, path in changes)
                    self.generation += 1
                    self.condition.notify_all()
            if not self.stop.is_set():
                raise RuntimeError("the filesystem subscription was interrupted")
        except Exception as error:  # noqa: BLE001 - propagate watcher failures to its owner
            with self.condition:
                self.error = error
                self.condition.notify_all()
        finally:
            started.installed.set()

    def mark(self) -> int:
        with self.condition:
            if self.error:
                raise self.error
            return self.generation

    def wait(self, generation: int, timeout: float | None) -> bool:
        with self.condition:
            changed = self.condition.wait_for(
                lambda: (
                    self.error is not None
                    or self.stop.is_set()
                    or self.generation != generation
                ),
                timeout=timeout,
            )
            if self.error:
                raise self.error
            return changed

    def close(self) -> None:
        self.stop.set()
        with self.condition:
            self.condition.notify_all()
        for thread in self.threads:
            thread.join()
        while self.roots:
            _path, (_recursive, descriptor) = self.roots.popitem()
            os.close(descriptor)

    def batch(self, timeout: float) -> set[str]:
        """Consume retained paths for a single batch reader, or an idle timeout."""
        if self.pending is None:
            raise RuntimeError("path batches require a collecting subscription")
        with self.condition:
            self.condition.wait_for(
                lambda: self.error is not None or self.stop.is_set() or self.pending,
                timeout=timeout,
            )
            if self.error:
                raise self.error
            paths = self.pending.copy()
            self.pending.clear()
            return paths


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


def _changes(paths, recursive, accepts, started):
    """The batches `watch` reports for these roots, polled when the kernel has no
    native watcher left to give. Exhaustion arises only while the watcher is
    created, before `started` reports it installed (notify drops a later watch it
    can't add), so the polling watcher misses no change the native one reported."""
    from watchfiles import watch

    options = {
        "watch_filter": lambda _change, path: accepts(Path(path)),
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
    """One shared native subscription; row and lifetime consumers stay independent.

    A row fold may wait for a page writer while retirement must remain runnable.
    Both consumers hold their own notification generation on this shared watcher.
    """

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
        if self.release is not None:
            self.release()
        watched = target_paths(targets)
        self.changes = FileChanges(
            roots,
            lambda changed: page_input(page, changed) or changed in watched,
        )
        # Threads retain FileChanges, never this memo owner. Discarding an unheld
        # page memory therefore closes and joins its provider.
        self.release = weakref.finalize(self, self.changes.close)
        self.targets = targets


def _page_plan(page: Path) -> tuple[set[Path], dict[Path, bool]]:
    targets = outside_inputs(page)
    return targets, {target.parent: False for target in targets} | page_roots(page)


def page_changes(page: Path) -> tuple[FileChanges, int]:
    """The process's shared page subscription, refreshed when the page's
    subdirectories, its claim or its file grants move what it watches, and the
    generation to wait from. An owner reads the page after taking both, and takes
    them again after each wake, which is how a new subdirectory joins the watch."""
    return memo(page, _PageChanges).connect(page)
