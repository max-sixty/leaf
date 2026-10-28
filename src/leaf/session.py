"""Page availability and the `leaf wait` watch.

A watch discovers its pages before loading delivery or page projections, and
loads the HTTP server only to revive a dead one. Status writes use those same
projections without importing a server. Receipt remains `delivery`'s."""

import contextlib
import shlex
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from .detached import StartRefused
from .file_changes import FileChanges, target_paths
from .files import file_stamp
from .findings import Finding, note
from .harness import Harness, claim_harness, session_harness
from .hook_transport import HOOK_TIMEOUT_S
from .interaction_log import record_command, record_watch
from .leases import (
    end_if_terminated,
    release_lease,
    take_wait_lease,
    waiter_lease_path,
)
from .locations import path_location, paths_same
from .presence import nudge_unwatched, turn_ending
from .refusals import Refused
from .registry.kernel import kinds_declaring
from .schema import ANSWER_INSTRUCTION
from .served_state.reading import (
    outside_inputs,
    page_input,
    page_reading,
    page_roots,
)
from .server import read_service, running_server
from .service import PageTransaction, owned_pages, unacknowledged
from .state import (
    SESSION_SUFFIX,
    session_claims,
    session_file,
    session_record,
    state_home,
    still_named,
)

# How often a watch rechecks a live page's server. It is also the longest a watch goes
# without a pass on a page whose files have not moved: nothing else a pass reads
# changes on the clock alone.
REVIVAL_CHECK_S = 5


def cmd_waiting(page_dir: Path) -> dict:
    """Keep the page open for feedback, which puts down every start that stands
    (`todos.item_starts`), and return the declaration's record. The updates still
    owed an answer, which the page goes on showing over it, are noted with the
    command that answers each."""
    from .activity import answer_command
    from .revisioning import activate_source
    from .served_state.context import read_page

    with PageTransaction(page_dir) as page:
        activate_source(page_dir, transaction=page)
        status = page.set_status("waiting")
        owed = read_page(page_dir, page.events).work.obligations
    if owed:
        answers = [answer_command(item["answer"], page_dir) for item in owed]
        note(Finding("page-open-owes", values={"answers": answers}, severity="advice"))
    return status


def cmd_idle(page_dir: Path) -> dict:
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
                f"so the page cannot close yet. {remedy}"
            )
        owed = blocking_obligations(
            state,
            watched=harness is not None
            and harness.watcher_live(listening=state["listening"]),
        )
        if owed:
            raise Refused(
                f"{unanswered(owed, page_dir, 'acknowledged')}; answer before closing. "
                + ANSWER_INSTRUCTION
            )
        # A to-do is work the agent still owes, which closing the page would leave
        # open on a page nobody holds.
        if todos := work.durable.log.owed:
            named = "; ".join(f"{todo['id']} ({todo['title']})" for todo in todos)
            raise Refused(
                f"{len(todos)} open to-do{'s' if len(todos) != 1 else ''}: {named}. "
                "End each before closing with "
                '`leaf task end <page> <id> done --text "<where the result is>"`, or '
                '`dropped --text "<why>"`.'
            )
        return page.set_status("idle")


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
    the agent's own choice, and `page init` stops a served page to re-initialize it and
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
        lease_paths = []
        for page in targets:
            path = waiter_lease_path(page, self.session_id)
            assert path is not None
            lease_paths.append(path)
        self.lease_paths = tuple(lease_paths)
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
            lease = take_wait_lease(path, supersede=supersede)
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

        def plan():
            discovery = self.discovery_targets()
            targets = discovery | {
                target for page in pages for target in outside_inputs(page)
            }
            if self.session_id:
                targets.add(session_file(self.session_id, SESSION_SUFFIX).resolve())
            targets.update(path.resolve() for path in self.lease_paths)
            roots = {self.claims: False}
            roots.update({target.parent: False for target in targets})
            for page in pages:
                roots.update(page_roots(page))
            return discovery, (pages, frozenset(targets)), roots

        def holds(key, roots):
            return (
                self.changes is not None
                and key == self.change_pages
                and self.changes.matches(roots)
            )

        def install(key, roots):
            if self.changes is not None:
                self.changes.close()
            watched = target_paths(key[1])
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

        while True:
            discovery, key, roots = plan()
            if not holds(key, roots):
                install(key, roots)
            assert self.changes is not None
            # Stamp the subscribed set. A locator added during installation must
            # differ at the next comparison, so its target is subscribed in turn.
            reading = self.reading(discovery)
            generation = self.changes.mark()
            # The roots follow each page's subdirectories, so a plan taken after
            # the generation must still match: one created before it is
            # subscribed now, and one created after it wakes the wait.
            if holds(*plan()[1:]):
                return (list(pages), reading, generation)

    def await_news(self, mark: tuple, timeout: float = REVIVAL_CHECK_S) -> bool:
        """Return True once anything the pass since `mark` read has moved, or False
        after `timeout` with nothing moved. A pass that found a different set of
        pages returns True at once: `mark` stamped the old set."""
        watched, before, generation = mark
        if self.watched != watched:
            return True
        assert self.changes is not None
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
            # Every act uses the reading under the lock below: a claim or
            # SessionEnd can win after page selection, and _read must then decline
            # every stale act.
            try:
                with PageTransaction(page_dir) as page:
                    reading, revive = self._read(page)
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
                    reading, _ = self._read(page)
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

    def _read(self, page: PageTransaction) -> tuple[PageTick, bool]:
        """Read one page transaction and say whether revival is due."""
        page_dir = page.page_dir
        watch_state = page.watch_state(self.harness)
        status = page.status
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


