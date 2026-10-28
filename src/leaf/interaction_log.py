"""Raw page diagnostics, with native session context captured at writing.

Application readers strip private session context before projecting or exposing
events. The developer response-time query interprets events through the current
application readers. Browser gestures, request timings and run context use
observations.jsonl.

Each `leaf` command records how long it took in every page it acted on, one
`leaf_command` observation as it exits (`record_command`), so a page says Leaf's own
share of an agent's reply on any harness. A command acts on the pages it names: an
initialized page as a `PAGE` argument (`cli.resolve_dir`; `page init`, which
creates or re-initializes one, records nothing), an answer reference's page
(`delivery.response_address`), or the pages a delivery it reads or acknowledges
carries (`delivery.acting_on_delivery`); each notes its page (`acting_on`). A
command that names none, as `leaf wait` watching every page a session owns,
records nothing: its time is the agent waiting, not Leaf answering. One that
names a page and then waits, as `leaf wait PAGE` does, records its own work as it
starts waiting. Harness hooks name no command pages; their time shows as delivery in the
page's pickup receipts. A harness's watch between turns records instead when it
started and how it ended (`record_watch`), so a pickup that waited with nothing
waking the session says whether a watch ran and could read the page. A command's time runs from its launcher's start, `bin/leaf`'s uv
included, to its exit; one the sandbox bridge runs for Claude Code is timed from
the bridge's start of it.

A browser batch is admitted whole by `interaction-batch.schema.json`, the schema
leaf.page's Worker admits it by too (`admit_batch`). The reader skips malformed lines,
deduplicates retries and reports sequence gaps before selection. Stored ts belongs
to the host clock; observed_at and monotonic_ms belong to one browser tab.

TODO(privacy): Define retention, export, and deletion before pages are shared
with other users. Client traces can contain draft text and entered values;
decide which fields to redact or omit for those users.
"""

import contextlib
import fcntl
import json
import os
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from .schema import INTERACTIONS_FILE
from .state import now_iso, session_record

BATCH_SCHEMA = json.loads(
    Path(__file__).with_name("interaction-batch.schema.json").read_text()
)


def append_interactions(page_dir: Path, records: list[dict]) -> list[dict]:
    """Append a complete batch without interleaving other processes' lines.

    Diagnostics are best effort across a process crash; unlike admitted user
    decisions they do not claim disk durability in the HTTP response.
    """
    from .event_log import jsonl_line

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


# The pages the running `leaf` command acts on, which its `leaf_command` record goes to.
_ACTED_ON: set[Path] = set()


def acting_on(page_dir: Path) -> None:
    """Note that this process's `leaf` command acts on `page_dir`."""
    _ACTED_ON.add(page_dir)


def launched() -> float:
    """When this `leaf` command started: its launcher's start where `bin/leaf`'s uv
    runs this process as `python -m leaf` with the same arguments, else this
    process's own."""
    import psutil

    process = psutil.Process()
    args = process.cmdline()[1:]
    parent = process.parent()
    words = parent.cmdline() if parent is not None else []
    if args[:2] == ["-m", "leaf"] and words[-len(args) :] == args:
        return parent.create_time()
    return process.create_time()


def record_command(command: str) -> None:
    """Record in each page this command acted on how long it has taken, with the
    harness session that ran it, once: a later call records nothing. A diagnostic
    the system won't let this process gather or write, as a sandbox may refuse a
    session record or a page, is dropped, since the command's own result has
    already been decided."""
    pages, ended = list(_ACTED_ON), time.time()
    _ACTED_ON.clear()
    if not pages:
        return
    import psutil

    from .harness import session_harness

    try:
        started = launched()
        harness = session_harness()
        session = harness.session if harness is not None else None
        record = {
            "source": "cli",
            "type": "leaf_command",
            "command": command,
            "started": datetime.fromtimestamp(started, UTC).isoformat(),
            "durationMs": round((ended - started) * 1000, 1),
            "session": session,
            "context": session_context(session),
        }
    except (OSError, psutil.Error):
        return
    for page_dir in pages:
        try:
            if (page_dir / "events.jsonl").is_file():
                append_interactions(page_dir, [record])
        except OSError:
            continue


def record_watch(pages: list[Path], session: str, began: float, ended: str) -> None:
    """Record in each page a harness's watch between turns read when it started,
    the protocol its Leaf speaks, and how it `ended`: `woke` the session,
    `superseded` by a later watch, `server-down`, `no-pages` left to watch,
    `harness-exited`, or `stopped` by a signal or an error. A watch that held a
    page it couldn't read shows its older protocol, and one killed outright leaves
    no record. Dropped where the page can't be written, as `record_command` is."""
    from .registry.kernel import kernel_protocol

    record = {
        "source": "cli",
        "type": "watch",
        "session": session,
        "started": datetime.fromtimestamp(began, UTC).isoformat(),
        "protocol": kernel_protocol(),
        "ended": ended,
    }
    for page_dir in pages:
        with contextlib.suppress(OSError):
            append_interactions(page_dir, [record])


def admit_batch(batch: object) -> dict:
    """The browser's batch, refused whole where it fails `BATCH_SCHEMA`, so the
    local server and leaf.page take the same batches."""
    # A harness hook records diagnostics through this module and loads no schema
    # engine (`test_hook_registration`), so only admission imports one.
    from .registry.schema import schema_error

    if error := schema_error(BATCH_SCHEMA, batch):
        raise ValueError(f"interaction batch: {error}")
    return batch


def client_records(session: str, page: str, entries: list[dict]) -> list[dict]:
    """An admitted batch's observations with their host-owned identity.

    The browser's wall clock stays `observed_at`; stored `ts` is host receipt
    time for every source. Duration calculations use the browser's monotonic
    clock within its session. Diagnostic payload fields remain open.
    """
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
