"""Private resource preparation, caller acceptance, and producer confirmation.

The child first announces a prepared resource without publishing ownership. The
caller captures the announced identity inside `starting_detached`, then accepts
on normal context exit. Acceptance is the caller's one write. The child commits
its resource and confirms that publication before the caller returns.

Abandonment before acceptance publishes nothing. After acceptance, a missing
confirmation is uncertain commitment, never evidence that the child did not
commit. The caller already holds the announced owner and retires only that
owner's resources; it never restores an owner an accepted start superseded.
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


class StartRefused(RuntimeError):
    """A detached start the producer refused, carrying its reason."""


class StartUnconfirmed(RuntimeError):
    """An accepted start whose publication confirmation did not arrive."""


@contextmanager
def starting_detached(
    arguments: list[str],
    *,
    harness: Harness | None,
    what: str,
    log: Path | None = None,
    cwd: Path | None = None,
    timeout: float | None = None,
):
    """Spawn `python -m leaf ARGUMENTS --handshake FD` in a session of its own, and
    yield its private announcement, then accept and confirm on context exit.

    Raises `StartRefused` with the child's reason when it refuses, exits, or does not
    answer within `timeout`; a child that has not answered by then is terminated.
    `what` names the child in a refusal that carries no reason of its own.
    sys.executable is the resolved uv environment, so this skips uv.
    """
    caller, child = socket.socketpair()
    try:
        with open(log or os.devnull, "wb", buffering=0) as output:
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
                env=detached_environment(harness),
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
    """The child's end: refuse with a reason, or announce and wait for the commit.

    Used as a context manager around the child's whole start, so a start that ends
    in an exception before announcing — a `sys.exit` refusal or a fault — reaches the
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
        """Prepare an announcement, accept the caller's commit, then confirm it.

        A caller leaving before acknowledgement publishes nothing. Once accepted,
        the producer commits its resource and confirms the resulting identity;
        losing the confirmation does not undo an accepted commit.
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
