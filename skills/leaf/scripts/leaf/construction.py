"""The construction reading of a thread's frozen markup, derived from the canonical
state fold.

`leaf page state <page> <thread>` prints it for each message that carries markup:
semantic HTML and its effective inputs, not a second widget renderer. Exact event
bodies, generated children and placement retain their event authority. Opaque widgets
expose their source and declared data rather than invented screen text. A page's own
document has no such reading: its HTML is the active revision file, read beside `page
state`'s current `state`.
"""

from copy import deepcopy
from pathlib import Path

from .data import data_manifest, deferred_records, source_file
from .projection import (
    StateProjection,
    folded_positions,
    generated_children,
    markup_value,
    record_members,
    retirement_outcomes,
)
from .registry.contract import state_specs
from .structure import SourceDocument


def event_origin(event: dict) -> dict:
    return {
        "kind": event["kind"],
        "event": event["id"],
        "seq": event["seq"],
        "author": event["author"],
        "revision": event["revision"],
    }


def input_readings(
    attrs: dict, entry: dict, stored: dict, page_dir: Path, registry: dict
) -> dict:
    """Read the current value of the source that constructs each input."""
    inputs = {}
    for name, spec in entry.get("x-data", {}).items():
        source = attrs.get(spec["source"])
        if source is None:
            continue
        reading = stored["sources"].get(source, {})
        inputs[name] = {
            "origin": {
                "input": name,
                "source": source,
                "contract": spec["contract"],
                "revision": reading.get("revision"),
                "path": [],
            },
            "available": "value" in reading,
            "edit": {
                "kind": "data",
                "page": str(page_dir),
                "source": source,
                "file": str(source_file(page_dir, source)),
                "binding_attribute": spec["source"],
            },
        }
        if "error" in reading:
            inputs[name]["error"] = reading["error"]
        if "value" in reading:
            inputs[name]["value"] = data_manifest(
                reading["value"], spec["contract"], registry
            )
            inputs[name]["updated"] = reading["updated"]
            if records := deferred_records(
                reading["value"], spec["contract"], registry
            ):
                inputs[name]["deferred"] = {
                    **records,
                    "file": str(source_file(page_dir, source)),
                    "revision": reading["revision"],
                }
    return inputs


