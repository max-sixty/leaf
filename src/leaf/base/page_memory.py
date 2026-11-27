"""What a process keeps of a page between readings, and for how long.

Some readings of a page are dear to repeat: a revision's parse, a candidate's capture
and check, the page's vocabulary, the activation answer, the presence token, the
events its log holds. Others are what a later answer is built from, such as the
readings the page's server last sent. Each is kept in the page's `PageMemory` under
one of these rules, so a kept reading is never stale, only dropped:

- A reading of files is kept beside their stamps and made again once one moves
  (`revision_artifact.read_revision`, `revisioning.held_activation`). A reading made
  over the page's layer is kept beside the layer's vocabulary and made again once
  another replaces it (`revision_artifact._Revisions`). A reading of the log, which
  only grows, is kept beside the place in the log it read to, and reads on from there
  (`event_log.read_events`).
- A reading keyed by a name that never changes meaning is kept as it was made: a
  revision's marker names one bundle for good (`revision_artifact.read_artifact`).
- A fact no file carries, such as whether another page's server is still running, is
  observed again once a time bound passes (`presence.PRESENCE_CACHE_S`).
- The readings the page's server last sent are kept as the baselines a later answer is
  patched from, the most recent few (`served_state.tail`). Each is named by its
  content and never sent again, so none can go stale.

A memory also holds what lasts as long as the process keeps the page: the page's
change subscription (`file_changes.page_changes`) and the mark of a page Leaf deletes
(`revision_artifact.Disposable`).

A process keeps the memories of the eight pages it read most recently (`PageMemories`),
and any memory something else still references (`memory_of`): a sample holds its own
and its parent's for its life (`samples.Sample`), however many sibling samples a
gallery opens.

A one-page server reads its own page and the samples it serves, and nothing of any
other page: a neighbour's panel row reads small files and keeps nothing
(`presence.other_leaves`). A command reads one page or a few. The website, and the
test suite serving a fresh page per test, read many, and keep the last eight however
many they read. A page read again after it was dropped is read afresh, which costs
time and never correctness.

A reader takes its part with `memo(page_dir, kind)`. Each `kind` is a class in the
module that reads it, so what is kept and when it goes stale stay with that module;
this one owns only how long it lasts.

A pure function of its arguments, which no file can make stale, is memoized at module
level instead, bounded by entry count (`styles._read_css`,
`events._fragment`). So is a reading of the machine rather than of a page, in
one slot replaced whole (`presence.neighbor_candidates`, `harness._registry_listing`).
So is the layer a selection of shared package roots alone composes, one per
selection, since many pages read it alike; a layer that reads a page's own copy of a
package is kept in that page's memory instead, beside the copy's stamp
(`layer._held`). What a page reads in either layer, such as its revisions'
vocabularies, is kept in the page's memory, so a layer many pages read holds nothing
of any one of them. A reading that takes seconds and that requests arriving together
all need, such as either layer, is kept with `once`, so the first of those requests
makes it and the rest wait for it rather than each making it again.
"""

import threading
import weakref
from collections.abc import Callable
from pathlib import Path
from typing import cast


class PageMemory:
    """One page's kept readings: one instance of each memo kind, made on first ask."""

    def __init__(self) -> None:
        self._memos: dict[type, object] = {}
        self._lock = threading.Lock()

    def memo[T](self, kind: type[T]) -> T:
        with self._lock:
            held = self._memos.get(kind)
            if held is None:
                held = self._memos[kind] = kind()
            return cast(T, held)


class Slot:
    """One kept reading and the key it answers, replaced whole, so a thread never
    pairs one key with another's reading. A memory keeps one instance per class, so
    each reading subclasses it once."""

    _held: tuple | None = None

    def get[T](self, key, read: Callable[[], T]) -> T:
        """The reading `key` names, made with `read` when the slot holds another."""
        held = self._held
        if held is not None and held[0] == key:
            return held[1]
        value = read()
        self._held = (key, value)
        return value


class Stamped:
    """Readings by key, each kept beside the stamps of what else it depends on and
    replaced whole once those move. A memory keeps one instance per class, so each
    use subclasses it once."""

    def __init__(self) -> None:
        self._held: dict = {}
        self._lock = threading.Lock()

    def of(self, key, stamps: tuple) -> dict:
        """What is kept for `key` while what it depends on stamps as `stamps`, for
        `once` to fill."""
        with self._lock:
            held = self._held.get(key)
            if held is None or held[0] != stamps:
                held = self._held[key] = (stamps, {})
            return held[1]


def once[T](held: dict, key, read: Callable[[], T]) -> T:
    """The reading `key` names in `held`, made with `read` if `held` lacks it.

    Of several threads that ask at once for a key `held` lacks, the first makes the
    reading and the rest wait for it, where `functools.cache` lets each make its own.
    A page server meets that when requests reach it together before it has composed
    the page's layer, which each of them needs."""
    entry = held.get(key) or held.setdefault(key, _Once())
    return entry.get(read)


class _Once:
    """One reading, made by the first thread to ask for it while the rest wait. A
    failed reading is not kept, so the next thread to ask makes it again."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._made: tuple | None = None

    def get[T](self, read: Callable[[], T]) -> T:
        if self._made is None:
            with self._lock:
                if self._made is None:
                    self._made = (read(),)
        return self._made[0]


class PageMemories:
    """The memories of the pages read most recently, least recent first, and of any
    page whose memory is still referenced elsewhere."""

    LIMIT = 8

    def __init__(self) -> None:
        self._memories: dict[Path, PageMemory] = {}
        self._held: weakref.WeakValueDictionary[Path, PageMemory] = (
            weakref.WeakValueDictionary()
        )
        self._lock = threading.Lock()

    def of(self, page_dir: Path) -> PageMemory:
        """The memory of `page_dir`, now the most recently read."""
        # Callers mostly pass the resolved path already, so skip the syscalls then.
        page = page_dir if page_dir in self._memories else page_dir.resolve()
        with self._lock:
            memory = (
                self._memories.pop(page, None) or self._held.get(page) or PageMemory()
            )
            self._memories[page] = self._held[page] = memory
            while len(self._memories) > self.LIMIT:
                del self._memories[next(iter(self._memories))]
            return memory


_memories = PageMemories()


def memory_of(page_dir: Path) -> PageMemory:
    """The memory this process keeps for `page_dir`, kept at least as long as the
    caller holds it."""
    return _memories.of(page_dir)


def memo[T](page_dir: Path, kind: type[T]) -> T:
    """The `kind` this process keeps for `page_dir`."""
    return memory_of(page_dir).memo(kind)
