"""Widget state, record, and retirement contract validation."""

from leaf.schema import ELEMENT_ID

from .contract import (
    RegistryError,
    deciding_outcomes,
    deciding_verbs,
    declares_string,
    json_validator,
    state_specs,
    verb_writer,
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
            detail = spec["detail"]
            unit, words = spec["unit"], creates["words"]
            if unit == "widget" or spec.get("record"):
                raise RegistryError(
                    f"{path}: <{tag}> x-state verb `{verb}` creates a child, so its "
                    "fold unit must name the detail field carrying the child's id "
                    "and it declares no record form"
                )
            expected_fields = {
                unit: {"type": "string", "pattern": f"^{ELEMENT_ID}$"},
                words: {"type": "string", "minLength": 1},
            }
            if (
                detail.get("properties") != expected_fields
                or set(detail.get("required", [])) != set(expected_fields)
                or detail.get("additionalProperties") is not False
            ):
                raise RegistryError(
                    f"{path}: <{tag}> x-state verb `{verb}` creates a child, so its "
                    f"detail must be exactly the required element id `{unit}` and "
                    f"the required non-empty words `{words}`"
                )
            child_tag = creates["child"]
            child = declarations.get(child_tag)
            if child is None:
                raise RegistryError(
                    f"{path}: <{tag}> x-state verb `{verb}` creates unknown child "
                    f"<{child_tag}>"
                )
            if tag not in child.get("x-owners", []):
                raise RegistryError(
                    f"{path}: <{tag}> x-state verb `{verb}` creates <{child_tag}>, "
                    "whose x-owners does not admit the sender"
                )
            if child.get("x-content") != "markup":
                raise RegistryError(
                    f"{path}: <{tag}> x-state verb `{verb}` creates <{child_tag}>, "
                    "which must declare x-content markup"
                )
            if set(child.get("required", [])) != {"id"}:
                raise RegistryError(
                    f"{path}: <{tag}> x-state verb `{verb}` creates <{child_tag}>, "
                    "which must require id and no other authored attributes"
                )
            expected_id = {
                "type": "string",
                "pattern": f"^{ELEMENT_ID}$",
            }
            if child.get("properties", {}).get("id") != expected_id:
                raise RegistryError(
                    f"{path}: <{tag}> x-state verb `{verb}` creates <{child_tag}>, "
                    "whose required id must use the canonical element-id schema"
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
        slot = kind + (f" `{attr}`" if attr else "")
        raise RegistryError(
            f"{path}: <{tag}> x-state verbs `{verb}` and "
            f"`{previous_verb}` claim the same physical record slot (unit "
            f"`{spec['unit']}`, {slot}); distinct verbs must record independently"
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
    # widget's own Ask closes, which admission reads off the sending document into
    # the answering action's meaning. On a widget with no local Ask nothing would
    # ever read it, so the name means that or is refused here.
    if "resolves" in properties and not (entry.get("x-awaits") or {}).get("answered"):
        raise RegistryError(
            f"{path}: <{tag}> declares attribute `resolves`, a reserved name (the "
            "thread an answer to its Ask closes), but originates no local Ask"
        )
    # One rule set for both writers: they differ in who sends the state, not in
    # how a verb, its unit, and record hang together.
    for verb, spec in state_specs(entry):
        detail_properties = spec["detail"].get("properties", {})
        required = set(spec["detail"].get("required", []))
        unit = spec["unit"]
        fields = [] if unit == "widget" else [unit]
        record = spec.get("record")
        if record:
            fields.append(record["value"])
            if record["kind"] == "position":
                fields.append(record["rank"])
                if record["within"] not in declarations:
                    raise RegistryError(
                        f"{path}: <{tag}> x-state verb `{verb}` records a "
                        f"position within unknown widget <{record['within']}>"
                    )
                # A rank is read between the unit's neighbours, which only the
                # widget holding the container has; a node cannot place itself.
                if unit == "widget":
                    raise RegistryError(
                        f"{path}: <{tag}> x-state verb `{verb}` records a "
                        "position, so its unit must be the part it places, "
                        "not the widget"
                    )
            if record["kind"] == "body":
                if entry.get("x-content") != "data":
                    raise RegistryError(
                        f"{path}: <{tag}> x-state verb `{verb}` records "
                        "its body, so x-content must be data; projection "
                        "states text rather than a prose subtree"
                    )
                nested = sorted(
                    child
                    for child, child_entry in declarations.items()
                    if tag in child_entry.get("x-owners", [])
                )
                if nested:
                    raise RegistryError(
                        f"{path}: <{tag}> x-state verb `{verb}` records "
                        f"its body but admits nested widgets {nested}; a "
                        "text statement cannot reconstruct their state"
                    )
            if record["kind"] == "value":
                attr = record["attr"]
                if attr not in properties:
                    raise RegistryError(
                        f"{path}: <{tag}> x-state verb `{verb}` records "
                        f"undeclared attribute `{attr}`"
                    )
                # An x-says value is words the user sees, and the file's
                # reading takes them from the markup — replay writing one
                # would change what the page says while that reading held
                # still, the desync the fence rules exist to prevent.
                if attr in said:
                    raise RegistryError(
                        f"{path}: <{tag}> x-state verb `{verb}` records "
                        f"x-says attribute `{attr}`, whose value is words "
                        "the user sees — declared state may not move the "
                        "page's words"
                    )
        undeclared = [field for field in fields if field not in detail_properties]
        optional = [field for field in fields if field not in required]
        if undeclared or optional:
            problem = (
                f"does not declare {undeclared}"
                if undeclared
                else f"does not require {optional}"
            )
            raise RegistryError(
                f"{path}: <{tag}> x-state verb `{verb}` reads detail fields "
                f"its schema {problem}"
            )
        if unit != "widget" and record and record["kind"] != "position":
            raise RegistryError(
                f"{path}: <{tag}> x-state verb `{verb}` records per-part "
                "state; only position records support that"
            )

        if unit != "widget" and not declares_string(detail_properties[unit]):
            raise RegistryError(
                f"{path}: <{tag}> x-state verb `{verb}` fold unit `{unit}` "
                "must be a string"
            )
        if record:
            value = record["value"]
            schema = detail_properties[value]
            # An attribute record names the set of elements wearing it, so its
            # detail field is a list of ids however many the group allows —
            # nothing downstream has to ask which kind of group it came from.
            if record["kind"] == "attribute":
                items = schema.get("items") if isinstance(schema, dict) else None
                if not (
                    isinstance(schema, dict)
                    and schema.get("type") == "array"
                    and isinstance(items, dict)
                    and items.get("type") == "string"
                ):
                    raise RegistryError(
                        f"{path}: <{tag}> x-state verb `{verb}` record "
                        f"value `{value}` must be an array of strings"
                    )
            elif record["kind"] == "value":
                # The record reads and writes the attribute, so its detail
                # field speaks the attribute's own schema — one vocabulary,
                # or the log's contract and the markup's drift apart.
                if schema != properties[record["attr"]]:
                    raise RegistryError(
                        f"{path}: <{tag}> x-state verb `{verb}` record "
                        f"value `{value}` must carry attribute "
                        f"`{record['attr']}`'s own schema"
                    )
                string_enum = (
                    isinstance(schema, dict)
                    and isinstance(schema.get("enum"), list)
                    and bool(schema["enum"])
                    and all(isinstance(value, str) for value in schema["enum"])
                )
                if not (declares_string(schema) or string_enum):
                    raise RegistryError(
                        f"{path}: <{tag}> x-state verb `{verb}` record "
                        f"value `{value}` must be a string or string enum; "
                        "HTML attributes cannot restore another JSON type"
                    )
            elif not declares_string(schema):
                raise RegistryError(
                    f"{path}: <{tag}> x-state verb `{verb}` record "
                    f"value `{value}` must be a string"
                )
            if record["kind"] == "position":
                rank = detail_properties[record["rank"]]
                if not (isinstance(rank, dict) and rank.get("type") == "string"):
                    raise RegistryError(
                        f"{path}: <{tag}> x-state verb `{verb}` record "
                        f"rank `{record['rank']}` holds a rank key, so its "
                        "detail field must be a string"
                    )


def validate_widget_retirement(
    tag: str, entry: dict, slots: dict, declarations: dict, path
) -> None:
    # Withdrawal is the author taking an unanswered question back, and the
    # declaration says which of its own outcomes that leaves the page in
    # (retirable_ids). A verb no slot of this widget retires under would
    # license nothing but the wrapper, so the withdrawal it promises would
    # fail as "ids dropped" on the version that tried it — the misdeclaration
    # is invisible until then, and this is where its author is standing.
    withdrawn = entry.get("x-withdrawn-as")
    if withdrawn is not None and withdrawn not in slots.get(tag, {}):
        raise RegistryError(
            f"{path}: <{tag}> x-withdrawn-as `{withdrawn}` retires none of its "
            "slots; withdrawing it would leave their ids on the page"
        )
    retired = entry.get("x-retired-when")
    if retired is None:
        return
    # Every owner, not the first: a slot that retires under its owner's outcome has
    # to retire whichever owner it was written in, or it would be settled under one
    # and undecidable under another.
    for owner in entry["x-owners"]:
        if retired not in deciding_outcomes(declarations[owner]):
            raise RegistryError(
                f"{path}: <{tag}> x-retired-when `{retired}` is invalid: <{owner}> "
                "declares no deciding x-state verb with that outcome"
            )


def validate_deciding_verb(tag: str, entry: dict, path) -> None:
    # A detail field named `outcome` is reserved: it is the decision an owner's
    # retirable members leave the page under (x-retired-when, x-withdrawn-as). One
    # verb per tag decides, for the whole widget, over a closed set of words.
    deciding = deciding_verbs(entry)
    if len(deciding) > 1:
        raise RegistryError(
            f"{path}: <{tag}> x-state verbs {deciding} all declare detail field "
            "`outcome`, a reserved name only one deciding verb may carry"
        )
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
        raise RegistryError(
            f"{path}: <{tag}> x-state verb `{deciding[0]}` declares detail field "
            "`outcome`, a reserved name: the deciding verb folds by widget, is "
            "written by the user, and requires `outcome` as a string enum"
        )


def validate_answered_conditions(declarations: dict, path) -> None:
    # Asked only after the record and retirement gates above have reported their
    # more fundamental structural errors. Each answering verb's condition reads state
    # the verb itself keeps: a whole-widget value, a standing action, or, for a verb
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
                    raise RegistryError(
                        f"{path}: <{tag}> x-awaits answering verb `{verb}` folds on "
                        "a part rather than the widget, so its condition needs "
                        "`empty`"
                    )
                continue
            if record.get("kind") != "position":
                raise RegistryError(
                    f"{path}: <{tag}> x-awaits answering verb `{verb}` tests an "
                    "empty container but records no position"
                )
            within = empty["within"]
            container = declarations.get(within)
            if container is None:
                raise RegistryError(
                    f"{path}: <{tag}> x-awaits answering verb `{verb}` names "
                    f"unknown container <{within}>"
                )
            if container.get("x-content") != "members":
                raise RegistryError(
                    f"{path}: <{tag}> x-awaits answering verb `{verb}` names "
                    f"<{within}>, whose x-content is not members"
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
                    raise RegistryError(
                        f"{path}: <{tag}> x-awaits answering verb `{verb}` tests "
                        f"undeclared <{within}> attribute `{attr}`"
                    )
                if attr in mutable:
                    raise RegistryError(
                        f"{path}: <{tag}> x-awaits answering verb `{verb}` tests "
                        f"mutable <{within}> attribute `{attr}`"
                    )
                for value in values:
                    if errors := sorted(
                        json_validator(schema).iter_errors(value), key=str
                    ):
                        raise RegistryError(
                            f"{path}: <{tag}> x-awaits answering verb `{verb}` tests "
                            f"<{within}> `{attr}` at {value!r}, which its schema "
                            f"does not admit: {errors[0].message}"
                        )


def retirement_slots(registry: dict) -> dict:
    """owner tag → {outcome verb → the tags that leave the page under it}: every
    owner/member pair `x-retired-when` relates, the member naming the outcome and
    `x-owners` the widgets whose decision reaches it. Read out of the merged
    registry rather than known here, so which widgets a decision settles is a
    fact about this page's vocabulary and never a list in the code."""
    slots = {}
    for tag, entry in registry.items():
        if not tag.startswith("lf-") or not entry.get("x-retired-when"):
            continue
        outcome = entry["x-retired-when"]
        for owner in entry["x-owners"]:
            slots.setdefault(owner, {}).setdefault(outcome, []).append(tag)
    return slots
