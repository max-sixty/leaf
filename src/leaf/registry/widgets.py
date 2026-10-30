"""Widget structure and interaction contract validation."""

from jsonschema.exceptions import SchemaError

from leaf.schema import (
    ATTRIBUTE_KEYS,
    DATA_SOURCE_NAME,
    EXTENSION_SCHEMA,
)

from .contract import (
    deciding_outcomes,
    deciding_verb,
    gathering,
    reference_relation_problem,
    registry_error,
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
    try:
        check_schema(entry)
    except SchemaError as error:
        raise registry_error(
            "declaration-schema", path, tag, **schema_reading(error)
        ) from error
    description = entry.get("description")
    if not isinstance(description, str) or not description.strip():
        raise registry_error("no-description", path, tag)
    extensions = {key: value for key, value in entry.items() if key.startswith("x-")}
    errors = sorted(json_validator(EXTENSION_SCHEMA).iter_errors(extensions), key=str)
    if errors:
        raise registry_error(
            "invalid-extensions", path, tag, **schema_reading(errors[0])
        )
    if entry.get("x-text-format") == "markdown" and entry.get("x-content") != "data":
        raise registry_error("markdown-needs-data", path, tag)
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
    _validate_widget_interactions(tag, entry, properties, awaits, path)
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
        ("x-owners", entry.get("x-owners", [])),
        ("x-unique", entry.get("x-unique", {}).values()),
        ("x-within", entry.get("x-within", [])),
    ):
        if unknown := sorted(set(named) - set(declarations)):
            raise registry_error(
                "unknown-declarations", path, tag, key=key, names=unknown
            )
    properties = entry.get("properties", {})
    layout = entry.get("x-reading-role")
    if layout:
        if entry.get("x-content") != "markup":
            raise registry_error(
                "requires",
                path,
                tag,
                key="x-reading-role",
                needs="x-content",
                value="markup",
            )
        required = set(entry.get("required", []))
        if "id" not in required or not _typed(properties, "id", "string"):
            raise registry_error("reading-role-attr", path, tag, role=layout, attr="id")
        if layout == "pane" and (
            "label" not in required or not _typed(properties, "label", "string")
        ):
            raise registry_error(
                "reading-role-attr", path, tag, role="pane", attr="label"
            )
    for input_name, spec in entry.get("x-data", {}).items():
        contract = spec["contract"]
        source_attr = spec.get("source")
        if contract not in data["contracts"]:
            raise registry_error(
                "data-contract", path, tag, input=input_name, contract=contract
            )
        source_schema = properties.get(source_attr, {})
        if source_attr and (
            not isinstance(source_schema, dict)
            or source_schema.get("type") != "string"
            or source_schema.get("pattern") != f"^{DATA_SOURCE_NAME}$"
        ):
            raise registry_error(
                "data-source", path, tag, input=input_name, attr=source_attr
            )
    for output_name, spec in entry.get("x-output", {}).items():
        if spec["contract"] not in data["contracts"]:
            raise registry_error(
                "unknown-output-contract",
                path,
                tag,
                output=output_name,
                contract=spec["contract"],
            )
    for input_name, spec in entry.get("x-data", {}).items():
        if (reference := spec.get("reference")) and (
            reference not in entry.get("x-refers", {})
            or entry["x-refers"][reference].get("key")
        ):
            raise registry_error(
                "data-reference", path, tag, input=input_name, attr=reference
            )
    if measured := entry.get("x-measured"):
        input_name = measured["input"]
        if input_name not in entry.get("x-data", {}):
            raise registry_error("measured-input", path, tag, input=input_name)
        source_attr = entry["x-data"][input_name].get("source")
        if source_attr not in entry.get("required", []):
            raise registry_error(
                "measured-source", path, tag, input=input_name, attr=source_attr
            )
        run_attr = measured["run"]
        run_schema = properties.get(run_attr)
        if not (
            run_attr in entry.get("required", [])
            and isinstance(run_schema, dict)
            and run_schema.get("type") == "string"
            and run_schema.get("minLength", 0) >= 1
        ):
            raise registry_error("measured-run", path, tag, attr=run_attr)
    said = set(entry.get("x-says", {}))
    for role in ("x-awaits", "x-thread-seat"):
        if entry.get(role) is not None and not _typed(properties, "id", "string"):
            raise registry_error("addressable-id", path, tag, key=role)
    for key in ATTRIBUTE_KEYS:
        declared = entry.get(key) or ()
        named = {declared} if isinstance(declared, str) else set(declared)
        if unknown := sorted(named - set(properties)):
            raise registry_error(
                "undeclared-attributes", path, tag, key=key, names=unknown
            )
    for attribute, reference in entry.get("x-refers", {}).items():
        if problem := reference_relation_problem(reference, registry, declarations):
            code, values = problem
            raise registry_error(code, path, tag, attr=attribute, **values)
    if isinstance(entry.get("x-visual"), dict):
        if not (
            "id" in entry.get("required", []) and _typed(properties, "id", "string")
        ):
            raise registry_error("visual-id", path, tag)
        part_attribute = entry["x-visual"].get("parts")
        if part_attribute and part_attribute not in properties:
            raise registry_error(
                "undeclared-attributes",
                path,
                tag,
                key="x-visual.parts",
                names=[part_attribute],
            )
        if not entry["x-upgrade"]:
            raise registry_error("visual-upgrade", path, tag)
    return properties, said


