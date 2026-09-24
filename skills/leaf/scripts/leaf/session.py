"""Agent status, waiting, and acknowledgement policy."""

import json
import secrets
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from .activity import unanswered
from .delivery import (
    batch_data,
    freeze_delivery,
    read_delivery,
    receive_batch,
    record_pickup,
)
from .detached import StartRefused
from .files import file_stamp, next_reading, read_json
from .host import Harness, session_harness
from .hosting import start_server
from .leases import take_lease, waiter_lease_path
from .locations import path_location, paths_same
from .machine import state_home
from .revisioning import activate_source
from .schema import (
    ANSWER_ASK_INSTRUCTION,
    SERVICE_FILE,
    STATUS_FILE,
)
from .served_state.page import full_state
from .served_state.reading import page_reading
from .server import running_server
from .service import (
    PageTransaction,
    claim_page,
    open_session_turn,
    owned_pages,
    unacknowledged,
)
from .work import standing_work_claims, work_subject

DELIVERY_CLAIM_DETAIL = "Reading your feedback"

# How often a watch rechecks a live page's server. It is also the longest a watch goes
# without a pass on a page whose files have not moved: nothing else a pass reads
# changes on the clock alone.
REVIVAL_CHECK_S = 5


def check_local_claim(state: str, detail: str) -> None:
    """What a local claim needs before it can name a subject.

    A local claim says "I am on this now", so the two other states have nothing
    to put there: `waiting` is the user's move, and `idle` is the end of the
    agent's side. Its own function because `idle` takes a different route to the
    same status write, and a claim admitted on one route and refused on the other
    would be reported to the agent as written either way.
    """
    if state != "working":
        sys.exit("--on says what you are working on; use it with `working`")
    if not detail:
        sys.exit("--on needs a detail; a Working receipt with no words says nothing")


def cmd_status(
    page_dir: Path,
    state: str,
    detail: str,
    on: str | None = None,
) -> list[dict]:
    """Write the declaration and return the user moves still owed an answer,
    which the page goes on showing over a `waiting` written ahead of them."""
    with PageTransaction(page_dir) as page:
        activate_source(page_dir)
        work = None
        if on is not None:
            check_local_claim(state, detail)
            work = work_subject(page_dir, page.events, on)
            previous = next(
                (
                    claim
                    for claim in standing_work_claims(page.status, page.events)
                    if claim["subject"] == work["subject"]
                ),
                None,
            )
            if previous and previous.get("event"):
                work["event"] = previous["event"]
        page.set_status(state, detail, work=work)
        return full_state(page_dir, page.events)["activity"]["obligations"]


def cmd_delivery_claim(
    delivery_id: str,
    detail: str | None = None,
    event_id: str | None = None,
) -> str:
    """Mark one exact, still-outstanding move from a delivery as Working.

    The immutable delivery supplies the page and candidate event identities. The
    page transaction re-derives its unsettled workflows and writes the claim
    under the same log lock, so a stale delivery cannot attach work to a newer
    move merely because both belong to the same thread or widget.
    """
    # No detail is Leaf speaking for the agent, so the user hears something the
    # moment their move is taken up. An agent that supplies one has said it itself,
    # whatever words it chose.
    stated = detail is not None
    detail = detail if stated else DELIVERY_CLAIM_DETAIL
    delivery = read_delivery(delivery_id)
    candidates = []
    for batch in delivery["batches"]:
        events = [
            event
            for event in batch["events"]
            if event_id is None or event["id"] == event_id
        ]
        if events:
            candidates.append((Path(batch["page"]), events))
    if event_id is not None and not candidates:
        sys.exit(f"event {event_id!r} is not in delivery {delivery_id!r}")
    if event_id is not None and len({page for page, _events in candidates}) > 1:
        sys.exit(
            f"event {event_id!r} occurs on more than one page in delivery "
            f"{delivery_id!r}"
        )

    for page_dir, delivered_events in candidates:
        with PageTransaction(page_dir) as page:
            state = full_state(
                page_dir,
                page.events,
                stored_status=page.status,
            )
            workflows = {
                item.get("input"): item
                for item in state["workflows"]
                if item["answer"] is not None or item["subject"]["kind"] == "widget"
            }
            event = next(
                (
                    delivered
                    for delivered in delivered_events
                    if delivered["id"] in workflows
                ),
                None,
            )
            workflow = workflows.get(event["id"]) if event is not None else None
            if workflow is None:
                continue
            target = workflow["subject"]
            handling = {
                "target": target,
                "event": event["id"],
                "after": page.events[-1]["seq"] if page.events else 0,
            }
            if target["kind"] == "widget":
                handling["revision"] = workflow.get("revision")
            page.set_status("working", detail, handling=handling, stated=stated)
            return (
                f"working on {target['kind']} {target['id']} for event "
                f"{event['id']} — {detail}"
            )

    selected = f" event {event_id}" if event_id is not None else ""
    return f"no outstanding user move{selected} in delivery {delivery_id}"


