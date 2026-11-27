"""The serving process's lifetime: how it ends (`exit_serving`), the signals that
end it, and the check inside the server that stops it once its service ends and hands
its restart to the copy of Leaf its session runs (`stop_when_service_ends`)."""

from __future__ import annotations

import os
import signal
import sys
import threading
import time
from pathlib import Path
from typing import NoReturn

from leaf.base.detached import starting_detached
from leaf.base.leases import end_if_terminated
from leaf.base.refusals import Refused
from leaf.base.schema import ORPHAN_GRACE_SECS
from leaf.base.server import read_service
from leaf.base.service import page_claim, page_holder
from leaf.base.state import LoadedCopy
from leaf.records.transaction import PageTransaction


def exit_serving(status: int) -> NoReturn:
    """End the serving process at once, which closes its listening socket, every
    accepted keep-alive socket and its live lease together; a graceful `shutdown()`
    can release the lease while a handler thread still owns an accepted connection.

    That exit runs no exit handler, so the App Servers the process started, each in
    a session of its own, are stopped first (`codex.stop_private_app_servers`)."""
    from leaf.agents.codex import stop_private_app_servers

    stop_private_app_servers()
    os._exit(status)


def exit_serving_on_signals() -> None:
    """End this serving process through `exit_serving` on SIGINT, SIGTERM or
    SIGHUP, as `server stop` ends it, with status 128 plus the signal's number.

    Unwinding instead would release the lease while the row publisher and the
    lifetime check still run, long enough for them to overwrite a successor's row
    or start a title App Server after the exit handlers stopped them.

    While it serves, uvicorn catches SIGINT and SIGTERM itself. It closes its
    listener, lets the responses in flight finish, and raises the signal again,
    which reaches this handler. A signal that arrived earlier, whose raise a
    finalizer discarded (`leases.release_on_termination`), ends the process here
    before the threads start."""
    end_if_terminated()
    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, lambda signum, _frame: exit_serving(128 + signum))


def stop_when_service_ends(page_dir: Path) -> None:
    """Apply desired state and session ownership from inside the server, exiting
    as the shutdown operation (`exit_serving`), and follow the copy of Leaf the
    session holding the page runs, once that is another than the server's.

    A pass reads service and ownership at least every two seconds, since a
    claimant that dies without ending its session writes nothing. Maintenance
    uses this timer alone: retained pages must not each hold a native watcher.

    A server outlives the hooks that start it, while the session holding its page
    runs the Leaf its hooks run (`session-lifetime.md`, "Which Leaf runs a
    session"). Where that is another Leaf, the agent checks the page with one Leaf
    while the user's tab draws it with another. Where Codex or Pi updated the
    server's copy in place, the server has lost its environment too: it would import
    each module it loads later from the new copy, beside the old modules it holds,
    and the browser would load the new copy's runtime from it. So each pass, while
    the service is persistent or a live session holds the page, asks which copy
    should run the server now (`state.LoadedCopy.successor`), and has the copy it
    names restart it (`_follow_copy`). It asks again only once it names another
    copy, so a copy that declines, as one that can't serve the page does, isn't
    asked on every pass. A server whose session has ended retires on its copy after
    its grace, which leaves its service enabled for a resumed session's prompt to
    serve again; a restart would instead disable it (`hosting.restarting_server`)."""

    copy = LoadedCopy()
    asked = None
    orphaned_at = None
    while True:
        service = read_service(page_dir)
        if not service or not service["enabled"]:
            exit_serving(0)
        persistent = service["lifetime"] == "persistent"
        held = page_claim(page_dir)
        holder = page_holder(page_dir, held, None)
        claimed = isinstance(holder, dict)
        if persistent or claimed:
            root = copy.successor(held["id"] if held is not None and claimed else None)
            if root is not None and root != asked:
                asked = root
                threading.Thread(
                    target=_follow_copy,
                    args=(page_dir, service["server_id"], root),
                    daemon=True,
                ).start()
        if persistent:
            time.sleep(2.0)
            continue
        if holder is not None:
            orphaned_at = None
        elif orphaned_at is None:
            orphaned_at = time.monotonic()
        elif time.monotonic() - orphaned_at >= ORPHAN_GRACE_SECS:
            # A transfer may land after the unlocked observation above. Recheck
            # beside process exit under the page transaction so a new live owner
            # cannot inherit a server already committed to retiring.
            try:
                with PageTransaction(page_dir) as page:
                    service = read_service(page_dir)
                    if not service or not service["enabled"]:
                        exit_serving(0)
                    if (
                        service["lifetime"] == "persistent"
                        or page.holder(None) is not None
                    ):
                        orphaned_at = None
                        continue
                    exit_serving(0)
            except FileNotFoundError:
                # Deleting the page removes its successful-init identity. The
                # service has nothing left to preserve and must not recreate it.
                exit_serving(0)
        time.sleep(min(2.0, ORPHAN_GRACE_SECS))


def _follow_copy(page_dir: Path, server_id: str, root: Path) -> None:
    """Hand the restart of this server to the copy at `root`
    (`vendoring.follow_copy`), and return once that copy runs and has taken it on.

    It runs through that copy's launcher, since this process's environment may have
    gone with its own copy, in a thread of its own, so the lifetime check goes on
    while the launcher builds the new copy's environment. A launch that fails, as
    one that can't build the environment does, is tried again on the retry ladder
    (`codex.retry_delay`) for as long as this server serves.

    The child's environment names no session, as a server a hook starts runs; it
    reads the session from the page's claim.

    It loads no module the server has not: the server loads `leaf.agents.codex` before
    it serves, as `exit_serving` relies on too, and processes that never serve, such
    as hooks, load this module through `hosting`, so `codex` is imported here rather
    than with it."""
    from leaf.agents.codex import retry_delay

    failures = 0
    while True:
        try:
            with starting_detached(
                [
                    "server",
                    "_follow",
                    str(page_dir),
                    "--server-id",
                    server_id,
                ],
                harness=None,
                what=f"the restart of the server for {page_dir} under the new copy",
                launcher=(root / "bin" / "leaf").resolve(),
            ):
                return
        except (Refused, OSError) as error:
            failures += 1
            print(f"Leaf's new copy did not start: {error}", file=sys.stderr)
        time.sleep(retry_delay(failures))
