"""Readings and derived declarations from a supplied registry vocabulary."""

import json
import re
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from leaf.base.files import read_json
from leaf.base.findings import Finding, Rejected, admitted_parts, element_at
from leaf.base.schema import (
    DATA_CONTRACT_NAME,
    DATA_SOURCE_NAME,
    ELEMENT_ID,
    INPUT_BINDINGS,
    RECORD_BINDING,
    WIDGET_NAME,
)
from leaf.source.registry.kernel import kernel_marks, verb_writers


def same_state_definition(recorded, current) -> bool:
    """Whether two recorded state definitions, or values in them, are one JSON value,
    as the browser compares them (`state/registry-contract.js`): `true` is not `1`, which
    Python's `==` takes it for, while `1.0` is `1`, as in JavaScript."""
    if isinstance(recorded, dict) and isinstance(current, dict):
        return recorded.keys() == current.keys() and all(
            same_state_definition(value, current[key])
            for key, value in recorded.items()
        )
    if isinstance(recorded, list) and isinstance(current, list):
        return len(recorded) == len(current) and all(
            map(same_state_definition, recorded, current)
        )
    return (
        isinstance(recorded, bool) == isinstance(current, bool) and recorded == current
    )


def matches_when(attrs: dict, when: dict | None) -> bool:
    """Every attribute `when` names holds one of the matching values, a flag's
    two values being its presence and its absence."""
    return all(
        any(
            (attr in attrs) == value
            if isinstance(value, bool)
            else attrs.get(attr) == value
            for value in values
        )
        for attr, values in (when or {}).items()
    )


def fact_condition(rule) -> dict | None:
    """The `when` of a fact declared to hold only for some occurrences,
    `{when: {attribute: [values]}}`, or None for a fact declared outright. The
    declaration schema says which facts may take that form (`schema.FACTS`)."""
    return (
        rule["when"] if isinstance(rule, Mapping) and rule.keys() == {"when"} else None
    )


def holds_for(attrs: dict, rule):
    """A declared fact as it holds for one occurrence, given its authored attributes.
    A fact declared with `{when}` is `True` while those attributes match `when` and
    `False` otherwise; any other declaration is returned as declared. Delivery's paint
    and every reader asking of one occurrence read a fact through this, as `exhibits`
    does; a reader asking whether the tag declares the fact at all reads the
    declaration whatever its condition, as `structure.shown_in` does."""
    when = fact_condition(rule)
    return rule if when is None else matches_when(attrs, when)


def exhibits(attrs: dict, entry: dict) -> bool:
    """Whether this occurrence quotes its descendants."""
    return bool(holds_for(attrs, entry.get("exhibit")))


def authored_inert(
    key: str, declaration: Mapping, attrs: dict, *, content: bool
) -> str | None:
    """Why an occurrence's authored override of the mark `key` means nothing on its
    element, or None where it holds. A width means nothing on an element that takes
    none of its own (`flow`, where its `flow` holds); otherwise the override
    holds where its `authored_on` says, and the condition it fails is the reason
    (`content`, a block in the page's flow, which `main`, `body` and `html` aren't;
    `declared`, a tag declaring the mark). Delivery paints only an override that holds
    (`revision_delivery.mark_declared`), and `page check` names the rest."""
    if key == "space" and holds_for(attrs, declaration.get("flow")):
        return "flow"
    condition = kernel_marks()[key]["authored_on"]
    holds = content if condition == "content" else bool(declaration.get(key))
    return None if holds else condition


def is_element_name(name: str) -> bool:
    """Whether a vocabulary key names one Leaf custom element rather than a selector.

    Non-dollar keys are authored vocabulary: exact ``WIDGET_NAME`` keys declare
    elements; every other key is a CSS selector idiom, including native tags and
    selectors such as ``lf-options.selected``. Validation admits selectors once
    at composition; consumers share this classification without parsing CSS.
    """
    return re.fullmatch(WIDGET_NAME, name) is not None


def element_declarations(registry: dict) -> dict:
    """The element declarations from one registry's authored vocabulary."""
    return {name: entry for name, entry in registry.items() if is_element_name(name)}


