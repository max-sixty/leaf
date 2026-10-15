"""Raw page diagnostics, with native session context captured at writing.

Application readers strip private session context before projecting or exposing
events. The developer response-time query interprets events through the current
application readers. Browser gestures, request timings and run context use
observations.jsonl.

Browser transport is validated at admission. The reader skips malformed lines,
deduplicates retries and reports sequence gaps before selection. Stored ts belongs
to the host clock; observed_at and monotonic_ms belong to one browser tab.

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
from .state import now_iso, session_record


def append_interactions(page_dir: Path, records: list[dict]) -> list[dict]:
    """Append a complete batch without interleaving other processes' lines.

    Diagnostics are best effort across a process crash; unlike admitted user
    decisions they do not claim disk durability in the HTTP response.
    """
    stamp = now_iso()
    records = [{"ts": stamp, **record} for record in records]
    data = "".join(jsonl_line(record) + "\n" for record in records).encode()
    descriptor = os.open(
        page_dir / INTERACTIONS_FILE, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600
    )
    with os.fdopen(descriptor, "wb") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        stream.write(data)
    return records


def client_records(session: str, page: str, entries: list[dict]) -> list[dict]:
    """Validate browser observations and attach their host-owned identity.

    The browser's wall clock stays `observed_at`; stored `ts` is host receipt
    time for every source. Duration calculations use the browser's monotonic
    clock within its session. Diagnostic payload fields remain open.
    """
    for entry in entries:
        validate_client_entry(entry)
    return [
        {
            **{key: value for key, value in entry.items() if key != "ts"},
            "source": "client",
            "session": session,
            "page": page,
        }
        for entry in entries
    ]


def session_context(session: str | None, claim: dict | None = None) -> dict | None:
    """Capture native session metadata as it stands at the write boundary."""
    if session is None:
        return None
    from .harness import session_harness

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
    lines = []
    for path in (page_dir / "events.jsonl", page_dir / INTERACTIONS_FILE):
        if not path.exists():
            continue
        for seq, line in enumerate(path.read_bytes().split(b"\n"), 1):
            try:
                row = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if path.name == "events.jsonl":
                context = row.pop("context", None)
                row = {
                    "source": "semantic",
                    "type": "event",
                    "context": context,
                    "ts": row["ts"],
                    "event": row,
                    "event_seq": seq,
                }
            lines.append(row)
    records = []
    seen = set()
    sessions = defaultdict(list)
    for row in lines:
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
