"""Agent status and the `leaf wait` watch.

A watch discovers its pages before loading delivery or page projections, and
loads the HTTP server only to revive a dead one. Status writes use those same
projections without importing a server. Receipt remains `delivery`'s."""

import contextlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from .detached import StartRefused
from .file_changes import FileChanges, existing_root, target_paths
from .files import file_stamp
from .findings import Finding, note
from .harness import Harness, claim_harness, session_harness
from .leases import (
    end_if_terminated,
    release_lease,
    supersede_lease,
    take_lease,
    waiter_lease_path,
)
from .locations import path_location, paths_same
from .machine import state_home
from .presence import nudge_unwatched
from .refusals import Refused
from .schema import ANSWER_ASK_INSTRUCTION, MESSAGE_KINDS
from .served_state.reading import outside_inputs, page_input, page_reading
from .server import read_service, running_server
from .service import (
    PageTransaction,
    owned_pages,
    read_status,
    session_claims,
    unacknowledged,
)
from .state import SESSION_SUFFIX, session_file, still_named

# How often a watch rechecks a live page's server. It is also the longest a watch goes
# without a pass on a page whose files have not moved: nothing else a pass reads
# changes on the clock alone.
REVIVAL_CHECK_S = 5

# How long a normal turn-end watch gives the concurrent Stop hook to carry input:
# this is that hook's timeout (`hooks/hooks.json`), not evidence of pickup.
STOP_HOOK_S = 20


def cmd_waiting(page_dir: Path, detail: str) -> tuple[dict, list[dict]]:
    """Declare the page waiting on its user, putting down every start that stands
    (`todos.put_down`), and return the declaration, with the updates still owed an
    answer, which the page goes on showing over it."""
    from .revisioning import activate_source
    from .served_state.context import read_page
    from .todos import put_down

    with PageTransaction(page_dir) as page:
        activate_source(page_dir, transaction=page)
        put_down(page)
        status = page.set_status("waiting", detail)
        return status, read_page(page_dir, page.events).work.obligations


def cmd_idle(page_dir: Path, detail: str) -> dict:
    """Idle, putting down every start that stands, unless the page still owes its
    user an answer.

    Idling over an event nobody has answered ends the leaf on a user still
    owed one — unread, or read and left. The watcher's whole batch, not the
    user-facing count, so a worker's report cannot be left in place as
    provisional state forever either. The answers it holds the page for are
    `activity.blocking_obligations`, a started update's included: the Stop hook lets
    the turn that started one end over it, but closing the page answers nothing. It
    holds the page for every open to-do too, which only its ending discharges.
    The check and the transition share the log lock, so an event arriving
    or an acknowledgement advancing the cursor orders against them."""
    from .activity import blocking_obligations, unanswered
    from .served_state.context import read_page
    from .todos import put_down

    with PageTransaction(page_dir) as page:
        events = page.events
        work = read_page(page_dir, events).work
        state = {**work.presence, "activity": work.activity}
        claim = page.active_claim
        harness = claim_harness(claim) if claim is not None else None
        pending = len(unacknowledged(events, page.cursor))
        if pending:
            remedy = (
                harness.input_unpicked(page_dir, listening=state["listening"])
                if harness
                else "`leaf wait` prints them."
            )
            raise Refused(
                f"{pending} event{'s' if pending != 1 else ''} nobody has picked up, "
                f"so the page cannot idle yet. {remedy}"
            )
        owed = blocking_obligations(
            state,
            watched=harness is not None
            and harness.watcher_live(listening=state["listening"]),
        )
        if owed:
            raise Refused(
                f"{unanswered(owed, page_dir, 'acknowledged')}; answer before idling. "
                + ANSWER_ASK_INSTRUCTION
            )
        # A to-do is work the agent still owes, which closing the page would leave
        # open on a page nobody holds.
        if todos := work.durable.log.owed:
            named = "; ".join(f"{todo['id']} ({todo['title']})" for todo in todos)
            raise Refused(
                f"{len(todos)} open to-do{'s' if len(todos) != 1 else ''}: {named}. "
                "End each before idling with "
                '`leaf task end <page> <id> done "<where the result is>"`, or '
                '`dropped "<why>"`.'
            )
        put_down(page)
        return page.set_status("idle", detail)


