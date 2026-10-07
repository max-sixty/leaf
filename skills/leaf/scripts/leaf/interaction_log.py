"""Diagnostic browser and HTTP activity for one page.

This append-only stream explains how a reader reached a decision. It is not
semantic state: page projections and acknowledgement never read it. A single
locked append keeps batches from concurrent server processes together, while
leaving event-log transactions and their durability rules untouched.

TODO(privacy): Define retention, export, and deletion before pages are shared
with other users. Client traces can contain draft text and entered values;
decide which fields to redact or omit for those users.
"""

import os
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
    """Stamp untrusted browser observations with server-owned provenance."""
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
