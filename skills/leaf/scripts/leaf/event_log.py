"""Append-only event log storage, locking, and attempt identity."""

import contextlib
import json
import os
import secrets
from collections.abc import Iterator
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from leaf.files import file_stamp, next_reading, read_json
from leaf.schema import CURSOR_FILE, EVENTS_FILE

try:
    import fcntl
except ImportError:  # pragma: no cover - unsupported non-POSIX platform
    fcntl = None


def require_cross_process_locking() -> None:
    """Refuse every writer/server path on a host without the log's lock."""
    if fcntl is None:
        raise RuntimeError(
            "leaf requires POSIX cross-process file locking; this platform has no fcntl"
        )


@contextlib.contextmanager
def flocked(path: Path):
    """An exclusive lock held while the block runs — the one serialization
    primitive here. The log serializes appends, cursor and status updates, and
    claim and delivery transitions. Stable purpose locks serialize contract or service
    transitions; a `.lock` beside a registry of JSON files serializes updates
    to them, since the files themselves are replaced by rename and a lock on a
    replaced inode holds nothing.

    The event log is the successful-init marker as well as a lease. A transaction
    racing page deletion must not recreate it and turn a deleted directory back into
    an initialized page, so it is opened, never created, and it outlives the lock.

    A purpose lock's file is the lock and nothing more, so it exists only while it
    is held or awaited: it is minted on first use and its holder removes it on the
    way out. A taker that waited on a file removed under it holds a lock on nothing
    anyone else can find, so it takes the lock again on whatever the path names
    now (`still_named`)."""
    require_cross_process_locking()
    if path.name == EVENTS_FILE:
        with open(path, "r+b") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            yield f
        return
    while True:
        f = open(path, "a+b")  # noqa: SIM115 - closed below, after the unlink
        fcntl.flock(f, fcntl.LOCK_EX)
        if still_named(f.fileno(), path):
            break
        f.close()
    try:
        yield f
    finally:
        path.unlink(missing_ok=True)
        f.close()


def still_named(held: int, path: Path) -> bool:
    """Whether PATH still names the file the descriptor HELD was opened on.

    A lock file is removed by whoever holds it, so a lock taken on a descriptor
    opened before that removal is a lock on an unlinked inode. Every taker asks this
    once it holds the lock and takes it again when the answer is no; the holder's
    removal can then never let two processes each believe they hold one name."""
    try:
        return os.path.samestat(os.fstat(held), os.stat(path))
    except FileNotFoundError:
        return False


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read_cursor(page_dir: Path) -> int:
    """The seq the agent has acknowledged through (`leaf wait --ack`); 0 before any.

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
    events either way; the escape is for what `wait` and `events` print, which
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
        if key not in {"id", "ts", "author", "seq", "meaning"}
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
        accepted = deepcopy(existing)
        accepted.pop("seq", None)
        return accepted
    return None


def _event_id_exists(events: list[dict], event_id: str) -> bool:
    """Whether this log already owns an event identity."""
    return any(existing.get("id") == event_id for existing in events)


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
        # An id is unique within this page and nowhere else. Eight hex
        # characters, re-rolled while this log already holds the candidate,
        # under the lease that serializes appends — so uniqueness is proven by
        # the write rather than assumed from width, and the id stays short
        # enough for an agent to read off a projection and retype into `leaf
        # thread reply --for`. Nothing may treat one as a global identifier: a host
        # keying an external operation on a `request` pairs the id with the page
        # (`references/packages.md`).
        while True:
            candidate = secrets.token_hex(4)
            if not _event_id_exists(events, candidate):
                event["id"] = candidate
                break
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
    return event, True


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
