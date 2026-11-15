"""Complete registry validation orchestration, and the checks of a vocabulary's
layer facts and the declarations beside its elements."""

import hashlib
import json

import jmespath
import turbohtml
from jmespath.exceptions import JMESPathError
from jsonschema.exceptions import SchemaError

from leaf.schema import (
    AWAITS_SCHEMA,
    EXTENSION_SCHEMA,
    IDIOM_SCHEMA,
    LAYER_FACTS,
    OPTIONAL_LAYER_FACTS,
    VERB_SCHEMA,
)

from .contract import (
    RegistryError,
    element_declarations,
    gathering,
    is_element_name,
    registry_error,
    registry_finding,
    state_specs,
)
from .kernel import answer_kinds
from .schema import (
    check_schema,
    json_validator,
    schema_reading,
    unresolved_schema_reference,
)
from .widgets import (
    validate_widget_relations,
    validate_widget_schemas,
)

# The facts that document a declaration's keys, each beside the schema that admits
# those keys (`validate_layer_declarations`).
DOCUMENTED_KEYS: dict[str, dict] = {
    "$keys": EXTENSION_SCHEMA,
    "$state": VERB_SCHEMA,
    "$awaits": AWAITS_SCHEMA,
}

# The vocabularies this process has validated, by a digest of their content, oldest
# first. Validation is a pure function of the vocabulary, `source` naming it only in a
# rejection, and every page selecting one layer composes the same one: the suite's
# pages, a site build's examples, and a harness's pages each validated it anew, about a
# tenth of a second apiece for the bundled packages.
_VALIDATED: dict[bytes, None] = {}
_VALIDATED_LIMIT = 16


def validate_registry(registry: dict, source) -> dict:
    """Validate one complete vocabulary, refusing with the first problem in each
    independent unit (`contract.gathering`)."""
    key = hashlib.blake2b(
        json.dumps(registry, sort_keys=True, separators=(",", ":")).encode(),
        digest_size=16,
    ).digest()
    if key in _VALIDATED:
        return registry
    _validate(registry, source)
    _VALIDATED[key] = None
    while len(_VALIDATED) > _VALIDATED_LIMIT:
        _VALIDATED.pop(next(iter(_VALIDATED)), None)
    return registry


def _validate(registry: dict, path) -> None:
    """The layer facts' shape first, since every later check reads it. Then the
    layer's other facts beside the element declarations, which read nothing of
    each other, and only once every declaration holds alone does each meet the
    others, so a declaration's relations never read another half-validated. The
    work roles read the declarations they map last."""
    check_layer_facts(registry, path)
    declarations = element_declarations(registry)
    with gathering() as unit:
        with unit():
            validate_layer_declarations(registry, path)
        with unit():
            validate_widget_schemas(declarations, path)
            validate_widget_relations(registry, declarations, registry["$data"], path)
            validate_work_roles(registry, declarations, path)


def check_layer_facts(registry: dict, path) -> None:
    """Refuse a vocabulary whose shared layer facts depart from `LAYER_FACTS`, or
    from `OPTIONAL_LAYER_FACTS` where it declares one, naming where and how the first
    departure in each fact does. Each fact is held to its own schema, so one that is
    missing or malformed is named beside every other."""
    findings = []
    for fact, schema in {**LAYER_FACTS, **OPTIONAL_LAYER_FACTS}.items():
        required = [fact] if fact in LAYER_FACTS else []
        reader = json_validator({"properties": {fact: schema}, "required": required})
        if error := min(reader.iter_errors(registry), key=str, default=None):
            findings.append(
                registry_finding("layer-facts", path, **schema_reading(error))
            )
    if findings:
        raise RegistryError(findings)


