"""Append-only event log storage, raw readings, locking, and attempt identity."""

import json
import os
import secrets
import signal
import sys
from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path

from leaf.files import file_stamp, next_reading, read_json
from leaf.schema import CURSOR_FILE
from leaf.session_cleanup import EVENTS_FILE, flocked, now_iso


def read_cursor(page_dir: Path) -> int:
    """The seq the agent's carrier has confirmed through; 0 before any.

    A cursor is a position in this log, so one past its end belongs to a log that
    is gone — what `page init` on a directory whose log was moved or renamed away
    leaves behind. Nothing the log holds now was acknowledged through that
    position, so it reads as 0: the events in the replacement log are delivered,
    and the next `leaf wait --ack` writes a position this log can hold. Trusting the
    stored seq instead is silent and unbounded — every event the new log ever
    takes arrives at or below the cursor, so `leaf wait` never returns, the hooks
    report each comment as already answered, and `leaf wait --ack` writes nothing."""
    stored = (read_json(page_dir / CURSOR_FILE) or {"seq": 0})["seq"]
    events = read_events(page_dir)
    return 0 if stored > (events[-1]["seq"] if events else 0) else stored


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


class EventRefused(ValueError):
    """The append door turned one event down, with what to do about it.

    Raised by `event_contracts.append_admitted`, the one door every writer
    appends through. It lives beside the log rather than beside the gates so that
    a layer between a writer and the file — `contract_writer`, which answers a
    command's refusal — can name one without importing the contracts. `user` is
    what the browser shows the person whose gesture it was: the reason itself,
    unless the gate worded it for them (`Refusal`)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.user = getattr(reason, "user", reason)


class Refusal(str):
    """A gate's reason with separate words for the user whose gesture it refuses,
    where the reason names internals that user never sees."""

    user: str

    def __new__(cls, reason: str, user: str):
        refusal = super().__new__(cls, reason)
        refusal.user = user
        return refusal


class AttemptConflict(ValueError):
    """One browser attempt was reused for a different event payload."""


def _attempt_payload(event: dict) -> dict:
    # Kind is part of the gesture. Only fields the append boundary itself assigns
    # disappear from the equality check.
    return {
        key: value
        for key, value in event.items()
        if key not in {"id", "ts", "author", "seq", "meaning", "attention"}
    }


def _matching_attempt(events: list[dict], event: dict) -> dict | None:
    attempt = event.get("attempt")
    if not attempt:
        return None
    for existing in events:
        if existing.get("attempt") != attempt:
            continue
        if _attempt_payload(existing) != _attempt_payload(event):
            raise AttemptConflict(
                f"attempt {attempt!r} already belongs to another event"
            )
        return deepcopy(existing)
    return None


def _event_id_exists(events: list[dict], event_id: str) -> bool:
    """Whether this log already owns an event identity."""
    return any(existing.get("id") == event_id for existing in events)


def new_event_id(events: list[dict]) -> str:
    """An unused page-local identity, allocated under the append lease.

    Eight hex characters stay short enough to read and retype. Uniqueness comes
    from checking the held log, not their width; a host pairs the id with its page.
    Admission allocates it before semantic folding and storage keeps that identity.
    """
    while True:
        candidate = secrets.token_hex(4)
        if not _event_id_exists(events, candidate):
            return candidate


def _append_event_unlocked(f, event: dict, events: list[dict]) -> tuple[dict, bool]:
    """Append while the caller holds this log file's exclusive lease."""
    # Attempt identity is checked under the log's append lock. Checking before
    # this point would leave two server threads free to observe absence together
    # and append together. Content and time deliberately play no part: an
    # intentional later identical message has a fresh attempt and is a second
    # event.
    if event.get("attempt") and (existing := _matching_attempt(events, event)):
        return existing, False
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
    f.write((jsonl_line(event) + "\n").encode())
    # To the platter before the caller is told it landed: an event is a
    # decision, the sender's 200 (or a CLI exit 0) is the claim it is kept,
    # and events are rare enough that a flush per append costs nothing.
    f.flush()
    os.fsync(f.fileno())
    # The record as every reader reads it back: seq is its line number, which the
    # stored line does not carry.
    f.seek(0)
    return {**event, "seq": f.read().count(b"\n")}, True


def append_event(page_dir: Path, event: dict) -> dict:
    # This low-level fixture seam can start a log in an existing directory.
    log = page_dir / EVENTS_FILE
    with open(log, "a", encoding="utf-8"):
        pass
    with flocked(log) as f:
        f.seek(0)
        events = _parse_events(f.read())
        accepted, _appended = _append_event_unlocked(f, event, events)
        return accepted


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

    The trigger is the log's own stamp (`next_reading`), the look the browser's news
    stream makes over the whole page, narrowed to the one file a follower reads. A
    moved stamp reads only the bytes past what was already read, and only through the
    last newline: the line after it is an append mid-flush, whose rest moves the stamp
    again. Seq is the line number, so the lines read are counted whether or not they
    parse, exactly as `_parse_events` counts them; the lines at or before `after` are
    counted without being parsed.

    The offset read so far is a position in the file first opened, and appends
    only ever grow that file. A log that is another file now (a rename put a new
    one in its place) or shorter than what was read is not the log being
    followed, and reading on from the old offset would print its middle under the
    wrong seqs, so the follower ends there, as it does when the log is removed.
    """
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
        stamp = next_reading(lambda: file_stamp(log), stamp)


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
        sys.exit(str(error))
