"""Shared event admission; the contract is events.md, "Admission".

`admitted_event` validates and derives a record from `page_view.PageView`, the
standing log, and a command. `append_admitted` performs that reading and write
under `service.PageTransaction`'s lease.

This module selects each kind's gates. Their implementations stay with their
domains: request lifecycles in `requests`, undo in `events`, and widget meaning
in `event_meaning`.
"""

from leaf.anchor_capture import capture_anchor
from leaf.asks import (
    asking,
    completion_met,
    page_awaiting_values,
    projected_action_holders,
    quoted_in,
    thread_ask_readings,
)
from leaf.document_reading import read_document
from leaf.event_log import EventRefused
from leaf.event_meaning import admit_widget_event, direct_dependencies
from leaf.events import build_threads, spoken_turns, taken_back, undo_error
from leaf.files import version_revisions
from leaf.page_view import PageView
from leaf.passages import enclosing_ids
from leaf.projection import (
    frozen_thread_reading,
    generated_children,
    page_reading,
    record_members,
    retirement_outcomes,
    rewritten_bodies,
)
from leaf.read_state import read_contract_error
from leaf.registry.contract import (
    created_child,
    schema_error,
    state_specs,
    visual_parts,
)
from leaf.registry.reactions import reaction_tokens
from leaf.requests import (
    receipt_contract_error,
    request_contract_error,
    request_lifecycles_for,
    request_phases,
)
from leaf.schema import EVENT_REFERENCES_SCHEMA, MESSAGE_KINDS, WIDGET_KINDS
from leaf.served_state.conversation import browser_conversation
from leaf.structure import resolve_source_target_reference, review_mode
from leaf.validation.instances import target_reference_contract_error

# The envelope the append lease itself assigns. Admission validates the complete
# record, so it supplies placeholders for the three fields that cannot exist
# until the write: an id proved unique against this log, the moment it landed,
# and its line number. A caller that supplies one of them is held to the
# contract's own reading of it.
APPEND_STAMPED = {"id": "pending", "ts": "pending", "seq": 1}


def event_record_error(contract: dict, event: dict):
    """The first complaint from one event kind's stored-record contract."""
    return schema_error(contract["record"], event)


def browser_command_error(contract: dict, event: dict):
    """The first complaint from what a browser client is allowed to post.

    A command is not yet a record: the server owns the envelope, the author, and
    every field admission derives. This reads the record contract with those
    fields supplied or lifted, beside the kind's own browser assertions — which
    are narrower than the record, because the fields a reply carries from the
    CLI are not a tab's to send."""
    schema = contract["record"]
    schema = {
        **schema,
        "properties": {
            key: value
            for key, value in schema["properties"].items()
            if key != "meaning"
        },
        "required": [key for key in schema["required"] if key != "meaning"],
    }
    return schema_error(
        {"allOf": [schema, contract["browser"]]},
        {
            **event,
            **APPEND_STAMPED,
            "author": "page" if event.get("kind") == "error" else "user",
        },
    )


def declared_event_error(
    event: dict, tag: str, registry: dict, kind: str, channel: str
):
    """Why a known widget's verb or detail violates one declared channel."""
    entry = registry.get(tag)
    if entry is None:
        return (
            f"registry no longer declares <{tag}> for {kind} widget {event['widget']!r}"
        )
    declared = entry.get(channel, {})
    spec = declared.get(event["action"])
    if spec is None:
        return f"<{tag}> does not declare {kind} verb {event['action']!r}" + (
            f"; it declares {sorted(declared)}" if kind == "report" and declared else ""
        )
    if message := schema_error(spec["detail"], event["detail"]):
        return f"<{tag}> {kind} {event['action']!r} detail is invalid: {message}"
    declared_references = spec.get("references", {})
    supplied_references = event.get("references", {})
    if "references" in event and (
        message := schema_error(EVENT_REFERENCES_SCHEMA, supplied_references)
    ):
        return f"<{tag}> {kind} {event['action']!r} references are invalid: {message}"
    if missing := sorted(set(declared_references) - set(supplied_references)):
        return (
            f"<{tag}> {kind} {event['action']!r} is missing declared reference "
            f"roles {missing}"
        )
    if unexpected := sorted(set(supplied_references) - set(declared_references)):
        return (
            f"<{tag}> {kind} {event['action']!r} carries undeclared reference "
            f"roles {unexpected}"
        )
    if "resolves" in event["detail"] and not event["detail"]["resolves"]:
        return f"<{tag}> {kind} {event['action']!r} resolves must name a non-empty thread id"
    if message := schema_error(
        {"type": "array", "items": {"type": "string", "minLength": 1}},
        direct_dependencies(event, spec),
    ):
        return (
            f"<{tag}> {kind} {event['action']!r} identity fields are invalid: {message}"
        )
    return None


