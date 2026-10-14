"""Native filesystem subscriptions for quiet page and session maintenance.

The files remain authority; notifications only schedule another canonical read.
A subscription is installed before its first observation, and a generation taken
before that observation retains writes arriving during it. Clock-only lifetime
and activity transitions still have bounded timed reads. A page's subscription
accepts exactly the inputs its reading stamps (`served_state.reading`), so
diagnostics never wake it. watchfiles owns platform notifications and polling
fallback.
"""

import os
import threading
import weakref
from pathlib import Path

from watchfiles._rust_notify import WatchfilesRustInternalError
from watchfiles.main import (
    RustNotify,
    _default_debug,
    _default_force_polling,
    _default_ignore_permission_denied,
    _default_poll_delay_ms,
)

from .page_memory import memo
from .refusals import Refused
from .served_state.reading import outside_inputs, page_input


class FileChanges:
    """One owner's subscription, grouped by native recursive-watch semantics."""

    def __init__(self, roots: dict[Path, bool], accepts, *, collect: bool = False):
        self.condition = threading.Condition()
        self.generation = 0
        self.error = None
        self.pending = set() if collect else None
        self.stop = threading.Event()
        self.threads = []
        self.watchers = []
        self.roots = {}
        try:
            # Keep the directory objects alive for exactly their subscription.
            # Linux can reuse a deleted directory's inode after an inotify watch
            # is revoked; an open descriptor prevents that identity alias.
            for path, recursive in roots.items():
                self.roots[path] = (
                    recursive,
                    os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC),
                )
            polling = _default_force_polling(None)
            for recursive in (False, True):
                paths = [path for path, nested in roots.items() if nested == recursive]
                if not paths:
                    continue
                watcher = RustNotify(
                    [str(path) for path in paths],
                    _default_debug(None),
                    polling,
                    _default_poll_delay_ms(300),
                    recursive,
                    _default_ignore_permission_denied(None),
                )
                self.watchers.append(watcher)
                thread = threading.Thread(
                    target=self._run, args=(watcher, accepts), daemon=True
                )
                thread.start()
                self.threads.append(thread)
        except BaseException as error:
            self.close()
            _refuse_exhausted_watcher(error)
            raise

    def matches(self, roots: dict[Path, bool]) -> bool:
        """Whether the installed, pinned directories still occupy these paths."""
        if self.stop.is_set() or self.roots.keys() != roots.keys():
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

    def _run(self, watcher, accepts):
        try:
            while not self.stop.is_set():
                changes = watcher.watch(25, 50, 0, self.stop)
                if changes == "stop":
                    return
                if changes == "signal":
                    raise RuntimeError("the filesystem subscription was interrupted")
                if changes == "timeout":
                    continue
                with self.condition:
                    paths = {path for _change, path in changes if accepts(Path(path))}
                    if paths:
                        if self.pending is not None:
                            self.pending.update(paths)
                        self.generation += 1
                        self.condition.notify_all()
        except Exception as error:  # noqa: BLE001 - propagate watcher failures to its owner
            with self.condition:
                try:
                    _refuse_exhausted_watcher(error)
                except Refused as refusal:
                    error = refusal
                self.error = error
                self.condition.notify_all()

    def mark(self) -> int:
        with self.condition:
            if self.error:
                raise self.error
            return self.generation

    def wait(self, generation: int, timeout: float) -> bool:
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
        for watcher in self.watchers:
            watcher.close()
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


def _refuse_exhausted_watcher(error: BaseException) -> None:
    """Name the Linux resource limit when native watcher creation exhausts it."""
    if isinstance(error, WatchfilesRustInternalError) and "os error 24" in str(error):
        raise Refused(
            "Could not start a filesystem watcher: the inotify instance limit "
            "may be reached. Check fs.inotify.max_user_instances and close unused "
            "watching processes."
        ) from error


def existing_root(path: Path) -> Path:
    """The nearest directory whose notifications can discover a missing child."""
    while not path.is_dir():
        path = path.parent
    return path


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

    def connect(self, page: Path) -> FileChanges:
        targets = outside_inputs(page)
        roots = {existing_root(target.parent): False for target in targets}
        roots[existing_root(page.parent)] = False
        roots[existing_root(page)] = True
        with self.lock:
            if (
                self.changes is None
                or self.targets != targets
                or not self.changes.matches(roots)
            ):
                if self.release is not None:
                    self.release()
                watched = target_paths(targets)
                self.changes = FileChanges(
                    roots,
                    lambda changed: page_input(page, changed) or changed in watched,
                )
                # Threads retain FileChanges, never this memo owner. Discarding
                # an unheld page memory therefore closes and joins its provider.
                self.release = weakref.finalize(self, self.changes.close)
                self.targets = targets
            return self.changes


def page_changes(page: Path) -> FileChanges:
    """The process's shared page subscription, refreshed when the claim or the
    page's file grants move what it watches outside the page."""
    return memo(page, _PageChanges).connect(page)
