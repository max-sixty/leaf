"""Declaration-driven state and retirement projections."""

from datetime import datetime
from typing import NamedTuple

from leaf.events import (
    action_rests_on,
    action_retracted,
    anchored_ids,
    note_settlements,
    report_settlements,
    retractions,
    taken_back,
)
from leaf.passages import EMPTY, collapse, enclosing_of, spoken
from leaf.registry import retirement_slots, state_specs
from leaf.structure import _StructParser, parse_structure


def _report_updates(projection) -> list[dict]:
    if projection is None:
        return []
    standing = {
        event["id"]
        for entries in projection.reports.values()
        for event, _spec in entries
    }
    effective = {
        event["id"]
        for event, _spec in projection.desired.values()
        if event["kind"] == "report"
    }
    updates = []
    for _coordinate, (event, spec) in projection.classified.values():
        if event["kind"] != "report":
            continue
        update_field = spec.get("update")
        updates.append(
            {
                "id": event["id"],
                "target": {"kind": "widget", "id": event["widget"]},
                "source": "report",
                "action": event["action"],
                "detail": event["detail"],
                "text": event["detail"][update_field] if update_field else None,
                "ts": event["ts"],
                "revision": event["revision"],
                "seq": event["seq"],
                "agent": event.get("agent"),
                "session": event.get("session"),
                "disposition": (
                    "effective"
                    if event["id"] in effective
                    else "standing"
                    if event["id"] in standing
                    else "settled"
                ),
            }
        )
    return updates


def _claim_effective(claim: dict, threads: dict, events: list) -> bool:
    target = claim["target"]
    if target["kind"] == "thread":
        thread = threads.get(target["id"])
        return bool(
            thread
            and not thread["resolved"]
            and not any(
                message["kind"] == "reply"
                and message["author"] == "claude"
                and message["seq"] > claim["log_floor"]
                for message in thread["msgs"]
            )
        )
    return not any(
        event["kind"] == "note"
        and event["seq"] > claim["log_floor"]
        and target["id"] in note_settlements(event, "work")
        for event in events
    )


def _claim_updates(claims: list, threads: dict, events: list) -> list[dict]:
    return [
        {
            **claim,
            "disposition": (
                "effective" if _claim_effective(claim, threads, events) else "settled"
            ),
        }
        for claim in claims
    ]


def _update_order(update: dict) -> tuple:
    return (
        update["seq"] if update["source"] == "report" else update["log_floor"],
        0 if update["source"] == "report" else 1,
        datetime.fromisoformat(update["ts"]),
        update["source"],
        update["target"]["kind"],
        update["target"]["id"],
        update["id"],
    )


def canonical_updates(
    projection,
    claims: list,
    threads: dict,
    events: list,
) -> list[dict]:
    """Normalize projected reports and ephemeral claims into one update feed."""
    return sorted(
        [*_report_updates(projection), *_claim_updates(claims, threads, events)],
        key=_update_order,
    )


def enclosing_widgets(rec: dict):
    """The lf-* elements standing around one, innermost first."""
    rec = rec["holder"]
    while rec is not None:
        yield rec
        rec = rec["holder"]


def enclosing_slot(rec: dict, registry: dict):
    """The innermost slot an element stands in and the widget whose decision
    retires it, or None where it stands in neither. The element itself counts:
    a slot's own id is the slot's, not the widget's around it."""
    for node in (rec, *enclosing_widgets(rec)):
        entry = registry.get(node["tag"]) or {}
        holder = node["holder"]
        if (
            entry.get("x-retired-when")
            and holder
            and holder["tag"] in entry["x-parent"]
        ):
            return node, holder
    return None


def retirement_holders(parser: _StructParser, registry: dict) -> list:
    """Every widget the page carries that a decision can settle, and what each
    outcome would retire: {"id", "tag", "retires": {outcome → ids},
    "withdrawn_as"}. An id belongs to a slot when the slot stands anywhere
    around it, found by walking out of the id rather than down from the widget,
    so a paragraph three elements deep in a slot is read like the slot's own.

    Every outcome the registry declares gets a set, carried in the markup or
    not: a suggestion that only inserts still retires its wrapper when accepted,
    and a structure built from the slots the page happens to hold would have
    nothing to license that with."""
    declared = retirement_slots(registry)
    holders = {}
    for rec in parser.lf_elements:
        wid = rec["attrs"].get("id")
        if wid and rec["tag"] in declared:
            holders[wid] = {
                "id": wid,
                "tag": rec["tag"],
                "retires": {outcome: set() for outcome in declared[rec["tag"]]},
                "withdrawn_as": registry[rec["tag"]].get("x-withdrawn-as"),
            }
    for wid, rec in parser.within.items():
        pair = enclosing_slot(rec, registry) if rec else None
        if pair is None:
            continue
        slot, holder = pair
        held = holders.get(holder["attrs"].get("id"))
        if held is not None:
            held["retires"][registry[slot["tag"]]["x-retired-when"]].add(wid)
    return list(holders.values())


