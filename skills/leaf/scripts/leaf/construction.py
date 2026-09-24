"""Construction-linked document inspection, derived from the canonical state fold.

This is semantic HTML and its effective inputs, not a second widget renderer.
Exact event bodies, generated children and placement retain their event authority.
Opaque widgets expose their source and declared data rather than invented screen
text. Every source location belongs to the immutable document that was read;
mutable-source locations are offered only when that source is the same document.
"""

from copy import deepcopy
from pathlib import Path

from .data import data_fragments, data_manifest, source_file
from .projection import (
    StateProjection,
    generated_children,
    recorded_owner,
    retirement_outcomes,
)
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
            if fragments := data_fragments(
                reading["value"], spec["contract"], registry
            ):
                inputs[name]["fragments"] = {
                    **fragments,
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
    editable: bool,
    retired: set,
    conversation: str | None = None,
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
            if conversation is not None:
                node["edit"] = {
                    "kind": "conversation",
                    "conversation": conversation,
                }
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
                node["inputs"] = inputs
            prepare(node["content"])

    prepare(roots)
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
                "edit": {
                    "kind": "generated",
                    "owner": widget,
                    "id": identity,
                    "operation": "author-in-owner",
                },
            }
            if conversation is not None:
                child["edit"] = {
                    "kind": "conversation",
                    "conversation": conversation,
                }
            owner["content"].append(child)
            by_id[identity] = child
            containers[identity] = owner["content"]
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
        if conversation is None:
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
                generated = created_in.get(identity) == unit
                if (
                    not generated
                    and recorded_owner(identity, parser.by_id, spoken, registry) != unit
                ):
                    continue
                if (record["attr"] in node["attrs"]) == (identity in value):
                    continue
                if not generated:
                    node.setdefault("authored", {}).setdefault(
                        "attrs", dict(node["attrs"])
                    )
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

    if conversation is None:
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
