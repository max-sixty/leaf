#!/usr/bin/env python3
"""Stop / UserPromptSubmit / SessionEnd hook — keeps the loop honest.

The loop asks the agent to restart `leaf wait` after every round, and a page
whose watcher never came back is invisible from the browser: it looks exactly like a
page whose user has said nothing yet. These hooks make the loop the harness's
business rather than the model's memory. Stop protects a background wait where the
host can return its result, and keeps a foreground-only host's page owner inside the
turn polling the exact wait session. A named wait transfers that duty to the task that
runs it. UserPromptSubmit surfaces unacknowledged events; SessionEnd releases the
session's claims, behind which a session-lifetime server retires once no live
successor has taken the page.

This script decides nothing. Both questions — whether this session holds a page
at all, and what to say about the ones it holds — belong to interact.py, which
owns the page-directory model. One `uv run` per turn is what it costs to ask
them there; a cheap answer here would be a second copy of a rule that changes
every time a host states its session lifetime a new way.

What is left is the one thing interact.py cannot do for itself: fail open.
Anything unexpected — no uv on PATH, a broken interact.py, a timeout — is
swallowed, and the turn proceeds with the guard silent. A Stop hook is the worst
possible place for a leaf bug to strand the user, and the failures worth
guarding hardest against are the ones where interact.py never starts.

The hook's environment and the shell tool's have to agree on XDG_STATE_HOME. A
serve and a `leaf wait` write their claim records from a shell initialized by
the user's profile, while interact.py reads them here from the environment the
agent host hands this process. A value set only in the shell profile leaves the
guard reading an empty claims home and saying nothing — fail-open, like
everything else here.
"""

import subprocess
import sys
from pathlib import Path

INTERACT = (
    Path(__file__).resolve().parents[2] / "skills" / "leaf" / "scripts" / "interact.py"
)


def main() -> None:
    try:
        answer = subprocess.run(
            ["uv", "run", str(INTERACT), "hook"],
            input=sys.stdin.read(),
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
