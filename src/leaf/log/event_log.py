"""Append-only event storage, application readings, locking, and attempt identity.

Stored events carry private native session context. It shares the event's durable
append and is stripped from application readings, returned records and attempt
comparisons.
"""

import json
import os
import secrets
import signal
import sys
import threading
from collections.abc import Generator, Iterable, Iterator
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path

from leaf.base.files import file_stamp
from leaf.base.findings import Finding, Rejected
from leaf.base.page_memory import memo
from leaf.base.refusals import Refused
from leaf.base.state import (
    EVENTS_FILE,
    flocked,
    now_iso,
    replace_bytes,
    session_record,
)
from leaf.source.registry.kernel import kernel_event_ownership


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


def matching_attempt(events: list[dict], event: dict) -> dict | None:
    """The record an earlier send of `event`'s attempt left in `events`, or None
    where none did. The same attempt sent with another payload raises
    `AttemptConflict`. The append door reads it under the log's lease
    (`event_contracts.append_admitted`)."""
    attempt = event.get("attempt")
    if not attempt:
        return None
    for existing in events:
        if existing.get("attempt") != attempt:
            continue
        if _attempt_payload(existing) != _attempt_payload(event):
            raise AttemptConflict(
                Finding("attempt-conflict", values={"attempt": attempt}), event
            )
        return deepcopy(existing)
    return None


def logged_ids(events: list[dict]) -> set[str]:
    """Every event identity the log holds. A command's ID names a widget or a message
    in one address space, so markup may not take one (`ids-taken-by-events`)."""
    return {event["id"] for event in events if "id" in event}


def new_event_id(events: list[dict]) -> str:
    """An unused page-local identity, allocated under the append lease.

    Eight hex characters stay short enough to read and retype. Uniqueness comes
    from checking the held log, not their width; a harness pairs the id with its page.
    Admission allocates it before semantic folding and storage keeps that identity.
    """
    taken = logged_ids(events)
    while True:
        candidate = secrets.token_hex(4)
        if candidate not in taken:
            return candidate


def end_last_line(f) -> None:
    """End the log's last line, under its exclusive lease, before an append and
    before a transaction reads the log (`transaction.PageTransaction`).

    A crash can tear an append mid-line: SIGKILL under a buffered flush, a full
    disk. The line discipline is the writer's, so the lease holder restores it.
    Without this, the next event glues onto the torn fragment and one lost event
    becomes an unreadable line mid-file. And a reader takes only whole lines
    (`_Tail`), so a record the tear left complete but for its newline would stay
    unread, and a retry of its attempt would be appended again."""
    f.seek(0, os.SEEK_END)
    if f.tell():
        f.seek(-1, os.SEEK_END)
        if f.read(1) != b"\n":
            f.write(b"\n")
            f.flush()


def append_event_unlocked(
    f, event: dict, events: list[dict], *, context: dict | None = None
) -> dict:
    """Append while the caller holds this log file's exclusive lease.

    Attempt identity is the append door's (`event_contracts.append_admitted`): it
    reads the log under this same lease before its gates, so two server threads
    cannot both observe an attempt's absence and append it twice."""
    if "id" in event:
        if event["id"] in logged_ids(events):
            raise ValueError(f"event id {event['id']!r} already exists")
    else:
        event["id"] = new_event_id(events)
    event.setdefault("ts", now_iso())
    end_last_line(f)
    f.seek(0)
    seq = f.read().count(b"\n") + 1
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


def initialized(page_dir: Path) -> bool:
    """Whether `page_dir` is an initialized page, which is whether its event log is
    a file.

    `page init` writes the log last and whole (`start_log`), after the package
    copies and the layer record, so a directory without a log is not yet a page,
    whatever else it holds. A lock on the log opens it without creating it
    (`state.flocked`), so a transaction racing the page's deletion can't make the
    directory a page again."""
    return (page_dir / EVENTS_FILE).is_file()


def start_log(page_dir: Path, events: list[dict] | tuple[dict, ...] = ()) -> None:
    """Start a page's log holding `events`, each already admitted, in order: empty
    for a page `page init` starts, or a sample's starting history (`samples`). It is
    written whole, since its inode marks the page `initialized`."""
    stored = "".join(
        jsonl_line({key: value for key, value in event.items() if key != "seq"}) + "\n"
        for event in events
    )
    replace_bytes([(page_dir / EVENTS_FILE, stored.encode(), False)])


def session_context(session: str | None, claim: dict | None = None) -> dict | None:
    """Capture native session metadata as it stands at the write boundary."""
    if session is None:
        return None
    from leaf.base.harness import session_harness

    owner = claim if claim and claim["id"] == session else None
    writer = session_harness() if owner is None else None
    lifecycle = session_record(session)
    return {
        "harness": owner["harness"]
        if owner
        else writer.name
        if writer and writer.session == session
        else None,
        "cwd": owner.get("cwd") if owner else None,
        "transcript_path": lifecycle.get("transcript_path") if lifecycle else None,
        "turn": lifecycle["turn"] if lifecycle else None,
        "provider": lifecycle["provider"] if lifecycle else None,
    }


def append_event(page_dir: Path, event: dict) -> dict:
    # This low-level fixture seam can start a log in an existing directory.
    log = page_dir / EVENTS_FILE
    with open(log, "a", encoding="utf-8"):
        pass
    with flocked(log) as f:
        f.seek(0)
        events = _parse_events(f.read())
        return append_event_unlocked(
            f, event, events, context=session_context(event.get("session"))
        )


