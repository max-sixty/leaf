"""Widget state, record, and retirement contract validation."""

from leaf.schema import ELEMENT_ID

from .contract import (
    CREATED_CHILDREN_DETAIL_SCHEMA,
    RegistryError,
    declares_string,
    json_validator,
    state_specs,
)


def _validate_widget_state_relations(
    tag: str, entry: dict, widgets: dict, path
) -> None:
    # A facet is one independently standing fact. Every way of stating that
    # fact therefore agrees on what it folds over and how authored markup can
    # record it. The name itself remains local to the tag: two widget families
    # may both call a facet `status` without sharing a contract.
    facet_specs: dict[str, tuple[str, str, dict | None]] = {}
    for channel, verb, spec in state_specs(entry):
        facet = spec["facet"]
        previous = facet_specs.get(facet)
        if previous is None:
            facet_specs[facet] = (channel, verb, spec.get("record"))
            continue
        previous_channel, previous_verb, previous_record = previous
        previous_spec = entry[previous_channel][previous_verb]
        if spec["unit"] != previous_spec["unit"]:
            raise RegistryError(
                f"{path}: <{tag}> {channel} verb `{verb}` and "
                f"{previous_channel} verb `{previous_verb}` share facet "
                f"`{facet}` but declare different fold units "
                f"(`{spec['unit']}` and `{previous_spec['unit']}`)"
            )
        if spec.get("record") != previous_record:
            raise RegistryError(
                f"{path}: <{tag}> {channel} verb `{verb}` and "
                f"{previous_channel} verb `{previous_verb}` share facet "
                f"`{facet}` but do not declare identical record forms "
                "(or both remain recordless)"
            )

    # Eligibility reuses the one awaiting projection. Close the target relation here:
    # self and every permitted holder must declare a local decision or aggregate-only
    # rollup. Runtime evaluators then neither guess a widget family nor maintain a
    # second representation of whether descendant reader work remains open.
    for verb, spec in entry.get("x-state", {}).items():
        creates = spec.get("creates")
        if creates:
            field = creates["field"]
            detail = spec["detail"]
            fields = detail.get("properties", {})
            if fields.get(field) != CREATED_CHILDREN_DETAIL_SCHEMA:
                raise RegistryError(
                    f"{path}: <{tag}> x-state verb `{verb}` creates through "
                    f"detail field `{field}`, which must be the canonical non-empty "
                    "element-id to non-empty string map"
                )
            if field in detail.get("required", []):
                raise RegistryError(
                    f"{path}: <{tag}> x-state verb `{verb}` creates detail field "
                    f"`{field}` must be optional"
                )
            child_tag = creates["child"]
            child = widgets.get(child_tag)
            if child is None:
                raise RegistryError(
                    f"{path}: <{tag}> x-state verb `{verb}` creates unknown child "
                    f"<{child_tag}>"
                )
            if tag not in child.get("x-parent", []):
                raise RegistryError(
                    f"{path}: <{tag}> x-state verb `{verb}` creates <{child_tag}>, "
                    "whose x-parent does not admit the sender"
                )
            if child.get("x-content") != "prose":
                raise RegistryError(
                    f"{path}: <{tag}> x-state verb `{verb}` creates <{child_tag}>, "
                    "which must declare x-content prose"
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

        requirement = spec.get("requires")
        if not requirement:
            continue
        target_tags = (
            [tag] if requirement["target"] == "self" else entry.get("x-parent", [])
        )
        if not target_tags:
            raise RegistryError(
                f"{path}: <{tag}> x-state verb `{verb}` requires its parent, "
                f"but <{tag}> declares no x-parent"
            )
        if not all(
            widgets[target].get("x-awaits") is not None for target in target_tags
        ):
            missing = sorted(
                target
                for target in target_tags
                if widgets[target].get("x-awaits") is None
            )
            raise RegistryError(
                f"{path}: <{tag}> x-state verb `{verb}` requires "
                f"{requirement['target']} awaiting state, but {missing} do not "
                "declare x-awaits"
            )
        idless = sorted(
            target
            for target in target_tags
            if requirement["target"] == "parent"
            and "id" not in widgets[target].get("required", [])
        )
        if idless:
            raise RegistryError(
                f"{path}: <{tag}> x-state verb `{verb}` requires "
                f"{requirement['target']} awaiting state, but {idless} do not "
                "require an id"
            )
    # A facet is semantic, but its record writes a physical slot. Body and
    # position have one per unit; value and attribute-set are keyed by attr.
    physical_slots: dict[tuple[str, str, str | None], tuple[str, str, str]] = {}
    for channel, verb, spec in state_specs(entry):
        record = spec.get("record")
        if record is None:
            continue
        kind = record["kind"]
        attr = record.get("attr")
        key = spec["unit"], kind, attr
        previous = physical_slots.setdefault(key, (channel, verb, spec["facet"]))
        previous_channel, previous_verb, previous_facet = previous
        if previous_facet == spec["facet"]:
            continue
        slot = kind + (f" `{attr}`" if attr else "")
        raise RegistryError(
            f"{path}: <{tag}> {channel} verb `{verb}` (facet "
            f"`{spec['facet']}`) and {previous_channel} verb "
            f"`{previous_verb}` (facet `{previous_facet}`) claim the "
            f"same physical record slot (unit `{spec['unit']}`, "
            f"{slot}); distinct facets must record independently"
        )

    # A resolves-bearing widget has one answer fact. Thread history can outlive
    # the markup that declared its verbs, so both thread builders deliberately
    # fold answers by widget id alone; requiring every action verb on that tag
    # to share the answer facet makes that historical key exact rather than a
    # compatibility approximation.
    state = entry.get("x-state", {})
    resolving = [
        (verb, spec)
        for verb, spec in state.items()
        if "resolves" in spec["detail"].get("properties", {})
    ]
    if resolving:
        answer_verb, answer_spec = resolving[0]
        answer_facet = answer_spec["facet"]
        for verb, spec in state.items():
            if spec["facet"] != answer_facet:
                raise RegistryError(
                    f"{path}: <{tag}> x-state verb `{verb}` uses facet "
                    f"`{spec['facet']}`, but `{answer_verb}` declares "
                    "`resolves`; every x-state verb on a resolves-bearing "
                    f"widget must share its answer facet `{answer_facet}`"
                )


def _validate_widget_record_contracts(
    tag: str,
    entry: dict,
    properties: dict,
    said: set,
    widgets: dict,
    path,
) -> None:
    # One rule set for both channels: x-state and x-report differ in
    # precedence, not in how a verb, its facet, unit, and record hang together.
    for channel, verb, spec in state_specs(entry):
        detail_properties = spec["detail"].get("properties", {})
        required = set(spec["detail"].get("required", []))
        unit = spec["unit"]
        fields = [] if unit == "widget" else [unit]
        record = spec.get("record")
        if record:
            fields.append(record["value"])
            if record["kind"] == "position":
                fields.append(record["order"])
                if record["within"] not in widgets:
                    raise RegistryError(
                        f"{path}: <{tag}> {channel} verb `{verb}` records a "
                        f"position within unknown widget <{record['within']}>"
                    )
                if spec["unit"] == "widget" and record["within"] not in entry.get(
                    "x-parent", []
                ):
                    raise RegistryError(
                        f"{path}: <{tag}> {channel} verb `{verb}` records "
                        f"its own position within <{record['within']}>, which "
                        "its x-parent does not admit"
                    )
            if record["kind"] == "body":
                if entry.get("x-content") != "data":
                    raise RegistryError(
                        f"{path}: <{tag}> {channel} verb `{verb}` records "
                        "its body, so x-content must be data; projection "
                        "states text rather than a prose subtree"
                    )
                nested = sorted(
                    child
                    for child, child_entry in widgets.items()
                    if tag in child_entry.get("x-parent", [])
                )
                if nested:
                    raise RegistryError(
                        f"{path}: <{tag}> {channel} verb `{verb}` records "
                        f"its body but admits nested widgets {nested}; a "
                        "text statement cannot reconstruct their state"
                    )
            if record["kind"] == "value":
                attr = record["attr"]
                if attr not in properties:
                    raise RegistryError(
                        f"{path}: <{tag}> {channel} verb `{verb}` records "
                        f"undeclared attribute `{attr}`"
                    )
                # Projection rebuilds a refused gesture from authored state.
                # A required string value gives every baseline an absolute
                # action detail; absence is represented by an admitted value.
                if attr not in entry.get("required", []):
                    raise RegistryError(
                        f"{path}: <{tag}> {channel} verb `{verb}` records "
                        f"optional attribute `{attr}`; recorded state must be "
                        "required so its authored value can be replayed"
                    )
                # An x-says value is words the reader sees, and the file's
                # reading takes them from the markup — replay writing one
                # would change what the page says while that reading held
                # still, the desync the fence rules exist to prevent.
                if attr in said:
                    raise RegistryError(
                        f"{path}: <{tag}> {channel} verb `{verb}` records "
                        f"x-says attribute `{attr}`, whose value is words "
                        "the reader sees — declared state may not move the "
                        "page's words"
                    )
        # `resolves` is a reserved detail field: thread settlement reads it
        # off every action as "the comment thread this action answers"
        # (build_threads, in both runtimes), so a verb spelling the name
        # means that or is refused here — a widget using it otherwise
        # would settle a thread silently.
        if "resolves" in detail_properties:
            # The reader's channel only. Both thread builders read `resolves`
            # off actions, so the name on a report verb declares an answer
            # nothing gives: the report would fold like any other and settle
            # no thread ever — the feature nobody wired up, which this door
            # exists to turn into an error. A thread is the reader's to close,
            # or an action of theirs; the agent's own way is `leaf resolve`.
            if channel != "x-state":
                raise RegistryError(
                    f"{path}: <{tag}> {channel} verb `{verb}` declares detail "
                    "field `resolves`, a reserved name (the comment thread "
                    "this action answers) — only an x-state verb settles a "
                    "thread, so rename the field"
                )
            if detail_properties["resolves"] != {"type": "string"}:
                raise RegistryError(
                    f"{path}: <{tag}> {channel} verb `{verb}` declares detail "
                    "field `resolves`, a reserved name (the comment thread "
                    'this action answers) — declare it {"type": "string"} or '
                    "rename the field"
                )
            # A thread is answered by the decision, and a decision is a widget
            # instance (x-awaits) — so the answer is absolute across the
            # widget, and both thread builders key the standing answer on
            # the widget id, the one key a log outlives its markup with.
            # A per-part verb answering a thread would fold per part and
            # settle per widget, and the disagreement is invisible: the
            # thread reads right until a second part is acted on. Whoever
            # writes that widget needs a decision per part first, and this is
            # where they find that out.
            if unit != "widget":
                raise RegistryError(
                    f"{path}: <{tag}> {channel} verb `{verb}` answers a "
                    f"comment thread (`resolves`) but folds per `{unit}` — "
                    "a thread is answered by the decision, and a decision is the "
                    "whole widget"
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
                f"{path}: <{tag}> {channel} verb `{verb}` reads detail fields "
                f"its schema {problem}"
            )
        # Undo restores a recorded action from authored markup. That markup
        # can reconstruct exactly the fold unit and the record's value/order;
        # any other required field would make a valid declaration impossible
        # to restore without a widget-specific default hidden in core.
        unrestorable = sorted(required.difference(fields))
        if channel == "x-state" and record and unrestorable:
            raise RegistryError(
                f"{path}: <{tag}> {channel} verb `{verb}` requires detail "
                f"fields {unrestorable} that authored markup cannot restore"
            )
        if unit != "widget" and record and record["kind"] != "position":
            raise RegistryError(
                f"{path}: <{tag}> {channel} verb `{verb}` records per-part "
                "state; only position records support that"
            )

        if unit != "widget" and not declares_string(detail_properties[unit]):
            raise RegistryError(
                f"{path}: <{tag}> {channel} verb `{verb}` fold unit `{unit}` "
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
                        f"{path}: <{tag}> {channel} verb `{verb}` record "
                        f"value `{value}` must be an array of strings"
                    )
            elif record["kind"] == "value":
                # The record reads and writes the attribute, so its detail
                # field speaks the attribute's own schema — one vocabulary,
                # or the log's contract and the markup's drift apart.
                if schema != properties[record["attr"]]:
                    raise RegistryError(
                        f"{path}: <{tag}> {channel} verb `{verb}` record "
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
                        f"{path}: <{tag}> {channel} verb `{verb}` record "
                        f"value `{value}` must be a string or string enum; "
                        "HTML attributes cannot restore another JSON type"
                    )
            elif not declares_string(schema):
                raise RegistryError(
                    f"{path}: <{tag}> {channel} verb `{verb}` record "
                    f"value `{value}` must be a string"
                )
            if record["kind"] == "position":
                order = detail_properties[record["order"]]
                if not (isinstance(order, dict) and order.get("type") == "integer"):
                    raise RegistryError(
                        f"{path}: <{tag}> {channel} verb `{verb}` record "
                        f"order `{record['order']}` counts the unit's "
                        "siblings, so its detail field must be an integer"
                    )


def _validate_widget_retirement(
    tag: str, entry: dict, slots: dict, widgets: dict, path
) -> None:
    # Withdrawal is the author taking an unanswered question back, and the
    # entry says which of its own outcomes that leaves the page in
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
    # Every holder, not the first: a slot that retires on its parent's verb has
    # to retire whichever parent it was written in, or it would be settled under
    # one and undecidable under another.
    for parent in entry["x-parent"]:
        parent_state = widgets[parent].get("x-state", {})
        if retired not in parent_state:
            raise RegistryError(
                f"{path}: <{tag}> x-retired-when `{retired}` is invalid: "
                f"<{parent}> does not declare that x-state verb"
            )
        if parent_state[retired]["unit"] != "widget":
            raise RegistryError(
                f"{path}: <{tag}> x-retired-when `{retired}` must fold by widget"
            )


def _validate_retirement_facets(slots: dict, widgets: dict, path) -> None:
    # A holder's retired slots are halves of one decision; outcomes on different
    # facets could stand at once, leaving no single settlement to render.
    for holder, outcomes in slots.items():
        state = widgets[holder]["x-state"]
        facets = {state[outcome]["facet"] for outcome in outcomes}
        if len(facets) > 1:
            mapping = ", ".join(
                f"`{outcome}` → `{state[outcome]['facet']}`" for outcome in outcomes
            )
            raise RegistryError(
                f"{path}: <{holder}> x-retired-when outcomes span facets "
                f"({mapping}); every retirement outcome for one holder must "
                "share one facet"
            )


def _validate_awaiting_units(widgets: dict, path) -> None:
    # Asked only after the record and retirement gates above have reported their
    # more fundamental structural errors. An answer may record its complete result
    # either on the widget or on a detail-named part: the projection identifies the
    # answer by owner and verb, while its declared coordinate owns durable replay.
    for tag, entry in widgets.items():
        answers = (entry.get("x-awaits") or {}).get("answers", [])
        until = (entry.get("x-awaits") or {}).get("until")
        completion_verbs = set(answers)
        if until:
            completion_verbs.add(until["verb"])
        declared_conditions = {
            verb: spec["completion"]
            for verb, spec in entry.get("x-state", {}).items()
            if spec.get("completion")
        }
        if non_answers := sorted(set(declared_conditions) - completion_verbs):
            raise RegistryError(
                f"{path}: <{tag}> x-state verbs {non_answers} declare completion "
                "conditions but are not x-awaits completion verbs"
            )
        # A widget-scoped answer is itself the whole Decision's value. A part-scoped
        # answer needs the predicate that lifts one part record to that whole-widget
        # meaning; without it the first part action would answer the Decision.
        if unanchored := sorted(
            verb
            for verb in completion_verbs
            if entry["x-state"][verb]["unit"] != "widget"
            and verb not in declared_conditions
        ):
            raise RegistryError(
                f"{path}: <{tag}> x-awaits completion verbs {unanchored} fold on a "
                "part rather than the widget, so each needs a completion condition"
            )
        for verb, completion in declared_conditions.items():
            if entry["x-state"][verb].get("record", {}).get("kind") != "position":
                raise RegistryError(
                    f"{path}: <{tag}> x-state verb `{verb}` completion requires a "
                    "position record"
                )
            empty = completion["empty"]
            within = empty["within"]
            container = widgets.get(within)
            if container is None:
                raise RegistryError(
                    f"{path}: <{tag}> x-state verb `{verb}` completion names "
                    f"unknown container <{within}>"
                )
            if container.get("x-content") != "items":
                raise RegistryError(
                    f"{path}: <{tag}> x-state verb `{verb}` completion names "
                    f"<{within}>, whose x-content is not items"
                )
            properties = container.get("properties", {})
            mutable = {
                spec["record"]["attr"]
                for channel in ("x-state", "x-report")
                for spec in container.get(channel, {}).values()
                if (spec.get("record") or {}).get("kind") == "value"
            }
            for attr, values in empty["when"].items():
                schema = properties.get(attr)
                if schema is None:
                    raise RegistryError(
                        f"{path}: <{tag}> x-state verb `{verb}` completion tests "
                        f"undeclared <{within}> attribute `{attr}`"
                    )
                if attr in mutable:
                    raise RegistryError(
                        f"{path}: <{tag}> x-state verb `{verb}` completion tests "
                        f"mutable <{within}> attribute `{attr}`"
                    )
                for value in values:
                    if errors := sorted(
                        json_validator(schema).iter_errors(value), key=str
                    ):
                        raise RegistryError(
                            f"{path}: <{tag}> x-state verb `{verb}` completion tests "
                            f"<{within}> `{attr}` at {value!r}, which its schema does "
                            f"not admit: {errors[0].message}"
                        )
        self_circular = sorted(
            verb
            for verb in completion_verbs
            if (entry["x-state"][verb].get("requires") or {})
            == {"target": "self", "awaiting": False}
        )
        if self_circular:
            raise RegistryError(
                f"{path}: <{tag}> x-awaits completion verbs {self_circular} "
                "require their own decision to be closed, so they cannot "
                "complete it"
            )
        parent_circular = sorted(
            verb
            for verb in completion_verbs
            if (entry["x-state"][verb].get("requires") or {})
            == {"target": "parent", "awaiting": False}
        )
        aggregate_parents = sorted(
            parent
            for parent in entry.get("x-parent", [])
            if (widgets[parent].get("x-awaits") or {}).get("rollup")
        )
        if parent_circular and aggregate_parents:
            raise RegistryError(
                f"{path}: <{tag}> x-awaits completion verbs {parent_circular} "
                f"require aggregate parents {aggregate_parents} to be closed, "
                "so they cannot complete it"
            )


def retirement_slots(registry: dict) -> dict:
    """holder tag → {outcome verb → the tags that leave the page under it}: every
    holder/slot pair `x-retired-when` relates, the slot naming the outcome and
    `x-parent` the widgets whose decision reaches it. Read out of the merged
    registry rather than known here, so which widgets a decision settles is a
    fact about this page's vocabulary and never a list in the code."""
    slots = {}
    for tag, entry in registry.items():
        if not tag.startswith("lf-") or not entry.get("x-retired-when"):
            continue
        outcome = entry["x-retired-when"]
        for holder in entry["x-parent"]:
            slots.setdefault(holder, {}).setdefault(outcome, []).append(tag)
    return slots