def validate_layer_declarations(registry: dict, path) -> None:
    """What `LAYER_FACTS` cannot say, in a vocabulary whose facts hold it
    (`check_layer_facts`): each name one fact gives another, each `when` and contract
    `schema` a JSON Schema, each `resources` entry JMESPath, the documented keys, and
    the idioms. Each event kind's clauses, documenting fact, idiom, the languages and
    each data contract is checked independently, and the refusal names the first
    problem in each (`contract.gathering`)."""
    events = registry["$events"]
    # A layer instructs only the kinds there are: events of a declared kind, and the
    # answers the kernel's own `answering` instructs.
    declared = {"handling": sorted(events["kinds"]), "answering": answer_kinds()}
    probe = turbohtml.parse("<p></p>").find("p")
    with gathering() as unit:
        for key in ("handling", "answering"):
            for kind, clauses in events[key].items():
                with unit():
                    _validate_event_clauses(key, kind, clauses, declared[key], path)
        for fact, schema in DOCUMENTED_KEYS.items():
            with unit():
                _validate_documented_keys(fact, registry.get(fact), schema, path)
        # Validate every selector, because it remains an authored vocabulary identity.
        for selector, entry in registry.items():
            if selector.startswith("$") or is_element_name(selector):
                continue
            with unit():
                _validate_idiom(probe, selector, entry, path)
        with unit():
            _validate_languages(registry["$languages"], path)
        for contract, declaration in registry["$data"]["contracts"].items():
            with unit():
                _validate_data_contract(contract, declaration, path)


def _validate_event_clauses(key: str, kind: str, clauses, declared, path) -> None:
    if kind not in declared:
        raise registry_error(
            "undeclared-event-kind", path, key=key, kind=kind, declared=declared
        )
    for clause in clauses:
        if "when" not in clause:
            continue
        try:
            check_schema(clause["when"])
        except SchemaError as error:
            raise registry_error(
                "invalid-when", path, key=key, kind=kind, **schema_reading(error)
            ) from error


def _validate_documented_keys(fact: str, members, schema: dict, path) -> None:
    """Each documenting fact holds exactly the keys its schema admits, one string per
    key, beside its description: the keys are closed by that schema, so a member for
    a key that cannot be declared is documentation of nothing, and a key with no
    member is one an author reads the registry for and finds unsaid. Agents query
    them and the site's table is generated from $keys, which is what makes the pin
    worth keeping."""
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


def _validate_idiom(probe, selector: str, entry: dict, path) -> None:
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


def _validate_languages(languages: dict, path) -> None:
    if strays := sorted(
        extension
        for extension, language in languages["paths"].items()
        if language not in languages["names"]
    ):
        raise registry_error("undeclared-language", path, extensions=strays)


def _validate_data_contract(contract: str, declaration: dict, path) -> None:
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


def validate_work_roles(registry: dict, declarations: dict, path) -> None:
    """Hold each `$work.widgets` entry, whose shape `check_layer_facts` holds, to
    the declaration of the tag it maps, refusing with the first problem in each.
    `runtime/work.js` reads the entries as given, so an attribute the tag lacks, or a
    value its state can't take, would leave a goal never done or a worker without its
    goal, with nothing saying why. A role's state is the one widget value record on
    its attribute, which work.js also reads as the role's report verb, and a worker's
    `on` names its goal by id."""
    roles = registry.get("$work", {}).get("widgets", {})
    if unknown := sorted(roles.keys() - declarations.keys()):
        raise registry_error(
            "unknown-declarations", path, key="$work.widgets", names=unknown
        )
    with gathering() as unit:
        for tag, role in roles.items():
            with unit():
                _validate_work_role(tag, role, declarations[tag], path)


def _validate_work_role(tag: str, role: dict, entry: dict, path) -> None:
    properties = entry.get("properties", {})
    for key in ("state", "on", "stoppedAt"):
        if key in role and role[key] not in properties:
            raise registry_error(
                "undeclared-attributes",
                path,
                tag,
                key=f"$work.widgets.{tag}.{key}",
                names=[role[key]],
            )
    references = entry.get("x-refers", {})
    if (on := role.get("on")) and (on not in references or "key" in references[on]):
        raise registry_error("work-reference", path, tag, attr=on)
    if "state" not in role:
        return
    state = role["state"]
    # No two verbs record one slot (`validate_widget_state_relations`), so one does.
    if not any(
        spec["unit"] == "widget"
        and spec.get("record") == {"kind": "value", "attr": state}
        for _, spec in state_specs(entry)
    ):
        raise registry_error("work-state", path, tag, attr=state)
    admitted = json_validator(properties[state])
    for key in ("done", "stopped", "running", "retired"):
        if refused := [
            value for value in role.get(key, ()) if not admitted.is_valid(value)
        ]:
            raise registry_error(
                "work-value", path, tag, key=key, attr=state, values=refused
            )
