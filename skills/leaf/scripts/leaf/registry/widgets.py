"""Widget structure and interaction contract validation."""

import re

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from leaf.schema import (
    ATTRIBUTE_KEYS,
    DATA_SOURCE_NAME,
    EXTENSION_SCHEMA,
    WIDGET_NAME,
    WIDGET_NAME_RULE,
)

from .contract import (
    RegistryError,
    deciding_outcomes,
    deciding_verb,
    declares_string,
    json_validator,
    reference_relation_error,
    state_specs,
    visual_part_attribute,
)
from .state import (
    validate_deciding_verb,
    validate_widget_record_contracts,
    validate_widget_retirement,
    validate_widget_state_relations,
)


def element_declarations(registry: dict, path) -> dict:
    invalid_names = [
        tag
        for tag in registry
        if not tag.startswith("$") and re.fullmatch(WIDGET_NAME, tag) is None
    ]
    if invalid_names:
        raise RegistryError(
            f"{path}: invalid element declaration names {invalid_names}: "
            f"{WIDGET_NAME_RULE}"
        )
    return {tag: entry for tag, entry in registry.items() if not tag.startswith("$")}


def validate_widget_schemas(declarations: dict, data: dict, path) -> None:
    # First validate every declaration in isolation. Cross-declaration checks run only after this
    # pass, so their result cannot depend on which widget happened to be written first.
    for tag, entry in declarations.items():
        try:
            Draft202012Validator.check_schema(entry)
        except SchemaError as error:
            raise RegistryError(
                f"{path}: <{tag}> is not a valid JSON Schema: {error.message}"
            ) from error
        description = entry.get("description")
        if not isinstance(description, str) or not description.strip():
            raise RegistryError(f"{path}: <{tag}> must carry a non-empty description")
        extensions = {
            key: value for key, value in entry.items() if key.startswith("x-")
        }
        errors = sorted(
            json_validator(EXTENSION_SCHEMA).iter_errors(extensions), key=str
        )
        if errors:
            raise RegistryError(
                f"{path}: <{tag}> registry extensions are invalid: {errors[0].message}"
            )
        for verb, spec in state_specs(entry):
            try:
                Draft202012Validator.check_schema(spec["detail"])
            except SchemaError as error:
                raise RegistryError(
                    f"{path}: <{tag}> x-state verb `{verb}` has an invalid "
                    f"detail schema: {error.message}"
                ) from error
            if spec["detail"].get("type") != "object":
                raise RegistryError(
                    f"{path}: <{tag}> x-state verb `{verb}` detail schema "
                    "must declare an object"
                )
            # A verb carries only the detail keys its declaration names — the
            # premise the layer's own field meanings rest on: both runtimes
            # dispatch thread settlement on `resolves` being present, which
            # is safe exactly because a closed schema makes carrying it a
            # declaration.
            if spec["detail"].get("additionalProperties") is not False:
                raise RegistryError(
                    f"{path}: <{tag}> x-state verb `{verb}` detail schema "
                    "must state additionalProperties: false — a verb carries "
                    "only the detail keys it declares"
                )
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
                raise RegistryError(
                    f"{path}: <{tag}> x-state verb `{verb}` detail schema "
                    f"declares {beyond}; a detail states its type, properties, "
                    "required and additionalProperties and nothing else, so the "
                    "keys a verb can carry are the ones it names"
                )
            if update := spec.get("update"):
                detail = spec["detail"]
                field = detail.get("properties", {}).get(update)
                if field is None:
                    raise RegistryError(
                        f"{path}: <{tag}> x-state verb `{verb}` update field "
                        f"`{update}` is not declared by its detail schema"
                    )
                if update not in detail.get("required", []):
                    raise RegistryError(
                        f"{path}: <{tag}> x-state verb `{verb}` update field "
                        f"`{update}` must be required — every report in the feed "
                        "needs words"
                    )
                if not declares_string(field):
                    raise RegistryError(
                        f"{path}: <{tag}> x-state verb `{verb}` update field "
                        f"`{update}` must be a string"
                    )
                if field.get("minLength", 0) < 1:
                    raise RegistryError(
                        f"{path}: <{tag}> x-state verb `{verb}` update field "
                        f"`{update}` must set minLength to at least 1"
                    )


