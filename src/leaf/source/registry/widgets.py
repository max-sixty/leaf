"""Widget structure and interaction contract validation."""

from jsonschema.exceptions import SchemaError

from leaf.base.findings import Finding
from leaf.base.schema import DECLARATION_SCHEMA, INPUT_BINDINGS
from leaf.source.registry.contract import (
    body_is_data,
    deciding_outcomes,
    element_declarations,
    fact_condition,
    gathering,
    registry_error,
    registry_finding,
    require_module,
    state_specs,
)
from leaf.source.registry.kernel import kernel_marks
from leaf.source.registry.schema import check_schema, json_validator, schema_reading
from leaf.source.registry.state import (
    validate_deciding_verb,
    validate_widget_record_contracts,
    validate_widget_retirement,
    validate_widget_state_relations,
)


def validate_widget_schemas(declarations: dict, path) -> None:
    """Hold each declaration on its own to its schemas, refusing with the first
    finding in each. The cross-declaration checks wait for this pass, so their
    result cannot depend on which widget happened to be written first."""
    with gathering() as unit:
        for tag, entry in declarations.items():
            with unit():
                _validate_widget_schema(tag, entry, path)


def _validate_widget_schema(tag: str, entry: dict, path) -> None:
    errors = sorted(json_validator(DECLARATION_SCHEMA).iter_errors(entry), key=str)
    if errors:
        raise registry_error(
            "invalid-declaration", path, tag, **schema_reading(errors[0])
        )
    try:
        check_schema(entry["attributes"])
    except SchemaError as error:
        raise registry_error(
            "attributes-schema", path, tag, **schema_reading(error)
        ) from error
    # An unbound data widget's <pre> is the text of its `value` input (host/element-data.js,
    # "Bound values"), so it can feed only one, and none where the <pre> is already
    # the element's words or its recorded state. Its other inputs leave the <pre> alone.
    inputs = [
        spec
        for spec in entry.get("inputs", {}).values()
        if spec.get("property") == "value"
    ]
    if body_is_data(entry) and inputs:
        if entry["content"] == "markdown":
            raise registry_error("data-input", path, tag, reason="words")
        if len(inputs) > 1:
            raise registry_error("data-input", path, tag, reason="inputs")
        if any(
            spec.get("record", {}).get("kind") == "body"
            for _, spec in state_specs(entry)
        ):
            raise registry_error("data-input", path, tag, reason="state")
    for verb, spec in state_specs(entry):
        if spec.get("record"):
            continue
        try:
            check_schema(spec["detail"])
        except SchemaError as error:
            raise registry_error(
                "verb-detail-schema", path, tag, verb=verb, **schema_reading(error)
            ) from error


def validate_widget_relations(
    registry: dict, declarations: dict, data: dict, path
) -> None:
    """Hold each declaration to the others and to the layer's facts, refusing with
    the first finding in each. A declaration's checks run in order, each relying on
    the ones before it, and read the others only as their schemas admit them, so
    one declaration's fault doesn't stop another's being checked."""
    with gathering() as unit:
        for tag, entry in declarations.items():
            with unit():
                _validate_widget_relations(
                    tag, entry, registry, declarations, data, path
                )


def _validate_widget_relations(
    tag: str, entry: dict, registry: dict, declarations: dict, data: dict, path
) -> None:
    properties = _validate_widget_structure(
        tag, entry, registry, declarations, data, path
    )
    awaits = _validate_widget_predicates(tag, entry, properties, path)
    _validate_widget_interactions(tag, entry, registry, awaits, path)
    validate_widget_state_relations(tag, entry, declarations, path)
    validate_widget_record_contracts(
        tag, entry, properties, registry, declarations, path
    )
    validate_deciding_verb(tag, entry, path)
    validate_widget_retirement(tag, entry, declarations, path)


def _typed(properties: dict, attr: str, kind: str) -> bool:
    """Whether the declaration's schema for `attr` is an object naming `kind` as its
    type. JSON Schema admits `true` and `false` as an attribute's schema too, and
    neither names a type."""
    schema = properties.get(attr)
    return isinstance(schema, dict) and schema.get("type") == kind


