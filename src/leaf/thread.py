"""Thread writes, addressed response admission, and provider reply reservations."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import NamedTuple, Never

from leaf.activity import answer_command, reply_command
from leaf.delivery import (
    ReceiptRefused,
    current_responses,
    pickup_receipts,
    record_pickup,
    response_address,
)
from leaf.event_contracts import append_admitted
from leaf.event_log import read_events
from leaf.events import build_threads, is_answer
from leaf.files import (
    latest_revision,
    require_revision,
)
from leaf.findings import Finding, Rejected, note
from leaf.harness import message_identity
from leaf.leases import contract_writer
from leaf.obligations import local_obligation_entry, shown_in
from leaf.passages import SourceReading
from leaf.projection import (
    generated_children,
    page_reading,
    retirement_outcomes,
    rewritten_bodies,
)
from leaf.registry.contract import matches_when
from leaf.registry.kernel import kinds_declaring
from leaf.revision_artifact import active_enclosing, read_revision
from leaf.service import PageTransaction, delivery_reply_attempt, same_claim
from leaf.thread_context import thread_message, thread_names
from leaf.validation.admission import (
    check_markup,
    checked_text,
    logged_id,
    revision_publication,
    thread_obligation,
)
from leaf.validation.source import SourceCheck, moved_threads, source_advice


def _messages(events: list) -> dict[str, dict]:
    return {
        event["id"]: event
        for event in events
        if event["kind"] in kinds_declaring("message")
    }


def _unknown_message(page_dir: Path, events: list, name: str) -> Never:
    held = logged_id(page_dir, events, name, current_responses(page_dir, events))
    raise Rejected(
        [
            Finding(
                "unknown-comment",
                values={"name": name, "held": held, "known": sorted(_messages(events))},
            )
        ]
    )


def thread_addressed(page_dir: Path, events: list, name: str) -> tuple[str, str]:
    """The thread `name` names (`work.page_subject`), and the message a write into it
    names (`thread_context.thread_message`). Refuses a name that reaches no thread,
    with what the log holds it as instead, and a widget on the page."""
    from leaf.work import page_subject

    subject = page_subject(page_dir, events, name)
    if subject is None:
        _unknown_message(page_dir, events, name)
    if subject["kind"] == "widget":
        raise Rejected([Finding("widget-not-thread", values={"name": name})])
    return subject["id"], thread_message(events, subject["id"], name)


def thread_named(page_dir: Path, events: list, name: str) -> str:
    """The id of the thread `name` reaches."""
    return thread_addressed(page_dir, events, name)[0]


def reserve_delivery_reply(
    session_id: str,
    delivery_id: str,
    target: dict,
    *,
    expected_claim: dict | None = None,
) -> None:
    """Reserve a delivery's response address before provider execution begins."""
    attempt = delivery_reply_attempt(delivery_id)
    with PageTransaction(Path(target["page"])) as page:
        claim = page.active_claim
        if claim is None or claim["id"] != session_id:
            raise ReceiptRefused(f"page is not claimed by session {session_id!r}")
        if expected_claim is not None and not same_claim(claim, expected_claim):
            raise ReceiptRefused("the correction's page acquisition has ended")
        page.reserve_delivery_reply(session_id, target["responds"], attempt)


def release_delivery_reply(session_id: str, delivery_id: str, target: dict) -> None:
    """Give up a delivery's reserved response address without answering it.

    Reserving the address fences competing provider finals and failure receipts
    while an answer is still coming. A delivery that ends without ever reaching a
    provider turn has no such answer coming, and until the reservation is given up it
    also blocks the harness from saying so, so the user is left with neither.
    """
    _clear_delivery_reply(session_id, delivery_reply_attempt(delivery_id), target)


def _clear_delivery_reply(session_id: str, attempt: str, target: dict) -> None:
    try:
        with PageTransaction(Path(target["page"])) as page:
            page.clear_delivery_reply_reservation(
                session_id,
                target["responds"],
                attempt,
            )
    except FileNotFoundError:
        pass


