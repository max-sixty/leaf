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
from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path

from leaf.files import file_stamp
from leaf.findings import Finding, Rejected
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


def _matching_attempt(events: list[dict], event: dict) -> dict | None:
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


def _event_id_exists(events: list[dict], event_id: str) -> bool:
    """Whether this log already owns an event identity."""
    return any(existing.get("id") == event_id for existing in events)


def new_event_id(events: list[dict]) -> str:
    """An unused page-local identity, allocated under the append lease.

    Eight hex characters stay short enough to read and retype. Uniqueness comes
    from checking the held log, not their width; a harness pairs the id with its page.
    Admission allocates it before semantic folding and storage keeps that identity.
    """
    while True:
        candidate = secrets.token_hex(4)
        if not _event_id_exists(events, candidate):
            return candidate


def _append_event_unlocked(
    f, event: dict, events: list[dict], *, context: dict | None = None
) -> dict:
    """Append while the caller holds this log file's exclusive lease.

    Attempt identity is the append door's (`event_contracts.append_admitted`): it
    reads the log under this same lease before its gates, so two server threads
    cannot both observe an attempt's absence and append it twice."""
    if "id" in event:
        if _event_id_exists(events, event["id"]):
            raise ValueError(f"event id {event['id']!r} already exists")
    else:
        event["id"] = new_event_id(events)
    event.setdefault("ts", now_iso())
    # A crash can tear the previous append mid-line: SIGKILL under a buffered
    # flush, a full disk. The line discipline is the writer's, so the writer
    # restores it — without this, the next event glues onto the torn fragment
    # and one lost event becomes an unreadable line mid-file.
    f.seek(0, os.SEEK_END)
    if f.tell():
        f.seek(-1, os.SEEK_END)
        if f.read(1) != b"\n":
            f.write(b"\n")
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
        f.seek(0)
        events = _parse_events(f.read())
        return _append_event_unlocked(
            f, event, events, context=session_context(event.get("session"))
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
            # The final line is a concurrent append mid-flush, complete on the
            # next read. An earlier one is the tear a crash left, standing alone
            # because append_event repairs the discipline before writing: that
            # event's sender already saw its send fail, the seqs around it hold,
            # and there is nothing anyone could do with a fragment — so it is
            # skipped, not raised over, and the page keeps reading.
            continue
        event.pop("context", None)
        event["seq"] = before + i + 1
        events.append(event)
    return events


def read_events(page_dir: Path) -> list:
    path = page_dir / EVENTS_FILE
    if not path.exists():
        return []
    return _parse_events(path.read_bytes())


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