def wait_acknowledgement(
    harness: Harness | None, page_dir: Path
) -> Callable[[str], str]:
    """What a `leaf wait` delivery of `page_dir` tells its reader about
    acknowledging it.

    Printing is not receipt, so the reader of the wait confirms it and starts the
    next wait in one command, in the way its harness runs a wait; `&&` starts no
    wait after a refused acknowledgement. A reader with no harness session names
    the page again, since it has no ownership set for an unnamed wait to watch,
    and its wait named one page, so the delivery carries that page alone. It is
    stated once for the delivery, ahead of the batches, where output cut off
    partway still shows it."""
    rearm = "leaf wait" if harness else shlex.join(["leaf", "wait", str(page_dir)])
    run_ack = (harness or Harness).run_ack

    def acknowledge(delivery_id: str) -> str:
        command = f"leaf delivery ack {delivery_id} && {rearm}"
        return (
            "If the output was cut off, reread it with "
            f"`leaf delivery read {delivery_id}` and follow any `next` commands. "
            f"Then, before any other work, {run_ack(command)}, which confirms "
            "this delivery and waits for the next. If you forward the delivery "
            "instead of handling it, acknowledge once it arrives where you sent it."
        )

    return acknowledge


def delivery_json(reading: PageTick, harness: Harness | None) -> str:
    """Freeze a watcher reading and present its bounded first part, as `delivery
    read` prints it."""
    from .delivery import batch_data, delivery_reading, freeze_delivery
    from .event_log import jsonl_line

    payload = freeze_delivery(
        [batch_data(reading.page_dir, reading.transaction, reading.batch)],
        acknowledge=wait_acknowledgement(harness, reading.page_dir),
    )
    return jsonl_line(delivery_reading(payload))


def read_watch_pass[DeliveryResult](
    watch: Watch,
    named: Path | None,
    deliver: Callable[[PageTick], DeliveryResult],
    ready: Callable[[PageTick], bool] = lambda reading: bool(reading.batch),
) -> _WatchPass[DeliveryResult]:
    """Read pages until this pass completes or one page ends the wait, delivering
    the first page the watch is `ready` to wake for: by default one with a batch
    to hand over. A page it is not ready for waits for a later pass."""
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
        if ready(reading):
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