# The path of each element's module, by tag, in a composed vocabulary. Composition
# derives it from the files it composes (`registry.layer.merged_registry`,
# `registry.page.compose_page_registry`), so no declaration says whether a module
# upgrades its element: the module's presence at `widgets/<tag>.js` does.
MODULES = "$modules"


def complete_declarations(registry: dict) -> dict:
    """Write into a merged vocabulary's element declarations the default each may
    leave unsaid, so every reader reads a complete entry: an element's content is its
    author's markup (`content`) unless it declares another, and its attribute schema
    (`attributes`) and each verb's `detail` schema admit only what they name unless
    they say otherwise (`_closed_by_default`); validation refuses a `detail` that
    does. An element that declares no `attributes` takes none of its own, so its
    schema starts as the one that names nothing. An input (`inputs`) declares the
    attributes it binds by (`schema.INPUT_BINDINGS`): each is a string attribute of
    the element unless `attributes` gives it a schema, and the one its `reference`
    names is one naming an element (`refers`), whether or not the entry lists it there.

    A verb (`verbs`) keeps one state for the whole widget (`unit: "widget"`) unless it
    names the detail field that tells its members apart, and a verb recording
    positions always tells them apart by `unit`, so only a verb with a `detail` schema
    that keeps a state for each member says its `unit`. A record that names no `kind`
    is one value in the attribute it names (`kind: "value"`). An obligation (`awaits`)
    is answered while the verb its `value` names has a state (`answered:
    {<verb>: {}}`) unless `answered` says when. So the fold, admission and each
    event's stored `meaning.state` read the same `unit`, `record` and `answered`
    whether the declaration spelt them or left them to their defaults.

    It runs before validation, so it completes only an entry of the shape it reads
    and leaves any other for validation to refuse."""
    for entry in element_declarations(registry).values():
        if not isinstance(entry, dict):
            continue
        if isinstance(attributes := entry.setdefault("attributes", {}), dict):
            entry["attributes"] = _closed_by_default(attributes)
        entry.setdefault("content", "markup")
        verbs = entry.get("verbs")
        for verb, spec in list(verbs.items()) if isinstance(verbs, dict) else ():
            if not isinstance(spec, dict):
                continue
            if isinstance(detail := spec.get("detail"), dict):
                spec["detail"] = _closed_by_default(detail)
            if isinstance(record := spec.get("record"), dict):
                spec["record"] = record = {"kind": "value", **record}
            # Each default stands first, where a declaration that writes it puts it.
            verbs[verb] = {"unit": record_unit(record), **spec}
        awaits = entry.get("awaits")
        if isinstance(awaits, dict) and isinstance(value := awaits.get("value"), str):
            awaits.setdefault("answered", {value: {}})
        inputs = entry.get("inputs")
        for spec in inputs.values() if isinstance(inputs, dict) else ():
            for key in INPUT_BINDINGS if isinstance(spec, dict) else ():
                if not isinstance(attribute := spec.get(key), str):
                    continue
                if isinstance(entry["attributes"], dict) and isinstance(
                    properties := entry["attributes"].setdefault("properties", {}), dict
                ):
                    properties.setdefault(attribute, {"type": "string"})
                if key == "reference" and isinstance(
                    entry.setdefault("refers", {}), dict
                ):
                    entry["refers"].setdefault(attribute, {})
    return registry


def record_unit(record) -> str:
    """The `unit` a verb's `record` decides: a position record's verb keeps a state for
    each member its `detail.unit` names, and any other, like a verb with no record that
    names no unit of its own, keeps one for the whole widget."""
    position = isinstance(record, dict) and record.get("kind") == "position"
    return "unit" if position else "widget"


def _closed_by_default(schema: dict) -> dict:
    """`schema` with `"type": "object"` and `"additionalProperties": false` written in,
    each where it doesn't write that keyword. `type` stands first and
    `additionalProperties` last, where a declaration that writes both puts them, so the
    vocabulary reads the same either way."""
    closed = {"type": "object", **schema}
    closed.setdefault("additionalProperties", False)
    return closed


