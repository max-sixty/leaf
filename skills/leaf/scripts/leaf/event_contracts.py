"""Browser and CLI event contracts against page and thread state."""

from pathlib import Path

from leaf.asks import (
    asking,
    completion_met,
    page_awaiting_values,
    projected_action_holders,
    quoted_in,
    thread_ask_projection,
)
from leaf.data import read_data
from leaf.event_meaning import direct_dependencies
from leaf.events import build_threads
from leaf.files import revision_path
from leaf.passages import enclosing_ids
from leaf.projection import frozen_thread_reading, page_projection
from leaf.registry.contract import (
    created_children,
    schema_error,
    state_specs,
    visual_parts,
)
from leaf.requests import request_lifecycles_for, request_phases
from leaf.structure import parse_revision


def event_record_error(contract: dict, event: dict, browser: bool = False):
    """The first complaint from one event kind's stored-record contract."""
    schema = contract["record"]
    instance = event
    if browser:
        # Supply the fields the server and reader add so the full record schema
        # can validate the unstamped request beside its browser assertions.
        schema = {
            **schema,
            "properties": {
                key: value
                for key, value in schema["properties"].items()
                if key not in {"meaning", "generated"}
            },
            "required": [
                key for key in schema["required"] if key not in {"meaning", "generated"}
            ],
        }
        schema = {"allOf": [schema, contract["browser"]]}
        instance = {
            **event,
            "id": "browser",
            "ts": "browser",
            "author": "page" if event.get("kind") == "error" else "user",
            "seq": 1,
        }
    return schema_error(schema, instance)


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


