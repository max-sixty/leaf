"""Thread writes, addressed response admission, and provider reply reservations."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import NamedTuple

from leaf.activity import answer_command
from leaf.delivery import (
    ReceiptRefused,
    current_responses,
    pickup_receipts,
    record_pickup,
    response_address,
)
from leaf.event_contracts import append_admitted
from leaf.event_log import read_events
from leaf.events import build_threads
from leaf.files import (
    latest_revision,
    require_revision,
    revision_path,
)
from leaf.harness import message_identity
from leaf.leases import contract_writer
from leaf.passages import SourceReading
from leaf.projection import (
    generated_children,
    page_reading,
    retirement_outcomes,
    rewritten_bodies,
)
from leaf.questions import asking, local_question_entry, quoted_in
from leaf.refusals import Refused
from leaf.registry.schema import json_value
from leaf.revision_artifact import active_enclosing, read_revision
from leaf.schema import MESSAGE_KINDS
from leaf.service import PageTransaction, delivery_reply_attempt, same_claim
from leaf.tasks import start_line_error
from leaf.thread_context import thread_message, thread_names
from leaf.validation.admission import (
    check_markup,
    logged_id,
    read_text_arg,
    thread_obligation,
)


def _messages(events: list) -> dict[str, dict]:
    return {event["id"]: event for event in events if event["kind"] in MESSAGE_KINDS}


def _unknown_message(page_dir: Path, events: list, name: str) -> None:
    held = logged_id(events, name, current_responses(page_dir, events))
    raise Refused(
        f"unknown comment id {name!r}"
        + (f"; {held}" if held else "")
        + f"; known: {json_value(sorted(_messages(events)))}"
    )


def _message(page_dir: Path, events: list, to: str) -> dict:
    messages = _messages(events)
    if to not in messages:
        _unknown_message(page_dir, events, to)
    return messages[to]


def thread_addressed(page_dir: Path, events: list, name: str) -> tuple[str, str]:
    """The thread `name` names (`work.page_subject`), and the message a write into it
    names (`thread_context.thread_message`). Refuses a name that reaches no thread,
    with what the log holds it as instead, and a widget on the page."""
    from leaf.work import page_subject

    subject = page_subject(page_dir, events, name)
    if subject is None:
        _unknown_message(page_dir, events, name)
    if subject["kind"] == "widget":
        raise Refused(f"{name} is a widget on the page, not a thread")
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
        page.bind_delivery_reply(session_id, target["responds"], attempt)


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
            page.clear_delivery_reply_binding(
                session_id,
                target["responds"],
                attempt,
            )
    except FileNotFoundError:
        pass


def delivery_reply_reserved(session_id: str, delivery_id: str, target: dict) -> bool:
    """Whether this delivery's binding of its reply address still stands."""
    try:
        with PageTransaction(Path(target["page"])) as page:
            binding = page.standing_reply_binding(target["responds"])
            return bool(
                binding is not None
                and binding["session"] == session_id
                and binding["attempt"] == delivery_reply_attempt(delivery_id)
            )
    except FileNotFoundError:
        return False


def thread_of(page_dir: Path, message_id: str) -> str:
    """The thread a message sits in, for a command that has to name it back."""
    return thread_names(read_events(page_dir))[message_id]


def _current_anchor(
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
            raise Refused(f"cannot use invalid index.html: {activation.error}")
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
            logged_id(events, section, current_responses(page_dir, events))
            if section
            else None
        )
        recourse = (
            f"; {held}, while `--section` takes an element id the page's markup "
            "declares"
            if held
            else ""
        )
        raise Refused(f"can't anchor in revision r{revision}: {err}{recourse}")
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
) -> dict:
    """Open a thread, as the user's own gestures do: on a passage where --quote or
    --section points at one, and on the page as a whole where neither does — the same
    anchorless shape the browser's general box posts, which is where a question about
    the work rather than a passage belongs. An anchor is captured against the active
    revision they are looking at and read as they see it: a slot
    their decision retired is off the page, and a draft they edited holds their words,
    so a quote is met here the way it would land there."""
    # Reading a body may wait on stdin; do that before taking the page lease.
    body = read_text_arg(page_dir, text)
    with PageTransaction(page_dir) as page:
        events = page.events
        revision, anchor = _current_anchor(
            page_dir, events, quote, section, part, transaction=page
        )
        if markup:
            check_markup(page_dir, "comment", markup, events)
        event = {
            "kind": "comment",
            "author": "agent",
            **message_identity(),
            "revision": revision,
            "text": body,
        }
        if anchor:
            event["anchor"] = anchor
        if markup:
            event["markup"] = markup
        if title is not None:
            event["title"] = title
        return append_admitted(page, event)[0]