def delivery_reply_reserved(session_id: str, delivery_id: str, target: dict) -> bool:
    """Whether this delivery's reservation of its reply address still stands."""
    try:
        with PageTransaction(Path(target["page"])) as page:
            reservation = page.open_reply_reservation(target["responds"])
            return bool(
                reservation is not None
                and reservation["session"] == session_id
                and reservation["attempt"] == delivery_reply_attempt(delivery_id)
            )
    except FileNotFoundError:
        return False


def thread_of(page_dir: Path, message_id: str) -> str:
    """The thread a message sits in, for a command that has to name it back."""
    return thread_names(read_events(page_dir))[message_id]


def current_anchor(
    page_dir: Path,
    events: list,
    quote: str,
    section: str,
    part: str,
    revision: int | None = None,
    *,
    transaction=None,
) -> tuple[int, dict | None]:
    """Capture one optional target against the page's active reading."""
    if revision is None:
        from leaf.revisioning import activate_source

        activation = activate_source(page_dir, transaction=transaction)
        if activation.error and (quote or section or part):
            raise Rejected(
                [
                    Finding(
                        "invalid-source",
                        values={"operation": "anchor", "error": activation.error},
                    )
                ]
            )
        revision = require_revision(page_dir)
    if not (quote or section or part):
        return revision, None
    from leaf.registry.storage import require_registry

    reading = read_revision(page_dir, revision).under(require_registry(page_dir))
    return revision, _capture_anchor(
        page_dir, events, reading, quote, section, part, revision
    )


def _capture_anchor(
    page_dir: Path,
    events: list,
    reading: SourceReading,
    quote: str,
    section: str,
    part: str,
    revision: int,
) -> dict:
    """Capture a target against one exact document reading."""
    from leaf.anchor_capture import capture_anchor

    page = page_reading(reading, events, revision)
    decided = retirement_outcomes(page.projection.actions)
    edited = rewritten_bodies(page.projection.actions)
    try:
        anchor = capture_anchor(
            page.document,
            page.registry,
            quote,
            section,
            decided,
            edited,
            part,
            additions=generated_children(page.projection.desired, page.document.ids),
        )
    except ValueError as err:
        held = (
            logged_id(page_dir, events, section, current_responses(page_dir, events))
            if section
            else None
        )
        raise Rejected(
            [
                Finding(
                    "unanchorable",
                    values={"revision": revision, "error": str(err), "held": held},
                )
            ]
        ) from err
    return anchor


@contract_writer
def cmd_comment(
    page_dir: Path,
    quote: str,
    section: str,
    part: str,
    text,
    markup: str,
    *,
    title: str | None = None,
    obligation: bool = False,
) -> dict:
    """Open a thread, as the user's own gestures do: on a passage where --quote or
    --section points at one, and on the page as a whole where neither does — the same
    anchorless shape the browser's general box posts, which is where a question about
    the work rather than a passage belongs. An anchor is captured against the active
    revision they are looking at and read as they see it: a slot
    their decision retired is off the page, and a draft they edited holds their words,
    so a quote is met here the way it would land there."""
    body = checked_text(page_dir, text)
    if markup:
        from leaf.render_gate.command import message_check

        # Apart from the page lease, since a browser run takes about a second.
        message_check(page_dir, "comment", markup)
    with PageTransaction(page_dir) as page:
        return open_thread(
            page_dir,
            page,
            body,
            quote,
            section,
            part,
            markup,
            title=title,
            obligation=obligation,
        )


