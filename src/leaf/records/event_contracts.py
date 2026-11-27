"""Shared event admission; the contract is events.md, "Admission".

`admitted_event` validates and derives a record from `page_view.PageView`, the
current log, and a command. `append_admitted` performs that reading and write
under `transaction.PageTransaction`'s lease, and `append_all_admitted` does so for
several events that land together or not at all.

This module selects each kind's gates. Their implementations stay with their
domains: undo in `events` and widget meaning in `event_meaning`.
"""

from pathlib import Path
from typing import Protocol

from leaf.base.findings import Finding
from leaf.base.harness import message_identity
from leaf.base.state import now_iso
from leaf.log.event_log import (
    APPEND_STAMPED,
    EventRefused,
    matching_attempt,
    new_event_id,
)
from leaf.log.events import (
    build_threads,
    spoken_turns,
    taken_back,
    undo_error,
    unshown,
)
from leaf.log.obligations import questions_in_words
from leaf.log.projection import (
    AuthoredOrders,
    container_owner,
    generated_children,
    projected_action_holders,
    record_members,
    recorded_owner,
)
from leaf.log.thread_context import thread_names
from leaf.records.event_meaning import AdmissionReadings, admit_widget_event
from leaf.records.markup_checks.instances import attribute_slot_errors
from leaf.records.page_view import CandidatePageView, PageView
from leaf.records.plans import plan_error
from leaf.records.read_state import read_contract_error
from leaf.records.todos import start_reading, todo_error
from leaf.records.work import widget_seat_error
from leaf.records.workflows import agent_inputs, attention_reading
from leaf.source.registry.contract import (
    created_child,
    detail_schema,
    event_spec,
    state_specs,
    verb_writer,
    visual_parts,
)
from leaf.source.registry.kernel import (
    kernel_event_kinds,
    kernel_event_ownership,
    kinds_declaring,
    verb_writers,
)
from leaf.source.registry.schema import schema_complaint
from leaf.source.registry.storage import IncompatibleLayer, layer_record
from leaf.source.structure import quoted_in


class OpenTransaction(Protocol):
    """An open page transaction (`transaction.PageTransaction`), as admission reads the
    log under its lease and appends to it."""

    @property
    def page_dir(self) -> Path: ...
    @property
    def events(self) -> list: ...

    def _append_record(self, event: dict) -> dict: ...


def event_record_error(contract: dict, event: dict) -> Finding | None:
    """The first complaint from one event kind's stored-record contract."""
    return invalid_event(contract["record"], event)


def command_record_schema(contract: dict) -> dict:
    """The stored record's shape before admission derives its meaning.

    A command may name its envelope where its writer owns it, but meaning always
    comes from admission. Both browser ingress and sample construction check
    this shape before any gate reads kind-specific fields.
    """
    schema = contract["record"]
    derived = kernel_event_ownership()["derived"]
    return {
        **schema,
        "properties": {
            key: value
            for key, value in schema["properties"].items()
            if key not in derived
        },
        "required": [key for key in schema["required"] if key not in derived],
    }


def browser_command_error(contract: dict, event: dict) -> Finding | None:
    """The first complaint from what a browser client is allowed to post.

    A command is not yet a record: the server owns the envelope, the author (which
    the endpoint has already stamped), and every field admission derives. This
    reads the record contract with those fields supplied or lifted, beside the
    kind's own browser assertions — which are narrower than the record, because the
    fields a reply carries from the CLI are not a tab's to send."""
    return invalid_event(
        {
            "allOf": [
                command_record_schema(contract),
                contract["browser"],
            ]
        },
        {**event, **APPEND_STAMPED},
    )


def invalid_event(schema: dict, event: dict) -> Finding | None:
    """The `invalid-event` finding for the first complaint `schema` makes of `event`:
    the `field` it concerns and the `error` there."""
    complaint = schema_complaint(schema, event)
    if complaint is None:
        return None
    return Finding("invalid-event", values={"kind": event.get("kind"), **complaint})


def command_error(event: dict, contracts: dict) -> Finding | None:
    """Validate a command before any kind-specific reader consumes its fields."""
    kind = event.get("kind")
    if not isinstance(kind, str) or kind not in contracts:
        return Finding("unknown-kind", values={"kinds": sorted(contracts)})
    return invalid_event(
        command_record_schema(contracts[kind]), {**APPEND_STAMPED, **event}
    )