def widget_advice(tag: str, registry: dict, path) -> list[Finding]:
    """What the element declaration of `tag` in `registry`, read with its defaults
    written in, advises its author, each finding naming the file `path`: a data
    input's source attribute not declared a string, which `leaf data`'s own grammar
    still checks; a measured input whose source or run receipt an instance may
    leave out, so that instance is never compared with its source's latest run; and
    a position record whose `within` names no container the declarations place
    at or inside the widget (`_containers`), so a drop of the widget's own members is
    refused at admission. The last is advice, not a refusal, because it can still
    work: a container outside the declared membership may stand in a member's
    markup, and another package may declare the membership that places it."""
    entry = registry[tag]
    properties = entry["attributes"].get("properties", {})
    required = set(entry["attributes"].get("required", []))
    found = []
    members = _members(registry)
    for verb, spec in state_specs(entry):
        record = spec.get("record") or {}
        if record.get("kind") != "position":
            continue
        if record["within"] not in (containers := _containers(tag, registry, members)):
            found.append(
                registry_finding(
                    "position-container",
                    path,
                    tag,
                    verb=verb,
                    within=record["within"],
                    containers=containers,
                )
            )
    for input_name, spec in entry.get("inputs", {}).items():
        source_attr = spec.get("source")
        if source_attr and not _typed(properties, source_attr, "string"):
            found.append(
                registry_finding(
                    "data-source", path, tag, input=input_name, attr=source_attr
                )
            )
        if (run_attr := spec.get("measured")) is None:
            continue
        if source_attr not in required:
            found.append(
                registry_finding(
                    "measured-source", path, tag, input=input_name, attr=source_attr
                )
            )
        run_schema = properties.get(run_attr)
        if not (
            run_attr in required
            and isinstance(run_schema, dict)
            and run_schema.get("type") == "string"
            and run_schema.get("minLength", 0) >= 1
        ):
            found.append(
                registry_finding(
                    "measured-run", path, tag, input=input_name, attr=run_attr
                )
            )
    return found


def _members(registry: dict) -> dict[str, set[str]]:
    """Each tag some declaration names in `owners` → the tags that name it."""
    members: dict[str, set[str]] = {}
    for name, entry in element_declarations(registry).items():
        for owner in entry.get("owners", []):
            members.setdefault(owner, set()).add(name)
    return members


def _containers(tag: str, registry: dict, members: dict) -> list[str]:
    """`tag` and the tags the declarations place inside it through `owners`, at any
    depth, that hold members of their own: where a position record of `tag` can put
    its units. A member that records positions itself is the nearer owner of every
    place beneath it (`projection.recorded_owner`), so the search neither counts nor
    passes it."""
    inside, frontier = set(), [tag]
    while frontier:
        for member in members.get(frontier.pop(), ()):
            if member == tag or member in inside:
                continue
            if any(
                (spec.get("record") or {}).get("kind") == "position"
                for _verb, spec in state_specs(registry[member])
            ):
                continue
            inside.add(member)
            frontier.append(member)
    return sorted(name for name in inside | {tag} if name in members)


