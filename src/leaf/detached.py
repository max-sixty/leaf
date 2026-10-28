"""Start a detached child process and wait until it is ready.

For example, `hosting._starting_server` starts a page server this way (`leaf
server _serve`), and `codex_adapter` starts the Codex delivery adapter (`leaf codex
run`). `starting_detached` spawns the child and yields what it sends through
`Handshake.announce`, or raises `StartRefused` with the child's reason.

Leaving the parent's `with` block normally accepts the start, and an exception
abandons it. Only after acceptance does the child run the `commit` callback it gave
`announce`, then send a confirmation. The page server writes its service record and
claim in that callback, so an abandoned start publishes nothing. The Codex adapter
passes no callback: it starts its connection before announcing and exits if
abandoned.

A missing confirmation raises `StartUnconfirmed`, though the child may have
committed. `hosting.claim_and_start` then stops the server only while the page still
holds the claim it captured, and never restores the claim that start replaced.
"""

import json
import os
import socket
import subprocess
import sys
import traceback
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path

from .harness import Harness, detached_environment
from .machine import sandbox_refusal
from .refusals import Refused


class StartRefused(Refused):
    """A detached start the producer refused, carrying its reason."""


class StartUnconfirmed(Refused):
    """An accepted start whose confirmation did not arrive. The child may have
    committed, though the caller reports it like a refusal."""


@contextmanager
def starting_detached(
    arguments: list[str],
    *,
    harness: Harness | None,
    what: str,
    log: Path | None = None,
    cwd: Path | None = None,
    timeout: float | None = None,
    module: str = "leaf",
    launcher: Path | None = None,
):
    """Spawn `python -m MODULE ARGUMENTS --handshake FD` in a session of its own, and
    yield its announcement, then accept and confirm on context exit.

    Raises `StartRefused` with the child's reason when it refuses, exits, or does not
    answer within `timeout`; a child that has not answered by then is terminated.
    `what` names the child in a refusal that carries no reason of its own.
    sys.executable is the resolved uv environment, so this skips uv. A selected
    session runtime supplies its launcher when starting delivery; the handshake
    descriptor passes through that launcher's exec chain unchanged.
    """
    caller, child = socket.socketpair()
    try:
        environment = detached_environment(harness)
        if launcher is not None:
            environment.pop("LEAF_HOST_LAUNCHER", None)
        with open(log or os.devnull, "wb", buffering=0) as output:
            process = subprocess.Popen(
                [
                    *([str(launcher)] if launcher else [sys.executable, "-m", module]),
                    *arguments,
                    "--handshake",
                    str(child.fileno()),
                ],
                cwd=cwd,
                env=environment,
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
        yield answer
        caller.sendall(b"\n")
        try:
            confirmed = caller.makefile("rb").readline()
        except TimeoutError:
            raise StartUnconfirmed(
                f"{what} was accepted but did not confirm publication"
            ) from None
        if not confirmed:
            raise StartUnconfirmed(
                f"{what} was accepted but did not confirm publication"
            )
        answer = json.loads(confirmed)
        if "error" in answer:
            raise StartRefused(answer["error"] or f"{what} did not commit")
    finally:
        caller.close()
        child.close()


class Handshake:
    """The child's end: refuse with a reason, or announce and wait for acceptance.

    Used as a context manager around the child's whole start, so a start that ends
    in an exception before announcing — a refusal or a fault — reaches the
    caller as its reason rather than as a bare end of stream.
    """

    def __init__(self, fd: int) -> None:
        self._socket = socket.socket(fileno=fd)
        self._answered = False

    def announce(
        self,
        answer: dict | None = None,
        *,
        commit: Callable[[], dict] | None = None,
    ) -> bool:
        """Send `answer`, wait for the caller to accept, and return whether it did.

        On acceptance, run `commit` if given and send its result as the
        confirmation. A child that passes no `commit` has already set up its
        resource, and cleans it up itself when this returns False. A confirmation
        that fails to send does not undo the commit.
        """
        try:
            self._socket.sendall(json.dumps(answer or {}).encode() + b"\n")
            accepted = self._socket.recv(1) == b"\n"
        except OSError:
            accepted = False
        if not accepted:
            self._answered = True
            self._socket.close()
            return False
        result = commit() if commit is not None else answer or {}
        self._answered = True
        try:
            self._socket.sendall(json.dumps(result).encode() + b"\n")
        except OSError:
            pass  # The caller already committed; confirmation cannot revoke it.
        finally:
            self._socket.close()
        return True

    def __enter__(self):
        return self

    def __exit__(self, kind, error, _traceback) -> None:
        if error is not None and not self._answered:
            # Worded as the CLI words each at its own boundary: a refusal by its
            # reason, an exit by its status, and any other fault by its class.
            if isinstance(error, Refused):
                reason = sandbox_refusal(error) or str(error)
            elif isinstance(error, SystemExit):
                reason = f"exited with status {error.code}"
            else:
                reason = "".join(traceback.format_exception_only(kind, error)).strip()
            try:
                self._socket.sendall(json.dumps({"error": reason}).encode() + b"\n")
            except OSError:
                pass
        self._socket.close()
