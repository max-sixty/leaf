"""Widget state, record, and retirement contract validation."""

from leaf.source.registry.contract import (
    body_is_data,
    deciding_outcomes,
    deciding_verb,
    deciding_verbs,
    declares_string,
    record_unit,
    registry_error,
    state_specs,
    verb_writer,
    withdrawing_outcome,
)


def validate_widget_state_relations(
    tag: str, entry: dict, declarations: dict, path
) -> None:
    for verb, spec in state_specs(entry):
        creates = spec.get("creates")
        if creates:
            # The created child is a row of its own: its id is the verb's fold unit,
            # so it stands on its own coordinate, and one detail field carries its
            # words. Anything else the detail carried would be state no reading keeps.
            # `contract.detail_schema` holds the id field to the element-id grammar.
            detail = spec["detail"]
            unit, words = spec["unit"], creates["words"]
            if unit == "widget" or spec.get("record"):
                raise registry_error("creates-unit", path, tag, verb=verb)
            expected_fields = {
                unit: {"type": "string"},
                words: {"type": "string", "minLength": 1},
            }
            if (
                detail.get("properties") != expected_fields
                or set(detail.get("required", [])) != set(expected_fields)
                or detail.get("additionalProperties") is not False
            ):
                raise registry_error(
                    "creates-detail", path, tag, verb=verb, unit=unit, words=words
                )
            child_tag = creates["child"]
            child = declarations.get(child_tag)
            if child is None:
                raise registry_error(
                    "creates-unknown", path, tag, verb=verb, child=child_tag
                )
            if tag not in child.get("owners", []):
                raise registry_error(
                    "creates-owner", path, tag, verb=verb, child=child_tag
                )
            if child.get("content") != "markup":
                raise registry_error(
                    "creates-content", path, tag, verb=verb, child=child_tag
                )
            # Composition gives the child's id the same grammar
            # (`contract.stamp_grammars`).
            if set(child["attributes"].get("required", [])) != {"id"}:
                raise registry_error(
                    "creates-required", path, tag, verb=verb, child=child_tag
                )
            # A creates verb owns id-and-words members, not independent widget
            # owners. Capabilities read from the authored owner inventory cannot
            # be supplied by these members. Presentation-only upgrades are allowed.
            owner_keys = ("verbs", "awaits", "history", "inputs")
            owned = [key for key in owner_keys if child.get(key)]
            if isinstance(child.get("visual"), dict):
                owned.append("visual")
            if owned:
                raise registry_error(
                    "creates-semantic-owner",
                    path,
                    tag,
                    verb=verb,
                    child=child_tag,
                    keys=owned,
                )

    # Each verb's record writes a physical slot of its own. Body and position have
    # one per unit; value and attribute-set are keyed by attr.
    physical_slots: dict[tuple[str, str, str | None], str] = {}
    for verb, spec in state_specs(entry):
        record = spec.get("record")
        if record is None:
            continue
        kind = record["kind"]
        attr = record.get("attr")
        key = spec["unit"], kind, attr
        previous_verb = physical_slots.setdefault(key, verb)
        if previous_verb == verb:
            continue
        raise registry_error(
            "shared-slot",
            path,
            tag,
            verbs=[verb, previous_verb],
            unit=spec["unit"],
            kind=kind,
            attr=attr,
        )


def validate_widget_record_contracts(
    tag: str,
    entry: dict,
    properties: dict,
    registry: dict,
    declarations: dict,
    path,
) -> None:
    # One rule set for both writers: they differ in who sends the state, not in
    # how a verb, its unit, and record hang together.
    for verb, spec in state_specs(entry):
        unit = spec["unit"]
        record = spec.get("record")
        if record is None:
            if binding := spec.get("contract"):
                fields = spec["detail"].get("properties", {})
                if binding["field"] not in fields or not declares_string(
                    properties.get(binding["attribute"])
                ):
                    raise registry_error(
                        "verb-contract", path, tag, verb=verb, **binding
                    )
            if unit == "widget":
                continue
            detail = spec["detail"]
            if unit not in detail.get("properties", {}) or unit not in detail.get(
                "required", []
            ):
                raise registry_error("unit-undeclared", path, tag, verb=verb, unit=unit)
            if not declares_string(detail["properties"][unit]):
                raise registry_error("unit-type", path, tag, verb=verb, unit=unit)
            continue
        kind = record["kind"]
        if unit != record_unit(record):
            raise registry_error(
                "record-unit", path, tag, verb=verb, kind=kind, unit=record_unit(record)
            )
        # A container is a declared element, which may be the widget itself; whether
        # the declarations place one at or inside the widget is advice
        # (`widgets.widget_advice`).
        if kind == "position" and record["within"] not in declarations:
            raise registry_error(
                "record-within", path, tag, verb=verb, within=record["within"]
            )
        if kind == "body":
            if not body_is_data(entry):
                raise registry_error("body-content", path, tag, verb=verb)
            nested = sorted(
                child
                for child, child_entry in declarations.items()
                if tag in child_entry.get("owners", [])
            )
            if nested:
                raise registry_error(
                    "body-nested", path, tag, verb=verb, widgets=nested
                )
        if kind == "value":
            attr = record["attr"]
            if attr not in properties:
                raise registry_error(
                    "record-undeclared", path, tag, verb=verb, attr=attr
                )
            schema = properties[attr]
            string_enum = (
                isinstance(schema, dict)
                and isinstance(schema.get("enum"), list)
                and bool(schema["enum"])
                and all(isinstance(value, str) for value in schema["enum"])
            )
            if not (declares_string(schema) or string_enum):
                raise registry_error("record-type", path, tag, verb=verb, attr=attr)


def validate_widget_retirement(tag: str, entry: dict, declarations: dict, path) -> None:
    # Withdrawal names a declared deciding outcome; it does not require slots
    # whose historical ids a future revision must retain.
    withdrawn = withdrawing_outcome(entry)
    if withdrawn is not None and withdrawn not in deciding_outcomes(entry):
        raise registry_error(
            "withdraws-outcome",
            path,
            tag,
            verb=deciding_verb(entry),
            outcome=withdrawn,
        )
    retired = entry.get("retired-when")
    if retired is None:
        return
    # Every owner, not the first: a slot that retires under its owner's outcome has
    # to retire whichever owner it was written in, or it would be settled under one
    # and undecidable under another.
    for owner in entry["owners"]:
        if retired not in deciding_outcomes(declarations[owner]):
            raise registry_error(
                "retired-when", path, tag, outcome=retired, owner=owner
            )


def validate_deciding_verb(tag: str, entry: dict, path) -> None:
    # A declared decision selects which members retire. Payload spelling alone
    # gives no other verb this role. One user verb per tag decides, over the widget.
    deciding = deciding_verbs(entry)
    if len(deciding) > 1:
        raise registry_error("deciding-verbs", path, tag, verbs=deciding)
    if not deciding:
        return
    spec = entry["verbs"][deciding[0]]
    schema = spec["detail"].get("properties", {}).get("outcome")
    words = schema.get("enum") if isinstance(schema, dict) else None
    if (
        spec["unit"] != "widget"
        or verb_writer(spec) != "user"
        or not isinstance(words, list)
        or not words
        or not all(isinstance(word, str) for word in words)
        or "outcome" not in spec["detail"].get("required", [])
    ):
        raise registry_error("deciding-verb", path, tag, verb=deciding[0])