def body_is_data(entry: Mapping) -> bool:
    """Whether the element's content is one `<pre>` holding text (`content`): in the
    notation its module reads (`data`), or in Markdown, which Leaf reads (`markdown`)."""
    return entry.get("content") in ("data", "markdown")


def upgraded(registry: dict, tag: str) -> bool:
    """Whether a module upgrades `tag` in the browser (`MODULES`)."""
    return tag in registry.get(MODULES, ())


def module_paths(registry: dict, available, *directories: str) -> dict[str, str]:
    """`MODULES` for a vocabulary: each declared element whose `<tag>.js` stands in
    one of `directories`, the earliest directory winning, among the `available`
    paths."""
    return {
        tag: path
        for tag in registry
        if is_element_name(tag)
        and (
            path := next(
                (
                    candidate
                    for directory in directories
                    if (candidate := f"{directory}/{tag}.js") in available
                ),
                None,
            )
        )
    }


def event_clauses(entry: dict, registry: dict | None) -> list[dict]:
    """What the layer asks of the agent for one delivered event, read off the
    registry's `$events`: the event kind's `handling` clauses, then the `answering`
    clauses of the answer it owes, each kept when its `when` schema matches.

    `entry` is the event record, plus the `answer` a delivery captured when the
    event owes one, addressed for the route delivering it (`workflows` and
    `delivery` own those derivations), the `thread` digest of the thread
    it belongs to (`thread_context` owns that one), and its batch's `held` to-dos
    (`delivery.batch_data`). `delivery.DELIVERY` declares
    the shape of each, as its batches carry them. A `when` can therefore read any
    of them as well as the record, so a clause states the case a delivery is in
    rather than naming a condition the delivery already settles, such as a
    thread's missing title. An event owing nothing is told nothing about
    answering: a pick before Done, or a message a newer one in its thread answers
    through. A project layer restates a kind's clauses merge-patch style, so the
    event carries the rule of the layer the page selects. A missing or invalid
    registry leaves the event unexplained; it never substitutes instructions from a
    different layer. What each case of each kind receives from the shipped layer,
    clause by clause, is snapshotted in
    `tests/model/interact_contract/_regtest_outputs/`, by
    `test_each_case_of_an_event_is_told_what_the_snapshot_shows`."""
    from leaf.source.registry.schema import json_validator

    declared = (registry or {}).get("$events", {})
    clauses = list(declared.get("handling", {}).get(entry["kind"]) or [])
    if answer := entry.get("answer"):
        clauses += declared.get("answering", {}).get(answer["kind"]) or []
    return [
        clause
        for clause in clauses
        if "when" not in clause or json_validator(clause["when"]).is_valid(entry)
    ]


def created_child(event: dict, spec: dict) -> tuple[str, str] | None:
    """The id and words of the child one validated action creates, or None where
    its verb declares no `creates`. The verb's fold unit names the child."""
    creates = spec.get("creates")
    if not creates:
        return None
    return event["detail"][spec["unit"]], event["detail"][creates["words"]]


@dataclass(frozen=True)
class VisualParts:
    """The part ids one authored element admits as `anchor.visual`: ids beginning one
    of its widget's declared prefixes. Admission does not say a part is on screen; the
    browser resolves that, and `thread create --part` checks an agent's id against what
    the page drew (`anchor_capture.drawn_part`). An admitted id nothing renders
    detaches, unless the widget's module draws parts on request or finds them by id, as
    a chart finds its points; then it stands on the whole element.
    """

    prefixes: tuple[str, ...] = ()

    def __contains__(self, part: str) -> bool:
        return part.split() == [part] and any(
            part.startswith(prefix) and part != prefix for prefix in self.prefixes
        )

    def __bool__(self) -> bool:
        return bool(self.prefixes)

    def __str__(self) -> str:
        return admitted_parts(self.prefixes)


def visual_parts(record: dict, registry: dict) -> VisualParts:
    """The visual-part ids one authored Leaf element admits."""
    visual = registry.get(record.get("tag"), {}).get("visual")
    return VisualParts(tuple(visual["prefixes"]) if isinstance(visual, dict) else ())