def open_thread(
    page_dir: Path,
    page: PageTransaction,
    body: str,
    quote: str = "",
    section: str = "",
    part: str = "",
    markup: str = "",
    *,
    title: str | None = None,
    obligation: bool = False,
    identity: dict | None = None,
) -> dict:
    """The agent's thread opened in `page`, an open transaction, as `cmd_comment`
    describes, from a `body` already checked (`checked_text`); `identity` names the
    agent and session where the writer isn't the agent's own process, as Leaf's
    clerk is (`clerk.apply_answer`)."""
    events = page.events
    revision, anchor = current_anchor(
        page_dir, events, quote, section, part, transaction=page
    )
    if markup:
        check_markup(
            page_dir,
            "comment",
            markup,
            events,
            publication=revision_publication(page_dir, revision),
        )
    event = {
        "kind": "comment",
        "author": "agent",
        **(identity or {}),
        "revision": revision,
        "text": body,
    }
    if obligation:
        event["obligation"] = True
    if anchor:
        event["anchor"] = anchor
    if markup:
        event["markup"] = markup
    if title is not None:
        event["title"] = title
    return append_admitted(page, event)[0]


def successful_replies(events: list[dict], responds: str) -> list[dict]:
    """Agent answers to this exact input (`events.is_answer`)."""
    return [
        event for event in events if is_answer(event) and event["responds"] == responds
    ]


@dataclass(frozen=True)
class Refuse:
    """An ordinary writer's settlement: a stale or settled response address is
    refused, with what the log holds instead."""


@dataclass(frozen=True)
class ProviderFinal:
    """A provider turn's final message, committed at the address its delivery
    reserved (`reserve_delivery_reply`), or its opening, posted there as progress.

    It keeps that address after the user settled the update, but yields to an answer
    another writer already gave it (a failure receipt is no answer), so a turn's
    answer committed after its reservation lapsed never answers twice; and it writes
    nothing once another delivery holds the address."""

    reservation: str


@dataclass(frozen=True)
class Receipt:
    """A harness's failure receipt: an update that no longer owes an answer takes
    none. With `only_if_unclaimed`, an update some turn already picked up is left to
    the writer following that turn."""

    only_if_unclaimed: bool


Settlement = Refuse | ProviderFinal | Receipt
REFUSE = Refuse()


class _Obligation(NamedTuple):
    """Where a reply goes once its address has been checked against the log."""

    parent: str
    thread: str
    responds: str | None
    # The update a progress reply takes in hand, if it owes one.
    in_hand: str | None


@contract_writer
def post_reply(
    page_dir: Path,
    address: dict,
    text,
    markup: str = "",
    *,
    settlement: Settlement = REFUSE,
    attempt: str | None = None,
    identity: dict | None = None,
    claimed_session: str | None = None,
    failure: str | None = None,
    validate_source: bool = False,
    todo: str | None = None,
    asks_back: bool = False,
    obligation: bool = False,
    ephemeral: bool = False,
    quote: str = "",
    section: str = "",
    part: str = "",
    detach: bool = False,
    title: str | None = None,
) -> dict | None:
    """Post one complete threaded reply, optionally moving or detaching its anchor;
    the appended record, or the earlier reply a repeated `attempt` names, or none
    when `settlement` leaves nothing to write.

    ``address`` takes the fields of a response address (`delivery.response_address`):
    ``responds`` fences the write to that exact current obligation, and ``parent``
    names the message it threads under (`obligations.response_address`). ``parent``
    alone posts a new agent message, which the thread must currently owe no reply
    for, and the event then carries no ``responds``. ``input`` and ``claim``, which
    a delivery captured, fence it to that page log and delivery owner.

    A repeated ``attempt`` is matched more loosely than the append door's payload
    identity: by kind, progress, failure receipt or answer, response address and
    declaration, so a CLI retry whose text was reworded returns the first reply
    rather than refusing.

    ``failure`` records a harness-owned failure code alongside its presentation text;
    ordinary agent answers omit it.

    ``todo`` titles work the reply promises and does not deliver: the reply opens
    that to-do on its thread, under the reply's own id (`todos.todo_reading`), so
    the user's message is answered and the work stays on the agent in one write.

    ``ephemeral`` posts progress at the same response address without answering it.
    It remains content, and cannot carry an obligation, a to-do, widgets, failure or
    relocation. Progress on an update the agent owes says what it has in hand, so it also takes that
    update in hand with its text as the line (`todos.start_reading`), which is why that
    text is one line: the update reads Working beside its thread and in the page's status, and
    the user's message gets the agent's first words and its Working line from one
    write.
    """
    text = checked_text(page_dir, text)
    if markup:
        from leaf.render_gate.command import message_check

        # Apart from the page lease, since a browser run takes about a second.
        message_check(page_dir, "reply", markup)
    posting_identity = message_identity() if identity is None else identity
    with PageTransaction(page_dir) as page:
        if claimed_session is not None:
            claim = page.claim_of(claimed_session)
            if claim is None:
                raise ReceiptRefused(
                    f"page is no longer claimed by session {claimed_session!r}"
                )
            posting_identity = {"agent": claim["agent"], "session": claim["id"]}
        captured = address.get("input")
        if captured is not None:
            if address["claim"] != page.delivery_owner:
                raise ReceiptRefused(
                    "response page claim no longer matches its delivery"
                )
            if not any(
                event["id"] == captured["id"] and event["seq"] == captured["seq"]
                for event in page.events
            ):
                raise ReceiptRefused("response no longer matches its page log")
        if attempt is not None and (
            repeated := _repeated_reply(
                page.events,
                attempt,
                address,
                ephemeral,
                failure is not None,
                todo,
                obligation,
            )
        ):
            return repeated
        addressed = _resolve_obligation(
            page,
            address,
            settlement,
            posting_identity.get("session"),
            ephemeral,
            failure,
        )
        if addressed is None:
            return None
        record, published = _compose_and_append(
            page,
            addressed,
            posting_identity,
            text,
            markup,
            attempt=attempt,
            failure=failure,
            validate_source=validate_source,
            todo=todo,
            asks_back=asks_back,
            explicit_obligation=obligation,
            ephemeral=ephemeral,
            quote=quote,
            section=section,
            part=part,
            detach=detach,
            title=title,
        )
    if published is not None:
        # Read apart from the page lease, so the user's page sees the reply at once.
        note(*_revision_advice(page_dir, published))
    return record


