"""A leaf process started in a session of its own, and the handshake that commits it.

A page server and a Codex delivery adapter both have to outlive the command that
starts them, so each is spawned into a session of its own rather than held. Their
caller still has to know whether the start happened, and has cleanup of its own to
run when it did not: a claim to restore, a stop to issue. So the start is a
handshake over a private socket pair, and the commit is the caller's to make:

1. The child answers once, with one JSON line: `{"error": reason}` to refuse, or
   its announcement — the URL a server minted, or nothing more than readiness.
2. The caller reads that line. An announcement it keeps is committed by writing one
   byte back, which is the last thing the caller does before returning it.
3. The child, having announced, waits for that byte. An end of stream instead means
   the caller left without taking the announcement, and the child withdraws what it
   started.

The commit is therefore one write in the caller, never a write in the child whose
reading the caller may or may not have finished. A caller interrupted anywhere
before it has sent that byte can run its cleanup knowing the child will not stay
up behind it, and a caller that sent it knows the child is committed. A child that
refuses, or dies before announcing, closes its end, and the caller reads the reason
or the end of stream.

The child's own streams go to the log its caller names or to nothing: what a start
has to say travels in the handshake, and nobody drains a pipe once it is over.
"""

import json
import os
import socket
import subprocess
import sys
import traceback
from pathlib import Path


class StartRefused(RuntimeError):
    """A detached start that did not commit, carrying the reason the child gave."""


def start_detached(
    arguments: list[str],
    *,
    what: str,
    log: Path | None = None,
    cwd: Path | None = None,
    timeout: float | None = None,
) -> dict:
    """Spawn `python -m leaf ARGUMENTS --handshake FD` in a session of its own, and
    return its announcement once the start is committed.

    Raises `StartRefused` with the child's reason when it refuses, exits, or does not
    answer within `timeout`; a child that has not answered by then is terminated.
    `what` names the child in a refusal that carries no reason of its own.
    sys.executable is the resolved uv environment, so this skips uv.
    """
    caller, child = socket.socketpair()
    try:
        with open(log or os.devnull, "ab", buffering=0) as output:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "leaf",
                    *arguments,
                    "--handshake",
                    str(child.fileno()),
                ],
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=output,
                start_new_session=True,
                pass_fds=(child.fileno(),),
            )
        child.close()
        caller.settimeout(timeout)
        try:
            line = caller.makefile("rb").readline()
        except TimeoutError:
            process.terminate()
            raise StartRefused(f"{what} did not become ready") from None
        answer = json.loads(line) if line else {"error": None}
        if "error" in answer:
            raise StartRefused(answer["error"] or f"{what} did not start")
        caller.sendall(b"\n")
        return answer
    finally:
        caller.close()
        child.close()


class Handshake:
    """The child's end: refuse with a reason, or announce and wait for the commit.

    Used as a context manager around the child's whole start, so a start that ends
    in an exception before announcing — a `sys.exit` refusal or a fault — reaches the
    caller as its reason rather than as a bare end of stream.
    """

    def __init__(self, fd: int) -> None:
        self._socket = socket.socket(fileno=fd)
        self._answered = False

    def announce(self, answer: dict | None = None) -> bool:
        """Announce the start and wait for the caller to commit it.

        False when the caller left without taking the announcement: the child then
        withdraws what it started.
        """
        self._answered = True
        try:
            self._socket.sendall(json.dumps(answer or {}).encode() + b"\n")
            return self._socket.recv(1) == b"\n"
        except OSError:
            return False
        finally:
            self._socket.close()

    def __enter__(self):
        return self

    def __exit__(self, kind, error, _traceback) -> None:
        if error is not None and not self._answered:
            # Worded as the CLI words each at its own boundary: an exit's message,
            # a RuntimeError's refusal, and any other fault by its class.
            if isinstance(error, SystemExit):
                reason = (
                    error.code
                    if isinstance(error.code, str)
                    else f"exited with status {error.code}"
                )
            elif isinstance(error, RuntimeError):
                reason = str(error)
            else:
                reason = "".join(traceback.format_exception_only(kind, error)).strip()
            try:
                self._socket.sendall(json.dumps({"error": reason}).encode() + b"\n")
            except OSError:
                pass
        self._socket.close()
