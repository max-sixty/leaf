"""Layer registry composition and contract validation."""

import json

import jmespath
import turbohtml
from jmespath.exceptions import JMESPathError
from jsonschema.exceptions import SchemaError

from leaf.schema import (
    AWAITS_SCHEMA,
    EXTENSION_SCHEMA,
    IDIOM_SCHEMA,
    LAYER_FACTS_SCHEMA,
    VERB_SCHEMA,
)

from .contract import (
    is_element_name,
    registry_error,
    stamp_decisions,
    stamp_states,
    stamp_words,
)
from .kernel import answer_kinds
from .schema import (
    check_schema,
    json_validator,
    schema_reading,
    unresolved_schema_reference,
)

# The `$events` members a layer may restate; the rest are the kernel's.
LAYER_OWNED_EVENTS = frozenset({"handling", "answering"})
# The facts both runtimes read from the kernel registry, each whole and none from a
# layer (`registry.kernel`): Python and the browser (`runtime/kernel-facts.js`) both
# read the running Leaf's own copy, so a layer's change would reach neither.
KERNEL_FACTS = frozenset({"$passages", "$names", "$marks", "$authored"})
# The facts that document a declaration's keys, each beside the schema that admits
# those keys (`validate_layer_declarations`).
DOCUMENTED_KEYS = {
    "$keys": EXTENSION_SCHEMA,
    "$state": VERB_SCHEMA,
    "$awaits": AWAITS_SCHEMA,
}


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
    `protocol`, which no layer changes; so is each of `KERNEL_FACTS`, whole.

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
        if name in KERNEL_FACTS:
            if _canonical(entry) != _canonical(earlier):
                raise registry_error("fixed-kernel-fact", name=name)
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
    """Write into a validated vocabulary what its readers read rather than derive:
    `$decisions` (`registry.contract.stamp_decisions`) and `$states`
    (`registry.contract.stamp_states`), which the browser reads, and each declared
    attribute's words as its schema's `enum` (`registry.contract.stamp_words`),
    which validation and an author reading the entry read.

    Each composition that ends in a vocabulary stamps it, `page init`'s layer and a
    page's own declarations over it, overwriting whatever a layer declared under
    these names.
    """
    stamp_decisions(registry)
    stamp_states(registry)
    stamp_words(registry)
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
    # A layer instructs only the kinds there are: events of a declared kind, and the
    # answers the kernel's own `answering` instructs.
    declared = {"handling": sorted(events["kinds"]), "answering": answer_kinds()}
    for key in ("handling", "answering"):
        for kind, clauses in events[key].items():
            if kind not in declared[key]:
                raise registry_error(
                    "undeclared-event-kind",
                    path,
                    key=key,
                    kind=kind,
                    declared=declared[key],
                )
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
    # Each documenting fact holds exactly the keys its schema admits, one string per
    # key, beside its description: the keys are closed by that schema, so a member for
    # a key that cannot be declared is documentation of nothing, and a key with no
    # member is one an author reads the registry for and finds unsaid. Agents query
    # them and the site's table is generated from $keys, which is what makes the pin
    # worth keeping.
    for fact, schema in DOCUMENTED_KEYS.items():
        members = registry.get(fact)
        admitted = set(schema["properties"])
        documented = set(members or {}) - {"description"}
        if (
            not isinstance(members, dict)
            or not isinstance(members.get("description"), str)
            or not all(isinstance(text, str) and text for text in members.values())
            or documented != admitted
        ):
            raise registry_error(
                "keys-documentation",
                path,
                fact=fact,
                missing=sorted(admitted - documented),
                unadmitted=sorted(documented - admitted),
            )
    # Validate every selector, because it remains an authored vocabulary identity.
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
        if errors := sorted(json_validator(IDIOM_SCHEMA).iter_errors(entry), key=str):
            raise registry_error(
                "idiom-schema", path, selector=selector, **schema_reading(errors[0])
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
