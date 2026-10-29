"""Readings and derived declarations from a supplied registry vocabulary."""

import json
import re
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from jsonschema._utils import equal as same_state_definition

from leaf.files import read_json
from leaf.schema import WIDGET_NAME

from ..findings import Finding, Rejected, element_at
from .kernel import verb_writers


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


def exhibits(attrs: dict, entry: dict) -> bool:
    """Whether this occurrence quotes its descendants."""
    rule = entry.get("x-exhibit", False)
    return matches_when(attrs, rule["when"]) if isinstance(rule, dict) else rule


def is_element_name(name: str) -> bool:
    """Whether a vocabulary key names one Leaf custom element rather than a selector.

    Non-dollar keys are authored vocabulary: exact ``WIDGET_NAME`` keys declare
    elements; every other key is a CSS selector idiom, including native tags and
    selectors such as ``lf-options.selected``. Validation admits selectors once
    at composition; consumers share this classification without parsing CSS.
    """
    return re.fullmatch(WIDGET_NAME, name) is not None


def element_declarations(registry: dict) -> dict:
    """The element schemas from one registry's authored vocabulary."""
    return {name: entry for name, entry in registry.items() if is_element_name(name)}


def event_clauses(entry: dict, registry: dict | None) -> list[dict]:
    """What the layer asks of the agent for one delivered event, read off the
    registry's `$events`: the event kind's `handling` clauses, then the `answering`
    clauses of the answer it owes, each kept when its `when` schema matches.

    `entry` is the event record, plus the `answer` a delivery captured when the
    event owes one, addressed for the route delivering it (`workflows` and
    `delivery` own those derivations), and the `thread` digest of the thread
    it belongs to (`thread_context` owns that one). `delivery.DELIVERY` declares
    the shape of each, as its batches carry them. A `when` can therefore read any
    of them as well as the record, so a clause states the case a delivery is in
    rather than naming a condition the delivery already settles, such as a
    thread's missing title. An event owing nothing is told nothing about
    answering: a pick before Done, or a message a newer one in its thread answers
    through. A project layer restates a kind's clauses merge-patch style, so the
    event carries the rule of the layer the page selects. A missing or invalid
    registry leaves the event unexplained; it never substitutes instructions from a
    different layer. What each case of each kind receives from the shipped layer,
    clause by clause, is snapshotted in `tests/_regtest_outputs/`, by
    `test_each_case_of_an_event_is_told_what_the_snapshot_shows`."""
    from .schema import json_validator

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
    """The part ids one authored element admits as `anchor.visual`.

    A widget admits its complete registered inventory when its opt-in attribute is
    present, or ids beginning its declared prefixes. Admission does not say a part
    is on screen; the browser resolves that, and an admitted id nothing renders detaches.
    """

    prefixes: tuple[str, ...] = ()
    all: bool = False

    def __contains__(self, part: str) -> bool:
        return part.split() == [part] and (
            self.all
            or any(
                part.startswith(prefix) and part != prefix for prefix in self.prefixes
            )
        )

    def __bool__(self) -> bool:
        return bool(self.prefixes or self.all)

    def __str__(self) -> str:
        if self.all:
            return "the registered visual inventory"
        if self.prefixes:
            return f"ids starting with {' or '.join(map(repr, self.prefixes))}"
        return "no visual parts"


def visual_parts(record: dict, registry: dict) -> VisualParts:
    """The visual-part ids one authored Leaf element admits."""
    visual = registry.get(record.get("tag"), {}).get("x-visual")
    if not isinstance(visual, dict):
        return VisualParts()
    if "prefixes" in visual:
        return VisualParts(prefixes=tuple(visual["prefixes"]))
    return VisualParts(all=visual["parts"] in record.get("attrs", {}))


def registry_path(registry: dict, path: str):
    """Resolve a dotted package declaration such as `$work.widgets`."""
    value = registry
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def reference_relation_problem(
    reference: dict, registry: dict, declarations: dict
) -> tuple[str, dict] | None:
    """Why one `{via, where}` or `{tag, key}` target relation cannot name a declared
    widget, as a finding's code and values. A keyed relation needs its key declared
    unique on the member, which also supplies the owner it resolves within, so one
    reference names at most one member."""
    if member := reference.get("tag"):
        key = reference["key"]
        if member not in declarations:
            return "refers-unknown-member", {"member": member}
        if key not in declarations[member].get("x-unique", {}):
            return "refers-unkeyed", {"member": member, "key": key}
        return None
    via = reference.get("via")
    if via is None:
        return None
    relation = registry_path(registry, via)
    if not isinstance(relation, dict):
        return "refers-unknown-map", {"via": via}
    predicate = reference["where"]
    if any(
        target in declarations
        and isinstance(declaration, dict)
        and all(declaration.get(key) == value for key, value in predicate.items())
        for target, declaration in relation.items()
    ):
        return None
    return "refers-unmatched", {"via": via, "where": predicate}


class RegistryError(Rejected):
    """A registry that is not a vocabulary, raised rather than exited because two doors
    read one. The CLI prints the message and stops; the page server owes the browser an
    answer, and `sys.exit` inside its request handler killed the connection mid-POST
    while every other rejection beside it returned a 400 — so a page whose
    stamp had fallen behind the running layer met the user's click with a dead socket
    and no words. The CLI renders it with Click's standard Error prefix, while the
    server catches the same rejection and answers the request.

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
# `projection/model.js` owns the reasoning and computes the keys between neighbours;
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
    fold unit, and an attribute set's or position's ids. Derived schemas are
    readings, never inserted into the registry beside the effect that owns them.

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
        value = entry["properties"][record["attr"]]
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
    (x-retired-when, x-withdrawn-as). Its required `outcome` carries that choice;
    the same field name on any other verb is ordinary domain data.
    The browser reads the role from `$decisions`
    (`registry.contract.stamp_decisions`)."""
    return spec.get("decides", False)