def is_answer(event: dict) -> bool:
    """Whether an event is an agent's answer to the input its ``responds`` names.

    A thread parent locates presentation; only ``responds`` names the input an
    answer settles. User replies carry none. Progress is never an answer, though a log
    written before #1727 addresses it to its input. A failure receipt names the input
    it gives up on without answering it, so an answer may still follow it.
    """
    return (
        event["kind"] == "reply"
        and event["author"] == "agent"
        and event.get("responds") is not None
        and not event.get("ephemeral")
        and "failure" not in event
    )


def successful_replies(events: list[dict], for_event: str) -> list[dict]:
    """Agent answers to this exact input (`is_answer`)."""
    return [
        event for event in events if is_answer(event) and event["responds"] == for_event
    ]


def answered_by_reply(events: list[dict], for_event: str) -> bool:
    """A successful exact reply wins over every later delivery completion.

    Failure receipts and user settlement do not assert a provider answer, so a
    recovered final message may still answer that original delivered address.
    """
    return bool(successful_replies(events, for_event))


@dataclass(frozen=True)
class Refuse:
    """An ordinary writer's settlement: a stale or settled response address is
    refused, with what the log holds instead."""


@dataclass(frozen=True)
class ProviderFinal:
    """A provider turn's final message, committed at the address its delivery
    reserved (`reserve_delivery_reply`).

    It keeps that address after the user settled the update, but yields to an answer
    another writer already gave it (a failure receipt is no answer), so a turn's
    answer committed after its binding lapsed never answers twice; and it writes
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

    to: str
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
    question: bool = False,
    task: str | None = None,
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
    ``for`` fences the write to that exact current obligation, and ``to`` names the
    message it threads under, which may differ from ``for`` when a widget gesture
    belongs to a frozen thread; ``to`` alone posts a new agent message, which the
    thread must currently owe no reply for, and the event then carries no
    ``responds``. ``input`` and ``claim``, which a delivery captured, fence it to that
    page log and delivery owner.

    A repeated ``attempt`` is matched more loosely than the append door's payload
    identity: by kind, progress, failure receipt or answer, response address and
    declaration, so a CLI retry whose text was reworded returns the first reply
    rather than refusing.

    ``failure`` records a harness-owned failure code alongside its presentation text;
    ordinary agent answers omit it.

    ``question`` makes the reply a prose Question on the user (`questions`).
    ``task`` titles work the reply promises and does not deliver: the reply opens
    that task on its thread, under the reply's own id (`tasks.task_reading`), so
    the user's message is answered and the work stays on the agent in one write.

    ``ephemeral`` posts progress at the same response address without answering it.
    It remains content, and cannot carry a question, widgets, failure or relocation.
    Progress on an update the agent owes says what it has in hand, so it also takes that
    update in hand with its text as the line (`tasks.start_reading`), which is why that
    text is one line: the update reads Working beside its thread and in the banner, and
    the user's message gets the agent's first words and its Working line from one
    write.
    """
    text = read_text_arg(page_dir, text)
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
                question,
                task,
            )
        ):
            return repeated
        obligation = _resolve_obligation(
            page,
            address,
            settlement,
            posting_identity.get("session"),
            ephemeral,
            failure,
        )
        if obligation is None:
            return None
        return _compose_and_append(
            page,
            obligation,
            posting_identity,
            text,
            markup,
            attempt=attempt,
            failure=failure,
            validate_source=validate_source,
            question=question,
            task=task,
            ephemeral=ephemeral,
            quote=quote,
            section=section,
            part=part,
            detach=detach,
            title=title,
        )


