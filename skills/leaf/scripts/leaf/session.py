"""Agent status, waiting, and acknowledgement policy."""

import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from .event_log import jsonl_line
from .files import read_json, write_json
from .host import host_identity
from .hosting import start_server
from .leases import take_waiter_lease, waiter_lease_path
from .locations import path_location, paths_same
from .passages import active_enclosing
from .registry.contract import RegistryError, handling
from .registry.reactions import described
from .registry.storage import load_registry
from .revisioning import activate_source
from .server import running_server
from .service import (
    PageTransaction,
    claim_page,
    open_session_turn,
    owned_pages,
    unacknowledged,
)
from .thread_context import batch_threads
from .work import work_subject


def check_local_claim(state: str, detail: str) -> None:
    """What a local claim needs before it can name a subject.

    A local claim says "I am on this now", so the two other states have nothing
    to put there: `waiting` is the reader's move, and `idle` is the end of the
    agent's side. Its own function because `idle` takes a different route to the
    same status write, and a claim admitted on one route and refused on the other
    would be reported to the agent as written either way.
    """
    if state != "working":
        sys.exit("--on says what you are working on; use it with `working`")
    if not detail:
        sys.exit("--on needs a detail; an Active receipt with no words says nothing")


def cmd_status(
    page_dir: Path,
    state: str,
    detail: str,
    on: str | None = None,
) -> None:
    with PageTransaction(page_dir) as page:
        activate_source(page_dir, page.events)
        work = None
        if on is not None:
            check_local_claim(state, detail)
            work = work_subject(page_dir, page.events, on)
        page.set_status(state, detail, work=work)


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
    SessionEnd, event arrival, delivery, and pickup recording have one order.
    A revival releases that transaction before waiting for the service
    transition, then rereads under a new transaction; no delivery snapshot
    crosses that unlocked interval.
    `watch_state` is ownership/lifetime; `lost` separately says the server is
    down with no restart left to make.
    """

    def __init__(self, identity: dict | None, named: Path | None = None):
        self.identity = identity
        self.session_id = identity["id"] if identity else None
        self.named = named
        self.lease_path = waiter_lease_path(named, identity)
        self.lease = None
        self._revived: set = set()
        self._lost: set = set()
        self._check_at: dict = {}

    def acquire(self) -> bool:
        """Take this carrier's exact liveness lease, idempotently."""
        if self.lease is not None or self.lease_path is None:
            return True
        self.lease = take_waiter_lease(self.lease_path)
        return self.lease is not None

    def pages(self) -> list:
        """Every page this session holds, re-read each pass, so a page served
        mid-watch joins it and a page another session picked up drops out.
        Naming one holds it in the set whatever the registry says — how a
        session picks up a leaf it didn't serve. A bare shell has no implicit
        ownership set, so it watches only a page explicitly named."""
        watched = owned_pages(self.session_id) if self.identity is not None else []
        named_at = None if self.named is None else path_location(self.named)
        if named_at is not None and not any(
            path_location(d) == named_at for d in watched
        ):
            watched.append(self.named)
        return watched

    def tick(self):
        """Yield each page while its ownership and delivery lock is held."""
        if self.lease_path is not None and self.lease is None:
            return
        for page_dir in self.pages():
            # This is only the account returned if ownership is already gone.
            # Every act uses the current reading under the lock below. Keeping
            # the harmless observation outside makes the lock boundary itself
            # testable: a claim or SessionEnd can win after page selection,
            # and _read must then decline every stale act.
            observed = read_json(page_dir / "status.json") or {"state": "idle"}
            try:
                with PageTransaction(page_dir) as page:
                    reading, revive = self._read(page, observed)
                    if not revive:
                        yield reading
                        continue
            except FileNotFoundError:
                # Discovery can race deletion; a missing marker is no page.
                continue

            started = start_server(page_dir, revive=True)
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
        watch_state = page.watch_state(self.identity)
        status = observed if watch_state == "lost" else page.status
        live = status["state"] != "idle"
        batch = (
            unacknowledged(page.events, page.cursor) if watch_state != "lost" else []
        )
        service = read_json(page_dir / "service.json")
        enabled = bool(service and service["enabled"])
        key, now, revive = str(page_dir), time.time(), False
        # Desired service state owns revival. Status says what the page is doing;
        # it does not turn a deliberately disabled service back on.
        if watch_state == "watching" and live and not enabled:
            self._lost.add(key)
        elif watch_state == "watching" and live and now > self._check_at.get(key, 0):
            self._check_at[key] = now + 5
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
        if self.lease is not None:
            self.lease.close()
            self.lease = None


