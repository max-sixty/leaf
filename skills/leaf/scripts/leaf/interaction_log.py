"""Diagnostic browser and HTTP activity for one page.

This append-only stream explains how a reader reached a decision. It is not
semantic state: page projections and acknowledgement never read it. A single
locked append keeps batches from concurrent server processes together, while
leaving event-log transactions and their durability rules untouched.

The browser transport is validated once at admission. Each bounded observation
has one sequence; oversized payloads are explicitly omitted by the producer.
The reader trusts admitted rows, skips torn append lines, deduplicates retries
and reports sequence gaps. Stored `ts` always belongs to the host clock; the
browser wall clock is `observed_at`, and its duration clock is `monotonic_ms`.

TODO(privacy): Define retention, export, and deletion before pages are shared
with other users. Client traces can contain draft text and entered values;
decide which fields to redact or omit for those users.
"""

import fcntl
import json
import math
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .event_log import jsonl_line
from .schema import INTERACTIONS_FILE
from .state import now_iso


def append_interactions(page_dir: Path, records: list[dict]) -> None:
    """Append a complete batch without interleaving other processes' lines.

    Diagnostics are best effort across a process crash; unlike admitted user
    decisions they do not claim disk durability in the HTTP response.
    """
    data = "".join(jsonl_line(record) + "\n" for record in records).encode()
    fd = os.open(
        page_dir / INTERACTIONS_FILE, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600
    )
    with os.fdopen(fd, "wb") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            stream.write(data)
            stream.flush()
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def client_records(session: str, page: str, entries: list[dict]) -> list[dict]:
    """Validate browser observations and add one canonical host timestamp.

    The browser's wall clock stays `observed_at`; stored `ts` is host receipt
    time for every source. Duration calculations use the browser's monotonic
    clock within its session. Diagnostic payload fields remain open.
    """
    for entry in entries:
        validate_client_entry(entry)
    stamp = now_iso()
    return [
        {**entry, "source": "client", "ts": stamp, "session": session, "page": page}
        for entry in entries
    ]


def interaction_time(value: str) -> datetime:
    """Read an ISO timestamp with an explicit offset, including browser UTC Z."""
    if not isinstance(value, str):
        raise TypeError("interaction time must be an ISO timestamp string")
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("interaction times require a timezone offset")
    return result


def validate_client_entry(entry: object) -> None:
    """Validate the common browser transport fields once, at admission."""
    if not isinstance(entry, dict):
        raise TypeError("interaction entry must be an object")
    if not isinstance(entry.get("type"), str) or not entry["type"]:
        raise ValueError("interaction type must be a nonempty string")
    interaction_time(entry.get("observed_at"))
    if type(entry.get("sequence")) is not int or entry["sequence"] < 1:
        raise ValueError("interaction sequence must be a positive integer")
    clock = entry.get("monotonic_ms")
    if type(clock) not in (int, float) or not math.isfinite(clock) or clock < 0:
        raise ValueError("interaction monotonic_ms must be finite and nonnegative")
    if entry.get("visibility") not in ("visible", "hidden"):
        raise ValueError("interaction visibility must be visible or hidden")


def read_interactions(
    page_dir: Path,
    *,
    session: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    types: tuple[str, ...] = (),
) -> list[dict]:
    """Read host-ordered diagnostics, preserving retry identity and loss evidence.

    The end cutoff defines observed history; deduplication and gap detection
    precede start, session and type filtering. Each browser sequence
    names one observation. Missing sequences are visible even under a type
    filter; an unsent tail leaves no evidence. Server/developer records have
    no browser session association.
    """
    path = page_dir / INTERACTIONS_FILE
    if not path.exists():
        return []
    with path.open() as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_SH)
        try:
            lines = stream.readlines()
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    records = []
    seen = set()
    sessions = defaultdict(list)
    for line in lines:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            # An interrupted append can leave a torn line.
            continue
        stamp = interaction_time(row["ts"])
        if until is not None and stamp >= until:
            continue
        if row["source"] == "client":
            key = (row["session"], row["sequence"])
            if key in seen:
                continue
            seen.add(key)
            sessions[row["session"]].append(row)
        records.append((stamp, row))
    for rows in sessions.values():
        previous = 0
        for row in sorted(rows, key=lambda row: row["sequence"]):
            if row["sequence"] > previous + 1:
                records.append(
                    (
                        interaction_time(row["ts"]),
                        {
                            "source": "reader",
                            "type": "interaction_gap",
                            "ts": row["ts"],
                            "session": row["session"],
                            "page": row["page"],
                            "sequence": previous + 1,
                            "through": row["sequence"] - 1,
                        },
                    )
                )
            previous = row["sequence"]
    dated = sorted(
        (stamp, row.get("sequence", 0), index, row)
        for index, (stamp, row) in enumerate(records)
    )
    return [
        row
        for stamp, _, _, row in dated
        if (session is None or row.get("session") == session)
        and (since is None or stamp >= since)
        and (not types or row["type"] in types or row["source"] == "reader")
    ]


def format_interaction(row: dict) -> str:
    """Render one line in the reader's local timezone; JSON retains full values."""
    time = interaction_time(row["ts"]).astimezone().isoformat(timespec="milliseconds")
    if row["source"] == "server":
        return (
            f"{time} server {row['method']} {row['path']} "
            f"→ {row['status']} ({row['durationMs']} ms)"
        )
    context = (
        f"{row.get('session', '?')} {row.get('page', '/')} #{row.get('sequence', '?')}"
    )
    detail = {
        key: value
        for key, value in row.items()
        if key not in {"source", "ts", "session", "page", "sequence", "type"}
    }
    fields = []
    for key, value in detail.items():
        rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        if len(rendered) > 200:
            rendered = rendered[:197] + "…"
        fields.append(f"{key}={rendered}")
    return f"{time} {context} {row.get('type', '?')}" + (
        " " + " ".join(fields) if fields else ""
    )
