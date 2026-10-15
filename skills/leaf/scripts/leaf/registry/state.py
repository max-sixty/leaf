"""Widget state, record, and retirement contract validation."""

from leaf.schema import ELEMENT_ID

from .contract import (
    deciding_outcomes,
    deciding_verbs,
    declares_string,
    registry_error,
    state_specs,
    verb_writer,
)
from .schema import json_validator, schema_reading


def validate_widget_state_relations(
    tag: str, entry: dict, declarations: dict, path
) -> None:
    for verb, spec in state_specs(entry):
        creates = spec.get("creates")
        if creates:
            # The created child is a row of its own: its id is the verb's fold unit,
            # so it stands on its own coordinate, and one detail field carries its
            # words. Anything else the detail carried would be state no reading keeps.
            detail = spec["detail"]
            unit, words = spec["unit"], creates["words"]
            if unit == "widget" or spec.get("record"):
                raise registry_error("creates-unit", path, tag, verb=verb)
            expected_fields = {
                unit: {"type": "string", "pattern": f"^{ELEMENT_ID}$"},
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
            if tag not in child.get("x-owners", []):
                raise registry_error(
                    "creates-owner", path, tag, verb=verb, child=child_tag
                )
            if child.get("x-content") != "markup":
                raise registry_error(
                    "creates-content", path, tag, verb=verb, child=child_tag
                )
            if set(child.get("required", [])) != {"id"}:
                raise registry_error(
                    "creates-required", path, tag, verb=verb, child=child_tag
                )
            expected_id = {
                "type": "string",
                "pattern": f"^{ELEMENT_ID}$",
            }
            if child.get("properties", {}).get("id") != expected_id:
                raise registry_error(
                    "creates-id", path, tag, verb=verb, child=child_tag
                )
            # A creates verb owns id-and-words members, not independent widget
            # owners. Capabilities read from the authored owner inventory cannot
            # be supplied by these members. Presentation-only upgrades are allowed.
            owner_keys = (
                "x-state",
                "x-awaits",
                "x-ask-context",
                "x-work",
                "x-history",
                "x-thread-seat",
                "x-thread-surface",
                "x-data",
                "x-measured",
            )
            owned = [key for key in owner_keys if child.get(key)]
            if isinstance(child.get("x-visual"), dict):
                owned.append("x-visual")
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
    said: set,
    registry: dict,
    declarations: dict,
    path,
) -> None:
    # `resolves` is a reserved attribute: the comment thread an answer to this
    # widget's own ask closes, which admission reads off the sending document into
    # the answering action's meaning. On a widget with no local ask nothing would
    # ever read it, so the name means that or is refused here.
    if "resolves" in properties and not (entry.get("x-awaits") or {}).get("answered"):
        raise registry_error("reserved-resolves", path, tag)
    # One rule set for both writers: they differ in who sends the state, not in
    # how a verb, its unit, and record hang together.
    for verb, spec in state_specs(entry):
        unit = spec["unit"]
        record = spec.get("record")
        if record is None:
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
        expected_unit = "unit" if kind == "position" else "widget"
        if unit != expected_unit:
            raise registry_error(
                "record-unit", path, tag, verb=verb, kind=kind, unit=expected_unit
            )
        if kind == "position" and record["within"] not in declarations:
            raise registry_error(
                "record-within", path, tag, verb=verb, within=record["within"]
            )
        if kind == "body":
            if entry.get("x-content") != "data":
                raise registry_error("body-content", path, tag, verb=verb)
            nested = sorted(
                child
                for child, child_entry in declarations.items()
                if tag in child_entry.get("x-owners", [])
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
            if attr in said:
                raise registry_error("record-says", path, tag, verb=verb, attr=attr)
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
    withdrawn = entry.get("x-withdrawn-as")
    if withdrawn is not None and withdrawn not in deciding_outcomes(entry):
        raise registry_error("withdrawn-as", path, tag, outcome=withdrawn)
    retired = entry.get("x-retired-when")
    if retired is None:
        return
    # Every owner, not the first: a slot that retires under its owner's outcome has
    # to retire whichever owner it was written in, or it would be settled under one
    # and undecidable under another.
    for owner in entry["x-owners"]:
        if retired not in deciding_outcomes(declarations[owner]):
            raise registry_error(
                "retired-when", path, tag, outcome=retired, owner=owner
            )


def validate_deciding_verb(tag: str, entry: dict, path) -> None:
    # A detail field named `outcome` is reserved: it is the decision an owner's
    # retirable members leave the page under (x-retired-when, x-withdrawn-as). One
    # verb per tag decides, for the whole widget, over a closed set of words.
    deciding = deciding_verbs(entry)
    if len(deciding) > 1:
        raise registry_error("deciding-verbs", path, tag, verbs=deciding)
    if not deciding:
        return
    spec = entry["x-state"][deciding[0]]
    schema = spec["detail"]["properties"]["outcome"]
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


def validate_answered_conditions(declarations: dict, path) -> None:
    # Asked only after the record and retirement gates above have reported their
    # more fundamental structural errors. Each answering verb's condition reads state
    # the verb itself keeps: a whole-widget value, an action in force, or, for a verb
    # recording positions, the emptiness of one member container inside the widget.
    for tag, entry in declarations.items():
        for verb, condition in (
            (entry.get("x-awaits") or {}).get("answered", {}).items()
        ):
            spec = entry["x-state"][verb]
            empty = condition.get("empty")
            record = spec.get("record") or {}
            if empty is None:
                if spec["unit"] != "widget":
                    raise registry_error("answering-part", path, tag, verb=verb)
                continue
            if record.get("kind") != "position":
                raise registry_error("answering-position", path, tag, verb=verb)
            within = empty["within"]
            container = declarations.get(within)
            if container is None:
                raise registry_error(
                    "answering-container", path, tag, verb=verb, within=within
                )
            if container.get("x-content") != "members":
                raise registry_error(
                    "answering-members", path, tag, verb=verb, within=within
                )
            properties = container.get("properties", {})
            mutable = {
                spec["record"]["attr"]
                for _verb, spec in state_specs(container)
                if (spec.get("record") or {}).get("kind") == "value"
            }
            for attr, values in empty["when"].items():
                schema = properties.get(attr)
                if schema is None:
                    raise registry_error(
                        "answering-undeclared",
                        path,
                        tag,
                        verb=verb,
                        within=within,
                        attr=attr,
                    )
                if attr in mutable:
                    raise registry_error(
                        "answering-mutable",
                        path,
                        tag,
                        verb=verb,
                        within=within,
                        attr=attr,
                    )
                for value in values:
                    if errors := sorted(
                        json_validator(schema).iter_errors(value), key=str
                    ):
                        raise registry_error(
                            "answering-schema",
                            path,
                            tag,
                            verb=verb,
                            within=within,
                            attr=attr,
                            value=value,
                            **schema_reading(errors[0]),
                        )
