"""The hooks the launcher answers without starting Leaf: those registered
`--if-claimed` in a session that holds no claim, and a tool boundary that would
read what the last quiet one read (`bin/leaf`)."""

import json
import os
import subprocess

from interact_support import ROOT, append_carried_log_record

from leaf import service as service_model
from leaf import state as state_model

LAUNCHER = str(ROOT / "bin" / "leaf")
REGISTRATIONS = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"]


def hook(event: str, session: str, env: dict | None = None) -> str:
    """Run Claude Code's first registered command for `event`, as it would, and
    return what it printed."""
    ran = subprocess.run(
        ["/bin/sh", "-c", REGISTRATIONS[event][0]["hooks"][0]["command"]],
        input=json.dumps({"hook_event_name": event, "session_id": session}),
        env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(ROOT), **(env or {})},
        capture_output=True,
        text=True,
        check=False,
    )
    assert ran.returncode == 0, ran.stderr
    return ran.stdout


def test_a_quiet_boundary_is_answered_without_leaf(claimed, tmp_path):
    """A session holding a page runs PostToolBatch after every batch of tool calls.
    One that finds what the last quiet boundary found never starts Leaf, which a
    stand-in package on the module path would witness, and new input brings Leaf
    back to hand it over."""
    standin = tmp_path / "standin" / "leaf"
    standin.mkdir(parents=True)
    (standin / "__init__.py").touch()
    started = tmp_path / "started"
    (standin / "__main__.py").write_text(
        f"from pathlib import Path\nPath({str(started)!r}).touch()\n"
    )
    witnessed = {"PYTHONPATH": str(standin.parent)}

    assert hook("PostToolBatch", "s1") == ""
    assert hook("PostToolBatch", "s1", witnessed) == ""
    assert not started.exists()

    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "one more"}
    )
    handed = json.loads(hook("PostToolBatch", "s1"))["hookSpecificOutput"]
    assert "one more" in handed["additionalContext"]
    # Its handover is the next boundary's to confirm, so that one runs Leaf too.
    assert hook("PostToolBatch", "s1", witnessed) == ""
    assert started.exists()


def test_claude_code_runs_the_whole_hook_once_its_session_claims(page_dir):
    """Claude Code runs Leaf's turn and tool hooks in every session the plugin is
    installed in, and most never use Leaf, so the launcher skips them until the
    session claims. The hook before a `leaf` command opens the turn the skipped
    prompt hook would have, a claim joins it, and the session's Stop hook then
    runs in full and closes it."""
    session = os.environ["CLAUDE_CODE_SESSION_ID"]
    hook("UserPromptSubmit", session)
    hook("PostToolBatch", session)
    hook("Stop", session)
    assert state_model.session_record(session) is None

    hook("PreToolUse", session)
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
