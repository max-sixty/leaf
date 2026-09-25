"""Page claims, serialized transactions, and status.

The transaction holds the page's append lease; what may be appended under it is
`event_contracts`' to say."""

import hashlib
import os
import secrets
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from leaf.event_log import (
    _append_event_unlocked,
    _matching_attempt,
    _parse_events,
    flocked,
    now_iso,
    read_cursor,
)
from leaf.files import read_json, write_json
from leaf.host import (
    HARNESSES,
    Harness,
    message_identity,
    session_harness,
)
from leaf.locations import page_key
from leaf.machine import pid_alive, state_home
from leaf.registry.layer import bookkeeping_kinds
from leaf.schema import (
    ACTIVITY_GRACE_SECS,
    EVENTS_FILE,
    STATUS_FILE,
    UNCLAIMED_AGENT,
)

# A repeated live detail carries only liveness. Renew it comfortably before the
# fifteen-minute activity boundary without turning tool output into file churn.
STREAM_ACTIVITY_RENEWAL = timedelta(minutes=5)


def delivery_reply_attempt(delivery_id: str) -> str:
    """Return the stable idempotency key for one delivery-bound reply."""
    digest = hashlib.sha256(delivery_id.encode()).hexdigest()[:32]
    return f"leaf-delivery-{digest}"


def claim_path(page_dir: Path) -> Path:
    """The one ownership record for a resolved page path."""
    return state_home() / "claims" / f"{page_key(page_dir)}.json"


# What a reader takes straight off a claim: these fields by name, one of the
# lifetime keys `claim_is_active` cascades on, and a `harness` whose value
# `host.claim_harness` looks up in `HARNESSES`.
CLAIM_IDENTITY = frozenset(
    {"page", "ts", "released", "id", "harness", "agent", "turn", "turn_closed"}
)
CLAIM_LIFETIMES = frozenset({"job", "activity", "pid"})


def readable_claim(claim: dict | None) -> dict | None:
    """The record if this version can read it as a claim, else None.

    The claims directory is one per machine, and several worktrees, hosts and
    sessions write it at once, each running the leaf it was built from. So a
    record here can have been written by another version, and Stage owes nothing
    to what an older one wrote: there is no migration and no shim that reads the
    old shape. What follows is this — a record the readings above can take their
    answers from is a claim, and any other record is not one this version can
    read, so the page reads as unclaimed until something claims it again.
    Dropping it is what deleting the stale state would have done, without the
    deletion.

    A harness the table no longer holds is that same record. The name is a value
    this version dispatches on rather than a field it reads, and renaming one is
    what renaming the field around it already proved reachable, so it is decided
    here with the rest instead of raising two calls further in.

    Every reader goes through `page_claim` or `claim_records`, so this is the
    only place that decides it, and a session is never taken down by a record it
    does not own."""
    if not claim or not CLAIM_IDENTITY <= claim.keys():
        return None
    if claim["harness"] not in HARNESSES:
        return None
    return claim if CLAIM_LIFETIMES & claim.keys() else None


def page_claim(page_dir: Path) -> dict | None:
    """The page's last claim, including one released or whose lifetime ended."""
    return readable_claim(read_json(claim_path(page_dir)))


def claim_lifetime(page_dir: Path, harness: Harness) -> dict:
    """The fields `claim_is_active` reads, as everything that writes them must.

    Two things state a lifetime on this rule: a page's claim, and a preview that
    takes no claim but is reaped by the session all the same. Neither is the
    place to learn which fields the reading needs — a host stating its lifetime a
    new way adds a branch below, and a writer that kept the old set fails on that
    host alone. So the set is built here, next to the reading that consumes it,
    and a claim carries these among its own fields rather than beside them."""
    return {
        "page": str(page_dir),
        "ts": now_iso(),
        "released": None,
        **harness.lifetime(),
    }