class RegistryError(Rejected):
    """A registry that is not a vocabulary, raised rather than exited because two doors
    read one. The CLI prints the message and stops; the page server owes the browser an
    answer, and `sys.exit` inside its request handler would kill the connection mid-POST
    while every other rejection beside it returns a 400 — so a page whose stamp has
    fallen behind the running layer would meet the user's click with a dead socket and
    no words. The CLI renders it with Click's standard Error prefix, while the server
    catches the same rejection and answers the request.

    It carries the first finding in each unit the check holds independent of the
    others (`gathering`), which `page check` and `package check` report as they are,
    so an author repairs them all from one check."""


def registry_finding(code: str, registry=None, tag: str = "", /, **values) -> Finding:
    """One registry problem: `code` names it, `registry` the file or composition it
    was read in, `tag` the element declaration it concerns, and `values` what the
    check read there."""
    if registry is not None:
        values["registry"] = str(registry)
    return Finding(code, element_at(tag) if tag else "", values)


def registry_error(code: str, registry=None, tag: str = "", /, **values):
    """The refusal of one registry problem (`registry_finding`)."""
    return RegistryError([registry_finding(code, registry, tag, **values)])


@contextmanager
def gathering():
    """Run independent registry checks and refuse once with what each refused.

    Each check runs inside the `unit()` this yields and stops at its own first
    finding; the next unit still runs, and leaving the block refuses with every
    unit's findings. A unit is independent when nothing it reads depends on another
    passing, such as each element declaration once the layer's facts hold. A check
    whose readings depend on an earlier one runs after that one's block, which
    refuses before it starts."""
    found: list[Finding] = []

    @contextmanager
    def unit():
        try:
            yield
        except RegistryError as error:
            found.extend(error.findings)

    yield unit
    if found:
        raise RegistryError(found)


def read_registry_declarations(path: Path):
    """Read the top-level declarations one registry layer contributes."""
    registry = read_registry_object(path)
    if registry is None:
        return None
    non_objects = [
        name for name, entry in registry.items() if not isinstance(entry, dict)
    ]
    if non_objects:
        raise registry_error("declaration-not-object", path, names=non_objects)
    return registry


def read_registry_object(path: Path) -> dict | None:
    """Read a registry file as the JSON object it must be, before any check of what
    its entries hold, or None where there is no file."""
    if (path.exists() or path.is_symlink()) and not path.is_file():
        raise registry_error("registry-not-file", path)
    try:
        registry = read_json(path)
    except json.JSONDecodeError as error:
        raise registry_error(
            "registry-json", path, error=error.msg, line=error.lineno
        ) from error
    except UnicodeDecodeError:
        raise registry_error("registry-not-utf8", path) from None
    if registry is None:
        if not path.is_file():
            return None
        raise registry_error("registry-not-object", path)
    if not isinstance(registry, dict):
        raise registry_error("registry-not-object", path)
    return registry


def declares_string(field_schema) -> bool:
    """Whether a detail field allows a string and nothing else, however it says so."""
    declared = field_schema.get("type") if isinstance(field_schema, dict) else None
    allowed = {declared} if isinstance(declared, str) else set(declared or [])
    return allowed == {"string"}


# A position record's rank: a base-36 fraction written as its digits after the point,
# never ending in 0, so string order is numeric order. The runtime's
# `lib/rank.js` owns the reasoning and computes the keys between neighbours;
# this rule is the one both runtimes must read the same way, and
# `tests/rank_cases.json` holds both runtimes to the same cases.
RANK = "[0-9a-z]*[1-9a-z]"
_IDENTITY = {"type": "string", "minLength": 1}