def retirable_ids(
    holders: list, events: list, dropped: set, outcomes: dict, spk: dict
) -> set:
    """Ids the previous version's settled widgets let the next one drop, given
    what it actually dropped. A logged outcome settles a widget: the slots
    declaring that outcome leave the page, and the widget holding them goes with
    them, its question answered — a suggestion accepted retires the markup it
    replaced, rejected retires the proposal, and either retires the wrapper.
    Which widgets those are is the registry's relation rather than a list here
    (`retirement_holders`), so a family a layer adds is licensed the day it is
    declared instead of failing three versions in with "ids dropped".

    A widget no one has answered can still be withdrawn — no decision rested on
    it — where the entry says what withdrawing it means (`x-withdrawn-as`:
    taking a suggestion back leaves the page as a `reject` would). That is the
    author asserting a state the user never gave, so it is hedged where a
    decision is not: only whole, every id under the slots it retires going with
    the widget, so a version can't quietly keep an unanswered proposal as
    settled content — and not while an unresolved thread is anchored in any of
    it. What the withdrawal doesn't name stays: the markup a pending deletion
    wraps is the page's own, and only the user's own `accept` consents to losing
    it.

    The outcomes are replay's own (`decisions`, folded over the version these
    widgets are on), so a decision a later version restated away settles
    nothing here either — replay hands the widget back as pending, and the
    slots stay needed. `spk` is that same version's reading, so the thread half of
    this answer stands on the page the outcomes were folded against."""
    anchored = anchored_ids(events, enclosing_of(spk))
    licensed = set()
    for holder in holders:
        answered = holder["id"] in outcomes
        outcome = outcomes[holder["id"]] if answered else holder["withdrawn_as"]
        retires = holder["retires"].get(outcome)
        if retires is None:
            continue
        whole = {holder["id"]} | retires
        if not answered and (whole & anchored or not retires <= dropped):
            continue
        licensed |= whole
    return licensed


def protected_ids(
    holders: list,
    events: list,
    dropped: set,
    projection,
    spk: dict,
    registry: dict,
) -> set:
    """Ids the next version must retain.

    Unresolved threads keep their anchor target. Effective standing state keeps
    its owner and fold unit, plus every page id its canonical liveness reading
    rests on. An older report hidden by a reader action remains in the log, but
    the action is the state the page must preserve.

    Declared retirement remains the explicit route for removing decision
    markup. Its holder and slots stay protected until ``retirable_ids`` licenses
    the outcome or a complete unanswered withdrawal.
    """
    within = enclosing_of(spk)
    state_ids = {
        identity
        for widget, unit, _facet in projection.desired
        for identity in (widget, unit)
    }
    state_ids.update(
        identity
        for event, _spec in projection.desired.values()
        for identity in action_rests_on(event, within)
    )
    retirement_ids = {holder["id"] for holder in holders}
    retirement_ids.update(
        identity
        for holder in holders
        for ids in holder["retires"].values()
        for identity in ids
    )
    licensed = retirable_ids(
        holders,
        events,
        dropped,
        decisions(projection.actions, registry),
        spk,
    )
    return (anchored_ids(events, within) | state_ids | retirement_ids) - licensed


def action_subjects(event: dict, byid: dict, within: dict, registry: dict) -> list:
    """What an action was *about*, at the finest grain the vocabulary allows.

    An action names the widget that sent it, but on a container that is rarely
    the thing decided: a `move` names the board and carries {card, to, index}, a
    `choose` names the group and carries {option}. So the subjects are the parts
    of the widget its detail points at, minus containers (x-content "items") —
    the column a card landed in is where the decision *put* it, not what it was
    about, and holding a version to a column's contents would refuse it for
    adding an unrelated card. Where a detail names no part of the widget (an
    `edit` carries text, an `accept` carries nothing) the widget is its own
    subject.

    No verb is interpreted here. A detail value counts when it names an element
    *inside the widget that sent the action* — not merely an id the page has
    somewhere, which would let a literal like "approved" collide with an element
    that happens to be called that."""
    widget = event["widget"]
    parts = action_rests_on(event, within)[1:]
    subjects = [
        v
        for v in parts
        if registry.get(byid.get(v, {}).get("tag"), {}).get("x-content") != "items"
    ]
    return subjects or [widget]


