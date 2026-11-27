"""A page's serialized transaction (`PageTransaction`), the claim changes made
under one, and the pages a session holds.

The transaction holds the lease on the page's log, so a page transition, a change
of the page's claim (`take_page_claim`, `restore_page_claim`) and a write to the
claimant's stream (`service.STREAM`) each order against every other. What may be
appended under the lease is `event_contracts`' to say, and how a line is written and
read back is `event_log`'s. The acknowledgement cursor (`acknowledged`) is read from
the log under it.

A transaction finishes interrupted publications before admitting a reader
(`revision_publication.finish_publications`), appending through admission under
this same transaction. A host that keeps pages outside this machine declares the
module that commits them there (`commit_provider`); successful completion calls its
`publish` under the same lease, and provider failure prevents the caller from
acknowledging success.

Cold harness hooks ask which pages a session holds (`owned_pages`), and Codex's tool
hook opens a transaction after every tool call, so process inspection (`harness`),
page-event semantics (`activity`) and the finishing of a publication, which loads
admission (`revision_publication`), are imported only in the functions that use
them."""

from __future__ import annotations

import importlib
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, NamedTuple

from leaf.base.files import unfinished_publications
from leaf.base.refusals import Refused
from leaf.base.schema import STREAM_FILE
from leaf.base.service import (
    STREAM,
    claim_is_active,
    claim_names_session,
    claim_path,
    claim_reading,
    claim_records,
    claimant_matches,
    dead_session,
    no_stream,
    page_claim,
    page_holder,
    prepare_claim,
    publish_claim,
    read_stream,
    same_claim,
)
from leaf.base.state import (
    CLAIM,
    EVENTS_FILE,
    claims_lock,
    flocked,
    now_iso,
    remove_claim,
    replace_bytes,
    session_lock_path,
)
from leaf.log.event_log import (
    append_event_unlocked,
    end_last_line,
    initialized,
    read_events,
    session_context,
)
from leaf.log.interaction_log import append_interactions

if TYPE_CHECKING:
    from leaf.base.harness import Harness

# A repeated live detail carries only liveness. Renew it comfortably before the
# fifteen-minute activity boundary without turning tool output into file churn.
STREAM_ACTIVITY_RENEWAL = timedelta(minutes=5)


def commit_provider() -> ModuleType | None:
    """The module a host names in `LEAF_PAGE_COMMIT` to keep each page outside this
    machine, as leaf.page's container keeps its pages in the session's Durable
    Object, or None where it names none. Leaf acknowledges a page transaction only once
    the module's `publish(transaction)` returns, and a drafts write only once its
    `publish_drafts(page_dir, drafts, replaces)` answers with the store the host holds
    (`drafts.py`); either raising fails what it commits."""
    provider = os.environ.get("LEAF_PAGE_COMMIT")
    return importlib.import_module(provider) if provider else None


