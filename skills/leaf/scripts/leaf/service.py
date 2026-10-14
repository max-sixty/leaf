"""Page claims, serialized transactions, and status.

The transaction holds the page's append lease; what may be appended under it is
`event_contracts`' to say. Cold harness hooks read claims, and Codex's tool hook
opens a transaction after every tool call, so process inspection and page-event
semantics are imported only by their callers. A transaction finishes interrupted
publications before admitting a reader. Hosts may declare LEAF_PAGE_COMMIT as a
module:function provider; successful completion calls it under the same append
lease, and provider failure prevents the caller from acknowledging success."""

from __future__ import annotations

import hashlib
import importlib
import os
import secrets
import sys
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
from leaf.files import read_json, unfinished_publications
from leaf.machine import pid_alive, sandbox_remedy, state_home
from leaf.refusals import Refused
from leaf.schema import STATUS_FILE
from leaf.state import (
    CLAIMED_SUFFIX,
    EVENTS_FILE,
    chat_exists,
    ensure_session,
    flocked,
    fsync_parents,
    now_iso,
    page_key,
    session_file,
    session_lock_path,
    session_record,
    write_json,
)

if TYPE_CHECKING:
    from leaf.harness import Harness

# A repeated live detail carries only liveness. Renew it comfortably before the
# fifteen-minute activity boundary without turning tool output into file churn.
STREAM_ACTIVITY_RENEWAL = timedelta(minutes=5)


def delivery_reply_attempt(delivery_id: str) -> str:
    """Return the stable idempotency key for one delivery-bound reply."""
    digest = hashlib.sha256(delivery_id.encode()).hexdigest()[:32]
    return f"leaf-delivery-{digest}"


def claim_path(page_dir: Path) -> Path:
    """The page's one canonical payload, also written by resident page servers."""
    return state_home().resolve() / "claims" / f"{page_key(page_dir)}.json"


def session_claims(session_id: str) -> Path:
    """This session's discovery locators; payloads remain canonical by page."""
    return state_home().resolve() / "claims" / session_file(session_id, "claims").stem