def declared_event_error(event: dict, rec: dict, registry: dict):
    """Why a known widget's verb or detail violates its `verbs` declaration, or
    names a verb the event's own writer does not write."""
    kind = event["kind"]
    tag = rec["tag"]
    entry = registry.get(tag)
    if entry is None:
        return Finding(
            "undeclared-tag",
            values={"kind": kind, "tag": tag, "widget": event["widget"]},
        )
    named = {"kind": kind, "tag": tag, "verb": event["action"]}
    spec = event_spec(entry, event)
    if spec is None:
        other = entry.get("verbs", {}).get(event["action"])
        if other is not None:
            return Finding(
                "foreign-verb",
                values={
                    **named,
                    "writer": verb_writer(other),
                    "sender": verb_writers()[kind],
                },
            )
        declared = sorted(
            verb for verb, _spec in state_specs(entry, writer=verb_writers()[kind])
        )
        return Finding("undeclared-verb", values={**named, "declared": declared})
    if complaint := schema_complaint(
        detail_schema(entry, spec, attrs=rec["attrs"], registry=registry),
        event["detail"],
    ):
        return Finding("invalid-detail", values={**named, **complaint})
    return None


def declared_action_error(
    event: dict,
    page_by_id: dict,
    thread_by_id: dict,
    registry: dict,
):
    """Why a stored action violates its sending widget's durable declaration."""
    # Page widgets come from the action's own immutable revision. Thread widgets
    # inhabit the panel's other live document. Either record answers both which
    # tag sent the action and whether it stands inside an exhibit.
    rec = page_by_id.get(event["widget"]) or thread_by_id.get(event["widget"])
    if rec is None:
        return Finding(
            "unknown-sender",
            values={
                "kind": event["kind"],
                "widget": event["widget"],
                "revision": event["revision"],
            },
        )
    tag = rec["tag"]
    if error := declared_event_error(event, rec, registry):
        return error
    # The exhibit rule at the door, not only in the shipped runtime's
    # browser controller: an exhibited widget is a mention, and the log outranks the
    # document — an action taken here would replay as a decision the user
    # made on quoted material. Any sender the key admits reaches this door.
    if quoted_in(rec, registry):
        return Finding("quoted-widget", values={"tag": tag, "widget": event["widget"]})
    return None


def position_record_error(
    event: dict,
    spec: dict,
    current: dict,
    by_id: dict,
    registry: dict,
    projected_holders: dict[str, dict],
):
    """Why a position record does not name one real relation owned by its sender."""
    record = spec["record"]
    unit_id = event["detail"]["unit"]
    target_id = event["detail"]["value"]
    named = {"unit": unit_id, "destination": target_id}
    unit = by_id.get(unit_id)
    if unit is None:
        return Finding("unknown-unit", values=named)

    target = by_id.get(target_id)
    if target is None:
        return Finding("unknown-destination", values=named)
    named["found"] = target["tag"]
    if target["tag"] != record["within"]:
        return Finding(
            "foreign-destination", values={**named, "within": record["within"]}
        )

    def holder(node: dict):
        return projected_holders.get(node["attrs"].get("id"), node.get("holder"))

    def inside(node: dict, owner: dict) -> bool:
        seen = set()
        while node is not None and id(node) not in seen:
            if node is owner:
                return True
            seen.add(id(node))
            node = holder(node)
        return False

    # Admission and projection use the same physical-slot ownership for both ends.
    owner = event["widget"]
    if (
        recorded_owner(unit_id, record, by_id, registry, holders=projected_holders)
        != owner
    ):
        return Finding("foreign-unit", values=named)
    if inside(target, unit):
        return Finding("nested-unit", values=named)
    # A part record repositions something inside its owning widget, so its
    # destination belongs there too.
    if (
        not inside(target, current)
        or container_owner(target_id, by_id, registry, holders=projected_holders)
        != owner
    ):
        return Finding("outside-destination", values=named)
    if target["tag"] not in (registry.get(unit["tag"]) or {}).get("owners", []):
        return Finding("unowned-placement", values={**named, "unit_tag": unit["tag"]})
    affected = (node for node in by_id.values() if inside(node, unit))
    if collisions := attribute_slot_errors(
        affected, by_id, registry, holders={**projected_holders, unit_id: target}
    ):
        return collisions[0]
    return None