def detail_schema(
    entry: dict, spec: dict, *, attrs: dict | None = None, registry: dict | None = None
) -> dict:
    """The event payload contract: an effect's fixed fields or custom command data.

    Recorded values use `value`; positions add `unit` and `rank`, and a verb
    declaring `text: true` adds a required non-empty `text`. Attribute values
    inherit the destination's exact schema. Every identity the event depends on
    (`event_meaning.direct_dependencies`) is a nonempty string: a custom verb's
    fold unit, and an attribute set's or position's ids. A verb that creates a
    child names it by its fold unit, which therefore holds an element id. Derived
    schemas are readings, never inserted into the registry beside the effect that
    owns them.

    A custom verb may bind one field to a data contract named by an authored
    attribute. Without an instance this reads the package's base schema. With an
    instance it also applies the selected contract, keeping each schema's local
    references rooted in that schema. An unknown contract refuses every value;
    markup validation reports the unknown name before the page is published.
    """
    record = spec.get("record")
    if record is None:
        detail, unit = spec["detail"], spec["unit"]
        properties = dict(detail.get("properties", {}))
        if unit != "widget":
            # Keep the base of `#/properties/…` references in the declared detail.
            declared = properties[unit]
            properties[unit] = {
                **declared,
                "minLength": max(declared.get("minLength", 0), 1),
            }
            if spec.get("creates"):
                properties[unit]["pattern"] = f"^{ELEMENT_ID}$"
        binding = spec.get("contract")
        if binding and attrs and (name := attrs.get(binding["attribute"])):
            assert registry is not None
            contract = registry["$data"]["contracts"].get(name)
            selected = (
                {"$id": f"leaf:contract/{name}", **contract["schema"]}
                if contract is not None
                else False
            )
            field = binding["field"]
            properties[field] = {"allOf": [properties[field], selected]}
        return {**detail, "properties": properties}
    kind = record["kind"]
    if kind == "value":
        value = entry["attributes"]["properties"][record["attr"]]
    elif kind == "attribute":
        value = {"type": "array", "items": _IDENTITY, "uniqueItems": True}
    elif kind == "body":
        value = {"type": "string"}
    else:
        value = _IDENTITY
    properties = {"value": value}
    if kind == "position":
        properties.update(
            unit=_IDENTITY,
            rank={"type": "string", "pattern": f"^(?:{RANK})$"},
        )
    if spec.get("text"):
        properties["text"] = {"type": "string", "minLength": 1}
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def decides(spec: dict) -> bool:
    """Whether a verb declares the role that selects retirable members
    (`retired-when`) or declines the proposal (its `withdraws`). Its required
    `outcome` carries that choice; the same field name on any other verb is
    ordinary domain data.
    The browser reads the role from `$decisions`
    (`registry.contract.stamp_decisions`)."""
    return spec.get("decides", False)


def deciding_verbs(entry: dict) -> list[str]:
    """Every verb (`verbs`) of one declaration that decides; validation holds it to one."""
    return [verb for verb, spec in entry.get("verbs", {}).items() if decides(spec)]


def deciding_verb(entry: dict) -> str | None:
    """The one deciding verb (`verbs`), or None."""
    return next(iter(deciding_verbs(entry)), None)


def deciding_outcomes(entry: dict) -> list[str]:
    """The outcomes the deciding verb may stand under; empty without one, or where
    the verb declares no `outcome` words. Validation reads it before holding the
    verb to its shape (`state.validate_deciding_verb`), and a declaration reads it
    of another whose own check may have failed."""
    verb = deciding_verb(entry)
    if verb is None:
        return []
    detail = entry["verbs"][verb].get("detail") or {}
    schema = detail.get("properties", {}).get("outcome")
    return list(schema.get("enum", [])) if isinstance(schema, dict) else []


def withdrawing_outcome(entry: dict) -> str | None:
    """The outcome of one declaration's deciding verb that declines the proposal
    (`withdraws`), or None."""
    verb = deciding_verb(entry)
    return entry["verbs"][verb].get("withdraws") if verb is not None else None


def verb_writer(spec: dict) -> str:
    """The side that writes one verb (`verbs`): `agent` where it says so, else `user`.
    The browser reads it from `$states` (`stamp_states`)."""
    return spec.get("writer", "user")


