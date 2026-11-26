"""`leaf codex run`, the Codex delivery adapter: the detached process that carries Leaf
delivery into later turns of one Codex task.

Serving a claimed page, or explicitly running `leaf page claim`, leaves this process
running behind the turn that started it (`codex_adapter.preparing_adapter`), so a
user's later updates reach the same Codex task instead of waiting for the agent to ask
again. It runs the task's session watch (`session.Watch`), as `leaf wait` and a hook
harness's watch between turns do: it captures each batch into the task's delivery
record, offers one delivery at a time through the task's transport
(`codex_adapter.offer_queued_delivery`), and reconciles the receipt its page is owed
however that delivery was taken (`codex.recover_codex_receipt`). It holds the task's
wait lease and a lease of its own, since a generic wait lease cannot prove its output
can enter a later Codex turn.

An adapter outlives the hooks that start it, and Codex replaces its one installed
copy in place (`session-lifetime.md`, "Which Leaf runs a session"), deleting the old
one, environment included, so an adapter left running would load each module it
imports later from the new copy, beside the old modules it already holds. So the
adapter asks each pass which copy should run it now (`state.LoadedCopy.successor`),
as a page server does (`server_lifetime.stop_when_service_ends`), and once that
names one, hands its task to an adapter from that copy (`_hand_over`). Only the Leaf the
task's hooks run claims for the task (`harness.session_harness`), so an adapter
starts from that copy. One running Codex's copy moves to the copy Codex puts at its
path, and one whose task's hooks have since run another installed copy moves to
that one. An update that moves the page protocol leaves the task's pages at the old
one, which the restart of each page's server renews (`vendoring.follow_copy`), and
the successor delivers their input once it does. An adapter from a checkout, as
where the task's hooks run one, follows no copy: it keeps the modules it loaded
and imports any later one from the checkout as it stands, since whoever runs a
checkout decides when it changes.

Restarting the adapter from the task's prompt hook would leave it on its deleted
copy until the task's next prompt, which can come hours later. Replacing the process
with `exec` through the new copy's launcher would leave nothing to try again when the
new adapter fails to start,
and would carry the start lock across the exec only if the new adapter knew to
release it.
"""

import sys
import time
from contextlib import ExitStack
from pathlib import Path

from leaf.agents import codex
from leaf.agents.codex import retire_gone_task_records, retry_delay
from leaf.agents.codex_adapter import (
    ADAPTER,
    TaskConnection,
    adapter_log_path,
    adapter_start_lock_path,
    capture_batch,
    check_queue_command,
    offer_queued_delivery,
    start_adapter,
)
from leaf.base.detached import Handshake
from leaf.base.harness import CodexHarness, Harness, session_harness
from leaf.base.leases import (
    adapter_is_live,
    adapter_lease_path,
    release_lease,
    take_lease,
    wait_is_live,
)
from leaf.base.refusals import Refused
from leaf.base.state import LoadedCopy, flocked
from leaf.commands.session import PageTick, Watch, read_watch_pass
from leaf.pages.render_gate.messages import message_check
from leaf.records.transaction import owned_pages