class _Published(NamedTuple):
    """A successful reply's checked publication: its preceding log, the revision,
    the source check, and the thread the reply moves itself, if it does."""

    events: list
    revision: int
    checked: SourceCheck
    moving_thread: str | None


def _revision_advice(page_dir: Path, published: _Published) -> list[Finding]:
    """What `page check` would advise on the revisions published since the agent's
    last successful reply, which the first successful reply on a revision reports
    beside its result; nothing for a later reply. Failure reports can name the
    active revision without checking source, so they neither emit nor consume advice.
    Progress carries no revision: it cannot include markup or move a thread.

    A successful reply publishes the source it checked, so a revision that answers a
    message needs no check before its reply. It names the threads those revisions
    moved (`validation.source.moved_threads`) other than one it moves itself."""
    events, checked = published.events, published.checked
    last = max(
        (
            event.get("revision", 0)
            for event in events
            if event["kind"] == "reply"
            and event["author"] == "agent"
            and "failure" not in event
        ),
        default=0,
    )
    if published.revision <= last:
        return []
    return [
        *(
            finding
            for finding in moved_threads(page_dir, events, last, checked)
            if finding.values["thread"] != published.moving_thread
        ),
        *source_advice(page_dir, checked),
    ]


def _repeated_reply(
    events: list,
    attempt: str,
    address: dict,
    ephemeral: bool,
    failed: bool,
    todo: str | None,
    obligation: bool,
) -> dict | None:
    """The reply an earlier write with this `attempt` appended, or None; refuses an
    attempt that named another kind of write: progress, a failure receipt and an
    answer are each their own."""
    existing = next(
        (event for event in events if event.get("attempt") == attempt), None
    )
    if existing is None:
        return None
    parent, responds = address.get("parent"), address.get("responds")
    same_scope = (
        existing.get("responds") == (None if ephemeral else responds)
        if responds is not None or parent is not None
        else True
    )
    if (
        existing["kind"] != "reply"
        or bool(existing.get("ephemeral")) != ephemeral
        or ("failure" in existing) != failed
        or (parent is not None and existing["parent"] != parent)
        or not same_scope
    ):
        raise Rejected([Finding("attempt-conflict", values={"attempt": attempt})])
    if existing.get("todo") != todo or bool(existing.get("obligation")) != obligation:
        # A repeat that promises differently would otherwise return the first
        # answer and drop what this one declares.
        raise Rejected(
            [Finding("redeclared-answer", values={"message": existing["id"]})]
        )
    return existing


