"""Agent status and the `leaf wait` watch.

A watch discovers its pages before loading delivery or page projections, and
loads the HTTP server only to revive a dead one. Status writes use those same
projections without importing a server. Receipt remains `delivery`'s."""

import contextlib
import json
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from .detached import StartRefused
from .event_log import read_events
from .files import file_stamp, next_reading, read_json
from .harness import Harness, claim_harness, session_harness
from .leases import release_lease, take_lease, waiter_lease_path
from .locations import path_location, paths_same
from .machine import state_home
from .schema import (
    ANSWER_ASK_INSTRUCTION,
    SERVICE_FILE,
)
from .served_state.reading import page_reading
from .server import running_server
from .service import (
    PageTransaction,
    claim_page,
    owned_pages,
    read_status,
    requires_agent_attention,
    unacknowledged,
)

# How often a watch rechecks a live page's server. It is also the longest a watch goes
# without a pass on a page whose files have not moved: nothing else a pass reads
# changes on the clock alone.
REVIVAL_CHECK_S = 5

# How long a turn-end watch holds input that was already pending as the turn ended:
# the Stop hook running beside it hands such input to the turn it continues, and
# this is that hook's timeout (`hooks/hooks.json`).
STOP_HOOK_S = 20


def cmd_waiting(page_dir: Path, detail: str) -> tuple[dict, list[dict]]:
    """Declare the page waiting on its user, putting down every start that stands
    (`tasks.put_down`), and return the declaration, with the user moves still owed an
    answer, which the page goes on showing over it."""
    from .revisioning import activate_source
    from .served_state.page import full_state
    from .tasks import put_down

    with PageTransaction(page_dir) as page:
        activate_source(page_dir, transaction=page)
        put_down(page)
        status = page.set_status("waiting", detail)
        return status, full_state(page_dir, page.events)["activity"]["obligations"]


