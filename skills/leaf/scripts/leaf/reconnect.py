"""Tell a session once when a page it served needs reconnecting.

When a session ends, its claim on a page stops being active, but Leaf keeps the
claim and leaves the page's service enabled. The resume `SessionStart` hook and each
prompt hook call `publishing_notices`, which reads those kept claims, older
generations included. For each page whose claim is no longer active or whose server
is not running, it tells the agent to run `leaf server start`, once per outage. It
skips a page the session released or stopped, a persistent service, a preview, and
a page another session has since claimed.

It takes the service and page locks and then the session lock, so a notice can't
race a transfer or a stop. The pages already reported are kept in a session file
outside the page log, which survives SessionEnd. A page leaves that file once its
claim is active and its server running, when the hook sees that or when a committed
start calls `recovered`. A hook whose session record has moved on reports nothing.
A harness drops the output of a hook that timed out, so a notice sent once may still
go unread.
"""

import shlex
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path

from .files import read_json
from .leases import page_locked
from .schema import PREVIEW_FILE
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


@contextmanager
def publishing_notices(
    harness: str | None, session_id: str, expected: dict | None
) -> Iterator[list[str] | None]:
    """Hold notice reservation and the decision to publish in one lifecycle reading.

    Callers prepare page input and freeze deliveries before entering, and publish
    what they took inside only if it yielded notices. Sorted service/page locks
    serialize stop, transfer, and recovery; the session lock is last. A stale
    lifecycle yields None without reserving anything. None for the harness skips
    reconnect inspection, while still holding the session lock for the lifecycle
    reading.
    """
    pages = (
        sorted(
            {
                Path(claim["page"])
                for claim in claim_records(session_id)
                if claim["harness"] == harness
            },
            key=str,
        )
        if harness
        else []
    )
    with ExitStack() as locks:
        retained = []
        for page_dir in pages:
            try:
                with ExitStack() as page_locks:
                    page_locks.enter_context(page_locked(page_dir))
                    page_locks.enter_context(PageTransaction(page_dir))
                    locks.enter_context(page_locks.pop_all())
                retained.append(page_dir)
            except FileNotFoundError:
                # Discovery can race page deletion; never recreate the page.
                continue
        locks.enter_context(flocked(session_lock_path(session_id)))
        if session_record(session_id) != expected:
            yield None
            return
        messages = []
        for page_dir in retained:
            claim = readable_claim(read_json(claim_path(page_dir)))
            if (
                claim is None
                or (claim["harness"], claim["id"]) != (harness, session_id)
                or (page_dir / PREVIEW_FILE).exists()
            ):
                continue
            from .server import read_service

            service = read_service(page_dir)
            if (
                service is None
                or "server_id" not in service
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
                    "Restore its server and the delivery of updates with:\n"
                    f"```sh\n{command}\n```"
                )
        yield messages
