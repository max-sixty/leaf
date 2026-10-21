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

from .leases import page_locked
from .schema import PREVIEW_FILE
from .service import (
    PageTransaction,
    claim_is_active,
    claim_records,
    page_claim,
)
from .state import (
    RECONNECT_SUFFIX,
    Record,
    flocked,
    session_file,
    session_lock_path,
    session_record,
)

NOTICES = Record(
    "reconnect",
    {
        "description": "The pages a session has been told to reconnect, one notice "
        "each per outage, in the state home's `sessions/<digest>.reconnect`.",
        "type": "object",
        "properties": {
            "pages": {
                "description": "Each page directory the session was told about.",
                "type": "array",
                "items": {"type": "string"},
            }
        },
        "required": ["pages"],
    },
    since=13,
)


def _notice_path(session_id: str) -> Path:
    # The session's key names one harness's session, as its lifecycle's does.
    return session_file(session_id, RECONNECT_SUFFIX)


def _reported(session_id: str) -> set[str]:
    record = NOTICES.read(_notice_path(session_id))
    return set(record["pages"]) if record else set()


def _report(session_id: str, reported: set[str]) -> None:
    NOTICES.write(_notice_path(session_id), {"pages": sorted(reported)})


def _healthy(page_dir: Path, claim: dict) -> bool:
    from .server import running_server

    return claim_is_active(claim) and running_server(page_dir) is not None


def _forget(page_dir: Path, session_id: str) -> None:
    """Close a reported outage while holding its session lock."""
    reported = _reported(session_id)
    if str(page_dir) in reported:
        reported.remove(str(page_dir))
        _report(session_id, reported)


def recovered(page_dir: Path, claim: dict) -> None:
    """Rearm notices after a committed serve, under its service/page locks.

    The publisher calls this after releasing its claim-publication session lock.
    A healthy start rearms even if the server fails before the next harness hook.
    """
    with flocked(session_lock_path(claim["id"])):
        if not _healthy(page_dir, claim):
            return
        _forget(page_dir, claim["id"])


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
            claim = page_claim(page_dir)
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
                or not service["enabled"]
                or service["lifetime"] != "session"
            ):
                continue
            key = str(page_dir)
            if _healthy(page_dir, claim):
                _forget(page_dir, session_id)
            else:
                reported = _reported(session_id)
                if key in reported:
                    continue
                reported.add(key)
                _report(session_id, reported)
                command = shlex.join(["leaf", "server", "start", key])
                messages.append(
                    f"Your Leaf page needs reconnecting: {page_dir}. "
                    "Restore its server and the delivery of updates with:\n"
                    f"```sh\n{command}\n```"
                )
        yield messages