def held_comment_error(event: dict, page_by_id: dict, registry: dict):
    """Why one comment cannot hold the widget it names.

    A comment holds the widget it is about and nothing inside it: a widget on the
    page, which its anchor names with no passage, datum or part. Which widgets offer
    a hold is their modules' to say, on the outlet each returns for itself
    (`module-annotations.md`, "Widget-local Thread placement"), so the page's
    vocabulary declares nothing here for admission to read."""
    target = event.get("holds")
    if not target:
        return None
    rec = page_by_id.get(target)
    if (
        rec is None
        or not registry.get(rec["tag"])
        or event.get("anchor") != {"section": target}
    ):
        return Finding("hold-target", values={"holds": target})
    return None


def visual_anchor_error(event: dict, page_by_id: dict, registry: dict):
    """Why a semantic visual coordinate is not authored on its section."""
    anchor = event.get("anchor") or {}
    visual = anchor.get("visual")
    if not visual:
        return None
    if anchor.get("quote") or anchor.get("datum"):
        return Finding("visual-with-passage", values={"visual": visual})
    section = anchor["section"]
    available = visual_parts(page_by_id.get(section) or {}, registry)
    if visual not in available:
        return Finding(
            "undeclared-visual",
            values={
                "visual": visual,
                "section": section,
                "prefixes": list(available.prefixes),
            },
        )
    return None


def datum_anchor_error(view, event: dict, page_by_id: dict, registry: dict):
    """Why a source-versioned datum was not displayed by its declared seat.

    Source values are replaceable and nothing keeps the ones they replaced, so a
    revision other than the source's current one is admitted as a comment on a
    value that has since changed: the reader and a replacement may have raced. A
    current revision that holds an error rather than a value is refused, since no
    widget drew it. A revision digests the value alone, so a reading under another
    contract than the seat's may still name a value the seat drew under its own, and
    that is left to `page check` (`data.bound_file_conflicts`).
    """
    anchor = event.get("anchor") or {}
    source = anchor.get("source")
    if source is None:
        return None
    section = anchor["section"]
    named = {"source": source, "section": section}
    rec = page_by_id.get(section)
    if rec is None:
        return Finding("datum-unknown-section", values=named)
    entry = registry.get(rec["tag"]) or {}
    bindings = [
        spec
        for spec in entry.get("inputs", {}).values()
        if rec["attrs"].get(spec.get("source")) == source
    ]
    if not bindings:
        return Finding("datum-unbound-source", values=named)
    reading = view.source(source, registry)
    if reading is None:
        return (
            None
            if source in view.contracts
            else Finding("datum-unsupplied-source", values=named)
        )
    if anchor.get("source_revision") != reading["revision"]:
        return None
    if "error" in reading:
        return Finding(
            "datum-undrawn-source", values={**named, "why": reading["error"]}
        )
    return None


def action_contract_error(view, event: dict, readings: AdmissionReadings):
    """Why a fresh action violates its declaration or current applicability.

    Validity is derived inside the append transaction from the action's authored
    document and the current log; a browser's possibly stale reading never
    authorizes this boundary.
    """
    registry = readings.registry
    revision = event["revision"]
    document = view.document(revision)
    # One reading of the panel's document for the whole door: the id universe the
    # declaration is looked up in and the projection a record is judged against
    # are the same message fragments, and parsing them twice would be two readings
    # that could only ever agree.
    thread = readings.thread
    thread_by_id = thread.by_id
    if error := declared_action_error(event, document.by_id, thread_by_id, registry):
        return error
    page_rec = document.by_id.get(event["widget"])
    rec = page_rec or thread_by_id[event["widget"]]
    tag = rec["tag"]
    if error := word_error(event, tag, registry):
        return error
    spec = registry[tag]["verbs"][event["action"]]
    # A created child is new: an id the markup already holds is an authored element,
    # which a user's gesture can mark or move but never write into being.
    created = created_child(event, spec)
    if created:
        authored = set(document.ids) | thread.structure.ids
        occupied = {
            child["id"]
            for projection in (readings.page(revision).projection, thread.projection)
            for children in generated_children(projection.desired, authored).values()
            for child in children
        }
    if created and created[0] in authored | occupied:
        return Finding(
            "created-exists",
            values={"tag": tag, "verb": event["action"], "created": created[0]},
        )
    return record_contract_error(view, event, spec, readings, page_rec is not None)