def cmd_idle(page_dir: Path, detail: str, on: str | None) -> None:
    """Idle, unless the page still owes its user an answer.

    Idling over an event nobody has answered ends the leaf on a user still
    owed one — unread, or read and left. The watcher's whole batch, not the
    user-facing count, so a worker's report cannot be left standing as
    provisional state forever either. The check and the transition share the
    log lock, so an event arriving or an acknowledgement advancing the cursor
    orders against them."""
    # Ahead of the transaction, which reaches `set_status` without a subject:
    # refused here, `idle --on` cannot be reported back as a claim the page
    # never took.
    if on is not None:
        check_local_claim("idle", detail)
    with PageTransaction(page_dir) as page:
        events = page.events
        cursor = page.cursor
        pending = len(unacknowledged(events, cursor))
        if pending:
            sys.exit(
                f"{pending} update{'s' if pending != 1 else ''} nobody has picked up; "
                "read them with `leaf wait` before idling"
            )
        owed = [
            obligation
            for obligation in full_state(page_dir, events)["activity"]["obligations"]
            if obligation["seq"] <= cursor
        ]
        if owed:
            sys.exit(
                f"{unanswered(owed, 'acknowledged')}; answer before idling. "
                + ANSWER_ASK_INSTRUCTION
            )
        page.set_status("idle", detail)


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
    down with no restart left to make.

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
            # Each wait writes its own start over the last one's, so a reader can
            # tell this wait from the one before it on the same lease
            # (`leases.started_wait`).
            lease.truncate(0)
            lease.write(secrets.token_hex(8).encode())
            lease.flush()
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
        return (file_stamp(self.claims), *map(_page_stamp, self.watched))

    def mark(self) -> tuple:
        """What the next pass starts from, taken before it reads, so a write that
        lands during the pass moves the stamps `await_news` compares against."""
        return (list(self.watched), self.reading())

    def await_news(self, mark: tuple, timeout: float = REVIVAL_CHECK_S) -> None:
        """Return once anything the pass since `mark` read has moved, or after
        `timeout` with nothing moved. A pass that found a different set of pages
        returns at once: `mark` stamped the old set."""
        watched, before = mark
        if self.watched == watched:
            next_reading(self.reading, before, timeout=timeout)

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
            observed = read_json(page_dir / STATUS_FILE)
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
                started = start_server(page_dir, revive=True)
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
                        reading = reading._replace(restarted=started[0])
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
        # it does not turn a deliberately disabled service back on.
        if watch_state == "watching" and live and not enabled:
            self._lost.add(key)
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
            lease.close()
        self.leases.clear()


def _page_stamp(page_dir: Path) -> str | None:
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
) -> _WatchPass:
    """Read pages until this pass completes or one page ends the wait."""
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
        if reading.batch:
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


def receive_delivery(delivery_id: str) -> list[Path]:
    """Confirm complete input and record its entry into this consumer's turn.

    Each page uses its own transaction. Interrupted multi-page receipt can be
    retried against the same immutable bounds; no receipt transfers ownership.
    Sibling turns open after releasing the page locks, so concurrent receipts
    never nest transactions across pages. Printing cannot confirm receipt.
    """
    payload = read_delivery(delivery_id)
    harness = session_harness()
    session_id = harness.session if harness else None
    pages = []
    for batch in payload["batches"]:
        page_dir = Path(batch["page"])
        with (
            PageTransaction(page_dir) as page,
            receive_batch(page, batch, session_id=session_id) as events,
        ):
            turn = page.open_turn(session_id) if session_id else None
            record_pickup(page, events, session=session_id, turn=turn)
        pages.append(page_dir)
    if session_id:
        open_session_turn(session_id)
    return pages


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
    received = receive_delivery(ack) if ack is not None else []
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
        """Print immutable input; only the consumer can confirm receipt."""
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