def deciding_verbs(entry: dict) -> list[str]:
    """Every x-state verb of one declaration that decides; validation holds it to one."""
    return [verb for verb, spec in entry.get("x-state", {}).items() if decides(spec)]


def deciding_verb(entry: dict) -> str | None:
    """The one deciding x-state verb, or None."""
    return next(iter(deciding_verbs(entry)), None)


def deciding_outcomes(entry: dict) -> list[str]:
    """The outcomes the deciding verb may stand under; empty without one, or where
    the verb declares no `outcome` words. Validation reads it before holding the
    verb to its shape (`state.validate_deciding_verb`), and a declaration reads it
    of another whose own check may have failed."""
    verb = deciding_verb(entry)
    if verb is None:
        return []
    detail = entry["x-state"][verb].get("detail") or {}
    schema = detail.get("properties", {}).get("outcome")
    return list(schema.get("enum", [])) if isinstance(schema, dict) else []


def verb_writer(spec: dict) -> str:
    """The side that writes one x-state verb: `agent` where it says so, else `user`.
    The browser reads it from `$states` (`stamp_states`)."""
    return spec.get("writer", "user")


def state_specs(entry: dict, *, writer: str | None = None):
    """The x-state verb declarations on one element declaration, as (verb, spec),
    narrowed to the verbs one side writes when `writer` names it."""
    for verb, spec in entry.get("x-state", {}).items():
        if writer is None or verb_writer(spec) == writer:
            yield verb, spec


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
            "record": spec.get("record"),
            "creates": spec.get("creates"),
            "decides": decides(spec),
            "detail": _semantic_schema(
                detail_schema(entry, spec, attrs=attrs, registry=registry)
            ),
        }
    )


def same_state_operation(recorded, current) -> bool:
    """The same fold destination and construction, independent of payload domain.

    The operation is the fields `state_definition` writes now, `detail` aside. A
    field an earlier Leaf recorded beside them, such as the verb flag it recorded
    as `update` and then `report`, is how that version wrote the definition, not
    part of the operation, so it never retracts a decision. A missing field still
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
    """The x-state verb an action or report names, when its writer sent it: a verb
    declares one writer, and the kind that carries it says which side sent it
    (`registry.kernel.verb_writers`), so its coordinate is only ever written from one
    side."""
    spec = entry.get("x-state", {}).get(event["action"])
    if spec is None or verb_writer(spec) != verb_writers()[event["kind"]]:
        return None
    return spec


def retirement_slots(registry: dict) -> dict:
    """owner tag → {outcome verb → the tags that leave the page under it}: every
    owner/member pair `x-retired-when` relates, the member naming the outcome and
    `x-owners` the widgets whose decision reaches it. Read out of the merged
    registry rather than known here, so which widgets a decision settles is a
    fact about this page's vocabulary and never a list in the code."""
    slots = {}
    for tag, entry in registry.items():
        if not is_element_name(tag) or not entry.get("x-retired-when"):
            continue
        outcome = entry["x-retired-when"]
        for owner in entry["x-owners"]:
            slots.setdefault(owner, {}).setdefault(outcome, []).append(tag)
    return slots


def stamp_states(registry: dict) -> dict:
    """Write `$states` into a validated vocabulary: tag → verb → {`writer`, the side
    `verb_writer` names; `definition`, the operation `state_definition` records on an
    admitted event}, for every x-state verb.

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
        if is_element_name(tag) and entry.get("x-state")
    }
    return registry


# A word a widget declares that its layer has to know, as two things: the x- key
# naming the attribute that carries it, and the layer-wide fact listing the words the
# layer has. A misspelt language colors nothing and a misspelt tone paints nothing,
# and each renders as a page that otherwise looks perfectly well, so the attribute's
# schema has to refuse any other word. The list is the layer's ($languages, $tones)
# rather than any widget's, and which attribute carries the word is the entry's to
# say, so a new tag that takes a tone needs only its x-tone. A third such word is a
# row here.
DECLARED_WORDS = (("x-language", "$languages"), ("x-tone", "$tones"))


def stamp_words(registry: dict) -> dict:
    """Write into a validated vocabulary each declared attribute's words
    (`DECLARED_WORDS`) as its schema's `enum`, so the attribute's schema is complete:
    validation refuses any other word, and an author reading the entry sees which it
    may write.

    An attribute's schema may be `true`, which then becomes the words alone, or
    `false`, which admits no word already and is left as it is.

    Each composition stamps it (`registry.layer.stamp_composition`)."""
    for key, fact in DECLARED_WORDS:
        for tag, entry in registry.items():
            if not (is_element_name(tag) and (attr := entry.get(key))):
                continue
            properties = entry["properties"]
            if properties[attr] is True:
                properties[attr] = {}
            if isinstance(properties[attr], dict):
                properties[attr]["enum"] = list(registry[fact]["names"])
    return registry


def stamp_decisions(registry: dict) -> dict:
    """Write `$decisions` into a validated vocabulary: owner tag → {`verb`, its deciding
    x-state verb; `retires`, `retirement_slots`' outcome → member tags}, for every tag
    that declares a deciding verb.

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
