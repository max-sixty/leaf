"""Append-only event storage, application readings, locking, and attempt identity.

Stored events carry private native session context. It shares the event's durable
append and is stripped from application readings, returned records and attempt
comparisons.

A log reads through its last newline. The line after it is an append mid-flush,
or the tear a crash left, which the next append ends with a newline of its own.

A process keeps each page's log as it last read it (`LogMemory`) and reads only the
bytes appended since, since a later reading of an append-only file is the earlier
one and its tail. A reading is a `Log`, a list of the application records that also
names the continuous reading of the file it belongs to (`LogLineage`). A reader that
keeps a fold of the log (`folded`) keeps it with that lineage and steps it through
only the events appended since it last read, so an append and the reading after it
cost what the new event changes rather than what the log holds. The file stays the
record and a fold is a cache of it: a process that has not read the log yet, or a
reading of a list that is not a page's log, folds every event.

A later reading of the same file is told from a different file by the file's
identity (device and inode), its size, which only grows, and the bytes that ended
the last reading, still where they were. A log written anew fails one of them:
`start_log` replaces the file, and the replacement may reuse the inode number its
predecessor freed, while a fixture that rewrites the file in place fails the last.
Either starts a new lineage, whose folds start again from the first event. Only an
edit that left those bytes where they were would read as an extension, and nothing
writes the log but an append under its lease and `start_log`.
"""

import json
import os
import secrets
import signal
import sys
import threading
import weakref
from collections.abc import Callable, Iterable, Iterator
from copy import deepcopy
from pathlib import Path
from typing import Protocol

from leaf.files import file_stamp
from leaf.findings import Finding, Rejected
from leaf.page_memory import memo
from leaf.refusals import Refused
from leaf.registry.kernel import kernel_event_ownership
from leaf.state import (
    EVENTS_FILE,
    flocked,
    now_iso,
    replace_bytes,
)


def jsonl_line(event: dict) -> str:
    """One event as one physical line. U+2028, U+2029 and U+0085 are legal raw in
    JSON strings and line breaks to any splitlines()-shaped reader, so they are
    written as escapes — a pasted comment carrying one must not decide where an
    event ends. The log's own reader splits on the "\\n" the writer puts between
    events either way; the escape is for what `wait` and `page events` print, which
    stays one event per line for every consumer. json.dumps escapes every other
    line-breaking character on its own."""
    line = json.dumps(event, ensure_ascii=False)
    for ch in "\u2028\u2029\u0085":
        line = line.replace(ch, f"\\u{ord(ch):04x}")
    return line


class EventRefused(Rejected):
    """The append door turned one event down, on the one finding that says why.

    Raised by `event_contracts.append_admitted`, the one door every writer
    appends through, and answered by the browser's endpoint as an event rejection.
    The finding carries the refused event's `kind` beside what it names."""

    def __init__(self, finding: Finding, event: dict):
        super().__init__([finding.but(values={"kind": event.get("kind")})])


class AttemptConflict(EventRefused):
    """One browser attempt was reused for a different event payload."""


# The envelope the append lease itself assigns. Admission validates the complete
# record, so pre-admission shape checks supply representative envelope fields.
# Semantic admission allocates the real identity before folding the candidate.
# A caller supplying an envelope field is held to the contract's reading of it.
APPEND_STAMPED = {"id": "pending", "ts": "pending", "seq": 1}


def _attempt_payload(event: dict) -> dict:
    # Kind is part of the gesture. Only fields the server assigns disappear from
    # the equality check: the append envelope, what admission derives, the author
    # each writer stamps, and the publication a revision write names.
    assigned = {
        *APPEND_STAMPED,
        *kernel_event_ownership()["derived"],
        "author",
        "publication",
    }
    return {key: value for key, value in event.items() if key not in assigned}


class Fold(Protocol):
    """A reading of the log made one event at a time from the first, which a reader
    may keep with the log's lineage (`folded`).

    A fold makes every change through the `Changes` it was last given (`use`), so it
    can read events the log does not hold yet and then be reverted to stand as it
    was, at the cost of what those events changed rather than a copy of the fold."""

    def step(self, event: dict) -> None:
        """Take the log's next event into the fold."""

    def use(self, changes: "Changes") -> None:
        """Make every later change through `changes`."""

    def reading(self):
        """What the fold has read so far, which later steps leave unchanged. A
        reading while changes are recorded leaves the fold as it found it."""