def _resolve_obligation(
    page: PageTransaction,
    address: dict,
    settlement: Settlement,
    session: str | None,
    ephemeral: bool,
    failure: str | None,
) -> _Obligation | None:
    """Check `address` against the obligations the log holds now; where the reply
    goes, or None where `settlement` says to write nothing."""
    page_dir, events = page.page_dir, page.events
    parent, responds = address.get("parent"), address.get("responds")
    if (
        isinstance(settlement, ProviderFinal)
        and responds is not None
        and successful_replies(events, responds)
    ):
        return None
    responses = current_responses(page_dir, events)
    expected = responses.get(responds)
    if responds is not None and parent is None:
        if expected is None or expected["kind"] != "reply":
            if isinstance(settlement, Receipt):
                return None
            held = logged_id(page_dir, events, responds, responses)
            raise Rejected(
                [Finding("unowed-reply", values={"event": responds, "held": held})]
            )
        parent = expected["parent"]
    assert parent is not None
    thread_id, parent = thread_addressed(page_dir, events, parent)
    in_hand = None
    if responds is not None:
        if (
            expected is None
            or expected["kind"] != "reply"
            or expected["parent"] != parent
        ):
            if isinstance(settlement, Receipt):
                return None
            if not isinstance(settlement, ProviderFinal):
                held = logged_id(page_dir, events, responds, responses)
                raise Rejected(
                    [
                        Finding(
                            "superseded-reply",
                            values={"event": responds, "parent": parent, "held": held},
                        )
                    ]
                )
        elif ephemeral:
            in_hand = responds
        # The open reply reservation decides who may write, whatever the
        # captured `writer` hint or a caller-supplied retry key says.
        reserved = page.open_reply_reservation(responds)
        if reserved is not None:
            if isinstance(settlement, ProviderFinal):
                if (session, settlement.reservation) != (
                    reserved["session"],
                    reserved["attempt"],
                ):
                    return None
            elif not ephemeral and (
                address.get("input") is None or failure is not None
            ):
                assert expected is not None
                raise Rejected(
                    [
                        Finding(
                            "reserved-answer",
                            values={
                                "event": responds,
                                "command": reply_command(expected, page_dir),
                                "failure": failure is not None,
                            },
                        )
                    ]
                )
    else:
        owed = thread_obligation(events, responses, thread_id)
        if owed is not None:
            raise Rejected(
                [
                    Finding(
                        "owed-response",
                        values={
                            "thread": thread_id,
                            "answer": answer_command(owed, page_dir),
                        },
                    )
                ]
            )
    if (
        isinstance(settlement, Receipt)
        and settlement.only_if_unclaimed
        and pickup_receipts(events, phase=None, input_id=responds)
    ):
        return None
    return _Obligation(parent, thread_id, None if ephemeral else responds, in_hand)