def claim_is_active(claim: dict | None) -> bool:
    """Whether a claim still names a live owner: the job record a background
    job's claim points at, the recent touch an `activity` claim stands on, or
    the process every other claim's pid names (`Harness.lifetime`). The only
    reading of that rule: the hooks reach it through `uv` rather than keeping a
    copy, so a host that states its lifetime a new way joins here alone, beside
    the one constructor above that writes what this reads."""
    if not claim or claim["released"] is not None:
        return False
    if "job" in claim:
        return (Path(claim["job"]) / "state.json").is_file()
    if "activity" in claim:
        return _touched_recently(Path(claim["page"]), claim["ts"])
    return pid_alive(claim["pid"])


def _touched_recently(page_dir: Path, claimed_at: str) -> bool:
    """Whether anything has touched this page inside ACTIVITY_GRACE_SECS.

    The page directory is the record of its own use, and it already holds both
    halves. The session appends events and writes status there; the server
    writes `viewed.json` every thirty seconds for as long as a tab holds the
    page's news stream, so a user looking at the page is a touch too. Neither
    side has to stamp a heartbeat for this, and one shallow `iterdir` reads both
    — shallow because every file a touch moves sits at the top level, and this is
    read on the serving watchdog's poll.

    Only a *visible* tab, though: `state-feed.js` closes the stream from its
    `visibilitychange` listener, so a page sitting in a background tab goes
    untouched until the user returns to it. That gap, not the agent's, is what
    ACTIVITY_GRACE_SECS has to clear, and it is why that constant is hours.

    `served_state/reading.py` deliberately excludes `viewed.json` from the
    page's own reading token, where counting it would have a stream answer its
    own question. There is no such loop here: ownership feeds the watchdog, not
    the token.

    The claim's own timestamp joins the files for the page that has been served
    but not yet written to, whose newest file can predate the claim."""
    newest = datetime.fromisoformat(claimed_at).timestamp()
    try:
        for entry in page_dir.iterdir():
            try:
                newest = max(newest, entry.stat().st_mtime)
            except OSError:  # replaced under us; the next pass sees its successor
                continue
    except (FileNotFoundError, NotADirectoryError):
        return False  # the page is gone, and a claim on it owns nothing
    return time.time() - newest < ACTIVITY_GRACE_SECS


def claim_records() -> list:
    """Every atomic page claim record currently on this machine, retiring each
    record whose page directory is gone.

    A claim outlives its session on purpose: it is the provenance of a page that
    is still there. Once the page is gone it says nothing, and a page is usually
    removed from outside leaf — a worktree's `.tmp/previews` goes with the
    worktree, a scratch directory with its session — so no leaf process sees the
    moment, and without this the record stays to be read by every later scan.
    This scan is where leaf learns it, so the record goes here, whichever version
    wrote it: a missing page is the same fact to every reader, and `page init`
    already keeps a page made again at that path from inheriting the record. A
    successor claim at that path could only be lost by a `page init` and a claim
    both landing between this check and the unlink."""
    directory = state_home() / "claims"
    if not directory.is_dir():
        return []
    claims = []
    for path in directory.glob("*.json"):
        record = read_json(path)
        page = record.get("page") if isinstance(record, dict) else None
        if isinstance(page, str) and not Path(page).is_dir():
            path.unlink(missing_ok=True)
        elif claim := readable_claim(record):
            claims.append(claim)
    return claims


