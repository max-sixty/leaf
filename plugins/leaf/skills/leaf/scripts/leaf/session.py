"""Agent status, waiting, and acknowledgement policy."""

import sys
import time
from pathlib import Path
from typing import NamedTuple

from .events import batch_threads, jsonl_line
from .files import _path_location, paths_same, read_json, write_json
from .hosting import start_server
from .registry import RegistryError, described, load_registry
from .service import (
    PageTransaction,
    claim_page,
    host_identity,
    owned_pages,
    running_server,
    take_waiter_lease,
    unacknowledged,
    waiter_lease_path,
)
from .work import work_subject


def cmd_status(
    page_dir: Path,
    state: str,
    detail: str,
    handoff: bool = False,
    on: str | None = None,
) -> None:
    with PageTransaction(page_dir) as page:
        work = None
        if on is not None:
            # A local claim says "I am on this now", so the two other states
            # have nothing to put there: `waiting` is the reader's move, and
            # `idle` is the end of the agent's side.
            if state != "working":
                sys.exit("--on says what you are working on; use it with `working`")
            if not detail:
                sys.exit("--on needs a detail; a work line with no words says nothing")
            work = work_subject(page_dir, page.events, on)
        page.set_status(state, detail, handoff=handoff, work=work)


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
    SessionEnd, event arrival, delivery, and the handoff status have one order.
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
        named_at = None if self.named is None else _path_location(self.named)
        if named_at is not None and not any(
            _path_location(d) == named_at for d in watched
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


def cmd_wait(page_dir: Path | None = None) -> int:
    """Hold until a user speaks or a worker reports, and deliver what was said.

    One watcher covers the session. The watch set is every page the session
    holds, re-read each pass, so a page served mid-wait joins the running watch
    without a second command, and a page another session has since picked up
    drops out on its own. Naming PAGE claims it first — how a session picks up
    a leaf it didn't serve — and holds it in the set, which is also the whole
    set outside a host session (a bare shell, the tests). A batch is one page's
    events, so its first line names the page and carries the conversations they
    land in, and `leaf ack` goes back to that page. The JSON envelope says nothing about what consumes it. The wait owner
    advances the cursor only after the complete batch reaches that next durable
    consumer.

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
    if page_dir is not None:
        claim_page(page_dir)
    identity = host_identity()
    watch = Watch(identity, named=page_dir)
    if not watch.acquire():
        target = "this session" if identity else str(page_dir)
        print(f"another `leaf wait` is already active for {target}", file=sys.stderr)
        return 2
    try:
        while True:
            readings = []
            live = []
            for reading in watch.tick():
                readings.append(reading)
                if reading.watch_state == "lost":
                    if page_dir is not None and paths_same(reading.page_dir, page_dir):
                        print(
                            f"stopped watching {page_dir}: this session no longer owns it",
                            file=sys.stderr,
                        )
                        return 2
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
                # The batch outranks the page's state: a wait already holding
                # events owes them to the agent whatever became of the leaf, so
                # an idled page still delivers here — it just no longer holds
                # the wait open below.
                if reading.batch:
                    # Whose events follow, said in-band: no event line names its
                    # page, and the ack has to go back to the right one. The
                    # conversations they land in come with them, because a
                    # delivered reply names only the message it answers and the
                    # session that knew what that was may since have compacted.
                    print(
                        jsonl_line(
                            {
                                "page": str(reading.page_dir),
                                "threads": batch_threads(
                                    reading.transaction.events, reading.batch
                                ),
                            }
                        ),
                        flush=True,
                    )
                    # A reaction's word explained beside it (`means`), off the
                    # page's own vendored vocabulary, so a token a project added
                    # reaches the agent already saying what it asks for. Read
                    # only where a batch carries one: the registry is a gate a
                    # page vendored before the layer last moved fails, and a
                    # wait that cannot deliver a comment over that would be a
                    # wait that delivers nothing.
                    registry = None
                    if any(e.get("token") for e in reading.batch):
                        try:
                            registry = load_registry(reading.page_dir)
                        except RegistryError:
                            registry = None  # the token still reaches the agent
                    for event in reading.batch:
                        print(jsonl_line(described(event, registry)), flush=True)
                    if reading.status["state"] != "working":
                        # Flip before the agent handles the batch: the handoff
                        # gap between this exit and pickup must not show
                        # "waiting". The tick still holds the page lock, so a
                        # transfer cannot land between delivery and this claim.
                        n = len(reading.batch)
                        reading.transaction.set_status(
                            "working",
                            f"picking up {n} update{'s' if n != 1 else ''}",
                            handoff=True,
                        )
                    return 0
                if reading.lost:
                    print(
                        f"{reading.page_dir}: server is not running; restart it with "
                        f"`leaf server start {reading.page_dir}`",
                        file=sys.stderr,
                    )
                    return 2
            # A leaf the agent idled has nobody left to carry a comment to, so it
            # leaves the watch, and the last one gone ends the wait too.
            if not live:
                if not readings:
                    print(
                        "nothing to watch: no page named and none claimed by "
                        "this session",
                        file=sys.stderr,
                    )
                    return 2
                one = len(readings) == 1
                names = ", ".join(str(r.page_dir) for r in readings)
                print(
                    f"the {'leaf' if one else 'leaves'} ended; {names} "
                    f"{'is' if one else 'are'} idle",
                    file=sys.stderr,
                )
                return 2
            time.sleep(1)
    finally:
        watch.release()


def cmd_ack(page_dir: Path, seq: int) -> None:
    """Acknowledge through one event of a complete wait batch that reached delivery.

    The target must be something `leaf wait` prints — a user event or a
    worker's report. This catches a mistyped sequence and prevents an agent from
    advancing the cursor to a trailing log entry it never saw. Writing only when
    the cursor advances makes retries harmless.
    """
    with PageTransaction(page_dir) as page:
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
            write_json(page_dir / "cursor.json", {"seq": seq})
