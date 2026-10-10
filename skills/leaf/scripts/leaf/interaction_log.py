"""Diagnostic browser and HTTP activity for one page.

This append-only stream explains how a reader reached a decision. It is not
semantic state: page projections and acknowledgement never read it. A single
locked append keeps batches from concurrent server processes together, while
leaving event-log transactions and their durability rules untouched.

TODO(privacy): Define retention, export, and deletion before pages are shared
with other users. Client traces can contain draft text and entered values;
decide which fields to redact or omit for those users.
"""

import json
import os
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from .event_log import jsonl_line
from .schema import INTERACTIONS_FILE
from .state import now_iso, require_cross_process_locking

try:
    import fcntl
except ImportError:  # pragma: no cover - unsupported non-POSIX platform
    fcntl = None


def append_interactions(page_dir: Path, records: list[dict]) -> None:
    """Append a complete batch without interleaving other processes' lines.

    Diagnostics are best effort across a process crash; unlike admitted user
    decisions they do not claim disk durability in the HTTP response.
    """
    require_cross_process_locking()
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
    """Validate browser transport fields, then stamp server-owned provenance.

    Diagnostic types and payload fields remain open. Only fields the transport
    reader interprets have a required shape; ordinary observations may omit the
    browser clock and sequence and use the server receipt time instead.
    """
    for entry in entries:
        validate_client_entry(entry)
    received = now_iso()
    return [
        {
            **entry,
            "source": "client",
            "received": received,
            "session": session,
            "page": page,
        }
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
    """Validate the fields consumed by diagnostic reconstruction and formatting."""
    if not isinstance(entry, dict):
        raise TypeError("interaction entry must be an object")
    if not isinstance(entry.get("type"), str) or not entry["type"]:
        raise ValueError("interaction type must be a nonempty string")
    if "ts" in entry:
        interaction_time(entry["ts"])
    if "sequence" in entry and (
        type(entry["sequence"]) is not int or entry["sequence"] < 1
    ):
        raise ValueError("interaction sequence must be a positive integer")
    if "target" in entry and not (
        isinstance(entry["target"], str)
        or isinstance(entry["target"], list)
        and all(isinstance(item, str) for item in entry["target"])
    ):
        raise ValueError("interaction target must be a string or array of strings")
    if "nodes" in entry and not (
        isinstance(entry["nodes"], list)
        and all(type(item) is int and item > 0 for item in entry["nodes"])
    ):
        raise ValueError("interaction nodes must be an array of positive integers")
    if entry["type"] == "interaction_part":
        for name, minimum in (
            ("sequence", 1),
            ("partOf", 1),
            ("part", 0),
            ("parts", 1),
        ):
            if type(entry.get(name)) is not int or entry[name] < minimum:
                raise ValueError(
                    f"interaction part {name} must be an integer >= {minimum}"
                )
        if entry["parts"] > 512 or entry["part"] >= entry["parts"]:
            raise ValueError(
                "interaction part must be within a group of at most 512 parts"
            )
        if entry["sequence"] != entry["partOf"] + entry["part"]:
            raise ValueError("interaction part sequence must equal partOf + part")
        if not isinstance(entry.get("json"), str):
            raise ValueError("interaction part json must be a string")
        if not isinstance(entry.get("originalType"), str) or not entry["originalType"]:
            raise ValueError("interaction part originalType must be a nonempty string")


def _validate_stored(row: object) -> None:
    if not isinstance(row, dict):
        raise TypeError("interaction record must be an object")
    if row.get("source") == "client":
        for name in ("session", "page"):
            if not isinstance(row.get(name), str) or not row[name]:
                raise ValueError(f"interaction {name} must be a nonempty string")
        interaction_time(row.get("received"))
        validate_client_entry(row)
    elif row.get("source") == "server":
        interaction_time(row.get("ts"))
        if any(not isinstance(row.get(name), str) for name in ("method", "path")):
            raise ValueError("server interaction method and path must be strings")
        if type(row.get("status")) is not int or type(row.get("durationMs")) not in (
            int,
            float,
        ):
            raise ValueError("server interaction status and durationMs must be numeric")
    else:
        raise ValueError("interaction source must be client or server")


def _invalid(row: object, number: int, reason: str) -> dict:
    diagnostic = {
        "source": "reader",
        "type": "interaction_invalid",
        "line": number,
        "error": reason,
        "record": row,
    }
    if isinstance(row, dict):
        for name in ("session", "page"):
            if isinstance(row.get(name), str) and row[name]:
                diagnostic[name] = row[name]
        if type(row.get("sequence")) is int and row["sequence"] > 0:
            diagnostic["sequence"] = row["sequence"]
        for name in ("ts", "received"):
            try:
                interaction_time(row.get(name))
            except (TypeError, ValueError):
                continue
            diagnostic["ts"] = row[name]
            break
    return diagnostic


def _time(row: dict) -> datetime | None:
    # Admission permits observations without a browser clock or sequence.
    value = row.get("ts") or row.get("received")
    return interaction_time(value) if value is not None else None


def read_interactions(
    page_dir: Path,
    *,
    session: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    types: tuple[str, ...] = (),
) -> list[dict]:
    """Read chronological diagnostics, reconstructing the browser transport.

    Deduplication and gap detection precede filtering. Browser sequence starts at
    one and counts transport parts, so a reconstructed row consumes its entire
    part range. Missing parts and sequence gaps remain explicit reader records,
    including when a type filter selects only commands. No ending gap can be
    inferred: an unsent tail leaves no evidence. Server requests have no session
    association and therefore do not appear under a session filter.
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
    seen = {}
    line_numbers = {}
    sessions = defaultdict(list)
    for number, line in enumerate(lines, 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            records.append(_invalid(line.rstrip("\n"), number, error.msg))
            continue
        try:
            _validate_stored(row)
        except (TypeError, ValueError) as error:
            invalid = _invalid(row, number, str(error))
            if (
                isinstance(row, dict)
                and row.get("source") == "client"
                and "session" in invalid
                and "sequence" in invalid
            ):
                sessions[invalid["session"]].append(invalid)
            else:
                records.append(invalid)
            continue
        if row.get("source") == "client" and isinstance(row.get("sequence"), int):
            key = (row["session"], row["sequence"])
            if key in seen:
                # Retries receive a new server receipt time, not a new identity.
                if {k: v for k, v in row.items() if k != "received"} != {
                    k: v for k, v in seen[key].items() if k != "received"
                }:
                    records.append(
                        _invalid(row, number, f"conflicting duplicate {key}")
                    )
                continue
            seen[key] = row
            line_numbers[key] = number
            sessions[row["session"]].append(row)
        else:
            records.append(row)
    for rows in sessions.values():
        rows.sort(key=lambda row: row["sequence"])
        previous = 0
        parts = defaultdict(list)
        for row in rows:
            if row["sequence"] > previous + 1:
                records.append(
                    {
                        **{
                            key: row[key]
                            for key in ("ts", "received", "session", "page")
                            if key in row
                        },
                        "source": "reader",
                        "type": "interaction_gap",
                        "sequence": previous + 1,
                        "through": row["sequence"] - 1,
                    }
                )
            previous = row["sequence"]
            if row.get("type") == "interaction_part":
                parts[row["partOf"]].append(row)
            else:
                records.append(row)
        for group in parts.values():
            group.sort(key=lambda row: row["part"])
            first = group[0]
            missing = sorted(
                set(range(first["parts"])) - {row["part"] for row in group}
            )
            provenance = {
                key: first[key]
                for key in ("ts", "session", "page", "received")
                if key in first
            }
            if missing:
                records.append(
                    {
                        **provenance,
                        "source": "reader",
                        "type": "interaction_incomplete",
                        "sequence": first["partOf"],
                        "originalType": first["originalType"],
                        "missingParts": missing,
                        "parts": first["parts"],
                    }
                )
            else:
                try:
                    if any(
                        (row["parts"], row["originalType"])
                        != (first["parts"], first["originalType"])
                        for row in group
                    ):
                        raise ValueError("interaction parts disagree on group metadata")
                    restored = json.loads("".join(row["json"] for row in group))
                    validate_client_entry(restored)
                    if (
                        restored.get("sequence") != first["partOf"]
                        or restored["type"] != first["originalType"]
                    ):
                        raise ValueError(
                            "reconstructed interaction disagrees with its parts"
                        )
                except (TypeError, ValueError) as error:
                    records.append(
                        {
                            **_invalid(
                                group,
                                line_numbers[(first["session"], first["sequence"])],
                                str(error),
                            ),
                            **provenance,
                            "sequence": first["partOf"],
                        }
                    )
                else:
                    records.append({**restored, **provenance, "source": "client"})
    selected = [
        row
        for row in records
        if (
            session is None
            or row.get("session") == session
            or row["source"] == "reader"
            and "session" not in row
        )
        and (since is None or _time(row) is None or _time(row) >= since)
        and (until is None or _time(row) is None or _time(row) < until)
        and (not types or row.get("type") in types or row["source"] == "reader")
    ]
    return sorted(
        selected,
        key=lambda row: (
            _time(row) or datetime.max.replace(tzinfo=UTC),
            row.get("sequence", 0),
        ),
    )


def format_interaction(row: dict) -> str:
    """Render one line in the reader's local timezone; JSON retains full values."""
    observed = _time(row)
    time = (
        observed.astimezone().isoformat(timespec="milliseconds")
        if observed is not None
        else "unknown-time"
    )
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
        if key
        not in {"source", "ts", "received", "session", "page", "sequence", "type"}
    }
    # The composed path and node ids stay available in JSON. Human output names
    # the input owner and nearest identified ancestor rather than every wrapper.
    target = detail.pop("target", None)
    nodes = detail.pop("nodes", None)
    if isinstance(target, list) and target:
        owner = target[0]
        ancestor = next((item for item in target[1:] if "#" in item), None)
        detail["target"] = owner + (f" < {ancestor}" if ancestor else "")
        if nodes:
            detail["node"] = nodes[0]
    elif target is not None:
        detail["target"] = target
    fields = []
    for key, value in detail.items():
        rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        if len(rendered) > 200:
            rendered = rendered[:197] + "…"
        fields.append(f"{key}={rendered}")
    return f"{time} {context} {row.get('type', '?')}" + (
        " " + " ".join(fields) if fields else ""
    )