class Changes:
    """The changes a fold makes, and while `recording`, the inverse of each, newest
    last, which `revert` applies. A fold that is not trying candidates holds the
    one that records nothing (`PLAIN`)."""

    def __init__(self, *, recording: bool = False) -> None:
        self.recording = recording
        self._inverse: list[Callable[[], None]] = []

    def put(self, mapping, key, value) -> None:
        """Set `key` of a mapping, or an index a list holds already."""
        if self.recording:
            try:
                previous = mapping[key]
            except KeyError:
                previous = _MISSING
            self._inverse.append(lambda: _restore(mapping, key, previous))
        mapping[key] = value

    def remove(self, mapping, key, *, keep_order: bool = True):
        """Take `key` out of `mapping`. Reverting puts it back, in its place where
        `keep_order`, which costs the keys after it, and last otherwise."""
        if not self.recording:
            return mapping.pop(key)
        later = []
        if keep_order:
            for other in reversed(mapping):
                if other == key:
                    break
                later.append(other)
        value = mapping.pop(key)
        self._inverse.append(lambda: _reinsert(mapping, key, value, later[::-1]))
        return value

    def add(self, members: set, item) -> None:
        if self.recording and item not in members:
            self._inverse.append(lambda: members.discard(item))
        members.add(item)

    def append(self, items: list, item) -> None:
        if self.recording:
            self._inverse.append(items.pop)
        items.append(item)

    def setattr(self, owner, name: str, value) -> None:
        if self.recording:
            previous = getattr(owner, name)
            self._inverse.append(lambda: setattr(owner, name, previous))
        setattr(owner, name, value)

    def revert(self) -> None:
        for inverse in reversed(self._inverse):
            inverse()
        self._inverse.clear()


PLAIN = Changes()
_MISSING = object()


def _restore(mapping, key, previous) -> None:
    if previous is _MISSING:
        del mapping[key]
    else:
        mapping[key] = previous


def _reinsert(mapping, key, value, later: list) -> None:
    mapping[key] = value
    for other in later:
        mapping[other] = mapping.pop(other)


class LogLineage:
    """One continuous reading of one log file and what is kept with it: the ids and
    attempts the file holds, and the folds readers keep (`folded`).

    A fold is kept beside an `anchor`, the reading of whatever else it reads, such as
    the document a projection folds the log against, and lives no longer than that
    anchor: a reading made for one check takes its folds with it when it goes."""

    def __init__(self) -> None:
        self.ids: set[str] = set()
        self.attempts: dict[str, dict] = {}
        # anchor → key → [how many of the file's events the fold has taken, the fold]
        self._folds: weakref.WeakKeyDictionary[object, dict[object, _Kept]] = (
            weakref.WeakKeyDictionary()
        )
        self._lock = threading.RLock()

    def took(self, events: Iterable[dict]) -> None:
        for event in events:
            if identity := event.get("id"):
                self.ids.add(identity)
            if attempt := event.get("attempt"):
                self.attempts.setdefault(attempt, event)

    def fold(self, log: "Log", anchor: object, key, start: Callable[[], Fold]):
        with self._lock:
            kept = self._folds.setdefault(anchor, {})
            held = kept.get(key)
            if held is not None and held.taken > log.stored:
                # A reading taken before an append another thread has read since.
                return _fold_all(log, start)
            if held is None:
                held = kept[key] = _Kept(start())
            try:
                for event in log[held.taken : log.stored]:
                    held.fold.step(event)
                    held.taken += 1
            except BaseException:
                # A step that raised may have changed part of the fold; the next
                # reading folds afresh and meets the same event.
                del kept[key]
                raise
            if log.stored == len(log):
                return held.fold.reading()
            # The candidates are read into the kept fold and taken back out, under
            # the lock, so no other reader sees them.
            changes = Changes(recording=True)
            held.fold.use(changes)
            try:
                for event in log[log.stored :]:
                    held.fold.step(event)
                return held.fold.reading()
            finally:
                changes.revert()
                held.fold.use(PLAIN)


