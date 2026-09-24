"""Conversation writes and the host-neutral delivery-bound reply lifecycle."""

import sys
from pathlib import Path

from leaf.asks import local_ask_entry
from leaf.delivery import current_responses, record_pickup
from leaf.event_contracts import append_admitted
from leaf.event_log import read_events
from leaf.events import build_threads
from leaf.files import (
    latest_revision,
    require_revision,
    revision_path,
)
from leaf.host import message_identity
from leaf.leases import contract_writer
from leaf.passages import active_enclosing
from leaf.projection import (
    generated_children,
    page_reading,
    retirement_outcomes,
    rewritten_bodies,
)
from leaf.requests import receipt_event
from leaf.schema import MESSAGE_KINDS, THREAD_ANSWER_KINDS
from leaf.service import PageTransaction, delivery_reply_attempt
from leaf.structure import SourceDocument, parse_revision
from leaf.thread_context import thread_roots
from leaf.validation.admission import (
    check_markup,
    logged_id,
    read_text_arg,
    thread_obligation,
)


def _messages(events: list) -> dict[str, dict]:
    return {event["id"]: event for event in events if event["kind"] in MESSAGE_KINDS}


def _message(page_dir: Path, events: list, to: str) -> dict:
    messages = _messages(events)
    if to not in messages:
        held = logged_id(events, to, current_responses(page_dir, events))
        sys.exit(
            f"unknown comment id {to!r}"
            + (f"; {held}" if held else "")
            + f"; known: {sorted(messages)}"
        )
    return messages[to]


def _thread_root(page_dir: Path, events: list, to: str) -> tuple[str, dict | None]:
    _message(page_dir, events, to)
    root_id = thread_roots(events)[to]
    return root_id, _messages(events).get(root_id)


def reserve_delivery_reply(session_id: str, delivery_id: str, target: dict) -> None:
    """Reserve a delivery's response address before provider execution begins."""
    attempt = delivery_reply_attempt(delivery_id)
    with PageTransaction(Path(target["page"])) as page:
        claim = page.active_claim
        if claim is None or claim["id"] != session_id:
            raise RuntimeError(f"page is not claimed by session {session_id!r}")
        page.bind_delivery_reply(session_id, target["responds"], attempt)


def release_delivery_reply(session_id: str, delivery_id: str, target: dict) -> None:
    """Give up a delivery's reserved response address without answering it.

    Reserving the address is what stops a second writer answering a delivery the
    provider is about to answer itself. A delivery that ends without ever reaching a
    provider turn has no such answer coming, and until the reservation is given up it
    also blocks the host from saying so, so the user is left with neither.
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
    """Whether an observed provider still owns this delivery's reply address."""
    try:
        with PageTransaction(Path(target["page"])) as page:
            binding = (
                (page.status.get("stream") or {}).get("reply_bindings") or {}
            ).get(target["responds"])
            return binding == {
                "session": session_id,
                "attempt": delivery_reply_attempt(delivery_id),
            }
    except FileNotFoundError:
        return False


