"""A view of another widget's answer (`x-shows`), such as a board card that stands in
the column of the pick its section holds.

The answer stays its widget's. The widget's `x-awaits.value` verb records it at the
widget's own coordinate whichever view the user changes it in, so a board drop and a
section pick are one fact, undone, refused and retracted as one. A view keeps no fact
of its own about it: an element declaring `x-shows` names the widget in the attribute
`attr` names, and stands in a compound owner whose attribute `value` names the answer
that owner holds. An owner without one holds the views of answers that name no value,
or one no owner beside it holds.

An answer names a value when it is one string: a `value` record's attribute, or the
members an `attribute` record picks when every one of them carries the same
`x-awaits.key`. An empty pick, a member without the key (an option the user wrote in)
or members naming different values name none. The browser's `runtime/shown-answer.js`
reads the same rule, and writes a value back through the widget's own command, which
the door admits under the widget's own declaration.

This module holds the markup to it (`shown_errors`, in every document `page check` and
message admission read): each view stands where its widget's authored answer puts it,
its owner has a sibling for answers that name no value, and every value a sibling
names is one the widget can take. The append door refuses a position move of a view
(`event_contracts.position_record_error`), which would record its place a second time.
A view therefore keeps its authored order among the views and units of its owner:
order would be a fact of the view's own, and a position record also names the owner
it stands in, which the answer decides.

A widget taking several picks is shown by the value they share, and a view answers
it with the members holding the value it was dropped on, replacing the set; the
widget's own completion, such as a `multiple` group's Done, still decides whether the
obligation is answered.

Rejected: an Answer record, or a value field on `lf-ask`, which would move the
answer off the widget that owns its words, options and obligation. A `via` on the
event naming the view, with the door proving the view may send that widget's
command: a value a view sends is one the widget's own declaration admits or refuses
alone, so the field would be bookkeeping no reader needs.
"""

from leaf.findings import Finding
from leaf.projection import recorded_owner
from leaf.registry.schema import json_validator
from leaf.validation.markup import found_at


def shown_widget(rec: dict, registry: dict) -> str | None:
    """The id of the widget whose answer one element shows, or None."""
    shows = (registry.get(rec["tag"]) or {}).get("x-shows")
    return rec["attrs"].get(shows["attr"]) if shows else None


def answer_declaration(entry: dict) -> tuple[dict, str | None] | None:
    """The record of a widget's answer verb and its member key, where a view can show
    it: a `value` record, or an `attribute` record its `x-awaits.key` names members of."""
    awaits = entry.get("x-awaits") or {}
    spec = entry.get("x-state", {}).get(awaits.get("value"), {})
    record = spec.get("record") or {}
    if record.get("kind") == "value":
        return record, None
    if record.get("kind") == "attribute" and awaits.get("key"):
        return record, awaits["key"]
    return None


def named_value(answer, key: str | None, by_id: dict) -> str | None:
    """The value one answer names (module docstring), given its record's value."""
    if key is None:
        return answer if isinstance(answer, str) and answer else None
    values = {(by_id.get(member) or {}).get("attrs", {}).get(key) for member in answer}
    return next(iter(values)) if len(values) == 1 and None not in values else None


def _members(owner: str, record: dict, by_id: dict, registry: dict) -> list[str]:
    return [
        member
        for member in by_id
        if recorded_owner(member, record, by_id, registry) == owner
    ]


def _authored_answer(owner: dict, record: dict, by_id: dict, registry: dict):
    if record["kind"] == "value":
        return owner["attrs"].get(record["attr"])
    return [
        member
        for member in _members(owner["attrs"]["id"], record, by_id, registry)
        if record["attr"] in by_id[member]["attrs"]
    ]


def _takes(owner: dict, entry: dict, record: dict, key, value, by_id, registry) -> bool:
    """Whether a widget's answer can name `value`."""
    if key is None:
        return json_validator(entry["properties"][record["attr"]]).is_valid(value)
    return any(
        by_id[member]["attrs"].get(key) == value
        for member in _members(owner["attrs"]["id"], record, by_id, registry)
    )


def shown_errors(document, registry: dict) -> list[Finding]:
    """Where one document's views disagree with the answers they show.

    A view whose widget is in another document is the reference check's to report
    (`instances.reference_errors`), since only that check reads the page and the
    thread together."""
    by_id = document.by_id
    errors = []
    open_checked = set()
    for rec in document.lf_elements:
        target = shown_widget(rec, registry)
        owner = by_id.get(target) if target else None
        if owner is None:
            continue
        shows = registry[rec["tag"]]["x-shows"]
        entry = registry.get(owner["tag"]) or {}
        declared = answer_declaration(entry)
        named = {"attr": shows["attr"], "target": target}
        if declared is None:
            errors.append(found_at("shows-no-answer", rec, **named))
            continue
        record, key = declared
        place = rec["holder"]
        if place is None:
            continue  # Membership is the structure check's to report.
        siblings = [
            sibling
            for sibling in by_id.values()
            if sibling["tag"] == place["tag"] and sibling["holder"] is place["holder"]
        ]
        if id(place["holder"]) not in open_checked and not any(
            shows["value"] not in sibling["attrs"] for sibling in siblings
        ):
            errors.append(
                found_at(
                    "shows-without-open",
                    rec,
                    **named,
                    place=place["tag"],
                    value_attr=shows["value"],
                )
            )
        open_checked.add(id(place["holder"]))
        for sibling in siblings:
            value = sibling["attrs"].get(shows["value"])
            if value and not _takes(owner, entry, record, key, value, by_id, registry):
                errors.append(
                    found_at(
                        "shows-untakeable",
                        rec,
                        **named,
                        place=sibling["tag"],
                        value=value,
                    )
                )
        answer = named_value(
            _authored_answer(owner, record, by_id, registry), key, by_id
        )
        held = {sibling["attrs"].get(shows["value"]) for sibling in siblings}
        if answer not in held:
            answer = None
        stands = place["attrs"].get(shows["value"]) or None
        if stands != answer:
            errors.append(
                found_at(
                    "shown-elsewhere",
                    rec,
                    rec["attrs"].get("id", ""),
                    **named,
                    place=place["tag"],
                    answer=answer,
                    stands=stands,
                    value_attr=shows["value"],
                )
            )
    return errors
