"""Construction-linked document inspection, derived from the canonical state fold.

This is semantic HTML and its effective inputs, not a second widget renderer.
Exact event bodies, generated children and placement retain their event authority.
Opaque widgets expose their source and declared data rather than invented screen
text. Every source location belongs to the immutable document that was read;
mutable-source locations are offered only when that source is the same document.
"""

from copy import deepcopy
from pathlib import Path

from .data import data_fragments, data_manifest
from .projection import (
    StateProjection,
    generated_children,
    recorded_owner,
    retirement_outcomes,
)
from .structure import _StructParser


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
    """Select exactly the current value or capture that constructs each input."""
    inputs = {}
    for name, spec in entry.get("x-data", {}).items():
        source = attrs.get(spec["source"])
        if source is None:
            continue
        snapshot = attrs.get(spec.get("snapshot"))
        source_store = stored["sources"].get(source, {})
        selected = (
            source_store.get("snapshots", {}).get(snapshot, {})
            if snapshot is not None
            else source_store
        )
        origin = {
            "input": name,
            "source": source,
            "contract": spec["contract"],
            "data_revision": stored["revision"],
            "revision": int(snapshot)
            if snapshot is not None
            else selected.get("revision"),
            "path": [],
        }
        if snapshot is not None:
            origin["snapshot"] = snapshot
        inputs[name] = {
            "origin": origin,
            "available": "value" in selected,
            "edit": {
                "kind": "data",
                "page": str(page_dir),
                "source": source,
                "binding_attribute": spec["source"],
                "snapshot_attribute": spec.get("snapshot"),
                "operation": "capture-and-rebind"
                if snapshot is not None
                else "data set",
                "pinned": snapshot is not None,
            },
        }
        if "value" in selected:
            inputs[name]["value"] = data_manifest(
                selected["value"], spec["contract"], registry
            )
            inputs[name]["updated"] = selected["updated"]
            if "label" in selected:
                inputs[name]["label"] = selected["label"]
            if fragments := data_fragments(
                selected["value"], spec["contract"], registry
            ):
                path = ["sources", source]
                if snapshot is not None:
                    path.extend(["snapshots", snapshot])
                inputs[name]["fragments"] = {
                    **fragments,
                    "file": str(page_dir / "data.json"),
                    "path": [*path, "value"],
                    "data_revision": stored["revision"],
                }
    return inputs


def constructed_content(
    parser: _StructParser,
    projection: StateProjection,
    spoken: dict,
    registry: dict,
    stored: dict,
    page_dir: Path,
    *,
    editable: bool,
    retired: set,
    thread: str | None = None,
) -> list:
    """Read structure, effective values, and mutation owners from one snapshot.

    Source attributes remain the construction vocabulary. `authored` appears only
    where a standing event changes a node, while `state` names that event and the
    exact declared slot. No value in this reading is an instruction to overwrite
    another owner's decision. Node locations inherit the enclosing reading's
    document source; source and vocabulary paths are not repeated per element.
    """
    roots = deepcopy(parser.content)
    by_id = {}
    containers = {}

    def prepare(items):
        for node in items:
            if isinstance(node, str):
                continue
            identity = node["attrs"].get("id")
            node["source"] = {"line": node.pop("line"), "column": node.pop("column")}
            if identity:
                by_id[identity] = node
                containers[identity] = items
            if thread is not None:
                node["edit"] = {"kind": "conversation", "thread": thread}
            else:
                node["edit"] = {
                    "kind": "source",
                    "matches_active": editable,
                }
                if identity:
                    node["edit"]["id"] = identity
            entry = registry.get(node["tag"], {})
            if entry.get("x-upgrade"):
                node["vocabulary"] = node["tag"]
            inputs = input_readings(node["attrs"], entry, stored, page_dir, registry)
            if inputs:
                if thread is not None:
                    for reading in inputs.values():
                        if reading["edit"]["pinned"]:
                            reading["edit"]["operation"] = "capture-and-reply"
                            reading["edit"]["thread"] = thread
                node["inputs"] = inputs
            prepare(node["content"])

    prepare(roots)
    for unit, children in generated_children(projection.desired, set(by_id)).items():
        owner = by_id.get(unit)
        if owner is None:
            continue
        for generated in children:
            identity = generated["id"]
            child = {
                "tag": generated["tag"],
                "attrs": {"id": identity},
                "content": [generated["text"]],
                "source": event_origin(generated["event"]),
                "edit": {
                    "kind": "generated",
                    "owner": unit,
                    "id": identity,
                    "operation": "author-in-owner",
                },
            }
            if thread is not None:
                child["edit"] = {"kind": "conversation", "thread": thread}
            owner["content"].append(child)
            by_id[identity] = child
            containers[identity] = owner["content"]
    ordered = sorted(projection.desired.items(), key=lambda item: item[1][0]["seq"])
    for (widget, unit, facet), (event, spec) in ordered:
        owner = by_id.get(unit)
        if owner is None:
            continue
        authority = event_origin(event)
        reading = {
            "facet": facet,
            "action": event["action"],
            "detail": event["detail"],
            "origin": authority,
        }
        if record := spec.get("record"):
            reading["construction"] = record
        owner.setdefault("state", []).append(reading)
        if thread is None:
            owner["edit"]["override_requires"] = (
                "restate" if event["kind"] == "action" else "absorb-or-overrule"
            )
        if not record:
            continue
        value = event["detail"].get(record["value"])
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
        elif kind == "attribute":
            for identity, node in by_id.items():
                generated = node["source"].get("event") == event["id"]
                if (
                    not generated
                    and recorded_owner(identity, parser.by_id, spoken, registry) != unit
                ):
                    continue
                if (record["attr"] in node["attrs"]) == (identity in value):
                    continue
                node.setdefault("authored", {}).setdefault("attrs", dict(node["attrs"]))
                if identity in value:
                    node["attrs"][record["attr"]] = None
                else:
                    node["attrs"].pop(record["attr"], None)
                node["authority"] = authority
        elif kind == "position":
            target = by_id[value]
            previous = containers[unit]
            owner.setdefault("authored", {})["placement"] = {
                "parent": next(
                    (i for i, n in by_id.items() if n["content"] is previous), None
                )
            }
            previous.remove(owner)
            children = target["content"]
            index = event["detail"][record["order"]]
            positions = [
                i
                for i, child in enumerate(children)
                if isinstance(child, dict) and child["attrs"].get("id")
            ]
            at = positions[index] if index < len(positions) else len(children)
            children.insert(at, owner)
            containers[unit] = children

    outcomes = retirement_outcomes(projection.actions, registry)

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
                and parent["tag"] in entry.get("x-parent", [])
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
