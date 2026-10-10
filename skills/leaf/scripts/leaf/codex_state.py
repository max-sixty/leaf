"""Codex delivery eligibility and paths for its serialized transport reservations.

The session lifecycle owner records provider identity, lifetime and revision.
This module derives an observation from that authority, and proves eligibility
with the page's dated activity rather than maintaining another running flag.
A pointer acknowledgement proves entry through its exact hook reservation and lifecycle revision.
Codex can resume without a user prompt. Its native transcript supplies ordered
turn starts and endings that both the queue adapter and hooks publish through the
same lifecycle owner. Transcript readings are disposable process memory; the
session record keeps only the hook-provided path needed to observe that source.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from threading import RLock

from .leases import session_state_path
from .state import (
    advance_turn,
    flocked,
    session_lock_path,
    session_record,
    write_session,
)


def transcript_event(line: bytes) -> tuple[str, str, str] | None:
    """Validate native lifecycle records at the transcript boundary."""
    record = json.loads(line)
    if not isinstance(record, dict):
        raise TypeError("Codex transcript record must be an object")
    if record["type"] != "event_msg":
        return None
    payload = record["payload"]
    if not isinstance(payload, dict):
        raise TypeError("Codex transcript event must be an object")
    event = payload["type"]
    if event not in {"task_started", "task_complete", "turn_aborted"}:
        return None
    turn, timestamp = payload["turn_id"], record["timestamp"]
    if not isinstance(turn, str) or not turn:
        raise ValueError("Codex transcript turn id must be a string")
    if not isinstance(timestamp, str):
        raise TypeError("Codex transcript timestamp must be a string")
    if datetime.fromisoformat(timestamp).tzinfo is None:
        raise ValueError("Codex transcript timestamp needs a time zone")
    return event, turn, timestamp


def reverse_transcript_lines(stream, length: int):
    """Yield complete lines backwards, retaining at most one line and a block.

    The first split fragment is the unfinished tail, or the empty fragment after
    a final newline. Neither is a record. Offsets identify the complete prefix
    that an incremental reader can resume after this cold observation.
    """
    position, fragments, tail = length, [], True
    while position:
        size = min(position, 64 * 1024)
        position -= size
        stream.seek(position)
        block = stream.read(size)
        cursor = len(block)
        while (separator := block.rfind(b"\n", 0, cursor)) != -1:
            if tail:
                tail = False
            else:
                fragments.append(block[separator + 1 : cursor])
                line = b"".join(reversed(fragments))
                fragments.clear()
                yield position + separator + 1, line
                del line
            cursor = separator
        if not tail:
            fragments.append(block[:cursor])
    if not tail:
        yield 0, b"".join(reversed(fragments))


@dataclass
class TranscriptTurns:
    """Read the tail cold, then only appended native Codex transcript records."""

    identity: tuple[int, int] | None = None
    offset: int = 0
    length: int = 0
    modified: int = 0
    session: str | None = None
    started: set[str] = field(default_factory=set)
    turn: str | None = None
    opened: str | None = None
    closed: str | None = None
    searched: str | None = None
    lock: RLock = field(default_factory=RLock, repr=False)

    def read(self, path: Path, current_provider: str | None = None) -> bool:
        """Consume complete appended records, leaving an in-flight tail unread."""
        with self.lock:
            return self._read(path, current_provider)

    def _cold(self, stream, length: int, current_provider: str | None) -> bool:
        stream.seek(0)
        first = stream.readline()
        if not first.endswith(b"\n"):
            return False
        metadata = json.loads(first)
        if not isinstance(metadata, dict) or metadata["type"] != "session_meta":
            raise ValueError("Codex transcript must begin with session_meta")
        session = metadata["payload"]["id"]
        if not isinstance(session, str) or not session:
            raise ValueError("Codex transcript session id must be a string")
        self.session = session
        self.started.clear()
        self.turn = self.opened = self.closed = None
        self.searched = current_provider
        endings = {}
        for start, line in reverse_transcript_lines(stream, length):
            if not self.offset:
                self.offset = start + len(line) + 1
            if (event := transcript_event(line)) is None:
                continue
            kind, turn, timestamp = event
            if self.turn is None:
                if kind != "task_started":
                    endings.setdefault(turn, timestamp)
                    continue
                self.turn, self.opened = turn, timestamp
                self.closed = endings.get(turn)
                self.started.add(turn)
                if current_provider is None or current_provider == turn:
                    break
            elif kind == "task_started" and turn == current_provider:
                self.started.add(turn)
                break
        return True

    def _read(self, path: Path, current_provider: str | None) -> bool:
        try:
            stream = path.open("rb")
        except FileNotFoundError:
            return False
        with stream:
            stat = os.fstat(stream.fileno())
            identity = stat.st_dev, stat.st_ino
            if (
                self.identity != identity
                or stat.st_size < self.length
                or (stat.st_size == self.length and stat.st_mtime_ns != self.modified)
            ):
                self.identity, self.offset = identity, 0
                self.session = None
            if self.session is None or (
                current_provider is not None
                and current_provider not in self.started
                and self.searched != current_provider
            ):
                self.offset = 0
                if not self._cold(stream, stat.st_size, current_provider):
                    return False
            stream.seek(self.offset)
            while line := stream.readline():
                if not line.endswith(b"\n"):
                    break
                if event := transcript_event(line):
                    kind, turn, timestamp = event
                    if kind == "task_started":
                        self.started.add(turn)
                        self.turn, self.opened, self.closed = turn, timestamp, None
                    elif turn == self.turn:
                        self.closed = timestamp
                self.offset = stream.tell()
            self.length, self.modified = stat.st_size, stat.st_mtime_ns
        return self.session is not None


@lru_cache(maxsize=8)
def transcript_turns(path: Path) -> TranscriptTurns:
    """Keep native source cursors only for this process's recent transcripts."""
    return TranscriptTurns()