def record_contract_error(view, event, spec, readings, page_owned=True):
    """Check either writer's effect against its owner's current projected members.

    Reports always name page widgets. User actions may instead name widgets in
    thread markup; only page positions have a revision floor and a stale-rank check.
    """
    record_kind = (spec.get("record") or {}).get("kind")
    if record_kind not in {"position", "attribute"}:
        return None
    registry = readings.registry
    if page_owned:
        reading = readings.page(event["revision"])
        if record_kind == "position" and (stale := stale_move_error(view, event, spec)):
            return stale
        projection, byid = (
            reading.projection,
            reading.document.by_id,
        )
    else:
        thread = readings.thread
        projection, byid = thread.projection, thread.by_id

    current = byid[event["widget"]]
    record = {
        "kind": event["kind"],
        "tag": current["tag"],
        "verb": event["action"],
        "widget": event["widget"],
    }
    if record_kind == "position":
        holders = projected_action_holders(projection, byid, registry)
        if error := position_record_error(
            event, spec, current, byid, registry, holders
        ):
            return error.but(values=record)
    if record_kind == "attribute":
        members = record_members(spec["record"], projection, byid, registry).get(
            event["widget"], set()
        )
        named = event["detail"]["value"]
        if strangers := sorted(set(named) - members):
            return Finding("unknown-members", values={**record, "strangers": strangers})
    return None


def stale_move_error(view, event: dict, spec: dict):
    """Why a move made on an older revision cannot land where the user dropped it.

    A rank lies among the authored units of its container on the revision the move
    was made on. Where the newest revision authors that container the same way, the
    rank lands in the same gap there and the move stands; where it does not, the
    newest revision would take the unit's place from its own markup, so the move is
    refused and made again on the page as it now stands."""
    revision, newest = event["revision"], view.revisions[-1]
    if revision == newest:
        return None
    record = spec["record"]
    owner, container = event["widget"], event["detail"]["value"]
    # Each revision's markup is read under the vocabulary it captured
    # (`AuthoredOrders.read`).
    made_on, now = (
        AuthoredOrders.read(view.reading(made, view.registry(made))).of(owner, record)
        for made in (revision, newest)
    )
    if made_on.get(container) == now.get(container):
        return None
    return Finding(
        "stale-move",
        values={
            "kind": event["kind"],
            "verb": event["action"],
            "widget": owner,
            "revision": revision,
            "newest": newest,
            "container": container,
        },
    )


def declared_report_error(event: dict, page, registry: dict):
    """Why a report violates its declaration or names a non-page widget.

    Page markup only, never a reply's: a report has to be answerable, and no
    version carries thread markup, so none could ever absorb or overrule one made
    there."""
    rec = page.by_id.get(event["widget"])
    tag = rec["tag"] if rec else None
    if tag is None:
        return Finding(
            "unknown-sender",
            values={
                "kind": event["kind"],
                "widget": event["widget"],
                "revision": event["revision"],
            },
        )
    return declared_event_error(event, rec, registry)


def admitting_registry(view, event: dict) -> dict:
    """The vocabulary that admits one event: the one its own document captured.

    An event names the revision it was made against, and that revision's artifact
    holds the registry its page was rendered from — so a `page init`, which changes
    the layer without touching an existing revision, cannot reinterpret a command
    the user made against the document in front of them. Admission records that
    semantic definition in the event. An event naming no revision takes the newest,
    which is the document any writer of one is looking
    at, and a page with no revision yet has the candidate's vocabulary.

    Read through `PageView.registry`, which opens the one captured file rather
    than materializing the whole bundle: this runs on every append."""
    revisions = view.revisions
    revision = event.get("revision")
    named = type(revision) is int and revision in set(revisions)
    if not named:
        revision = revisions[-1] if revisions else None
    registry = view.registry(revision)
    if registry is None:
        raise EventRefused(Finding("no-registry"), event)
    return registry