class _Kept:
    """One kept fold and how many of the file's events it has taken."""

    __slots__ = ("fold", "taken")

    def __init__(self, fold: Fold) -> None:
        self.fold = fold
        self.taken = 0


class Log(list):
    """One reading of a page's log: its application records in order.

    A list, so a reader iterates it as it would any list of events. It also names
    its lineage, how many lines it read, a torn one included as `seq` counts it, and
    how many of its events the file holds: `plus` makes a log with candidates the
    file does not hold yet, which admission folds to read the page as an append
    would leave it. A kept fold reads them and is reverted (`Fold.use`).

    Each reading is a list of its own, a copy of references costing about 14 µs at
    4,000 events; the folds kept with the lineage are never copied."""

    __slots__ = ("lineage", "lines", "stored")

    def __init__(
        self,
        events: Iterable[dict],
        lineage: LogLineage,
        lines: int,
        stored: int | None = None,
    ):
        super().__init__(events)
        self.lineage = lineage
        self.lines = lines
        self.stored = len(self) if stored is None else stored

    def plus(self, *events: dict) -> "Log":
        return Log([*self, *events], self.lineage, self.lines, self.stored)

    def __reduce__(self):
        # A copy, a deep copy for a frozen capture included, is a list like any
        # other: what it holds may change apart from the file.
        return list, (list(self),)


def _fold_all(events: Iterable[dict], start: Callable[[], Fold]):
    fold = start()
    for event in events:
        fold.step(event)
    return fold.reading()


def folded(events: list, anchor: object | None, key, start: Callable[[], Fold]):
    """The reading of `start()`'s fold stepped through `events`.

    Where `events` is a reading of a page's log (`Log`) and `anchor` is given, the
    fold is kept with the log's lineage beside `anchor`, under `key`, and a later
    reading of the log steps it through only what was appended since. `anchor` and
    `key` together name every input of the fold besides the log, so the fold kept
    under them is the one `start()` would make. Any other list is folded whole."""
    if anchor is None or not isinstance(events, Log):
        return _fold_all(events, start)
    return events.lineage.fold(events, anchor, key, start)


def extended(events: list, *more: dict) -> list:
    """`events` with `more` after them: the log an append would leave, which the
    folds kept for `events` read where it is a page's log."""
    return events.plus(*more) if isinstance(events, Log) else [*events, *more]


def _held_ids(events: list[dict]):
    if isinstance(events, Log):
        return events.lineage.ids
    return {existing.get("id") for existing in events}


def _matching_attempt(events: list[dict], event: dict) -> dict | None:
    attempt = event.get("attempt")
    if not attempt:
        return None
    if isinstance(events, Log):
        existing = events.lineage.attempts.get(attempt)
        if existing is not None and existing["seq"] > events.lines:
            existing = None
    else:
        existing = next((e for e in events if e.get("attempt") == attempt), None)
    if existing is None:
        return None
    if _attempt_payload(existing) != _attempt_payload(event):
        raise AttemptConflict(
            Finding("attempt-conflict", values={"attempt": attempt}), event
        )
    return deepcopy(existing)


def new_event_id(events: list[dict]) -> str:
    """An unused page-local identity, allocated under the append lease.

    Eight hex characters stay short enough to read and retype. Uniqueness comes
    from checking the held log, not their width; a harness pairs the id with its page.
    Admission allocates it before semantic folding and storage keeps that identity.
    """
    held = _held_ids(events)
    while True:
        candidate = secrets.token_hex(4)
        if candidate not in held:
            return candidate