def event_reference_error(
    event: dict, spec: dict, document, registry: dict, *, fragment: bool = False
) -> str | None:
    """Why one declared role does not name its exact authored source target."""
    for role, contract in spec.get("references", {}).items():
        resolution = resolve_source_target_reference(
            document, event["references"][role], fragment=fragment
        )
        if resolution["status"] != "resolved":
            return (
                f"reference role {role!r} is {resolution['status']} in its "
                "authored document"
            )
        if event["references"][role]["kind"] == "structure" and resolution[
            "target"
        ].get("attrs", {}).get("id"):
            return (
                f"reference role {role!r} resolves to an authored id and must use "
                "that exact id record"
            )
        if error := target_reference_contract_error(
            contract, resolution["target"], registry
        ):
            return f"reference role {role!r} {error}"
    return None


def thread_reference_document(structure, widget: str):
    """The one frozen markup fragment that authored a thread widget, or None."""
    matches = [
        fragment
        for fragment in structure.fragments.values()
        if widget in fragment.by_id
    ]
    return matches[0] if len(matches) == 1 else None


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
        return (
            f"unknown action widget {event['widget']!r} in revision "
            f"r{event['revision']} "
            "or agent-authored thread markup"
        )
    tag = rec["tag"]
    if error := declared_event_error(event, tag, registry, "action", "x-state"):
        return error
    # The exhibit rule at the door, not only in the shipped runtime's
    # browser controller: an exhibited widget is a mention, and the log outranks the
    # document — an action taken here would replay as a decision the user
    # made on quoted material. Any sender the key admits reaches this door.
    if quoted_in(rec, registry):
        return (
            f"<{tag}> {event['widget']!r} stands inside an exhibit (x-exhibit); "
            "quoted material takes no input"
        )
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
    record = spec.get("record") or {}
    if record.get("kind") != "position":
        return None

    unit_id = (
        event["widget"] if spec["unit"] == "widget" else event["detail"][spec["unit"]]
    )
    unit = current if spec["unit"] == "widget" else by_id.get(unit_id)
    if unit is None:
        return f"position record names unknown {spec['unit']} {unit_id!r}"

    target_id = event["detail"][record["value"]]
    target = by_id.get(target_id)
    if target is None:
        return f"position record names unknown destination {target_id!r}"
    if target["tag"] != record["within"]:
        return (
            f"position record destination {target_id!r} is <{target['tag']}>, "
            f"not <{record['within']}>"
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

    def recording_owner(node: dict):
        """Nearest enclosing widget whose declaration records durable state.

        The walk starts at the holder, so a part that records facets of its own is
        still its container's to place: facet names are local to the widget contract
        that declares them."""
        node = node["holder"]
        while node is not None:
            entry = registry.get(node["tag"], {})
            if any(spec.get("record") for _, _, spec in state_specs(entry)):
                return node
            node = node["holder"]
        return None

    def positions_itself(node: dict) -> bool:
        """Whether the node's own contract records where the node stands."""
        return any(
            spec.get("unit") == "widget"
            and (spec.get("record") or {}).get("kind") == "position"
            for _, _, spec in state_specs(registry.get(node["tag"], {}))
        )

    # A node has one place and one widget records it: the node itself when its own
    # contract records its position, otherwise the nearest recording widget above it.
    # The browser folds a self-position and a container's part position into two
    # different maps, so admitting both would place one node twice.
    if unit is not current and positions_itself(unit):
        return (
            f"position record unit {unit_id!r} records its own position, so action "
            f"widget {event['widget']!r} cannot place it"
        )
    if unit is not current and recording_owner(unit) is not current:
        return (
            f"position record unit {unit_id!r} is not owned by action widget "
            f"{event['widget']!r}"
        )
    if inside(target, unit):
        return (
            f"position record cannot put {unit_id!r} inside itself or its descendant "
            f"{target_id!r}"
        )
    # A part record repositions something inside its owning widget, so its
    # destination belongs there too. A self-position record instead moves the
    # widget among containers admitted by its x-owners (often siblings of its
    # current parent), and the registry relation below is its complete boundary.
    if unit is not current and not inside(target, current):
        return (
            f"position record destination {target_id!r} is outside action widget "
            f"{event['widget']!r}"
        )
    if target["tag"] not in (registry.get(unit["tag"]) or {}).get("x-owners", []):
        return (
            f"position record cannot put <{unit['tag']}> {unit_id!r} within "
            f"<{target['tag']}> {target_id!r}"
        )
    return None


def held_comment_error(event: dict, page_by_id: dict, registry: dict):
    """Why one comment cannot hold the exact command goal it names."""
    target = event.get("holds")
    if not target:
        return None
    rec = page_by_id.get(target)
    conversation = (
        (registry.get(rec["tag"]) or {}).get("x-conversation") if rec else None
    )
    if (
        rec is None
        or not conversation
        or not conversation.get("hold")
        or not asking(rec["attrs"], conversation.get("when"))
        or event.get("anchor") != {"section": target}
    ):
        return (
            "comment holds must name its exact-section anchor on a matching "
            "x-conversation hold target"
        )
    return None


def version_response_comment_error(event: dict, page_by_id: dict, registry: dict):
    """Why a comment cannot require the authored response it names."""
    response = event.get("response")
    if not response:
        return None
    anchor = event.get("anchor")
    target = anchor.get("section") if isinstance(anchor, dict) else None
    rec = page_by_id.get(target)
    conversation = (
        (registry.get(rec["tag"]) or {}).get("x-conversation") if rec else None
    )
    if (
        rec is None
        or not conversation
        or conversation.get("response") != response
        or not asking(rec["attrs"], conversation.get("when"))
        or anchor != {"section": target}
    ):
        return (
            "comment response must match its exact-section x-conversation "
            "response target"
        )
    return None


def visual_anchor_error(event: dict, page_by_id: dict, registry: dict):
    """Why a semantic visual coordinate is not authored on its section."""
    anchor = event.get("anchor") or {}
    visual = anchor.get("visual")
    if not visual:
        return None
    if anchor.get("quote") or anchor.get("datum"):
        return (
            f"visual anchor {visual!r} names a box rather than a passage, "
            "so it cannot also carry a quote or a datum"
        )
    section = anchor["section"]
    available = visual_parts(page_by_id.get(section) or {}, registry)
    if visual not in available:
        return (
            f"visual anchor {visual!r} is not declared on section {section!r}; "
            f"known: {list(available)}"
        )
    return None


def datum_anchor_error(view, event: dict, page_by_id: dict, registry: dict):
    """Why a source-versioned datum was not displayed by its declared seat.

    Source values are replaceable and nothing keeps the ones they replaced, so a
    revision other than the source's current one is admitted as a comment on a
    value that has since changed: the reader and a replacement may have raced.
    """
    anchor = event.get("anchor") or {}
    source = anchor.get("source")
    if source is None:
        return None
    section = anchor["section"]
    rec = page_by_id.get(section)
    if rec is None:
        return f"datum anchor names unknown section {section!r}"
    entry = registry.get(rec["tag"]) or {}
    bindings = [
        spec
        for spec in entry.get("x-data", {}).values()
        if rec["attrs"].get(spec["source"]) == source
    ]
    if not bindings:
        return f"datum anchor source {source!r} is not bound by section {section!r}"
    if source not in view.contracts:
        return f"datum anchor source {source!r} has never been supplied to this page"
    return None


def action_contract_error(view, event: dict, events: list, registry: dict):
    """Why a fresh action violates its declaration or current applicability.

    Eligibility is derived inside the append transaction from the action's
    authored document and the standing log. A browser evaluates the same
    declaration for honest controls, but its possibly stale reading never
    authorizes this boundary.
    """
    revision = event["revision"]
    document = view.document(revision)
    # One reading of the panel's document for the whole door: the id universe the
    # declaration is looked up in and the projection the requirement is judged
    # against are the same frozen fragments, and parsing them twice was two
    # readings that could only ever agree.
    thread = frozen_thread_reading(events, registry)
    thread_projection = thread.projection
    thread_by_id = thread.by_id
    if error := declared_action_error(event, document.by_id, thread_by_id, registry):
        return error
    page_rec = document.by_id.get(event["widget"])
    rec = page_rec or thread_by_id[event["widget"]]
    tag = rec["tag"]
    spec = registry[tag]["x-state"][event["action"]]
    # A created child is new: an id the markup already holds is an authored element,
    # which a user's gesture can mark or move but never write into being.
    created = created_child(event, spec)
    if created and (created[0] in document.by_id or created[0] in thread_by_id):
        return (
            f"<{tag}> action {event['action']!r} creates {created[0]!r}, which "
            "already names an authored element"
        )
    if spec.get("references"):
        reference_document = (
            document
            if page_rec
            else thread_reference_document(thread.structure, event["widget"])
        )
        if reference_document is None:
            return (
                f"<{tag}> {event['widget']!r} has no unique authored document for "
                "its references"
            )
        if error := event_reference_error(
            event, spec, reference_document, registry, fragment=not page_rec
        ):
            return f"<{tag}> action {event['action']!r} is invalid: {error}"
    requirement = spec.get("requires")
    completion = spec.get("completion")
    record_kind = (spec.get("record") or {}).get("kind")
    if (
        not requirement
        and not completion
        and record_kind not in {"position", "attribute"}
    ):
        return None

    if page_rec:
        reading = page_reading(document, events, registry, revision)
        projection, parser, spk = reading.projection, reading.document, reading.spoken
        byid = parser.by_id
        current = parser.by_id[event["widget"]]
    else:
        # Thread markup is frozen in the log: it has no version retraction floor
        # and its actions read the whole conversation window.
        projection, byid, spk = thread_projection, thread_by_id, thread.spoken
        current = byid[event["widget"]]

    holders = projected_action_holders(projection, byid, registry)
    if error := position_record_error(event, spec, current, byid, registry, holders):
        return f"<{tag}> action {event['action']!r} is invalid: {error}"
    if record_kind == "attribute":
        members = record_members(event["widget"], projection, byid, spk, registry)
        named = event["detail"][spec["record"]["value"]]
        if strangers := sorted(set(named) - members):
            return (
                f"<{tag}> action {event['action']!r} is invalid: {strangers} name no "
                f"member of {event['widget']!r}"
            )
    if completion:
        record = spec.get("record") or {}
        after_holders = dict(holders)
        if record.get("kind") == "position":
            unit_id = (
                event["widget"]
                if spec["unit"] == "widget"
                else event["detail"][spec["unit"]]
            )
            after_holders[unit_id] = byid[event["detail"][record["value"]]]
        if not completion_met(
            current,
            spec,
            projection,
            byid,
            registry,
            positioned_holders=after_holders,
        ):
            return (
                f"<{tag}> {event['widget']!r} action {event['action']!r} is "
                "unavailable: its recorded result does not satisfy its completion "
                "condition"
            )
    if not requirement:
        return None
    if page_rec:
        # This door asks whether the request is answered, not whether it is the
        # user's to deal with: a conversation standing in the widget's seat
        # takes it off their list without answering it, and refusing their pick
        # over their own remark would refuse them the answer they were asked for.
        awaiting_values = page_awaiting_values(
            document,
            projection,
            spk,
            registry,
            request_phases=request_phases(
                request_lifecycles_for(
                    events,
                    parser.lf_elements,
                    registry,
                    {"kind": "page", "revision": revision},
                    view.data(registry),
                )
            ),
        )
    else:
        threads = build_threads(events, enclosing_ids(document))
        settled = {root for root, value in threads.items() if value["resolved"]}
        awaiting_values = thread_ask_readings(
            events,
            registry,
            settled,
            request_phases=request_phases(
                request_lifecycles_for(
                    events,
                    thread.elements,
                    registry,
                    {"kind": "thread"},
                    view.data(registry),
                )
            ),
            reading=thread,
        )["awaiting"]
    target = (
        current
        if requirement["target"] == "self"
        else holders.get(current["attrs"]["id"], current["holder"])
    )
    target_id = target["attrs"]["id"]
    awaiting = awaiting_values.get(target_id, False)
    if awaiting != requirement["awaiting"]:
        return (
            f"<{tag}> {event['widget']!r} action {event['action']!r} is "
            f"unavailable: {requirement['target']} {target_id!r} is "
            f"{'still ' if awaiting else 'no longer '}awaiting the user"
        )
    return None


def report_contract_error(
    event: dict, page, registry: dict, *, resolve_references: bool = True
):
    """Why a structurally complete report violates its widget's declaration —
    an action's `action_contract_error` for the kind only an agent sends. Page
    markup only, never a reply's: a report has to be answerable, and thread
    markup is frozen in the log, so no version could ever absorb or overrule one
    made there."""
    rec = page.by_id.get(event["widget"])
    tag = rec["tag"] if rec else None
    if tag is None:
        return (
            f"unknown report widget {event['widget']!r} in revision "
            f"r{event['revision']} — "
            "reports name page widgets only; thread markup is frozen, so no "
            "version could ever answer a report made there"
        )
    if error := declared_event_error(event, tag, registry, "report", "x-report"):
        return error
    if resolve_references:
        spec = registry[tag]["x-report"][event["action"]]
        if error := event_reference_error(event, spec, page, registry):
            return f"<{tag}> report {event['action']!r} is invalid: {error}"
    return None


def admitting_registry(view, event: dict) -> dict:
    """The vocabulary that admits one event: the one its own document captured.

    An event names the revision it was made against, and that revision's artifact
    holds the registry its page was rendered from — so a re-vendor, which replaces
    the layer without touching a standing revision, cannot reinterpret a command
    the user made against the document in front of them. `stored_meaning_error`
    reads the recorded side from that same capture. An event naming no revision
    takes the newest, which is the document any writer of one is looking at, and a
    page with no revision yet has only the layer it carries.

    Read through `PageView.registry`, which opens the one captured file rather
    than materializing the whole bundle: this runs on every append."""
    revisions = view.revisions
    revision = event.get("revision")
    if type(revision) is not int or revision not in set(revisions):
        revision = revisions[-1] if revisions else None
    registry = view.registry(revision)
    if registry is None:
        raise EventRefused("the page has no registry.json")
    return registry


def _revision_error(view, event: dict) -> str | None:
    """Why the document an event was made against is not one this page holds."""
    if "revision" not in event:
        return None
    live = view.revisions
    if event["revision"] not in live:
        return f"{event['kind']} revision must be one of {live}"
    return None


def _approval_error(view, event: dict, events: list, registry: dict):
    """Why a sign-off cannot record approval of the version it names."""
    if event["kind"] != "done":
        return None
    if version_revisions(events).get(event["version"]) != event["revision"]:
        return f"v{event['version']} does not stamp revision r{event['revision']}"
    document = view.document(event["revision"])
    if review_mode(document) != "sign-off":
        return (
            f"v{event['version']} does not declare "
            '<meta name="lf-review" content="sign-off">, so it has no '
            "approval to record"
        )
    page = page_reading(document, events, registry, event["revision"])
    threads = build_threads(events, page.within)
    document_state = read_document(page, threads, view.data(registry))
    conversation, _reading = browser_conversation(events, registry, threads)
    unanswered = [
        *document_state.asks["unanswered"],
        *conversation["asks"]["unanswered"],
    ]
    if unanswered:
        identities = ", ".join(ask["id"] for ask in unanswered)
        return f"v{event['version']} still has unanswered Asks: {identities}"
    return None


def _action_error(view, event: dict, events: list, registry: dict):
    if event["kind"] != "action":
        return None
    return action_contract_error(view, event, events, registry)


def _request_error(view, event: dict, events: list, registry: dict):
    if event["kind"] != "request":
        return None
    return request_contract_error(view, event, events, registry)


def _report_error(view, event: dict, registry: dict) -> str | None:
    if event["kind"] != "report":
        return None
    return report_contract_error(event, view.document(event["revision"]), registry)


def _receipt_error(view, event: dict, events: list) -> str | None:
    if event["kind"] != "receipt":
        return None
    return receipt_contract_error(view, event, events)


def _reaction_error(event: dict, registry: dict) -> str | None:
    if not event.get("token"):
        return None
    tokens = reaction_tokens(registry)
    if event["token"] not in tokens:
        return (
            f"unknown reaction token {event['token']!r}; this layer "
            f"declares {sorted(tokens)}"
        )
    return None


def _anchored_comment_error(
    view, event: dict, events: list, registry: dict, capture_anchors: bool
):
    """Why a comment's declared target is not a place on the page it names.

    A passage anchor a runtime resolved against the rendered page is already
    answered: the page holds words no file reading can produce — a widget's label,
    a module's own rendering — and an earlier runtime may spell the same words in
    whitespace this reading collapses away. Reading it back off the file would
    refuse both. A transport that resolves nothing (the MCP surface, which renders
    the authored source with no runtime behind it) asks for the capture here
    instead; `leaf comment` has already made it against the same reading.
    """
    if event["kind"] != "comment":
        return None
    anchor = event.get("anchor") or {}
    recapture = bool(capture_anchors and anchor) and not (
        anchor.get("datum") or anchor.get("visual") or anchor.get("part")
    )
    if not (
        recapture
        or event.get("holds")
        or event.get("response")
        or anchor.get("visual")
        or anchor.get("source")
    ):
        return None
    document = view.document(event["revision"])
    page_by_id = document.by_id
    for error in (
        datum_anchor_error(view, event, page_by_id, registry),
        held_comment_error(event, page_by_id, registry),
        version_response_comment_error(event, page_by_id, registry),
        visual_anchor_error(event, page_by_id, registry),
    ):
        if error:
            return error
    if not recapture:
        return None
    page = page_reading(document, events, registry, event["revision"])
    try:
        canonical = capture_anchor(
            document,
            registry,
            anchor.get("quote", ""),
            anchor.get("section"),
            retirement_outcomes(page.projection.actions, registry),
            rewritten_bodies(page.projection.actions),
            prefix=anchor.get("prefix") if "prefix" in anchor else None,
            suffix=anchor.get("suffix") if "suffix" in anchor else None,
            additions=generated_children(page.projection.desired, page.document.ids),
        )
    except ValueError as error:
        return f"comment anchor is not in the current page reading: {error}"
    if "quote" in anchor and anchor["quote"] != canonical.get("quote"):
        return "comment anchor quote does not match the current page reading"
    # Store the file-side reading, not the client's abbreviated proof. Compact
    # clients may name only quote and section; capture adds the context needed to
    # keep that passage attached when the same words occur elsewhere later.
    event["anchor"] = canonical
    return None


def _parent_error(event: dict, events: list) -> str | None:
    if "parent" not in event:
        return None
    messages = {logged["id"] for logged in events if logged["kind"] in MESSAGE_KINDS}
    if event["parent"] not in messages:
        return f"unknown parent {event['parent']!r}"
    return None


def _conversation_presentation_error(view, event: dict, events: list) -> str | None:
    if event["kind"] not in {"summary", "conversation_title"}:
        return None
    threads = build_threads(events, view.within, withdrawn=taken_back(events))
    thread = threads.get(event["conversation"])
    if thread is None:
        return f"unknown conversation {event['conversation']!r}"
    if event["kind"] == "conversation_title":
        return None
    messages = [message["id"] for message in spoken_turns(thread)]
    try:
        start = messages.index(event["from"])
        end = messages.index(event["through"])
    except ValueError:
        return "summary endpoints must name spoken turns in the named conversation"
    if start >= end:
        return "summary must cover at least two messages in conversation order"
    return None


def _withdrawal_error(view, event: dict, events: list) -> str | None:
    if event["kind"] != "undo":
        return None
    return undo_error(event, events, view.within)


def admission_error(
    view, events: list, event: dict, registry: dict, *, capture_anchors: bool = False
) -> str | None:
    """The first failing gate for one event, in append-door order.

    Every gate is stated once for every writer: one that names a kind runs
    wherever an event of that kind comes from, and one that names a field runs
    wherever the field is set. A gate a given kind cannot reach costs a
    comparison, which is what keeps this a list of the contract's rules rather
    than a routing table per transport.
    """
    return (
        _revision_error(view, event)
        or _approval_error(view, event, events, registry)
        or _action_error(view, event, events, registry)
        or _request_error(view, event, events, registry)
        or _report_error(view, event, registry)
        or _receipt_error(view, event, events)
        or _reaction_error(event, registry)
        or _anchored_comment_error(view, event, events, registry, capture_anchors)
        or _parent_error(event, events)
        or _conversation_presentation_error(view, event, events)
        or read_contract_error(event, events)
        or _withdrawal_error(view, event, events)
    )


def admitted_event(
    view, events: list, event: dict, *, capture_anchors: bool = False
) -> dict:
    """The record one event becomes, or `EventRefused` saying why it does not.

    All of admission but the write. The page as the door may read it, the
    standing log, and the event decide this between them, so a caller holding a
    page's markup as literal text can put an event to the same rules the server
    applies without a page directory, a server, or a browser under it.
    """
    registry = admitting_registry(view, event)
    contracts = registry["$events"]["kinds"]
    kind = event.get("kind")
    if kind not in contracts:
        raise EventRefused(f"kind must be one of {sorted(contracts)}")
    if error := admission_error(
        view, events, event, registry, capture_anchors=capture_anchors
    ):
        raise EventRefused(error)
    if kind in WIDGET_KINDS:
        event = admit_widget_event(
            view.document(event["revision"]), event, events, registry
        )
    if error := event_record_error(contracts[kind], {**APPEND_STAMPED, **event}):
        raise EventRefused(f"{kind} event is invalid: {error}")
    return event


def append_admitted(page, event: dict, *, capture_anchors: bool = False) -> dict:
    """Admit one event and append it, under the page transaction's log lease.

    The one door. `page` is an open `service.PageTransaction`, whose lease makes
    every decision here one transaction: the standing log the gates read, the
    meaning derived from it, and the write. A refusal raises `EventRefused` with
    what to do about it — `contract_writer` turns that into a CLI exit and the
    browser endpoint into a final 400.
    """
    # Ahead of the gates, not only ahead of the write: a retry asks for the event
    # its attempt already carried, and the page it was admitted against may since
    # have moved past admitting it.
    if accepted := page.matching_attempt(event):
        return accepted
    return page._append_record(
        admitted_event(
            PageView(page.page_dir),
            page.events,
            event,
            capture_anchors=capture_anchors,
        )
    )