def _compose_and_append(
    page: PageTransaction,
    obligation: _Obligation,
    posting_identity: dict,
    text: str,
    markup: str,
    *,
    attempt: str | None,
    failure: str | None,
    validate_source: bool,
    todo: str | None,
    asks_back: bool,
    explicit_obligation: bool,
    ephemeral: bool,
    quote: str,
    section: str,
    part: str,
    detach: bool,
    title: str | None,
) -> tuple[dict, "_Published | None"]:
    """Check the reply's content against the page, compose its event and append it
    at `obligation`. Successful replies publish saved edits when `validate_source`
    requests it. Progress and failure reports use the active revision; detaching
    still checks saved source. Return the appended record and any checked
    publication for `_revision_advice` to read."""
    page_dir, events = page.page_dir, page.events
    parent, thread_id, responds, in_hand = obligation
    event = {
        "kind": "reply",
        "author": "agent",
        **posting_identity,
        "parent": parent,
        "text": text,
        **({"responds": responds} if responds is not None else {}),
    }
    opening = _messages(events)[thread_id]
    moving = bool(quote or section or part)
    if ephemeral and (
        todo or explicit_obligation or markup or failure or moving or detach
    ):
        raise Rejected([Finding("ephemeral-content")])
    if detach and moving:
        raise Rejected([Finding("detach-with-target")])
    relocating = moving or detach
    if relocating and opening.get("holds"):
        raise Rejected([Finding("held-anchor", values={"thread": thread_id})])
    current_thread = (
        build_threads(events, active_enclosing(page_dir)).get(thread_id)
        if detach
        else None
    )
    if detach and (current_thread is None or current_thread["anchor"] is None):
        raise Rejected([Finding("no-anchor", values={"thread": thread_id})])
    reply_revision = None
    prospective_anchor = None
    source_events = events
    checked = None
    if (validate_source and not ephemeral and failure is None) or detach:
        if relocating:
            source_events = [
                *events,
                {
                    **event,
                    "id": "prospective-anchor-transition",
                    "seq": events[-1]["seq"] + 1,
                    "ts": "pending",
                    "anchor": None,
                },
            ]
        from leaf.revisioning import planned_activation
        from leaf.validation.source import check_source

        checked = check_source(page_dir, source_events)
        if checked.errors:
            raise Rejected(
                [
                    Finding(
                        "invalid-source",
                        values={
                            "operation": "reply" if validate_source else "detach",
                            "error": "; ".join(map(str, checked.errors)),
                        },
                    )
                ]
            )
        reply_revision = planned_activation(page_dir, checked).revision
        assert reply_revision is not None
        if moving:
            prospective_anchor = _capture_anchor(
                page_dir,
                events,
                checked.reading,
                quote,
                section,
                part,
                reply_revision,
            )
    if prospective_anchor is not None:
        revision, anchor = reply_revision, prospective_anchor
    elif moving:
        revision, anchor = current_anchor(
            page_dir,
            events,
            quote,
            section,
            part,
            revision=require_revision(page_dir)
            if failure is not None
            else reply_revision,
            transaction=page,
        )
    elif detach:
        revision, anchor = reply_revision, None
    else:
        revision, anchor = None, None
    if relocating or markup:
        revision = revision or latest_revision(page_dir)
    if markup:
        # Every route that publishes saved edits has published or planned them by
        # now, so the markup is checked under the reading the reply is stored with.
        publication = (
            checked.reading
            if checked is not None
            else revision_publication(page_dir, revision)
        )
        fragment = check_markup(
            page_dir,
            "reply",
            markup,
            events,
            publication=publication,
            thread=thread_id,
        )
    # A markup-only answer must itself request input. Explicit obligations need
    # no widget: the message is their source.
    if (
        asks_back
        and not explicit_obligation
        and not (
            markup
            and any(
                local_obligation_entry(publication.registry.get(rec["tag"]) or {})
                and matches_when(
                    rec["attrs"],
                    publication.registry[rec["tag"]]["x-awaits"].get("when"),
                )
                and not shown_in(rec, publication.registry)
                for rec in fragment.lf_elements
            )
        )
    ):
        raise Rejected([Finding("undeclared-answer")])
    if ephemeral:
        event["ephemeral"] = True
    if in_hand is not None:
        claim = page.claim
        turn = (
            claim["turn"]
            if claim and claim["id"] == posting_identity.get("session")
            else None
        )
        event["start"] = {
            "item": in_hand,
            **({"turn": turn} if turn else {}),
        }
    if explicit_obligation:
        event["obligation"] = True
    if todo is not None:
        event["todo"] = todo
    if markup:
        event["markup"] = markup
    if attempt is not None:
        event["attempt"] = attempt
    if failure is not None:
        event["failure"] = failure
    if relocating or markup:
        event["revision"] = revision
    if relocating:
        event["anchor"] = anchor
    if title is not None:
        event["title"] = title
    published = None
    if checked is not None:
        from leaf.revisioning import publish_checked_event

        record = publish_checked_event(page, checked, event)
        if failure is None:
            published = _Published(
                events, record["revision"], checked, thread_id if relocating else None
            )
    else:
        record, _ = append_admitted(page, event)
    return record, published