class ClaimTransition(NamedTuple):
    """One claim's publication (`PageTransaction.publishing_claim`), for its
    rollback (`PageTransaction.restore_claim`): the page's claim at this shape before
    it, the claim as its readers take it (`service.claim_reading`), and the bytes of
    each claim of another shape it removed (`service.publish_claim`), filled as it
    publishes."""

    previous: dict | None
    claim: dict
    displaced: dict[Path, bytes]


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
            end_last_line(self._log)
            if publications := unfinished_publications(self.page_dir, self.events):
                from leaf.records.revision_publication import finish_publications

                finish_publications(self, publications)
        except BaseException:
            self._lock.__exit__(*sys.exc_info())
            raise
        return self

    def __exit__(self, exc_type, exc, traceback):
        try:
            if exc_type is None and (provider := commit_provider()) is not None:
                provider.publish(self)
        finally:
            assert self._lock is not None
            self._lock.__exit__(exc_type, exc, traceback)

    @property
    def claim(self) -> dict | None:
        return page_claim(self.page_dir)

    @property
    def active_claim(self) -> dict | None:
        """The claim while its session lives, which a reader acting for that session
        acts by; who holds the page for a reader deciding whether it may act
        against its holder is `holder`'s."""
        claim = self.claim
        return claim if claim_is_active(claim) else None

    def holder(self, session_id: str | None) -> dict | str | None:
        """Who holds the page for a reader acting for `session_id`
        (`service.page_holder`)."""
        return page_holder(self.page_dir, self.claim, session_id)

    def open_reply_reservation(self, responds: str) -> dict | None:
        """The reply reservation on `responds` while the claim turn it names is open
        (`delivery` header)."""
        from leaf.records.activity import reply_reservation_stands

        reservation = self.stream["reply_reservations"].get(responds)
        claim = self.active_claim
        if claim and reply_reservation_stands(reservation, claim["id"], claim):
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
        """The claim, while the page is still `session_id`'s
        (`service.claim_names_session`)."""
        claim = self.claim
        return claim if claim_names_session(claim, session_id) else None

    def take_claim(self, harness: Harness) -> ClaimTransition:
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
            projected = claim_reading(claim)
            assert projected is not None  # a claim reads as one
            if not claim_is_active(projected):
                raise Refused(dead_session(projected))
            transition = ClaimTransition(self.claim, projected, {})
            yield transition
            transition.displaced.update(publish_claim(self.page_dir, claim))

    def restore_claim(self, transition: ClaimTransition) -> None:
        """Roll back one failed claim without erasing a successor's, putting back
        what it replaced: the previous claim at this shape and, unread, each claim
        of another shape the publication removed."""
        if not same_claim(self.claim, transition.claim):
            return
        path = claim_path(self.page_dir)
        if transition.previous is None:
            remove_claim(path)
        else:
            # The claim's own keys, less what its reading took from its session.
            publish_claim(
                self.page_dir,
                {
                    key: value
                    for key, value in transition.previous.items()
                    if key in CLAIM.schema["properties"]
                },
            )
        with flocked(claims_lock()):
            for other, stored in transition.displaced.items():
                replace_bytes([(other, stored, False)])

    def note_messaged(self, ending: str) -> None:
        """Record that input reaching this page messaged its session after a turn
        ended.

        `delivery.nudge_unwatched` sends at most one such message per ending of a
        turn, from browser-event admission, from
        a watch giving up its lease, or from the page's server reading a turn
        interrupted, and a watch that wakes the session marks the ending too
        (`session.woke_after`). `ending` names the claim's turn id
        and its close stamp, or for an interrupted turn its last opening, so a
        later ending, whether a close under a new id or an interrupt after a new
        prompt renewed the same one, never matches the ending a message already
        went out for."""
        claim = CLAIM.read(claim_path(self.page_dir))
        assert claim is not None
        publish_claim(self.page_dir, {**claim, "messaged_ending": ending})

    @property
    def status(self) -> dict:
        """The agent's declaration, as the log under this lease holds it
        (`activity.declaration`)."""
        from leaf.records.activity import declaration

        return declaration(self.events)

    @property
    def stream(self) -> dict:
        return read_stream(self.page_dir)

    def _write_stream(self, stream: dict) -> None:
        """The one writer of `stream.json` (`service.STREAM`)."""
        STREAM.write(self.page_dir / STREAM_FILE, stream)

    def clear_stream(self) -> None:
        """Forget everything the harness observed of the claimant's task, as the
        agent's `idle` declaration does (`session.set_status`)."""
        if self.stream != no_stream():
            self._write_stream(no_stream())

    def set_stream_activity(
        self, session_id: str, turn_id: str, activity: dict
    ) -> None:
        """Record activity observed directly from the task's live event stream."""
        if self.status["state"] == "idle":
            return
        stream = self.stream
        now = now_iso()
        after = self.events[-1]["seq"] if self.events else 0
        previous = stream["activity"]
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
            and {**previous, "ts": now} == observed
            and datetime.fromisoformat(now) - datetime.fromisoformat(previous["ts"])
            < STREAM_ACTIVITY_RENEWAL
        ):
            return
        self._write_stream({**stream, "activity": observed})

    def clear_stream_activity(
        self, session_id: str, turn_id: str | None = None
    ) -> None:
        """Remove this task's live reading without changing its declaration."""
        stream = self.stream
        activity = stream["activity"]
        if not activity or activity["session"] != session_id:
            return
        if turn_id is not None and activity["turn"] != turn_id:
            return
        self._write_stream({**stream, "activity": None})

    def set_stream_reply(
        self,
        session_id: str,
        turn_id: str,
        address: dict,
        attempt: str,
        item_id: str | None,
        text: str,
        state: str,
        *,
        settles: bool = False,
    ) -> None:
        """Replace the provisional reply at a delivery's captured response address."""
        stream = self.stream
        claim = self.claim
        assert claim is not None
        previous = stream["reply"]
        timestamp = (
            previous["ts"]
            if previous
            and previous["session"] == session_id
            and previous["turn"] == turn_id
            else None
        )
        updated_at = now_iso()
        reply = {
            "session": session_id,
            "turn": turn_id,
            "attempt": attempt,
            "parent": address["parent"],
            "responds": address["responds"],
            "item": item_id,
            "text": text,
            "state": state,
            "settles": settles,
            "agent": claim["agent"],
            "ts": timestamp or updated_at,
            "updated_at": updated_at,
        }
        reservations = self._reserved(
            stream, session_id, address["responds"], attempt, turn_id
        )
        if previous == reply and reservations == stream["reply_reservations"]:
            return
        self._publish_stream_reply(
            {**stream, "reply_reservations": reservations}, previous, reply
        )

    def _publish_stream_reply(
        self, stream: dict, previous: dict | None, reply: dict
    ) -> None:
        """Publish provisional words and record their availability, not visibility.

        A nonblank transition records no text. Reconnects may repeat it; readers
        select the first observation for the exact input and attempt. Diagnostic
        I/O failure is reported without interrupting the published reply; explicit
        diagnostic ingestion still propagates write failures (`interaction_log`).
        """
        self._write_stream({**stream, "reply": reply})
        if reply["text"].strip() and (
            previous is None
            or not previous["text"].strip()
            or any(
                previous[key] != reply[key]
                for key in ("session", "turn", "attempt", "responds")
            )
        ):
            try:
                append_interactions(
                    self.page_dir,
                    [
                        {
                            "source": "server",
                            "type": "reply_stream_words",
                            "input_id": reply["responds"],
                            "parent": reply["parent"],
                            "attempt": reply["attempt"],
                            "session": reply["session"],
                            "turn": reply["turn"],
                            "agent": reply["agent"],
                            "context": session_context(reply["session"], self.claim),
                        }
                    ],
                )
            except OSError as error:
                print(
                    f"Stream diagnostic not written: {error}",
                    file=sys.stderr,
                    flush=True,
                )

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
        stream = self.stream
        claim = self.claim
        assert claim is not None
        reservations = self._reserved(
            stream, session_id, responds, attempt, claim["turn"]
        )
        if reservations != stream["reply_reservations"]:
            self._write_stream({**stream, "reply_reservations": reservations})

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
        reserved = self.open_reply_reservation(responds)
        if reserved is not None and not _held_by(reserved, session_id, attempt):
            raise RuntimeError(
                f"response {responds!r} is already reserved by another delivery"
            )
        return {
            **stream["reply_reservations"],
            responds: {"session": session_id, "attempt": attempt, "turn": turn_id},
        }

    def set_stream_reply_state(
        self,
        session_id: str,
        turn_id: str,
        attempt: str,
        text: str,
        state: str,
    ) -> bool:
        """Finish the matching displayed draft without changing its reservation."""
        stream = self.stream
        reply = stream["reply"]
        if not reply or (reply["session"], reply["turn"], reply["attempt"]) != (
            session_id,
            turn_id,
            attempt,
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
        if finished != reply:
            self._publish_stream_reply(stream, reply, finished)
        return True

    def clear_delivery_reply_reservation(
        self,
        session_id: str,
        responds: str,
        attempt: str,
    ) -> None:
        """Release one response address without changing its visible draft."""
        stream = self.stream
        reservations = dict(stream["reply_reservations"])
        if _held_by(reservations.pop(responds, None), session_id, attempt):
            self._write_stream({**stream, "reply_reservations": reservations})

    def clear_stream_reply(self, session_id: str, turn_id: str | None = None) -> None:
        """Remove this task's provisional reply without changing thread history."""
        stream = self.stream
        reply = stream["reply"]
        if not reply or reply["session"] != session_id:
            return
        if turn_id is not None and reply["turn"] != turn_id:
            return
        reservations = dict(stream["reply_reservations"])
        if _held_by(reservations.get(reply["responds"]), session_id, reply["attempt"]):
            del reservations[reply["responds"]]
        self._write_stream(
            {**stream, "reply": None, "reply_reservations": reservations}
        )

    @property
    def events(self) -> list:
        if self._events is None:
            self._events = read_events(self.page_dir)
        return self._events

    def _append_record(self, event: dict) -> dict:
        """Write one admitted record under this transaction's log lease.

        The lease is this class's to hold, so the write is this class's to make;
        what makes a record admissible is not. `event_contracts.append_admitted`
        is the one caller — every writer reaches the log through that door, and
        nothing else here may append."""
        try:
            return append_event_unlocked(
                self._log,
                event,
                self.events,
                context=session_context(event.get("session"), self.claim),
            )
        finally:
            self._events = None

    @property
    def cursor(self) -> int:
        return acknowledged(self.events)

    def watch_state(self, harness: Harness | None) -> str:
        holder = self.holder(harness.session if harness else None)
        if isinstance(holder, str) or not claimant_matches(holder, harness):
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


def take_page_claim(page_dir: Path) -> ClaimTransition | None:
    """Make the harness session the page's watcher, if a harness supplied one.

    `server start` and `page claim` claim; waiting and authoring commands do not.
    A bare-shell serve makes no claim and therefore starts as persistent.
    """
    from leaf.base.harness import session_harness

    harness = session_harness()
    if not harness:
        return None
    with PageTransaction(page_dir) as page:
        return page.take_claim(harness)


def claim_page(page_dir: Path) -> bool:
    return take_page_claim(page_dir) is not None


def restore_page_claim(page_dir: Path, transition: ClaimTransition | None) -> None:
    """Undo a failed startup's claim, provided no successor replaced it."""
    if transition is None:
        return
    with PageTransaction(page_dir) as page:
        page.restore_claim(transition)


def owned_pages(session_id: str | None) -> list:
    """Active pages owned by one session, or by every session when id is None."""
    pages = {
        Path(claim["page"])
        for claim in claim_records(session_id)
        if claim_is_active(claim) and initialized(Path(claim["page"]))
    }
    return sorted(pages, key=str)


def acknowledged(events: list) -> int:
    """The acknowledgement cursor: the seq this log's input is confirmed received
    through, the greatest `through` among its `receipt` events, or 0 before any.

    Receipt (`delivery.receive_batch`) writes the event under the page transaction
    in the log whose position it confirms, so a cursor is never past its own log's
    end, and a log `page init` starts afresh has none."""
    return max(
        (event["through"] for event in events if event["kind"] == "receipt"),
        default=0,
    )


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