def publish_claim(page_dir: Path, claim: dict) -> None:
    """Prepare discovery, then commit ownership in the canonical payload.

    Discovery validates the payload's owner against the partition. A transfer's
    old locator therefore stops being current at the canonical commit, which also
    admits the prepared new locator. Failed preparation leaves ownership intact.
    Resident writers retain the same flat payload path, so their atomic updates
    cannot destroy discovery.
    """
    path = claim_path(page_dir)
    previous = read_json(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    locator = session_claims(claim["id"]) / path.name
    locator.parent.mkdir(parents=True, exist_ok=True)
    staged = locator.with_name(f".{secrets.token_hex(8)}.tmp")
    try:
        staged.symlink_to(Path("..") / path.name)
        os.replace(staged, locator)
        fsync_parents([locator])
    finally:
        staged.unlink(missing_ok=True)
    write_json(path, claim)
    if (
        isinstance(previous, dict)
        and isinstance(previous.get("id"), str)
        and previous["id"] != claim["id"]
    ):
        (session_claims(previous["id"]) / path.name).unlink(missing_ok=True)


# What a reader takes straight off a claim: these fields by name, one of the
# lifetime keys `claim_is_active` cascades on, and a `harness` whose value
# `harness.claim_harness` looks up in `HARNESSES`.
CLAIM_IDENTITY = frozenset(
    {"page", "ts", "id", "harness", "agent", "generation", "acquisition"}
)
CLAIM_LIFETIMES = frozenset({"job", "chat", "pid"})


def readable_claim(claim: dict | None) -> dict | None:
    """The record if this version can read it as a claim, else None.

    Another version may have written the record (root AGENTS.md, "Stage"). One the
    readings above cannot take their answers from is not a claim, so the page reads
    as unclaimed until something claims it again.

    A harness the table no longer holds is such a record: the name is a value this
    version dispatches on, so it is decided here rather than raising two calls
    further in.

    Every reader goes through `page_claim` or `claim_records`, so this is the only
    place that decides it."""
    if not isinstance(claim, dict) or not CLAIM_IDENTITY <= claim.keys():
        return None
    from leaf.harness import HARNESSES

    if claim["harness"] not in HARNESSES:
        return None
    record = session_record(claim["id"])
    if record is None or claim["generation"] != record["generation"]:
        return {**claim, "turn": None, "turn_opened": None, "turn_closed": None}
    return {
        **claim,
        **record["lifetime"],
        "turn": record["turn"],
        "turn_opened": record["turn_opened"],
        "turn_closed": record["turn_closed"],
    }


def page_claim(page_dir: Path) -> dict | None:
    """The page's last claim, including one whose session or lifetime ended."""
    return readable_claim(read_json(claim_path(page_dir)))


def claim_is_active(claim: dict | None) -> bool:
    """Whether a claim still names a live owner: the job record a background
    job's claim points at, the native source a persisted `chat` stands on, or
    the process every other claim's pid names (`Harness.lifetime`). The only
    reading of that rule: cold hooks and the CLI both call it, so a harness that
    states its lifetime a new way joins here alone, beside the one constructor
    above that writes what this reads."""
    if not claim:
        return False
    record = session_record(claim["id"])
    if (
        not record
        or record["generation"] != claim["generation"]
        or record["ended"] is not None
    ):
        return False
    if "job" in claim:
        return (Path(claim["job"]) / "state.json").is_file()
    if claim.get("chat") is True:
        return chat_exists(record)
    return "pid" in claim and pid_alive(claim["pid"])


def dead_session(claim: dict) -> str:
    """Why a claim just prepared has no live session. Its session can end between
    preparing and publishing, but where a sandbox runs the command in a process
    namespace of its own, as Claude Code's does on Linux, the session's process
    was never visible to it, and only a command run outside the sandbox can claim."""
    if "pid" in claim and not pid_alive(claim["pid"]) and (remedy := sandbox_remedy()):
        return f"the session's process ({claim['pid']}) is not visible here: {remedy}"
    return "the prepared acquisition no longer has a live session"


def claim_names_session(claim: dict | None, session_id: str) -> bool:
    """Whether the page is still `session_id`'s to record what its task took from
    the page and answered there: the claim names that session, and the session
    has not ended.

    Unlike `claim_is_active`, this survives the session's own restart. A new
    lifetime begins its generation before it publishes that generation's claim,
    and a task that holds several pages claims them back one at a time, so the
    claim may name an older generation, or a lifetime that has gone, of a session
    still running. What that session's task received and answered stays its own
    to record; only another session's claim takes the page from it."""
    if not claim or claim["id"] != session_id:
        return False
    record = session_record(session_id)
    return record is not None and record["ended"] is None


def may_receive(claim: dict | None, session_id: str | None) -> bool:
    """Whether `session_id` may take receipt of the page's input under `claim`
    (`delivery.receive_batch`): the claim names it, or, for a reader with no
    session, no session holds the page."""
    if session_id is None:
        return not claim_is_active(claim)
    return claim_names_session(claim, session_id)


def claimant_matches(claim: dict | None, harness: Harness | None) -> bool:
    """Whether the record names this harness, or neither names a claimant.

    Harness identity is independent of liveness: readers pass the active claim
    when asking which harness owns the page now. Resource retirement instead uses
    the exact acquisition reading (`same_claim`).
    """
    if harness is None:
        return claim is None
    return bool(
        claim and (claim["harness"], claim["id"]) == (harness.name, harness.session)
    )


def same_claim(left: dict | None, right: dict | None) -> bool:
    """Whether two readings name the same acquisition, including no claimant.

    Lifecycle projection may change between readings; acquisition is the exact
    publication a resource owner may retire or a failed start may restore.
    """
    if left is None or right is None:
        return left is right
    return left["acquisition"] == right["acquisition"]


def claim_records(session_id: str | None = None) -> list:
    """Readable claims for pages still on this machine.

    A scan observes ownership without changing it. A missing directory can be
    recreated and claimed immediately after the observation, so removing its
    claim here could erase the successor's ownership. Fresh page initialization
    clears the prior claim under the page lock instead.

    Payloads are canonical by page. A named lookup enumerates only that
    session's locators, checking the canonical payload owner before admitting it.
    No unrelated claim files are opened or page directories inspected."""
    directory = (
        session_claims(session_id) if session_id else state_home().resolve() / "claims"
    )
    if not directory.is_dir():
        return []
    claims = []
    for path in directory.glob("*.json"):
        record = read_json(path)
        page = record.get("page") if isinstance(record, dict) else None
        if isinstance(page, str) and claim_path(Path(page)) != path.resolve():
            continue
        if (
            session_id is not None
            and isinstance(record, dict)
            and isinstance(record.get("id"), str)
            and path.parent != session_claims(record["id"])
        ):
            continue
        if isinstance(page, str) and not Path(page).is_dir():
            continue
        elif (
            session_id is None
            or (isinstance(record, dict) and record.get("id") == session_id)
        ) and (claim := readable_claim(record)):
            claims.append(claim)
    return claims


class PageTransaction:
    """One page transition serialized by its append-only log. A `deadline`
    bounds the wait for the log's lock (`flocked`)."""

    def __init__(self, page_dir: Path, *, deadline: float | None = None):
        self.page_dir = page_dir.resolve()
        self.deadline = deadline
        self._lock = None
        self._log = None
        self._events = None

    def __enter__(self):
        self._events = None
        self._lock = flocked(self.page_dir / EVENTS_FILE, deadline=self.deadline)
        self._log = self._lock.__enter__()
        try:
            if publications := unfinished_publications(self.page_dir, self.events):
                from leaf.revisioning import finish_publications

                finish_publications(self, publications)
        except BaseException:
            self._lock.__exit__(*sys.exc_info())
            raise
        return self

    def __exit__(self, exc_type, exc, traceback):
        try:
            if exc_type is None and (provider := os.environ.get("LEAF_PAGE_COMMIT")):
                module, name = provider.split(":", 1)
                getattr(importlib.import_module(module), name)(self)
        finally:
            self._lock.__exit__(exc_type, exc, traceback)

    @property
    def claim(self) -> dict | None:
        return page_claim(self.page_dir)

    @property
    def active_claim(self) -> dict | None:
        claim = self.claim
        return claim if claim_is_active(claim) else None

    def open_reply_reservation(self, responds: str) -> dict | None:
        """The reply reservation on `responds` while the claim turn it names is open
        (`delivery` header)."""
        from leaf.activity import reply_reservation_stands

        reservation = (
            (self.status.get("stream") or {}).get("reply_reservations") or {}
        ).get(responds)
        claim = self.active_claim
        if claim and reply_reservation_stands(
            reservation, claim["id"], claim["turn"], claim["turn_closed"]
        ):
            return reservation
        return None

    @property
    def delivery_owner(self) -> str | None:
        """The last logical owner, even after release, end or process restart.

        Another session's claim supersedes delivered authorizations; liveness
        and process generations do not. Reply reservations fence provider finals
        (`delivery`).
        """
        claim = self.claim
        return claim["id"] if claim else None

    def claim_of(self, session_id: str) -> dict | None:
        """The claim, while the page is still `session_id`'s (`claim_names_session`)."""
        claim = self.claim
        return claim if claim_names_session(claim, session_id) else None

    def take_claim(self, harness: Harness) -> tuple[dict | None, dict]:
        """Record this session as the page's watcher.

        The record carries the claimant's harness as well as its id, so every
        later reader — the page server, the append door, the Stop hook, none of
        them necessarily the claimant's own process — rebuilds what the claimant
        declared instead of reading its own environment."""
        with self.publishing_claim(prepare_claim(harness, self.page_dir)) as transition:
            pass
        return transition

    @contextmanager
    def publishing_claim(self, claim: dict):
        """Validate an intent, publish dependent resources, then acquire the page.

        Page then session is the lifecycle lock order. The session cannot end or
        replace its generation between intent validation and claim publication.
        The caller performs only short local publication while this lock stands;
        ownership is the final mutation, after those resources are ready.
        """
        with flocked(session_lock_path(claim["id"])):
            projected = readable_claim(claim)
            if not claim_is_active(projected):
                raise Refused(dead_session(projected))
            previous = self.claim
            yield previous, projected
            publish_claim(self.page_dir, claim)
            # Lets Codex's tool hook skip a session that never held a page
            # (`state.hook_needed`).
            session_file(claim["id"], CLAIMED_SUFFIX).touch()

    def restore_claim(self, expected: dict, previous: dict | None) -> None:
        """Roll back one failed claim without erasing a successor's."""
        if not same_claim(self.claim, expected):
            return
        path = claim_path(self.page_dir)
        if previous is None:
            path.unlink(missing_ok=True)
            (session_claims(expected["id"]) / path.name).unlink(missing_ok=True)
        else:
            publish_claim(
                self.page_dir,
                {
                    key: value
                    for key, value in previous.items()
                    if key
                    not in {"turn", "turn_opened", "turn_closed", *CLAIM_LIFETIMES}
                },
            )

    def owned_by(self, harness: Harness | None) -> bool:
        """Whether this transaction may act for the given waiter."""
        return claimant_matches(self.active_claim, harness)

    def note_messaged(self, ending: str) -> None:
        """Record that input reaching this page messaged its session after a turn
        ended.

        `presence.nudge_unwatched` sends at most one such message per ending of a
        turn (`session-lifetime.md`, Watchers), from browser-event admission or
        from a watch giving up its lease. `ending` names the claim's turn id
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

    def set_status(self, state: str, detail: str) -> dict:
        """Write the page's `waiting` or `idle` declaration and return it as written.

        The work the agent has in hand is no status: it is the log's `start` events,
        and the `put_down` that `leaf status` writes beside a declaration takes them
        back (`todos`). The stream the harness observes carries across a `waiting`,
        and `idle` clears it with the leaf."""
        status = {"state": state, "detail": detail, "ts": now_iso()}
        if state != "idle" and (stream := self.status.get("stream")):
            status["stream"] = stream
        write_json(self.page_dir / STATUS_FILE, status)
        return status

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
        previous = stream.get("activity")
        observed = {
            "session": session_id,
            "turn": turn_id,
            "kind": activity["kind"],
            **({"detail": activity["detail"]} if activity.get("detail") else {}),
            "ts": now,
            "after": after,
        }
        if (
            previous
            and (
                previous["session"],
                previous["turn"],
                previous.get("kind"),
                previous.get("detail"),
                previous["after"],
            )
            == (
                observed["session"],
                observed["turn"],
                observed["kind"],
                observed.get("detail"),
                observed["after"],
            )
            and datetime.fromisoformat(now) - datetime.fromisoformat(previous["ts"])
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
        previous = stream.get("reply") or {}
        timestamp = (
            previous.get("ts")
            if previous.get("session") == session_id and previous.get("turn") == turn_id
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
            "agent": self.claim["agent"],
            "ts": timestamp or updated_at,
            "updated_at": updated_at,
        }
        reservations = self._reserved(stream, session_id, responds, attempt, turn_id)
        if previous == reply and reservations == stream.get("reply_reservations"):
            return
        stream["reply"] = reply
        stream["reply_reservations"] = reservations
        status["stream"] = stream
        write_json(self.page_dir / STATUS_FILE, status)

    def reserve_delivery_reply(
        self,
        session_id: str,
        responds: str,
        attempt: str,
    ) -> None:
        """Reserve one response address before its provider can produce output.

        The reservation names the claim's turn as it stands, since the delivery's
        own turn does not exist yet; that turn takes the reservation over when its
        reply opens (`set_stream_reply`). Reserving again, as a retried start
        does, names the claim's turn as it stands then."""
        status = dict(self.status)
        stream = dict(status.get("stream") or {})
        reservations = self._reserved(
            stream, session_id, responds, attempt, self.claim["turn"]
        )
        if reservations == stream.get("reply_reservations"):
            return
        stream["reply_reservations"] = reservations
        status["stream"] = stream
        write_json(self.page_dir / STATUS_FILE, status)

    def _reserved(
        self,
        stream: dict,
        session_id: str,
        responds: str,
        attempt: str,
        turn_id: str,
    ) -> dict:
        """The stream's reservations with one response address reserved for `attempt`
        in `turn_id`, refusing an address another delivery's reservation holds while
        it stands (`activity.reply_reservation_stands`)."""
        reservations = dict(stream.get("reply_reservations") or {})
        reserved = self.open_reply_reservation(responds)
        if reserved is not None and not _held_by(reserved, session_id, attempt):
            raise RuntimeError(
                f"response {responds!r} is already reserved by another delivery"
            )
        reservations[responds] = {
            "session": session_id,
            "attempt": attempt,
            "turn": turn_id,
        }
        return reservations

    def set_stream_reply_state(
        self,
        session_id: str,
        turn_id: str,
        attempt: str,
        text: str,
        state: str,
    ) -> bool:
        """Finish the matching displayed draft without changing its reservation."""
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

    def clear_delivery_reply_reservation(
        self,
        session_id: str,
        responds: str,
        attempt: str,
    ) -> None:
        """Release one response address without changing its visible draft."""
        status = dict(self.status)
        stream = dict(status.get("stream") or {})
        reservations = dict(stream.get("reply_reservations") or {})
        if not _held_by(reservations.get(responds), session_id, attempt):
            return
        reservations.pop(responds)
        if reservations:
            stream["reply_reservations"] = reservations
        else:
            stream.pop("reply_reservations", None)
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
        reservations = dict(stream.get("reply_reservations") or {})
        if _held_by(reservations.get(reply["responds"]), session_id, reply["attempt"]):
            reservations.pop(reply["responds"])
        if reservations:
            stream["reply_reservations"] = reservations
        else:
            stream.pop("reply_reservations", None)
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
            return _append_event_unlocked(self._log, event, self.events)
        finally:
            self._events = None

    @property
    def cursor(self) -> int:
        return read_cursor(self.page_dir)

    def watch_state(self, harness: Harness | None) -> str:
        if not self.owned_by(harness):
            return "lost"
        return "ended" if self.status["state"] == "idle" else "watching"


def _held_by(reservation: dict | None, session_id: str, attempt: str) -> bool:
    """Whether one reply reservation is this delivery attempt's, whatever turn it
    names."""
    return bool(
        reservation
        and reservation.get("session") == session_id
        and reservation.get("attempt") == attempt
    )


def prepare_claim(harness: Harness, page_dir: Path) -> dict:
    """Capture an unpublished acquisition in the claimant's process.

    Lifetime and cwd come from the launching harness, not a detached child. Preparing
    the canonical session is independent of any page ownership publication.
    """
    session = ensure_session(harness.session, harness.lifetime())
    return {
        "page": str(page_dir),
        "ts": now_iso(),
        "id": harness.session,
        "generation": session["generation"],
        "acquisition": secrets.token_hex(16),
        "harness": harness.name,
        "agent": harness.agent,
        "cwd": os.getcwd(),
    }


def take_page_claim(page_dir: Path) -> tuple[dict | None, dict] | None:
    """Make the harness session the page's watcher, if a harness supplied one.

    `server start` and `page claim` claim; waiting and authoring commands do not.
    A bare-shell serve makes no claim and therefore starts as persistent.
    """
    from leaf.harness import session_harness

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


def read_status(page_dir: Path) -> dict:
    """The page's work declaration, `status.json`, as every reader takes it.

    A page whose agent has declared nothing, such as a copy served before any
    `leaf status`, reads as a bare `waiting`: no work under way and nothing ended,
    so the page waits on its user and a wait keeps watching it. A record without
    a `state` describes no declaration either, and reads the same (`AGENTS.md`,
    "Stage"). The first status write replaces it."""
    record = read_json(page_dir / STATUS_FILE)
    if record is None or "state" not in record:
        return {"state": "waiting", "detail": ""}
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

    Delivery, the unpicked-input Stop guard and the idle gate read the same
    admission decision. The user-facing pending count includes only user input;
    workers' reports and page errors wake the agent without increasing that count.
    """
    return [e for e in events if e["seq"] > cursor and requires_agent_attention(e)]


def requires_agent_attention(event: dict) -> bool:
    """Admission's decision that this event changes work the agent owes.

    A record without the admitted decision is absent input.
    """
    return event.get("attention") is True