def post_response(
    reference: str, text, markup: str = "", *, reservation: str | None = None, **options
) -> dict | None:
    """Author a complete reply at the delivery's exact captured response address.

    The reference chooses page, input and frozen thread destination. All rich reply
    options belong to the durable writer. A direct write refuses a superseded input;
    a provider's final (`reservation`, `ProviderFinal`) preserves its captured
    destination after user settlement but yields to another successful answer.
    Explicit addressed replies commit immediately; reservations prevent competing
    provider finals and failure receipts.

    Each write's retry key (`post_reply`'s `attempt`) is derived here, never given:
    the reservation for a provider's answer and the reservation's progress line for
    its progress, so a provider's repeat returns the first; without a reservation,
    the reference, in disjoint namespaces for answers and failure receipts so a
    receipt's key never stands in for a later answer's. Progress without a
    reservation takes no key, so each line posts.
    """
    address = response_address(reference)
    if address["kind"] != "reply":
        raise Rejected(
            [
                Finding(
                    "not-a-reply",
                    values={
                        "reference": reference,
                        "answer": answer_command(address, Path(address["page"])),
                    },
                )
            ]
        )
    ephemeral = options.get("ephemeral", False)
    if reservation is not None:
        attempt = f"{reservation}-progress" if ephemeral else reservation
    elif ephemeral:
        attempt = None
    else:
        namespace = "failure" if options.get("failure") is not None else "response"
        attempt = f"leaf-{namespace}-{sha256(reference.encode()).hexdigest()}"
    return post_reply(
        Path(address["page"]),
        address,
        text,
        markup,
        settlement=REFUSE if reservation is None else ProviderFinal(reservation),
        attempt=attempt,
        validate_source=True,
        **options,
    )


def fail_answer(
    page_dir: Path,
    responds: str,
    failure: str,
    text: str,
    *,
    attempt: str,
    identity: dict,
    only_if_unclaimed: bool,
    claimed_session: str | None = None,
) -> dict | None:
    """Tell the user no answer to one update is coming, in the update's own terms.

    A harness that gives up on an update settles the obligation the update's workflow
    `answer` names and hands the next step back to the user, so a failed update is
    never left owed with nobody to answer it:

    - a `reply` answer takes a reply carrying `failure` in its thread, which
      the user resends into; an open reply reservation refuses it until its
      turn gives the reply up;
    - a `markup` answer takes a failed pickup: the user's answer to the obligation stands in the log,
      and answering again sends a new answer.

    An update with no answer outstanding writes nothing, except that a repeated reply
    receipt is found by its `attempt` and returned. `only_if_unclaimed` leaves an update
    some turn already picked up to the writer following that turn.
    """
    with PageTransaction(page_dir) as page:
        if claimed_session is not None and page.claim_of(claimed_session) is None:
            raise ReceiptRefused(
                f"page is no longer claimed by session {claimed_session!r}"
            )
        answer = current_responses(page_dir, page.events).get(responds)
    if answer is not None and answer["kind"] == "markup":
        return _fail_markup_answer(
            page_dir, responds, failure, only_if_unclaimed, claimed_session
        )
    return post_reply(
        page_dir,
        {"responds": responds},
        text,
        settlement=Receipt(only_if_unclaimed),
        attempt=attempt,
        failure=failure,
        identity=identity,
        claimed_session=claimed_session,
    )