class PageTick(NamedTuple):
    """Where one page stands at one pass of the watch."""

    page_dir: Path
    status: dict
    batch: list
    live: bool
    watch_state: str
    lost: bool
    restarted: str | None
    transaction: PageTransaction


class Watch:
    """A session's watch, one locked page reading at a time.

    A tick yields while the page's log lock remains held. The caller decides how
    to deliver the batch before asking for the next tick, so claim transfer,
    SessionEnd, event arrival, and delivery have one order. Pickup is recorded
    later, when the consumer confirms the delivery under its own transaction.
    A revival releases that transaction before waiting for the service
    transition, then rereads under a new transaction; no delivery snapshot
    crosses that unlocked interval.
    `watch_state` is ownership/lifetime; `lost` separately says the server is
    down with nothing left to bring it back: never served, or dead after a
    revival that did not hold. A stopped service is not lost: `server stop` is
    the agent's own choice, and `page init` stops a served page to re-vendor it and
    starts it again, so the wait watches a disabled service without reviving it.

    Between passes native subscriptions follow this session's claim partition,
    canonical targets (including prepared claims), lifecycle, and each page a pass
    found. A subscription is installed before its observation; its generation
    retains a write landing during the pass. Timed
    passes check process and lease facts, while a quiet wait performs no repeated
    page-tree stat scans.
    """

    def __init__(self, harness: Harness | None, pages: tuple[Path, ...] = ()):
        self.harness = harness
        self.session_id = harness.session if harness else None
        self.explicit_pages = pages
        targets = (None,) if harness else pages
        self.lease_paths = tuple(
            waiter_lease_path(page, self.session_id) for page in targets
        )
        self.leases = []
        self._revived: set = set()
        self._lost: set = set()
        self._check_at: dict = {}
        self.claims = (
            session_claims(self.session_id)
            if self.session_id
            else state_home() / "claims"
        )
        self.watched: list[Path] = []
        self.changes = None
        self.change_pages = None

    def acquire(self, *, supersede: bool = False) -> bool:
        """Hold the session lease, or every explicitly watched standalone page,
        taking it from a live holder where `supersede` says to."""
        if self.leases:
            return True
        for path in self.lease_paths:
            lease = supersede_lease(path) if supersede else take_lease(path)
            if lease is None:
                self.release()
                return False
            self.leases.append(lease)
        return True

    def holds(self) -> bool:
        """Whether no later watch has superseded this one's leases."""
        return all(
            still_named(lease.fileno(), path)
            for lease, path in zip(self.leases, self.lease_paths, strict=True)
        )

    def pages(self) -> list:
        """Read the current ownership set and include explicitly named pages."""
        watched = owned_pages(self.session_id) if self.harness is not None else []
        locations = {path_location(page) for page in watched}
        for page in self.explicit_pages:
            if path_location(page) not in locations:
                watched.append(page)
                locations.add(path_location(page))
        return watched

    def discovery_targets(self) -> set[Path]:
        """Canonical payloads named by this session's prepared or admitted locators."""
        if not self.session_id:
            return set()
        return {
            self.claims.parent / locator.name for locator in self.claims.glob("*.json")
        }

    def reading(self, discovery: set[Path] | None = None) -> tuple:
        """Stamp discovery and its payloads before a claim can enter the page set."""
        if discovery is None:
            discovery = self.discovery_targets()
        return (
            file_stamp(self.claims),
            tuple((target, file_stamp(target)) for target in sorted(discovery)),
            tuple(map(file_stamp, self.lease_paths)),
            *map(_page_reading_or_none, self.watched),
        )

    def mark(self) -> tuple:
        """What the next pass starts from, taken before it reads, so a write that
        lands during the pass moves the stamps `await_news` compares against."""
        pages = tuple(self.watched)
        discovery = self.discovery_targets()
        targets = discovery | {
            target for page in pages for target in outside_inputs(page)
        }
        if self.session_id:
            targets.add(session_file(self.session_id, SESSION_SUFFIX).resolve())
        targets.update(path.resolve() for path in self.lease_paths)
        roots = {existing_root(self.claims): False}
        roots.update({existing_root(target.parent): False for target in targets})
        for page in pages:
            roots[existing_root(page.parent)] = False
            roots[existing_root(page)] = True
        key = (pages, frozenset(targets))
        if (
            self.changes is None
            or key != self.change_pages
            or not self.changes.matches(roots)
        ):
            if self.changes is not None:
                self.changes.close()
            watched = target_paths(targets)
            self.changes = FileChanges(
                roots,
                lambda changed: (
                    changed == self.claims
                    or changed.parent == self.claims
                    or changed in watched
                    or any(page_input(page, changed) for page in pages)
                ),
            )
            self.change_pages = key
        # Stamp the subscribed set. A locator added during installation must
        # differ at the next comparison, so its target is subscribed in turn.
        return (list(pages), self.reading(discovery), self.changes.mark())

    def await_news(self, mark: tuple, timeout: float = REVIVAL_CHECK_S) -> bool:
        """Return True once anything the pass since `mark` read has moved, or False
        after `timeout` with nothing moved. A pass that found a different set of
        pages returns True at once: `mark` stamped the old set."""
        watched, before, generation = mark
        if self.watched != watched:
            return True
        deadline = time.monotonic() + timeout
        while True:
            if self.reading() != before:
                return True
            remaining = deadline - time.monotonic()
            # A stop whose raise a finalizer discarded ends the watch here, since
            # nothing would interrupt the wait (`release_on_termination`).
            end_if_terminated()
            if remaining <= 0 or not self.changes.wait(generation, remaining):
                return False
            # Native APIs may coalesce diagnostics with their parent directory,
            # or deliver pre-subscription changes late. A notification schedules
            # the authoritative comparison; it is not itself an application write.
            generation = self.changes.mark()

    def tick(self):
        """Yield each page while its ownership and delivery lock is held."""
        if len(self.leases) != len(self.lease_paths):
            return
        self.watched = self.pages()
        for page_dir in self.watched:
            # This is only the account returned if ownership is already gone.
            # Every act uses the current reading under the lock below. Keeping
            # the harmless observation outside makes the lock boundary itself
            # testable: a claim or SessionEnd can win after page selection,
            # and _read must then decline every stale act.
            observed = read_status(page_dir)
            try:
                with PageTransaction(page_dir) as page:
                    reading, revive = self._read(page, observed)
                    if not revive:
                        yield reading
                        continue
            except FileNotFoundError:
                # Discovery can race deletion; a missing marker is no page.
                continue

            try:
                from .hosting import start_server

                started = start_server(page_dir, revive=True, harness=self.harness)
            except StartRefused as error:
                note(
                    Finding(
                        "revive-refused",
                        values={"page": str(page_dir), "error": str(error)},
                        severity="advice",
                    )
                )
                started = None
            key = str(page_dir)
            if started:
                self._revived.add(key)
                self._lost.discard(key)
            else:
                self._lost.add(key)

            # Ownership or status may have changed while the service transition
            # ran. Only this second transactional reading may be delivered.
            try:
                with PageTransaction(page_dir) as page:
                    reading, _ = self._read(page, observed)
                    if (
                        started
                        and reading.watch_state == "watching"
                        and reading.live
                        and not reading.lost
                    ):
                        reading = reading._replace(restarted=started.url)
                    yield reading
            except FileNotFoundError:
                continue

    def _read(self, page: PageTransaction, observed: dict) -> tuple[PageTick, bool]:
        """Read one page transaction and say whether revival is due."""
        page_dir = page.page_dir
        watch_state = page.watch_state(self.harness)
        status = observed if watch_state == "lost" else page.status
        live = status["state"] != "idle"
        from .delivery import deliverable

        batch = deliverable(page) if watch_state != "lost" else []
        service = read_service(page_dir)
        enabled = bool(service and service["enabled"])
        key, now, revive = str(page_dir), time.time(), False
        # Desired service state owns revival. Status says what the page is doing;
        # it does not turn a disabled service back on, and a disabled one is not
        # lost either: whoever stopped it may start it again.
        if watch_state == "watching" and live and service is None:
            self._lost.add(key)
        elif watch_state == "watching" and live and not enabled:
            self._lost.discard(key)
            self._revived.discard(key)
        elif watch_state == "watching" and live and now > self._check_at.get(key, 0):
            self._check_at[key] = now + REVIVAL_CHECK_S
            if running_server(page_dir):
                # A server seen running earns the next death its own revival —
                # one attempt per death, so a server dying on arrival still
                # can't respawn every five seconds.
                self._revived.discard(key)
                self._lost.discard(key)
            elif key in self._revived:
                self._lost.add(key)
            else:
                revive = True
        elif watch_state != "watching" or not live:
            self._lost.discard(key)
            self._revived.discard(key)
        return (
            PageTick(
                page_dir,
                status,
                batch,
                live,
                watch_state,
                key in self._lost,
                None,
                page,
            ),
            revive,
        )

    def release(self) -> None:
        """Release this watcher's liveness proof, however it ended."""
        for lease in self.leases:
            release_lease(lease)
        self.leases.clear()
        if self.changes is not None:
            self.changes.close()
            self.changes = None


