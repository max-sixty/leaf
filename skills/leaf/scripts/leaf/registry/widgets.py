"""Widget structure and interaction contract validation."""

import re

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from leaf.schema import ATTRIBUTE_KEYS, DATA_SOURCE_NAME, WIDGET_NAME

from .contract import (
    EXTENSION_READER,
    RegistryError,
    declares_string,
    json_validator,
    registry_path,
    state_specs,
    visual_part_attribute,
)
from .state import (
    _validate_widget_record_contracts,
    _validate_widget_retirement,
    _validate_widget_state_relations,
)


def _widget_entries(registry: dict, path) -> dict:
    invalid_names = [
        tag
        for tag in registry
        if not tag.startswith("$") and re.fullmatch(WIDGET_NAME, tag) is None
    ]
    if invalid_names:
        raise RegistryError(f"{path}: invalid registry entry names: {invalid_names}")
    widgets = {tag: entry for tag, entry in registry.items() if tag.startswith("lf-")}
    return widgets


def _validate_widget_schemas(widgets: dict, path) -> None:
    # First validate every entry in isolation. Cross-entry checks run only after this
    # pass, so their result cannot depend on which widget happened to be written first.
    for tag, entry in widgets.items():
        try:
            Draft202012Validator.check_schema(entry)
        except SchemaError as error:
            raise RegistryError(
                f"{path}: <{tag}> is not a valid JSON Schema: {error.message}"
            )
        description = entry.get("description")
        if not isinstance(description, str) or not description.strip():
            raise RegistryError(f"{path}: <{tag}> must carry a non-empty description")
        extensions = {
            key: value for key, value in entry.items() if key.startswith("x-")
        }
        errors = sorted(EXTENSION_READER.iter_errors(extensions), key=str)
        if errors:
            raise RegistryError(
                f"{path}: <{tag}> registry extensions are invalid: {errors[0].message}"
            )
        declared_verbs = [
            *state_specs(entry),
            *(
                ("x-request", verb, spec)
                for verb, spec in entry.get("x-request", {}).get("verbs", {}).items()
            ),
        ]
        recorded_attributes = {
            record["attr"]
            for _channel, _verb, spec in state_specs(entry)
            if (record := spec.get("record")) and "attr" in record
        }
        for channel, verb, spec in declared_verbs:
            try:
                Draft202012Validator.check_schema(spec["detail"])
            except SchemaError as error:
                raise RegistryError(
                    f"{path}: <{tag}> {channel} verb `{verb}` has an invalid "
                    f"detail schema: {error.message}"
                )
            if spec["detail"].get("type") != "object":
                raise RegistryError(
                    f"{path}: <{tag}> {channel} verb `{verb}` detail schema "
                    "must declare an object"
                )
            # A verb carries only the detail keys its entry declares — the
            # premise the layer's own field meanings rest on: both runtimes
            # dispatch thread settlement on `resolves` being present, which
            # is safe exactly because a closed schema makes carrying it a
            # declaration.
            if spec["detail"].get("additionalProperties") is not False:
                raise RegistryError(
                    f"{path}: <{tag}> {channel} verb `{verb}` detail schema "
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
                    f"{path}: <{tag}> {channel} verb `{verb}` detail schema "
                    f"declares {beyond}; a detail states its type, properties, "
                    "required and additionalProperties and nothing else, so the "
                    "keys a verb can carry are the ones it names"
                )
            if channel == "x-request":
                detail_properties = spec["detail"].get("properties", {})
                required = set(spec["detail"].get("required", []))
                widget_properties = entry.get("properties", {})
                for field, attribute in spec.get("bind", {}).items():
                    if field not in detail_properties or field not in required:
                        raise RegistryError(
                            f"{path}: <{tag}> x-request verb `{verb}` binds detail "
                            f"field `{field}`, but that field is not declared and "
                            "required"
                        )
                    if not declares_string(detail_properties[field]):
                        raise RegistryError(
                            f"{path}: <{tag}> x-request verb `{verb}` binds detail "
                            f"field `{field}`, which must be a string"
                        )
                    attribute_schema = widget_properties.get(attribute, {})
                    if attribute_schema.get("type") != "string":
                        raise RegistryError(
                            f"{path}: <{tag}> x-request verb `{verb}` binds `{field}` "
                            f"to `{attribute}`, which is not a declared string attribute"
                        )
                    if attribute not in entry.get("required", []):
                        raise RegistryError(
                            f"{path}: <{tag}> x-request verb `{verb}` binds `{field}` "
                            f"to `{attribute}`, which is not a required authored attribute"
                        )
                    if attribute in recorded_attributes:
                        raise RegistryError(
                            f"{path}: <{tag}> x-request verb `{verb}` binds `{field}` "
                            f"to `{attribute}`, which is written by x-state or x-report"
                        )
            if update := spec.get("update"):
                detail = spec["detail"]
                field = detail.get("properties", {}).get(update)
                if field is None:
                    raise RegistryError(
                        f"{path}: <{tag}> {channel} verb `{verb}` update field "
                        f"`{update}` is not declared by its detail schema"
                    )
                if update not in detail.get("required", []):
                    raise RegistryError(
                        f"{path}: <{tag}> {channel} verb `{verb}` update field "
                        f"`{update}` must be required — every report in the feed "
                        "needs words"
                    )
                if not declares_string(field):
                    raise RegistryError(
                        f"{path}: <{tag}> {channel} verb `{verb}` update field "
                        f"`{update}` must be a string"
                    )
                if field.get("minLength", 0) < 1:
                    raise RegistryError(
                        f"{path}: <{tag}> {channel} verb `{verb}` update field "
                        f"`{update}` must set minLength to at least 1"
                    )


