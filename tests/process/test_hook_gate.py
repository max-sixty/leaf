"""Hooks registered `--if-claimed`, which the launcher answers without uv
(`bin/leaf`): without starting Leaf in unclaimed sessions and for worker tool
batches, and on the environment's interpreter otherwise."""

import json
import os
import signal
import subprocess

from interact_support import ROOT, STATED_TIMEOUT

from leaf import service as service_model
from leaf import state as state_model

LAUNCHER = str(ROOT / "bin" / "leaf")
REGISTRATIONS = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"]


def hook(event: str, session: str) -> None:
    """Run Claude Code's first registered command for `event`, as it would."""
    ran = subprocess.run(
        ["/bin/sh", "-c", REGISTRATIONS[event][0]["hooks"][0]["command"]],
        input=json.dumps({"hook_event_name": event, "session_id": session}),
        env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(ROOT)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert ran.returncode == 0, ran.stderr


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
    turn_record = state_model.session_record(session)
    assert turn_record is not None
    assert turn_record["turn_closed"] is None
    claimed = subprocess.run(
        [LAUNCHER, "page", "claim", str(page_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert claimed.returncode == 0, claimed.stderr
    claim = service_model.page_claim(page_dir)
    assert claim is not None
    assert claim["id"] == session
    assert claim["turn_closed"] is None

    hook("Stop", session)
    turn_record_2 = state_model.session_record(session)
    assert turn_record_2 is not None
    assert turn_record_2["turn_closed"] is not None


def test_a_claimed_session_runs_its_gated_hooks_without_uv(claimed, tmp_path):
    """A hook registered `--if-claimed` in a session holding a page runs whole on
    the environment's interpreter, with no uv once uv has synced the environment
    to the lock, and a worker's tool batch, which receives nothing, stops before
    Leaf's imports."""
    uv = tmp_path / "uv"
    uv.write_text("#!/bin/sh\nexit 72\n")
    uv.chmod(0o755)

    def run(worker, *, harness="claude-code", event="PostToolBatch", path=None):
        """The hook's exit status and output, and whether it imported Leaf's hooks."""
        ran = subprocess.run(
            [LAUNCHER, "hook", "--harness", harness, "--if-claimed"],
            input=json.dumps(
                {
                    "hook_event_name": event,
                    "session_id": "s1",
                    **({"agent_id": "worker"} if worker else {}),
                }
            ),
            env={
                **os.environ,
                "PATH": path or str(tmp_path) + os.pathsep + os.environ["PATH"],
                "PYTHONPROFILEIMPORTTIME": "1",
            },
            capture_output=True,
            text=True,
            timeout=STATED_TIMEOUT,
            check=False,
        )
        imported = {
            line.rsplit("|", 1)[1].strip()
            for line in ran.stderr.splitlines()
            if line.startswith("import time:")
        }
        return ran.returncode, ran.stdout, "leaf.hooks" in imported

    # With the real uv, which syncs the environment if the lock moved since it
    # last did.
    assert run(False, path=os.environ["PATH"]) == (0, "", True)
    assert run(True) == (0, "", False)
    assert run(False) == (0, "", True)
    assert run(True, event="UserPromptSubmit") == (0, "", True)
    assert run(True, harness="codex") == (0, "", True)


def test_a_terminated_pages_follower_exits_with_its_signal(claimed, spawn):
    """Leaf's Claude Code hooks module ends the pages follower with SIGTERM while a
    session sits idle, and reads an exit of 128 plus the signal as that ending
    rather than a failure to show the user (`report` in `hooks/claude-code.ts`)."""
    follower = spawn(
        [LAUNCHER, "hook", "--harness", "claude-code", "--if-claimed", "--pages"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    # As the module asks, the follower is also the session's forks lane, so it
    # waits on the page's changes between reads.
    follower.stdin.write(
        json.dumps({"hook_event_name": "Pages", "session_id": "s1", "forks": True})
    )
    follower.stdin.close()
    # The claimed page has no server, so the follower lists nothing and goes on
    # following it.
    assert json.loads(follower.stdout.readline()) == []
    assert follower.poll() is None
    follower.send_signal(signal.SIGTERM)
    assert follower.wait(timeout=STATED_TIMEOUT) == 128 + signal.SIGTERM, (
        follower.stderr.read()
    )
