"""The text a caller pipes to a `leaf` command on stdin, read only where it can end.

Text comes on stdin through a pipe, a heredoc or a file. A terminal or a socket is
the caller's own session, which may never end: Claude Code hands a command spanning
lines a socket that stays open (measured at 2.1.304), so a reply whose `--markup`
spans lines and that gives no `--text` would wait there until the tool's timeout.
Reading neither, a command given no text finds none and refuses at once, as for an
empty pipe. An option that names stdin itself, `--file -`, reads it whatever it is.

A sandboxed command runs under the bridge (`bridge.run`), which relays the
caller's stdin over a pipe of its own, so the bridge's client reads the caller's
descriptor and passes the reading to the command as `STDIN_PIPED`.
"""

import io
import os
import stat
import sys

# Set by the bridge's client to "1" or "0": whether the caller's stdin is piped.
STDIN_PIPED = "LEAF_STDIN_PIPED"


def piped(fd: int) -> bool:
    """Whether `fd` is a pipe or a file, which ends, rather than a terminal or a
    socket, which may not."""
    mode = os.fstat(fd).st_mode
    return stat.S_ISFIFO(mode) or stat.S_ISREG(mode)


def piped_stdin() -> str:
    """The text piped or redirected to this command, or "" when nothing was. A
    stream with no descriptor was handed in by the caller in process, and is read."""
    if (relayed := os.environ.get(STDIN_PIPED)) is not None:
        return sys.stdin.read() if relayed == "1" else ""
    try:
        fd = sys.stdin.fileno()
    except io.UnsupportedOperation:
        return sys.stdin.read()
    return sys.stdin.read() if piped(fd) else ""