def _page_reading_or_none(page_dir: Path) -> str | None:
    """A page's reading, or None once its directory is gone."""
    try:
        return page_reading(page_dir)
    except (FileNotFoundError, NotADirectoryError):
        return None


@dataclass(frozen=True)
class _WatchPass[DeliveryResult]:
    """What one complete pass observed, or the outcome that ended it early."""

    readings: list[PageTick]
    live: list[PageTick]
    outcome: int | None
    delivered: DeliveryResult | None = None


def wait_acknowledgement(harness: Harness | None) -> Callable[[str], str]:
    """What a `leaf wait` delivery tells its reader about acknowledging it.

    Printing is not receipt, so the reader of the wait confirms it, in the way its
    harness runs the next wait. It is stated once for the delivery, ahead of the
    batches, where output cut off partway still shows it."""
    run_ack = (harness or Harness).run_ack

    def acknowledge(delivery_id: str) -> str:
        return (
            "Whoever ran the `leaf wait` that printed this delivery acknowledges "
            "it; until then the user's updates read Sent rather than Picked up. If "
            f"the output was cut off, reread it with `leaf delivery read {delivery_id}`. "
            "Follow any `next` commands before confirming. If you handle it, "
            "acknowledge before any other "
            "work; if you forward it, acknowledge once it durably arrives there. To "
            f"acknowledge, {run_ack(delivery_id)}: it confirms this delivery and "
            "waits for the next."
        )

    return acknowledge


