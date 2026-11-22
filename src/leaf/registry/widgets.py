"""Widget structure and interaction contract validation."""

from jsonschema.exceptions import SchemaError

from leaf.findings import Finding
from leaf.schema import ATTRIBUTE_FACTS, DECLARATION_SCHEMA

from .contract import (
    deciding_outcomes,
    deciding_verb,
    fact_condition,
    gathering,
    reference_relation_problem,
    registry_error,
    registry_finding,
    require_module,
    state_specs,
)
from .kernel import kernel_marks
from .schema import check_schema, json_validator, schema_reading
from .state import (
    validate_answered_conditions,
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
    if entry.get("text-format") == "markdown" and entry.get("content") != "data":
        raise registry_error("markdown-needs-data", path, tag)
    # An unbound data widget's <pre> is its one input's text (element-data.js,
    # "Bound values"), so it can feed only one, and none where the <pre> is already
    # the element's words or its recorded state.
    inputs = entry.get("inputs", {})
    if entry.get("content") == "data" and inputs:
        if len(inputs) > 1:
            raise registry_error("data-input", path, tag, reason="inputs")
        if entry.get("text-format") == "markdown":
            raise registry_error("data-input", path, tag, reason="words")
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
    _validate_widget_interactions(tag, entry, registry, properties, awaits, path)
    validate_widget_state_relations(tag, entry, declarations, path)
    validate_widget_record_contracts(
        tag, entry, properties, registry, declarations, path
    )
    validate_deciding_verb(tag, entry, path)
    validate_widget_retirement(tag, entry, declarations, path)
    validate_answered_conditions(tag, entry, data, declarations, path)


def _typed(properties: dict, attr: str, kind: str) -> bool:
    """Whether the declaration's schema for `attr` is an object naming `kind` as its
    type. JSON Schema admits `true` and `false` as an attribute's schema too, and
    neither names a type."""
    schema = properties.get(attr)
    return isinstance(schema, dict) and schema.get("type") == kind


def widget_advice(tag: str, registry: dict, declarations: dict, path) -> list[Finding]:
    """What the element declaration of `tag` in `registry`, read with its defaults
    written in, advises its author, each finding naming the file `path`: a data
    input's source attribute not declared a string, which `leaf data`'s own grammar
    still checks; a measured input whose source or run receipt an instance may leave
    out, so that instance is never compared with its source's latest run; a widget
    that asks with no string `id` declared, which each instance's own check still
    requires; and a `refers` relation no element in `declarations` can meet, which
    each reference an instance makes still meets or is refused
    (`reference-contract`)."""
    entry = registry[tag]
    properties = entry["attributes"].get("properties", {})
    required = set(entry["attributes"].get("required", []))
    found = []
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
    if entry.get("awaits") is not None and not _typed(properties, "id", "string"):
        found.append(registry_finding("addressable-id", path, tag, key="awaits"))
    for attribute, reference in entry.get("refers", {}).items():
        if problem := reference_relation_problem(reference, registry, declarations):
            code, values = problem
            found.append(registry_finding(code, path, tag, attr=attribute, **values))
    return found


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
        if "id" not in required or not _typed(properties, "id", "string"):
            raise registry_error("reading-role-attr", path, tag, role=layout, attr="id")
        if "label" not in required or not _typed(properties, "label", "string"):
            raise registry_error(
                "reading-role-attr", path, tag, role=layout, attr="label"
            )
    for input_name, spec in entry.get("inputs", {}).items():
        contract = spec["contract"]
        if contract not in data["contracts"]:
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
    for input_name, spec in entry.get("inputs", {}).items():
        if (reference := spec.get("reference")) and reference not in entry.get(
            "refers", {}
        ):
            raise registry_error(
                "data-reference", path, tag, input=input_name, attr=reference
            )
    for key in ATTRIBUTE_FACTS:
        declared = entry.get(key) or ()
        named = {declared} if isinstance(declared, str) else set(declared)
        if unknown := sorted(named - set(properties)):
            raise registry_error(
                "undeclared-attributes", path, tag, key=key, names=unknown
            )
    if isinstance(entry.get("visual"), dict):
        if not ("id" in required and _typed(properties, "id", "string")):
            raise registry_error("visual-id", path, tag)
        part_attribute = entry["visual"].get("parts")
        if part_attribute and part_attribute not in properties:
            raise registry_error(
                "undeclared-attributes",
                path,
                tag,
                key="visual.parts",
                names=[part_attribute],
            )
    return properties


def _validate_widget_predicates(tag: str, entry: dict, properties: dict, path) -> dict:
    # A predicate names declared attributes. Booleans test presence or absence;
    # strings must be values the attribute's schema admits, or the widget silently
    # disappears from every consumer.
    awaits = entry.get("awaits", {})
    conditions = [
        ("awaits", awaits.get("when", {})),
        *(
            ("awaits", condition.get("when", {}))
            for condition in awaits.get("answered", {}).values()
        ),
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
        for key in ("source", "reference")
        if key in spec
    }
    if dynamic := sorted(data_bindings & mutable_values):
        raise registry_error("binding-written", path, tag, attrs=dynamic)
    for spec in entry.get("inputs", {}).values():
        if (run_attr := spec.get("measured")) in mutable_values:
            raise registry_error("run-written", path, tag, attr=run_attr)
    return awaits


def _validate_widget_interactions(
    tag: str,
    entry: dict,
    registry: dict,
    properties: dict,
    awaits: dict,
    path,
) -> None:
    answered = awaits.get("answered", {})
    # The user answers their own obligation, so only a verb the user writes can answer it.
    user_verbs = {verb for verb, _spec in state_specs(entry, writer="user")}
    if unknown := sorted(set(answered) - user_verbs):
        raise registry_error("awaits-verbs", path, tag, verbs=unknown)
    if awaits and awaits["value"] not in user_verbs:
        raise registry_error("awaits-value", path, tag)
    # A retired obligation was asked and has ended, so the flag that retires it has to be
    # one registration already reads as stopping the widget asking.
    retired = awaits.get("retired")
    if retired and awaits.get("when", {}).get(retired) != [False]:
        raise registry_error("awaits-retired", path, tag, flag=retired)
    # A blanket answer is one decision per obligation, taken through the widget's deciding
    # verb, so it names an outcome that verb declares and the verb answers the obligation.
    if (blanket := awaits.get("all")) and (
        deciding_verb(entry) not in answered or blanket not in deciding_outcomes(entry)
    ):
        raise registry_error("awaits-blanket", path, tag, outcome=blanket)
    require_module(tag, entry, registry, path)
    # A version overrules a report in force with `overruled` on the element,
    # so a widget with an agent-written verb that doesn't declare the attribute
    # is one whose every report contradiction is unpublishable.
    agent_verbs = [verb for verb, _spec in state_specs(entry, writer="agent")]
    if agent_verbs and not _typed(properties, "overruled", "boolean"):
        raise registry_error("unoverruled", path, tag, verbs=agent_verbs)
    # A user decision folded on the widget needs an explicit withdrawal route:
    # `restated` names that intent; ordinary source edits leave the decision in
    # force. Child-folding verbs place it on elements this declaration does not name.
    folds_whole = any(
        spec["unit"] == "widget" for _verb, spec in state_specs(entry, writer="user")
    )
    if folds_whole and not _typed(properties, "restated", "boolean"):
        raise registry_error("unrestated", path, tag)
