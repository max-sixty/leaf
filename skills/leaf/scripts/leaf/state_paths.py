"""State-home paths and the claim evidence a cold hook can read without uv.

This module uses only the standard library so the installed plugin's SessionEnd
hook can distinguish a genuinely untouched session from one whose page was
claimed through another Leaf checkout. It does not decide whether a claim is
active; the CLI remains the owner of that reading.
"""

import json
import os
from pathlib import Path


def state_home_path() -> Path:
    root = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    return Path(root) / "leaf"


def session_may_have_claim(session_id: str) -> bool:
    """Whether shared state contains a claim this session might own.

    Unreadable or older records are inconclusive, so let the CLI decide. A
    negative reading is safe only when every record names another session.
    """
    for path in (state_home_path() / "claims").glob("*.json"):
        try:
            record = json.loads(path.read_text())
        except (OSError, ValueError):
            return True
        if not isinstance(record, dict) or record.get("id") in (None, session_id):
            return True
    return False