def _validate_shown_answers(tag: str, entry: dict, declarations: dict, path) -> None:
    """Hold both sides of a view relation (`shown_answers.py`) to attributes that
    exist. A misnamed one would leave a view that places nothing and an answer no
    view can read, with nothing on the page saying so.

    The view names its widget through a plain reference, and its compound owners
    carry the attribute naming the answer they hold. An answer read by member
    (`x-awaits.key`) is a set of members, which the key names one by one, so the
    key is unique among the members of one widget."""
    if shows := entry.get("x-shows"):
        reference = entry["x-refers"].get(shows["attr"])
        if reference is None or reference:
            raise registry_error("shows-reference", path, tag, attr=shows["attr"])
        if lacking := sorted(
            owner
            for owner in entry["x-owners"]
            if shows["value"] not in declarations[owner].get("properties", {})
        ):
            raise registry_error(
                "shows-value", path, tag, attr=shows["value"], owners=lacking
            )
    awaits = entry.get("x-awaits") or {}
    if key := awaits.get("key"):
        spec = entry.get("x-state", {}).get(awaits["value"], {})
        keyed = [
            member
            for member, declared in declarations.items()
            if declared.get("x-unique", {}).get(key) == tag
        ]
        if (spec.get("record") or {}).get("kind") != "attribute" or not keyed:
            raise registry_error("awaits-key", path, tag, key=key)


def _validate_widget_predicates(tag: str, entry: dict, properties: dict, path) -> dict:
    # A predicate names declared attributes. Booleans test presence or absence;
    # strings must be values the attribute's schema admits, or the widget silently
    # disappears from every consumer.
    awaits = entry.get("x-awaits", {})
    if entry.get("x-encloses"):
        if "id" not in entry.get("required", []):
            raise registry_error("enclosing-id", path, tag)
        if entry.get("x-content") != "markup":
            raise registry_error("enclosing-prose", path, tag)
    conditions = [
        ("x-awaits", awaits.get("when", {})),
        *(
            ("x-awaits", condition.get("when", {}))
            for condition in awaits.get("answered", {}).values()
        ),
        ("x-thread-seat", entry.get("x-thread-seat", {}).get("when", {})),
        (
            "x-exhibit",
            entry["x-exhibit"]["when"]
            if isinstance(entry.get("x-exhibit"), dict)
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
                # Booleans test presence, just as `obligations.asking` reads them.
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
    thread = entry.get("x-thread-seat", {})
    mutable_values = {
        spec["record"]["attr"]
        for _verb, spec in state_specs(entry)
        if (spec.get("record") or {}).get("kind") == "value"
    }
    if dynamic := sorted(set(thread.get("when", {})) & mutable_values):
        raise registry_error("seat-written", path, tag, attrs=dynamic)
    data_bindings = {
        spec[key]
        for spec in entry.get("x-data", {}).values()
        for key in ("source", "reference")
        if key in spec
    }
    if dynamic := sorted(data_bindings & mutable_values):
        raise registry_error("binding-written", path, tag, attrs=dynamic)
    if (measured := entry.get("x-measured")) and measured["run"] in mutable_values:
        raise registry_error("run-written", path, tag, attr=measured["run"])
    return awaits


def _validate_widget_interactions(
    tag: str,
    entry: dict,
    properties: dict,
    awaits: dict,
    path,
) -> None:
    if entry.get("x-work"):
        if entry.get("x-inline"):
            raise registry_error("work-inline", path, tag)
        if entry.get("x-content") != "markup":
            raise registry_error(
                "work-content", path, tag, content=entry.get("x-content")
            )
    answered = awaits.get("answered", {})
    if entry.get("x-awaits") is not None and not answered:
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
    needs_upgrade = [
        key
        for key in (
            "x-state",
            "x-language",
            "x-verbatim",
            "x-shadow",
            "x-thread-surface",
            "x-thread-seat",
            "x-history",
        )
        if entry.get(key) and not entry["x-upgrade"]
    ]
    if needs_upgrade:
        raise registry_error("needs-upgrade", path, tag, keys=needs_upgrade)
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