def state_specs(entry: dict, *, writer: str | None = None):
    """The verb (`verbs`) declarations on one element declaration, as (verb, spec),
    narrowed to the verbs one side writes when `writer` names it."""
    for verb, spec in entry.get("verbs", {}).items():
        if writer is None or verb_writer(spec) == writer:
            yield verb, spec


def recorded(spec: dict) -> dict | None:
    """Where a verb's state reads in markup: its `record` without the members that
    bind it to the element in the browser (`schema.RECORD_BINDING`), or None for a
    verb with no record. An admitted event stores this, so a declaration that names
    another property or event keeps every decision recorded before it, and a state
    in `leaf page state` shows it as its construction. The browser's `sameRecord`
    (`runtime/state/registry.js`) compares two records the same way."""
    record = spec.get("record")
    return record and {
        key: value for key, value in record.items() if key not in RECORD_BINDING
    }


def _semantic_schema(schema):
    """Strip JSON Schema annotations without changing literal values or names."""
    if not isinstance(schema, dict):
        return schema
    annotations = {
        "title",
        "description",
        "$comment",
        "default",
        "examples",
        "deprecated",
        "readOnly",
        "writeOnly",
    }
    maps = {
        "properties",
        "patternProperties",
        "$defs",
        "definitions",
        "dependentSchemas",
    }
    single = {
        "additionalProperties",
        "unevaluatedProperties",
        "propertyNames",
        "items",
        "additionalItems",
        "unevaluatedItems",
        "contains",
        "not",
        "if",
        "then",
        "else",
        "contentSchema",
    }
    sequences = {"allOf", "anyOf", "oneOf", "prefixItems"}
    result = {}
    for key, value in schema.items():
        if key in annotations:
            continue
        if key in {"enum", "const"}:
            result[key] = value
        elif key in maps:
            result[key] = {
                name: _semantic_schema(child) for name, child in value.items()
            }
        elif key in sequences:
            result[key] = [_semantic_schema(child) for child in value]
        elif key in single:
            result[key] = _semantic_schema(value)
        else:
            result[key] = value
    return result


def state_definition(
    origin: str,
    entry: dict,
    spec: dict,
    *,
    attrs: dict | None = None,
    registry: dict | None = None,
) -> dict:
    """The admitted semantic definition and payload domain of one widget verb.

    Later declarations may reuse a verb's name with different meaning or types.
    Recorded definitions distinguish those new operations from history, while
    descriptive schema annotations remain free to change. A verb's `text` flag
    is not recorded: all it changes is the required `text` in `detail`. Its
    `attention` declaration changes delivery, not the state operation; admission
    records that decision separately on the event.
    """
    from copy import deepcopy

    return deepcopy(
        {
            "origin": origin,
            "unit": spec["unit"],
            "record": recorded(spec),
            "creates": spec.get("creates"),
            "decides": decides(spec),
            "detail": _semantic_schema(
                detail_schema(entry, spec, attrs=attrs, registry=registry)
            ),
        }
    )


def same_state_operation(recorded, current) -> bool:
    """The same fold destination and construction, independent of payload domain.

    The operation is the fields `state_definition` writes, `detail` aside. A field
    another Leaf version recorded beside them, such as a verb flag, is how that version
    wrote the definition, not part of the operation, so it never retracts a decision. A
    missing field still
    fails."""
    return (
        isinstance(recorded, dict)
        and isinstance(current, dict)
        and all(
            key in recorded and same_state_definition(recorded[key], value)
            for key, value in current.items()
            if key != "detail"
        )
    )


def event_spec(entry: dict, event: dict) -> dict | None:
    """The verb (`verbs`) an action or report names, when its writer sent it: a verb
    declares one writer, and the kind that carries it says which side sent it
    (`registry.kernel.verb_writers`), so its coordinate is only ever written from one
    side."""
    spec = entry.get("verbs", {}).get(event["action"])
    if spec is None or verb_writer(spec) != verb_writers()[event["kind"]]:
        return None
    return spec