def cmd_idle(page_dir: Path, detail: str) -> dict:
    """Idle, putting down every start that stands, unless the page still owes its
    user an answer.

    Idling over an event nobody has answered ends the leaf on a user still
    owed one — unread, or read and left. The watcher's whole batch, not the
    user-facing count, so a worker's report cannot be left standing as
    provisional state forever either. The answers it holds the page for are
    `activity.blocking_obligations`, a started move's included: the Stop hook lets
    the turn that started one end over it, but closing the page answers nothing. It
    holds the page for every open task too, which only its ending discharges.
    The check and the transition share the log lock, so an event arriving
    or an acknowledgement advancing the cursor orders against them."""
    from .activity import blocking_obligations, unanswered
    from .served_state.page import full_state
    from .tasks import owed_tasks, put_down

    with PageTransaction(page_dir) as page:
        events = page.events
        state = full_state(page_dir, events)
        claim = page.active_claim
        harness = claim_harness(claim) if claim is not None else None
        pending = len(unacknowledged(events, page.cursor))
        if pending:
            remedy = (
                harness.input_unpicked(page_dir, listening=state["listening"])
                if harness
                else "`leaf wait` prints them."
            )
            sys.exit(
                f"{pending} update{'s' if pending != 1 else ''} nobody has picked up, "
                f"so the page cannot idle yet. {remedy}"
            )
        owed = blocking_obligations(
            state,
            carried=harness is not None
            and harness.carrier_live(listening=state["listening"]),
        )
        if owed:
            sys.exit(
                f"{unanswered(owed, 'acknowledged')}; answer before idling. "
                + ANSWER_ASK_INSTRUCTION
            )
        # A task is work the agent still owes, which closing the page would leave
        # standing on a page nobody holds.
        if tasks := owed_tasks(events):
            named = "; ".join(f"{task['id']} ({task['title']})" for task in tasks)
            sys.exit(
                f"{len(tasks)} open task{'s' if len(tasks) != 1 else ''}: {named}. "
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
    the agent's own move, and `page init` stops a served page to re-vendor it and
    starts it again, so the wait watches a disabled service without reviving it.

    Between passes the watch follows `reading`, the stamps of what a pass reads:
    the machine's claims, which say which pages the session holds, and each page a
    pass found. A pass runs when one moves, so an event reaches the watch in a look
    (`LOOK_S`) rather than on a timer, and a quiet page costs stat calls rather than
    a locked read of its whole log.
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
        self.claims = state_home() / "claims"
        self.watched: list[Path] = []

    def acquire(self) -> bool:
        """Hold the session lease, or every explicitly watched standalone page."""
        if self.leases:
            return True
        for path in self.lease_paths:
            lease = take_lease(path)
            if lease is None:
                self.release()
                return False
            self.leases.append(lease)
        return True

    def pages(self) -> list:
        """Read the current ownership set and include explicitly named pages."""
        watched = owned_pages(self.session_id) if self.harness is not None else []
        locations = {path_location(page) for page in watched}
        for page in self.explicit_pages:
            if path_location(page) not in locations:
                watched.append(page)
                locations.add(path_location(page))
        return watched

    def reading(self) -> tuple:
        """The stamps of everything the last pass read: the claims, and its pages."""
        return (file_stamp(self.claims), *map(_page_reading_or_none, self.watched))

    def mark(self) -> tuple:
        """What the next pass starts from, taken before it reads, so a write that
        lands during the pass moves the stamps `await_news` compares against."""
        return (list(self.watched), self.reading())

    def await_news(self, mark: tuple, timeout: float = REVIVAL_CHECK_S) -> bool:
        """Return True once anything the pass since `mark` read has moved, or False
        after `timeout` with nothing moved. A pass that found a different set of
        pages returns True at once: `mark` stamped the old set."""
        watched, before = mark
        if self.watched != watched:
            return True
        return next_reading(self.reading, before, timeout=timeout) != before

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
                print(error, file=sys.stderr)
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
        batch = (
            unacknowledged(page.events, page.cursor) if watch_state != "lost" else []
        )
        service = read_json(page_dir / SERVICE_FILE)
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
        """Release this carrier's liveness proof, however it ended."""
        for lease in self.leases:
            release_lease(lease)
        self.leases.clear()


def _page_reading_or_none(page_dir: Path) -> str | None:
    """A page's reading, or None once its directory is gone."""
    try:
        return page_reading(page_dir)
    except (FileNotFoundError, NotADirectoryError):
        return None


class _WatchPass(NamedTuple):
    """What one complete pass observed, or the outcome that ended it early."""

    readings: list[PageTick]
    live: list[PageTick]
    outcome: int | None


def wait_acknowledgement(harness: Harness | None) -> Callable[[str], str]:
    """What a `leaf wait` delivery tells its reader about acknowledging it.

    Printing is not receipt, so the reader of the wait confirms it, in the way its
    harness runs the next wait. It is stated once for the delivery, ahead of the
    batches, where output cut off partway still shows it."""
    run_ack = (harness or Harness).run_ack

    def acknowledge(delivery_id: str) -> str:
        return (
            "Whoever ran the `leaf wait` that printed this delivery acknowledges "
            "it; until then the user's moves read Sent rather than Picked up. If "
            "the output was cut off, acknowledge nothing and rerun the wait with room "
            "for the whole envelope. If you handle it, acknowledge before any other "
            "work; if you forward it, acknowledge once it durably arrives there. To "
            f"acknowledge, {run_ack(delivery_id)}: it confirms this delivery and "
            "waits for the next."
        )

    return acknowledge


def delivery_json(reading: PageTick, harness: Harness | None) -> str:
    """Freeze and serialize a watcher reading as one delivery envelope."""
    from .delivery import batch_data, freeze_delivery

    payload = freeze_delivery(
        [batch_data(reading.page_dir, reading.transaction, reading.batch)],
        carrier="wait",
        acknowledge=wait_acknowledgement(harness),
    )
    return json.dumps(payload, ensure_ascii=False)


def read_watch_pass(
    watch: Watch,
    named: Path | None,
    deliver: Callable[[PageTick], None],
    ready: Callable[[PageTick], bool] = lambda reading: True,
) -> _WatchPass:
    """Read pages until this pass completes or one page ends the wait. A batch
    the watch is not `ready` to hand over waits for a later pass."""
    readings = []
    live = []
    for reading in watch.tick():
        readings.append(reading)
        if reading.watch_state == "lost":
            if named is not None and paths_same(reading.page_dir, named):
                print(
                    f"stopped watching {named}: this session no longer owns it",
                    file=sys.stderr,
                )
                return _WatchPass(readings, live, 2)
            continue
        if reading.live and not reading.lost:
            live.append(reading)
        if reading.restarted:
            print(
                f"{reading.page_dir}: server had died; "
                f"restarted at {reading.restarted}",
                file=sys.stderr,
                flush=True,
            )
        # A batch outranks the page's state: a wait already holding events owes
        # them to the agent whatever became of the leaf, so an idled page still
        # delivers here — it just no longer holds the wait open below.
        if reading.batch and ready(reading):
            deliver(reading)
            return _WatchPass(readings, live, 0)
        if reading.lost:
            # A session-wide carrier still serves its other leaves. Treat the
            # unavailable page as fatal only when it is the named watch, or when
            # the completed pass finds no live page left to carry.
            if named is None or not paths_same(reading.page_dir, named):
                continue
            print(
                f"{reading.page_dir}: server is not running; restart it with "
                f"`leaf server start {reading.page_dir}`",
                file=sys.stderr,
            )
            return _WatchPass(readings, live, 2)
    lost = [reading for reading in readings if reading.lost]
    if lost and not live:
        for reading in lost:
            print(
                f"{reading.page_dir}: server is not running; restart it with "
                f"`leaf server start {reading.page_dir}`",
                file=sys.stderr,
            )
        return _WatchPass(readings, live, 2)
    return _WatchPass(readings, live, None)


def _ended_watch(readings: list[PageTick], page_dir: Path | None) -> int:
    """Explain why a pass with no live pages has nowhere left to wait."""
    held = [reading for reading in readings if reading.watch_state != "lost"]
    if not held:
        transferred = [reading for reading in readings if reading.watch_state == "lost"]
        if transferred:
            one = len(transferred) == 1
            names = ", ".join(str(reading.page_dir) for reading in transferred)
            print(
                f"stopped watching {names}: this session no longer owns "
                f"{'it' if one else 'them'}",
                file=sys.stderr,
            )
            return 2
        if page_dir is None:
            print(
                "nothing to watch: no page named and none claimed by this session",
                file=sys.stderr,
            )
        else:
            print(
                f"nothing to watch: {page_dir} is not claimed by this session",
                file=sys.stderr,
            )
        return 2
    one = len(held) == 1
    names = ", ".join(str(reading.page_dir) for reading in held)
    print(
        f"the {'leaf' if one else 'leaves'} ended; {names} "
        f"{'is' if one else 'are'} idle",
        file=sys.stderr,
    )
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

    A named initial wait claims that page. A receipt resumes the session's
    current ownership set without taking any page back from a successor. A
    standalone consumer watches the pages its delivery names. Exit 0 carries
    the next immutable delivery; exit 2 names why the watch ended. A refused
    receipt raises before a watch starts, leaving that page's cursor unchanged.
    """
    if page_dir is not None and ack is not None:
        raise ValueError("PAGE and --ack cannot be used together")
    received = []
    if ack is not None:
        from .delivery import receive_delivery

        received = receive_delivery(ack)
    if page_dir is not None:
        claim_page(page_dir)
    harness = session_harness()
    explicit = (page_dir,) if page_dir else tuple(received) if harness is None else ()
    named = explicit[0] if len(explicit) == 1 else None
    watch = Watch(harness, pages=explicit)
    if not watch.acquire():
        target = "this session" if harness else ", ".join(map(str, explicit))
        print(f"another `leaf wait` is already active for {target}", file=sys.stderr)
        return 2

    def print_delivery(reading: PageTick) -> None:
        """Print immutable input; only the consumer can confirm receipt. Where the
        harness's hook carries input into the turn, the wait only wakes it."""
        if harness and harness.hooks_carry():
            print(new_input_line(reading.page_dir), flush=True)
        else:
            print(delivery_json(reading, harness), flush=True)

    try:
        while True:
            mark = watch.mark()
            reading = read_watch_pass(watch, named, print_delivery)
            if reading.outcome is not None:
                return reading.outcome
            if not reading.live:
                return _ended_watch(reading.readings, named)
            watch.await_news(mark)
    finally:
        watch.release()


def _log_end(page_dir: Path) -> int:
    """The last sequence number in a page's log, or 0 for an empty or gone log."""
    with contextlib.suppress(FileNotFoundError):
        return max((event["seq"] for event in read_events(page_dir)), default=0)
    return 0


def watch_between_turns(harness: Harness, *, interrupted: bool = False) -> str | None:
    """The session's watch run by the harness's own Stop hook, which the harness starts
    in the background as each turn ends (`Harness.watches_between_turns`), and
    what it wakes the session with, or None where it ends without waking it.

    It wakes the session for a page with new input, which the prompt hook then
    hands over as the turn the wake opens begins, and for live pages none of whose
    servers can be brought back. It ends silently where another watch already
    holds the session's lease, no page is left to watch, or the harness process that
    started it has gone (`Harness.process_runs`), leaving the session's input to its
    `nudge`.

    Input that was already pending as the turn ended waits for the Stop hook
    beside this one, which hands it to the turn it continues. It is the wake's to
    carry only once that hook let the turn end over it, or failed to answer within
    its own timeout. Input arriving later wakes the session at once, between two
    turns or within one, where it reaches the turn at its next tool result.

    A watch started as the user interrupted the turn wakes only for that later
    input: the turn the pending input was handed to is the one the user stopped,
    and their next prompt carries it. Input admitted between the interruption and
    the watch's first look at the log waits for that prompt too, since nothing
    records what the stopped turn was handed."""
    watch = Watch(harness)
    if not watch.acquire():
        return None
    # Where each page's log stood as the watch first saw it, and when the Stop
    # hook's answer over what was pending then is due: an event past that point
    # arrived since. A page claimed while the watch runs is first seen then.
    began: dict[Path, tuple[int, float]] = {}

    def first_sight(page_dir: Path, end: int) -> tuple[int, float]:
        return began.setdefault(page_dir, (end, time.monotonic() + STOP_HOOK_S))

    for page_dir in owned_pages(harness.session):
        first_sight(page_dir, _log_end(page_dir))
    woke = []

    def ready(reading: PageTick) -> bool:
        claim = reading.transaction.active_claim
        last = reading.batch[-1]["seq"]
        end, settled = first_sight(reading.page_dir, last)
        if interrupted:
            return last > end
        return (
            (claim is not None and claim.get("turn_closed") is not None)
            or last > end
            or time.monotonic() > settled
        )

    try:
        while harness.process_runs():
            mark = watch.mark()
            reading = read_watch_pass(
                watch, None, lambda tick: woke.append(tick.page_dir), ready
            )
            for tick in reading.readings:
                if tick.page_dir not in began:
                    first_sight(tick.page_dir, _log_end(tick.page_dir))
            if woke:
                return new_input_line(woke[0])
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
    # Input admitted while this watch held the lease was not nudged, so now the
    # lease is gone, any such input is nudged as admission would have.
    for page_dir in owned_pages(harness.session):
        with contextlib.suppress(FileNotFoundError), PageTransaction(page_dir) as page:
            if any(
                requires_agent_attention(event)
                for event in unacknowledged(page.events, page.cursor)
            ):
                from .event_endpoint import nudge_unwatched

                nudge_unwatched(page)
    return None
