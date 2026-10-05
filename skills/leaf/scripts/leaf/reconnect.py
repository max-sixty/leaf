"""One reconnect notice per outage of a session's previously served page.

A session ending invalidates ownership without deleting its last claim or disabling
its desired service. Resume and prompt hooks inspect those retained claims, including
older generations, before the normal carrier selects currently owned pages. Either
lost ownership or a dead serving incarnation needs reconnecting; the old server may
still answer during its orphan grace period.

Explicit releases, stops, standing services, previews, and successor claims are not
outages this session should repair. Inspection holds the service and page locks, then
the session lock, so a notice cannot race a transfer or explicit stop. Notification
state lives outside the page log, persists across SessionEnd, and resets only after
matching active ownership and the exact serving lease prove recovery. Reserving it
before emitting guarantees at-most-once output, not receipt of timed-out hook context.
"""

import shlex
from pathlib import Path

from .files import read_json
from .leases import page_locked
from .schema import PREVIEW_FILE, SERVICE_FILE
from .service import (
    PageTransaction,
    claim_is_active,
    claim_path,
    claim_records,
    readable_claim,
)
from .state import flocked, session_file, session_lock_path, session_record, write_json


def _notice_path(harness: str, session_id: str) -> Path:
    return session_file(session_id, f"{harness}.reconnect")


def _reported(harness: str, session_id: str) -> set[str]:
    record = read_json(_notice_path(harness, session_id))
    if not isinstance(record, list) or not all(
        isinstance(page, str) for page in record
    ):
        return set()
    return set(record)


def _healthy(page_dir: Path, claim: dict) -> bool:
    from .server import running_server

    return claim_is_active(claim) and running_server(page_dir) is not None


def _forget(page_dir: Path, harness: str, session_id: str) -> None:
    """Close a reported outage while holding its session lock."""
    reported = _reported(harness, session_id)
    if str(page_dir) in reported:
        reported.remove(str(page_dir))
        write_json(_notice_path(harness, session_id), sorted(reported))


def recovered(page_dir: Path, claim: dict) -> None:
    """Rearm notices after a committed serve, under its service/page locks.

    The publisher calls this after releasing its claim-publication session lock.
    A healthy start rearms even if the server fails before the next harness hook.
    """
    harness, sid = claim["harness"], claim["id"]
    with flocked(session_lock_path(sid)):
        if not _healthy(page_dir, claim):
            return
        _forget(page_dir, harness, sid)


def notices(harness: str, session_id: str, expected: dict | None) -> list[str]:
    """Reserve notices for this hook's lifecycle, without reclaiming any page."""
    messages = []
    for previous in claim_records(session_id):
        if previous["harness"] != harness:
            continue
        page_dir = Path(previous["page"])
        try:
            with (
                page_locked(page_dir),
                PageTransaction(page_dir),
                flocked(session_lock_path(session_id)),
            ):
                if session_record(session_id) != expected:
                    return []
                raw = read_json(claim_path(page_dir))
                claim = readable_claim(raw)
                if (
                    claim is None
                    or (claim["harness"], claim["id"]) != (harness, session_id)
                    or raw["released"] is not None
                    or (page_dir / PREVIEW_FILE).exists()
                ):
                    continue
                service = read_json(page_dir / SERVICE_FILE)
                if (
                    not isinstance(service, dict)
                    or not {"enabled", "lifetime", "host", "port", "server_id"}
                    <= service.keys()
                    or not service["enabled"]
                    or service["lifetime"] != "session"
                ):
                    continue
                key = str(page_dir)
                if _healthy(page_dir, claim):
                    _forget(page_dir, harness, session_id)
                else:
                    reported = _reported(harness, session_id)
                    if key in reported:
                        continue
                    reported.add(key)
                    write_json(_notice_path(harness, session_id), sorted(reported))
                    command = shlex.join(["leaf", "server", "start", key])
                    messages.append(
                        f"Your Leaf page needs reconnecting: {page_dir}. "
                        "Restore its server and feedback delivery with:\n"
                        f"```sh\n{command}\n```"
                    )
        except FileNotFoundError:
            # Discovery can race page deletion; it must not recreate the page.
            continue
    return messages