def opens_on_newest(event: dict) -> bool:
    """Whether admission records the event against the page's newest revision,
    though it names none: a to-do on a widget, which that revision declares. Asked
    of a command before validation too, so it reads the shape it may not have."""
    subject = event.get("subject")
    return (
        event.get("kind") == "todo"
        and isinstance(subject, dict)
        and subject.get("kind") == "widget"
    )


def _revision_error(view, event: dict) -> Finding | None:
    """Why the document an event was made against is not one this page holds."""
    if "revision" not in event:
        return None
    live = view.revisions
    if event["revision"] not in live:
        return Finding(
            "unknown-revision",
            values={
                "kind": event["kind"],
                "revision": event["revision"],
                "revisions": list(live),
            },
        )
    return None


def _action_error(view, event: dict, readings: AdmissionReadings):
    if event["kind"] != "action":
        return None
    return action_contract_error(view, event, readings)


def _report_error(view, event: dict, readings: AdmissionReadings) -> Finding | None:
    if event["kind"] != "report":
        return None
    registry = readings.registry
    document = view.document(event["revision"])
    if error := declared_report_error(event, document, registry):
        return error
    tag = document.by_id[event["widget"]]["tag"]
    spec = registry[tag]["verbs"][event["action"]]
    return record_contract_error(view, event, spec, readings)


def _anchored_comment_error(view, event: dict, registry: dict):
    """Why a comment's declared target is not a place on the page it names.

    A passage anchor a runtime resolved against the rendered page is already
    answered: the page holds words no file reading can produce — a widget's label,
    a module's own rendering — and an earlier runtime may spell the same words in
    whitespace this reading collapses away. Reading it back off the file would
    refuse both. `leaf thread create` captures its anchor before it writes, against the
    file reading, or against the drawn page where that reading lacks the quote
    (`render_gate.drawn_anchor`).
    """
    if event["kind"] != "comment":
        return None
    anchor = event.get("anchor") or {}
    if not (event.get("holds") or anchor.get("visual") or anchor.get("source")):
        return None
    page_by_id = view.document(event["revision"]).by_id
    for error in (
        datum_anchor_error(view, event, page_by_id, registry),
        held_comment_error(event, page_by_id, registry),
        visual_anchor_error(event, page_by_id, registry),
    ):
        if error:
            return error
    return None


def _parent_error(event: dict, events: list) -> Finding | None:
    """A parent is a message some reading shows: one the log holds that no undo took
    back, or one taken back that something still stands on, which keeps its place in
    its thread (`events.unshown`). An event naming any other would stand on a message
    no reading shows."""
    if "parent" not in event:
        return None
    parent = event["parent"]
    if not any(
        logged["id"] == parent and logged["kind"] in kinds_declaring("message")
        for logged in events
    ):
        return Finding("unknown-parent", values={"parent": parent})
    if parent in unshown(events, taken_back(events)):
        return Finding("withdrawn-parent", values={"parent": parent})
    return None


def _named_question_error(event: dict, events: list) -> Finding | None:
    """A message's `obligation` names questions its own thread asks in words
    (`obligations.questions_in_words`). An event naming any other would put nothing
    back on On Me."""
    if not isinstance(event.get("obligation"), list):
        return None
    threads = thread_names(events)
    asked = questions_in_words(events, threads, threads[event["parent"]])
    for question in event["obligation"]:
        if question not in asked:
            return Finding("unasked-obligation", values={"question": question})
    return None