class _WatchPass(NamedTuple):
    """What one complete pass observed, or the outcome that ended it early."""

    readings: list[PageTick]
    live: list[PageTick]
    outcome: int | None


def _batch_registry(page_dir: Path):
    """The vendored registry, for a batch's `means` and `handling` readings."""
    try:
        return load_registry(page_dir)
    except RegistryError:
        return None  # the batch still reaches the agent, unexplained


def batch_data(
    page_dir: Path,
    transaction: PageTransaction,
    batch: list[dict],
) -> dict:
    """Build one complete delivery batch without taking receipt for it."""
    # The batch explains itself off the page's own vendored vocabulary: a
    # reaction's word beside it (`means`), and under `handling` what the layer
    # asks of the agent for each kind present, so the rule reaches the agent at
    # the moment it applies. A stale registry must not block the batch.
    registry = _batch_registry(page_dir)
    return {
        "page": str(page_dir),
        "threads": batch_threads(
            transaction.events,
            batch,
            active_enclosing(page_dir),
        ),
        "handling": handling(batch, registry),
        "events": [described(event, registry) for event in batch],
    }


def serialize_batch(
    page_dir: Path,
    transaction: PageTransaction,
    batch: list[dict],
) -> str:
    """Serialize one complete delivery batch without taking receipt for it."""
    # Whose events follow, said in-band: no event line names its page, and the
    # ack has to go back to the right one. The conversations they land in come
    # with them, because a delivered reply names only the message it answers and
    # the session that knew what that was may since have compacted.
    data = batch_data(page_dir, transaction, batch)
    lines = [
        jsonl_line(
            {
                "page": data["page"],
                "threads": data["threads"],
                "handling": data["handling"],
            }
        )
    ]
    lines.extend(jsonl_line(event) for event in data["events"])
    return "\n".join(lines)


def batch_jsonl(reading: PageTick) -> str:
    """Serialize a watcher reading as one complete delivery batch."""
    return serialize_batch(reading.page_dir, reading.transaction, reading.batch)


def record_pickup(
    page: PageTransaction,
    events: list[dict],
    *,
    phase: str = "opened",
    session: str | None = None,
    turn: str | None = None,
) -> dict | None:
    """Durably record one delivery transition for exact reader moves.

    ``queued`` means Codex's durable same-task queue accepted the batch;
    ``opened`` means the batch entered an agent turn. Both are transport
    evidence, not authored work claims. A queued transition may therefore be
    followed by an opened transition for the same events, while a retry of the
    same transition appends nothing.
    """
    if phase not in {"queued", "opened"}:
        raise ValueError(f"unknown pickup phase {phase!r}")
    claim = page.claim
    if session is None and claim:
        session = claim.get("id")
    if phase == "opened" and turn is None and claim and claim.get("id") == session:
        turn = claim.get("turn")
    wanted = [event["id"] for event in events if event.get("author") == "user"]
    picked = {
        (event_id, event["phase"], event["session"], event["turn"])
        for event in page.events
        if event["kind"] == "pickup"
        for event_id in event["events"]
    }
    fresh = list(
        dict.fromkeys(
            event_id
            for event_id in wanted
            if (event_id, phase, session, turn) not in picked
        )
    )
    if not fresh:
        return None
    return page.append_event(
        {
            "kind": "pickup",
            "author": "page",
            "events": fresh,
            "phase": phase,
            "session": session,
            "turn": turn,
        }
    )


def _deliver_batch(reading: PageTick) -> bool:
    """Write one page's complete batch to its direct consumer.

    Answers that a turn opened, because under this carrier the handoff is the
    opening: `leaf wait` returns with the batch on stdout and the words are in
    model context before anything else runs.
    """
    print(batch_jsonl(reading), flush=True)
    return True