def wake_line(page_dir: Path, *, new_input: bool) -> str:
    """What a watch says as it wakes the session, where the harness's prompt hook
    carries what woke it into the turn: `new_input`, or an answer a closed turn left
    owed (`left_owed`)."""
    if new_input:
        return (
            f"{page_dir} has new input; Leaf's prompt hook puts it in your context "
            "with this notification"
        )
    return (
        f"{page_dir} has an update still owed an answer; Leaf's prompt hook names it "
        "in your context with this notification"
    )


def cmd_wait(page_dir: Path | None = None) -> int:
    """Watch for the next batch.

    A named wait observes that page without taking ownership; an unnamed one
    watches the session's current ownership set, and a consumer with no harness
    session has none, so it names its page. Exit 0 carries the next immutable
    delivery; exit 2 names why the watch ended.
    """
    # Leaf's work ends here; the watch that follows is the agent waiting.
    record_command("wait")
    harness = session_harness()
    explicit = (page_dir,) if page_dir else ()
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
            reading = read_watch_pass(watch, page_dir, print_delivery)
            if reading.delivered is False:
                break
            if reading.outcome is not None:
                return reading.outcome
            if not reading.live:
                return _ended_watch(reading.readings, page_dir)
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
    `receipt` does not prove delivery. Other admitted attention (including
    reports, errors, reactions and widget actions) remains
    transport input, independent of whether it carries a response obligation.
    """
    from .served_state.context import read_page
    from .workflows import agent_inputs

    if not batch:
        return []
    agents = agent_inputs(read_page(page.page_dir, page.events).work.durable)
    pending = []
    for event in batch:
        if event["kind"] in kinds_declaring("message") and event["id"] not in agents:
            continue
        pending.append(event)
    return pending


def left_owed(page: PageTransaction) -> list[dict]:
    """The updates whose answers the claimant's closed turn left owed and no prompt
    has named since their delivery (`activity.left_owed`). The Stop hook lets such
    a turn end on its answer, and the watch wakes a turn of its own for them, whose
    prompt hook names them."""
    from .activity import left_owed as owed_after
    from .delivery import reminded
    from .served_state.context import read_page

    claim = page.active_claim
    if claim is None or claim["turn_closed"] is None:
        return []
    work = read_page(page.page_dir, page.events).work
    by_id = {event["id"]: event for event in page.events}
    return [
        by_id[obligation["input"]]
        for obligation in owed_after(
            {**work.presence, "activity": work.activity},
            lambda input_id: reminded(page.events, input_id),
        )
    ]


def watch_between_turns(
    harness: Harness, *, interrupted: bool = False, at_prompt: bool = False
) -> str | None:
    """Wake for meaningful unreceived input, without treating a log look as pickup.

    Input already present at startup waits for the concurrent Stop hook to close
    the turn, since that hook may still continue it over what the turn owes; the
    input then gets a turn of its own (`hook_transport`). The turn's closing ends
    that bounded grace; input arriving while the watch runs wakes immediately,
    unless it arrives in a later turn than the one the watch follows
    (`later_turn_wakes`), which takes it itself. A watch after Escape
    wakes for what the stopped turn left deliverable: input that never entered its
    context, and input its hooks handed over that its transcript does not show
    (`delivery.deliverable`); input the turn confirmed waits for a prompt.
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
    # The concurrent Stop hook has its timeout to close the turn.
    settled = time.monotonic() + HOOK_TIMEOUT_S
    watch = Watch(harness)
    watch.acquire(supersede=True)
    # The turn this watch follows, none for a prompt's watch, and when it saw each
    # later turn closed.
    followed = (
        None if at_prompt else (session_record(harness.session) or {}).get("turn")
    )
    later_closed: dict[str, float] = {}

    def later_turn_wakes(claim: dict) -> bool:
        """Whether input wakes the session in a turn opened after the one this
        watch follows. While that turn runs it takes input at its next tool
        boundary or Stop hook, so a wake would only show the user a second notice
        of input the turn is about to read. The Stop hook that closes it starts
        the watch that takes over from this one, so this one wakes then only if
        no successor has come within the Stop hooks' time. Escape ends a turn
        with no Stop hook, leaving its record open, and the harness's own `idle`
        is the reading that moves then; a harness that gives none keeps the
        immediate wake, except for a prompt's watch."""
        if claim["turn_closed"] is not None:
            closed = later_closed.setdefault(claim["turn"], time.monotonic())
            return time.monotonic() > closed + HOOK_TIMEOUT_S
        live = harness.live_turn()
        if live is None:
            # A prompt's watch follows the running turn itself, which its Stop hook
            # hands over to the next watch.
            return not at_prompt
        return live["state"] == "idle"

    # What `left_owed` found on each page, by the log and turn it read, so a pass
    # that finds nothing changed folds no page.
    owed: dict[Path, tuple[tuple, list[dict]]] = {}

    def reminders(page: PageTransaction) -> list[dict]:
        claim = page.active_claim
        key = (
            len(page.events),
            claim and claim["turn"],
            claim and claim["turn_closed"],
        )
        if (kept := owed.get(page.page_dir)) is None or kept[0] != key:
            owed[page.page_dir] = kept = (key, left_owed(page))
        return kept[1]

    def ready(reading: PageTick) -> bool:
        pending = wake_inputs(reading.transaction, reading.batch) or (
            [] if interrupted else reminders(reading.transaction)
        )
        if not pending:
            return False
        if interrupted:
            return True
        claim = reading.transaction.active_claim
        if claim is not None and claim["turn"] != followed:
            return later_turn_wakes(claim)
        return (
            (claim is not None and claim["turn_closed"] is not None)
            or any(
                datetime.fromisoformat(event["ts"]).timestamp() >= began
                for event in pending
            )
            or time.monotonic() > settled
        )

    # How the watch ended, which its record in each page it read keeps.
    ended = "stopped"
    try:
        while harness.process_runs():
            mark = watch.mark()
            reading = read_watch_pass(
                watch,
                None,
                lambda tick: wake_line(
                    tick.page_dir,
                    new_input=bool(wake_inputs(tick.transaction, tick.batch)),
                ),
                ready,
            )
            # Superseded during the pass, it leaves what it found to its successor.
            if not watch.holds():
                ended = "superseded"
                return None
            if reading.delivered is not None:
                ended = "woke"
                woke_after(harness.session)
                return reading.delivered
            if reading.outcome is not None:
                ended = "server-down"
                return "\n".join(
                    f"{tick.page_dir}: server is not running; restart it with "
                    f"`leaf server start {tick.page_dir}`"
                    for tick in reading.readings
                    if tick.lost
                )
            if not reading.live:
                ended = "no-pages"
                return None
            watch.await_news(mark)
        ended = "harness-exited"
    finally:
        watch.release()
        record_watch(watch.watched, harness.session, began, ended)
    # Input admitted while this watch held the lease was not nudged, so now the
    # lease is gone, any such input is nudged as admission would have.
    nudge_pending(harness.session)
    return None


def woke_after(session: str) -> None:
    """Mark each page the session holds as messaged for the ending of its turn, as a
    watch exits to wake the session, so admission does not nudge it too in the
    moment before the woken turn starts (`presence.nudge_unwatched`)."""
    for page_dir in owned_pages(session):
        with contextlib.suppress(FileNotFoundError), PageTransaction(page_dir) as page:
            if claim := page.active_claim:
                page.note_messaged(turn_ending(claim))


def nudge_pending(session: str) -> None:
    """Nudge the session for each page it holds whose input could wake it, as
    admission would have with no watch holding the lease (`nudge_unwatched`)."""
    from .delivery import deliverable

    for page_dir in owned_pages(session):
        with contextlib.suppress(FileNotFoundError), PageTransaction(page_dir) as page:
            if wake_inputs(page, deliverable(page)):
                nudge_unwatched(page)
