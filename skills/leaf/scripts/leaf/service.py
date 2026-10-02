"""Page claims, serialized transactions, and status.

The transaction holds the page's append lease; what may be appended under it is
`event_contracts`' to say. Claim discovery runs in a cold host hook, so
process inspection and page-event semantics are imported only by their callers."""

import hashlib
import os
import secrets
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from leaf.event_log import (
    _append_event_unlocked,
    _matching_attempt,
    _parse_events,
    read_cursor,
)
from leaf.files import read_json
from leaf.machine import pid_alive, state_home
from leaf.schema import (
    ACTIVITY_GRACE_SECS,
    INTERACTIONS_FILE,
    STATUS_FILE,
    UNNAMED_AGENT,
)
from leaf.state import (
    EVENTS_FILE,
    flocked,
    now_iso,
    page_key,
    write_json,
    ensure_session,
    session_record,
    open_session_turn,
    close_session_turn,
)

if TYPE_CHECKING:
    from leaf.host import Harness

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
    {"page", "ts", "released", "id", "harness", "agent", "generation"}
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
    if not isinstance(claim, dict) or not CLAIM_IDENTITY <= claim.keys():
        return None
    from leaf.host import HARNESSES

    if claim["harness"] not in HARNESSES:
        return None
    record = session_record(claim["id"])
    if record is None or claim["generation"] != record["generation"]:
        return {**claim, "turn": None, "turn_opened": None, "turn_closed": None}
    return {
        **claim,
        "released": claim["released"] or record["ended"],
        **record["lifetime"],
        "turn": record["turn"],
        "turn_opened": record["turn_opened"],
        "turn_closed": record["turn_closed"],
    }


def page_claim(page_dir: Path) -> dict | None:
    """The page's last claim, including one released or whose lifetime ended."""
    return readable_claim(read_json(claim_path(page_dir)))


