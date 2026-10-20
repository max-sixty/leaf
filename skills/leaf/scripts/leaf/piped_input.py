"""The text a caller hands a `leaf` command on stdin, read only where it can end.

Text comes on stdin through a pipe, a heredoc or a file. A terminal or a socket is
the caller's own session, which may never end: Claude Code hands a command spanning
lines a socket that stays open (measured at 2.1.304), so a reply whose `--markup`
spans lines and that gives no `--text` would wait there until the tool's timeout.
Reading neither, a command finds no text and refuses at once, as for an empty pipe.
The bridge (`bridge.run`) relays a sandboxed command's stdin by the same rule, since
the command it starts reads a pipe of its own.
"""

import io
import os
import stat
import sys


def piped(fd: int) -> bool:
    """Whether `fd` is a pipe or a file, which ends, rather than a terminal or a
    socket, which may not."""
    mode = os.fstat(fd).st_mode
    return stat.S_ISFIFO(mode) or stat.S_ISREG(mode)


def piped_stdin() -> str:
    """The text piped or redirected to this command, or "" when nothing was. A
    stream with no descriptor was handed in by the caller in process, and is read."""
    try:
        fd = sys.stdin.fileno()
    except io.UnsupportedOperation:
        return sys.stdin.read()
    return sys.stdin.read() if piped(fd) else ""
