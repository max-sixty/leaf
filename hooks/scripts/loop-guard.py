#!/usr/bin/env python3
"""Stop / UserPromptSubmit / SessionEnd hook — keeps the loop honest.

The loop is the harness's business rather than the model's memory: a page whose
watcher never came back is invisible from the browser, and looks exactly like a
page whose user has said nothing yet. Stop keeps a turn from ending over a page
whose carrier is not running, and over a delivered move it has not answered.
UserPromptSubmit opens the turn and surfaces waiting input; SessionEnd releases the
session's claims, behind which a session-lifetime server retires once no live
successor has taken the page.

In Claude Code a second Stop registration runs this script with `--watch`, which
Claude Code keeps in the background (`asyncRewake`) as the session's watch between
turns: its exit 2 wakes the session with its stderr, and any other ending is
silent. Codex runs the same `hooks.json`, ignoring `asyncRewake` and so waiting on
the hook, which is why that registration keeps a `$CLAUDECODE` gate ahead of this
script.

The library owns discovery and every hook's behavior. uv supplies its Python and
dependencies; the hook module runs directly, avoiding CLI imports and command
registration before checking whether this session holds a page. The host's
Python only launches that process and carries its answer.

What is left is the one thing the hook module cannot do for itself: fail open. Anything
unexpected — no uv on PATH, an install that will not sync, a timeout — is
swallowed, and the turn proceeds with the guard silent. A Stop hook is the worst
possible place for a leaf bug to strand the user, and the failures worth
guarding hardest against are the ones where the module never starts. The watch fails
open too: this script wakes the session only with what the watch printed on a
clean exit, and passes the host's signal at the hook's timeout on to it.

The hook's environment and the shell tool's have to agree on XDG_STATE_HOME. A
serve and a `leaf wait` write their claim records from a shell initialized by
the user's profile, while the library reads them here from the environment the
agent host hands this process. A value set only in the shell profile leaves the
guard reading an empty claims home and saying nothing — fail-open, like
everything else here.

This asks uv for the project rather than running `bin/leaf`, because the guard
never needs the browser the launcher's two special cases supply. `--no-dev`
matches the launcher: the dev group is the suite's, not a host's.
"""

import contextlib
import signal
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
COMMAND = [
    "uv",
    "run",
    "-q",
    "--no-dev",
    "--project",
    str(PROJECT),
    "python",
    "-m",
    "leaf.hooks",
]


def watch(payload: str) -> None:
    """Run the watch, and wake the session, by exiting 2 with it on stderr, only
    with what the watch printed on a clean exit. uv and Python spend exit 2 on their
    own failures, so the status alone would wake the session with an error at
    every turn's end."""
    children = []
    # The host stops the hook at its timeout; the watch has to let its lease go
    # with it, and a signal before it starts must not leave it starting unwatched.
    for ending in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(
            ending,
            lambda signum, _frame: (
                children[0].terminate() if children else sys.exit(128 + signum)
            ),
        )
    with contextlib.suppress(Exception):
        children.append(
            subprocess.Popen(
                [*COMMAND, "--watch"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
        )
        [child] = children
        woke, _ = child.communicate(payload)
        if child.returncode == 0 and woke.strip():
            sys.stderr.write(woke)
            sys.exit(2)


def main() -> None:
    try:
        payload = sys.stdin.read()
        if "--watch" in sys.argv[1:]:
            watch(payload)
            return
        answer = subprocess.run(
            COMMAND,
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
