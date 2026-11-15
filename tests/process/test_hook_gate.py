"""Hooks registered `--if-claimed` (`bin/leaf`): those the launcher answers
without starting Leaf, in unclaimed sessions and for worker tool batches, and
the pages follower, which ends with the signal that stopped it."""

import hashlib
import json
import os
import signal
import subprocess

from interact_support import ROOT, STATED_TIMEOUT

from leaf import service as service_model
from leaf import state as state_model

LAUNCHER = str(ROOT / "bin" / "leaf")
REGISTRATIONS = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"]


def hook(event: str, session: str, cwd) -> None:
    """Run Claude Code's first registered command for `event`, as it would, from
    the session's working directory `cwd`."""
    ran = subprocess.run(
        ["/bin/sh", "-c", REGISTRATIONS[event][0]["hooks"][0]["command"]],
        input=json.dumps({"hook_event_name": event, "session_id": session}),
        cwd=cwd,
        env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(ROOT)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert ran.returncode == 0, ran.stderr


def test_claude_code_runs_the_whole_hook_once_its_session_claims(page_dir, tmp_path):
    """Claude Code runs Leaf's turn and tool hooks in every session the plugin is
    installed in, and most never use Leaf, so the launcher skips them until the
    session claims. The hook before a `leaf` command opens the turn the skipped
    prompt hook would have, a claim joins it, and the session's Stop hook then
    runs in full and closes it. A `leaf.py` in the session's working directory
    never stands in for Leaf."""
    session = os.environ["CLAUDE_CODE_SESSION_ID"]
    task = tmp_path / "task"
    task.mkdir()
    (task / "leaf.py").write_text('raise SystemExit("the task\'s leaf.py ran")\n')
    hook("UserPromptSubmit", session, task)
    hook("PostToolBatch", session, task)
    hook("Stop", session, task)
    assert state_model.session_record(session) is None

    hook("PreToolUse", session, task)
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

    hook("Stop", session, task)
    turn_record_2 = state_model.session_record(session)
    assert turn_record_2 is not None
    assert turn_record_2["turn_closed"] is not None


def test_worker_batch_skips_uv_even_when_parent_holds_a_page(claimed, tmp_path):
    """Ignored worker batches need no project sync or managed Leaf imports."""
    uv = tmp_path / "uv"
    uv.write_text("#!/bin/sh\nexit 72\n")
    uv.chmod(0o755)

    def run(worker, *, harness="claude-code", event="PostToolBatch"):
        return subprocess.run(
            [LAUNCHER, "hook", "--harness", harness, "--if-claimed"],
            input=json.dumps(
                {
                    "hook_event_name": event,
                    "session_id": "s1",
                    **({"agent_id": "worker"} if worker else {}),
                }
            ),
            env={**os.environ, "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"]},
            capture_output=True,
            text=True,
            timeout=STATED_TIMEOUT,
            check=False,
        )

    worker = run(True)
    assert (worker.returncode, worker.stdout, worker.stderr) == (0, "", "")
    parent = run(False)
    assert parent.returncode == 72, (parent.stdout, parent.stderr)
    prompt = run(True, event="UserPromptSubmit")
    assert prompt.returncode == 72, (prompt.stdout, prompt.stderr)
    codex = run(True, harness="codex")
    assert codex.returncode == 72, (codex.stdout, codex.stderr)


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
        json.dumps(
            {
                "hook_event_name": "Pages",
                "session_id": "s1",
                "forks": True,
                "module": hashlib.sha256(
                    (ROOT / "hooks" / "claude-code.ts").read_bytes()
                ).hexdigest(),
            }
        )
    )
    follower.stdin.close()
    # The claimed page has no server, so the follower lists nothing and goes on
    # following it.
    assert json.loads(follower.stdout.readline()) == {"pages": [], "completions": []}
    assert follower.poll() is None
    follower.send_signal(signal.SIGTERM)
    assert follower.wait(timeout=STATED_TIMEOUT) == 128 + signal.SIGTERM, (
        follower.stderr.read()
    )
