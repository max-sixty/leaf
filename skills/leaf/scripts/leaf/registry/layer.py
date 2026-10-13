"""Layer registry composition and contract validation."""

import json
from copy import deepcopy

import jmespath
import turbohtml
from jmespath.exceptions import JMESPathError
from jsonschema.exceptions import SchemaError

from leaf.schema import DECLARED_MARKS, EXTENSION_SCHEMA, LAYER_FACTS_SCHEMA

from .contract import (
    is_element_name,
    registry_error,
    stamp_decisions,
    stamp_states,
)
from .schema import (
    check_schema,
    json_validator,
    schema_reading,
    unresolved_schema_reference,
)

# The `$events` members a layer may restate; the rest are the kernel's.
LAYER_OWNED_EVENTS = frozenset({"handling", "answering"})


def merge_layer_declarations(merged: dict, declarations: dict) -> None:
    """Fold one layer's top-level registry declarations into the merge.

    Every authored vocabulary entry replaces the earlier one whole, whether an
    element schema or a selector idiom: a half-old, half-new entry is no layer's
    declaration. A $ declaration holds shared layer facts, so its members merge.
    A member that is itself a map merges by its own keys:
    $languages.paths is indexed by extension, and a layer adding `.svelte` must not
    silently drop every shipped extension with it. Scalar and list members replace
    whole — a names list is one statement. `$events` is the exception: every member
    but `handling` and `answering` is Leaf's fixed kernel transport contract and its
    `protocol`, which no layer changes.

    Inside a map member the merge is JSON merge-patch: a later layer's value
    replaces the key, a new key joins, and `null` removes one — which is the
    only way a project can take a shipped reaction token off its bar, or a user
    an extension off `$languages.paths`, without restating the whole map.
    """
    for name, entry in declarations.items():
        earlier = merged.get(name)
        if not (name.startswith("$") and earlier is not None):
            merged[name] = entry
            continue
        if name == "$events":
            # Only the kernel's own value passes, compared as JSON so that `true` or
            # `1.0` is not taken for a protocol of 1, and the kernel's copy is kept.
            for key in entry.keys() - LAYER_OWNED_EVENTS:
                if _canonical(entry[key]) != _canonical(earlier.get(key)):
                    raise registry_error("fixed-events", key=key)
            entry = {key: entry[key] for key in entry.keys() & LAYER_OWNED_EVENTS}
        combined = {**earlier, **entry}
        for key, value in entry.items():
            if isinstance(value, dict) and isinstance(earlier.get(key), dict):
                combined[key] = {
                    k: v for k, v in {**earlier[key], **value}.items() if v is not None
                }
        merged[name] = {k: v for k, v in combined.items() if v is not None}


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True)


def stamp_composition(registry: dict) -> dict:
    """Write into a validated vocabulary what the browser reads rather than derives:
    `$decisions` (`registry.contract.stamp_decisions`), `$states`
    (`registry.contract.stamp_states`), and `$marks`, the declared marks
    (`schema.DECLARED_MARKS`) it paints on a message it renders.

    Each composition that ends in a vocabulary stamps it, `page init`'s layer and a
    page's own declarations over it, overwriting whatever a layer declared under
    these names.
    """
    stamp_decisions(registry)
    stamp_states(registry)
    registry["$marks"] = deepcopy(DECLARED_MARKS)
    return registry


def check_layer_facts(registry: dict, path) -> None:
    """Refuse a vocabulary whose shared layer facts depart from `LAYER_FACTS_SCHEMA`,
    naming where and how."""
    error = min(
        json_validator(LAYER_FACTS_SCHEMA).iter_errors(registry), key=str, default=None
    )
    if error is not None:
        raise registry_error("layer-facts", path, **schema_reading(error))


