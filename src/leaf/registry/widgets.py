"""Widget structure and interaction contract validation."""

from jsonschema.exceptions import SchemaError

from leaf.schema import ATTRIBUTE_FACTS, DECLARATION_SCHEMA, FACT_NEEDS

from .contract import (
    deciding_outcomes,
    deciding_verb,
    declared_fact,
    gathering,
    reference_relation_problem,
    registry_error,
    require_module,
    state_specs,
)
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
    for fact, needs in FACT_NEEDS.items():
        if declared_fact(entry, fact) is None:
            continue
        for need in needs:
            if declared_fact(entry, need) is None:
                raise registry_error("needs-fact", path, tag, fact=fact, needs=need)
    if (
        declared_fact(entry, "words.text-format") == "markdown"
        and declared_fact(entry, "content") != "data"
    ):
        raise registry_error("markdown-needs-data", path, tag)
    # An unbound data widget's <pre> is its one input's text (element-data.js,
    # "Bound values"), so it can feed only one, and none where the <pre> is already
    # the element's words or its recorded state.
    inputs = declared_fact(entry, "data.inputs", {})
    if declared_fact(entry, "content") == "data" and inputs:
        if len(inputs) > 1:
            raise registry_error("data-input", path, tag, reason="inputs")
        if declared_fact(entry, "words.text-format") == "markdown":
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
    properties, said = _validate_widget_structure(
        tag, entry, registry, declarations, data, path
    )
    awaits = _validate_widget_predicates(tag, entry, properties, path)
    _validate_widget_interactions(tag, entry, registry, properties, awaits, path)
    validate_widget_state_relations(tag, entry, declarations, path)
    validate_widget_record_contracts(
        tag, entry, properties, said, registry, declarations, path
    )
    validate_deciding_verb(tag, entry, path)
    validate_widget_retirement(tag, entry, declarations, path)
    _validate_shown_answers(tag, entry, declarations, path)
    validate_answered_conditions(tag, entry, data, declarations, path)


def _typed(properties: dict, attr: str, kind: str) -> bool:
    """Whether the declaration's schema for `attr` is an object naming `kind` as its
    type. JSON Schema admits `true` and `false` as an attribute's schema too, and
    neither names a type."""
    schema = properties.get(attr)
    return isinstance(schema, dict) and schema.get("type") == kind


def _validate_widget_structure(
    tag: str, entry: dict, registry: dict, declarations: dict, data: dict, path
) -> tuple[dict, set]:
    for key, named in (
        ("markup.owners", declared_fact(entry, "markup.owners", [])),
        ("markup.unique", declared_fact(entry, "markup.unique", {}).values()),
    ):
        if unknown := sorted(set(named) - set(declarations)):
            raise registry_error(
                "unknown-declarations", path, tag, key=key, names=unknown
            )
    attributes = entry["attributes"]
    properties = attributes.get("properties", {})
    required = set(attributes.get("required", []))
    layout = declared_fact(entry, "markup.reading-role")
    if layout:
        if declared_fact(entry, "content") != "markup":
            raise registry_error(
                "requires",
                path,
                tag,
                key="markup.reading-role",
                needs="content",
                value="markup",
            )
        if "id" not in required or not _typed(properties, "id", "string"):
            raise registry_error("reading-role-attr", path, tag, role=layout, attr="id")
        if layout == "pane" and (
            "label" not in required or not _typed(properties, "label", "string")
        ):
            raise registry_error(
                "reading-role-attr", path, tag, role="pane", attr="label"
            )
    for input_name, spec in declared_fact(entry, "data.inputs", {}).items():
        contract = spec["contract"]
        source_attr = spec.get("source")
        if contract not in data["contracts"]:
            raise registry_error(
                "data-contract", path, tag, input=input_name, contract=contract
            )
        if source_attr and not _typed(properties, source_attr, "string"):
            raise registry_error(
                "data-source", path, tag, input=input_name, attr=source_attr
            )
    for output_name, spec in declared_fact(entry, "data.outputs", {}).items():
        if spec["contract"] not in data["contracts"]:
            raise registry_error(
                "unknown-output-contract",
                path,
                tag,
                output=output_name,
                contract=spec["contract"],
            )
    for input_name, spec in declared_fact(entry, "data.inputs", {}).items():
        if (reference := spec.get("reference")) and (
            reference not in declared_fact(entry, "markup.refers", {})
            or entry["markup"]["refers"][reference].get("key")
        ):
            raise registry_error(
                "data-reference", path, tag, input=input_name, attr=reference
            )
    # A measured input joins the source's current run to the receipt the authored
    # value was written with, so every element names both.
    for input_name, spec in declared_fact(entry, "data.inputs", {}).items():
        run_attr = spec.get("measured")
        if run_attr is None:
            continue
        source_attr = spec.get("source")
        if source_attr not in required:
            raise registry_error(
                "measured-source", path, tag, input=input_name, attr=source_attr
            )
        run_schema = properties.get(run_attr)
        if not (
            run_attr in required
            and isinstance(run_schema, dict)
            and run_schema.get("type") == "string"
            and run_schema.get("minLength", 0) >= 1
        ):
            raise registry_error(
                "measured-run", path, tag, input=input_name, attr=run_attr
            )
    said = set(declared_fact(entry, "words.says", {}))
    if declared_fact(entry, "server.awaits") is not None and not _typed(
        properties, "id", "string"
    ):
        raise registry_error("addressable-id", path, tag, key="server.awaits")
    for key in ATTRIBUTE_FACTS:
        declared = declared_fact(entry, key) or ()
        named = {declared} if isinstance(declared, str) else set(declared)
        if unknown := sorted(named - set(properties)):
            raise registry_error(
                "undeclared-attributes", path, tag, key=key, names=unknown
            )
    for attribute, reference in declared_fact(entry, "markup.refers", {}).items():
        if problem := reference_relation_problem(reference, registry, declarations):
            code, values = problem
            raise registry_error(code, path, tag, attr=attribute, **values)
    if isinstance(declared_fact(entry, "words.visual"), dict):
        if not ("id" in required and _typed(properties, "id", "string")):
            raise registry_error("visual-id", path, tag)
        part_attribute = entry["words"]["visual"].get("parts")
        if part_attribute and part_attribute not in properties:
            raise registry_error(
                "undeclared-attributes",
                path,
                tag,
                key="words.visual.parts",
                names=[part_attribute],
            )
    return properties, said


