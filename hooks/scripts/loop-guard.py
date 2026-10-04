#!/usr/bin/env python3
"""Claude Code's background-watch transport, separate from Leaf's application.

The synchronous Stop, prompt and SessionEnd registrations call `bin/leaf hook`
directly. That shell launcher owns uv; no Leaf Python process starts an
environment manager.

This supervisor calls `bin/leaf hook --watch`. Claude's asyncRewake registration
wakes on exit 2, a status uv can also use for startup failures, so only a clean
Leaf return with a nonempty result becomes stderr and exit 2 here. Every other
ending is silent. The harness's timeout signal is forwarded to the child, allowing
the watch to release its lease. The registration gates on CLAUDECODE because
Codex ignores asyncRewake and would wait on this long-running command.
"""

import contextlib
import signal
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]


def watch(payload: str) -> None:
    """Run the watch, and wake the session, by exiting 2 with it on stderr, only
    with what the watch printed on a clean exit. uv and Python spend exit 2 on their
    own failures, so the status alone would wake the session with an error at
    every turn's end."""
    children = []
    # The harness stops the hook at its timeout; the watch has to let its lease go
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
                [str(PROJECT / "bin" / "leaf"), "hook", "--watch"],
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


if __name__ == "__main__":
    watch(sys.stdin.read())