def _edit_error(event: dict, events: list) -> Finding | None:
    """An edit revises the words of a message its own author wrote: the user's own,
    or an agent's, whichever session posted it, so a successor can correct what a
    predecessor said. A reaction or a bare drawing has none to revise, and a message
    the user took back has none left.

    An edit that names its `base`, the revision its words were written over (the
    message's own id, or the latest edit of it still in force; a browser names an edit
    of its own still sending once the log has answered it), lands only on that
    revision: one written over words another tab has since replaced would silently
    take their place. An undone edit no longer stands, so the revision before it is the
    one a rewrite writes over. Words the message already says are no revision, and no
    turn; no words at all delete the message (events.md, "Messages")."""
    if event["kind"] != "edit":
        return None
    name = event["message"]
    target = next(
        (
            logged
            for logged in events
            if logged["kind"] in kinds_declaring("message") and logged["id"] == name
        ),
        None,
    )
    message = {"message": name}
    if target is None:
        return Finding("unknown-message", values=message)
    if target["author"] != event["author"]:
        return Finding("foreign-message", values={**message, "author": event["author"]})
    if "text" not in target:
        return Finding("wordless-message", values=message)
    withdrawn = taken_back(events)
    if name in withdrawn:
        return Finding("withdrawn-message", values=message)
    revisions = [
        logged
        for logged in events
        if logged["kind"] == "edit"
        and logged["message"] == name
        and logged["id"] not in withdrawn
    ]
    latest = revisions[-1] if revisions else target
    if "base" in event and event["base"] != latest["id"]:
        return Finding(
            "stale-edit",
            values={**message, "base": event["base"], "latest": latest["id"]},
        )
    if event["text"] == latest["text"]:
        return Finding("unchanged-edit", values=message)
    return None


def _thread_presentation_error(view, event: dict, events: list) -> Finding | None:
    if event["kind"] not in {"summary", "thread_title"}:
        return None
    threads = build_threads(events, view.within)
    thread = threads.get(event["thread"])
    named = {"thread": event["thread"]}
    if thread is None:
        return Finding("missing-thread", values=named)
    if event["kind"] == "thread_title":
        return None
    named |= {"from": event["from"], "through": event["through"]}
    messages = [message["id"] for message in spoken_turns(thread)]
    try:
        start = messages.index(event["from"])
        end = messages.index(event["through"])
    except ValueError:
        return Finding("summary-endpoints", values=named)
    if start > end:
        return Finding("summary-order", values=named)
    return None


def _withdrawal_error(
    view, event: dict, events: list, readings: AdmissionReadings
) -> Finding | None:
    if event["kind"] != "undo":
        return None
    newest = view.revisions[-1]
    absorbed = readings.page(newest).projection.absorbed
    if error := undo_error(event, events, absorbed):
        return error
    # The gesture taken back is a widget's action, whose meaning names its tag, or
    # another kind, which no widget's word speaks for.
    target = next(e for e in events if e["id"] == event["undoes"])
    if target["kind"] != "action":
        return word_error(event, target["kind"], {})
    origin = target["meaning"].get("state", {}).get("origin")
    return word_error(event, origin, readings.registry)


def word_error(event: dict, tag: str | None, registry: dict) -> Finding | None:
    """Why a gesture of a `tag` element carries the wrong word on its question: a
    widget that asks says on each act and undo of it whether its question is answered
    (`obligations.gesture_answers`), and one that doesn't says nothing. An act that
    left the word out would answer nothing however the user acted, with nothing to
    tell anyone."""
    asks = bool((registry.get(tag) or {}).get("awaits"))
    if asks and "answered" not in event:
        return Finding("answered-missing", values={"tag": tag})
    if not asks and "answered" in event:
        return Finding("answered-unasked", values={"tag": tag})
    return None


def admission_error(
    view,
    events: list,
    event: dict,
    registry: dict,
    readings: AdmissionReadings,
) -> Finding | None:
    """The first failing gate for one event, in append-door order.

    Every gate is stated once for every writer: one that names a kind runs
    wherever an event of that kind comes from, and one that names a field runs
    wherever the field is set. A gate a given kind cannot reach costs a
    comparison, which is what keeps this a list of the contract's rules rather
    than a routing table per transport.
    """
    return (
        _publication_error(view, event)
        or _revision_error(view, event)
        or _action_error(view, event, readings)
        or _report_error(view, event, readings)
        or _anchored_comment_error(view, event, registry)
        or _parent_error(event, events)
        or _named_question_error(event, events)
        or _edit_error(event, events)
        or _thread_presentation_error(view, event, events)
        or _reanchor_error(view, event, events)
        or read_contract_error(event, events)
        or _withdrawal_error(view, event, events, readings)
        or _todo_error(view, event, readings)
        or _plan_error(event, readings)
    )


def _plan_error(event: dict, readings) -> Finding | None:
    """A plan's outline nests one level at a time and names only items the page
    holds (`plans.plan_error`)."""
    if event["kind"] != "plan":
        return None
    return plan_error(event, readings.log.todos, readings.work.plan_ids)


