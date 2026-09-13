"""CLI commands that write conversation and worker-report events."""

import json
import sys
from pathlib import Path

from leaf.asks import local_ask_entry, page_awaiting_values
from leaf.delivery import current_responses
from leaf.event_contracts import report_contract_error
from leaf.event_log import read_events
from leaf.events import build_threads
from leaf.files import (
    latest_published,
    latest_revision,
    require_revision,
    revision_path,
    version_revisions,
)
from leaf.host import message_identity
from leaf.leases import contract_writer
from leaf.passages import active_enclosing
from leaf.projection import (
    generated_children,
    markup_facet,
    page_reading,
    retirement_outcomes,
    rewritten_bodies,
)
from leaf.schema import MESSAGE_KINDS
from leaf.service import PageTransaction
from leaf.structure import SourceDocument, parse_revision
from leaf.thread_context import thread_roots
from leaf.validation.admission import check_markup, read_text_arg


def _messages(events: list) -> dict[str, dict]:
    return {event["id"]: event for event in events if event["kind"] in MESSAGE_KINDS}


def _message(events: list, to: str) -> dict:
    messages = _messages(events)
    if to not in messages:
        sys.exit(f"unknown comment id {to!r}; known: {sorted(messages)}")
    return messages[to]


def _thread_root(events: list, to: str) -> tuple[str, dict | None]:
    _message(events, to)
    root_id = thread_roots(events)[to]
    return root_id, _messages(events).get(root_id)


def thread_of(page_dir: Path, message_id: str) -> str:
    """The thread a message sits in, for a command that has to name it back."""
    return thread_roots(read_events(page_dir))[message_id]


def _version_response_unanswered(page_dir: Path, events: list, root: dict) -> bool:
    """Whether the page still owes this root the authored answer it asked for.

    Both readings below project markup alone: the empty event lists are the gate's
    subject rather than an omission. The reader's own pick lives in the log, and
    folding it in moved whichever side of the comparison it happened to fall on —
    before the proposal it answered the originating revision, after it the current
    one — so the same markup resolved or refused according to where one press
    landed in the log. A stamped version is what this thread asked for, so an
    unstamped live revision cannot settle it.
    """
    from leaf.registry.storage import require_registry

    version = latest_published(page_dir, events)
    revision = version_revisions(events)[version]
    if revision <= root["revision"]:
        return True
    registry = require_registry(page_dir)
    document = parse_revision(page_dir, revision)
    page = page_reading(document, [], registry, revision)
    projection, parser, spk = page.projection, page.document, page.spoken
    awaiting = page_awaiting_values(document, projection, spk, registry)
    target = root["anchor"]["section"]
    if awaiting.get(target, False):
        return True

    current = parser.by_id.get(target)
    if current is None:
        return True
    response = root["response"]
    current_entry = registry.get(current["tag"], {})
    if (current_entry.get("x-conversation") or {}).get("response") != response:
        return True

    original_revision = root["revision"]
    original_document = parse_revision(page_dir, original_revision)
    original_page = page_reading(original_document, [], registry, original_revision)
    original_projection = original_page.projection
    original = original_page.document
    original_spk = original_page.spoken
    original_awaiting = page_awaiting_values(
        original,
        original_projection,
        original_spk,
        registry,
    )
    if original_awaiting.get(target, False):
        return False

    spec = current_entry["x-state"][response["verb"]]
    current_answer = markup_facet(target, spec, parser.by_id, spk, registry)
    original_answer = markup_facet(target, spec, original.by_id, original_spk, registry)
    return current_answer == original_answer


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
    decided = retirement_outcomes(page.projection.actions, registry)
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
        sys.exit(f"can't anchor in revision r{revision}: {err}")
    return anchor


