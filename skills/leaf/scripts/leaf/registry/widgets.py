"""Widget structure and interaction contract validation."""

import turbohtml
from jsonschema.exceptions import SchemaError

from leaf.schema import (
    ATTRIBUTE_KEYS,
    DATA_SOURCE_NAME,
    EXTENSION_SCHEMA,
)

from .contract import (
    deciding_outcomes,
    deciding_verb,
    reference_relation_problem,
    registry_error,
    state_specs,
    visual_part_attribute,
)
from .schema import check_schema, json_validator, schema_reading
from .state import (
    validate_deciding_verb,
    validate_widget_record_contracts,
    validate_widget_retirement,
    validate_widget_state_relations,
)


def validate_widget_schemas(declarations: dict, data: dict, path) -> None:
    # First validate every declaration in isolation. Cross-declaration checks run only after this
    # pass, so their result cannot depend on which widget happened to be written first.
    for tag, entry in declarations.items():
        try:
            check_schema(entry)
        except SchemaError as error:
            raise registry_error(
                "declaration-schema", path, tag, **schema_reading(error)
            ) from error
        description = entry.get("description")
        if not isinstance(description, str) or not description.strip():
            raise registry_error("no-description", path, tag)
        extensions = {
            key: value for key, value in entry.items() if key.startswith("x-")
        }
        errors = sorted(
            json_validator(EXTENSION_SCHEMA).iter_errors(extensions), key=str
        )
        if errors:
            raise registry_error(
                "invalid-extensions", path, tag, **schema_reading(errors[0])
            )
        if (
            entry.get("x-text-format") == "markdown"
            and entry.get("x-content") != "data"
        ):
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
            if spec["detail"].get("type") != "object":
                raise registry_error("verb-detail-type", path, tag, verb=verb)
            # A verb carries only the detail keys its declaration names — the
            # premise the layer's own field meanings rest on: both runtimes
            # dispatch thread settlement on `resolves` being present, which
            # is safe exactly because a closed schema makes carrying it a
            # declaration.
            if spec["detail"].get("additionalProperties") is not False:
                raise registry_error("verb-detail-open", path, tag, verb=verb)
            # And nothing beside those four keys, because that clause closes an
            # object only against names `properties` does not match: a
            # `patternProperties` beside it admits a field no declaration
            # spells, and `resolves` is a field — so a per-part verb could come
            # to settle a comment thread with every door that reads the name
            # seeing nothing to read. Each of those doors reads the declaration
            # rather than the event, so one unnamed key makes all of them
            # approximate at once.
            spelled = {"type", "properties", "required", "additionalProperties"}
            if beyond := sorted(set(spec["detail"]) - spelled):
                raise registry_error(
                    "verb-detail-keys", path, tag, verb=verb, keys=beyond
                )


def validate_widget_relations(
    registry: dict, declarations: dict, data: dict, path
) -> None:
    for tag, entry in declarations.items():
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
    if entry.get("x-initial"):
        if not entry["x-upgrade"]:
            raise registry_error(
                "requires", path, tag, key="x-initial", needs="x-upgrade", value=True
            )
        if entry.get("x-prepaint") is not None:
            raise registry_error("initial-and-prepaint", path, tag)
    if (prepaint := entry.get("x-prepaint")) is not None:
        if isinstance(prepaint, dict):
            named = declarations.get(prepaint["as"], {}).get("x-prepaint")
            if not isinstance(named, str):
                raise registry_error("prepaint-as", path, tag, **{"as": prepaint["as"]})
            prepaint = named
        _validate_prepaint(tag, entry, prepaint, path)
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
        if "id" not in required or properties.get("id", {}).get("type") != "string":
            raise registry_error("reading-role-attr", path, tag, role=layout, attr="id")
        if layout == "pane" and (
            "label" not in required
            or properties.get("label", {}).get("type") != "string"
        ):
            raise registry_error(
                "reading-role-attr", path, tag, role="pane", attr="label"
            )
    for input_name, spec in entry.get("x-data", {}).items():
        contract = spec["contract"]
        source_attr = spec["source"]
        if contract not in data["contracts"]:
            raise registry_error(
                "data-contract", path, tag, input=input_name, contract=contract
            )
        source_schema = properties.get(source_attr, {})
        if (
            not isinstance(source_schema, dict)
            or source_schema.get("type") != "string"
            or source_schema.get("pattern") != f"^{DATA_SOURCE_NAME}$"
        ):
            raise registry_error(
                "data-source", path, tag, input=input_name, attr=source_attr
            )
    if measured := entry.get("x-measured"):
        input_name = measured["input"]
        if input_name not in entry.get("x-data", {}):
            raise registry_error("measured-input", path, tag, input=input_name)
        source_attr = entry["x-data"][input_name]["source"]
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
        if entry.get(role) is not None and (
            not isinstance(properties.get("id"), dict)
            or properties["id"].get("type") != "string"
        ):
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
            "id" in entry.get("required", [])
            and isinstance(properties.get("id"), dict)
            and properties["id"].get("type") == "string"
        ):
            raise registry_error("visual-id", path, tag)
        part_attribute = visual_part_attribute(entry)
        part_schema = properties.get(part_attribute)
        if part_attribute and not (
            isinstance(part_schema, dict)
            and part_schema.get("type") == "string"
            and part_schema.get("minLength", 0) >= 1
        ):
            raise registry_error("visual-parts-attr", path, tag, attr=part_attribute)
        if not entry["x-upgrade"]:
            raise registry_error("visual-upgrade", path, tag)
    return properties, said