def _todo_error(view, event: dict, readings) -> Finding | None:
    """A `todo` event stands on a thread, a declared widget, an element, or the page; a
    `todo_end` names an open to-do; and a start names explicit agent work or an owed
    update (`todos.todo_error`)."""
    if start := start_reading(event):
        event = start
    elif event["kind"] not in {"todo", "todo_end"}:
        return None
    held = event["kind"] in {"todo", "start"}

    def seat_error(widget: str) -> Finding | None:
        if not view.revisions:
            return Finding("not-a-widget", values={"widget": widget})
        return widget_seat_error(readings.page(view.revisions[-1]), widget)

    def element_error(element: str) -> Finding | None:
        if (
            not view.revisions
            or element not in readings.page(view.revisions[-1]).document.ids
        ):
            return Finding("not-an-element", values={"element": element})
        return None

    owed = agent_inputs(readings.work) if held else set()
    return todo_error(
        event,
        readings.log,
        seat_error=seat_error,
        element_error=element_error,
        owed=owed,
        items=lambda: readings.work.all_obligations["all"],
    )


def _publication_error(view, event: dict) -> Finding | None:
    if "publication" not in event:
        return None
    publication = {"publication": event["publication"]}
    if (
        not isinstance(view, CandidatePageView)
        or event["publication"] != view.publication
    ):
        return Finding("publication-owner", values=publication)
    return None


def _reanchor_error(view, event: dict, events: list) -> Finding | None:
    """A revision falls back to a thread's surviving section, or detaches it."""
    if event["kind"] != "reanchor":
        return None
    named = {"thread": event["thread"]}
    thread = build_threads(events, view.within).get(event["thread"])
    if thread is None or thread["resolved"] or not thread["anchor"]:
        return Finding("reanchor-thread", values=named)
    section = thread["anchor"].get("section")
    if event["anchor"] is not None and (
        event["anchor"] != {"section": section}
        or section not in view.document(event["revision"]).ids
    ):
        return Finding("reanchor-section", values={**named, "section": section})
    return None


def settled_attention(event: dict, contract: dict) -> bool | None:
    """The attention an event's kind and author decide alone, or None for the
    user's input, which needs attention when it changes work or requests it.

    A report or an error always wakes the agent, and a render reading does where it
    holds a failure; the agent's own events and the user's bookkeeping never do.
    """
    if event["kind"] in {"report", "error"}:
        return True
    if event["kind"] == "render":
        return any(finding["severity"] == "error" for finding in event["findings"])
    if event["author"] != "user" or contract.get("bookkeeping"):
        return False
    return None


def admitted_event(view, events: list, event: dict) -> dict:
    """The record one event becomes, or `EventRefused` on the finding that says why
    it does not.

    All of admission but the write. The page as the door may read it, the
    current log, and the event decide this between them, so a caller holding a
    page's markup as literal text can put an event to the same rules the server
    applies without a page directory, a server, or a browser under it.
    """
    registry = admitting_registry(view, event)
    # The kernel's records are this Leaf's own, whichever Leaf initialized the page: no
    # layer can change them, and a page at this protocol reads what they add
    # (`state.kernel_protocol`).
    contracts = kernel_event_kinds()
    if error := command_error(event, contracts):
        raise EventRefused(error, event)
    kind = event["kind"]
    if "id" not in event:
        event = {**event, "id": new_event_id(events)}
    readings = AdmissionReadings(view, events, registry)
    if error := admission_error(view, events, event, registry, readings):
        raise EventRefused(error, event)
    if kind in verb_writers():
        event = admit_widget_event(view.document(event["revision"]), event, readings)
    if opens_on_newest(event):
        # The revision the to-do was opened against, which the stamp that completes
        # it must come after (`publishing`).
        event = {**event, "revision": view.revisions[-1]}
    # Fold only a validated event. Attention is server-owned and boolean by
    # construction; the placeholder completes the stored shape before that fold.
    if error := event_record_error(
        contracts[kind], {**APPEND_STAMPED, **event, "attention": False}
    ):
        raise EventRefused(error, event)
    attention = settled_attention(event, contracts[kind])
    if attention is None and kind == "undo":
        # The agent was told of the gesture, so it is told of the withdrawal, whether
        # it has yet to read the gesture or has already acted on it.
        withdrawn = next(logged for logged in events if logged["id"] == event["undoes"])
        attention = True if withdrawn["attention"] else None
    if attention is None:
        candidate = {
            **APPEND_STAMPED,
            **event,
            "seq": events[-1]["seq"] + 1 if events else 1,
        }
        # The sender's vocabulary validates its command; the active vocabulary
        # decides what that command changes for the page the agent owes now.
        revisions = view.revisions
        active_registry = view.registry(revisions[-1] if revisions else None)
        # An event made against the newest revision was admitted in the active
        # vocabulary, so `readings` already reads the log before it in that one.
        before = (
            readings
            if active_registry is registry
            else AdmissionReadings(view, events, active_registry)
        )
        # `after` folds the whole log again for one event more, and the state read
        # that follows the append folds it a third time. Not yet built: an
        # incremental fold that carries `before`'s reading forward by the candidate,
        # and hands that reading on to the state read, so an append folds the log
        # once.
        after = AdmissionReadings(view, [*events, candidate], active_registry)
        attention = attention_reading(before) != attention_reading(after)
    event = {**event, "attention": attention}
    return event


