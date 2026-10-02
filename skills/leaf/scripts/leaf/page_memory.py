"""What a process keeps of a page between readings, and for how long.

Some readings of a page are dear to repeat: a revision's parse, a candidate's capture
and check, the vendored vocabulary, the activation answer, the presence token. Each is
kept between reads and checked against the stamps of the files it read. They are kept
in a `PageMemory`, which belongs to whoever answers for the page and lasts as long as
that owner holds it:

- a one-page server holds its page's memory for its life (`http.page_endpoint`);
- a sample holds its own until it is released (`samples.Sample`);
- a server reading a neighbour holds the neighbour's while it sees it serving
  (`presence.other_leaves`);
- an owner of a changing set of pages, a command (`__main__`) or a site
  (`leaf_website`), holds the memories of the pages it read most recently
  (`PageMemories`).

Nothing read from a page's files is kept process-wide. A process that reads many pages,
such as the test suite serving a fresh page per test, keeps only what its live owners
hold. A page nobody holds is read afresh on each call. That costs time and never
correctness.

An owner binds its memory around the work it does for the page (`holding`,
`holding_pages`), and a reader takes its part with `memo(page_dir, kind)`. The binding
is a context variable, so it follows a request onto the worker thread that answers it,
and a thread started bare holds nothing. Each `kind` is a class in the module that
reads it, so what is kept and when it goes stale stay with that module; this one owns
only how long it lasts.

A pure function of its arguments, which no file can make stale, is memoized at module
level instead, bounded by entry count (`revision_artifact._shared_registry`,
`thread_context._fragment`). So is a reading of the machine rather than of a page, in
one slot replaced whole (`presence.neighbor_candidates`, `host._registry_listing`).
"""

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
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
    """The memories an owner of a changing set of pages keeps: those of the pages it
    read most recently, so a long-lived command or a site holds a few pages' worth
    however many it reads over its life. A one-shot command reads fewer than that."""

    LIMIT = 8

    def __init__(self) -> None:
        self._memories: dict[Path, PageMemory] = {}
        self._lock = threading.Lock()

    def of(self, page_dir: Path) -> PageMemory:
        """The memory of `page_dir`, now the most recently read."""
        # Callers mostly pass the resolved path already, so skip the syscalls then.
        page = page_dir if page_dir in self._memories else page_dir.resolve()
        with self._lock:
            memory = self._memories.pop(page, None) or PageMemory()
            self._memories[page] = memory
            while len(self._memories) > self.LIMIT:
                del self._memories[next(iter(self._memories))]
            return memory


# Where each page read in this context is kept: a page's memory, or None.
_bound: ContextVar[Callable[[Path], PageMemory | None] | None] = ContextVar(
    "leaf_page_memory", default=None
)


@contextmanager
def _binding(lookup: Callable[[Path], PageMemory | None]) -> Iterator[None]:
    token = _bound.set(lookup)
    try:
        yield
    finally:
        _bound.reset(token)


def holding(page_dir: Path, memory: PageMemory):
    """Keep what the block reads of `page_dir` in `memory`, and nothing of any other
    page, even inside a command's `holding_pages`."""
    page = page_dir.resolve()
    return _binding(
        lambda path: memory if path == page_dir or path.resolve() == page else None
    )


def holding_pages(memories: PageMemories):
    """Keep what the block reads of each page in `memories`."""
    return _binding(memories.of)


def memo(page_dir: Path, kind: type[T]) -> T:
    """The bound memory's `kind` for `page_dir`, or a fresh one nobody keeps."""
    lookup = _bound.get()
    memory = lookup(page_dir) if lookup is not None else None
    return memory.memo(kind) if memory is not None else kind()