def read_watch_pass(
    watch: Watch,
    named: Path | None,
    deliver: Callable[[PageTick], bool] = _deliver_batch,
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
        if reading.live:
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
            # Whether handing the batch over opens a turn is the carrier's to
            # answer rather than something read off it. A direct wait says yes:
            # leaving the Stop hook's stamp standing through the turn it exits
            # into is what had the page telling the reader the agent had left
            # and to nudge it, two minutes into a turn spent answering them. The
            # Codex adapter says no; its own docstring holds why. The prompt
            # hook stamps the openings no delivery carries. The Stop hook closed
            # the turn across the session's pages, so an opening here reopens
            # the same set.
            if deliver(reading):
                turn = None
                if watch.session_id:
                    turn = reading.transaction.open_turn(watch.session_id)
                record_pickup(
                    reading.transaction,
                    reading.batch,
                    phase="opened",
                    session=watch.session_id,
                    turn=turn,
                )
                if watch.session_id:
                    open_session_turn(watch.session_id, reading.transaction)
            return _WatchPass(readings, live, 0)
        if reading.lost:
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


def cmd_wait(page_dir: Path | None = None, *, claim_named: bool = True) -> int:
    """Hold until a user speaks or a worker reports, and deliver what was said.

    One watcher covers the session. The watch set is every page the session
    holds, re-read each pass, so a page served mid-wait joins the running watch
    without a second command, and a page another session has since picked up
    drops out on its own. With `claim_named`, naming PAGE claims it first — how
    a session picks up a leaf it didn't serve — and holds it in the set. Without
    that flag, an ack re-arm uses PAGE only as the delivered batch's coordinate:
    a host resumes the session-wide set it already owns, while outside a host
    the named page remains the whole watch set. A batch is one page's events, so
    its first line names the page and carries the conversations they land in,
    and `leaf ack` goes back to that page. The JSON envelope says nothing about
    what consumes it. The wait owner advances the cursor only after the complete
    batch reaches that next durable consumer.

    A wait ends on someone speaking, on the last watched leaf ending, or on a
    server being down with no restart to make. It puts no clock on how long a
    user takes, because there is no such measurement to take from this side of
    the wire: a page whose address their browser can't route to and one they
    simply haven't opened yet look identical at every length, so a deadline over
    it announces the first while describing the second — and the second is the
    ordinary case. Only their browser can tell them apart, and the user holds
    the URL from the turn that handed it over, so the report comes from them;
    references/serving-pages.md's "Unreachable URLs and `--host`" carries the
    recourse."""
    if page_dir is not None and claim_named:
        claim_page(page_dir)
    identity = host_identity()
    # A host re-arm resumes its session-wide watch. The page stays named only
    # for a public wait that claims it, or for the bare shell whose named page
    # is its whole watch set.
    named = page_dir if claim_named or identity is None else None
    watch = Watch(identity, named=named)
    if not watch.acquire():
        target = "this session" if identity else str(page_dir)
        print(f"another `leaf wait` is already active for {target}", file=sys.stderr)
        return 2
    try:
        while True:
            reading = read_watch_pass(watch, named)
            if reading.outcome is not None:
                return reading.outcome
            # A leaf the agent idled has nobody left to carry a comment to, so it
            # leaves the watch, and the last one gone ends the wait too.
            if not reading.live:
                return _ended_watch(reading.readings, page_dir)
            time.sleep(1)
    finally:
        watch.release()


def acknowledge(page: PageTransaction, seq: int) -> None:
    """Advance one locked page through a delivered batch target."""
    events = page.events
    # By the seq the event carries, never by its position in the list. A seq
    # is a line number and read_events skips what it can't read, so the two
    # coincide only on a log nothing tore.
    target = next((e for e in events if e["seq"] == seq), None)
    if target is None:
        end = events[-1]["seq"] if events else 0
        sys.exit(f"event {seq} does not exist; the log ends at {end}")
    if target["author"] != "user" and target["kind"] not in ("report", "error"):
        sys.exit(f"event {seq} is not a user event, a report, or a page error")
    if seq > page.cursor:
        write_json(page.page_dir / "cursor.json", {"seq": seq})


def cmd_ack(page_dir: Path, seq: int) -> None:
    """Acknowledge through one event of a complete wait batch that reached delivery.

    The target must be something `leaf wait` prints — a user event or a
    worker's report. This catches a mistyped sequence and prevents an agent from
    advancing the cursor to a trailing log entry it never saw. Writing only when
    the cursor advances makes retries harmless.
    """
    with PageTransaction(page_dir) as page:
        acknowledge(page, seq)