def _stored_events(data: bytes, before: int = 0) -> list[dict]:
    """The events in `data` as the log stores them, private session `context`
    included, each numbered by its line as `seq`, the first being the log's line
    `before + 1`."""
    events = []
    # The log's grammar is events joined by "\n" — the writer's own separator,
    # not splitlines()'s wider class, which reads a U+2028 inside a comment's
    # text as a break and leaves half an event leading a line no parse can take.
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
            # The final line is a concurrent append mid-flush, complete on the
            # next read. An earlier one is the tear a crash left, standing alone
            # because append_event_unlocked repairs the discipline before
            # writing: that event's sender already saw its send fail, the seqs
            # around it hold,
            # and there is nothing anyone could do with a fragment — so it is
            # skipped, not raised over, and the page keeps reading.
            continue
        event["seq"] = before + i + 1
        events.append(event)
    return events


def _parse_events(data: bytes, before: int = 0) -> list[dict]:
    """The events in `data` as application readings take them (`_stored_events`),
    less their private session context."""
    events = _stored_events(data, before)
    for event in events:
        event.pop("context", None)
    return events


class _Read:
    """The events one page's log holds and the attempts they were sent with, as this
    process has read them so far, beside the place in the log they were read to."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.tail: _Tail | None = None
        self.events: list[dict] = []
        self.attempts: set[str] = set()

    def read_on(self, log: Path) -> None:
        """Read on to the end of `log`, under `lock`."""
        self.tail = self.tail or _Tail(log)
        try:
            events = self.tail.read_on()
        except FileNotFoundError:
            # Another log from here on, read whole, or none.
            self.tail, self.events, self.attempts = _Tail(log), [], set()
            try:
                events = self.tail.read_on()
            except FileNotFoundError:
                return
        self.events += events
        self.attempts.update(
            event["attempt"] for event in events if event.get("attempt")
        )


@contextmanager
def _read(page_dir: Path) -> Generator[_Read]:
    """The page's kept reading of its log (`page_memory`), read on to the log's end
    and held for the block."""
    held = memo(page_dir, _Read)
    with held.lock:
        held.read_on(page_dir.resolve() / EVENTS_FILE)
        yield held


def read_events(page_dir: Path) -> list[dict]:
    """Every event in the page's log, as application readings take them
    (`_parse_events`), or none where the page has no log.

    The page's memory keeps the events read so far, and each read parses only the
    lines appended since (`_Tail`), so parsing costs what the log gained since the
    last read, not its length. The list is the caller's, but every reader of the
    page in this process shares its events, so none may change one in place."""
    with _read(page_dir) as held:
        return list(held.events)


def read_stored_events(page_dir: Path) -> list[dict]:
    """Every event in the page's log as stored, private session context included,
    for the page's diagnostics (`interaction_log.read_interactions`)."""
    path = page_dir / EVENTS_FILE
    if not path.exists():
        return []
    return _stored_events(path.read_bytes())


def _line_start(data: bytes, n: int) -> int:
    """Where line `n + 1` of `data` starts: past its `n`th newline, or at its end."""
    at = 0
    for _ in range(n):
        at = data.find(b"\n", at) + 1
        if not at:
            return len(data)
    return at


class _Tail:
    """A reader's place in one log: the file it first opened, and the bytes and lines
    it has read there.

    Each read takes only the bytes past that place, and only through the last
    newline: the line after it is an append mid-flush, whose rest a later read
    takes. Seq is the line number, so the lines read are counted whether or not they
    parse, exactly as `_parse_events` counts them. Appends only ever grow the file
    first opened, so a log that is another file now (a rename put a new one in its
    place) or shorter than what was read is not the log this place is in: reading
    on would take its middle under the wrong seqs, so the read raises
    FileNotFoundError, as it does where the log is gone."""

    def __init__(self, log: Path) -> None:
        self.log = log
        self.inode: int | None = None
        self.read = self.lines = 0

    def read_on(self, after: int = 0) -> list[dict]:
        """The events appended since the last read, less those at or before seq
        `after`, which are counted without being parsed."""
        with open(self.log, "rb") as f:
            opened = os.fstat(f.fileno())
            self.inode = self.inode or opened.st_ino
            if opened.st_ino != self.inode or opened.st_size < self.read:
                raise FileNotFoundError(f"{self.log} is another file now")
            f.seek(self.read)
            data = f.read()
        complete = data[: data.rfind(b"\n") + 1]
        unread = _line_start(complete, max(0, after - self.lines))
        events = _parse_events(
            complete[unread:], self.lines + complete.count(b"\n", 0, unread)
        )
        self.read += len(complete)
        self.lines += complete.count(b"\n")
        return events


def admitted_attempts(page_dir: Path, attempts: Iterable[str]) -> set[str]:
    """Which of `attempts` the page's log holds an event sent with. The log keeps every
    attempt it admitted, so an answer never lapses. The page's memory keeps the
    attempts beside the events read so far (`_read`), so asking, as each draft write
    does, costs what the log gained since the last read, not its length."""
    with _read(page_dir) as held:
        return held.attempts.intersection(attempts)


def follow_events(page_dir: Path, after: int) -> Iterator[dict]:
    """Every event after seq `after`, then each one appended from here on, forever.

    It waits on the page's native subscription (`file_changes.page_changes`), so an
    event any process appends wakes it, and each wake compares the log's own stamp
    with the one taken before the last read. A moved stamp reads on from the
    follower's place in the log (`_Tail`), and a log that is another file now or
    gone ends the follower.
    """
    # Only a follower waits on the page's changes, so the log's other readers, the
    # cold hooks among them, don't load the page's inputs.
    from leaf.log.file_changes import page_changes

    log = page_dir / EVENTS_FILE
    gone = FileNotFoundError(f"{log} is gone")
    tail = _Tail(log)
    stamp = file_stamp(log)
    while True:
        if stamp is None:
            raise gone
        try:
            events = tail.read_on(after)
        except FileNotFoundError:
            raise gone from None
        yield from events
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
