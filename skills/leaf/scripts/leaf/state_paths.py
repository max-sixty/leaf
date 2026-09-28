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


def end_session(session_id: str) -> None:
    """Release this session's claims under each page's transaction lock.

    SessionEnd does not need the claim's lifetime reading: the host has ended
    the session, so any unreleased record still naming it may be closed. A
    successor is checked after taking the same log lock as claim transitions.
    """
    if not session_id:
        return
    key = hashlib.sha256(session_id.encode()).hexdigest()[:32]
    (state_home_path() / "sessions" / f"{key}.hooks").unlink(missing_ok=True)

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
