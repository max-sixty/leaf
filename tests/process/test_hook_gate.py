"""The hooks the launcher answers without starting Leaf, in a session that holds no
claim (`state.hook_needed`)."""

import json
import os
import subprocess

from interact_support import ROOT
from leaf import service as service_model
from leaf import state as state_model

LAUNCHER = str(ROOT / "bin" / "leaf")


def hook(event: str, session: str, **env: str) -> None:
    ran = subprocess.run(
        [LAUNCHER, "hook", "--harness", "claude-code"],
        input=json.dumps({"hook_event_name": event, "session_id": session}),
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        check=False,
    )
    assert ran.returncode == 0, ran.stderr


def test_claude_code_runs_the_whole_hook_once_its_session_claims(page_dir):
    """Claude Code runs Leaf's prompt and Stop hooks in every session the plugin is
    installed in, and most never use Leaf, so the launcher skips them until the
    session claims. The hook before a `leaf` command opens the turn the skipped
    prompt hook would have, a claim joins it, and the session's Stop hook then
    runs in full and closes it."""
    session = os.environ["CLAUDE_CODE_SESSION_ID"]
    hook("UserPromptSubmit", session)
    hook("Stop", session)
    assert state_model.session_record(session) is None

    # No CLAUDE_PID, so this hook starts no bridge.
    hook("PreToolUse", session, CLAUDE_PID="")
    assert state_model.session_record(session)["turn_closed"] is None
    claimed = subprocess.run(
        [LAUNCHER, "page", "claim", str(page_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert claimed.returncode == 0, claimed.stderr
    claim = service_model.page_claim(page_dir)
    assert claim["id"] == session
    assert claim["turn_closed"] is None

    hook("Stop", session)
    assert state_model.session_record(session)["turn_closed"] is not None