def declared_action_error(
    event: dict,
    page_by_id: dict,
    thread_by_id: dict,
    registry: dict,
    prior_registry: dict | None = None,
    *,
    stored: bool = True,
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
    spec = registry[tag]["x-state"][event["action"]]
    creates = spec.get("creates")
    if creates and stored:
        if "generated" not in event:
            return (
                f"<{tag}> action {event['action']!r} declares generated children "
                "but the event has no generated snapshot"
            )
        expected = sorted(created_children(event, spec))
        if event["generated"] != expected:
            return (
                f"<{tag}> action {event['action']!r} generated snapshot must equal "
                f"the sorted keys of detail field {creates['field']!r}: "
                f"expected {expected}, found {event['generated']}"
            )
    elif not creates and "generated" in event:
        return (
            f"<{tag}> action {event['action']!r} has a generated snapshot but its "
            "declaration creates no children"
        )
    if prior_registry is not None:
        prior = (
            prior_registry.get(tag, {})
            .get("x-state", {})
            .get(event["action"], {})
            .get("creates")
        )
        if prior != creates:
            return (
                f"<{tag}> action {event['action']!r} changes its recorded creates "
                f"declaration from {prior!r} to {creates!r}"
            )
    # The exhibit rule at the door, not only in the shipped runtime's
    # sendAction: an exhibited widget is a mention, and the log outranks the
    # document — an action taken here would replay as a decision the reader
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
        """Nearest enclosing widget whose declaration records durable state."""
        while node is not None:
            entry = registry.get(node["tag"], {})
            if any(spec.get("record") for _, _, spec in state_specs(entry)):
                return node
            node = node["holder"]
        return None

    if recording_owner(unit) is not current:
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
    # widget among containers admitted by its x-parent (often siblings of its
    # current parent), and the registry relation below is its complete boundary.
    if unit is not current and not inside(target, current):
        return (
            f"position record destination {target_id!r} is outside action widget "
            f"{event['widget']!r}"
        )
    if target["tag"] not in (registry.get(unit["tag"]) or {}).get("x-parent", []):
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


def datum_anchor_error(page_dir: Path, event: dict, page_by_id: dict, registry: dict):
    """Why a source-versioned datum was not displayed by its declared seat.

    Current source values are replaceable, so an older valid revision may race a
    replacement and is admitted as an already-outdated comment. An authored
    snapshot selection is immutable and therefore has one exact revision.
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

    stored = read_data(page_dir)
    revision = anchor["data_revision"]
    if revision > stored["revision"]:
        return (
            f"datum anchor data revision {revision} is newer than page data "
            f"revision {stored['revision']}"
        )
    source_store = stored["sources"].get(source)
    if source_store is None:
        return f"datum anchor source {source!r} has never been supplied to this page"

    for binding in bindings:
        snapshot_attr = binding.get("snapshot")
        selected = rec["attrs"].get(snapshot_attr) if snapshot_attr else None
        if selected is None:
            if revision in source_store["revisions"]:
                return None
            continue
        if revision == int(selected) and selected in source_store.get("snapshots", {}):
            return None
    return (
        f"datum anchor data revision {revision} was never displayed from source "
        f"{source!r} by section {section!r}"
    )


def action_contract_error(page_dir: Path, event: dict, events: list, registry: dict):
    """Why a fresh action violates its declaration or current applicability.

    Eligibility is derived inside the append transaction from the action's
    authored document and the standing log. A browser evaluates the same
    declaration for honest controls, but its possibly stale reading never
    authorizes this boundary.
    """
    revision = event["revision"]
    page = parse_revision(page_dir, revision)
    # One reading of the panel's document for the whole door: the id universe the
    # declaration is looked up in and the projection the requirement is judged
    # against are the same frozen fragments, and parsing them twice was two
    # readings that could only ever agree.
    thread = frozen_thread_reading(events, registry)
    thread_projection = thread.projection
    thread_by_id = thread.by_id
    if error := declared_action_error(
        event, page.by_id, thread_by_id, registry, stored=False
    ):
        return error
    page_rec = page.by_id.get(event["widget"])
    rec = page_rec or thread_by_id[event["widget"]]
    tag = rec["tag"]
    spec = registry[tag]["x-state"][event["action"]]
    requirement = spec.get("requires")
    completion = spec.get("completion")
    position = (spec.get("record") or {}).get("kind") == "position"
    if not requirement and not completion and not position:
        return None

    if page_rec:
        html = revision_path(page_dir, revision).read_text(encoding="utf-8")
        projection, parser, spk = page_projection(html, events, registry, revision)
        byid = parser.by_id
        current = parser.by_id[event["widget"]]
        # This door asks whether the request is answered, not whether it is the
        # reader's to deal with: a conversation standing in the widget's seat
        # takes it off their list without answering it, and refusing their pick
        # over their own remark would refuse them the answer they were asked for.
        awaiting_values = page_awaiting_values(
            html,
            parser,
            projection,
            spk,
            registry,
            request_phases=request_phases(
                request_lifecycles_for(
                    events,
                    parser.lf_elements,
                    registry,
                    {"kind": "page", "revision": revision},
                )
            ),
        )
    else:
        # Thread markup is frozen in the log: it has no version retraction floor
        # and its actions read the whole conversation window.
        projection, byid = thread_projection, thread_by_id
        current = byid[event["widget"]]
        page_html = revision_path(page_dir, revision).read_text(encoding="utf-8")
        threads = build_threads(events, enclosing_ids(page_html))
        settled = {root for root, value in threads.items() if value["resolved"]}
        _, awaiting_values = thread_ask_projection(
            events,
            registry,
            settled,
            request_phases=request_phases(
                request_lifecycles_for(
                    events,
                    thread.elements,
                    registry,
                    {"kind": "thread"},
                )
            ),
            reading=thread,
        )

    holders = projected_action_holders(projection, byid, registry)
    if error := position_record_error(event, spec, current, byid, registry, holders):
        return f"<{tag}> action {event['action']!r} is invalid: {error}"
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
            f"{'still ' if awaiting else 'no longer '}awaiting the reader"
        )
    return None


def report_contract_error(event: dict, page_by_id: dict, registry: dict):
    """Why a structurally complete report violates its widget's declaration —
    the CLI door's mirror of the POST door's action_contract_error. Page markup
    only, never a reply's: a report has to be answerable, and thread markup is
    frozen in the log, so no version could ever absorb or overrule one made
    there."""
    rec = page_by_id.get(event["widget"])
    tag = rec["tag"] if rec else None
    if tag is None:
        return (
            f"unknown report widget {event['widget']!r} in revision "
            f"r{event['revision']} — "
            "reports name page widgets only; thread markup is frozen, so no "
            "version could ever answer a report made there"
        )
    return declared_event_error(event, tag, registry, "report", "x-report")