def _validate_widget_structure(
    tag: str, entry: dict, registry: dict, declarations: dict, data: dict, path
) -> dict:
    if unknown := sorted(set(entry.get("owners", [])) - set(declarations)):
        raise registry_error(
            "unknown-declarations", path, tag, key="owners", names=unknown
        )
    attributes = entry["attributes"]
    properties = attributes.get("properties", {})
    required = set(attributes.get("required", []))
    layout = entry.get("reading-role")
    if layout:
        if entry.get("content") != "markup":
            raise registry_error(
                "requires",
                path,
                tag,
                key="reading-role",
                needs="content",
                value="markup",
            )
        if "id" not in required:
            raise registry_error("reading-role-attr", path, tag, role=layout, attr="id")
        if "label" not in required or not _typed(properties, "label", "string"):
            raise registry_error(
                "reading-role-attr", path, tag, role=layout, attr="label"
            )
    # `leaf data set` validates a source's value against its contract, so an input
    # that can bind a source names a contract this vocabulary declares. An input that
    # only reads another widget's output matches that output by the contract's name,
    # and the package holding the output declares the contract.
    for input_name, spec in entry.get("inputs", {}).items():
        contract = spec["contract"]
        if "source" in spec and contract not in data["contracts"]:
            raise registry_error(
                "data-contract", path, tag, input=input_name, contract=contract
            )
    for output_name, spec in entry.get("outputs", {}).items():
        if spec["contract"] not in data["contracts"]:
            raise registry_error(
                "unknown-output-contract",
                path,
                tag,
                output=output_name,
                contract=spec["contract"],
            )
    # A `refers` attribute the widget hasn't got leaves the widget out of every pass
    # that reads it, with no error anywhere, so the door refuses it.
    if unknown := sorted(set(entry.get("refers", {})) - set(properties)):
        raise registry_error(
            "undeclared-attributes", path, tag, key="refers", names=unknown
        )
    if isinstance(entry.get("visual"), dict) and "id" not in required:
        raise registry_error("visual-id", path, tag)
    return properties


def _validate_widget_predicates(tag: str, entry: dict, properties: dict, path) -> dict:
    # A predicate names declared attributes. Booleans test presence or absence;
    # strings must be values the attribute's schema admits, or the widget silently
    # disappears from every consumer.
    awaits = entry.get("awaits", {})
    conditions = [
        ("awaits", awaits.get("when", {})),
        *(
            (key, when)
            for key in kernel_marks()
            if (when := fact_condition(entry.get(key))) is not None
        ),
    ]
    for declaration, condition in conditions:
        for attr, values in condition.items():
            if attr not in properties:
                raise registry_error(
                    "predicate-attribute", path, tag, key=declaration, attr=attr
                )
            schema = properties[attr]
            for value in values:
                tested = {"key": declaration, "attr": attr, "value": value}
                # Booleans test presence, just as `contract.matches_when` reads them.
                if isinstance(value, bool):
                    continue
                if errors := sorted(json_validator(schema).iter_errors(value), key=str):
                    raise registry_error(
                        "predicate-schema",
                        path,
                        tag,
                        **tested,
                        **schema_reading(errors[0]),
                    )
    mutable_values = {
        spec["record"]["attr"]
        for _verb, spec in state_specs(entry)
        if (spec.get("record") or {}).get("kind") == "value"
    }
    data_bindings = {
        spec[key]
        for spec in entry.get("inputs", {}).values()
        for key in INPUT_BINDINGS
        if key in spec
    }
    if dynamic := sorted(data_bindings & mutable_values):
        raise registry_error("binding-written", path, tag, attrs=dynamic)
    for spec in entry.get("inputs", {}).values():
        if (run_attr := spec.get("measured")) in mutable_values:
            raise registry_error("run-written", path, tag, attr=run_attr)
    return awaits


def _validate_widget_interactions(
    tag: str, entry: dict, registry: dict, awaits: dict, path
) -> None:
    # The user answers their own obligation, so its answer is a verb the user writes.
    user_verbs = {verb for verb, _spec in state_specs(entry, writer="user")}
    if awaits and awaits["value"] not in user_verbs:
        raise registry_error("awaits-value", path, tag)
    # A retired obligation was asked and has ended, so the flag that retires it has to be
    # one registration already reads as stopping the widget asking.
    retired = awaits.get("retired")
    if retired and awaits.get("when", {}).get(retired) != [False]:
        raise registry_error("awaits-retired", path, tag, flag=retired)
    # A blanket answer is one decision per obligation, taken through the widget's deciding
    # verb, so it names an outcome that verb declares.
    if (blanket := awaits.get("all")) and blanket not in deciding_outcomes(entry):
        raise registry_error("awaits-blanket", path, tag, outcome=blanket)
    require_module(tag, entry, registry, path)