def _validate_prepaint(tag: str, entry: dict, prepaint: str, path) -> None:
    """Hold an x-prepaint to what delivery can write into every occurrence: one plain
    element that only a module will take out again.

    Delivery and the message path insert its bytes as written, so they must be the
    element the parser reads back, byte for byte: markup the parser would close,
    reorder or drop, such as a root left open, would take in the occurrence's own
    children once inserted, and taking the prepaint out would take those with it. It
    is copied into each occurrence, so an id would repeat; a custom element would
    upgrade as a widget of its own, and a script would run. Delivery owns its
    `data-lf-` marks (`revision_delivery.mark_declared`).
    """
    if entry.get("x-upgrade") is not True:
        raise registry_error("prepaint-upgrade", path, tag)
    nodes = list(turbohtml.parse(prepaint, scripting=True).find("body").children)
    if len(nodes) != 1 or getattr(nodes[0], "html", None) != prepaint:
        raise registry_error("prepaint-shape", path, tag)
    for element in [nodes[0], *nodes[0].find_all(True)]:
        attrs = element.attrs
        if "-" in element.tag or element.tag in ("script", "style", "template", "slot"):
            raise registry_error("prepaint-element", path, tag, element=element.tag)
        if "id" in attrs or any(name.startswith("data-lf-") for name in attrs):
            raise registry_error("prepaint-marks", path, tag, element=element.tag)


def _validate_widget_predicates(tag: str, entry: dict, properties: dict, path) -> dict:
    # A predicate names attributes and values the page can actually carry, or its
    # widget silently disappears from every consumer. The value's kind follows the
    # attribute's own schema — a flag is there or it isn't, an enum admits what it
    # lists — and a subschema that states neither contradicts nothing.
    awaits = entry.get("x-awaits", {})
    if entry.get("x-ask-context"):
        if "id" not in entry.get("required", []):
            raise registry_error("ask-context-id", path, tag)
        if entry.get("x-content") != "markup":
            raise registry_error("ask-context-prose", path, tag)
    conditions = [
        ("x-awaits", awaits.get("when", {})),
        *(
            ("x-awaits", condition.get("when", {}))
            for condition in awaits.get("answered", {}).values()
        ),
        ("x-thread-seat", entry.get("x-thread-seat", {}).get("when", {})),
    ]
    for declaration, condition in conditions:
        for attr, values in condition.items():
            if attr not in properties:
                raise registry_error(
                    "predicate-attribute", path, tag, key=declaration, attr=attr
                )
            schema = properties[attr]
            declared = schema if isinstance(schema, dict) else {}
            for value in values:
                tested = {"key": declaration, "attr": attr, "value": value}
                if isinstance(value, bool):
                    # A subschema saying neither a type nor an enum contradicts
                    # nothing; one that says either has told us this attribute
                    # carries a value.
                    if declared.get("type") not in (
                        None,
                        "boolean",
                    ) or declared.get("enum"):
                        raise registry_error("predicate-not-flag", path, tag, **tested)
                elif declared.get("type") == "boolean":
                    raise registry_error("predicate-flag", path, tag, **tested)
                if (
                    allowed := declared.get("enum")
                ) is not None and value not in allowed:
                    raise registry_error("predicate-enum", path, tag, **tested)
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
    data_bindings = {spec["source"] for spec in entry.get("x-data", {}).values()}
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
    # The user answers their own ask, so only a verb the user writes can answer it.
    user_verbs = {verb for verb, _spec in state_specs(entry, writer="user")}
    if unknown := sorted(set(answered) - user_verbs):
        raise registry_error("awaits-verbs", path, tag, verbs=unknown)
    if awaits and awaits["value"] not in user_verbs:
        raise registry_error("awaits-value", path, tag)
    # A retired ask was asked and has ended, so the flag that retires it has to be
    # one registration already reads as stopping the widget asking.
    retired = awaits.get("retired")
    if retired and awaits.get("when", {}).get(retired) != [False]:
        raise registry_error("awaits-retired", path, tag, flag=retired)
    # A blanket answer is one decision per ask, taken through the widget's deciding
    # verb, so it names an outcome that verb declares and the verb answers the ask.
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
    if agent_verbs and not (
        isinstance(properties.get("overruled"), dict)
        and properties["overruled"].get("type") == "boolean"
    ):
        raise registry_error("unoverruled", path, tag, verbs=agent_verbs)
    # A user decision folded on the widget needs an explicit withdrawal route:
    # `restated` names that intent; ordinary source edits leave the decision in
    # force. Child-folding verbs place it on elements this declaration does not name.
    folds_whole = any(
        spec["unit"] == "widget" for _verb, spec in state_specs(entry, writer="user")
    )
    if folds_whole and not (
        isinstance(properties.get("restated"), dict)
        and properties["restated"].get("type") == "boolean"
    ):
        raise registry_error("unrestated", path, tag)