def retirement_slots(registry: dict) -> dict:
    """owner tag → {outcome verb → the tags that leave the page under it}: every
    owner/member pair `retired-when` relates, the member naming the outcome and
    `owners` the widgets whose decision reaches it. Read out of the merged
    registry rather than known here, so which widgets a decision settles is a
    fact about this page's vocabulary and never a list in the code."""
    slots = {}
    for tag, entry in registry.items():
        if not is_element_name(tag) or not entry.get("retired-when"):
            continue
        outcome = entry["retired-when"]
        for owner in entry["owners"]:
            slots.setdefault(owner, {}).setdefault(outcome, []).append(tag)
    return slots


def stamp_states(registry: dict) -> dict:
    """Write `$states` into a validated vocabulary: tag → verb → {`writer`, the side
    `verb_writer` names; `definition`, the operation `state_definition` records on an
    admitted event}, for every verb (`verbs`).

    Each composition stamps it (`registry.layer.stamp_composition`), so the browser
    compares an event's recorded operation with this definition, and reads a verb's
    writer, rather than deriving either a second time."""
    registry["$states"] = {
        tag: {
            verb: {
                "writer": verb_writer(spec),
                "definition": state_definition(tag, entry, spec),
            }
            for verb, spec in state_specs(entry)
        }
        for tag, entry in registry.items()
        if is_element_name(tag) and entry.get("verbs")
    }
    return registry


# A word a widget takes that its layer has to know, as two things: the attribute that
# carries it, the same on every widget (the registry's `$attributes`), and the
# layer-wide fact listing the words the layer has. A misspelt tone paints nothing, and
# renders as a page that otherwise looks perfectly well, so the attribute's schema has
# to refuse any other word. The list is the layer's ($tones) rather than any widget's,
# so a new tag that takes a tone needs only to declare `tone`. A second such word is a
# row here.
DECLARED_WORDS = (("tone", "$tones"),)
# The attribute that holds an element's title on every widget that takes it
# (`$attributes`), which names the element away from itself
# (`passages.element_name`, the browser's `addressableName`).
NAME_ATTRIBUTE = "label"


def stamp_words(registry: dict) -> dict:
    """Write into a validated vocabulary the words of each attribute that takes the
    layer's (`DECLARED_WORDS`) as its schema's `enum`, so the attribute's schema is
    complete: validation refuses any other word, and an author reading the entry sees
    which it may write.

    An attribute's schema may be `true`, which then becomes the words alone, or
    `false`, which admits no word already and is left as it is.

    Each composition stamps it (`registry.layer.stamp_composition`)."""
    for attr, fact in DECLARED_WORDS:
        for entry in element_declarations(registry).values():
            properties = entry["attributes"].get("properties", {})
            if attr not in properties:
                continue
            if properties[attr] is True:
                properties[attr] = {}
            if isinstance(properties[attr], dict):
                properties[attr]["enum"] = list(registry[fact]["names"])
    return registry


# The boolean attribute a version sets on a widget to take back what a writer recorded
# on the whole of it: the user's decision (the registry's `$restated`) or the agent's
# report (`$report`).
RETRACTIONS = {"user": "restated", "agent": "overruled"}


def stamp_retractions(registry: dict) -> dict:
    """Write into a validated vocabulary, for each verb whose unit is the whole widget,
    the attribute that takes it back (`RETRACTIONS`) as a boolean, replacing any the
    widget's declaration lists. So a version can take back every such decision and
    report whatever the declaration says, and validation and an author reading the
    entry read the attribute there. An agent's verb always has that unit. A verb with
    another unit names a member by id, as a board's move names a card, and that
    member's own declaration lists `restated`.

    Each composition stamps it (`registry.layer.stamp_composition`)."""
    for entry in element_declarations(registry).values():
        for _verb, spec in state_specs(entry):
            if spec["unit"] == "widget":
                properties = entry["attributes"].setdefault("properties", {})
                properties[RETRACTIONS[verb_writer(spec)]] = {"type": "boolean"}
    return registry