def constructed_content(
    parser: SourceDocument,
    projection: StateProjection,
    spoken: dict,
    registry: dict,
    stored: dict,
    page_dir: Path,
    *,
    retired: set,
    thread: str,
) -> list:
    """Read structure, effective values, and mutation owners from one snapshot.

    Source attributes remain the construction vocabulary. `authored` appears only
    where an event in force changes a node, while `state` names that event and the
    exact declared slot. No value in this reading is an instruction to overwrite
    another owner's decision. Node locations inherit the enclosing reading's
    document source; source and vocabulary paths are not repeated per element.
    """
    roots = deepcopy(parser.content)
    by_id = {}
    # The id of each identified node's nearest identified ancestor.
    parents = {}

    def prepare(items, parent=None):
        for node in items:
            if isinstance(node, str):
                continue
            identity = node["attrs"].get("id")
            node["source"] = {"line": node.pop("line"), "column": node.pop("column")}
            if identity:
                by_id[identity] = node
                parents[identity] = parent
            node["edit"] = {"kind": "thread", "thread": thread}
            entry = registry.get(node["tag"], {})
            if entry.get("x-upgrade"):
                node["vocabulary"] = node["tag"]
            inputs = input_readings(node["attrs"], entry, stored, page_dir, registry)
            if inputs:
                node["inputs"] = inputs
            prepare(node["content"], identity or parent)

    prepare(roots)
    members = parser.by_id
    # Created child id → its owner, so a record the owner states reaches the children
    # other events created as well as the authored ones.
    created_in = {}
    for widget, children in generated_children(projection.desired, set(by_id)).items():
        owner = by_id.get(widget)
        if owner is None:
            continue
        for generated in children:
            identity = generated["id"]
            created_in[identity] = widget
            child = {
                "tag": generated["tag"],
                "attrs": {"id": identity},
                "content": [generated["text"]],
                "source": event_origin(generated["event"]),
                "edit": {"kind": "thread", "thread": thread},
            }
            owner["content"].append(child)
            by_id[identity] = child
    # Owner and verb → the position record a move in force places units by.
    placed = {}
    ordered = sorted(projection.desired.items(), key=lambda item: item[1][0]["seq"])
    for (widget, unit, _verb), (event, spec) in ordered:
        owner = by_id.get(unit)
        if owner is None:
            continue
        authority = event_origin(event)
        reading = {
            "action": event["action"],
            "detail": event["detail"],
            "origin": authority,
        }
        if record := spec.get("record"):
            reading["construction"] = record
        owner.setdefault("state", []).append(reading)
        if not record:
            continue
        value = event["detail"].get("value")
        kind = record["kind"]
        if kind == "body":
            owner.setdefault("authored", {})["content"] = owner["content"]
            owner["content"] = [value]
        elif kind == "value":
            owner.setdefault("authored", {}).setdefault("attrs", dict(owner["attrs"]))
            if value is None:
                owner["attrs"].pop(record["attr"], None)
            else:
                owner["attrs"][record["attr"]] = value
        elif kind == "position" and event["id"] not in projection.absorbed:
            owner.setdefault("authored", {})["placement"] = {"parent": parents[unit]}
            placed[(widget, event["action"])] = record

    # Every attribute-set owner paints its complete state over its current members.
    # A move can give an unchanged destination baseline a new member to paint.
    for widget, rec in members.items():
        for verb, spec in state_specs(registry.get(rec["tag"], {})):
            record = spec.get("record") or {}
            if record.get("kind") != "attribute":
                continue
            held = projection.desired.get((widget, widget, verb))
            value = (
                held[0]["detail"]["value"]
                if held
                else markup_value(widget, spec, members, spoken, registry)
            )
            for identity in record_members(
                widget, record, projection, members, registry
            ):
                node = by_id[identity]
                if (record["attr"] in node["attrs"]) == (identity in value):
                    continue
                if identity not in created_in:
                    node.setdefault("authored", {}).setdefault(
                        "attrs", dict(node["attrs"])
                    )
                if identity in value:
                    node["attrs"][record["attr"]] = None
                else:
                    node["attrs"].pop(record["attr"], None)
                if held:
                    node["authority"] = event_origin(held[0])

    # Each container lists its units in the fold's order, in the slots its authored
    # units held and after them.
    for (widget, verb), record in placed.items():
        order = folded_positions(
            widget, verb, record, members, spoken, registry, projection
        )
        units = {unit for listed in order.values() for unit in listed}
        for container, listed in order.items():
            content = by_id[container]["content"]
            slots = [
                i
                for i, node in enumerate(content)
                if isinstance(node, dict) and node["attrs"].get("id") in units
            ]
            nodes = [by_id[unit] for unit in listed]
            for i, node in zip(slots, nodes, strict=False):
                content[i] = node
            content.extend(nodes[len(slots) :])
            for i in reversed(slots[len(nodes) :]):
                content.pop(i)

    outcomes = retirement_outcomes(projection.actions)

    def visible(items, parent=None):
        result = []
        for node in items:
            if isinstance(node, str):
                result.append(node)
                continue
            if node["attrs"].get("id") in retired:
                continue
            entry = registry.get(node["tag"], {})
            if (
                parent is not None
                and entry.get("x-retired-when")
                and parent["tag"] in entry.get("x-owners", [])
                and outcomes.get(parent["attrs"].get("id")) == entry["x-retired-when"]
            ):
                continue
            node["content"] = visible(node["content"], node)
            result.append(node)
        return result

    if thread is None:
        main = next((node for node in by_id.values() if node["tag"] == "main"), None)

        # Main need not carry an id; find it in the already parsed tree.
        def main_content(items):
            for node in items:
                if isinstance(node, dict):
                    if node["tag"] == "main":
                        return node["content"]
                    found = main_content(node["content"])
                    if found is not None:
                        return found
            return None

        roots = main["content"] if main else (main_content(roots) or [])
    return visible(roots)