def validate_layer_declarations(registry: dict, path) -> None:
    """The layer facts' shape (`LAYER_FACTS_SCHEMA`), then what the schema cannot
    say: each name one fact gives another, each `when` and contract `schema` a JSON
    Schema, each `resources` entry JMESPath, the documented keys, and the idioms."""
    check_layer_facts(registry, path)
    events = registry["$events"]
    for key in ("handling", "answering"):
        for kind, clauses in events[key].items():
            if key == "handling" and kind not in events["kinds"]:
                raise registry_error("undeclared-event-kind", path, kind=kind)
            for clause in clauses:
                if "when" not in clause:
                    continue
                try:
                    check_schema(clause["when"])
                except SchemaError as error:
                    raise registry_error(
                        "invalid-when",
                        path,
                        key=key,
                        kind=kind,
                        **schema_reading(error),
                    ) from error
    # $keys documents exactly the x- keys the lint admits, one string per key: the
    # keys are closed here (EXTENSION_SCHEMA), so a member for a key that cannot be
    # declared is documentation of nothing, and a key with no member is one an author
    # reads the registry for and finds unsaid. Agents query it and the site's table is
    # generated from it, which is what makes the pin worth keeping.
    keys = registry.get("$keys")
    admitted = set(EXTENSION_SCHEMA["properties"])
    documented = set(keys or {}) - {"description"}
    if (
        not isinstance(keys, dict)
        or not isinstance(keys.get("description"), str)
        or not all(isinstance(text, str) and text for text in keys.values())
        or documented != admitted
    ):
        raise registry_error(
            "keys-documentation",
            path,
            missing=sorted(admitted - documented),
            unadmitted=sorted(documented - admitted),
        )
    # Idioms share author-facing fields with elements; only marks whose readers
    # consume delivery's paint can be declared on selectors. Validate every selector,
    # even one without marks, because it remains an authored vocabulary identity.
    marks = {key for key, mark in DECLARED_MARKS.items() if mark.get("idiom")}
    allowed = {"description", "x-example", "x-instructions"} | marks
    probe = turbohtml.parse("<p></p>").find("p")
    for selector, entry in registry.items():
        if selector.startswith("$") or is_element_name(selector):
            continue
        try:
            probe.matches(selector)
        except turbohtml.SelectorSyntaxError as error:
            raise registry_error(
                "idiom-selector", path, selector=selector, error=str(error)
            ) from None
        if (
            not isinstance(entry, dict)
            or set(entry) - allowed
            or not isinstance(entry.get("description"), str)
            or not entry["description"].strip()
            or not isinstance(entry.get("x-example"), str)
            or not entry["x-example"].strip()
        ):
            raise registry_error(
                "idiom-fields", path, selector=selector, marks=sorted(marks)
            )
        for key in set(entry) - {"description"}:
            if not json_validator(EXTENSION_SCHEMA["properties"][key]).is_valid(
                entry[key]
            ):
                raise registry_error(
                    "idiom-value", path, selector=selector, key=key, value=entry[key]
                )
    languages = registry["$languages"]
    if strays := sorted(
        extension
        for extension, language in languages["paths"].items()
        if language not in languages["names"]
    ):
        raise registry_error("undeclared-language", path, extensions=strays)
    for contract, declaration in registry["$data"]["contracts"].items():
        for expression in declaration.get("resources", []):
            try:
                jmespath.compile(expression)
            except JMESPathError as error:
                raise registry_error(
                    "contract-resource",
                    path,
                    contract=contract,
                    expression=expression,
                    error=str(error),
                ) from error
        records = declaration.get("records") or {}
        if len(set(records.values())) != len(records):
            raise registry_error("contract-records", path, contract=contract)
        try:
            check_schema(declaration["schema"])
        except SchemaError as error:
            raise registry_error(
                "contract-schema", path, contract=contract, **schema_reading(error)
            ) from error
        if reference := unresolved_schema_reference(declaration["schema"]):
            raise registry_error(
                "contract-reference", path, contract=contract, reference=reference
            )
