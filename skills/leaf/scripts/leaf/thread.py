"""Thread writes, addressed response admission, and provider reply reservations."""

import sys
from hashlib import sha256
from pathlib import Path

from leaf.activity import answer_command
from leaf.asks import local_ask_entry
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
    sys.exit(
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
        sys.exit(f"{name} is a widget on the page, not a thread")
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
            sys.exit(f"cannot use invalid index.html: {activation.error}")
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
        sys.exit(f"can't anchor in revision r{revision}: {err}{recourse}")
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
        if title is not None and (refusal := title_refusal(page_dir, title)):
            sys.exit(refusal)
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
        return append_admitted(page, event)


def successful_replies(events: list[dict], for_event: str) -> list[dict]:
    """Agent answers to this exact input, excluding progress and failure receipts.

    A thread parent locates presentation; only ``responds`` names the input an
    answer settles. User replies, progress and failures do not assert an answer.
    """
    return [
        event
        for event in events
        if event["kind"] == "reply"
        and event["author"] == "agent"
        and event.get("responds") == for_event
        and not event.get("ephemeral")
        and "failure" not in event
    ]


def answered_by_reply(events: list[dict], for_event: str) -> bool:
    """A successful exact reply wins over every later delivery completion.

    Failure receipts and user settlement do not assert a provider answer, so a
    recovered final message may still answer that original delivered address.
    """
    return bool(successful_replies(events, for_event))


@contract_writer
def post_reply(
    page_dir: Path,
    to: str | None,
    text,
    markup: str,
    awaits: bool = False,
    *,
    for_event: str | None,
    quote: str = "",
    section: str = "",
    part: str = "",
    detach: bool = False,
    attempt: str | None = None,
    when_settled: str = "refuse",
    only_if_unclaimed: bool = False,
    failure: str | None = None,
    identity: dict | None = None,
    validate_source: bool = False,
    claimed_session: str | None = None,
    ephemeral: bool = False,
    captured_input: dict | None = None,
    captured_claim: str | None = None,
    title: str | None = None,
    reservation: str | None = None,
) -> dict | None:
    """Post one complete threaded reply, optionally moving or detaching its anchor;
    the appended record, or the earlier reply a repeated `attempt` names, or none
    when `when_settled` leaves nothing to write.

    ``for_event`` fences the write to the exact current obligation. Its response
    address may differ from ``to`` when a widget gesture belongs to a frozen
    thread. The immutable response reference supplies both values. ``to``
    without ``for_event`` posts a new agent message, which the thread must
    currently owe no reply for; the event then carries no ``responds``.

    ``when_settled`` distinguishes completed delivery answers from failure receipts.
    ``post`` retains the delivered response address even after settlement, but
    yields to an answer another writer already gave the move (a failure receipt
    is no answer), so a turn's answer committed after its binding lapsed never
    answers twice; ``skip`` omits a receipt when no answer is owed. The default ``refuse`` rejects a stale
    response address from an ordinary CLI writer.

    ``failure`` records a harness-owned failure code alongside its presentation text;
    ordinary agent answers omit it.

    ``ephemeral`` posts progress at the same response address without answering it.
    It remains content, and cannot carry a question, widgets, failure or relocation.
    Progress on a move the agent owes says what it has in hand, so it also takes that
    move in hand with its text as the line (`tasks.start_reading`), which is why that
    text is one line: the move reads Working beside its thread and in the banner, and
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
        if captured_input is not None and captured_claim != page.delivery_owner:
            raise ReceiptRefused("response page claim no longer matches its delivery")
        provider_session = (
            posting_identity.get("session") if reservation is not None else None
        )
        events = page.events
        if captured_input is not None and not any(
            event["id"] == captured_input["id"]
            and event["seq"] == captured_input["seq"]
            for event in events
        ):
            raise ReceiptRefused("response no longer matches its page log")
        if attempt is not None:
            existing = next(
                (event for event in events if event.get("attempt") == attempt), None
            )
            if existing:
                same_scope = (
                    existing.get("responds") == (None if ephemeral else for_event)
                    if for_event is not None or to is not None
                    else True
                )
                if (
                    existing["kind"] != "reply"
                    or bool(existing.get("ephemeral")) != ephemeral
                    or (to is not None and existing["parent"] != to)
                    or not same_scope
                ):
                    sys.exit(f"attempt {attempt!r} already belongs to another event")
                return existing
        if (
            when_settled == "post"
            and for_event is not None
            and answered_by_reply(events, for_event)
        ):
            return None
        responses = current_responses(page_dir, events)
        if for_event is not None and to is None:
            expected = responses.get(for_event)
            if expected is None or expected["kind"] != "reply":
                held = logged_id(events, for_event, responses)
                refusal = f"event {for_event!r} takes no reply; " + (
                    held or f"this page's log holds no event {for_event!r}"
                )
                if when_settled == "skip":
                    return None
                sys.exit(refusal)
            to = expected["to"]
        assert to is not None
        thread_id, to = thread_addressed(page_dir, events, to)
        opening = _messages(events).get(thread_id)
        # Current custody belongs to the binding, independently of capture-time
        # writer hints and caller-supplied retry identity.
        in_hand = None
        if for_event is not None:
            expected = responses.get(for_event)
            if (
                expected is None
                or expected["kind"] != "reply"
                or (expected["to"], expected["for"]) != (to, for_event)
            ):
                if when_settled == "skip":
                    return None
                if when_settled != "post":
                    sys.exit(
                        f"event {for_event!r} no longer requires a reply to {to!r}; "
                        "read the current delivery or thread state"
                    )
            elif ephemeral:
                in_hand = for_event
            binding = page.standing_reply_binding(for_event)
            if binding is not None:
                if reservation is not None:
                    if (provider_session, reservation) != (
                        binding["session"],
                        binding["attempt"],
                    ):
                        return None
                elif not ephemeral and (captured_input is None or failure is not None):
                    refusal = (
                        f"event {for_event!r} is answered by this turn's messages; "
                    )
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
                    sys.exit(refusal)
        else:
            standing = thread_obligation(events, responses, thread_id)
            if standing is not None:
                sys.exit(
                    f"thread {thread_id!r} currently requires a response; "
                    f"{answer_command(standing)} answers it"
                )
        if only_if_unclaimed and pickup_receipts(
            events, phase=None, input_id=for_event
        ):
            return None
        moving = bool(quote or section or part)
        if ephemeral and (awaits or markup or failure or moving or detach):
            sys.exit(
                "--ephemeral is for progress text; it cannot ask a question, carry widgets, report failure, or move the thread"
            )
        if in_hand is not None and start_line_error(text.strip()):
            sys.exit(
                f"progress on {in_hand!r}, a move you owe, takes it in hand, and its "
                "text is the Working line beside the thread and in the banner: write "
                "it as one line saying what you are doing"
            )
        if detach and moving:
            sys.exit("--detach cannot be combined with --quote, --section, or --part")
        relocating = moving or detach
        if relocating and opening is None:
            sys.exit(
                f"thread {thread_id!r} has no surviving opening comment, so its "
                "anchor cannot be changed"
            )
        if relocating and opening.get("holds"):
            sys.exit(
                f"thread {thread_id!r} holds the command goal named by its opening "
                "comment, so its anchor cannot be changed"
            )
        current_thread = (
            build_threads(events, active_enclosing(page_dir)).get(thread_id)
            if detach
            else None
        )
        if detach and (current_thread is None or current_thread["anchor"] is None):
            sys.exit(f"thread {thread_id!r} has no current anchor to detach")
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
                        **({"responds": for_event} if for_event is not None else {}),
                    },
                ]
            if source_matches_active:
                reply_revision = active
            else:
                from leaf.validation.source import check_source

                checked = check_source(page_dir, source_events)
                if checked.errors:
                    operation = "reply" if validate_source else "detach"
                    sys.exit(
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
        if awaits and fragment:
            from leaf.registry.storage import require_registry

            registry = require_registry(page_dir)
            structural = sorted(
                {
                    rec["tag"]
                    for rec in fragment.lf_elements
                    if local_ask_entry(registry.get(rec["tag"]) or {})
                }
            )
            if structural:
                sys.exit(
                    "--awaits is for a prose question; reply markup already declares "
                    "a local Ask "
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
            **(
                {"responds": for_event}
                if for_event is not None and not ephemeral
                else {}
            ),
        }
        if ephemeral:
            event["ephemeral"] = True
        if in_hand is not None:
            claim = page.claim
            turn = (
                claim.get("turn")
                if claim and claim["id"] == posting_identity.get("session")
                else None
            )
            event["start"] = {
                "item": in_hand,
                **({"turn": turn} if turn else {}),
            }
        if awaits:
            event["awaits"] = True
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
            record = append_admitted(page, event)
        if in_hand is not None and page.status["state"] == "idle":
            page.set_status("waiting", "")
        return record


def post_response(
    reference: str, text, markup: str = "", *, reservation: str | None = None, **options
) -> dict | None:
    """Author a complete reply at the delivery's exact captured response address.

    The reference chooses page, input and frozen thread destination. All rich reply
    options belong to the durable writer. A direct write refuses a superseded input;
    a provider's final preserves its captured destination after user settlement but
    yields to another successful answer. Explicit addressed replies commit immediately;
    reservations prevent competing provider finals and failure receipts.
    """
    address = response_address(reference)
    if address["kind"] != "reply":
        sys.exit(
            f"response {reference!r} requires {answer_command(address)}, not a reply"
        )
    attempt = options.pop("attempt", None)
    if reservation is None and (attempt is not None or not options.get("ephemeral")):
        # Public retry keys identify this addressed author's writes, never a
        # provider's reservation. The disjoint namespace prevents a progress
        # retry key from consuming its provider final's append identity too.
        retry = reference if attempt is None else f"{reference}:{attempt}"
        attempt = f"leaf-response-{sha256(retry.encode()).hexdigest()}"
    return post_reply(
        Path(address["page"]),
        address["to"],
        text,
        markup,
        for_event=address["for"],
        captured_input=address["input"],
        captured_claim=address["claim"],
        attempt=attempt,
        when_settled="post" if reservation is not None else "refuse",
        validate_source=True,
        reservation=reservation,
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
    """Tell the user no answer to one move is coming, in the move's own terms.

    A harness that gives up on a move settles the obligation the move's workflow
    `answer` names and hands the next step back to the user, so a failed move is
    never left owed with nobody to answer it:

    - a `reply` answer takes a reply carrying `failure` in its thread, which
      the user resends into; provider custody refuses it until its turn gives the
      reply up;
    - a `markup` answer takes a failed pickup: the user's Ask answer stands in the
      log, and answering again sends a new move.

    A move with no answer outstanding writes nothing, except that a repeated reply
    receipt is found by its `attempt` and returned. `only_if_unclaimed` leaves a move
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
        None,
        text,
        "",
        for_event=responds,
        attempt=attempt,
        when_settled="skip",
        only_if_unclaimed=only_if_unclaimed,
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
    """Record a failed pickup of a page move, rechecking its answer under the lock."""
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
        [move] = [event for event in events if event["id"] == responds]
        return record_pickup(page, [move], phase="failed", failure=failure)


@contract_writer
def cmd_edit(page_dir: Path, to: str, text) -> dict:
    """Append a text revision to one agent-authored message.

    The message event is immutable: the edit points back to it, so the log retains
    every wording while thread folds project the latest one. Markup stays frozen with
    the original message because user actions may already rest on widgets it sent.
    """
    from leaf.registry.storage import require_registry

    body = read_text_arg(page_dir, text)
    with PageTransaction(page_dir) as page:
        require_registry(page_dir)
        events = page.events
        target = _message(page_dir, events, to)
        if target["author"] != "agent":
            sys.exit(f"message {to!r} is not agent-authored")
        identity = message_identity()
        return append_admitted(
            page,
            {
                "kind": "edit",
                "author": "agent",
                **identity,
                "message": to,
                "text": body,
            },
        )


def title_event(thread: str, title: str, identity: dict) -> dict:
    """The `thread_title` event naming `thread`, in the voice of `identity`."""
    return {
        "kind": "thread_title",
        "author": "agent",
        **identity,
        "thread": thread,
        "title": title,
    }


def title_refusal(page_dir: Path, title: str) -> str | None:
    """What admission would say of `title`, asked before a command posts the message
    whose thread it names: a command that posts and names does neither when the name
    is refused, rather than posting and then failing."""
    from leaf.event_contracts import (
        admitting_registry,
        command_error,
    )
    from leaf.page_view import PageView

    event = title_event("pending", title, message_identity())
    registry = admitting_registry(PageView(page_dir), event, read_events(page_dir))
    return command_error(event, registry["$events"]["kinds"])


def name_untitled(page, thread: str, title: str, identity: dict) -> dict | None:
    """Append `thread`'s first title in the voice of `identity`, within the caller's
    page transaction, or nothing where it has one: a name given once stands until
    someone renames the thread on purpose (`cmd_title`)."""
    if (
        build_threads(page.events, active_enclosing(page.page_dir))[thread]["title"]
        is not None
    ):
        return None
    return append_admitted(page, title_event(thread, title, identity))


@contract_writer
def cmd_title(page_dir: Path, thread: str, text: str) -> dict:
    """Name the thread `thread` reaches without adding a turn or changing its
    obligations."""
    with PageTransaction(page_dir) as page:
        return append_admitted(
            page,
            title_event(
                thread_named(page_dir, page.events, thread), text, message_identity()
            ),
        )


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
        return append_admitted(
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
        return append_admitted(page, event)


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
            sys.exit(f"detail fields are name=value, got {field!r}")
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
        return append_admitted(page, event)
