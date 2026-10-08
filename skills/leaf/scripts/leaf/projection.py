"""Declaration-driven state and retirement projections."""

import re
from typing import NamedTuple

from leaf.events import (
    action_retracted,
    event_coordinate,
    report_settlements,
    retractions,
    taken_back,
)
from leaf.passages import (
    EMPTY,
    SourceReading,
    enclosing_of,
)
from leaf.registry.contract import (
    WRITERS,
    decides,
    detail_schema,
    event_spec,
    retirement_slots,
    same_state_definition,
    same_state_operation,
    state_definition,
    state_specs,
)
from leaf.registry.schema import schema_error
from leaf.schema import agent_name
from leaf.structure import SourceDocument
from leaf.thread_context import (
    ThreadStructure,
    thread_names,
    thread_structure,
    thread_widgets,
)


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
        updates.append(
            {
                "id": event["id"],
                "target": {"kind": "widget", "id": event["widget"]},
                "source": "report",
                "action": event["action"],
                "detail": event["detail"],
                "text": event["detail"]["text"] if spec.get("update") else None,
                "ts": event["ts"],
                "revision": event["revision"],
                "seq": event["seq"],
                "agent": agent_name(event),
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


def canonical_updates(projection) -> list[dict]:
    """Normalize projected reports into the one update feed, in log order."""
    return sorted(_report_updates(projection), key=lambda update: update["seq"])


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
            and holder["tag"] in entry["x-owners"]
        ):
            return node, holder
    return None


def retirement_holders(parser: SourceDocument, registry: dict) -> list:
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


NO_RECORD = object()

# A position record's rank: a base-36 fraction written as its digits after the point,
# never ending in 0, so string order is numeric order. The runtime's
# `projection/model.js` owns the reasoning and computes the keys between neighbours;
# these two rules are the ones both runtimes must read the same way, and
# `tests/rank_cases.json` holds both runtimes to the same cases.
RANK = re.compile(r"[0-9a-z]*[1-9a-z]")
_RANK_DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"


def authored_rank(index: int) -> str:
    """The rank of the unit at `index` in its authored container."""
    return "z" * (index // 35) + _RANK_DIGITS[index % 35 + 1]


class StateProjection(NamedTuple):
    """The durable widget state declared by one page and log window.

    `absorbed` holds the moves whose container this document authors differently
    from the revision the move was made on (`move_absorbed`). Every revision that
    does passed `page check` against the fold that held the move, so its markup
    wrote the unit where the move put it. An absorbed move still stands, as a
    written-back pick does, but no longer places its unit: the markup does.

    `standing` holds every action that survives, neither taken back nor retracted;
    `actions` is the newest of them at each coordinate. A browser withdrawing the one
    on top locally falls back to the next of these rather than judging survival
    again."""

    actions: dict
    reports: dict
    desired: dict
    report_settlements: dict
    classified: dict
    absorbed: frozenset
    standing: frozenset


class PageReading(NamedTuple):
    """One page document and the durable state folded against that exact source."""

    reading: SourceReading
    revision: int
    events: list
    projection: StateProjection

    @property
    def document(self) -> SourceDocument:
        return self.reading.document

    @property
    def registry(self) -> dict:
        return self.reading.registry

    @property
    def spoken(self) -> dict:
        return self.reading.spoken

    @property
    def within(self) -> dict:
        return self.reading.within


class FrozenThreadReading(NamedTuple):
    """The panel's frozen markup and durable state as one document.

    No revision window or retraction floor bounds this projection. The markup
    was frozen into the log, so its actions read the whole thread window.
    """

    structure: ThreadStructure
    spoken: dict
    thread_by_name: dict
    thread_by_widget: dict
    projection: StateProjection

    @property
    def by_id(self) -> dict:
        return self.structure.by_id

    @property
    def elements(self) -> list[dict]:
        return [
            record
            for fragment in self.structure.fragments.values()
            for record in fragment.lf_elements
        ]

    def subject_thread(self, subject: dict) -> str | None:
        """The thread a workflow or update subject stands in: a thread subject is
        its own, a widget frozen into a message is its thread's, and a page widget
        stands in none."""
        if subject["kind"] == "thread":
            return subject["id"]
        if subject["kind"] == "widget":
            return self.thread_by_widget.get(subject["id"])
        return None


def state_projection(
    events: list,
    byid: dict,
    spk: dict,
    registry: dict,
    upto,
    floors: dict | None = None,
    *,
    withdrawn: set | None = None,
) -> StateProjection:
    """Project user actions and agent reports onto owner-unit-verb coordinates.

    A verb declares one writer, so a coordinate holds actions or reports, never
    both. `actions` holds the last surviving user action per coordinate.
    `reports` keeps every live report there because stamping retires all of
    them. `desired` is the state that stands at each coordinate: its action, or
    its newest live report.

    Both writers share one classification pass over the window. They end by
    different facts: undo or a retraction floor ends an action, while a note
    settling a report ends that report. `report_settlements` retains the answer
    version for gate diagnostics; `classified` retains valid entries for other
    derived readings. Events apply where their admitted operation still matches
    the widget and their payload remains valid in its current domain. A domain
    may broaden without losing valid decisions. The log and captured document
    retain the original operation; changing a declaration never applies it to a
    different record or constructor."""
    if floors is None:
        floors = retractions(events, upto)
    if withdrawn is None:
        withdrawn = taken_back(events)
    settled = report_settlements(events, upto)
    actions = {}
    standing = set()
    reports = {}
    settlement_versions = {}
    classified = {}
    # Where each id sits: all the retraction test asks of a page, taken once for
    # the walk rather than per event.
    within = enclosing_of(spk)
    for event in events:
        if event["kind"] not in WRITERS:
            continue
        if upto is not None and event["revision"] > upto:
            continue
        rec = byid.get(event["widget"])
        if rec is None:
            continue
        spec = event_spec(registry.get(rec["tag"], {}), event)
        if spec is None:
            continue
        recorded = event["meaning"].get("state")
        current = state_definition(rec["tag"], registry[rec["tag"]], spec)
        if not same_state_operation(recorded, current):
            continue
        # Admission already checked this payload. Only a changed domain needs
        # the validator again; it may broaden without losing the old operation.
        if not same_state_definition(recorded, current) and schema_error(
            detail_schema(registry[rec["tag"]], spec), event["detail"]
        ):
            continue
        coordinate = event_coordinate(event)
        entry = (event, spec)
        classified[event["id"]] = (coordinate, entry)
        if event["kind"] == "action":
            if event["id"] in withdrawn or action_retracted(event, floors, within):
                continue
            actions[coordinate] = entry
            standing.add(event["id"])
        elif settled_at := settled.get(event["id"]):
            settlement_versions[coordinate] = max(
                settlement_versions.get(coordinate, 0), settled_at
            )
        else:
            reports.setdefault(coordinate, []).append(entry)

    desired = {coordinate: entries[-1] for coordinate, entries in reports.items()}
    desired.update(actions)
    orders = {}
    absorbed = frozenset(
        event["id"]
        for _coordinate, (event, spec) in classified.values()
        if event["kind"] == "action"
        and move_absorbed(event, spec, byid, spk, registry, orders)
    )
    return StateProjection(
        actions,
        reports,
        desired,
        settlement_versions,
        classified,
        absorbed,
        frozenset(standing),
    )


def with_action(
    projection: StateProjection, event: dict, spec: dict
) -> StateProjection:
    """The projection with one newer action standing at its admitted coordinate.

    An action made against the window this projection folds is the latest at its
    coordinate and no floor of that window can have retracted it, so admission
    reads a candidate this way instead of folding the whole log again."""
    coordinate = event_coordinate(event)
    entry = (event, spec)
    return projection._replace(
        actions={**projection.actions, coordinate: entry},
        desired={**projection.desired, coordinate: entry},
        standing=projection.standing | {event["id"]},
    )


def frozen_thread_reading(
    events: list, registry: dict, *, withdrawn: set | None = None
) -> FrozenThreadReading:
    """Project every frozen message fragment through one shared reading."""
    structure = thread_structure(events)
    by_name = thread_names(events)
    spk = {}
    for fragment in structure.fragments.values():
        spk.update(SourceReading(fragment, registry).spoken)
    by_widget = thread_widgets(structure, by_name)
    return FrozenThreadReading(
        structure,
        spk,
        by_name,
        by_widget,
        state_projection(
            events, structure.by_id, spk, registry, None, floors={}, withdrawn=withdrawn
        ),
    )


def recorded_owner(unit: str, byid: dict, spk: dict, registry: dict):
    """The nearest enclosing widget whose element declaration records state."""
    for candidate in reversed(spk.get(unit, EMPTY).within):
        rec = byid.get(candidate)
        entry = registry.get(rec["tag"], {}) if rec else {}
        if any(spec.get("record") for _, spec in state_specs(entry)):
            return candidate
    return None


def markup_value(unit: str, spec: dict, byid: dict, spk: dict, registry: dict):
    """What one version's markup shows for a unit's declared record form: every
    element inside it carrying the attribute, the unit's own attribute's value, or
    its body's words — the empty list where the markup shows no pick. A unit's
    place is read against the whole fold instead (`recorded_state`).

    An attribute record is a set, never one element: a group taking several
    picks marks several options, and one shape for both is what lets the fold
    compare like with like whatever the group allows."""
    record = spec.get("record")
    if not record:
        return NO_RECORD
    if record["kind"] == "position":
        raise ValueError("a position is read against the whole fold: recorded_state")
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
    rec = byid.get(unit)
    return rec["body"] if rec else ""  # "body"


def authored_positions(
    owner: str, record: dict, byid: dict, spk: dict, registry: dict
) -> dict[str, list[str]]:
    """Container id → the ids of its units in one version's markup order, for each
    `within` container `owner` records positions in."""
    containers = {
        cid: rec
        for cid, rec in byid.items()
        if rec["tag"] == record["within"]
        and recorded_owner(cid, byid, spk, registry) == owner
    }
    order = {cid: [] for cid in containers}
    for uid, rec in byid.items():
        holder = rec["holder"]
        cid = holder["attrs"].get("id") if holder else None
        if cid in containers and containers[cid] is holder:
            order[cid].append(uid)
    return order


def move_absorbed(
    event: dict, spec: dict, byid: dict, spk: dict, registry: dict, orders: dict
) -> bool:
    """Whether this document authors a move's container differently from the
    revision the move was made on: other units, or the same in another order, than
    the move's `meaning.among`. The rank lies among those authored units, so it lands
    in the gap the user chose only while they stand as they did; a document that
    changes them has written the unit itself (`page check`). `orders` caches each
    owner's authored order across the calls one reading makes."""
    among = event["meaning"].get("among")
    if among is None:
        return False
    record = spec["record"]
    owner = event["widget"]
    if owner not in orders:
        orders[owner] = authored_positions(owner, record, byid, spk, registry)
    return orders[owner].get(event["detail"]["value"]) != among


def folded_positions(
    owner: str,
    verb: str,
    record: dict,
    byid: dict,
    spk: dict,
    registry: dict,
    projection: StateProjection,
) -> dict[str, list[str]]:
    """Container id → its units in the order the fold leaves on this markup.

    Authored units rank by authored index; each standing move this markup has not
    absorbed (`move_absorbed`) puts its unit in its container at the rank it names,
    and a container lists its units by rank, ties by id. `projection/model.js`'s
    `foldWidgetStates` is the browser's reading of the same rule."""
    order = authored_positions(owner, record, byid, spk, registry)
    ranks = {
        unit: authored_rank(index)
        for units in order.values()
        for index, unit in enumerate(units)
    }
    standing = sorted(projection.desired.items(), key=lambda item: item[1][0]["seq"])
    orders = {owner: authored_positions(owner, record, byid, spk, registry)}
    for (widget, unit, action), (event, spec) in standing:
        if (
            widget != owner
            or action != verb
            or move_absorbed(event, spec, byid, spk, registry, orders)
        ):
            continue
        destination = order.get(event["detail"]["value"])
        if destination is None or unit not in ranks:
            continue
        for units in order.values():
            if unit in units:
                units.remove(unit)
        destination.append(unit)
        ranks[unit] = event["detail"]["rank"]
    return {
        container: sorted(units, key=lambda unit: (ranks[unit], unit))
        for container, units in order.items()
    }


class Placement(NamedTuple):
    """Where one unit stands: its container, and the nearest unit both documents
    list before it there, None where no shared unit precedes it."""

    container: str | None
    after: str | None


def _placement(unit: str, order: dict, shared: set) -> Placement:
    for container, units in order.items():
        if unit in units:
            before = [i for i in units[: units.index(unit)] if i in shared]
            return Placement(container, before[-1] if before else None)
    return Placement(None, None)


def recorded_state(
    coordinate: tuple,
    event: dict,
    spec: dict,
    markup: tuple,
    folded: tuple,
    registry: dict,
    projection: StateProjection,
):
    """What one version's markup shows at a standing coordinate, beside the state
    the fold leaves there: a pair the caller compares, or NO_RECORD for a verb with
    no record form. `markup` and `folded` are each a document's `(byid, spk)`; the
    fold is `projection` read on `folded`.

    Most record forms are the event's own detail. A position is a `Placement`,
    read on both sides from the whole fold: the unit's container and the nearest
    unit both documents list before it, which is the gap the user dropped it into.
    A version may add or drop cards around it, or rearrange cards away from it, and
    still say the same."""
    widget, unit, verb = coordinate
    record = spec.get("record")
    if not record:
        return NO_RECORD
    if record["kind"] != "position":
        return markup_value(unit, spec, *markup, registry), folded_value(event, spec)
    shown = authored_positions(widget, record, *markup, registry)
    left = folded_positions(widget, verb, record, *folded, registry, projection)
    shared = {i for units in shown.values() for i in units} & {
        i for units in left.values() for i in units
    }
    return _placement(unit, shown, shared), _placement(unit, left, shared)


def folded_value(e: dict, spec: dict):
    """The exact state left in detail.value, sorted only for unordered id sets.

    Body source includes Markdown syntax and meaningful whitespace. Visible passage
    words are a separate reading and never determine semantic equality.
    """
    record = spec.get("record")
    if not record:
        return NO_RECORD
    value = e["detail"]["value"]
    if record["kind"] == "attribute":
        return sorted(value)
    return value


def page_reading(
    reading: SourceReading, events: list, revision: int, *, withdrawn: set | None = None
) -> PageReading:
    """Read one page's markup and log window through one construction.

    Document inspection and the passage readings used by `leaf thread open` and
    `page check` share declarations, floors, and the log window. The document's
    own reading (`SourceReading`) travels with the projection for callers that need
    its authored construction; a stored revision's is held across reads, so only
    the fold over the log is taken here."""
    return PageReading(
        reading,
        revision,
        events,
        state_projection(
            events,
            reading.document.by_id,
            reading.spoken,
            reading.registry,
            revision,
            withdrawn=withdrawn,
        ),
    )


def rewritten_bodies(actions: dict) -> dict:
    """id → (verb, text): the user's standing rewrite of each element whose
    element declaration records a verb as the body (x-state record kind "body"), as
    replay leaves it. The action projection is read here for the one record kind
    whose state is words rather than markup, so the passage reading can hold
    those words where the authored body was."""
    return {
        unit: (e["action"], e["detail"]["value"])
        for (_widget, unit, _verb), (e, spec) in actions.items()
        if (spec.get("record") or {}).get("kind") == "body"
    }


def generated_children(desired: dict, authored_ids: set) -> dict:
    """Owner id → the children standing creating actions supply, in log order.

    Each created child is its action's fold unit, so it stands on a coordinate of its
    own: a later action of another verb leaves it standing, and only an undo or a
    retraction of that action takes it away. An authored element with the same id
    already supplies that construction and keeps its authored content.
    """
    children = {}
    for (widget, unit, _verb), (event, spec) in sorted(
        desired.items(), key=lambda item: item[1][0]["seq"]
    ):
        if (creates := spec.get("creates")) and unit not in authored_ids:
            children.setdefault(widget, []).append(
                {
                    "id": unit,
                    "tag": creates["child"],
                    "text": event["detail"][creates["words"]],
                    "event": event,
                }
            )
    return children


def record_members(
    owner: str, projection: StateProjection, byid: dict, spk: dict, registry: dict
) -> set:
    """The ids an attribute record on `owner` may name: the authored elements it
    records, and the children its standing actions created."""
    authored = {
        oid
        for oid in byid
        if owner in spk.get(oid, EMPTY).within[:-1]
        and recorded_owner(oid, byid, spk, registry) == owner
    }
    created = generated_children(projection.desired, set(byid)).get(owner, [])
    return authored | {child["id"] for child in created}


def retirement_outcomes(actions: dict) -> dict:
    """widget id → the outcome its standing deciding action names.

    Which verb decides is the registry's word: the one whose detail declares the
    reserved `outcome` (`decides`), whose value `x-retired-when` and
    `x-withdrawn-as` name, so nothing here knows a widget or verb by name."""
    return {
        widget: e["detail"]["outcome"]
        for (widget, _unit, _verb), (e, spec) in actions.items()
        if decides(spec)
    }
