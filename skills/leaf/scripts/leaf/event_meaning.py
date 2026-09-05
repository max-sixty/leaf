"""Compile admitted widget commands into durable semantic facts.

The log keeps direct identities, never a snapshot of their ancestor tree. A
projection tests those identities against the document it reads, so moving a
referenced element still changes containment without changing an old event.
"""

from leaf.registry.contract import created_children
from leaf.structure import parse_revision
from leaf.thread_context import thread_structure


def direct_dependencies(event: dict, spec: dict) -> list[str]:
    """The owner, fold unit, and declared direct references before canonical ordering."""
    detail = event["detail"]
    owner = event["widget"]
    unit = owner if spec["unit"] == "widget" else detail[spec["unit"]]
    fields = list(spec.get("references", []))
    record = spec.get("record") or {}
    if record.get("kind") in {"attribute", "position"}:
        fields.append(record["value"])
    dependencies = [owner, unit]
    for field in fields:
        value = detail.get(field)
        if value is not None:
            dependencies.extend(value if isinstance(value, list) else [value])
    dependencies.extend(created_children(event, spec))
    return dependencies


def state_meaning(event: dict, entry: dict, document: dict) -> dict:
    """Resolve one validated verb using its sending document's declaration."""
    channel = "x-state" if event["kind"] == "action" else "x-report"
    spec = entry[channel][event["action"]]
    dependencies = direct_dependencies(event, spec)
    owner, unit = dependencies[:2]
    meaning = {
        "document": document,
        "coordinate": [owner, unit, spec["facet"]],
        "depends": sorted(set(dependencies)),
    }
    if event["kind"] == "action" and event["action"] in entry.get("x-awaits", {}).get(
        "answers", []
    ):
        meaning["answer"] = event["detail"].get("resolves")
    return meaning


def admit_widget_event(page_dir, event: dict, events: list, registry: dict) -> dict:
    """Stamp server-owned meaning after command validation, under the append lock."""
    page = parse_revision(page_dir, event["revision"])
    record = page.by_id.get(event["widget"])
    document = {"kind": "page", "revision": event["revision"]}
    if record is None:
        record = thread_structure(events).by_id[event["widget"]]
        document = {"kind": "thread"}
    entry = registry[record["tag"]]
    admitted = dict(event)
    if event["kind"] == "request":
        admitted["meaning"] = {"document": document}
    else:
        admitted["meaning"] = state_meaning(event, entry, document)
        spec = entry["x-state" if event["kind"] == "action" else "x-report"][
            event["action"]
        ]
        if spec.get("creates"):
            admitted["generated"] = sorted(created_children(event, spec))
    return admitted


def stored_meaning_error(
    event: dict, page, thread, registry: dict, prior_registry: dict
) -> str | None:
    """Reject a layer that would reinterpret the meaning of an admitted event."""
    record = page.by_id.get(event["widget"])
    document = {"kind": "page", "revision": event["revision"]}
    if record is None:
        record = thread.by_id[event["widget"]]
        document = {"kind": "thread"}
    entry = registry[record["tag"]]
    expected = (
        {"document": document}
        if event["kind"] == "request"
        else state_meaning(event, entry, document)
    )
    if event["meaning"] != expected:
        return f"{event['kind']} {event['id']} changes admitted meaning from {event['meaning']!r} to {expected!r}"
    if event["kind"] in {"action", "report"}:
        channel = "x-state" if event["kind"] == "action" else "x-report"
        before = prior_registry[record["tag"]][channel][event["action"]].get("record")
        after = entry[channel][event["action"]].get("record")
        if before != after:
            return f"{event['kind']} {event['id']} changes its admitted record form"
    return None