@contract_writer
def cmd_comment(
    page_dir: Path, quote: str, section: str, part: str, text, markup: str
) -> None:
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
            "author": "claude",
            **message_identity(),
            "revision": revision,
            "text": body,
        }
        if anchor:
            event["anchor"] = anchor
        if markup:
            event["markup"] = markup
        accepted = page.append_event(event)
    print(json.dumps(accepted, ensure_ascii=False))


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
    skip_if_settled: bool = False,
    only_if_unclaimed: bool = False,
    failure: str | None = None,
    identity: dict | None = None,
    validate_source: bool = False,
) -> dict | None:
    """Post one complete threaded reply, optionally moving or detaching its anchor.

    ``for_event`` fences the write to the exact current obligation. Its response
    address may differ from ``to`` when a widget gesture belongs to a frozen
    conversation. One unambiguous delivered reply supplies both values. ``initiates``
    explicitly posts when the conversation currently owes no reply. Durable hosts may
    make an already-settled retry a no-op. ``failure`` records a host-owned failure
    code alongside its presentation text; ordinary agent answers omit it.
    """
    body = read_text_arg(page_dir, text)
    posting_identity = message_identity() if identity is None else identity
    with PageTransaction(page_dir) as page:
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
                sys.exit("a delivered reply uses --for; omit --to to infer both")
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
                    "reply needs exactly one reply obligation from this turn's "
                    "opened delivery to infer; use --for EVENT_ID when more than "
                    "one was delivered"
                )
            for_event, expected = pending[0]
            to = expected["to"]
        else:
            expected = responses.get(for_event)
            if expected is not None and expected["kind"] == "version":
                root_id, _ = _thread_root(events, to or expected["conversation"])
                if skip_if_settled:
                    return None
                sys.exit(
                    f"thread {root_id!r} requires a page version and cannot take a "
                    "reply; incorporate its request in the next version, or open a "
                    "separate thread on the same Ask with `leaf comment --section "
                    "<ask-id>` if you need an answer first"
                )
            if expected is None or expected["kind"] != "reply":
                if skip_if_settled:
                    return None
                sys.exit(
                    f"event {for_event!r} no longer requires a reply; "
                    "read the current delivery or conversation state"
                )
            if to is None:
                to = expected["to"]
        assert to is not None
        root_id, root = _thread_root(events, to)
        if root and (root.get("response") or {}).get("kind") == "version":
            if skip_if_settled:
                return None
            sys.exit(
                f"thread {root_id!r} requires a page version and cannot take a reply; "
                "incorporate its request in the next version, or open a separate "
                "thread on the same Ask with `leaf comment --section <ask-id>` if "
                "you need an answer first"
            )
        if for_event is not None:
            expected = responses.get(for_event)
            if expected != {"kind": "reply", "to": to, "for": for_event}:
                if skip_if_settled:
                    return None
                sys.exit(
                    f"event {for_event!r} no longer requires a reply to {to!r}; "
                    "read the current delivery or conversation state"
                )
        else:
            reply_roots = {
                _thread_root(events, response["to"])[0]
                for response in responses.values()
                if response["kind"] == "reply"
            }
            if root_id in reply_roots:
                sys.exit(
                    f"conversation {root_id!r} currently requires a response; "
                    "use the delivered --for event instead of --initiates"
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
            "author": "claude",
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
        if relocating:
            event["revision"] = revision
            event["anchor"] = anchor
        return page.append_event(event)


@contract_writer
def cmd_edit(page_dir: Path, to: str, text) -> dict:
    """Append a text revision to one message authored by this agent session.

    The message event is immutable: the edit points back to it, so the log retains
    every wording while thread folds project the latest one. Markup stays frozen with
    the original message because reader actions may already rest on widgets it sent.
    """
    from leaf.registry.storage import require_registry

    body = read_text_arg(page_dir, text)
    with PageTransaction(page_dir) as page:
        require_registry(page_dir)
        events = page.events
        target = _message(events, to)
        if target["author"] != "claude":
            sys.exit(f"message {to!r} is not agent-authored")
        identity = message_identity()
        owner = target.get("session")
        if not owner:
            sys.exit(f"message {to!r} has no agent session identity")
        if owner != identity.get("session"):
            sys.exit(f"message {to!r} belongs to agent session {owner!r}")
        return page.append_event(
            {
                "kind": "edit",
                "author": "claude",
                **identity,
                "message": to,
                "text": body,
            },
        )


@contract_writer
def cmd_resolve(page_dir: Path, to: str) -> None:
    """Close a thread, as the reader's own ✓ Resolve does. Same event, same rule on
    `parent` — any message in the thread names it — and `author` the whole
    difference, which is how the panel can say who closed it."""
    with PageTransaction(page_dir) as page:
        events = page.events
        root_id, root = _thread_root(events, to)
        if (
            root
            and (root.get("response") or {}).get("kind") == "version"
            and _version_response_unanswered(page_dir, events, root)
        ):
            sys.exit(
                f"thread {root_id!r} requires a page version that answers its "
                "originating Ask, or changes its declared answer if it was already "
                "answered, before the agent can resolve it"
            )
        event = {
            "kind": "resolve",
            "author": "claude",
            **message_identity(),
            "parent": to,
        }
        accepted = page.append_event(event)
    print(json.dumps(accepted, ensure_ascii=False))


@contract_writer
def cmd_report(
    page_dir: Path,
    widget: str,
    verb: str,
    fields: tuple,
    *,
    references: str | None = None,
) -> None:
    """A worker's provisional news: a declared state change folded onto a page
    widget, validated at this door the way the POST door validates an action,
    stamped with the posting session's voice, and made against the active revision —
    the page the reader is looking at. The runtime paints it live; it stands until
    a stamped revision absorbs or overrules it by id (see `version stamp`), and the
    page's watcher wakes to fold it in. Field values
    are strings — the declared detail schemas for reports speak in attribute
    values, which is all a report may move."""
    from leaf.registry.storage import require_registry
    from leaf.revisioning import activate_source

    detail = {}
    for field in fields:
        name, eq, value = field.partition("=")
        if not eq or not name:
            sys.exit(f"detail fields are name=value, got {field!r}")
        detail[name] = value
    parsed_references = None
    if references is not None:
        try:
            parsed_references = json.loads(references)
        except json.JSONDecodeError as error:
            sys.exit(f"references must be one JSON object: {error.msg}")
    with PageTransaction(page_dir) as page:
        events = page.events
        activate_source(page_dir, events)
        revision = require_revision(page_dir)
        registry = require_registry(page_dir)
        event = {
            "kind": "report",
            "author": "claude",
            **message_identity(),
            "widget": widget,
            "action": verb,
            "detail": detail,
            "revision": revision,
            **({"references": parsed_references} if references is not None else {}),
        }
        if error := report_contract_error(
            event, parse_revision(page_dir, revision), registry
        ):
            sys.exit(error)
        accepted = page.append_event(event, registry)
    print(json.dumps(accepted, ensure_ascii=False))