NO_RECORD = object()


class StateProjection(NamedTuple):
    """The durable widget state declared by one page and log window."""

    actions: dict
    reports: dict
    desired: dict
    report_settlements: dict
    classified: dict


def state_coordinate(widget: str, unit: str, spec: dict) -> tuple[str, str, str]:
    """The one identity of a durable fact: its owner, fold unit, and local facet."""
    return widget, unit, spec["facet"]


def state_projection(
    events: list,
    byid: dict,
    spk: dict,
    registry: dict,
    upto,
    floors: dict | None = None,
) -> StateProjection:
    """Project both durable channels onto owner-unit-facet coordinates.

    `actions` holds the last surviving reader action per coordinate. `reports`
    keeps every live report there because stamping retires all of them.
    `desired` gives a reader action precedence over provisional agent news on
    the same coordinate.

    Both channels share one classification pass over the window. They end by
    different facts: undo or a retraction floor ends an action, while a note
    settling a report ends that report. `report_settlements` retains the answer
    version for gate diagnostics; `classified` retains valid entries for other
    derived readings. An event whose widget the markup lacks stands nowhere."""
    if floors is None:
        floors = retractions(events, upto)
    withdrawn = taken_back(events)
    settled = report_settlements(events, upto)
    actions = {}
    reports = {}
    settlement_versions = {}
    classified = {}
    # Where each id sits: all the retraction test asks of a page, taken once for
    # the walk rather than per event.
    within = enclosing_of(spk)
    for event in events:
        if event["kind"] == "action":
            channel = "x-state"
        elif event["kind"] == "report":
            channel = "x-report"
        else:
            continue
        if upto is not None and event["revision"] > upto:
            continue
        rec = byid.get(event["widget"])
        if rec is None:
            continue
        spec = (registry.get(rec["tag"], {}).get(channel) or {}).get(event["action"])
        if not spec:
            continue
        unit = (
            event["widget"]
            if spec["unit"] == "widget"
            else event["detail"].get(spec["unit"])
        )
        if not isinstance(unit, str):
            continue
        coordinate = state_coordinate(event["widget"], unit, spec)
        entry = (event, spec)
        classified[event["id"]] = (coordinate, entry)
        if event["kind"] == "action":
            if event["id"] in withdrawn or action_retracted(event, floors, within):
                continue
            actions[coordinate] = entry
        elif settled_at := settled.get(event["id"]):
            settlement_versions[coordinate] = max(
                settlement_versions.get(coordinate, 0), settled_at
            )
        else:
            reports.setdefault(coordinate, []).append(entry)

    desired = {coordinate: entries[-1] for coordinate, entries in reports.items()}
    desired.update(actions)
    return StateProjection(
        actions,
        reports,
        desired,
        settlement_versions,
        classified,
    )


def recorded_owner(unit: str, byid: dict, spk: dict, registry: dict):
    """The nearest enclosing widget whose registry entry records state."""
    for candidate in reversed(spk.get(unit, EMPTY).within):
        rec = byid.get(candidate)
        entry = registry.get(rec["tag"], {}) if rec else {}
        if any(spec.get("record") for _, _, spec in state_specs(entry)):
            return candidate
    return None


def markup_facet(unit: str, spec: dict, byid: dict, spk: dict, registry: dict):
    """What one version's markup shows for a unit's declared record form: every
    element inside it carrying the attribute, the unit's own attribute's value,
    the declared container enclosing it, or its body's words — the empty list
    where the markup shows no pick.

    An attribute record is a set, never one element: a group taking several
    picks marks several options, and one shape for both is what lets the fold
    compare like with like whatever the group allows."""
    record = spec.get("record")
    if not record:
        return NO_RECORD
    if record["kind"] == "attribute":
        return sorted(
            oid
            for oid, orec in byid.items()
            if record["attr"] in orec["attrs"]
            and unit in spk.get(oid, EMPTY).within[:-1]
            and recorded_owner(oid, byid, spk, registry) == unit
        )
    if record["kind"] == "value":
        rec = byid.get(unit)
        return rec["attrs"].get(record["attr"]) if rec else None
    if record["kind"] == "position":
        enclosing = [
            i
            for i in spk.get(unit, EMPTY).within[:-1]
            if byid.get(i, {}).get("tag") == record["within"]
        ]
        return enclosing[-1] if enclosing else None
    return collapse(spk.get(unit, EMPTY).words)  # "body"


