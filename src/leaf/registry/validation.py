"""Complete registry validation orchestration, and the checks of a vocabulary's
layer facts and the declarations beside its elements."""

import hashlib
import json

import jmespath
import turbohtml
from jmespath.exceptions import JMESPathError
from jsonschema.exceptions import SchemaError

from leaf.findings import Finding, note, noted
from leaf.schema import (
    IDIOM_SCHEMA,
    LAYER_FACTS,
)

from .contract import (
    RegistryError,
    element_declarations,
    gathering,
    is_element_name,
    registry_error,
    registry_finding,
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

# The vocabularies this process has validated, by a digest of their content, oldest
# first. Validation is a pure function of the vocabulary, `source` naming it only in a
# rejection, and every page selecting one layer composes the same one: the suite's
# pages, a site build's examples, and a harness's pages each validated it anew, about a
# tenth of a second apiece for the bundled packages. Each keeps what its validation
# advised, which names the source it was first read from.
_VALIDATED: dict[bytes, tuple[Finding, ...]] = {}
_VALIDATED_LIMIT = 16


def validate_registry(registry: dict, source) -> dict:
    """Validate one complete vocabulary, refusing with the first problem in each
    independent unit (`contract.gathering`), and noting what it advises."""
    key = hashlib.blake2b(
        json.dumps(registry, sort_keys=True, separators=(",", ":")).encode(),
        digest_size=16,
    ).digest()
    if (advice := _VALIDATED.get(key)) is None:
        with noted() as said:
            _validate(registry, source)
        advice = _VALIDATED[key] = tuple(said)
        while len(_VALIDATED) > _VALIDATED_LIMIT:
            _VALIDATED.pop(next(iter(_VALIDATED)), None)
    note(*advice)
    return registry


def _validate(registry: dict, path) -> None:
    """The layer facts' shape first, since every later check reads it. Then the
    layer's other facts beside the element declarations, which read nothing of
    each other, and only once every declaration holds alone does each meet the
    others, so a declaration's relations never read another half-validated."""
    check_layer_facts(registry, path)
    declarations = element_declarations(registry)
    with gathering() as unit:
        with unit():
            validate_layer_declarations(registry, path)
        with unit():
            validate_widget_schemas(declarations, path)
            validate_widget_relations(registry, declarations, registry["$data"], path)


def check_layer_facts(registry: dict, path) -> None:
    """Refuse a vocabulary whose shared layer facts depart from `LAYER_FACTS`,
    naming where and how the first departure in each fact does. Each fact is held to
    its own schema, so one that is missing or malformed is named beside every other."""
    findings = []
    for fact, schema in LAYER_FACTS.items():
        reader = json_validator({"properties": {fact: schema}, "required": [fact]})
        if error := min(reader.iter_errors(registry), key=str, default=None):
            findings.append(
                registry_finding("layer-facts", path, **schema_reading(error))
            )
    if findings:
        raise RegistryError(findings)


def validate_layer_declarations(registry: dict, path) -> None:
    """What `LAYER_FACTS` cannot say, in a vocabulary whose facts hold it
    (`check_layer_facts`): each name one fact gives another, each `when` and contract
    `schema` a JSON Schema, each `resources` entry JMESPath, and the idioms. Each
    event kind's clauses, idiom, the languages and each data contract is checked
    independently, and the refusal names the first problem in each
    (`contract.gathering`)."""
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
        note(
            registry_finding(
                "undeclared-event-kind", path, key=key, kind=kind, declared=declared
            )
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