@contract_writer
def _fail_markup_answer(
    page_dir: Path,
    responds: str,
    failure: str,
    only_if_unclaimed: bool,
    claimed_session: str | None,
) -> dict | None:
    """Record a failed pickup of a page action, rechecking its answer under the lock."""
    with PageTransaction(page_dir) as page:
        if claimed_session is not None and page.claim_of(claimed_session) is None:
            raise ReceiptRefused(
                f"page is no longer claimed by session {claimed_session!r}"
            )
        events = page.events
        answer = current_responses(page_dir, events).get(responds)
        if answer is None or (
            only_if_unclaimed and pickup_receipts(events, phase=None, input_id=responds)
        ):
            return None
        [update] = [event for event in events if event["id"] == responds]
        return record_pickup(page, [update], phase="failed", failure=failure)


def title_event(thread: str, title: str, identity: dict | None = None) -> dict:
    """The `thread_title` event naming `thread`, in the voice of `identity` where one
    is given; without one, admission gives it the posting session's
    (`event_contracts.voiced`)."""
    return {
        "kind": "thread_title",
        "author": "agent",
        **(identity or {}),
        "thread": thread,
        "title": title,
    }


def name_untitled(page, thread: str, title: str, identity: dict) -> dict | None:
    """Append `thread`'s first title in the voice of `identity`, within the caller's
    page transaction, or nothing where it has one: a name given once stands until
    someone renames the thread on purpose (`cmd_edit`)."""
    if (
        build_threads(page.events, active_enclosing(page.page_dir))[thread]["title"]
        is not None
    ):
        return None
    return append_admitted(page, title_event(thread, title, identity))[0]


@contract_writer
def cmd_edit(
    page_dir: Path, message: str, text, *, title: str | None = None
) -> list[dict]:
    """Append a text revision to one agent-authored message, rename the thread it is
    in, or both, and return the records appended.

    The message event is immutable: the edit points back to it, so the log retains
    every wording while thread folds project the latest one. Markup stays frozen with
    the original message because user actions may already rest on widgets it sent.
    Admission refuses a message another voice wrote (`event_contracts._edit_error`).
    A rename adds no turn and changes no obligation. Under one lease, the rename is
    admitted before the edit is appended, so a refused title leaves the text unedited.
    """
    from leaf.event_contracts import admitted_event, voiced
    from leaf.page_view import PageView
    from leaf.registry.storage import require_registry

    body = checked_text(page_dir, text) if text is not None or title is None else None
    with PageTransaction(page_dir) as page:
        require_registry(page_dir)
        named = None
        if title is not None:
            thread = thread_named(page_dir, page.events, message)
            named = title_event(thread, title)
            admitted_event(PageView(page_dir), page.events, voiced(named))
        records = []
        if body is not None:
            edit = {
                "kind": "edit",
                "author": "agent",
                "message": message,
                "text": body,
            }
            records.append(append_admitted(page, edit)[0])
        if named is not None:
            records.append(append_admitted(page, named)[0])
        return records


@contract_writer
def cmd_summarize(
    page_dir: Path,
    from_message: str,
    through_message: str,
    text,
    *,
    label: str | None = None,
) -> dict:
    """Append a presentation summary over one contiguous message range, in the
    thread its first message sits in."""
    from leaf.registry.storage import require_registry

    body = checked_text(page_dir, text, allow_empty=True)
    with PageTransaction(page_dir) as page:
        require_registry(page_dir)
        record, _ = append_admitted(
            page,
            {
                "kind": "summary",
                "author": "agent",
                "thread": thread_named(page_dir, page.events, from_message),
                "from": from_message,
                "through": through_message,
                "text": body,
                **({"label": label} if label is not None else {}),
            },
        )
        return record


@contract_writer
def cmd_resolve(page_dir: Path, parent: str) -> dict:
    """Close a thread, as the user's own ✓ Resolve does. Same event, same rule on
    `parent` — any message in the thread names it — and `author` the whole
    difference, which is how the panel can say who closed it."""
    with PageTransaction(page_dir) as page:
        _thread_id, parent = thread_addressed(page_dir, page.events, parent)
        event = {
            "kind": "resolve",
            "author": "agent",
            "parent": parent,
        }
        return append_admitted(page, event)[0]
