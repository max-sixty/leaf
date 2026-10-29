"""Page claims, serialized transactions, the agent's declaration, and its stream.

The transaction holds the page's append lease; what may be appended under it is
`event_contracts`' to say. Cold harness hooks read claims, and Codex's tool hook
opens a transaction after every tool call, so process inspection and page-event
semantics are imported only by their callers. A transaction finishes interrupted
publications before admitting a reader. Hosts may declare LEAF_PAGE_COMMIT as a
module:function provider; successful completion calls it under the same append
lease, and provider failure prevents the caller from acknowledging success.

The agent's `waiting` or `idle` declaration is a `status` event in the log
(`set_status`, read by `activity.declaration`). What the harness observes of the
claimant's task as it runs, its live activity, the reply it drafts and the response
addresses it has reserved, is `stream.json` (`STREAM`). It stays out of the log: it
changes several times a second while a turn streams, means nothing once that turn
has ended, and a reservation fences competing writers of one answer."""

from __future__ import annotations

import hashlib
import importlib
import os
import secrets
import sys
from contextlib import contextmanager, nullcontext
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from leaf.event_log import (
    _append_event_unlocked,
    _matching_attempt,
    _parse_events,
)
from leaf.files import read_json, unfinished_publications
from leaf.interaction_log import append_interactions, session_context
from leaf.machine import pid_alive, sandbox_remedy
from leaf.refusals import Refused
from leaf.schema import STREAM_FILE
from leaf.state import (
    EVENTS_FILE,
    STRING,
    TIME,
    Record,
    chat_exists,
    claims_lock,
    described,
    drop_locator,
    ensure_session,
    flocked,
    fsync_parents,
    held_claims,
    now_iso,
    object_schema,
    page_key,
    page_stands,
    remove_claim,
    session_claims,
    session_live,
    session_lock_path,
    session_record,
    standing_claims,
    state_home,
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


CLAIM = Record(
    "claim",
    described(
        "The session that receives a page's updates, in the state home's "
        "`claims/<page key>.json` (`claim_path`).",
        object_schema(
            {
                "page": described("The page directory.", STRING),
                "ts": described("When the claim was published.", TIME),
                "id": described("The claimant session (`state.SESSION`).", STRING),
                "generation": described(
                    "The generation of the session this claim names.", STRING
                ),
                "acquisition": described(
                    "This publication's own identity (`same_claim`).", STRING
                ),
                "harness": described("The claimant's `Harness.name`.", STRING),
                "agent": described("The name the claimant shows.", STRING),
                "cwd": described("The claimant's working directory.", STRING),
            },
            {
                "messaged_ending": described(
                    "The turn ending after which input last messaged the session "
                    "(`note_messaged`).",
                    STRING,
                )
            },
        ),
    ),
    since=13,
)


def publish_claim(page_dir: Path, claim: dict) -> None:
    """Prepare discovery, then commit ownership in the canonical payload: the one
    writer of a claim.

    Discovery validates the payload's owner against the partition. A transfer's
    old locator therefore stops being current at the canonical commit, which also
    admits the prepared new locator. Failed preparation leaves ownership intact.
    Resident writers retain the same flat payload path, so their atomic updates
    cannot destroy discovery. The claims lock keeps a retirement from removing
    what this publishes (`state.retire_claim`).
    """
    path = claim_path(page_dir)
    locator = session_claims(claim["id"]) / path.name
    with flocked(claims_lock()):
        locator.parent.mkdir(parents=True, exist_ok=True)
        previous = CLAIM.read(path)
        staged = locator.with_name(f".{secrets.token_hex(8)}.tmp")
        try:
            staged.symlink_to(Path("..") / path.name)
            os.replace(staged, locator)
            fsync_parents([locator])
        finally:
            staged.unlink(missing_ok=True)
        CLAIM.write(path, claim)
        if previous is not None and previous["id"] != claim["id"]:
            drop_locator(previous["id"], path.name)


# The keys a claim's reading takes from its session's lifetime (`claim_reading`).
CLAIM_LIFETIMES = frozenset({"job", "app", "chat", "pid"})


def claim_reading(claim: dict | None) -> dict | None:
    """A claim as its readers take it: the record, with its session's lifetime and
    turn while the session is still in the generation the claim names.

    A claim naming a harness this Leaf does not know, as a later Leaf's may, reads
    as no claim: the name is a value this Leaf dispatches on
    (`harness.claim_harness`). Every reader goes through `page_claim` or
    `claim_records`."""
    from leaf.harness import HARNESSES

    if claim is None or claim["harness"] not in HARNESSES:
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
    return claim_reading(CLAIM.read(claim_path(page_dir)))


def claim_is_active(claim: dict | None) -> bool:
    """Whether a claim still names a live owner: its session's generation, not
    ended, with a lifetime that still lives (`lifetime_is_live`). Cold hooks and
    the CLI both call it."""
    if not claim:
        return False
    record = session_record(claim["id"])
    if not session_live(record) or record["generation"] != claim["generation"]:
        return False
    return lifetime_is_live(claim, record)


def lifetime_is_live(lifetime: dict, record: dict | None) -> bool:
    """Whether the owner a `Harness.lifetime` names still lives: the job record a
    background job's lifetime points at, the Claude desktop app's record an `app`
    lifetime points at while it is unarchived and still names the session, the
    native source a persisted `chat` stands on (`record`, the session's), or the
    process every other lifetime's pid names. The only reading of that rule: a claim and the sandbox
    bridge's registrations both carry a lifetime beside the session's `id`, so a
    harness that states its lifetime a new way joins here alone."""
    if "job" in lifetime:
        return (Path(lifetime["job"]) / "state.json").is_file()
    if "app" in lifetime:
        app = read_json(Path(lifetime["app"]))
        return (
            app is not None
            and not app["isArchived"]
            and app["cliSessionId"] == lifetime["id"]
        )
    if lifetime.get("chat") is True:
        return chat_exists(record)
    return "pid" in lifetime and pid_alive(lifetime["pid"])


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
    return session_live(session_record(session_id))


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

    Payloads are canonical by page. A named lookup reads only through the
    locators whose payloads name that session (`state.held_claims`), and opens no
    unrelated claim file; the unnamed scan reads every payload
    (`state.standing_claims`). Each retires the claims it finds on pages that are
    gone."""
    paths = held_claims(session_id) if session_id else standing_claims()
    claims = []
    for path in paths:
        claim = claim_reading(CLAIM.read(path))
        if (
            claim is not None
            and claim_path(Path(claim["page"])) == path.resolve()
            and (session_id is None or claim["id"] == session_id)
            and page_stands(Path(claim["page"]))
        ):
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

        reservation = self.stream["reply_reservations"].get(responds)
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
            projected = claim_reading(claim)
            if not claim_is_active(projected):
                raise Refused(dead_session(projected))
            previous = self.claim
            yield previous, projected
            publish_claim(self.page_dir, claim)

    def restore_claim(self, expected: dict, previous: dict | None) -> None:
        """Roll back one failed claim without erasing a successor's."""
        if not same_claim(self.claim, expected):
            return
        path = claim_path(self.page_dir)
        if previous is None:
            remove_claim(path)
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
        turn, from browser-event admission, from
        a watch giving up its lease, or from the page's server reading a turn
        interrupted, and a watch that wakes the session marks the ending too
        (`session.woke_after`). `ending` names the claim's turn id
        and its close stamp, or for an interrupted turn its last opening, so a
        later ending, whether a close under a new id or an interrupt after a new
        prompt renewed the same one, never matches the ending a message already
        went out for."""
        claim = CLAIM.read(claim_path(self.page_dir))
        publish_claim(self.page_dir, {**claim, "messaged_ending": ending})

    @property
    def status(self) -> dict:
        """The agent's declaration, as the log under this lease holds it
        (`activity.declaration`)."""
        from leaf.activity import declaration

        return declaration(self.events)

    @property
    def stream(self) -> dict:
        return read_stream(self.page_dir)

    def _write_stream(self, stream: dict) -> None:
        """The one writer of `stream.json` (`STREAM`)."""
        STREAM.write(self.page_dir / STREAM_FILE, stream)

    def set_status(self, state: str) -> dict:
        """Append the page's `waiting` or `idle` declaration, a `status` event in the
        posting session's voice, and return the record.

        The work the agent has in hand is no status: it is the log's `start` events,
        and a declaration puts every start before it down (`todos.item_starts`). The
        stream the harness observes carries across a `waiting`, and `idle` clears it
        with the leaf."""
        from leaf.event_contracts import append_admitted

        record, _ = append_admitted(
            self,
            {
                "kind": "status",
                "author": "agent",
                "state": state,
            },
        )
        if state == "idle" and self.stream != no_stream():
            self._write_stream(no_stream())
        return record

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
            "agent": self.claim["agent"],
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
        reservations = self._reserved(
            stream, session_id, responds, attempt, self.claim["turn"]
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
            return _append_event_unlocked(
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


def cmd_claim(page_dir: Path, *, manual_delivery: bool = False) -> dict:
    """Connect delivery before publishing ownership, without starting a server.

    An explicit watcher claims with manual_delivery before its first wait. Hooks do
    not prepare adapters, so this interval leaves delivery to that watcher; once its
    wait is live, ordinary serving and reclaiming preserve the selected watch.
    """
    from leaf.harness import session_harness

    harness = session_harness()
    if harness is None:
        raise Refused("only an agent harness session can claim a page")
    preparation = nullcontext() if manual_delivery else harness.preparing_delivery()
    with preparation, PageTransaction(page_dir) as page:
        page.take_claim(harness)
    return {"session": harness.session}


def restore_page_claim(
    page_dir: Path, transition: tuple[dict | None, dict] | None
) -> None:
    """Undo a failed startup's claim, provided no successor replaced it."""
    if transition is None:
        return
    previous, expected = transition
    with PageTransaction(page_dir) as page:
        page.restore_claim(expected, previous)


def no_stream() -> dict:
    """The stream while the harness observes nothing of the claimant's task: no live
    activity, no reply it is drafting, and no response address it has reserved
    (`delivery` header)."""
    return {"activity": None, "reply": None, "reply_reservations": {}}


_TURN = {
    "session": described("The claimant session the harness observed.", STRING),
    "turn": described("The turn it observed.", STRING),
}
STREAM = Record(
    "stream",
    described(
        "What the harness observes of the claimant's task as it runs, in the page "
        "directory's `stream.json`; `no_stream` while it observes nothing.",
        object_schema(
            {
                "activity": described(
                    "What the task is doing now (`set_stream_activity`), or null.",
                    {
                        **object_schema(
                            {
                                **_TURN,
                                "kind": described(
                                    "The step observed; the page reads one of "
                                    "`activity.WORK_KINDS`.",
                                    STRING,
                                ),
                                "ts": described("When it was last observed.", TIME),
                                "after": described(
                                    "The log's last `seq` when it was observed.",
                                    {"type": "integer"},
                                ),
                            },
                            {"detail": described("What the step names.", STRING)},
                        ),
                        "type": ["object", "null"],
                    },
                ),
                "reply": described(
                    "The reply it is drafting (`set_stream_reply`), or null.",
                    {
                        **object_schema(
                            {
                                **_TURN,
                                "attempt": described(
                                    "The delivery attempt it is drafted under.",
                                    STRING,
                                ),
                                "parent": described(
                                    "The thread it replies in.", STRING
                                ),
                                "responds": described("The input it answers.", STRING),
                                "item": described(
                                    "The harness's id for the message supplying the "
                                    "draft, or null while none is attached.",
                                    {"type": ["string", "null"]},
                                ),
                                "text": described("Its words so far.", STRING),
                                "state": STRING,
                                "settles": {"type": "boolean"},
                                "agent": described(
                                    "The name the claimant shows.", STRING
                                ),
                                "ts": described("When the draft began.", TIME),
                                "updated_at": described(
                                    "When the draft last changed.", TIME
                                ),
                            }
                        ),
                        "type": ["object", "null"],
                    },
                ),
                "reply_reservations": described(
                    "Each open reply reservation, by the response address it holds "
                    "(`thread.reserve_delivery_reply`).",
                    {
                        "type": "object",
                        "additionalProperties": object_schema(
                            {**_TURN, "attempt": STRING}
                        ),
                    },
                ),
            }
        ),
    ),
    since=16,
)


def read_stream(page_dir: Path) -> dict:
    """The page's stream, `stream.json`, as every reader takes it, or `no_stream`
    before the first write."""
    return STREAM.read(page_dir / STREAM_FILE) or no_stream()


def owned_pages(session_id: str | None) -> list:
    """Active pages owned by one session, or by every session when id is None."""
    pages = {
        Path(claim["page"])
        for claim in claim_records(session_id)
        if claim_is_active(claim) and (Path(claim["page"]) / EVENTS_FILE).is_file()
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