def delivery_json(reading: PageTick, harness: Harness | None) -> str:
    """Freeze a watcher reading and present its bounded first part."""
    from .delivery import batch_data, delivery_reading, freeze_delivery

    payload = freeze_delivery(
        [batch_data(reading.page_dir, reading.transaction, reading.batch)],
        acknowledge=wait_acknowledgement(harness),
    )
    return json.dumps(delivery_reading(payload), indent=2, ensure_ascii=False)


def read_watch_pass[DeliveryResult](
    watch: Watch,
    named: Path | None,
    deliver: Callable[[PageTick], DeliveryResult],
    ready: Callable[[PageTick], bool] = lambda reading: True,
) -> _WatchPass[DeliveryResult]:
    """Read pages until this pass completes or one page ends the wait. A batch
    the watch is not `ready` to hand over waits for a later pass."""
    readings = []
    live = []
    for reading in watch.tick():
        readings.append(reading)
        if reading.watch_state == "lost":
            if named is not None and paths_same(reading.page_dir, named):
                note(Finding("not-owned", values={"pages": [str(named)]}))
                return _WatchPass(readings, live, 2)
            continue
        if reading.live and not reading.lost:
            live.append(reading)
        if reading.restarted:
            note(
                Finding(
                    "server-restarted",
                    values={"page": str(reading.page_dir), "url": reading.restarted},
                    severity="advice",
                )
            )
        # A batch outranks the page's state: a wait already holding events owes
        # them to the agent whatever became of the leaf, so an idled page still
        # delivers here — it just no longer holds the wait open below.
        if reading.batch and ready(reading):
            return _WatchPass(readings, live, 0, deliver(reading))
        if reading.lost:
            # A session-wide watcher still serves its other leaves. Treat the
            # unavailable page as fatal only when it is the named watch, or when
            # the completed pass finds no live page left to carry.
            if named is None or not paths_same(reading.page_dir, named):
                continue
            note(_server_down(reading))
            return _WatchPass(readings, live, 2)
    lost = [reading for reading in readings if reading.lost]
    if lost and not live:
        note(*map(_server_down, lost))
        return _WatchPass(readings, live, 2)
    return _WatchPass(readings, live, None)