def _repeated_reply(
    events: list,
    attempt: str,
    address: dict,
    ephemeral: bool,
    failed: bool,
    question: bool,
    task: str | None,
) -> dict | None:
    """The reply an earlier write with this `attempt` appended, or None; refuses an
    attempt that named another kind of write: progress, a failure receipt and an
    answer are each their own."""
    existing = next(
        (event for event in events if event.get("attempt") == attempt), None
    )
    if existing is None:
        return None
    to, for_event = address.get("to"), address.get("for")
    same_scope = (
        existing.get("responds") == (None if ephemeral else for_event)
        if for_event is not None or to is not None
        else True
    )
    if (
        existing["kind"] != "reply"
        or bool(existing.get("ephemeral")) != ephemeral
        or ("failure" in existing) != failed
        or (to is not None and existing["parent"] != to)
        or not same_scope
    ):
        raise Refused(f"attempt {attempt!r} already belongs to another event")
    if (bool(existing.get("question")), existing.get("task")) != (question, task):
        # A repeat that asks or promises differently would otherwise return the
        # first answer and drop what this one declares.
        raise Refused(
            f"{existing['id']!r} already answered this with a different "
            "declaration; ask or promise in a new message with `leaf thread reply`"
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
    to, for_event = address.get("to"), address.get("for")
    if (
        isinstance(settlement, ProviderFinal)
        and for_event is not None
        and answered_by_reply(events, for_event)
    ):
        return None
    responses = current_responses(page_dir, events)
    if for_event is not None and to is None:
        expected = responses.get(for_event)
        if expected is None or expected["kind"] != "reply":
            if isinstance(settlement, Receipt):
                return None
            held = logged_id(events, for_event, responses)
            raise Refused(
                f"event {for_event!r} takes no reply; "
                + (held or f"this page's log holds no event {for_event!r}")
            )
        to = expected["to"]
    thread_id, to = thread_addressed(page_dir, events, to)
    in_hand = None
    if for_event is not None:
        expected = responses.get(for_event)
        if (
            expected is None
            or expected["kind"] != "reply"
            or (expected["to"], expected["for"]) != (to, for_event)
        ):
            if isinstance(settlement, Receipt):
                return None
            if not isinstance(settlement, ProviderFinal):
                held = logged_id(events, for_event, responses)
                raise Refused(
                    f"event {for_event!r} no longer requires a reply to {to!r}; "
                    + (held or "read the current delivery or thread state")
                )
        elif ephemeral:
            in_hand = for_event
        # Current custody belongs to the binding, independently of capture-time
        # writer hints and caller-supplied retry identity.
        binding = page.standing_reply_binding(for_event)
        if binding is not None:
            if isinstance(settlement, ProviderFinal):
                if (session, settlement.reservation) != (
                    binding["session"],
                    binding["attempt"],
                ):
                    return None
            elif not ephemeral and (
                address.get("input") is None or failure is not None
            ):
                refusal = f"event {for_event!r} is answered by this turn's messages; "
                if failure is not None:
                    refusal += (
                        "failure receipts wait for this turn to release the answer; "
                        "answer in your final message or use "
                        "`leaf response reply <answer.ref>` without `--failure`"
                    )
                else:
                    refusal += (
                        "use `leaf response reply <answer.ref>` to commit "
                        "an explicit answer"
                    )
                raise Refused(refusal)
    else:
        standing = thread_obligation(events, responses, thread_id)
        if standing is not None:
            raise Refused(
                f"thread {thread_id!r} currently requires a response; "
                f"{answer_command(standing)} answers it"
            )
    if (
        isinstance(settlement, Receipt)
        and settlement.only_if_unclaimed
        and pickup_receipts(events, phase=None, input_id=for_event)
    ):
        return None
    return _Obligation(to, thread_id, None if ephemeral else for_event, in_hand)


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
    question: bool,
    task: str | None,
    ephemeral: bool,
    quote: str,
    section: str,
    part: str,
    detach: bool,
    title: str | None,
) -> dict:
    """Check the reply's content against the page, compose its event and append it
    at `obligation`, publishing saved page edits first where `validate_source` or a
    detach reads them."""
    page_dir, events = page.page_dir, page.events
    to, thread_id, responds, in_hand = obligation
    opening = _messages(events).get(thread_id)
    moving = bool(quote or section or part)
    if ephemeral and (question or task or markup or failure or moving or detach):
        raise Refused(
            "--ephemeral is for progress text; it cannot ask a question, open a task, carry widgets, report failure, or move the thread"
        )
    if in_hand is not None and start_line_error(text.strip()):
        raise Refused(
            f"progress on {in_hand!r}, an update you owe, takes it in hand, and its "
            "text is the Working line beside the thread and in the banner: write "
            "it as one line saying what you are doing"
        )
    if detach and moving:
        raise Refused("--detach cannot be combined with --quote, --section, or --part")
    relocating = moving or detach
    if relocating and opening is None:
        raise Refused(
            f"thread {thread_id!r} has no surviving opening comment, so its "
            "anchor cannot be changed"
        )
    if relocating and opening.get("holds"):
        raise Refused(
            f"thread {thread_id!r} holds the command goal named by its opening "
            "comment, so its anchor cannot be changed"
        )
    current_thread = (
        build_threads(events, active_enclosing(page_dir)).get(thread_id)
        if detach
        else None
    )
    if detach and (current_thread is None or current_thread["anchor"] is None):
        raise Refused(f"thread {thread_id!r} has no current anchor to detach")
    reply_revision = None
    prospective_page = None
    prospective_anchor = None
    source_events = events
    source_matches_active = True
    if validate_source or detach:
        active = latest_revision(page_dir)
        source_matches_active = bool(
            active is not None
            and (page_dir / "index.html").is_file()
            and (page_dir / "index.html").read_bytes()
            == revision_path(page_dir, active).read_bytes()
        )
        if relocating:
            source_events = [
                *events,
                {
                    "kind": "reply",
                    "id": "prospective-anchor-transition",
                    "author": "agent",
                    "text": text,
                    "seq": events[-1]["seq"] + 1,
                    "ts": "pending",
                    "parent": to,
                    "anchor": None,
                    **({"responds": responds} if responds is not None else {}),
                },
            ]
        if source_matches_active:
            reply_revision = active
        else:
            from leaf.validation.source import check_source

            checked = check_source(page_dir, source_events)
            if checked.errors:
                operation = "reply" if validate_source else "detach"
                raise Refused(
                    f"cannot {operation} while index.html is invalid: "
                    f"{'; '.join(checked.errors)}"
                )
            prospective_page = checked.document
            if moving:
                from leaf.registry.storage import require_registry

                prospective_anchor = _capture_anchor(
                    page_dir,
                    events,
                    SourceReading(checked.document, require_registry(page_dir)),
                    quote,
                    section,
                    part,
                    (active or 0) + 1,
                )
    fragment = (
        check_markup(page_dir, "reply", markup, events, page=prospective_page)
        if markup
        else None
    )
    if question and fragment:
        from leaf.registry.storage import require_registry

        registry = require_registry(page_dir)
        structural = sorted(
            {
                rec["tag"]
                for rec in fragment.lf_elements
                if local_question_entry(registry.get(rec["tag"]) or {})
                and asking(rec["attrs"], registry[rec["tag"]]["x-awaits"].get("when"))
                and not quoted_in(rec, registry)
            }
        )
        if structural:
            raise Refused(
                "--question is for a prose question; reply markup already declares "
                "a local Question "
                f"({', '.join(f'<{tag}>' for tag in structural)})"
            )
    if not source_matches_active:
        from leaf.revisioning import planned_activation

        reply_revision = planned_activation(page_dir, checked).revision
    if prospective_anchor is not None:
        revision, anchor = reply_revision, prospective_anchor
    elif moving:
        revision, anchor = _current_anchor(
            page_dir,
            events,
            quote,
            section,
            part,
            revision=reply_revision,
            transaction=page,
        )
    elif detach:
        revision, anchor = reply_revision, None
    else:
        revision, anchor = None, None
    event = {
        "kind": "reply",
        "author": "agent",
        **posting_identity,
        "parent": to,
        "text": text,
        **({"responds": responds} if responds is not None else {}),
    }
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
    if question:
        event["question"] = True
    if task is not None:
        event["task"] = task
    if markup:
        event["markup"] = markup
    if attempt is not None:
        event["attempt"] = attempt
    if failure is not None:
        event["failure"] = failure
    if relocating or markup:
        event["revision"] = revision or latest_revision(page_dir)
    if relocating:
        event["anchor"] = anchor
    if title is not None:
        event["title"] = title
    if not source_matches_active:
        from leaf.revisioning import publish_checked_event

        record = publish_checked_event(page, checked, event)
    else:
        record, _ = append_admitted(page, event)
    if in_hand is not None and page.status["state"] == "idle":
        page.set_status("waiting", "")
    return record


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
    """
    address = response_address(reference)
    if address["kind"] != "reply":
        raise Refused(
            f"response {reference!r} requires {answer_command(address)}, not a reply"
        )
    attempt = options.pop("attempt", None)
    if reservation is None and (attempt is not None or not options.get("ephemeral")):
        # Public retry keys identify this addressed author's writes, never a
        # provider's reservation. The disjoint namespaces prevent a progress
        # retry key from consuming its provider final's append identity too, and
        # a failure receipt's from standing in for a later answer's.
        retry = reference if attempt is None else f"{reference}:{attempt}"
        namespace = "failure" if options.get("failure") is not None else "response"
        attempt = f"leaf-{namespace}-{sha256(retry.encode()).hexdigest()}"
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
      the user resends into; provider custody refuses it until its turn gives the
      reply up;
    - a `markup` answer takes a failed pickup: the user's Question answer stands in the
      log, and answering again sends a new answer.

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
        {"for": responds},
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


def title_event(thread: str, title: str, identity: dict) -> dict:
    """The `thread_title` event naming `thread`, in the voice of `identity`."""
    return {
        "kind": "thread_title",
        "author": "agent",
        **identity,
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
    from leaf.event_contracts import admitted_event
    from leaf.page_view import PageView
    from leaf.registry.storage import require_registry

    # Text comes from stdin when neither option gives it; read it before the lease.
    body = read_text_arg(page_dir, text) if text is not None or title is None else None
    with PageTransaction(page_dir) as page:
        require_registry(page_dir)
        named = None
        if title is not None:
            thread = thread_named(page_dir, page.events, message)
            named = title_event(thread, title, message_identity())
            admitted_event(PageView(page_dir), page.events, named)
        records = []
        if body is not None:
            _message(page_dir, page.events, message)
            edit = {
                "kind": "edit",
                "author": "agent",
                **message_identity(),
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

    body = read_text_arg(page_dir, text, allow_empty=text == "")
    with PageTransaction(page_dir) as page:
        require_registry(page_dir)
        record, _ = append_admitted(
            page,
            {
                "kind": "summary",
                "author": "agent",
                **message_identity(),
                "thread": thread_named(page_dir, page.events, from_message),
                "from": from_message,
                "through": through_message,
                "text": body,
                **({"label": label} if label is not None else {}),
            },
        )
        return record


@contract_writer
def cmd_resolve(page_dir: Path, to: str) -> dict:
    """Close a thread, as the user's own ✓ Resolve does. Same event, same rule on
    `parent` — any message in the thread names it — and `author` the whole
    difference, which is how the panel can say who closed it."""
    with PageTransaction(page_dir) as page:
        _thread_id, to = thread_addressed(page_dir, page.events, to)
        event = {
            "kind": "resolve",
            "author": "agent",
            **message_identity(),
            "parent": to,
        }
        return append_admitted(page, event)[0]


@contract_writer
def cmd_report(
    page_dir: Path,
    widget: str,
    verb: str,
    fields: tuple,
) -> dict:
    """A worker's provisional news: a declared state change folded onto a page
    widget, admitted the way the append door admits a user's action,
    stamped with the posting session's voice, and made against the active revision —
    the page the user is looking at. The runtime paints it live; it stands until
    a stamped revision absorbs or overrules it by id (see `page stamp`), and the
    page's watcher wakes to fold it in. Field values
    are strings — the declared detail schemas for reports speak in attribute
    values, which is all a report may move."""
    from leaf.revisioning import activate_source

    detail = {}
    for field in fields:
        name, eq, value = field.partition("=")
        if not eq or not name:
            raise Refused(f"detail fields are name=value, got {field!r}")
        detail[name] = value
    with PageTransaction(page_dir) as page:
        activate_source(page_dir, transaction=page)
        event = {
            "kind": "report",
            "author": "agent",
            **message_identity(),
            "widget": widget,
            "action": verb,
            "detail": detail,
            "revision": require_revision(page_dir),
        }
        return append_admitted(page, event)[0]