class DeliveryReply:
    """One delivery-bound reply from provisional text through durable commit."""

    def __init__(
        self,
        session_id: str,
        turn_id: str,
        delivery_id: str,
        target: dict,
    ):
        self.session_id = session_id
        self.turn_id = turn_id
        self.target = dict(target)
        self.attempt = delivery_reply_attempt(delivery_id)
        self.text = ""
        self.replace(None, "")

    def replace(
        self,
        item_id: str | None,
        text: str,
        *,
        settles: bool = False,
    ) -> bool:
        """Replace the visible text without appending conversation history."""
        self.text = text
        try:
            with PageTransaction(Path(self.target["page"])) as page:
                claim = page.active_claim
                if (
                    claim is None
                    or claim["id"] != self.session_id
                    or claim.get("turn") != self.turn_id
                    or claim.get("turn_closed") is not None
                ):
                    return False
                page.set_stream_reply(
                    self.session_id,
                    self.turn_id,
                    self.target["reply_to"],
                    self.target["responds"],
                    self.attempt,
                    item_id,
                    text,
                    "active",
                    settles=settles,
                )
                return True
        except FileNotFoundError:
            return False

    def finish(
        self,
        state: str,
        completed_text: str | None = None,
    ) -> BaseException | None:
        """Commit only a completed final, retaining rejected or partial text.

        A completed answer retains its delivered response address even when that
        move was settled during the turn. The reply reopens the conversation.

        The binding is given up on every way out but a commit, which clears it in
        the transaction that appends the reply. That includes the ways out that
        raise: recording the draft's last state re-reads a page the turn's own work
        may have left unopenable, and a binding left standing refuses every other
        writer the delivery's move — the carrier's receipt that no answer is coming
        among them — until the claim itself goes.
        """
        committed = False
        try:
            if state == "completed" and completed_text:
                try:
                    self._commit(completed_text)
                    committed = True
                    return None
                except (OSError, RuntimeError, SystemExit, ValueError) as error:
                    self._set_state("failed", completed_text)
                    return error
            self._set_state(
                state if state != "completed" else "partial",
                self.text,
            )
            return None
        finally:
            if not committed:
                self._release_binding()

    def disconnect(self) -> None:
        """Keep partial text visible while its provider connection recovers."""
        self._set_state("disconnected", self.text)

    def _set_state(self, state: str, text: str) -> None:
        try:
            with PageTransaction(Path(self.target["page"])) as page:
                page.set_stream_reply_state(
                    self.session_id,
                    self.turn_id,
                    self.attempt,
                    text,
                    state,
                )
        except FileNotFoundError:
            pass

    def _release_binding(self) -> None:
        _clear_delivery_reply(self.session_id, self.attempt, self.target)

    def _commit(self, text: str) -> dict | None:
        page_dir = Path(self.target["page"])
        try:
            accepted = cmd_reply(
                page_dir,
                self.target["reply_to"],
                text,
                "",
                for_event=self.target["responds"],
                attempt=self.attempt,
                when_settled="post",
                identity={"session": self.session_id},
                validate_source=True,
                claimed_session=self.session_id,
            )
            with PageTransaction(page_dir) as page:
                page.clear_delivery_reply_binding(
                    self.session_id,
                    self.target["responds"],
                    self.attempt,
                )
                page.clear_stream_reply(self.session_id, self.turn_id)
            return accepted
        except FileNotFoundError:
            return None


def thread_of(page_dir: Path, message_id: str) -> str:
    """The thread a message sits in, for a command that has to name it back."""
    return thread_roots(read_events(page_dir))[message_id]


def _current_anchor(
    page_dir: Path,
    events: list,
    quote: str,
    section: str,
    part: str,
    revision: int | None = None,
) -> tuple[int, dict | None]:
    """Capture one optional target against the page's active reading."""
    if revision is None:
        from leaf.revisioning import activate_source

        activation = activate_source(page_dir, events)
        if activation.error and (quote or section or part):
            sys.exit(f"cannot use invalid index.html: {activation.error}")
        revision = require_revision(page_dir)
    if not (quote or section or part):
        return revision, None
    document = parse_revision(page_dir, revision)
    return revision, _capture_anchor(
        page_dir, events, document, quote, section, part, revision
    )


