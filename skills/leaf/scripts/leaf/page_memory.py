"""What a process keeps of a page between readings, and for how long.

Some readings of a page are dear to repeat: a revision's parse, a candidate's capture
and check, the vendored vocabulary, the activation answer, the presence token. Each is
kept between reads and checked against the stamps of the files it read, so a kept
reading is never stale, only dropped. They are kept in a `PageMemory`. A process
keeps the memories of the eight pages it read most recently (`PageMemories`), and any
memory something else still references (`memory_of`): a sample holds its own for its
life (`samples.Sample`), however many sibling samples a gallery opens.

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
level instead, bounded by entry count (`revision_artifact._shared_registry`,
`thread_context._fragment`). So is a reading of the machine rather than of a page, in
one slot replaced whole (`presence.neighbor_candidates`, `host._registry_listing`).
"""

import threading
import weakref
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")


class PageMemory:
    """One page's kept readings: one instance of each memo kind, made on first ask."""

    def __init__(self) -> None:
        self._memos: dict[type, object] = {}
        self._lock = threading.Lock()

    def memo(self, kind: type[T]) -> T:
        with self._lock:
            held = self._memos.get(kind)
            if held is None:
                held = self._memos[kind] = kind()
            return held


class Slot:
    """One kept reading and the key it answers, replaced whole, so a thread never
    pairs one key with another's reading. A memory keeps one instance per class, so
    each reading subclasses it once."""

    _held: tuple | None = None

    def get(self, key, read: Callable[[], T]) -> T:
        """The reading `key` names, made with `read` when the slot holds another."""
        held = self._held
        if held is not None and held[0] == key:
            return held[1]
        value = read()
        self._held = (key, value)
        return value


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


def memo(page_dir: Path, kind: type[T]) -> T:
    """The `kind` this process keeps for `page_dir`."""
    return memory_of(page_dir).memo(kind)