class PageTransaction:
    """One page transition serialized by its append-only log."""

    def __init__(self, page_dir: Path):
        self.page_dir = page_dir.resolve()
        self._lock = None
        self._log = None
        self._events = None

    def __enter__(self):
        self._events = None
        self._lock = flocked(self.page_dir / EVENTS_FILE)
        self._log = self._lock.__enter__()
        return self

    def __exit__(self, exc_type, exc, traceback):
        return self._lock.__exit__(exc_type, exc, traceback)

    @property
    def claim(self) -> dict | None:
        return page_claim(self.page_dir)

    @property
    def active_claim(self) -> dict | None:
        claim = self.claim
        return claim if claim_is_active(claim) else None

    def take_claim(self, harness: Harness) -> tuple[dict | None, dict]:
        """Record this session as the page's watcher.

        The record carries the claimant's harness as well as its id, so every
        later reader — the page server, the append door, the Stop hook, none of
        them necessarily the claimant's own process — rebuilds what the claimant
        declared instead of reading its own environment."""
        previous = self.claim
        path = claim_path(self.page_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        same_open_turn = bool(
            previous
            and claim_is_active(previous)
            and previous["released"] is None
            and previous["id"] == harness.session
            and previous.get("turn_closed") is None
        )
        claim = {
            **claim_lifetime(self.page_dir, harness),
            "id": harness.session,
            "harness": harness.name,
            "agent": harness.agent,
            "cwd": os.getcwd(),
            # Opaque identity of the currently open agent turn on this page.
            # Delivery transitions name it, so an unresolved pickup from an old
            # turn cannot become "being handled" merely because a later prompt
            # opened another turn in the same session.
            "turn": previous["turn"] if same_open_turn else secrets.token_hex(8),
            # When this session's last turn ended. None until one has, and
            # cleared again when a batch delivered to this session opens the
            # next turn. See close_turn and open_turn.
            "turn_closed": None,
        }
        write_json(path, claim)
        return previous, claim

    def restore_claim(self, expected: dict, previous: dict | None) -> None:
        """Roll back one failed claim without erasing a successor's."""
        if self.claim != expected:
            return
        path = claim_path(self.page_dir)
        if previous is None:
            path.unlink(missing_ok=True)
        else:
            write_json(path, previous)

    def owned_by(self, harness: Harness | None) -> bool:
        """Whether this transaction may act for the given waiter."""
        if harness is None:
            return self.active_claim is None
        claim = self.active_claim
        return bool(
            claim and (claim["harness"], claim["id"]) == (harness.name, harness.session)
        )

    def release_claim(self) -> None:
        claim = self.claim
        if claim and claim["released"] is None:
            write_json(claim_path(self.page_dir), {**claim, "released": now_iso()})

    def close_turn(self, session_id: str, turn_id: str | None = None) -> None:
        """Record that the turn which could have renewed this page's claim has ended.

        A `working` claim is written by a model's turn rather than by a process,
        and a turn can end at any token without running anything — so there is no
        close to write on the way out, and a claim nobody renewed used to be
        found only by a clock fifteen minutes later. The Stop hook is the harness
        observing that same moment exactly, which is what the hooks are for.

        It lands here with the rest of the claim's provenance and not in
        status.json, the line SessionEnd already draws: what the agent said it
        was doing stays the agent's to write, and whether anything is still
        behind those words stays the page's to judge from evidence.
        """
        claim = self.claim
        if (
            claim
            and claim["released"] is None
            and claim["id"] == session_id
            and (turn_id is None or claim.get("turn") == turn_id)
        ):
            write_json(claim_path(self.page_dir), {**claim, "turn_closed": now_iso()})

    def open_turn(self, session_id: str, turn_id: str | None = None) -> str | None:
        """Record that a turn of this session's is running again.

        `close_turn` is stamped by the Stop hook, and until this it was stamped
        by nothing else — so the page could see a turn end but never see the
        next one begin. That is not symmetric bookkeeping for its own sake: the
        canonical activity fold stops believing a declaration left behind by a
        closed turn, and an opened delivery belongs to the current turn only by
        exact turn identity. Without an opening, a session that came back could
        be presented as one that had walked away.

        Two things observe the beginning. A prompt is one: the hook that mirrors
        the Stop hook fires with the turn already running, whoever caused it —
        including the user who did the thing the banner told them to and
        nudged in the terminal, leaving no batch for any delivery to carry. A
        delivery is the other, and whether it is belongs to the carrier that
        makes it: the direct consumer confirms a complete delivery, so its receipt opens
        the turn; the Codex adapter hands a pointer to a durable queue an
        unloaded task leaves standing, so its handoff is not, and it declines
        this.

        Nothing else about the claim moves. What the agent said it was doing
        stays the agent's to write, and the fifteen-minute grace on that claim's
        own age still catches a turn that ends without a Stop to stamp it.
        """
        claim = self.claim
        if not claim or claim["released"] is not None or claim["id"] != session_id:
            return None
        if turn_id is not None and (
            claim.get("turn") != turn_id or claim.get("turn_closed") is not None
        ):
            claim = {**claim, "turn": turn_id, "turn_closed": None}
            write_json(claim_path(self.page_dir), claim)
        elif claim.get("turn_closed") is not None:
            claim = {
                **claim,
                "turn": secrets.token_hex(8),
                "turn_closed": None,
            }
            write_json(claim_path(self.page_dir), claim)
        return claim.get("turn")

    def note_messaged_turn(self) -> None:
        """Record that input reaching this page messaged its session while the
        claim's turn was closed.

        Browser-event admission sends at most one such message per closed turn
        (`session-lifetime.md`, Carriers). The turn id is the exact key: an
        opening mints a new one whenever it clears a closing, so a later closed
        turn never matches the turn a message already went out in."""
        claim = self.claim
        write_json(claim_path(self.page_dir), {**claim, "messaged_turn": claim["turn"]})

    @property
    def status(self) -> dict:
        return read_json(self.page_dir / STATUS_FILE)

    def set_status(
        self,
        state: str,
        detail: str,
        *,
        work: dict | None = None,
        handling: dict | None = None,
    ) -> None:
        """Write the page declaration and any typed local evidence it renews.

        A local line is the same sentence read at a second seat: the page's one
        line says what the agent is doing, and a typed subject says so where the
        work lives. One command writes both because they are one claim, so a
        write after a turn has ended renews the page line and the subject line
        together.

        Standing work carries across every other status write, so a page-wide
        status update does not silently drop what a helper is holding. Exact
        delivery handling carries until another delivered move replaces it; the
        interaction fold stops using it as soon as that move is settled.
        A new claim replaces the old claim on its semantic subject; `idle`
        clears them all with the leaf.
        """
        status = {
            "state": state,
            "detail": detail,
            "ts": now_iso(),
            # Order the agent's declaration against delivery transitions without
            # comparing wall-clock timestamps that are only precise to a second.
            "after": self.events[-1]["seq"] if self.events else 0,
        }
        if state != "idle" and (stream := self.status.get("stream")):
            status["stream"] = stream
        if state != "idle" and (current_handling := self.status.get("handling")):
            status["handling"] = current_handling
        claims = [] if state == "idle" else list(self.status.get("work", []))
        if work:
            claims = [held for held in claims if held["subject"] != work["subject"]]
            claims.append(
                {
                    "id": secrets.token_hex(4),
                    **work,
                    "detail": detail,
                    "ts": status["ts"],
                    **self.voice(),
                }
            )
        if claims:
            status["work"] = claims
        if handling:
            status["handling"] = {
                "id": secrets.token_hex(4),
                **handling,
                "detail": detail,
                "ts": status["ts"],
                **self.voice(),
            }
        write_json(self.page_dir / STATUS_FILE, status)

    def voice(self) -> dict:
        """Who a line written on this page speaks as: the posting session where
        one is running, which need not be the claimant, and the page's claimant
        otherwise — a line written by a server speaks in the name of whoever
        holds the page. `UNCLAIMED_AGENT` covers a page nothing has claimed,
        where there is no name to use and inventing one would put words in a
        program's mouth."""
        identity = message_identity()
        claim = self.claim
        return {
            "agent": identity.get("agent")
            or (claim["agent"] if claim else UNCLAIMED_AGENT),
            "session": identity.get("session") or (claim["id"] if claim else None),
        }

    def set_stream_activity(
        self, session_id: str, turn_id: str, activity: dict
    ) -> None:
        """Record activity observed directly from the task's live event stream."""
        status = dict(self.status)
        if status["state"] == "idle":
            return
        stream = dict(status.get("stream") or {})
        now = now_iso()
        after = self.events[-1]["seq"] if self.events else 0
        standing = stream.get("activity")
        observed = {
            "session": session_id,
            "turn": turn_id,
            "kind": activity["kind"],
            **({"detail": activity["detail"]} if activity.get("detail") else {}),
            "ts": now,
            "after": after,
        }
        if (
            standing
            and (
                standing["session"],
                standing["turn"],
                standing.get("kind"),
                standing.get("detail"),
                standing["after"],
            )
            == (
                observed["session"],
                observed["turn"],
                observed["kind"],
                observed.get("detail"),
                observed["after"],
            )
            and datetime.fromisoformat(now) - datetime.fromisoformat(standing["ts"])
            < STREAM_ACTIVITY_RENEWAL
        ):
            return
        stream["activity"] = observed
        status["stream"] = stream
        write_json(self.page_dir / STATUS_FILE, status)

    def clear_stream_activity(
        self, session_id: str, turn_id: str | None = None
    ) -> None:
        """Remove this task's live reading without changing its declaration."""
        status = dict(self.status)
        stream = dict(status.get("stream") or {})
        activity = stream.get("activity")
        if not activity or activity.get("session") != session_id:
            return
        if turn_id is not None and activity.get("turn") != turn_id:
            return
        stream.pop("activity")
        if stream:
            status["stream"] = stream
        else:
            status.pop("stream", None)
        write_json(self.page_dir / STATUS_FILE, status)

    def set_stream_reply(
        self,
        session_id: str,
        turn_id: str,
        reply_to: str,
        responds: str,
        attempt: str,
        item_id: str | None,
        text: str,
        state: str,
        *,
        settles: bool = False,
    ) -> None:
        """Replace the provisional reply owned by one delivered response."""
        status = dict(self.status)
        stream = dict(status.get("stream") or {})
        standing = stream.get("reply") or {}
        timestamp = (
            standing.get("ts")
            if standing.get("session") == session_id and standing.get("turn") == turn_id
            else None
        )
        updated_at = now_iso()
        reply = {
            "session": session_id,
            "turn": turn_id,
            "attempt": attempt,
            "reply_to": reply_to,
            "responds": responds,
            "item": item_id,
            "text": text,
            "state": state,
            "settles": settles,
            # The claimant's name: a stream reply is the task that holds the page
            # speaking, and `take_claim` always wrote one.
            "agent": self.claim["agent"],
            "ts": timestamp or updated_at,
            "updated_at": updated_at,
        }
        bindings = dict(stream.get("reply_bindings") or {})
        binding = {"session": session_id, "attempt": attempt}
        if (
            (standing_binding := bindings.get(responds))
            and standing_binding.get("session") == session_id
            and standing_binding != binding
        ):
            raise RuntimeError(
                f"response {responds!r} is already bound to another delivery"
            )
        if standing == reply and bindings.get(responds) == binding:
            return
        stream["reply"] = reply
        bindings[responds] = binding
        stream["reply_bindings"] = bindings
        status["stream"] = stream
        write_json(self.page_dir / STATUS_FILE, status)

    def bind_delivery_reply(
        self,
        session_id: str,
        responds: str,
        attempt: str,
    ) -> None:
        """Reserve one response address before its provider can produce output."""
        status = dict(self.status)
        stream = dict(status.get("stream") or {})
        bindings = dict(stream.get("reply_bindings") or {})
        binding = {"session": session_id, "attempt": attempt}
        if (
            (standing := bindings.get(responds))
            and standing.get("session") == session_id
            and standing != binding
        ):
            raise RuntimeError(
                f"response {responds!r} is already bound to another delivery"
            )
        if bindings.get(responds) == binding:
            return
        bindings[responds] = binding
        stream["reply_bindings"] = bindings
        status["stream"] = stream
        write_json(self.page_dir / STATUS_FILE, status)

    def set_stream_reply_state(
        self,
        session_id: str,
        turn_id: str,
        attempt: str,
        text: str,
        state: str,
    ) -> bool:
        """Finish the matching displayed draft without changing its binding."""
        status = dict(self.status)
        stream = dict(status.get("stream") or {})
        reply = stream.get("reply") or {}
        if (
            reply.get("session") != session_id
            or reply.get("turn") != turn_id
            or reply.get("attempt") != attempt
        ):
            return False
        finished = {
            **reply,
            "item": None,
            "text": text,
            "state": state,
            "settles": False,
            "updated_at": now_iso(),
        }
        if finished == reply:
            return True
        stream["reply"] = finished
        status["stream"] = stream
        write_json(self.page_dir / STATUS_FILE, status)
        return True

    def clear_delivery_reply_binding(
        self,
        session_id: str,
        responds: str,
        attempt: str,
    ) -> None:
        """Release one response address without changing its visible draft."""
        status = dict(self.status)
        stream = dict(status.get("stream") or {})
        bindings = dict(stream.get("reply_bindings") or {})
        if bindings.get(responds) != {"session": session_id, "attempt": attempt}:
            return
        bindings.pop(responds)
        if bindings:
            stream["reply_bindings"] = bindings
        else:
            stream.pop("reply_bindings", None)
        if stream:
            status["stream"] = stream
        else:
            status.pop("stream", None)
        write_json(self.page_dir / STATUS_FILE, status)

    def clear_stream_reply(self, session_id: str, turn_id: str | None = None) -> None:
        """Remove this task's provisional reply without changing conversation history."""
        status = dict(self.status)
        stream = dict(status.get("stream") or {})
        reply = stream.get("reply")
        if not reply or reply.get("session") != session_id:
            return
        if turn_id is not None and reply.get("turn") != turn_id:
            return
        stream.pop("reply")
        bindings = dict(stream.get("reply_bindings") or {})
        binding = bindings.get(reply["responds"])
        if binding == {"session": session_id, "attempt": reply["attempt"]}:
            bindings.pop(reply["responds"])
        if bindings:
            stream["reply_bindings"] = bindings
        else:
            stream.pop("reply_bindings", None)
        if stream:
            status["stream"] = stream
        else:
            status.pop("stream", None)
        write_json(self.page_dir / STATUS_FILE, status)

    @property
    def events(self) -> list:
        if self._events is None:
            self._log.seek(0)
            self._events = _parse_events(self._log.read())
        return self._events

    def matching_attempt(self, event: dict) -> dict | None:
        """An accepted retry, read under this transaction's log lease."""
        return _matching_attempt(self.events, event)

    def _append_record(self, event: dict) -> dict:
        """Write one admitted record under this transaction's log lease.

        The lease is this class's to hold, so the write is this class's to make;
        what makes a record admissible is not. `event_contracts.append_admitted`
        is the one caller — every writer reaches the log through that door, and
        nothing else here may append."""
        try:
            accepted, appended = _append_event_unlocked(self._log, event, self.events)
        except Exception:
            self._events = None
            raise
        if appended:
            self._events = None
        return accepted

    @property
    def cursor(self) -> int:
        return read_cursor(self.page_dir)

    def watch_state(self, harness: Harness | None) -> str:
        if not self.owned_by(harness):
            return "lost"
        return "ended" if self.status["state"] == "idle" else "watching"


def take_page_claim(page_dir: Path) -> tuple[dict | None, dict] | None:
    """Make the host session the page's watcher, if a host supplied one.

    `server start` and named `leaf wait` claim; authoring commands do not. A
    bare-shell serve makes no claim and therefore starts as standing.
    """
    harness = session_harness()
    if not harness:
        return None
    with PageTransaction(page_dir) as page:
        return page.take_claim(harness)


def claim_page(page_dir: Path) -> bool:
    return take_page_claim(page_dir) is not None


def restore_page_claim(
    page_dir: Path, transition: tuple[dict | None, dict] | None
) -> None:
    """Undo a failed startup's claim, provided no successor replaced it."""
    if transition is None:
        return
    previous, expected = transition
    with PageTransaction(page_dir) as page:
        page.restore_claim(expected, previous)


@contextmanager
def starting_claim(page_dir: Path, *, standing: bool = False):
    """Claim the page for whatever starts inside, and give the claim back if the
    start raises.

    The one claim transition a start takes: `server start`, `server run`, a
    `--user` preview's first start, and `leaf codex start`. A standing start
    declines the claim. What counts as a start that raised is the caller's: a
    detached start raises until its handshake commits (`detached`), so a caller
    that leaves before committing restores the claim it took. The restore keeps a
    successor's claim that replaced this one in between.
    """
    transition = None if standing else take_page_claim(page_dir)
    try:
        yield
    except BaseException:
        restore_page_claim(page_dir, transition)
        raise


def open_session_turn(session_id: str) -> None:
    """Clear the turn-ended stamp on every page one session holds.

    A turn belongs to the session, not to the page whose batch opened it. The
    Stop hook stamps the ending across `owned_pages`, so an opening that clears
    only one page leaves every sibling claim stamped through a turn that is
    demonstrably running: the user comments on one leaf, and two minutes later
    the next leaf tells its own user the agent left when its turn ended and to
    nudge it in the terminal.

    Each page takes its own transaction, the way the Stop hook takes them, and
    a page the turn never touches still falls to the fifteen-minute grace on its
    own claim age.
    """
    for page_dir in owned_pages(session_id):
        try:
            with PageTransaction(page_dir) as page:
                page.open_turn(session_id)
        except FileNotFoundError:
            continue


def close_session_turn(session_id: str) -> bool:
    """Stamp the end of a turn across every page one session still holds."""
    pages = owned_pages(session_id)
    for page_dir in pages:
        try:
            with PageTransaction(page_dir) as page:
                page.close_turn(session_id)
        except FileNotFoundError:
            continue
    return bool(pages)


def owned_pages(session_id: str | None) -> list:
    """Active pages owned by one session, or by every session when id is None."""
    pages = {
        Path(claim["page"])
        for claim in claim_records()
        if claim_is_active(claim)
        and (session_id is None or claim["id"] == session_id)
        and (Path(claim["page"]) / EVENTS_FILE).is_file()
    }
    return sorted(pages, key=str)


def unacknowledged(events: list, cursor: int) -> list:
    """The events past the acknowledgement cursor that the page's watcher owes a
    reading: the user's own, and workers' reports — a report moves the page the
    way a user's action does, and the watcher is the one who can absorb it into
    a version. One cursor and one predicate for the whole batch, so `leaf
    wait`'s output, the Stop hook's count, and the idle gate cannot disagree
    about what is still owed. The user's banner counts only the user half
    (full_state's `pending`): a report is news the agent owes the page, not
    something the user owes an answer. A session that reports to a page it
    also watches reads its own report back once — rare enough (workers report,
    the watcher publishes) that a session-keyed carve-out would cost a second,
    parameterized predicate for no failure anyone has hit."""
    return [
        e
        for e in events
        if e["seq"] > cursor
        # The user's own, a worker's report, and the page reporting itself
        # broken — the last is the agent's debt exactly as a report is.
        and requires_agent_attention(e)
    ]


def requires_agent_attention(event: dict) -> bool:
    """Whether a log event creates host work, rather than user bookkeeping."""
    return (
        event["author"] == "user" and event["kind"] not in bookkeeping_kinds()
    ) or event["kind"] in {"report", "error"}


def claim_update_sources(status: dict) -> list[dict]:
    """The status store's work claims at their public boundary.

    `status.json` remains the small replace-in-place store its transient claims
    need. The browser and `page state` receive typed source envelopes instead, so
    every downstream consumer reads the same target and lifecycle vocabulary.
    """
    sources = []
    for claim in status.get("work", []):
        target = claim["subject"]
        source = {
            "id": claim.get("id")
            or f"claim:{target['kind']}:{target['id']}:{claim['after']}",
            "target": target,
            "source": "claim",
            "action": "working",
            "detail": {"text": claim["detail"]},
            "text": claim["detail"],
            "ts": claim["ts"],
            "log_floor": claim["after"],
            "agent": claim.get("agent"),
            "session": claim.get("session"),
        }
        if event := claim.get("event"):
            source["event"] = event
        if target["kind"] == "widget":
            source["revision"] = claim["revision"]
        sources.append(source)
    if handling := status.get("handling"):
        target = handling["target"]
        source = {
            "id": handling["id"],
            "target": target,
            "source": "claim",
            "scope": "interaction",
            "action": "working",
            "detail": {"text": handling["detail"]},
            "text": handling["detail"],
            "ts": handling["ts"],
            "log_floor": handling["after"],
            "event": handling["event"],
            "agent": handling.get("agent"),
            "session": handling.get("session"),
        }
        if target["kind"] == "widget":
            source["revision"] = handling["revision"]
        sources.append(source)
    return sources