def _capture_anchor(
    page_dir: Path,
    events: list,
    document: SourceDocument,
    quote: str,
    section: str,
    part: str,
    revision: int,
) -> dict:
    """Capture a target against one exact document reading."""
    from leaf.anchor_capture import capture_anchor
    from leaf.registry.storage import require_registry

    registry = require_registry(page_dir)
    page = page_reading(document, events, registry, revision)
    decided = retirement_outcomes(page.projection.actions)
    edited = rewritten_bodies(page.projection.actions)
    try:
        anchor = capture_anchor(
            document,
            registry,
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
    page_dir: Path, quote: str, section: str, part: str, text, markup: str
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
        revision, anchor = _current_anchor(page_dir, events, quote, section, part)
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
        return append_admitted(page, event)


@contract_writer
def cmd_reply(
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
    initiates: bool = False,
    when_settled: str = "refuse",
    only_if_unclaimed: bool = False,
    failure: str | None = None,
    identity: dict | None = None,
    validate_source: bool = False,
    claimed_session: str | None = None,
) -> dict | None:
    """Post one complete threaded reply, optionally moving or detaching its anchor.

    ``for_event`` fences the write to the exact current obligation. Its response
    address may differ from ``to`` when a widget gesture belongs to a frozen
    conversation. One unambiguous delivered reply supplies both values. ``initiates``
    explicitly posts when the conversation currently owes no reply.

    ``when_settled`` distinguishes completed delivery answers from failure receipts.
    ``post`` retains the delivered response address even after settlement; ``skip``
    omits a receipt when no answer is owed. The default ``refuse`` rejects a stale
    response address from an ordinary CLI writer.

    ``failure`` records a host-owned failure code alongside its presentation text;
    ordinary agent answers omit it.
    """
    body = read_text_arg(page_dir, text)
    posting_identity = message_identity() if identity is None else identity
    with PageTransaction(page_dir) as page:
        if claimed_session is not None:
            claim = page.active_claim
            if claim is None or claim["id"] != claimed_session:
                raise RuntimeError(
                    f"page is no longer claimed by session {claimed_session!r}"
                )
            posting_identity = {"agent": claim["agent"], "session": claim["id"]}
        events = page.events
        if attempt is not None:
            existing = next(
                (event for event in events if event.get("attempt") == attempt), None
            )
            if existing:
                same_scope = (
                    existing.get("responds") == for_event
                    if for_event is not None
                    else existing.get("initiates") is True
                    if initiates
                    else True
                )
                if (
                    existing["kind"] != "reply"
                    or (to is not None and existing["parent"] != to)
                    or not same_scope
                ):
                    sys.exit(f"attempt {attempt!r} already belongs to another event")
                return existing
        responses = current_responses(page_dir, events)
        if initiates:
            if for_event is not None:
                sys.exit("reply accepts --for or --initiates, not both")
            if to is None:
                sys.exit("reply --initiates requires --to")
        elif for_event is None:
            if to is not None:
                sys.exit(
                    "use --for EVENT_ID to answer user input; "
                    "--to ID --initiates starts a new message when no reply is owed"
                )
            claim = page.active_claim
            delivered = (
                {
                    event_id
                    for event in events
                    if event["kind"] == "pickup"
                    and event["phase"] == "opened"
                    and event["session"] == claim["id"]
                    and event["turn"] == claim.get("turn")
                    for event_id in event["events"]
                }
                if claim is not None
                and posting_identity.get("session") == claim["id"]
                and claim.get("turn") is not None
                and claim.get("turn_closed") is None
                else set()
            )
            pending = [
                (event_id, response)
                for event_id, response in responses.items()
                if event_id in delivered and response["kind"] == "reply"
            ]
            if len(pending) != 1:
                sys.exit(
                    "cannot infer a reply: this turn's opened delivery holds "
                    f"{len(pending)} reply obligations. Read what the page still "
                    "owes with `leaf page state <page>`; use --for EVENT_ID to "
                    "answer one, or --to ID --initiates only if that read shows "
                    "nothing owed"
                )
            for_event, expected = pending[0]
            to = expected["to"]
        else:
            expected = responses.get(for_event)
            if expected is None or expected["kind"] not in THREAD_ANSWER_KINDS:
                held = logged_id(events, for_event, responses)
                refusal = f"event {for_event!r} takes no reply; " + (
                    held or f"this page's log holds no event {for_event!r}"
                )
                if when_settled == "skip":
                    return None
                if when_settled != "post" or to is None:
                    sys.exit(refusal)
            elif to is None:
                to = expected["to"]
        assert to is not None
        root_id, root = _thread_root(page_dir, events, to)
        if for_event is not None:
            expected = responses.get(for_event)
            if (
                expected is None
                or expected["kind"] not in THREAD_ANSWER_KINDS
                or (expected["to"], expected["for"]) != (to, for_event)
            ):
                if when_settled == "skip":
                    return None
                if when_settled != "post":
                    sys.exit(
                        f"event {for_event!r} no longer requires a reply to {to!r}; "
                        "read the current delivery or conversation state"
                    )
            elif expected["kind"] == "turn" and expected["attempt"] != attempt:
                sys.exit(
                    f"event {for_event!r} is answered by this turn's messages; "
                    "finish the reply in your final message"
                )
        else:
            standing = thread_obligation(events, responses, root_id)
            if standing is not None and standing["kind"] == "turn":
                sys.exit(
                    f"conversation {root_id!r} is answered by this turn's messages; "
                    "finish the reply in your final message"
                )
            if standing is not None:
                sys.exit(
                    f"conversation {root_id!r} currently requires a response; "
                    f"use `--for {standing['for']}` instead of --initiates"
                )
        if only_if_unclaimed and any(
            event["kind"] == "pickup" and for_event in event["events"]
            for event in events
        ):
            return None
        moving = bool(quote or section or part)
        if detach and moving:
            sys.exit("--detach cannot be combined with --quote, --section, or --part")
        relocating = moving or detach
        if relocating and root is None:
            sys.exit(
                f"thread {root_id!r} has no surviving opening comment, so its "
                "anchor cannot be changed"
            )
        if relocating and root.get("holds"):
            sys.exit(
                f"thread {root_id!r} holds the command goal named by its opening "
                "comment, so its anchor cannot be changed"
            )
        current_thread = (
            build_threads(events, active_enclosing(page_dir)).get(root_id)
            if detach
            else None
        )
        if detach and (current_thread is None or current_thread["anchor"] is None):
            sys.exit(f"conversation {root_id!r} has no current anchor to detach")
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
            if detach or section:
                source_events = [
                    *events,
                    {
                        "kind": "reply",
                        "id": "prospective-anchor-transition",
                        "parent": to,
                        "anchor": (
                            None
                            if detach
                            else {
                                "section": section,
                                **({"visual": part} if part else {}),
                            }
                        ),
                    },
                ]
            if source_matches_active:
                reply_revision = active
            else:
                from leaf.validation.source import check_source

                checked = check_source(page_dir, source_events, allow_transition=False)
                if checked.errors:
                    operation = "reply" if validate_source else "detach"
                    sys.exit(
                        f"cannot {operation} while index.html is invalid: "
                        f"{'; '.join(checked.errors)}"
                    )
                prospective_page = checked.document
                if moving:
                    prospective_anchor = _capture_anchor(
                        page_dir,
                        events,
                        checked.document,
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
            from leaf.revisioning import activate_checked_source

            activation = activate_checked_source(page_dir, checked)
            if activation.error:
                operation = "reply" if validate_source else "detach"
                sys.exit(
                    f"cannot {operation} while index.html is invalid: {activation.error}"
                )
            reply_revision = activation.revision
        if prospective_anchor is not None:
            revision, anchor = reply_revision, prospective_anchor
        elif moving:
            revision, anchor = _current_anchor(
                page_dir, events, quote, section, part, revision=reply_revision
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
            "text": body,
            **(
                {"responds": for_event}
                if for_event is not None
                else {"initiates": True}
            ),
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
        return append_admitted(page, event)


def fail_answer(
    page_dir: Path,
    responds: str,
    failure: str,
    text: str,
    *,
    attempt: str,
    identity: dict,
    only_if_unclaimed: bool,
) -> dict | None:
    """Tell the user no answer to one move is coming, in the move's own terms.

    A host that gives up on a move settles the obligation the move's workflow
    `answer` names and hands the next step back to the user, so a failed move is
    never left owed with nobody to answer it:

    - a `reply` answer takes a reply carrying `failure` in its conversation, which
      the user resends into; a `turn` answer refuses it until its turn gives the
      reply up and the answer reads as a `reply` again;
    - a `receipt` answer takes a failed receipt carrying `failure`, the request's
      own terminal outcome, which reopens its seat for the user to press again;
    - a `markup` answer takes a failed pickup: the user's Ask answer stands in the
      log, and answering again sends a new move.

    A move with no answer outstanding writes nothing, except that a repeated reply
    receipt is found by its `attempt` and returned. `only_if_unclaimed` leaves a move
    some turn already picked up to the writer following that turn.
    """
    with PageTransaction(page_dir) as page:
        answer = current_responses(page_dir, page.events).get(responds)
    if answer is not None and answer["kind"] in {"receipt", "markup"}:
        return _fail_page_answer(
            page_dir, responds, failure, text, identity, only_if_unclaimed
        )
    return cmd_reply(
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
    )


@contract_writer
def _fail_page_answer(
    page_dir: Path,
    responds: str,
    failure: str,
    text: str,
    identity: dict,
    only_if_unclaimed: bool,
) -> dict | None:
    """Write a receipt or markup failure, rechecking the answer under the lock."""
    with PageTransaction(page_dir) as page:
        events = page.events
        answer = current_responses(page_dir, events).get(responds)
        if answer is None or (
            only_if_unclaimed
            and any(
                event["kind"] == "pickup" and responds in event["events"]
                for event in events
            )
        ):
            return None
        if answer["kind"] == "receipt":
            return append_admitted(
                page, receipt_event(responds, "failed", text, identity, failure)
            )
        [move] = [event for event in events if event["id"] == responds]
        return record_pickup(page, [move], phase="failed", failure=failure)


@contract_writer
def cmd_edit(page_dir: Path, to: str, text) -> dict:
    """Append a text revision to one message authored by this agent session.

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
        owner = target.get("session")
        if not owner:
            sys.exit(f"message {to!r} has no agent session identity")
        if owner != identity.get("session"):
            sys.exit(f"message {to!r} belongs to agent session {owner!r}")
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


@contract_writer
def cmd_title(page_dir: Path, conversation: str, text: str) -> dict:
    """Name a conversation without adding a turn or changing its obligations."""
    with PageTransaction(page_dir) as page:
        return append_admitted(
            page,
            {
                "kind": "conversation_title",
                "author": "agent",
                **message_identity(),
                "conversation": conversation,
                "title": text,
            },
        )


@contract_writer
def cmd_summarize(
    page_dir: Path,
    conversation: str,
    from_message: str,
    through_message: str,
    text,
) -> dict:
    """Append a presentation summary over one contiguous message range."""
    from leaf.registry.storage import require_registry

    body = read_text_arg(page_dir, text)
    with PageTransaction(page_dir) as page:
        require_registry(page_dir)
        return append_admitted(
            page,
            {
                "kind": "summary",
                "author": "agent",
                **message_identity(),
                "conversation": conversation,
                "from": from_message,
                "through": through_message,
                "text": body,
            },
        )


@contract_writer
def cmd_resolve(page_dir: Path, to: str) -> dict:
    """Close a thread, as the user's own ✓ Resolve does. Same event, same rule on
    `parent` — any message in the thread names it — and `author` the whole
    difference, which is how the panel can say who closed it."""
    with PageTransaction(page_dir) as page:
        _message(page_dir, page.events, to)
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
    a stamped revision absorbs or overrules it by id (see `version stamp`), and the
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
        events = page.events
        activate_source(page_dir, events)
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
