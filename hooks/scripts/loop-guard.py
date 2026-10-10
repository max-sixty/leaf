#!/usr/bin/env python3
"""Claude Code's background-watch transport, separate from Leaf's application.

The synchronous Stop, prompt and SessionEnd registrations call `bin/leaf hook`
directly. That shell launcher owns uv; no Leaf Python process starts an
environment manager.

This supervisor calls `bin/leaf` with its own arguments, which the registration
states (`hook --harness claude-code --watch`). Claude's asyncRewake registration
wakes on exit 2, a status uv can also use for startup failures, so only a clean
Leaf return with a nonempty result becomes stderr and exit 2 here. Failures keep
the child's stderr and become nonblocking exit 1; cancellation stays quiet.
The harness's timeout signal is forwarded to the child, allowing the watch to
release its lease. Only Claude Code's registrations run it: Codex
ignores asyncRewake and would wait on this long-running command.

Where Leaf's hooks module keeps the session's watch instead (`hooks/claude-code.ts`),
it marks the Stop payload it passes on `leaf_watch: "module"`, and this ends at once
without starting a second watch.
"""

import contextlib
import json
import signal
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]


def watch(args: list[str], payload: str) -> None:
    """Run the watch, and wake the session, by exiting 2 with it on stderr, only
    with what the watch printed on a clean exit. uv and Python spend exit 2 on their
    own failures, so the status alone would wake the session with an error at
    every turn's end."""
    children = []
    cancelled = False

    def cancel(signum, _frame):
        nonlocal cancelled
        cancelled = True
        if children:
            children[0].terminate()
        else:
            sys.exit(128 + signum)

    # A harness timeout forwards termination so the watch releases its lease.
    for ending in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(ending, cancel)
    try:
        children.append(
            subprocess.Popen(
                [str(PROJECT / "bin" / "leaf"), *args],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        )
    except OSError as error:
        sys.exit(f"Leaf watch could not start: {error}")
    [child] = children
    woke, errors = child.communicate(payload)
    if cancelled:
        return
    if child.returncode != 0:
        sys.stderr.write(f"Leaf watch failed (exit {child.returncode}): {errors}")
        sys.exit(1)
    if woke.strip():
        sys.stderr.write(woke)
        sys.exit(2)


def module_watches(payload: str) -> bool:
    """Whether Leaf's hooks module marked this Stop as one whose watch it keeps."""
    with contextlib.suppress(ValueError):
        record = json.loads(payload)
        return isinstance(record, dict) and record.get("leaf_watch") == "module"
    return False


if __name__ == "__main__":
    payload = sys.stdin.read()
    if not module_watches(payload):
        watch(sys.argv[1:], payload)