def validate_widget_relations(
    registry: dict, declarations: dict, data: dict, slots: dict, path
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
        validate_widget_retirement(tag, entry, slots, declarations, path)


def _validate_widget_structure(
    tag: str, entry: dict, registry: dict, declarations: dict, data: dict, path
) -> tuple[dict, set]:
    if unknown := sorted(set(entry.get("x-owners", [])) - set(declarations)):
        raise RegistryError(
            f"{path}: <{tag}> x-owners names unknown element declarations {unknown}"
        )
    properties = entry.get("properties", {})
    layout = entry.get("x-reading-role")
    if layout:
        if entry.get("x-content") != "markup":
            raise RegistryError(
                f"{path}: <{tag}> x-reading-role requires x-content: markup"
            )
        required = set(entry.get("required", []))
        if "id" not in required or properties.get("id", {}).get("type") != "string":
            raise RegistryError(
                f"{path}: <{tag}> x-reading-role {layout} instances require a string id"
            )
        if layout == "pane" and (
            "label" not in required
            or properties.get("label", {}).get("type") != "string"
        ):
            raise RegistryError(
                f"{path}: <{tag}> x-reading-role pane instances require a string label"
            )
    required_members = entry.get("x-required-members", {})
    if required_members and entry.get("x-content") != "members":
        raise RegistryError(
            f"{path}: <{tag}> x-required-members requires x-content: members"
        )
    for member_tag, constraint in required_members.items():
        member = declarations.get(member_tag)
        if member is None:
            raise RegistryError(
                f"{path}: <{tag}> x-required-members names unknown member "
                f"declaration <{member_tag}>"
            )
        if tag not in member.get("x-owners", []):
            raise RegistryError(
                f"{path}: <{tag}> x-required-members names <{member_tag}>, but that member "
                "does not name it in x-owners"
            )
        attribute = constraint["one-each"]
        attribute_schema = member.get("properties", {}).get(attribute, {})
        values = (
            attribute_schema.get("enum") if isinstance(attribute_schema, dict) else None
        )
        if (
            attribute not in member.get("required", [])
            or not isinstance(values, list)
            or not values
            or any(not isinstance(value, str) or not value for value in values)
        ):
            raise RegistryError(
                f"{path}: <{tag}> x-required-members <{member_tag}> one-each `{attribute}` "
                "must name a required, non-empty string enum on the member"
            )
    for input_name, spec in entry.get("x-data", {}).items():
        contract = spec["contract"]
        source_attr = spec["source"]
        if contract not in data["contracts"]:
            raise RegistryError(
                f"{path}: <{tag}> x-data input `{input_name}` names unknown "
                f"contract {contract!r}"
            )
        source_schema = properties.get(source_attr, {})
        if (
            not isinstance(source_schema, dict)
            or source_schema.get("type") != "string"
            or source_schema.get("pattern") != f"^{DATA_SOURCE_NAME}$"
        ):
            raise RegistryError(
                f"{path}: <{tag}> x-data input `{input_name}` source attribute "
                f"`{source_attr}` must be a canonical data source string"
            )
    if measured := entry.get("x-measured"):
        input_name = measured["input"]
        if input_name not in entry.get("x-data", {}):
            raise RegistryError(
                f"{path}: <{tag}> x-measured input `{input_name}` is not one "
                "of its x-data inputs"
            )
        source_attr = entry["x-data"][input_name]["source"]
        if source_attr not in entry.get("required", []):
            raise RegistryError(
                f"{path}: <{tag}> x-measured input `{input_name}` source "
                f"attribute `{source_attr}` must be required"
            )
        at_attr = measured["at"]
        at_schema = properties.get(at_attr)
        if not (
            at_attr in entry.get("required", [])
            and isinstance(at_schema, dict)
            and at_schema.get("type") == "string"
            and at_schema.get("format") == "date-time"
        ):
            raise RegistryError(
                f"{path}: <{tag}> x-measured timestamp attribute `{at_attr}` "
                "must be required and declare a date-time string"
            )
    said = set(entry.get("x-says", {}))
    for role in ("x-awaits", "x-thread-seat"):
        if entry.get(role) is not None and (
            not isinstance(properties.get("id"), dict)
            or properties["id"].get("type") != "string"
        ):
            raise RegistryError(
                f"{path}: <{tag}> {role} instances are addressable, so the "
                "element declaration must declare a string `id` attribute"
            )
    for key in ATTRIBUTE_KEYS:
        declared = entry.get(key) or ()
        named = {declared} if isinstance(declared, str) else set(declared)
        if unknown := sorted(named - set(properties)):
            raise RegistryError(
                f"{path}: <{tag}> {key} names undeclared attributes {unknown}"
            )
    for attribute, reference in entry.get("x-refers", {}).items():
        if error := reference_relation_error(reference, registry, declarations):
            raise RegistryError(f"{path}: <{tag}> x-refers `{attribute}` {error}")
    if isinstance(entry.get("x-visual"), dict):
        if not (
            "id" in entry.get("required", [])
            and isinstance(properties.get("id"), dict)
            and properties["id"].get("type") == "string"
        ):
            raise RegistryError(
                f"{path}: <{tag}> has addressable visual parts but does not "
                "require a string `id` for their anchor"
            )
        part_attribute = visual_part_attribute(entry)
        part_schema = properties.get(part_attribute)
        if part_attribute and not (
            isinstance(part_schema, dict)
            and part_schema.get("type") == "string"
            and part_schema.get("minLength", 0) >= 1
        ):
            raise RegistryError(
                f"{path}: <{tag}> x-visual parts attribute `{part_attribute}` "
                "must be a non-empty string"
            )
        if not entry["x-upgrade"]:
            raise RegistryError(
                f"{path}: <{tag}> declares addressable visual parts but has no "
                "upgraded handler to resolve them"
            )
    return properties, said


def _validate_widget_predicates(tag: str, entry: dict, properties: dict, path) -> dict:
    # A predicate names attributes and values the page can actually carry, or its
    # widget silently disappears from every consumer. The value's kind follows the
    # attribute's own schema — a flag is there or it isn't, an enum admits what it
    # lists — and a subschema that states neither contradicts nothing.
    awaits = entry.get("x-awaits", {})
    if entry.get("x-ask-surface"):
        if "id" not in entry.get("required", []):
            raise RegistryError(f"{path}: <{tag}> x-ask-surface does not require an id")
        if entry.get("x-content") != "markup":
            raise RegistryError(
                f"{path}: <{tag}> x-ask-surface must admit prose around the Ask it frames"
            )
        if awaits:
            raise RegistryError(
                f"{path}: <{tag}> declares both x-ask-surface and x-awaits — the broader "
                "Ask frames one nested source; the nested widget owns its state"
            )
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
                raise RegistryError(
                    f"{path}: <{tag}> {declaration} names undeclared attribute `{attr}`"
                )
            schema = properties[attr]
            declared = schema if isinstance(schema, dict) else {}
            for value in values:
                if isinstance(value, bool):
                    # A subschema saying neither a type nor an enum contradicts
                    # nothing; one that says either has told us this attribute
                    # carries a value.
                    if declared.get("type") not in (
                        None,
                        "boolean",
                    ) or declared.get("enum"):
                        raise RegistryError(
                            f"{path}: <{tag}> {declaration} tests `{attr}` as "
                            f"{str(value).lower()}, but that attribute is not a flag"
                        )
                elif declared.get("type") == "boolean":
                    raise RegistryError(
                        f"{path}: <{tag}> {declaration} tests flag `{attr}` as "
                        f"{value!r}; a flag is there or it isn't"
                    )
                if (
                    allowed := declared.get("enum")
                ) is not None and value not in allowed:
                    raise RegistryError(
                        f"{path}: <{tag}> {declaration} tests `{attr}` at "
                        f"{value!r}, which its own enum does not admit"
                    )
                if errors := sorted(json_validator(schema).iter_errors(value), key=str):
                    raise RegistryError(
                        f"{path}: <{tag}> {declaration} tests `{attr}` at "
                        f"{value!r}, which its own schema does not admit: "
                        f"{errors[0].message}"
                    )
    thread = entry.get("x-thread-seat", {})
    mutable_values = {
        spec["record"]["attr"]
        for _verb, spec in state_specs(entry)
        if (spec.get("record") or {}).get("kind") == "value"
    }
    if dynamic := sorted(set(thread.get("when", {})) & mutable_values):
        raise RegistryError(
            f"{path}: <{tag}> x-thread-seat predicate attributes are authored "
            f"and static, but {dynamic} are written by value records"
        )
    data_bindings = {spec["source"] for spec in entry.get("x-data", {}).values()}
    if dynamic := sorted(data_bindings & mutable_values):
        raise RegistryError(
            f"{path}: <{tag}> x-data binding attributes are authored, "
            f"but {dynamic} are written by value records"
        )
    if (measured := entry.get("x-measured")) and measured["at"] in mutable_values:
        raise RegistryError(
            f"{path}: <{tag}> x-measured timestamp attribute "
            f"`{measured['at']}` is an authored snapshot instant, but is written "
            "by a value record"
        )
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
            raise RegistryError(
                f"{path}: <{tag}> declares x-work but is inline; "
                "local work chrome needs a block slot"
            )
        if entry.get("x-content") != "markup":
            raise RegistryError(
                f"{path}: <{tag}> declares x-work but x-content is "
                f"{entry.get('x-content')}; generated local chrome may only join "
                "authored prose"
            )
    answered = awaits.get("answered", {})
    if entry.get("x-awaits") is not None and not answered:
        raise RegistryError(
            f"{path}: <{tag}> x-awaits local Ask declares no `answered` condition"
        )
    # The user answers their own Ask, so only a verb the user writes can answer it.
    user_verbs = {verb for verb, _spec in state_specs(entry, writer="user")}
    if unknown := sorted(set(answered) - user_verbs):
        raise RegistryError(
            f"{path}: <{tag}> x-awaits answers with verbs {unknown}, which are not "
            "x-state verbs the user writes"
        )
    # A blanket answer is one decision per Ask, taken through the widget's deciding
    # verb, so it names an outcome that verb declares and the verb answers the Ask.
    if (blanket := awaits.get("all")) and (
        deciding_verb(entry) not in answered or blanket not in deciding_outcomes(entry)
    ):
        raise RegistryError(
            f"{path}: <{tag}> x-awaits blanket answer `{blanket}` is not an outcome "
            "of a deciding verb that answers its Ask"
        )
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
            "x-reserve",
        )
        if entry.get(key) and not entry["x-upgrade"]
    ]
    if needs_upgrade:
        raise RegistryError(
            f"{path}: <{tag}> declares {', '.join(needs_upgrade)} "
            "but has no upgraded handler"
        )
    # A version overrules a standing report with `overruled` on the element,
    # so a widget with an agent-written verb that doesn't declare the attribute
    # is one whose every report contradiction is unpublishable.
    agent_verbs = [verb for verb, _spec in state_specs(entry, writer="agent")]
    if agent_verbs and not (
        isinstance(properties.get("overruled"), dict)
        and properties["overruled"].get("type") == "boolean"
    ):
        raise RegistryError(
            f"{path}: <{tag}> declares agent-written x-state verbs {agent_verbs} but "
            "not the boolean `overruled` "
            "attribute a version overrules a standing report with"
        )
    # The same rule for the user's verbs: a version that rewrites what a
    # decision rested on must say `restated` on the element ($restated),
    # and a closed schema without the attribute is a widget whose every
    # rewrite is unpublishable — the words gate demands an attribute the
    # widget's own schema refuses. Held only where a verb folds on the
    # widget itself: a verb folding per child (move's "card") rests its
    # decisions on elements this declaration doesn't name.
    folds_whole = any(
        spec["unit"] == "widget" for _verb, spec in state_specs(entry, writer="user")
    )
    if folds_whole and not (
        isinstance(properties.get("restated"), dict)
        and properties["restated"].get("type") == "boolean"
    ):
        raise RegistryError(
            f"{path}: <{tag}> declares user x-state verbs that fold on the widget "
            "but not the boolean `restated` attribute a version retracts a "
            "decision with"
        )
