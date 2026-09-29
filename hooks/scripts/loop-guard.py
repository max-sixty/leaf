#!/usr/bin/env python3
"""Stop / UserPromptSubmit / SessionEnd / PostToolUse hook — keeps the loop honest.

The loop asks the agent to restart `leaf wait` after every round, and a page
whose watcher never came back is invisible from the browser: it looks exactly like a
page whose user has said nothing yet. These hooks make the loop the harness's
business rather than the model's memory. Stop protects a background wait where the
host can return its result and keeps a foreground-only host's page owner inside the
turn polling the exact wait session. A named wait transfers that duty to the task
that runs it.
UserPromptSubmit opens the turn and surfaces waiting input; SessionEnd releases the
session's claims, behind which a session-lifetime server retires once no live
successor has taken the page. In Claude Code, PostToolUse after a background
command names a `leaf wait` that command started, with how to close the turn it
outlives. Codex runs the same `hooks.json` and ignores its `if` filter, so that
registration keeps a `$CLAUDECODE` gate ahead of this script.

The CLI owns the turn's active-ownership reading. SessionEnd only releases
records still naming the ended session, under the page transaction lock. Its
standard-library path works before this plugin copy has an environment.

What is left is the one thing the CLI cannot do for itself: fail open. Anything
unexpected — no uv on PATH, an install that will not sync, a timeout — is
swallowed, and the turn proceeds with the guard silent. A Stop hook is the worst
possible place for a leaf bug to strand the user, and the failures worth
guarding hardest against are the ones where the CLI never starts.

The hook's environment and the shell tool's have to agree on XDG_STATE_HOME. A
serve and a `leaf wait` write their claim records from a shell initialized by
the user's profile, while the CLI reads them here from the environment the
agent host hands this process. A value set only in the shell profile leaves the
guard reading an empty claims home and saying nothing — fail-open, like
everything else here.

This asks uv for the project rather than running `bin/leaf`, because the guard
never needs the browser the launcher's two special cases supply. `--no-dev`
matches the launcher: the dev group is the suite's, not a host's.
"""

import json
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]


def main() -> None:
    try:
        payload = sys.stdin.read()
        hook = json.loads(payload)
        event = hook.get("hook_event_name")
        if event == "SessionEnd":
            sys.path.insert(0, str(PROJECT / "skills" / "leaf" / "scripts"))
            from leaf.state_paths import end_session

            end_session(hook.get("session_id") or "")
            return
        answer = subprocess.run(
            ["uv", "run", "-q", "--no-dev", "--project", str(PROJECT), "leaf", "hook"],
            input=payload,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        sys.stdout.write(answer.stdout)
    except Exception:  # noqa: BLE001 — a hook that raises stops the turn it guards
        return


if __name__ == "__main__":
    main()