def claim_is_active(claim: dict | None) -> bool:
    """Whether a claim still names a live owner: the job record a background
    job's claim points at, the recent touch an `activity` claim stands on, or
    the process every other claim's pid names (`Harness.lifetime`). The only
    reading of that rule: cold hooks and the CLI both call it, so a host that
    states its lifetime a new way joins here alone, beside the one constructor
    above that writes what this reads."""
    if not claim or claim["released"] is not None:
        return False
    if "generation" in claim:
        record = session_record(claim["id"])
        if (
            not record
            or record["generation"] != claim["generation"]
            or record["ended"] is not None
        ):
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
    page's freshness requests, so a user looking at the page is a touch too. Neither
    side has to stamp a heartbeat for this, and one shallow `iterdir` reads both
    — shallow because every file a touch moves sits at the top level, and this is
    read on the serving watchdog's poll.

    Only a *visible* tab, though: `state-feed.js` stops freshness requests from its
    `visibilitychange` listener, so a page sitting in a background tab goes
    untouched until the user returns to it. That gap, not the agent's, is what
    ACTIVITY_GRACE_SECS has to clear, and it is why that constant is hours.

    Diagnostic `interactions.jsonl` is excluded: a request alone does not prove
    a visible reader or active agent. `served_state/reading.py` excludes both it
    and `viewed.json` from the page's own reading token, where counting either
    would make freshness answer its own question. There is no such loop here:
    ownership feeds the watchdog, not the token.

    The claim's own timestamp joins the files for the page that has been served
    but not yet written to, whose newest file can predate the claim."""
    newest = datetime.fromisoformat(claimed_at).timestamp()
    try:
        for entry in page_dir.iterdir():
            if entry.name == INTERACTIONS_FILE:
                continue
            try:
                newest = max(newest, entry.stat().st_mtime)
            except OSError:  # replaced under us; the next pass sees its successor
                continue
    except (FileNotFoundError, NotADirectoryError):
        return False  # the page is gone, and a claim on it owns nothing
    return time.time() - newest < ACTIVITY_GRACE_SECS


def claim_records(session_id: str | None = None) -> list:
    """Every atomic page claim record currently on this machine, retiring each
    record whose page directory is gone. When a session is named, unrelated
    records need no harness validation or lifetime reading.

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
        elif (
            session_id is None
            or (isinstance(record, dict) and record.get("id") == session_id)
        ) and (claim := readable_claim(record)):
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

    def take_claim(self, harness: "Harness") -> tuple[dict | None, dict]:
        """Record this session as the page's watcher.

        The record carries the claimant's harness as well as its id, so every
        later reader — the page server, the append door, the Stop hook, none of
        them necessarily the claimant's own process — rebuilds what the claimant
        declared instead of reading its own environment."""
        previous = self.claim
        path = claim_path(self.page_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        session = ensure_session(harness.session, harness.lifetime())
        claim = {
            "page": str(self.page_dir),
            "ts": now_iso(),
            "released": None,
            "id": harness.session,
            "generation": session["generation"],
            "harness": harness.name,
            "agent": harness.agent,
            "cwd": os.getcwd(),
        }
        write_json(path, claim)
        return previous, page_claim(self.page_dir)

    def restore_claim(self, expected: dict, previous: dict | None) -> None:
        """Roll back one failed claim without erasing a successor's."""
        if self.claim != expected:
            return
        path = claim_path(self.page_dir)
        if previous is None:
            path.unlink(missing_ok=True)
        else:
            write_json(
                path,
                {
                    key: value
                    for key, value in previous.items()
                    if key
                    not in {"turn", "turn_opened", "turn_closed", *CLAIM_LIFETIMES}
                },
            )

    def owned_by(self, harness: "Harness | None") -> bool:
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
            write_json(
                claim_path(self.page_dir),
                {**read_json(claim_path(self.page_dir)), "released": now_iso()},
            )

    def close_turn(self, session_id: str, turn_id: str | None = None) -> None:
        claim = self.claim
        if claim and claim["id"] == session_id and claim_is_active(claim):
            close_session_turn(session_id, turn_id)

    def open_turn(self, session_id: str, turn_id: str | None = None) -> str | None:
        claim = self.claim
        if not claim or claim["id"] != session_id or not claim_is_active(claim):
            return None
        record = open_session_turn(session_id, turn_id)
        return record["turn"] if record else None

    def note_messaged(self, ending: str) -> None:
        """Record that input reaching this page messaged its session after a turn
        ended.

        Browser-event admission sends at most one such message per ending of a
        turn (`session-lifetime.md`, Carriers). `ending` names the claim's turn id
        and its close stamp, or for an interrupted turn its last opening, so a
        later ending, whether a close under a new id or an interrupt after a new
        prompt renewed the same one, never matches the ending a message already
        went out for."""
        write_json(
            claim_path(self.page_dir),
            {**read_json(claim_path(self.page_dir)), "messaged_ending": ending},
        )

    @property
    def status(self) -> dict:
        return read_status(self.page_dir)

    def set_status(
        self,
        state: str,
        detail: str,
        *,
        work: dict | None = None,
    ) -> dict:
        """Write the page declaration and any typed local evidence it renews, and
        return it as written.

        A local line is the same sentence read at a second seat: the page's one
        line says what the agent is doing, and a typed subject says so where the
        work lives. One command writes both because they are one claim, so a
        write after a turn has ended renews the page line and the subject line
        together.

        Standing work carries across every other status write, so a page-wide
        status update does not silently drop what a helper is holding. A new
        claim replaces the old claim on its semantic subject; `idle`
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
        claims = [] if state == "idle" else list(self.status.get("work", []))
        if work:
            claims = [held for held in claims if held["subject"] != work["subject"]]
            voice = self.voice()
            claim = self.claim
            claims.append(
                {
                    "id": secrets.token_hex(4),
                    **work,
                    "detail": detail,
                    "ts": status["ts"],
                    **voice,
                    # The claimant's turn that wrote it, which is how the Stop hook
                    # tells work this turn declared from work an earlier turn left
                    # (`activity.turn_obligations`). Another session's claim names
                    # none. A Claude Code subagent runs as its parent's session, so
                    # a claim it wrote would name the parent's turn; workers leave
                    # status to the session driving the page.
                    "turn": (
                        claim.get("turn")
                        if claim and claim["id"] == voice["session"]
                        else None
                    ),
                }
            )
        if claims:
            status["work"] = claims
        write_json(self.page_dir / STATUS_FILE, status)
        return status

    def voice(self) -> dict:
        """Who a line written on this page speaks as: the posting session where
        one is running, which need not be the claimant, and the page's claimant
        otherwise — a line written by a server speaks in the name of whoever
        holds the page. `UNNAMED_AGENT` covers a page nothing has claimed,
        where there is no name to use and inventing one would put words in a
        program's mouth."""
        from leaf.host import message_identity

        identity = message_identity()
        claim = self.claim
        return {
            "agent": identity.get("agent")
            or (claim["agent"] if claim else UNNAMED_AGENT),
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
        bindings = self._bound(stream, session_id, responds, attempt, turn_id)
        if standing == reply and bindings == stream.get("reply_bindings"):
            return
        stream["reply"] = reply
        stream["reply_bindings"] = bindings
        status["stream"] = stream
        write_json(self.page_dir / STATUS_FILE, status)

    def bind_delivery_reply(
        self,
        session_id: str,
        responds: str,
        attempt: str,
    ) -> None:
        """Reserve one response address before its provider can produce output.

        The reservation names the claim's turn as it stands, since the delivery's
        own turn does not exist yet; that turn takes the binding over when its
        reply opens (`set_stream_reply`). Reserving again, as a retried start
        does, names the claim's turn as it stands then."""
        status = dict(self.status)
        stream = dict(status.get("stream") or {})
        bindings = self._bound(
            stream, session_id, responds, attempt, self.claim["turn"]
        )
        if bindings == stream.get("reply_bindings"):
            return
        stream["reply_bindings"] = bindings
        status["stream"] = stream
        write_json(self.page_dir / STATUS_FILE, status)

    def _bound(
        self,
        stream: dict,
        session_id: str,
        responds: str,
        attempt: str,
        turn_id: str,
    ) -> dict:
        """The stream's bindings with one response address bound to `attempt`
        in `turn_id`, refusing an address another delivery's binding holds while
        it stands (`activity.reply_binding_stands`)."""
        from leaf.activity import reply_binding_stands

        bindings = dict(stream.get("reply_bindings") or {})
        standing = bindings.get(responds)
        claim = self.claim
        if reply_binding_stands(
            standing, claim["id"], claim["turn"], claim["turn_closed"]
        ) and not _held_by(standing, session_id, attempt):
            raise RuntimeError(
                f"response {responds!r} is already bound to another delivery"
            )
        bindings[responds] = {
            "session": session_id,
            "attempt": attempt,
            "turn": turn_id,
        }
        return bindings

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
        if not _held_by(bindings.get(responds), session_id, attempt):
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
        """Remove this task's provisional reply without changing thread history."""
        status = dict(self.status)
        stream = dict(status.get("stream") or {})
        reply = stream.get("reply")
        if not reply or reply.get("session") != session_id:
            return
        if turn_id is not None and reply.get("turn") != turn_id:
            return
        stream.pop("reply")
        bindings = dict(stream.get("reply_bindings") or {})
        if _held_by(bindings.get(reply["responds"]), session_id, reply["attempt"]):
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

    def watch_state(self, harness: "Harness | None") -> str:
        if not self.owned_by(harness):
            return "lost"
        return "ended" if self.status["state"] == "idle" else "watching"


def _held_by(binding: dict | None, session_id: str, attempt: str) -> bool:
    """Whether one reply binding is this delivery attempt's, whatever turn it names."""
    return bool(
        binding
        and binding.get("session") == session_id
        and binding.get("attempt") == attempt
    )


def take_page_claim(page_dir: Path) -> tuple[dict | None, dict] | None:
    """Make the host session the page's watcher, if a host supplied one.

    `server start`, a named `leaf wait` and `page claim` claim; authoring
    commands do not. A
    bare-shell serve makes no claim and therefore starts as standing.
    """
    from leaf.host import session_harness

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


def read_status(page_dir: Path) -> dict:
    """The page's work declaration, `status.json`, as every reader takes it.

    A page whose agent has declared nothing, such as a copy served before any
    `leaf status`, reads as a bare `waiting`: no work under way and nothing ended,
    so the page waits on its user and a wait keeps watching it. A record without
    a `state` describes no declaration either, and reads the same (`AGENTS.md`,
    "Stage"). The first status write replaces it."""
    record = read_json(page_dir / STATUS_FILE)
    if record is None or "state" not in record:
        return {"state": "waiting", "detail": "", "after": 0}
    return record


def owned_pages(session_id: str | None) -> list:
    """Active pages owned by one session, or by every session when id is None."""
    pages = {
        Path(claim["page"])
        for claim in claim_records(session_id)
        if claim_is_active(claim) and (Path(claim["page"]) / EVENTS_FILE).is_file()
    }
    return sorted(pages, key=str)


def unacknowledged(events: list, cursor: int) -> list:
    """Attention-marked events past the page's acknowledgement cursor.

    Carriers, the unpicked-input Stop guard and the idle gate read the same
    admission decision. The user-facing pending count includes only user input;
    workers' reports and page errors wake the agent without increasing that count.
    """
    return [e for e in events if e["seq"] > cursor and requires_agent_attention(e)]


def requires_agent_attention(event: dict) -> bool:
    """Admission's decision that this event changes work the agent owes.

    A record without the admitted decision is absent input.
    """
    return event.get("attention") is True


# The fields every stored work claim carries (`PageService.set_status`).
CLAIM_FIELDS = frozenset(
    {"id", "subject", "after", "detail", "ts", "agent", "session", "turn"}
)


def claim_update_sources(status: dict) -> list[dict]:
    """The status store's work claims at their public boundary.

    `status.json` remains the small replace-in-place store its transient claims
    need. The browser and `page state` receive typed source envelopes instead, so
    every downstream consumer reads the same target and lifecycle vocabulary.

    A claim lacking a field `PageService.set_status` writes today, such as the
    poster's voice, was written by an older leaf and is absent here, so every
    envelope carries the name its work is shown under.
    """
    sources = []
    for claim in status.get("work", []):
        target = claim.get("subject", {})
        required = CLAIM_FIELDS | (
            {"revision"} if target.get("kind") == "widget" else set()
        )
        if not required <= claim.keys():
            continue
        source = {
            "id": claim["id"],
            "target": target,
            "source": "claim",
            "action": "working",
            "detail": {"text": claim["detail"]},
            "text": claim["detail"],
            "ts": claim["ts"],
            "log_floor": claim["after"],
            "agent": claim["agent"],
            "session": claim["session"],
            "turn": claim["turn"],
        }
        if event := claim.get("event"):
            source["event"] = event
        if target["kind"] == "widget":
            source["revision"] = claim["revision"]
        sources.append(source)
    return sources