def _named_attributes(entry: dict):
    """(attribute, grammar) for each attribute of one element declaration whose value
    is a name Leaf looks up: the element's own `id`, an input's source attribute
    (`inputs`) and a verb's `contract` attribute. A `refers` attribute is
    left out: `page check` resolves its value to the element it names, whatever that
    element's id or key."""
    yield "id", ELEMENT_ID
    for spec in entry.get("inputs", {}).values():
        if source := spec.get("source"):
            yield source, DATA_SOURCE_NAME
    for _verb, spec in state_specs(entry):
        if binding := spec.get("contract"):
            yield binding["attribute"], DATA_CONTRACT_NAME


def stamp_grammars(registry: dict) -> dict:
    """Write into a validated vocabulary the `id` every element takes, as a string and
    the first of its attributes, and the grammar of each attribute `_named_attributes`
    finds, as its schema's `pattern`, replacing any the declaration gave. Leaf owns
    `id` and these grammars, so a package declares only whether an element requires
    its `id` and that a verb's `contract` attribute is a string; an input's source
    attribute is one already, written by `complete_declarations` where the declaration
    left it out. Validation and an author reading the entry read the rest here. A
    schema a declaration lists for `id` is replaced, not kept: Leaf names a created
    child, an asking widget and a pane by id, and one whose `id` took no string could
    never be named. Another such attribute's schema may be `true`, which then becomes
    the grammar alone, or `false`, which admits no value already and is left as it is.

    Each composition stamps it (`registry.layer.stamp_composition`)."""
    for entry in element_declarations(registry).values():
        attributes = entry["attributes"]
        properties = attributes["properties"] = {"id": {"type": "string"}} | {
            attr: schema
            for attr, schema in attributes.get("properties", {}).items()
            if attr != "id"
        }
        for attr, grammar in _named_attributes(entry):
            if properties.get(attr) is True:
                properties[attr] = {}
            if isinstance(properties.get(attr), dict):
                properties[attr]["pattern"] = f"^{grammar}$"
    return registry


def stamp_decisions(registry: dict) -> dict:
    """Write `$decisions` into a validated vocabulary: owner tag → {`verb`, its deciding
    verb (`verbs`); `retires`, `retirement_slots`' outcome → member tags}, for every
    tag that declares a deciding verb.

    Each composition stamps it (`registry.layer.stamp_composition`), so the browser
    reads which verb decides a widget and what its outcome takes off the page rather
    than walking the declarations a second time. Python reads `deciding_verb` and
    `retirement_slots` themselves, the definitions this is derived from, since
    validation asks them of declarations that no composition has stamped yet."""
    slots = retirement_slots(registry)
    registry["$decisions"] = {
        tag: {"verb": verb, "retires": slots.get(tag, {})}
        for tag, entry in registry.items()
        if is_element_name(tag) and (verb := deciding_verb(entry)) is not None
    }
    return registry


def validate_modules(registry: dict, path) -> None:
    """Refuse each declaration of what only a module provides whose tag has none
    (`contract.MODULES`), the first finding in each. Validation asks it of every
    declaration, and a composition that reuses an earlier validation asks it again
    (`registry.page.compose_page_registry`): the declarations it validated can stand
    unchanged while a module file goes. It lives here, beside `MODULES`, because that
    reuse runs in a harness hook, which loads no schema validator."""
    with gathering() as unit:
        for tag, entry in element_declarations(registry).items():
            with unit():
                require_module(tag, entry, registry, path)


def require_module(tag: str, entry: dict, registry: dict, path) -> None:
    # A declaration of one of these without its module is a widget that reads as
    # working and does nothing. Declarations validated apart from the files they
    # compose with carry no `MODULES`, and there nothing can say.
    needs_module = [
        key
        for key in (
            "verbs",
            "verbatim",
            "shadow",
            "history",
        )
        if entry.get(key)
    ] + (["visual"] if isinstance(entry.get("visual"), dict) else [])
    # Leaf sets an input's `property` only on an element whose class is defined.
    if any(spec.get("property") for spec in entry.get("inputs", {}).values()):
        needs_module.append("inputs")
    if needs_module and MODULES in registry and not upgraded(registry, tag):
        raise registry_error(
            "needs-module", path, tag, keys=needs_module, module=f"widgets/{tag}.js"
        )