class LogMemory:
    """A page's log as this process last read it (module header)."""

    # How many of the bytes that ended the last reading a later one compares.
    BOUNDARY = 64

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._log: Log | None = None
        self._file: tuple[int, int] | None = None
        self._offset = 0
        self._boundary = b""

    def read(self, f) -> Log:
        """The log `f`, a binary handle open on it, holds through its last newline."""
        fd = f.fileno()
        with self._lock:
            stat = os.fstat(fd)
            log = self._log
            if (
                log is None
                or (stat.st_dev, stat.st_ino) != self._file
                or stat.st_size < self._offset
                or os.pread(fd, len(self._boundary), self._offset - len(self._boundary))
                != self._boundary
            ):
                log = Log([], LogLineage(), 0)
                self._file = (stat.st_dev, stat.st_ino)
                self._offset, self._boundary = 0, b""
            if stat.st_size > self._offset:
                data = os.pread(fd, stat.st_size - self._offset, self._offset)
                complete = data[: data.rfind(b"\n") + 1]
                if complete:
                    events = _parse_events(complete, log.lines)
                    log.lineage.took(events)
                    log = Log(
                        [*log, *events], log.lineage, log.lines + complete.count(b"\n")
                    )
                    self._offset += len(complete)
                    self._boundary = (self._boundary + complete)[-self.BOUNDARY :]
            self._log = log
            return log


def read_log(page_dir: Path, f) -> Log:
    """The log that `f`, a binary handle open on `page_dir`'s log, holds."""
    return memo(page_dir, LogMemory).read(f)


def _append_event_unlocked(
    f, event: dict, events: Log, *, context: dict | None = None
) -> dict:
    """Append while the caller holds this log file's exclusive lease, where `events`
    is the log read under it.

    Attempt identity is the append door's (`event_contracts.append_admitted`): it
    reads the log under this same lease before its gates, so two server threads
    cannot both observe an attempt's absence and append it twice."""
    if "id" in event:
        if event["id"] in events.lineage.ids:
            raise ValueError(f"event id {event['id']!r} already exists")
    else:
        event["id"] = new_event_id(events)
    event.setdefault("ts", now_iso())
    # A crash can tear the previous append mid-line: SIGKILL under a buffered
    # flush, a full disk. The line discipline is the writer's, so the writer
    # restores it — without this, the next event glues onto the torn fragment
    # and one lost event becomes an unreadable line mid-file. The log read under
    # the lease counted every line through the last newline, so this event's line
    # follows those and the fragment.
    lines = events.lines
    f.seek(0, os.SEEK_END)
    if f.tell():
        f.seek(-1, os.SEEK_END)
        if f.read(1) != b"\n":
            f.write(b"\n")
            lines += 1
    seq = lines + 1
    stored = event if context is None else {**event, "context": context}
    f.write((jsonl_line(stored) + "\n").encode())
    # To the platter before the caller is told it landed: an event is a
    # decision, the sender's 200 (or a CLI exit 0) is the claim it is kept,
    # and events are rare enough that a flush per append costs nothing.
    f.flush()
    os.fsync(f.fileno())
    # The record as every reader reads it back: seq is its line number, which the
    # stored line does not carry.
    return {**event, "seq": seq}


def start_log(page_dir: Path, events: list[dict] | tuple[dict, ...] = ()) -> None:
    """Start a page's log holding `events`, each already admitted, in order: empty
    for a page `page init` starts, or a sample's starting history (`samples`). The
    log's inode is the page's successful-init marker, so it is written whole."""
    stored = "".join(
        jsonl_line({key: value for key, value in event.items() if key != "seq"}) + "\n"
        for event in events
    )
    replace_bytes([(page_dir / EVENTS_FILE, stored.encode(), False)])


def append_event(page_dir: Path, event: dict) -> dict:
    # This low-level fixture seam can start a log in an existing directory.
    from .interaction_log import session_context

    log = page_dir / EVENTS_FILE
    with open(log, "a", encoding="utf-8"):
        pass
    with flocked(log) as f:
        return _append_event_unlocked(
            f,
            event,
            read_log(page_dir, f),
            context=session_context(event.get("session")),
        )