def _validate_widget_relations(
    registry: dict, widgets: dict, data: dict, slots: dict, path
) -> None:
    for tag, entry in widgets.items():
        properties, said = _validate_widget_structure(
            tag, entry, registry, widgets, data, path
        )
        awaits, response = _validate_widget_predicates(tag, entry, properties, path)
        _validate_widget_interactions(tag, entry, properties, awaits, response, path)
        _validate_widget_state_relations(tag, entry, widgets, path)
        _validate_widget_record_contracts(tag, entry, properties, said, widgets, path)
        _validate_widget_retirement(tag, entry, slots, widgets, path)


def _validate_widget_structure(
    tag: str, entry: dict, registry: dict, widgets: dict, data: dict, path
) -> tuple[dict, set]:
    if unknown := sorted(set(entry.get("x-parent", [])) - set(widgets)):
        raise RegistryError(f"{path}: <{tag}> x-parent names unknown widgets {unknown}")
    properties = entry.get("properties", {})
    request = entry.get("x-request")
    if request:
        if "id" not in entry.get("required", []):
            raise RegistryError(
                f"{path}: <{tag}> x-request instances are addressable, so the "
                "entry must require an id"
            )
        verbs = set(request["verbs"])
        offered = set()
        for member, attribute in request["offers"].items():
            member_entry = widgets.get(member)
            if member_entry is None:
                raise RegistryError(
                    f"{path}: <{tag}> x-request offers unknown widget <{member}>"
                )
            if tag not in member_entry.get("x-parent", []):
                raise RegistryError(
                    f"{path}: <{tag}> x-request offers <{member}>, but that "
                    "widget does not name it in x-parent"
                )
            attribute_schema = member_entry.get("properties", {}).get(attribute)
            values = (
                attribute_schema.get("enum")
                if isinstance(attribute_schema, dict)
                else None
            )
            if (
                not isinstance(values, list)
                or not values
                or any(not isinstance(value, str) or not value for value in values)
            ):
                raise RegistryError(
                    f"{path}: <{tag}> x-request offer <{member}> `{attribute}` "
                    "must be a non-empty string enum"
                )
            if attribute not in member_entry.get("required", []):
                raise RegistryError(
                    f"{path}: <{tag}> x-request offer <{member}> attribute "
                    f"`{attribute}` must be required"
                )
            if unknown := sorted(set(values) - verbs):
                raise RegistryError(
                    f"{path}: <{tag}> x-request offer <{member}> `{attribute}` "
                    f"names undeclared verbs {unknown}"
                )
            offered.update(values)
        if missing := sorted(verbs - offered):
            raise RegistryError(
                f"{path}: <{tag}> x-request verbs {missing} cannot be offered "
                "by any declared child widget"
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
        if snapshot_attr := spec.get("snapshot"):
            snapshot_schema = properties.get(snapshot_attr, {})
            if (
                not isinstance(snapshot_schema, dict)
                or snapshot_schema.get("type") != "string"
                or snapshot_schema.get("pattern") != "^[1-9][0-9]*$"
            ):
                raise RegistryError(
                    f"{path}: <{tag}> x-data input `{input_name}` snapshot attribute "
                    f"`{snapshot_attr}` must be a positive decimal string"
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
    for role in ("x-awaits", "x-conversation", "x-request"):
        if entry.get(role) is not None and (
            not isinstance(properties.get("id"), dict)
            or properties["id"].get("type") != "string"
        ):
            raise RegistryError(
                f"{path}: <{tag}> {role} instances are addressable, so the "
                "entry must declare a string `id` attribute"
            )
    for key in ATTRIBUTE_KEYS:
        declared = entry.get(key) or ()
        named = {declared} if isinstance(declared, str) else set(declared)
        if unknown := sorted(named - set(properties)):
            raise RegistryError(
                f"{path}: <{tag}> {key} names undeclared attributes {unknown}"
            )
    for attribute, reference in entry.get("x-refers", {}).items():
        via = reference.get("via")
        if via is None:
            continue
        relation = registry_path(registry, via)
        if not isinstance(relation, dict):
            raise RegistryError(
                f"{path}: <{tag}> x-refers `{attribute}` names unknown registry "
                f"map {via!r}"
            )
        predicate = reference["where"]
        matches = [
            target
            for target, declaration in relation.items()
            if target in widgets
            and isinstance(declaration, dict)
            and all(declaration.get(key) == value for key, value in predicate.items())
        ]
        if not matches:
            expected = ", ".join(f"{key}={value!r}" for key, value in predicate.items())
            raise RegistryError(
                f"{path}: <{tag}> x-refers `{attribute}` requires {via} "
                f"where {expected}, but no declared widget matches"
            )
    if part_attribute := visual_part_attribute(entry):
        if not (
            "id" in entry.get("required", [])
            and isinstance(properties.get("id"), dict)
            and properties["id"].get("type") == "string"
        ):
            raise RegistryError(
                f"{path}: <{tag}> has addressable visual parts but does not "
                "require a string `id` for their anchor"
            )
        part_schema = properties.get(part_attribute)
        if not (
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
    # A drawing's box is the clip around something drawn at a size of its own, and
    # the theme lays it out as a row so the drawing keeps the column's axis and
    # scrolls only past the room. Every child of that element is an item in the row,
    # so a word the layer writes into it stands beside the drawing rather than over
    # it and takes it off the axis by half the word's width — a picture placed
    # slightly wrong, which nothing else on the page has any way to notice. The
    # widget that has words as well as a drawing is a box, which lays out both.
    # (x-paints is the other kind of word and is not this: it renders into the
    # shared clip, which is positioned out of the flow.)
    if entry.get("x-wide") == "drawing" and said:
        raise RegistryError(
            f"{path}: <{tag}> is x-wide: drawing and says {sorted(said)} — a "
            "drawing's box holds what was drawn and lays out nothing beside it, "
            "so a widget that says an attribute as well declares x-wide: box"
        )
    return properties, said


def _validate_widget_predicates(
    tag: str, entry: dict, properties: dict, path
) -> tuple[dict, dict | None]:
    # A predicate names attributes and values the page can actually carry, or its
    # widget silently disappears from every consumer. The value's kind follows the
    # attribute's own schema — a flag is there or it isn't, an enum admits what it
    # lists — and a subschema that states neither contradicts nothing.
    awaits = entry.get("x-awaits", {})
    request = entry.get("x-request", {})
    if request.get("region") and request.get("decision") is not True:
        raise RegistryError(
            f"{path}: <{tag}> x-request.region requires decision: true — a region "
            "owns the title of a request that joins the reader's Decision projection"
        )
    if request.get("decision") is True and entry.get("x-awaits") is not None:
        raise RegistryError(
            f"{path}: <{tag}> declares both x-request.decision and x-awaits — one "
            "widget cannot own both a lifecycle request and a state decision or rollup"
        )
    if entry.get("x-decision"):
        if "id" not in entry.get("required", []):
            raise RegistryError(f"{path}: <{tag}> x-decision does not require an id")
        if entry.get("x-content") != "prose":
            raise RegistryError(
                f"{path}: <{tag}> x-decision must admit prose around the Decision it frames"
            )
        if awaits:
            raise RegistryError(
                f"{path}: <{tag}> declares both x-decision and x-awaits — the broader "
                "Decision frames one nested decision source; the nested widget owns its state"
            )
        if request.get("decision") is True:
            raise RegistryError(
                f"{path}: <{tag}> declares both x-decision and x-request.decision — the broader "
                "Decision frames one nested external request; the nested widget owns its lifecycle"
            )
    conditions = [
        ("x-awaits", awaits.get("when", {})),
        ("x-awaits", awaits.get("until", {}).get("when", {})),
        ("x-conversation", entry.get("x-conversation", {}).get("when", {})),
        ("x-work", entry.get("x-work", {}).get("when", {})),
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
    conversation = entry.get("x-conversation", {})
    mutable_values = {
        spec["record"]["attr"]
        for channel in ("x-state", "x-report")
        for spec in entry.get(channel, {}).values()
        if (spec.get("record") or {}).get("kind") == "value"
    }
    if dynamic := sorted(set(conversation.get("when", {})) & mutable_values):
        raise RegistryError(
            f"{path}: <{tag}> x-conversation predicate attributes are authored "
            f"and static, but {dynamic} are written by value records"
        )
    response = conversation.get("response")
    if response and (entry.get("x-awaits") is None or awaits.get("rollup")):
        raise RegistryError(
            f"{path}: <{tag}> x-conversation requires a version response but "
            "declares no x-awaits standing decision"
        )
    data_bindings = {
        attr
        for spec in entry.get("x-data", {}).values()
        for attr in (spec["source"], spec.get("snapshot"))
        if attr is not None
    }
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
    return awaits, response


def _validate_widget_interactions(
    tag: str,
    entry: dict,
    properties: dict,
    awaits: dict,
    response: dict | None,
    path,
) -> None:
    work = entry.get("x-work")
    if work and work["seat"] == "content":
        if entry.get("x-inline"):
            raise RegistryError(
                f"{path}: <{tag}> declares a content work seat but is inline; "
                "local work chrome needs a block slot"
            )
        if entry.get("x-content") != "prose":
            raise RegistryError(
                f"{path}: <{tag}> declares a content work seat but x-content is "
                f"{entry.get('x-content')}; generated local chrome may only join "
                "authored prose"
            )
    if work and work["seat"] == "conversation" and not entry.get("x-conversation"):
        raise RegistryError(
            f"{path}: <{tag}> declares a conversation work seat but declares "
            "no x-conversation"
        )
    # A blanket answer is one of this widget's own verbs, so the log records it
    # the way every other decision is recorded.
    answers = awaits.get("answers", [])
    if awaits.get("rollup"):
        local_fields = sorted(set(awaits) - {"rollup"})
        if local_fields:
            raise RegistryError(
                f"{path}: <{tag}> x-awaits rollup also declares local decision "
                f"fields {local_fields}"
            )
    elif entry.get("x-awaits") is not None and not answers:
        raise RegistryError(
            f"{path}: <{tag}> x-awaits local decision declares no answer verbs"
        )
    if unknown := sorted(set(answers) - set(entry.get("x-state", {}))):
        raise RegistryError(
            f"{path}: <{tag}> x-awaits names undeclared answer verbs {unknown}"
        )
    if awaits.get("rollup") and "id" not in entry.get("required", []):
        raise RegistryError(
            f"{path}: <{tag}> x-awaits rollup through descendants does "
            "not require an id"
        )
    if (blanket := awaits.get("all")) and blanket not in entry.get("x-state", {}):
        raise RegistryError(
            f"{path}: <{tag}> x-awaits answers every one at once with "
            f"`{blanket}`, which it does not declare as an x-state verb"
        )
    if blanket and blanket not in answers:
        raise RegistryError(
            f"{path}: <{tag}> x-awaits blanket verb `{blanket}` is not one of "
            "its answer verbs"
        )
    # The until verb closes a thread decision, so it too is one of the widget's own
    # verbs — same rule as `all`, same reason.
    if (until := awaits.get("until")) and until["verb"] not in entry.get("x-state", {}):
        raise RegistryError(
            f"{path}: <{tag}> x-awaits holds decisions open until `{until['verb']}`, "
            "which it does not declare as an x-state verb"
        )
    if response:
        verb = response["verb"]
        if verb not in answers:
            raise RegistryError(
                f"{path}: <{tag}> x-conversation version response names `{verb}`, "
                "which x-awaits does not declare as an answer verb"
            )
        record = entry.get("x-state", {}).get(verb, {}).get("record") or {}
        if record.get("kind") not in {"attribute", "value"}:
            raise RegistryError(
                f"{path}: <{tag}> x-conversation version response verb `{verb}` "
                "has no attribute or value record for a version to change"
            )
    needs_upgrade = [
        key
        for key in (
            "x-state",
            "x-report",
            "x-request",
            "x-language",
            "x-verbatim",
            "x-shadow",
            "x-thread-surface",
            "x-conversation",
        )
        if entry.get(key) and not entry["x-upgrade"]
    ]
    if needs_upgrade:
        raise RegistryError(
            f"{path}: <{tag}> declares {', '.join(needs_upgrade)} "
            "but has no upgraded handler"
        )
    # A version overrules a standing report with `overruled` on the element,
    # so a widget with an agent channel that doesn't declare the attribute is
    # one whose every report contradiction is unpublishable.
    if entry.get("x-report") and not (
        isinstance(properties.get("overruled"), dict)
        and properties["overruled"].get("type") == "boolean"
    ):
        raise RegistryError(
            f"{path}: <{tag}> declares x-report but not the boolean `overruled` "
            "attribute a version overrules a standing report with"
        )
    # The same rule for the other channel: a version that rewrites what a
    # decision rested on must say `restated` on the element ($restated),
    # and a closed schema without the attribute is a widget whose every
    # rewrite is unpublishable — the words gate demands an attribute the
    # widget's own schema refuses. Held only where a verb folds on the
    # widget itself: a verb folding per child (move's "card") rests its
    # decisions on elements this entry doesn't name.
    folds_whole = any(
        spec["unit"] == "widget" for spec in entry.get("x-state", {}).values()
    )
    if folds_whole and not (
        isinstance(properties.get("restated"), dict)
        and properties["restated"].get("type") == "boolean"
    ):
        raise RegistryError(
            f"{path}: <{tag}> declares x-state verbs that fold on the widget "
            "but not the boolean `restated` attribute a version retracts a "
            "decision with"
        )