def run_adapter(
    codex_path: str,
    handshake: Handshake | None = None,
    app_server: str | None = None,
) -> int:
    """Own the session watch until every claimed page ends or transfers, or another
    copy should run the adapter (`LoadedCopy.successor`), in which case the adapter
    first starts its successor from that copy.

    A detached adapter announces its readiness through `handshake` once it holds
    its leases and its transport answers, and exits if `leaf page claim` left
    without committing that start."""
    harness = session_harness()
    if harness is None or harness.name != CodexHarness.name:
        raise Refused("the Codex adapter needs a Codex task identity")
    with ExitStack() as resources:
        copy = LoadedCopy()
        resources.callback(copy.close)
        lease = take_lease(adapter_lease_path(harness.session))
        if lease is None:
            raise Refused("a Codex delivery adapter is already active")
        # The lease's record names this adapter's transport, so a later `leaf page
        # claim` in the task verifies any requested endpoint against the one it joins.
        resources.callback(release_lease, lease)
        ADAPTER.write(adapter_lease_path(harness.session), {"app_server": app_server})
        watch = Watch(harness)
        if not watch.acquire():
            raise Refused(
                "another `leaf wait` is already active; stop it before starting delivery"
            )
        resources.callback(watch.release)
        connection = None
        start_lock = adapter_start_lock_path(harness.session)

        def retire() -> None:
            """Let this adapter's leases go, and with them, once the task owns no page,
            the log this run wrote. Taken under the start lock, so no successor starts
            until it is done; a task that still owns a page keeps the log for the next
            adapter it starts. On the way out it retires every task's delivery records
            whose pages are gone (`retire_gone_task_records`)."""
            resources.close()
            if not owned_pages(harness.session):
                adapter_log_path(harness.session).unlink(missing_ok=True)
            retire_gone_task_records()

        def capture(tick: PageTick) -> bool:
            """Capture the batch a pass found on one page into the task's collecting
            record, which the next offer delivers."""
            return capture_batch(
                harness.session, tick.transaction, tick.batch, work=tick.work
            )

        if app_server is not None:
            connection = TaskConnection(app_server, harness.session, message_check)
            resources.callback(connection.stop)
            connection.start()
        else:
            check_queue_command(codex_path)
        if handshake is not None and not handshake.announce():
            return 1
        failures = 0
        while True:
            if (root := copy.successor(harness.session)) is not None:
                return _hand_over(harness, codex_path, app_server, resources, root)
            try:
                recovered = codex.recover_codex_receipt(harness.session)
                if not recovered:
                    with flocked(start_lock):
                        if not owned_pages(harness.session):
                            retire()
                            return 0
                    recovered = offer_queued_delivery(
                        codex_path,
                        harness.session,
                        connection,
                    )
            # Transport and page errors belong to this retry boundary; neither
            # may end the adapter and strand the pages it claims.
            except Exception as error:
                failures += 1
                if failures == 1:
                    print(
                        f"Codex delivery retry: {error}",
                        file=sys.stderr,
                        flush=True,
                    )
                time.sleep(retry_delay(failures))
                continue
            failures = 0
            if recovered:
                continue

            mark = watch.mark()
            reading = read_watch_pass(watch, None, deliver=capture)
            if reading.delivered:
                continue
            if reading.outcome is not None or not reading.live:
                with flocked(start_lock):
                    reading = read_watch_pass(watch, None, deliver=capture)
                    if reading.delivered or (reading.outcome is None and reading.live):
                        continue
                    if not owned_pages(harness.session):
                        retire()
                        return reading.outcome or 0
                # The adapter belongs to the session's ownership, not its current
                # authored status. Idle pages deliver nothing; a later status
                # resumes this same adapter. Wait outside the startup lock.
                watch.await_news(mark, timeout=1)
                continue
            # A second a pass, as well as each time a page moves: the queued offer
            # and receipt recovery above answer to Codex, not to the page's files.
            watch.await_news(mark, timeout=1)


def _hand_over(
    harness: Harness,
    codex_path: str,
    app_server: str | None,
    resources: ExitStack,
    root: Path,
) -> int:
    """Hand this adapter's task to an adapter from the copy at `root`, and return
    once one holds the task, a `leaf wait` does, or the task owns no page.

    Under the start lock, this adapter lets `resources`, its leases and connection,
    go before the successor takes them, so a claim meanwhile waits and then joins
    the successor, which reconciles any turn the dropped connection was following.
    The successor starts through that copy's launcher, since this process's
    environment may have gone with its own copy. One that refuses or can't start is
    tried again on the retry ladder, with nothing held meanwhile."""
    start_lock = adapter_start_lock_path(harness.session)
    failures = 0
    while owned_pages(harness.session):
        with flocked(start_lock):
            resources.close()
            if adapter_is_live(harness.session) or wait_is_live(None, harness.session):
                return 0
            try:
                start_adapter(
                    harness, codex_path, app_server, (root / "bin" / "leaf").resolve()
                )
                return 0
            except (Refused, OSError) as error:
                failures += 1
                print(
                    f"Codex delivery handover retry: {error}",
                    file=sys.stderr,
                    flush=True,
                )
        time.sleep(retry_delay(failures))
    return 0