def write_refusal(page_dir: Path) -> Finding | None:
    """Why this Leaf may write no event to the page, or None where it may: the page
    is at another page protocol (`registry.storage.layer_record`). A writer that
    must not fail on a page it cannot write, such as a hook, asks this first."""
    try:
        layer_record(page_dir)
    except IncompatibleLayer as refused:
        return refused.findings[0]
    return None


def voiced(event: dict) -> dict:
    """`event` in its writer's voice: an agent's event that names none takes the
    posting session's (`harness.message_identity`), so no writer stamps it by hand.
    A writer that speaks for another session, as the page server titling a thread
    for its claimant does, names that voice itself, and it stands."""
    if event["author"] != "agent" or "agent" in event or "session" in event:
        return event
    # The voice reads beside its author, where a writer stamping it put it.
    return {"kind": event["kind"], "author": "agent", **message_identity(), **event}


def append_admitted(
    page: OpenTransaction, event: dict, *, view=None
) -> tuple[dict, bool]:
    """Admit one event and append it, under the page transaction's log lease; the
    record, and whether this call appended it.

    The one door. `page` is an open `transaction.PageTransaction`, whose lease makes
    every decision here one transaction: the current log the gates read, the
    meaning derived from it, and the write. A refusal raises `EventRefused` on the
    finding that says what to do about it, which the CLI presents as an error and the browser
    endpoint answers as a final 400. An `attempt` the log already holds returns that record unappended,
    or raises `AttemptConflict` when it names another payload. The event speaks in
    its writer's voice (`voiced`).
    """
    event = voiced(event)
    # Ahead of the gates, not only ahead of the write: a retry asks for the event
    # its attempt already carried, and the page it was admitted against may since
    # have moved past admitting it. Content and time play no part: an intentional
    # later identical message has a fresh attempt and is a second event.
    if accepted := matching_attempt(page.events, event):
        return accepted, False
    if refusal := write_refusal(page.page_dir):
        raise EventRefused(refusal, event)
    record = page._append_record(
        admitted_event(
            view if view is not None else PageView(page.page_dir), page.events, event
        )
    )
    return record, True


def append_all_admitted(page: OpenTransaction, events: list[dict]) -> list[dict]:
    """Admit `events` in order, each against the log as the ones before it leave it,
    then append them; their records. A refusal of any appends none, so a command that
    writes several events writes all of them or none. An event keeps the `id` it
    names, so a later one in `events` can name it."""
    view = PageView(page.page_dir)
    trial = list(page.events)
    for event in events:
        # A retry the trial already holds appends nothing, and one whose attempt
        # names another payload is refused here, before anything is written.
        if matching_attempt(trial, voiced(event)) is not None:
            continue
        record = admitted_event(view, trial, voiced(event))
        # Stamped as the append stamps it, so the next is read after it.
        seq = trial[-1]["seq"] + 1 if trial else 1
        trial.append({**record, "ts": now_iso(), "seq": seq})
    return [append_admitted(page, event, view=view)[0] for event in events]
