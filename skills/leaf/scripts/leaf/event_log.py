"""Append-only event log storage, locking, and attempt identity."""

import contextlib
import json
import os
import secrets
import threading
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from leaf.files import read_json

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
    replaced inode holds nothing."""
    require_cross_process_locking()
    # comments.jsonl is the successful-init marker as well as a lease. A
    # transaction racing page deletion must not recreate it and turn a deleted
    # directory back into an initialized page. Purpose locks are disposable and
    # may be minted on first use.
    mode = "r+b" if path.name == "comments.jsonl" else "a+b"
    with open(path, mode) as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield f


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read_cursor(page_dir: Path) -> int:
    """The seq the agent has acknowledged through (`leaf ack`); 0 before any."""
    return (read_json(page_dir / "cursor.json") or {"seq": 0})["seq"]


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


class AttemptConflict(ValueError):
    """One browser attempt was reused for a different event payload."""


class AttemptExecution:
    """One execution shared by concurrent HTTP requests for the same attempt.

    Success is durable in the event log. The record coordinates requests while a
    handler is executing and is released once that handler finishes, so a concurrent
    retry receives the same outcome and a later one is free to be evaluated again.
    """

    def __init__(self, payload: dict):
        self.payload = payload
        self.done = threading.Event()
        self.result = None


def _attempt_payload(event: dict) -> dict:
    # Kind is part of the gesture. Only fields the append boundary itself assigns
    # disappear from the equality check.
    return {
        key: value
        for key, value in event.items()
        if key not in {"id", "ts", "author", "seq"}
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
        # Event ids escape the page with host requests as durable idempotency and
        # recovery keys. Keep them globally collision-resistant, and still prove
        # uniqueness against this log under the append lease rather than treating
        # probability as an invariant.
        while True:
            candidate = secrets.token_hex(16)
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
    log = page_dir / "comments.jsonl"
    with open(log, "a", encoding="utf-8"):
        pass
    with flocked(log) as f:
        f.seek(0)
        events = _parse_events(f.read())
        accepted, _appended = _append_event_unlocked(f, event, events)
        return accepted


def _parse_events(data: bytes) -> list[dict]:
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
        event["seq"] = i + 1
        events.append(event)
    return events


def read_events(page_dir: Path) -> list:
    path = page_dir / "comments.jsonl"
    if not path.exists():
        return []
    return _parse_events(path.read_bytes())
