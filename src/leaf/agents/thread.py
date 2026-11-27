"""Thread writes, addressed response admission, and provider reply reservations."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import NamedTuple, Never

from leaf.agents.delivery import (
    ReceiptRefused,
    current_responses,
    pickup_receipts,
    record_pickup,
    response_address,
)
from leaf.base.files import (
    latest_revision,
    require_revision,
)
from leaf.base.findings import Finding, Rejected, element_at, note
from leaf.base.harness import message_identity
from leaf.base.leases import contract_writer
from leaf.base.service import delivery_reply_attempt, same_claim
from leaf.base.state import acting_turn
from leaf.log.event_log import read_events
from leaf.log.events import (
    active_summaries,
    build_threads,
    is_answer,
    settle,
    taken_back,
    thread_structure,
)
from leaf.log.obligations import questions_in_words
from leaf.log.projection import page_reading
from leaf.log.thread_context import thread_message, thread_names
from leaf.records.activity import answer_command, reply_command
from leaf.records.authored_checks.admission import (
    check_markup,
    checked_text,
    logged_id,
    revision_publication,
    thread_obligation,
)
from leaf.records.authored_checks.source import (
    SourceCheck,
    check_source,
    moved_threads,
    source_advice,
)
from leaf.records.event_contracts import append_admitted, append_all_admitted
from leaf.records.todos import TodoReading
from leaf.records.transaction import PageTransaction
from leaf.records.work import page_subject
from leaf.source.anchor_capture import Drawing, capture_anchor, drawn_part
from leaf.source.data import read_data
from leaf.source.obligation_sources import local_obligation_entry
from leaf.source.passages import holds_html, message_markup
from leaf.source.reading import SourceReading
from leaf.source.registry.contract import matches_when
from leaf.source.registry.kernel import kinds_declaring, title_limit, wait_limit
from leaf.source.revision_artifact import active_enclosing, read_revision
from leaf.source.structure import SourceDocument, shown_in
from leaf.source.vocabulary import require_registry

# The browser check a message's markup runs before it posts
# (`render_gate.messages.message_check`): given the page, the kind of message and the
# markup, it raises `Rejected` where a widget in the markup doesn't draw. The render
# gate stands above this module, so each write takes the check from its command, and
# a write given none posts the markup unrun, as on a host with no browser.
MessageCheck = Callable[[Path, str, str], None]


def drawn_markup(text: str) -> str:
    """The markup an agent's message draws from `text` where its Markdown holds HTML
    (`passages.holds_html`); else none, and the message is Markdown alone."""
    return message_markup(text) if holds_html(text) else ""


def _messages(events: list) -> dict[str, dict]:
    return {
        event["id"]: event
        for event in events
        if event["kind"] in kinds_declaring("message")
    }


def asking_widget(fragment, registry: dict) -> dict | None:
    """The first widget in a message's markup that waits on the user (`awaits`),
    which makes it the message's request for an answer."""
    return next(
        (
            rec
            for rec in fragment.lf_elements
            if local_obligation_entry(registry.get(rec["tag"]) or {})
            and matches_when(rec["attrs"], registry[rec["tag"]]["awaits"].get("when"))
            and not shown_in(rec, registry)
        ),
        None,
    )


def unasked_widget(fragment, registry: dict) -> dict:
    """The first widget in the markup that could wait on the user but whose
    attributes keep it from asking, with the attributes it would ask with, so an
    undeclared answer's refusal names what to add rather than only the flags."""
    for rec in fragment.lf_elements:
        entry = registry.get(rec["tag"]) or {}
        if not local_obligation_entry(entry) or shown_in(rec, registry):
            continue
        when = entry["awaits"].get("when") or {}
        needs = [
            _attribute_written(attr, values)
            for attr, values in when.items()
            if not matches_when(rec["attrs"], {attr: values})
        ]
        return {
            "tag": rec["tag"],
            "id": rec["attrs"].get("id"),
            "needs": " and ".join(needs),
        }
    return {}


def _attribute_written(attr: str, values: list) -> str:
    """How markup meets one `when` condition: a flag's presence or absence, or
    the first value it allows."""
    if True in values:
        return f"`{attr}`"
    if values == [False]:
        return f"no `{attr}`"
    return f'`{attr}="{values[0]}"`'