def _server_down(reading: PageTick) -> Finding:
    return Finding("server-down", values={"page": str(reading.page_dir)})


def _ended_watch(readings: list[PageTick], page_dir: Path | None) -> int:
    """Explain why a pass with no live pages has nowhere left to wait."""
    held = [
        str(reading.page_dir) for reading in readings if reading.watch_state != "lost"
    ]
    if not held:
        if transferred := [
            str(reading.page_dir)
            for reading in readings
            if reading.watch_state == "lost"
        ]:
            note(Finding("not-owned", values={"pages": transferred}))
        else:
            page = str(page_dir) if page_dir is not None else None
            note(Finding("nothing-to-watch", values={"page": page}))
        return 2
    note(Finding("pages-idle", values={"pages": held}, severity="advice"))
    return 2


def new_input_line(page_dir: Path) -> str:
    """What a watch says on finding input where the harness's prompt hook carries it
    into the turn: it only wakes the session."""
    return (
        f"{page_dir} has new input; Leaf's prompt hook puts it in your context with "
        "this notification"
    )


def cmd_wait(page_dir: Path | None = None, *, ack: str | None = None) -> int:
    """Confirm a complete delivery, if given, then watch for the next batch.

    A named wait observes that page without taking ownership. A receipt resumes
    the session's current ownership set. A
    standalone consumer watches the pages its delivery names. Exit 0 carries
    the next immutable delivery; exit 2 names why the watch ended. A refused
    receipt raises before a watch starts, leaving that page's cursor unchanged.
    """
    received = []
    if ack is not None:
        from .delivery import receive_delivery

        received = receive_delivery(ack)
    harness = session_harness()
    explicit = (page_dir,) if page_dir else tuple(received) if harness is None else ()
    named = explicit[0] if len(explicit) == 1 else None
    watch = Watch(harness, pages=explicit)
    if not watch.acquire():
        target = "this session" if harness else ", ".join(map(str, explicit))
        note(Finding("wait-active", values={"target": target}))
        return 2

    def print_delivery(reading: PageTick) -> bool:
        """Print immutable input; only the consumer can confirm receipt.

        An explicit wait is a complete delivery route. Earlier successful hooks
        cannot prove that a later one will run, so it never delegates its input
        to the next hook. The native between-turn watch owns hook wakes, and a
        wait it has superseded prints nothing, since that watch carries the input.
        """
        if not watch.holds():
            return False
        print(delivery_json(reading, harness), flush=True)
        return True

    try:
        while watch.holds():
            mark = watch.mark()
            reading = read_watch_pass(watch, named, print_delivery)
            if reading.delivered is False:
                break
            if reading.outcome is not None:
                return reading.outcome
            if not reading.live:
                return _ended_watch(reading.readings, named)
            watch.await_news(mark)
        note(Finding("watch-taken-over"))
        return 2
    finally:
        watch.release()


