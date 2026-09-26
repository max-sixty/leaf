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
import time
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from .event_log import jsonl_line, require_cross_process_locking

try:
    import fcntl
except ImportError:  # pragma: no cover - unsupported non-POSIX platform
    fcntl = None


INTERACTIONS_FILE = "interactions.jsonl"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


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
        stream.write(data)
        stream.flush()


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


def lines(page_dir: Path, *, follow: bool = False) -> Iterator[str]:
    """Read complete JSON lines, optionally waiting for later appends."""
    path = page_dir / INTERACTIONS_FILE
    offset = 0
    identity = None
    while True:
        try:
            with path.open(encoding="utf-8") as stream:
                stat = os.fstat(stream.fileno())
                current = (stat.st_dev, stat.st_ino)
                if current != identity or stat.st_size < offset:
                    offset = 0
                identity = current
                stream.seek(offset)
                while line := stream.readline():
                    if not line.endswith("\n"):
                        break
                    offset = stream.tell()
                    yield line.rstrip("\n")
        except FileNotFoundError:
            pass
        if not follow:
            return
        time.sleep(0.2)