def folded_facet(e: dict, spec: dict):
    """The state the folded action left: the detail field the record declares,
    collapsed the way `spoken` collapses where it compares against words, and
    sorted where it compares against a set of marked elements."""
    record = spec.get("record")
    if not record:
        return NO_RECORD
    value = e["detail"].get(record["value"])
    if record["kind"] == "body":
        return collapse(str(value))
    if record["kind"] == "attribute":
        return sorted(value)
    return value


def page_projection(html: str, events: list, registry: dict, upto):
    """Project one page's markup and log window through one construction.

    `record_lag`, `page state`, and the passage readings used by `leaf comment`
    and `version check` therefore cannot drift on declarations, floors, or the
    window. The parser and spoken reading travel with the projection for callers
    that compare it with authored markup."""
    parser = parse_structure(html)
    spk = spoken(html, registry)
    return (
        state_projection(events, parser.by_id, spk, registry, upto),
        parser,
        spk,
    )


def rewritten_bodies(actions: dict) -> dict:
    """id → (verb, text): the user's standing rewrite of each element whose
    registry entry records a verb as the body (x-state record kind "body"), as
    replay leaves it. The action projection is read here for the one record kind
    whose state is words rather than markup, so the passage reading can hold
    those words where the authored body was."""
    return {
        unit: (e["action"], e["detail"][spec["record"]["value"]])
        for (_widget, unit, _facet), (e, spec) in actions.items()
        if (spec.get("record") or {}).get("kind") == "body"
    }


def decisions(actions: dict, registry: dict) -> dict:
    """widget id → the accept/reject its action projection leaves standing.

    Which verbs decide is the registry's word too: `x-retired-when` names the
    outcome under which an element leaves the page, so nothing here knows a
    widget or verb by name."""
    # Widgets only: $keys spells its members in the x- keys' own names, so a sweep
    # over every entry would take its paragraph on x-retired-when for a verb.
    deciding = {
        e["x-retired-when"]
        for tag, e in registry.items()
        if tag.startswith("lf-") and "x-retired-when" in e
    }
    return {
        unit: e["action"]
        for (_widget, unit, _facet), (e, _) in actions.items()
        if e["action"] in deciding
    }


def record_lag_entries(projection: StateProjection, byid, spk, registry: dict) -> list:
    """Coordinates whose markup lags the user's standing state — the record debt a
    log-less reader would miss. Advice, never errors: a version is free to stay
    silent (replay resolves it), but references/page-authoring.md's "Honoring
    reader state" obligation needs a feedback loop, and a finished page's final
    version is the page that has
    to read right without the log. One comparison, rendered twice: `record_lag`
    speaks it, `page state` ships it — the same entries, so the advice a check
    prints and the debt an agent queries cannot disagree."""
    entries = []
    for coordinate in sorted(projection.desired):
        widget, unit, facet = coordinate
        e, spec = projection.desired[coordinate]
        if unit not in byid:
            continue
        f_cur = markup_facet(unit, spec, byid, spk, registry)
        f_log = folded_facet(e, spec)
        if f_cur is NO_RECORD or f_cur == f_log:
            continue
        entries.append(
            {
                "widget": widget,
                "unit": unit,
                "facet": facet,
                "channel": e["kind"],
                "action": e["action"],
                "log": f_log,
                "markup": f_cur,
            }
        )
    return entries


def record_lag(
    projection: StateProjection, byid: dict, spk: dict, registry: dict
) -> list:
    """`record_lag_entries` as advice lines, for check and the transcript."""
    lag = []
    for n in record_lag_entries(projection, byid, spk, registry):
        who = "the log records" if n["channel"] == "action" else "a report records"
        lag.append(
            f"`{n['unit']}` ({n['facet']} facet): {who} {n['action']} → "
            f"{n['log']!r}; "
            f"the markup still shows {n['markup']!r}"
        )
    return lag