def _parse_events(data: bytes, before: int = 0) -> list[dict]:
    """The events in `data`, whose first line is the log's line `before + 1`."""
    events = []
    # The log's grammar is events joined by "\n" — the writer's own separator,
    # not splitlines()'s wider class, which once read a U+2028 inside a comment's
    # text as a break and left half an event leading a line no parse could take.
    # Bytes, decoded per line: a crash can tear mid-character as easily as
    # mid-line (ensure_ascii=False writes multi-byte UTF-8), and one strict
    # read_text of the file would raise on the tear before any line-level
    # tolerance could reach it.
    lines = data.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            event = json.loads(line.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            # The tear a crash left, standing alone because the next append
            # ended its line: that event's sender already saw its send fail, the
            # seqs around it hold, and there is nothing anyone could do with a
            # fragment — so it is skipped, not raised over, and the page keeps
            # reading.
            continue
        event.pop("context", None)
        event["seq"] = before + i + 1
        events.append(event)
    return events


def read_events(page_dir: Path) -> list:
    try:
        with open(page_dir / EVENTS_FILE, "rb") as f:
            return read_log(page_dir, f)
    except FileNotFoundError:
        return []


def _line_start(data: bytes, n: int) -> int:
    """Where line `n + 1` of `data` starts: past its `n`th newline, or at its end."""
    at = 0
    for _ in range(n):
        at = data.find(b"\n", at) + 1
        if not at:
            return len(data)
    return at


def follow_events(page_dir: Path, after: int) -> Iterator[dict]:
    """Every event after seq `after`, then each one appended from here on, forever.

    It waits on the page's native subscription (`file_changes.page_changes`), so an
    event any process appends wakes it, and each wake compares the log's own stamp
    with the one taken before the last read. A moved stamp reads only the bytes past
    what was already read, and only through the last newline: the line after it is
    an append mid-flush, whose rest moves the stamp again. Seq is the line number, so
    the lines read are counted whether or not they parse, exactly as `_parse_events`
    counts them; the lines at or before `after` are counted without being parsed.

    The offset read so far is a position in the file first opened, and appends
    only ever grow that file. A log that is another file now (a rename put a new
    one in its place) or shorter than what was read is not the log being
    followed, and reading on from the old offset would print its middle under the
    wrong seqs, so the follower ends there, as it does when the log is removed.
    """
    # file_changes reads the page's inputs, which reach back here through `service`.
    from leaf.file_changes import page_changes

    log = page_dir / EVENTS_FILE
    gone = FileNotFoundError(f"{log} is gone")
    read = lines = 0
    followed = None
    stamp = file_stamp(log)
    while True:
        if stamp is None:
            raise gone
        try:
            with open(log, "rb") as f:
                opened = os.fstat(f.fileno())
                followed = followed or opened.st_ino
                if opened.st_ino != followed or opened.st_size < read:
                    raise gone
                f.seek(read)
                data = f.read()
        except FileNotFoundError:
            raise gone from None
        complete = data[: data.rfind(b"\n") + 1]
        unread = _line_start(complete, max(0, after - lines))
        yield from _parse_events(
            complete[unread:], lines + complete.count(b"\n", 0, unread)
        )
        read += len(complete)
        lines += complete.count(b"\n")
        seen = stamp
        while (stamp := file_stamp(log)) == seen:
            # The generation is taken before the stamp it confirms, so an append
            # between the two still ends the wait.
            changes, generation = page_changes(page_dir)
            if file_stamp(log) == seen:
                # A signal may reach a watcher thread while Python's main thread
                # waits here, leaving its handler pending until this wait ends.
                changes.wait(generation, 1.0)


def cmd_events(page_dir: Path, after: int, *, follow: bool = False) -> None:
    """Print each event after `after` as the log reads back, and with `follow` each
    one appended from then on, until stopped.

    A reader that goes away is the ordinary end rather than a failure, whether
    `head` closed the pipe or a follower's consumer stopped it: SIGINT, SIGTERM, and
    a closed stdout all exit 0. Each line is flushed as it is printed, since a
    follower's stdout is a pipe whose reader waits on that line.
    """
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    records = (
        follow_events(page_dir, after)
        if follow
        else (event for event in read_events(page_dir) if event["seq"] > after)
    )
    try:
        for event in records:
            print(jsonl_line(event), flush=True)
    except KeyboardInterrupt:
        sys.exit(0)
    except BrokenPipeError:
        # The interpreter flushes stdout again on exit, into the same closed pipe.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
    except FileNotFoundError as error:
        raise Refused(str(error)) from error