def second_request(asking: dict | None) -> list[Finding]:
    """What `--obligation` beside `asking`, a widget in the message that asks, does:
    the message asks twice, and the obligation stays on On Me after the user answers
    the widget, since only their words answer it. Advice, since the words may ask
    something the widget doesn't."""
    if asking is None:
        return []
    return [
        Finding(
            "obligation-beside-widget",
            values={"tag": asking["tag"], "id": asking["attrs"].get("id")},
        )
    ]


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
) -> tuple[int, dict | None, Finding | None]:
    """Capture one optional target against the page's active reading: the revision,
    the anchor, and the note to give beside it (`anchor_capture.capture_anchor`)."""
    if revision is None:
        from leaf.records.revisioning import activate_source

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
        return revision, None, None

    reading = read_revision(page_dir, revision).under(require_registry(page_dir))
    return revision, *_capture_anchor(
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
) -> tuple[dict, Finding | None]:
    """Capture a target against one exact document reading, with its note."""
    page = page_reading(reading, events, revision)
    try:
        return capture_anchor(
            page.document,
            page.registry,
            quote,
            section,
            part=part,
            **page.logged_words,
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


# How a message names the page's render reading as the drawing that read its visuals
# (`anchor_capture.Drawing`).
LAST_CHECKED = "when the page was last checked"


class UndrawnPart(Exception):
    """A `--part` in a visual that no render reading of `revision`, with the page's
    data as it stands, read (`render_reading`), which a caller may learn by drawing the
    page (`render_gate.drawn_anchor.drawn_visuals`)."""

    def __init__(self, revision: int):
        super().__init__(f"no render reading of revision r{revision} read the visual")
        self.revision = revision


class Drawn(NamedTuple):
    """What the page drew of `revision` in a browser, where the files couldn't settle a
    `--part` (`render_gate.drawn_anchor`): the `drawing` of the page's visuals the part
    is checked against."""

    revision: int
    drawing: Drawing


def _drawn_part(
    page_dir: Path, revision: int, section: str, part: str, drawing: Drawing | None
) -> Finding | None:
    """What the page drew says of a thread on `part` in the visual `section` of
    `revision` (`anchor_capture.drawn_part`), as `drawing` read the page, or else as
    the page's render reading of `revision` with the data the page holds now read it.
    Raises `UndrawnPart` where that reading didn't read the visual, and refuses a part
    the page would show nowhere as a capture refuses its target."""
    if drawing is None:
        from leaf.records.render_reading import drawn_visuals

        data = read_data(page_dir, read_revision(page_dir, revision).registry)
        visuals = drawn_visuals(
            page_dir, read_revision(page_dir, revision).digest, data["version"]
        )
        if section not in visuals:
            raise UndrawnPart(revision)
        drawing = Drawing(visuals, LAST_CHECKED)
    try:
        return drawn_part(section, part, drawing)
    except ValueError as err:
        raise Rejected(
            [
                Finding(
                    "unanchorable",
                    values={"revision": revision, "error": str(err), "held": None},
                )
            ]
        ) from err


@contract_writer
def cmd_comment(
    page_dir: Path,
    quote: str,
    section: str,
    part: str,
    text,
    *,
    title: str | None = None,
    obligation: bool = False,
    drawn: Drawn | None = None,
    check: MessageCheck | None = None,
) -> dict:
    """Open a thread, as the user's own gestures do: on a passage where --quote or
    --section points at one, and on the page as a whole where neither does — the same
    anchorless shape the browser's general box posts, which is where a question about
    the work rather than a passage belongs. An anchor is captured against the active
    revision they are looking at and read as they see it: a slot
    their decision retired is off the page, and a draft they edited holds their words,
    so a quote is met here the way it would land there, and a `--part` is checked
    against what the page drew (`anchor_capture.drawn_part`). A quote is stored as
    given, and the record carries the note on where the page shows it where the file's
    reading doesn't find its words once (`unplaced-quote`).

    A part in a visual no render reading of the version read needs the drawn page,
    which the command draws and passes back as `drawn` (`render_gate.drawn_anchor`),
    since the render gate stands above this module; until then it is raised as
    `UndrawnPart`. For the same reason the command passes `check`, which runs the
    message's HTML before the page lease is taken."""
    title = agent_title(title)
    body = checked_text(page_dir, text, html=True)
    if check is not None and (markup := drawn_markup(body)):
        check(page_dir, "comment", markup)
    with PageTransaction(page_dir) as page:
        record, found = open_thread(
            page_dir,
            page,
            body,
            quote,
            section,
            part,
            title=title,
            obligation=obligation,
            drawn=drawn,
        )
    note(*found)
    return record


def open_thread(
    page_dir: Path,
    page: PageTransaction,
    body: str,
    quote: str = "",
    section: str = "",
    part: str = "",
    *,
    title: str | None = None,
    obligation: bool = False,
    identity: dict | None = None,
    drawn: Drawn | None = None,
) -> tuple[dict, list[Finding]]:
    """The agent's thread opened in `page`, an open transaction, as `cmd_comment`
    describes, from a `body` already checked (`checked_text`), and the notes to give
    beside it; `identity` names the agent and session where the writer isn't the
    agent's own process, as Leaf's clerk is (`clerk.apply_answer`). `drawn` is what
    the page drew of the revision the command's first attempt read, where the files
    couldn't settle a part (`render_gate.drawn_anchor`)."""
    events = page.events
    revision, anchor, quoted = current_anchor(
        page_dir,
        events,
        quote,
        section,
        part,
        None if drawn is None else drawn.revision,
        transaction=page,
    )
    placed = (
        _drawn_part(
            page_dir, revision, section, part, None if drawn is None else drawn.drawing
        )
        if part
        else None
    )
    twice = []
    if markup := drawn_markup(body):
        publication = revision_publication(page_dir, revision)
        fragment = check_markup(
            page_dir, "comment", markup, events, publication=publication
        )
        if obligation:
            twice = second_request(asking_widget(fragment, publication.registry))
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
    if title is not None:
        event["title"] = title
    record = append_admitted(page, event)[0]
    # The caller says them once the message stands, which a later gate could still
    # refuse.
    return record, [*twice, *(found for found in (placed, quoted) if found)]


class OwedAnswer(Exception):
    """A question asked again in a thread that still owes the user a reply: the
    question waits on that reply, after which it is the user's again
    (`obligations`). Its words say how to give the reply."""


def ask_again(
    page: PageTransaction, question: str, body: str, identity: dict
) -> dict | None:
    """The agent's message asking `question` (`message:<id>`, or the bare id) again in
    its thread in `page`, an open transaction, from a `body` already checked; like
    a message that asks, it reopens the thread if it was resolved. Where its HTML holds a widget that asks, such as a
    choice, the message asks with it. Otherwise it asks in words: a question first
    asked in words stands open on it under its own id, as `leaf thread reply <page>
    <message> --obligation <question>` posts it, and one a widget asked is asked
    anew, as `--obligation` alone posts it. None where `question` names no question
    asked in its thread (`thread_questions`). `OwedAnswer` where the thread owes the
    user a reply, which the question waits on. Refused, as an agent's reply is, where
    its HTML doesn't validate (`check_markup`)."""
    message = question.removeprefix("message:")
    name = f"message:{message}"
    try:
        addressed = _resolve_obligation(
            page, {"parent": message}, REFUSE, identity["session"], False, None
        )
    except Rejected:
        return None
    assert addressed is not None
    for found in addressed.advice:
        if found.code == "owed-response":
            raise OwedAnswer(str(found))
    registry = require_registry(page.page_dir)
    asked = thread_questions(page.events, addressed.thread, registry)
    if name not in asked:
        return None
    widget = markup_asks(drawn_markup(body), registry)
    return _compose_and_append(
        page,
        addressed,
        identity,
        {"text": body},
        attempt=None,
        failure=None,
        validate_source=False,
        promise=None,
        asks_back=False,
        explicit_obligation=False if widget else ([name] if asked[name] else True),
        ephemeral=False,
        quote="",
        section="",
        part="",
        detach=False,
        title=None,
        title_owed=False,
    )[0]


def markup_asks(markup: str, registry: dict) -> bool:
    """Whether the markup a message draws (`drawn_markup`) holds a widget that asks
    (`asking_widget`), which asks in place of an obligation."""
    return bool(markup) and bool(asking_widget(SourceDocument(markup), registry))


def widget_asks(fragment: SourceDocument | None, registry: dict) -> bool:
    """Whether a message's HTML as it now reads (`thread_structure`) holds a widget
    that asks (`asking_widget`), a question `widget_question` names."""
    return fragment is not None and bool(asking_widget(fragment, registry))


def widget_question(message: str) -> str:
    """The id that names the question a widget in message `message` asks, which
    `ask_again` takes."""
    return f"message:{message}"


def thread_questions(events: list, thread: str, registry: dict) -> dict[str, bool]:
    """The questions `thread`'s messages ask, each by the id that names it, and
    whether it was asked in words (`obligations.questions_in_words`) rather than by a
    widget (`widget_asks`)."""
    names = thread_names(events)
    asked = dict.fromkeys(questions_in_words(events, names, thread), True)
    for message, fragment in thread_structure(events).fragments.items():
        if names.get(message) == thread and widget_asks(fragment, registry):
            asked[widget_question(message)] = False
    return asked


def settling_answer(page_dir: Path, events: list[dict], responds: str) -> dict | None:
    """The agent's latest answer since the input `responds` names that names it or an
    input after it in its thread, which leaves that input answered (`events.settle`);
    else None. A failure receipt is no answer, so the first answer after one at the
    same input carries `responds`, and every later one finds it here."""
    for thread in build_threads(events, active_enclosing(page_dir)).values():
        places = settle(thread).places
        if (place := places.get(responds)) is None:
            continue
        return next(
            (
                turn
                for turn in reversed(thread["turns"])
                if is_answer(turn)
                and turn["seq"] > place
                and places.get(turn["responds"], -1) >= place
            ),
            None,
        )
    return None


def successful_replies(events: list[dict], responds: str) -> list[dict]:
    """Agent answers to this exact input (`events.is_answer`)."""
    return [
        event for event in events if is_answer(event) and event["responds"] == responds
    ]


@dataclass(frozen=True)
class Refuse:
    """An ordinary writer's settlement: a write at a reference that no longer names its
    thread's newest standing input is refused, with the command that answers the
    thread instead (`post_reply`)."""


@dataclass(frozen=True)
class ProviderFinal:
    """A provider turn's final message, committed at the address its delivery
    reserved (`reserve_delivery_reply`), or its opening, posted there as progress.

    It yields to an answer another writer already gave the update, by naming it or a
    newer input in its thread (`settling_answer`; a failure receipt is no answer), so
    a turn's answer committed after its reservation lapsed never answers twice, and
    it writes nothing once another delivery holds the address. Where its reference no
    longer names the thread's newest standing input, it skips that check and answers
    the input it was written for (`_resolve_obligation`): the turn can't write again,
    and the user watched it write those words. Codex alone writes this way, so it
    stands as a special case outside the rule every other write follows."""

    reservation: str


@dataclass(frozen=True)
class Receipt:
    """A writer that answers only what is still owed: a harness's failure receipt,
    or the working line a line fork of the agent's conversation posts (`forks`). An
    update that no longer owes an answer takes none. With `only_if_unclaimed`, an
    update some turn already picked up is left to the writer following that turn.
    With `fence`, the receipt writes only while `fence` holds of the page under the
    lock its append takes, as a line goes in only while its round still awaits it. A
    receipt's progress, such as a line fork's working line, takes nothing in hand: its
    writer is not the turn that will answer, and a start would read as that turn's,
    renewing it and holding the update at Working before the session has it."""

    only_if_unclaimed: bool = False
    fence: Callable[[PageTransaction], bool] | None = None


Settlement = Refuse | ProviderFinal | Receipt
REFUSE = Refuse()


class _Obligation(NamedTuple):
    """Where a reply goes once its address has been checked against the log."""

    parent: str
    thread: str
    responds: str | None
    # The update a progress reply takes in hand, if it owes one.
    in_hand: str | None
    # What the command notes beside the reply once it is in.
    advice: tuple[Finding, ...] = ()


@contract_writer
def post_reply(
    page_dir: Path,
    address: dict,
    text,
    *,
    emoji: str | None = None,
    settlement: Settlement = REFUSE,
    attempt: str | None = None,
    identity: dict | None = None,
    claimed_session: str | None = None,
    failure: str | None = None,
    validate_source: bool = False,
    todo: str | None = None,
    waiting_on: str | None = None,
    asks_back: bool = False,
    obligation: bool | list[str] = False,
    ephemeral: bool = False,
    quote: str = "",
    section: str = "",
    part: str = "",
    detach: bool = False,
    title: str | None = None,
    title_owed: bool = False,
    check: MessageCheck | None = None,
) -> dict | None:
    """Post one complete threaded reply, optionally moving or detaching its anchor;
    the appended record, or the earlier reply a repeated `attempt` names, or none
    when `settlement` leaves nothing to write.

    ``address`` takes the fields of a response address (`delivery.response_address`):
    ``responds`` fences an answer to that exact current obligation, and ``parent``
    names the message it threads under (`obligations.response_address`). ``parent``
    alone posts a new agent message, and the event then carries no ``responds``: it
    answers nothing, so an answer its thread owes stays owed, which the command
    notes beside it (`owed-response`). ``input`` and ``claim``, which a delivery
    captured, fence it to that page log and delivery owner.

    A ``responds`` that no longer names its thread's newest standing input refuses
    the write, which would mark input the agent never read answered
    (`superseded-reply`); that is the one check (`_resolve_obligation`). At the newest input, a write goes in
    whether or not that input is still owed, and answers it only where it is. So
    progress after an answer takes in hand the newest still-open to-do an earlier
    answer there opened, and an answer that declares nothing further is noted with
    the `leaf task end` that ends such a to-do: `--todo` and then `--done` on one
    reference both go in.

    A repeated ``attempt`` returns the reply it appended, matched by kind,
    progress, failure receipt or answer, and response address rather than by the
    append door's payload identity, so a provider's repeated final returns the
    first however it reads; a CLI answer's key covers its whole write
    (`post_response`).

    ``emoji`` posts the reply as one emoji in place of ``text``, which is then None: a
    reaction, which answers and declares what it leaves as words do (`events.md`,
    "Reactions").

    ``failure`` records a harness-owned failure code alongside its presentation text;
    ordinary agent answers omit it.

    ``claimed_session`` names the session Leaf writes for, as a line fork's working
    message or a harness's failure receipt: Leaf's own write, which goes in as the
    claimant's and says nothing beside it.

    ``check`` runs the reply's HTML before the page lease is taken
    (`MessageCheck`).

    ``todo`` titles work the reply promises and does not deliver: the reply opens
    that to-do on its thread, under the reply's own id (`todos.todo_reading`), so
    the user's message is answered and the work stays on the agent in one write.
    ``waiting_on`` names what that work waits on (`todos`), fitted to `wait_limit`.

    ``title`` names the thread where it has no title yet, and ``title_owed`` refuses
    a reply into an untitled thread that gives none (`untitled-thread`), as the
    agent's own command does: Leaf's own writes, such as a line fork's working line
    or a Codex turn's final message, owe none.

    ``ephemeral`` posts progress at the same response address without answering it.
    It remains content, and cannot carry an obligation, a to-do, widgets, failure or
    relocation. Progress on work the agent owes says what it has in hand, so it also
    takes that work in hand with its text as the line (`todos.start_reading`), which is
    why that text is one line: the update it addresses while that is owed, or else the
    to-do an answer opened, addressed by the update the answer answered or by the
    to-do's own message. The work reads Working beside its thread and in the page's
    status, so the user's message gets the agent's first words and its Working line
    from one write, and a promise's thread and On <agent> row show the line its work
    runs under. A `Receipt`'s progress takes nothing in hand.
    """
    title = agent_title(title)
    # The to-do's fields the reply carries. Admission refuses a blank one, and a wait
    # with no to-do.
    promise = {
        field: value
        for field, value in (
            ("todo", agent_title(todo)),
            (
                "waiting_on",
                None if waiting_on is None else fitted(waiting_on, wait_limit()),
            ),
        )
        if value is not None
    }
    if emoji is None:
        text = checked_text(page_dir, text, html=True)
        if check is not None and (markup := drawn_markup(text)):
            check(page_dir, "reply", markup)
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
                page.events, attempt, address, ephemeral, failure is not None
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
            done=not (
                ephemeral or promise or obligation or asks_back or failure is not None
            ),
        )
        if addressed is None:
            return None
        record, published = _compose_and_append(
            page,
            addressed,
            posting_identity,
            {"emoji": emoji} if emoji is not None else {"text": text},
            attempt=attempt,
            failure=failure,
            validate_source=validate_source,
            promise=promise,
            asks_back=asks_back,
            explicit_obligation=obligation,
            ephemeral=ephemeral,
            quote=quote,
            section=section,
            part=part,
            detach=detach,
            title=title,
            title_owed=title_owed,
        )
    if claimed_session is None:
        note(*addressed.advice)
        if record.get("unannounced"):
            # The agent may not have heard of the user's resolve, and what it just
            # said may be news they would want to stop for, which only it can judge.
            note(
                Finding(
                    "stays-closed",
                    values={
                        "thread": addressed.thread,
                        "command": f"leaf thread reopen {page_dir} {record['id']}",
                    },
                )
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
    moved (`authored_checks.source.moved_threads`) other than one it moves itself."""
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
    events: list, attempt: str, address: dict, ephemeral: bool, failed: bool
) -> dict | None:
    """The reply an earlier write with this `attempt` appended, or None; refuses an
    attempt that named another kind of write, progress, a failure receipt and an
    answer each being their own, or a write that answered another update."""
    existing = next(
        (event for event in events if event.get("attempt") == attempt), None
    )
    if existing is None:
        return None
    parent, responds = address.get("parent"), address.get("responds")
    if (
        existing["kind"] != "reply"
        or bool(existing.get("ephemeral")) != ephemeral
        or ("failure" in existing) != failed
        or (parent is not None and existing["parent"] != parent)
        # Progress, and an answer after one that promised a to-do, answer nothing.
        or existing.get("responds") not in (None, responds)
    ):
        raise Rejected([Finding("attempt-conflict", values={"attempt": attempt})])
    return existing


def _resolve_obligation(
    page: PageTransaction,
    address: dict,
    settlement: Settlement,
    session: str | None,
    ephemeral: bool,
    failure: str | None,
    done: bool = False,
) -> _Obligation | None:
    """Check `address` against the thread it writes to; where the reply goes and what
    the command notes beside it, or None where `settlement` says to write nothing.
    `done` says the write is an answer that declares nothing further (`post_reply`).

    A write at a reference goes in only while the input it names is its thread's
    newest standing input, answered or not (`workflows.Handover`), and an answer then
    settles every input up to there (`events.settle`). Any other is refused
    (`superseded-reply`): the user has added to the thread or taken that input back
    since, and the agent writes again once it has read the thread as it stands. A
    receipt writes nothing instead, and a provider's final, which can't be written
    again, goes in answering the input it was written for (`ProviderFinal`). That is
    the one check on what a reply answers: a second reply at the newest reference
    goes in like the first, answering nothing new."""
    from leaf.agents.presence import read_work

    page_dir, events = page.page_dir, page.events
    parent, responds = address.get("parent"), address.get("responds")
    if (
        isinstance(settlement, ProviderFinal)
        and responds is not None
        and settling_answer(page_dir, events, responds)
    ):
        return None
    work = read_work(page_dir, events)
    responses = current_responses(page_dir, events, work)
    expected = responses.get(responds)
    owed = expected is not None and expected["kind"] == "reply"
    if responds is not None and parent is None:
        if not owed:
            # Only a receipt addresses an update by `responds` alone; every other
            # writer names the reply's parent (`obligations.response_address`).
            assert isinstance(settlement, Receipt)
            return None
        assert expected is not None
        parent = expected["parent"]
    assert parent is not None
    thread_id, parent = thread_addressed(page_dir, events, parent)
    # Progress on the message that opened a to-do still open takes that to-do in hand.
    in_hand = (
        address["parent"]
        if responds is None
        and ephemeral
        and not isinstance(settlement, Receipt)
        and any(todo["id"] == address["parent"] for todo in TodoReading(events).owed)
        else None
    )
    # A write at an input an earlier answer settled goes in, and answers nothing new.
    answered = responds is not None and settling_answer(page_dir, events, responds)
    answers = None if ephemeral or answered else responds
    advice: list[Finding] = []
    if responds is not None:
        thread = work.durable.threads.get(thread_id)
        place = settle(thread).places.get(responds) if thread else None
        newest = work.durable.newest_inputs.get(thread_id)
        stale = place is None or place != newest
        if stale and isinstance(settlement, Receipt):
            return None
        if stale and not isinstance(settlement, ProviderFinal):
            owed_here = thread_obligation(events, responses, thread_id)
            held = (
                f"{answer_command(owed_here, page_dir)} answers the thread"
                if owed_here is not None
                else "nothing in it is owed now, and"
                f" `leaf thread reply {page_dir} {thread_id}` posts into it"
            )
            found = {"event": responds, "held": held}
            raise Rejected([Finding("superseded-reply", values=found)])
        if isinstance(settlement, Receipt) and not owed:
            return None
        elif answered:
            # The to-dos earlier answers at this reference opened that are still
            # open: progress takes the newest in hand, and an answer that declares
            # nothing further is noted with the `leaf task end` that ends each.
            opened = {reply["id"] for reply in successful_replies(events, responds)}
            open_todos = [
                todo for todo in TodoReading(events).owed if todo["id"] in opened
            ]
            if ephemeral and open_todos:
                in_hand = open_todos[-1]["id"]
            advice += [
                Finding(
                    "promised-todo",
                    values={
                        "event": responds,
                        "page": str(page_dir),
                        "todo": todo["id"],
                        "title": todo["prompt"]["text"],
                    },
                )
                for todo in open_todos
                if done
            ]
        elif ephemeral and owed and not isinstance(settlement, Receipt):
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
            elif answers is not None and (
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
    if answers is None and not (ephemeral and responds):
        # A message that answers nothing, other than progress on an update, leaves
        # what its thread owes owed.
        owed = thread_obligation(events, responses, thread_id)
        if owed is not None:
            advice.append(
                Finding(
                    "owed-response",
                    values={
                        "thread": thread_id,
                        "answer": answer_command(owed, page_dir),
                    },
                )
            )
    if isinstance(settlement, Receipt) and (
        (
            settlement.only_if_unclaimed
            and pickup_receipts(events, phase=None, input_id=responds)
        )
        or (settlement.fence is not None and not settlement.fence(page))
    ):
        return None
    return _Obligation(parent, thread_id, answers, in_hand, tuple(advice))


def _compose_and_append(
    page: PageTransaction,
    obligation: _Obligation,
    posting_identity: dict,
    said: dict,
    *,
    attempt: str | None,
    failure: str | None,
    validate_source: bool,
    promise: dict | None,
    asks_back: bool,
    explicit_obligation: bool | list[str],
    ephemeral: bool,
    quote: str,
    section: str,
    part: str,
    detach: bool,
    title: str | None,
    title_owed: bool,
) -> tuple[dict, "_Published | None"]:
    """Check the reply's content (`drawn_markup`) against the page, compose its event
    and append it at `obligation`. `said` is what the reply says: its `text`, or its
    `emoji`. Successful replies publish saved edits when
    `validate_source` requests it. Progress and failure reports use the active
    revision; detaching still checks saved source. Return the appended record and any checked
    publication for `_revision_advice` to read.

    `promise` holds the fields of the to-do the reply opens, its `todo` title and any
    `waiting_on`, which the event carries as they are.

    `title_owed` refuses a reply into an untitled thread that gives no `title`
    (`untitled-thread`). The user asked for every thread to have a title, whether or
    not a surface shows it. On a page no session claims, no harness is asked for one
    as the user posts (`thread_titles`), so the agent's reply is where it comes from,
    and the delivery's request for one goes unread by an agent that reads the delivery
    through a filter, as `jq` with a field list does."""
    page_dir, events = page.page_dir, page.events
    parent, thread_id, responds, in_hand, _advice = obligation
    markup = drawn_markup(said["text"]) if "text" in said else ""
    event = {
        "kind": "reply",
        "author": "agent",
        **posting_identity,
        "parent": parent,
        **said,
        **({"responds": responds} if responds is not None else {}),
    }
    opening = _messages(events)[thread_id]
    # Admission refuses a reply whose thread is taken back, so where the thread is
    # gone from the reading there is nothing to say of it.
    before = build_threads(events, active_enclosing(page_dir)).get(thread_id)
    moving = bool(quote or section or part)
    widget = bool(markup) and bool(SourceDocument(markup).lf_elements)
    if ephemeral and (
        promise or explicit_obligation or widget or failure or moving or detach
    ):
        raise Rejected([Finding("ephemeral-content")])
    if detach and moving:
        raise Rejected([Finding("detach-with-target")])
    relocating = moving or detach
    if relocating and opening.get("holds"):
        raise Rejected([Finding("held-anchor", values={"thread": thread_id})])
    if title_owed and title is None and before is not None and before["title"] is None:
        raise Rejected([Finding("untitled-thread", values={"thread": thread_id})])
    if detach:
        # A thread the user took back whole is gone from the reading, and the
        # append door refuses a reply into it (`withdrawn-parent`).
        if before is not None and before["anchor"] is None:
            # Already where --detach would put it: activating the edit that removed
            # the passage, which any tab's poll may do first, detached it. The reply
            # lands without a transition, so the thread keeps the anchor it left.
            detach = relocating = False
    reply_revision = None
    prospective_anchor = None
    source_events = events
    checked = None
    if (validate_source and not ephemeral and failure is None) or detach:
        if relocating:
            # The stand-in carries the thread's move and none of the reply's text,
            # whose ids the reply's own check below compares with the page's.
            source_events = [
                *events,
                {
                    **event,
                    "id": "prospective-anchor-transition",
                    "seq": events[-1]["seq"] + 1,
                    "ts": "pending",
                    "text": "",
                    "anchor": None,
                },
            ]
        from leaf.records.revision_publication import planned_activation

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
    quoted = None
    if prospective_anchor is not None:
        revision, (anchor, quoted) = reply_revision, prospective_anchor
    elif moving:
        revision, anchor, quoted = current_anchor(
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
    asking = asking_widget(fragment, publication.registry) if markup else None
    twice = second_request(asking) if explicit_obligation else []
    # An answer that declares nothing must ask with a widget in its text. Explicit
    # obligations need no widget: the message is their source.
    if asks_back and not explicit_obligation and asking is None:
        unasked = unasked_widget(fragment, publication.registry) if markup else {}
        raise Rejected([Finding("undeclared-answer", values=unasked)])
    unannounced = (
        before is not None
        and _goes_in_unannounced(before, asks=bool(explicit_obligation or asking))
        and not ephemeral
        and failure is None
    )
    if unannounced:
        event["unannounced"] = True
    if ephemeral:
        event["ephemeral"] = True
    if in_hand is not None:
        event["start"] = {"item": in_hand}

    # The turn the reply's command acts in, which names the start it carries
    # (`todos.start_reading`) and says whether the turn that wrote a progress
    # message still runs (`activity.turn_runs`).
    if turn := acting_turn(page.claim, posting_identity.get("session")):
        event["turn"] = turn
    if explicit_obligation:
        event["obligation"] = explicit_obligation
    if promise:
        event.update(promise)
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
        from leaf.records.revision_publication import publish_checked_event

        record = publish_checked_event(page, checked, event)
        if failure is None:
            published = _Published(
                events, record["revision"], checked, thread_id if relocating else None
            )
    else:
        record, _ = append_admitted(page, event)
    # Said once the message stands, which a later gate could still refuse.
    note(*twice, *([quoted] if quoted else []))
    if title is not None and before and before["title"] not in (None, title):
        # A thread keeps the first title it was given (`events.build_threads`), so
        # the agent hears which one stands.
        note(Finding("title-kept", values={"title": before["title"]}))
    return record, published


def _goes_in_unannounced(thread: dict, *, asks: bool) -> bool:
    """Whether the agent's message goes into `thread` without reopening it, which
    the reply records as `unannounced` (`events.build_threads`): the user resolved
    the thread and it has not reopened since, whatever closed it after, and the
    message asks them nothing, in words or with a widget.

    A thread the user resolved stays off their list until someone reopens it. The
    user chose that: they end most threads with a last word and then Resolve, which
    means they are done with the thread and not that they took the word back, so
    the request stays owed (`events.owed_turns`) and its answer, like the result of
    work the agent promised, brings nothing back to their list.

    The user also chose that bringing the thread back is the agent's call (root
    `AGENTS.md`, "Leaf's role"), which it makes with `cmd_reopen`, before or after
    the message, so no rule here reads the call off the message. The reply's
    command says that it stayed closed (`stays-closed`, `post_reply`), since the
    user's resolve reaches the agent only where it retires a question, and the
    agent that was never told can still bring back what it just said. A provider's
    final message ends its turn and prints nothing its agent reads, so the
    handling Leaf delivers with a turn's answer (the kernel registry's clause for
    `answer.writer: "turn"`) has the agent post such news with the command.

    A rule that kept every message quiet would leave a question as the agent's only
    way to say it could not do what was asked. A rule keyed on the answer would
    reopen the thread for a promised result, which names no input, and leave it
    closed for the promise. A flag on the reply would have to be chosen before the
    agent knows the thread is closed, and a provider's final message could not
    carry it. A message that asks reopens the thread by itself, since the user
    answers a question in its thread and ends one they won't answer by resolving
    it."""
    return thread["closed_by_user"] and not asks


def post_response(
    reference: str,
    text,
    *,
    reservation: str | None = None,
    check: MessageCheck | None = None,
    **options,
) -> dict | None:
    """Author a complete reply at the delivery's exact captured response address.

    The reference chooses page, input and thread destination. All rich reply
    options belong to the durable writer. A direct answer refuses a superseded
    input, except where `post_reply` says; a provider's final (`reservation`,
    `ProviderFinal`) preserves its captured destination after user settlement but
    yields to another successful answer.
    Explicit addressed replies commit immediately; reservations prevent competing
    provider finals and failure receipts.

    Each write's retry key (`post_reply`'s `attempt`) is derived here, never given:
    the reservation for a provider's answer and the reservation's progress line for
    its progress, so a provider's repeat returns the first; without a reservation,
    the whole write, its reference, words and options, in disjoint namespaces for
    answers and failure receipts so a receipt's key never stands in for a later
    answer's. So only a retry identical to an earlier answer returns it, and an
    answer that differs from it goes in as its own write (`post_reply`). Progress
    without a reservation takes no key, so each line posts.
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
        write = json.dumps([reference, text, options], sort_keys=True)
        attempt = f"leaf-{namespace}-{sha256(write.encode()).hexdigest()}"
    return post_reply(
        Path(address["page"]),
        address,
        text,
        settlement=REFUSE if reservation is None else ProviderFinal(reservation),
        attempt=attempt,
        validate_source=True,
        check=check,
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


def fitted(words: str, limit: int) -> str:
    """`words` on one line, cut at a word to fit `limit` characters, ending in an
    ellipsis where it was cut. Neither the agent nor a model can count characters,
    and long words for a title or a wait break nothing, so Leaf fits them rather than
    refusing them, which would leave the thread untitled or drop the message or ask
    they ride on."""
    line = " ".join(words.split())
    if len(line) <= limit:
        return line
    return line[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def fit_title(words: str) -> str:
    """`words` as a thread title, fitted to `title_limit`."""
    return fitted(words, title_limit())


def agent_title(words: str | None) -> str | None:
    """The title the agent gave a command, fitted (`fit_title`), noting beside the
    command's result the name a cut leaves."""
    if words is None:
        return None
    title = fit_title(words)
    if len(" ".join(words.split())) > title_limit():
        note(
            Finding(
                "title-fitted",
                values={"title": title, "limit": title_limit()},
            )
        )
    return title


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
    page_dir: Path,
    message: str,
    text,
    *,
    title: str | None = None,
    check: MessageCheck | None = None,
) -> list[dict]:
    """Append a text revision to one agent-authored message, rename the thread it is
    in, or both, and return the records appended.

    The message event is immutable: the edit points back to it, so the log retains
    every wording while readings take the latest, its HTML included
    (`events.thread_structure`). HTML in the new words meets the gates a new
    message's does, `check` included, under the revision the user is looking at,
    which the edit names as such a message does. Where the message holds a widget
    the user has acted on, the edit goes in and Leaf says what becomes of their
    answer (`_answered_widgets`). A summary folding the message stands, and
    Leaf names it (`_folding_summaries`), since only the agent knows whether its
    edit changes what the summary reports. Admission refuses a message another voice
    wrote (`event_contracts._edit_error`). A rename adds no turn and changes no
    obligation. The edit and the rename land together or not at all
    (`event_contracts.append_all_admitted`), so a refused title leaves the text
    unedited.
    """
    title = agent_title(title)
    body = (
        checked_text(page_dir, text, html=True)
        if text is not None or title is None
        else None
    )
    markup = drawn_markup(body) if body is not None else ""
    if markup and check is not None:
        check(page_dir, "edit", markup)
    answered = []
    with PageTransaction(page_dir) as page:
        require_registry(page_dir)
        events = page.events
        named = None
        if title is not None:
            thread = thread_named(page_dir, events, message)
            named = title_event(thread, title)
        edit = None
        if body is not None:
            edit = {
                "kind": "edit",
                "author": "agent",
                "message": message,
                "text": body,
            }
            target = _messages(events).get(message)
            # A message Leaf refuses to edit, such as one the user wrote, is
            # admission's to refuse, in its own words.
            if target is not None and target["author"] == "agent":
                fragment = None
                if markup:
                    revision = latest_revision(page_dir)
                    fragment = check_markup(
                        page_dir,
                        "edit",
                        markup,
                        events,
                        publication=revision_publication(page_dir, revision),
                        thread=thread_names(events).get(message),
                        replacing=message,
                    )
                    if revision is not None:
                        edit["revision"] = revision
                answered = [
                    *_answered_widgets(events, message, fragment),
                    *_folding_summaries(page_dir, events, message),
                ]
        records = append_all_admitted(
            page, [event for event in (edit, named) if event is not None]
        )
    note(*answered)
    return records


def _answered_widgets(
    events: list, message: str, rewritten: SourceDocument | None
) -> list[Finding]:
    """What a rewrite of `message` to the markup `rewritten` (None for words alone)
    does to each widget in it the user has acted on. Their latest action stays
    recorded against the ids it rests on (`meaning.depends`: the widget, its unit
    and the options it chose), so it shows wherever the new markup keeps those ids,
    and not once one is gone; a child the user created through the widget lives in
    the log (`meaning.creates`), so no wording needs to hold it. Advice, since the
    agent may mean either."""
    drawn = thread_structure(events).fragments.get(message)
    if drawn is None:
        return []
    withdrawn = taken_back(events)
    acted = [
        event
        for event in events
        if event["kind"] == "action"
        and event["id"] not in withdrawn
        and event["widget"] in drawn.by_id
    ]
    created = {e["meaning"]["unit"] for e in acted if e["meaning"].get("creates")}
    rests = {e["widget"]: set(e["meaning"]["depends"]) - created for e in acted}
    kept = rewritten.ids if rewritten is not None else set()
    return [
        Finding(
            "edit-answered-widget",
            element_at(drawn.by_id[widget]["tag"], widget),
            {"message": message, "kept": ids <= kept},
        )
        for widget, ids in rests.items()
    ]


def _folding_summaries(page_dir: Path, events: list, message: str) -> list[Finding]:
    """The summary in force that folds `message`, as advice the agent reads after
    editing it: the summary stands as written (`events.active_summaries`)."""
    thread = thread_names(events).get(message)
    if thread is None:
        return []
    threads = build_threads(events, active_enclosing(page_dir))
    return [
        Finding(
            "edit-under-summary",
            values={
                "message": message,
                "summary": summary["id"],
                "from": summary["from"],
                "through": summary["through"],
            },
        )
        for summary in active_summaries(events, threads)[thread]
        if message in summary["covers"]
    ]


@contract_writer
def cmd_summarize(
    page_dir: Path,
    from_message: str,
    through_message: str,
    text,
    *,
    label: str | None = None,
    fence=None,
) -> dict | None:
    """Append a presentation summary over one contiguous message range, in the
    thread its first message sits in; or nothing, where `fence`, given the page
    under its lock, says the writer no longer should, as a fork that summarizes a
    thread for the agent (`summary_fork`)."""
    body = checked_text(page_dir, text, allow_empty=True)
    with PageTransaction(page_dir) as page:
        if fence is not None and not fence(page):
            return None
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


@contract_writer
def cmd_reopen(page_dir: Path, parent: str) -> dict:
    """Reopen a thread, as the user's own Reopen does: the same event, addressed as
    `cmd_resolve` addresses its own. It is how the agent brings a thread the user
    resolved back to their list (`_goes_in_unannounced`). Like any reopening, it
    puts back a turn of theirs that a closing had ended unanswered
    (`events.owed_turns`)."""
    with PageTransaction(page_dir) as page:
        _thread_id, parent = thread_addressed(page_dir, page.events, parent)
        event = {"kind": "unresolve", "author": "agent", "parent": parent}
        return append_admitted(page, event)[0]