def sync_transcript_turn(
    session_id: str, transcript_path: str | Path | None = None
) -> dict | None:
    """Publish the native transcript's latest turn under the captured lifecycle.

    A prompt may name a turn before its source record is available. A different
    provider turn is adopted only when the source also holds the current one,
    proving their order; source lag cannot replace a newer prompt. Endings apply
    only to the source's latest turn, and a closed provider identity stays closed.
    Missing files and partial tails defer observation to the next pass. There is
    no transcript discovery or second durable lifecycle beside the session record.
    """
    expected = session_record(session_id)
    if expected is None or expected["ended"] is not None:
        return expected
    source = transcript_path or expected.get("transcript_path")
    if source is None:
        return expected
    if not isinstance(source, (str, Path)):
        raise TypeError("Codex transcript path must be a string")
    path = Path(source).absolute()
    reading = transcript_turns(path)
    with reading.lock:
        if (
            not reading.read(
                path,
                current_provider=expected["turn"] if expected["provider"] else None,
            )
            or reading.session != session_id
        ):
            return expected
        turn, opened, closed = reading.turn, reading.opened, reading.closed
        ordered = expected["turn"] in reading.started
    with flocked(session_lock_path(session_id)):
        current = session_record(session_id)
        if current != expected:
            return current
        if current.get("transcript_path") != str(path):
            current = write_session({**current, "transcript_path": str(path)})
        if turn is None:
            return current
        if turn != current["turn"]:
            if current["provider"] and not ordered:
                return current
            current = advance_turn(session_id, turn, running=True, observed_at=opened)
        if closed is not None and current["turn_closed"] is None:
            current = advance_turn(session_id, turn, running=False, observed_at=closed)
        return current


def delivery_dir(session_id: str) -> Path:
    return session_state_path(session_id, "deliveries")


def delivery_lock_path(session_id: str) -> Path:
    return session_lock_path(session_id)


def hook_turn(session_id: str) -> dict | None:
    """The canonical session observation for transport reservation revision checks.

    Running is derived from the dated session lifecycle, never stored by a
    second Codex writer. Page activity still proves current delivery eligibility.
    """
    record = session_record(session_id)
    if record is None:
        return None
    return {
        **record,
        "running": bool(
            record["ended"] is None
            and record["turn"] is not None
            and record["turn_closed"] is None
        ),
    }


def delivery_turn(session_id: str) -> str | None:
    """The observed provider turn eligible for hook delivery.

    Use the same dated activity reading as the page, so an interrupted or stale
    turn never holds the idle queue indefinitely. Claims derive the current
    provider turn from the session lifecycle; delivery hooks renew it and offer
    feedback. Read outside the delivery lock: capture takes a page transaction
    before that lock.
    """
    observed = hook_turn(session_id)
    if not observed or not observed["running"]:
        return None
    from .presence import claimant_reading
    from .service import PageTransaction, owned_pages

    for page_dir in owned_pages(session_id):
        try:
            with PageTransaction(page_dir) as page:
                present, turn = claimant_reading(page_dir, page.events)
                if present["claim_session"] == session_id and turn.running:
                    return observed["turn"]
        except FileNotFoundError:
            continue
    return None


def confirm_codex_pointer(session_id: str, payload: dict) -> list[Path]:
    """Confirm the owning task's complete pointer receipt in its exact turn.

    A hook reservation remains bound to its offered turn. Already queued input
    and recovery reminders have no such reservation; their explicit reader
    confirmation records the current receiver's turn under the page lock.
    """
    from .codex import Accepted, accept_codex_delivery, read_task_delivery
    from .delivery import ReceiptRefused, receive

    observation = hook_turn(session_id)
    if not observation or not observation["running"]:
        raise ReceiptRefused("the receiving provider turn has ended")
    record = read_task_delivery(session_id, payload["id"])
    if record is None or isinstance(record, Accepted):
        return receive(payload, session_id)
    received = accept_codex_delivery(
        session_id, payload["id"], observation["turn"], hook_observation=observation
    )
    if len(received) != len(payload["batches"]):
        raise ReceiptRefused("delivery no longer owns its page or receiving turn")
    return [batch["page"] for batch in received]