def wake_inputs(page: PageTransaction, batch: list[dict]) -> list[dict]:
    """Select what can wake a hook without changing its immutable receipt batch.

    A settled thread input has already had its meaning answered, even when its
    delivery was never received. Unsettled inputs read their existing canonical
    workflow. A completed receipt advances the cursor, so handed input is already
    absent from this unreceived batch. An opened record without the completed
    cursor write does not prove delivery. Other admitted attention (including
    reports, errors, reactions and widget actions) remains
    transport input, independent of whether it carries a response obligation.
    """
    from .served_state.context import read_page

    agent_inputs = {
        item["input"]
        for item in read_page(page.page_dir, page.events).work.durable.workflows
        if item["next_actor"] == "agent"
    }
    pending = []
    for event in batch:
        if event["kind"] in MESSAGE_KINDS and event["id"] not in agent_inputs:
            continue
        pending.append(event)
    return pending


def watch_between_turns(harness: Harness, *, interrupted: bool = False) -> str | None:
    """Wake for meaningful unreceived input, without treating a log look as pickup.

    A normal watch gives the concurrent Stop hook its bounded opportunity to
    carry input already present at startup. The turn's closing ends that grace;
    input arriving while the watch runs wakes immediately. A watch after Escape
    trusts the receipt cursor: input held outside the stopped turn's context can
    wake, while that turn's received input waits for a prompt.
    Settled thread input alone never wakes; it remains in the next receipt batch.
    The session lease and each page transaction retain ownership of delivery,
    revival and competing-watch decisions. The newest watch takes the lease from
    any holder, and a watch superseded that way ends without a word: the newest
    runs the Leaf its harness runs now, while an older one may run a Leaf the
    session has since left, one that cannot read a page the session now holds.
    """
    # Event timestamps have millisecond precision. Include the startup millisecond
    # in immediate delivery rather than delaying an arrival in that millisecond.
    began = int(time.time() * 1000) / 1000
    settled = time.monotonic() + STOP_HOOK_S
    watch = Watch(harness)
    watch.acquire(supersede=True)

    def ready(reading: PageTick) -> bool:
        pending = wake_inputs(reading.transaction, reading.batch)
        if not pending:
            return False
        if interrupted:
            return True
        claim = reading.transaction.active_claim
        return (
            (claim is not None and claim["turn_closed"] is not None)
            or any(
                datetime.fromisoformat(event["ts"]).timestamp() >= began
                for event in pending
            )
            or time.monotonic() > settled
        )

    try:
        while harness.process_runs():
            mark = watch.mark()
            reading = read_watch_pass(watch, None, lambda tick: tick.page_dir, ready)
            # Superseded during the pass, it leaves what it found to its successor.
            if not watch.holds():
                return None
            if reading.delivered is not None:
                return new_input_line(reading.delivered)
            if reading.outcome is not None:
                return "\n".join(
                    f"{tick.page_dir}: server is not running; restart it with "
                    f"`leaf server start {tick.page_dir}`"
                    for tick in reading.readings
                    if tick.lost
                )
            if not reading.live:
                return None
            watch.await_news(mark)
    finally:
        watch.release()
    from .delivery import deliverable

    # Input admitted while this watch held the lease was not nudged, so now the
    # lease is gone, any such input is nudged as admission would have.
    for page_dir in owned_pages(harness.session):
        with contextlib.suppress(FileNotFoundError), PageTransaction(page_dir) as page:
            if wake_inputs(page, deliverable(page)):
                nudge_unwatched(page)
    return None