def _validate_shown_answers(tag: str, entry: dict, declarations: dict, path) -> None:
    """Hold both sides of a view relation (`shown_answers.py`) to attributes that
    exist. A misnamed one would leave a view that places nothing and an answer no
    view can read, with nothing on the page saying so.

    The view names its widget through a plain reference, and its compound owners
    carry the attribute naming the answer they hold. An answer read by member
    (`server.awaits.key`) is a set of members, which the key names one by one, so the
    key is unique among the members of one widget."""
    if shows := declared_fact(entry, "server.shows"):
        reference = entry["markup"]["refers"].get(shows["attr"])
        if reference is None or reference:
            raise registry_error("shows-reference", path, tag, attr=shows["attr"])
        if lacking := sorted(
            owner
            for owner in entry["markup"]["owners"]
            if shows["value"]
            not in declarations[owner]["attributes"].get("properties", {})
        ):
            raise registry_error(
                "shows-value", path, tag, attr=shows["value"], owners=lacking
            )
    awaits = declared_fact(entry, "server.awaits") or {}
    if key := awaits.get("key"):
        spec = declared_fact(entry, "server.state", {}).get(awaits["value"], {})
        keyed = [
            member
            for member, declaration in declarations.items()
            if declared_fact(declaration, "markup.unique", {}).get(key) == tag
        ]
        if (spec.get("record") or {}).get("kind") != "attribute" or not keyed:
            raise registry_error("awaits-key", path, tag, key=key)


def _validate_widget_predicates(tag: str, entry: dict, properties: dict, path) -> dict:
    # A predicate names declared attributes. Booleans test presence or absence;
    # strings must be values the attribute's schema admits, or the widget silently
    # disappears from every consumer.
    awaits = declared_fact(entry, "server.awaits", {})
    if declared_fact(entry, "server.encloses"):
        if "id" not in entry["attributes"].get("required", []):
            raise registry_error("enclosing-id", path, tag)
        if declared_fact(entry, "content") != "markup":
            raise registry_error("enclosing-prose", path, tag)
    conditions = [
        ("server.awaits", awaits.get("when", {})),
        *(
            ("server.awaits", condition.get("when", {}))
            for condition in awaits.get("answered", {}).values()
        ),
        (
            "server.exhibit",
            entry["server"]["exhibit"]["when"]
            if isinstance(declared_fact(entry, "server.exhibit"), dict)
            else {},
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
        for spec in declared_fact(entry, "data.inputs", {}).values()
        for key in ("source", "reference")
        if key in spec
    }
    if dynamic := sorted(data_bindings & mutable_values):
        raise registry_error("binding-written", path, tag, attrs=dynamic)
    for spec in declared_fact(entry, "data.inputs", {}).values():
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
    if declared_fact(entry, "server.work"):
        if declared_fact(entry, "words.inline"):
            raise registry_error("work-inline", path, tag)
        if declared_fact(entry, "content") != "markup":
            raise registry_error(
                "work-content", path, tag, content=declared_fact(entry, "content")
            )
    answered = awaits.get("answered", {})
    if declared_fact(entry, "server.awaits") is not None and not answered:
        raise registry_error("awaits-unanswered", path, tag)
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
