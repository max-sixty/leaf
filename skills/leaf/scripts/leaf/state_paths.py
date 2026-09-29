"""State-home paths and session cleanup a cold hook can run without uv.

This module uses only the standard library so the installed plugin's SessionEnd
hook can release a page claimed through another Leaf checkout.
"""

import hashlib
import json
import os
from pathlib import Path


def state_home_path() -> Path:
    root = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    return Path(root) / "leaf"


# A session's files that end with it: the mark its hooks leave, and its page
# servers' log of the thread titles they asked for.
HOOKS_SUFFIX = "hooks"
TITLES_SUFFIX = "titles.log"


def session_file(session_id: str, suffix: str) -> Path:
    """One state-home file belonging to a single host session.

    A host's session id is not a filename, so the session is named by a digest of
    it. Every file one session owns — its leases, their start mark and locks, and a
    Codex task's deliveries and adapter log — is that one name with a different
    suffix, in the state home's `sessions/`.
    """
    key = hashlib.sha256(session_id.encode()).hexdigest()[:32]
    return state_home_path() / "sessions" / f"{key}.{suffix}"


def end_session(session_id: str) -> None:
    """Release this session's claims under each page's transaction lock, and
    remove the files that end with it.

    SessionEnd does not need the claim's lifetime reading: the host has ended
    the session, so any unreleased record still naming it may be closed. A
    successor is checked after taking the same log lock as claim transitions.
    """
    if not session_id:
        return
    for suffix in (HOOKS_SUFFIX, TITLES_SUFFIX):
        session_file(session_id, suffix).unlink(missing_ok=True)

    from .event_log import flocked, now_iso
    from .files import write_json
    from .locations import page_key
    from .schema import EVENTS_FILE

    for path in (state_home_path() / "claims").glob("*.json"):
        try:
            record = json.loads(path.read_text())
            if not isinstance(record, dict) or record.get("id") != session_id:
                continue
            page_name = record.get("page")
            if not isinstance(page_name, str) or "released" not in record:
                continue
            page = Path(page_name).resolve()
            if path.stem != page_key(page):
                continue
            with flocked(page / EVENTS_FILE):
                current = json.loads(path.read_text())
                if (
                    isinstance(current, dict)
                    and current.get("id") == session_id
                    and current.get("page") == page_name
                    and "released" in current
                    and current.get("released") is None
                ):
                    write_json(path, {**current, "released": now_iso()})
        except (OSError, ValueError, TypeError):
            continue
