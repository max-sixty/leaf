"""Declaration-driven state and retirement projections."""

from collections.abc import Callable, Iterable
from copy import copy
from dataclasses import dataclass, replace
from functools import cached_property
from typing import NamedTuple

from leaf.event_log import folded
from leaf.events import (
    InForce,
    event_coordinate,
    note_settlements,
)
from leaf.passages import (
    EMPTY,
    SourceReading,
    enclosing_of,
)
from leaf.registry.contract import (
    decides,
    event_spec,
    retirement_slots,
    same_state_definition,
    same_state_operation,
    state_definition,
    state_specs,
)
from leaf.registry.kernel import verb_writers
from leaf.registry.schema import schema_error
from leaf.schema import agent_name
from leaf.structure import SourceDocument
from leaf.thread_context import ThreadStructure, logged_fragment


def _reports(projection) -> list[dict]:
    if projection is None:
        return []
    unsettled = {
        event["id"]
        for entries in projection.reports.values()
        for event, _spec in entries
    }
    effective = {
        event["id"]
        for event, _spec in projection.desired.values()
        if event["kind"] == "report"
    }
    reports = []
    for _coordinate, (event, spec) in projection.classified.values():
        if event["kind"] != "report":
            continue
        reports.append(
            {
                "id": event["id"],
                "target": {"kind": "widget", "id": event["widget"]},
                "source": "report",
                "action": event["action"],
                "detail": event["detail"],
                "text": event["detail"]["text"] if spec.get("text") else None,
                "ts": event["ts"],
                "revision": event["revision"],
                "seq": event["seq"],
                "agent": agent_name(event),
                "session": event.get("session"),
                "disposition": (
                    "effective"
                    if event["id"] in effective
                    else "outranked"
                    if event["id"] in unsettled
                    else "settled"
                ),
            }
        )
    return reports


def canonical_reports(projection) -> list[dict]:
    """Normalize projected reports into the one report feed, in log order."""
    return sorted(_reports(projection), key=lambda report: report["seq"])


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
    for wid, rec in parser.holders.items():
        pair = enclosing_slot(rec, registry) if rec else None
        if pair is None:
            continue
        slot, holder = pair
        held = holders.get(holder["attrs"].get("id"))
        if held is not None:
            held["retires"][registry[slot["tag"]]["x-retired-when"]].add(wid)
    return list(holders.values())


NO_RECORD = object()

# The digits of a position record's rank (`registry.contract.RANK`).
_RANK_DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"


def authored_rank(index: int) -> str:
    """The rank of the unit at `index` in its authored container."""
    return "z" * (index // 35) + _RANK_DIGITS[index % 35 + 1]


@dataclass(frozen=True)
class StateProjection:
    """The durable widget state declared by one page and log window.

    `absorbed` holds the moves whose container this document authors differently
    from the revision the move was made on (`move_absorbed`). Every revision that
    does passed `page check` against the fold that held the move, so its markup
    wrote the unit where the move put it. An absorbed move still stands, as a
    written-back pick does, but no longer places its unit: the markup does.

    `in_force` holds every action that survives, neither taken back nor retracted;
    `actions` is the newest of them at each coordinate. A browser withdrawing the one
    on top locally falls back to the next of these rather than judging survival
    again.

    A reading that asks about each widget in turn, such as the obligation
    inventory, reads that widget's coordinates through an index built once per
    projection (`actions_by_owner`, `desired_by_owner`, `desired_by_unit`,
    `classified_by_unit`), so its cost grows with the page rather than with the page
    times its widgets."""

    actions: dict
    reports: dict
    desired: dict
    classified: dict
    absorbed: frozenset
    in_force: frozenset

    @cached_property
    def actions_by_owner(self) -> dict[str, dict]:
        """Owner id → its coordinates in `actions` and what holds each, in
        `actions`' order."""
        index = {}
        for coordinate, held in self.actions.items():
            index.setdefault(coordinate[0], {})[coordinate] = held
        return index

    @cached_property
    def desired_by_owner(self) -> dict[str, list]:
        """Owner id → each of its coordinates in `desired` with the state standing
        there, `(coordinate, entry)`, in `desired`'s order."""
        index = {}
        for coordinate, entry in self.desired.items():
            index.setdefault(coordinate[0], []).append((coordinate, entry))
        return index

    @cached_property
    def desired_by_unit(self) -> dict[str, list]:
        """Unit id → the state standing at each of its coordinates, whatever their
        owner, in `desired`'s order."""
        index = {}
        for coordinate, entry in self.desired.items():
            index.setdefault(coordinate[1], []).append(entry)
        return index

    @cached_property
    def classified_by_unit(self) -> dict[str, list]:
        """Unit id → the `classified` entries at its coordinates, whatever their
        owner, each `(coordinate, (event, spec))`, in log order."""
        index = {}
        for coordinate, entry in self.classified.values():
            index.setdefault(coordinate[1], []).append((coordinate, entry))
        return index


class PageReading(NamedTuple):
    """One page document and the durable state folded against that exact source."""

    reading: SourceReading
    revision: int
    events: list
    projection: StateProjection
    prior: Callable[[], Iterable[tuple[int, SourceReading]]] | None = None

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
        """The thread a workflow or report subject stands in: a thread subject is
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
    *,
    retracting: bool = True,
    anchor: object | None = None,
) -> StateProjection:
    """Project user actions and agent reports onto owner-unit-verb coordinates.

    A verb declares one writer, so a coordinate holds actions or reports, never
    both. `actions` holds the last surviving user action per coordinate.
    `reports` keeps every live report there because stamping retires all of
    them. `desired` is the state that stands at each coordinate: its action, or
    its newest live report. `obligations.previously_requested` reads `desired` on
    prefixes of the log by the same rule, from `classified` and `in_force`.

    Both writers share one classification pass over the window. They end by
    different facts: undo or a retraction floor ends an action, while a note
    settling a report ends that report. `classified` retains valid entries for other
    derived readings. Events apply where their admitted operation still matches
    the widget and their payload remains valid in its current domain. A domain
    may broaden without losing valid decisions. The log and captured document
    retain the original operation; changing a declaration never applies it to a
    different record or constructor.

    A version note through `upto` retracts what it restates where `retracting`;
    the frozen thread markup no version rewrites folds with none. Given `anchor`,
    the reading of `byid`, `spk` and `registry`, the fold is kept with a page's log
    and steps only through what was appended since (`event_log.folded`)."""
    return folded(
        events,
        anchor,
        ("state", upto, retracting),
        lambda: ProjectionFold(byid, spk, registry, upto, retracting=retracting),
    )


class ProjectionFold:
    """`state_projection`'s walk over the log, one event at a time.

    An undo withdraws its action and a note through `upto` retracts and settles
    where it falls (`InForce`). What a reader of the whole log would order by the
    first action or report standing at the end, `reading` orders the same way, so a
    walk and a whole read give one projection."""

    def __init__(self, byid: dict, spk: dict, registry: dict, upto, *, retracting):
        self.byid = byid
        self.registry = registry
        self.upto = upto
        self.retracting = retracting
        self.writers = verb_writers()
        # Where each id sits is all the retraction test asks of a page, taken once
        # for the walk rather than per event.
        self.in_force = InForce(enclosing_of(spk))
        self.classified: dict[str, tuple] = {}
        # Each classified event → its place in the walk.
        self.position: dict[str, int] = {}
        self.specs: dict[str, dict] = {}
        # coordinate → its live reports, id → entry, in log order.
        self.reports: dict[tuple, dict[str, tuple]] = {}
        self.report_at: dict[str, tuple] = {}
        self.absorbed: set[str] = set()
        # (widget, verb, kind) → its spec and current definition, which the
        # document and vocabulary decide alone.
        self.definitions: dict[tuple, tuple | None] = {}
        self._orders = None

    def grow(self, byid: dict, spk: dict) -> None:
        """Take in a part of the document that came with an event, whose ids no
        earlier event names: the frozen thread markup, which each message carrying
        markup adds to (`FrozenFold`)."""
        self.byid.update(byid)
        self.in_force.within.update(enclosing_of(spk))
        self._orders = None

    def copy(self) -> "ProjectionFold":
        """A walk that goes on from here without changing this one, the document
        `grow` adds to included."""
        twin = copy(self)
        twin.byid = dict(self.byid)
        twin.in_force = self.in_force.copy()
        twin.in_force.within = dict(self.in_force.within)
        twin.classified = dict(self.classified)
        twin.position = dict(self.position)
        twin.specs = dict(self.specs)
        twin.reports = {
            coordinate: dict(entries) for coordinate, entries in self.reports.items()
        }
        twin.report_at = dict(self.report_at)
        twin.absorbed = set(self.absorbed)
        return twin

    def _definition(self, event: dict) -> tuple | None:
        key = (event["widget"], event["action"], event["kind"])
        if key not in self.definitions:
            rec = self.byid[event["widget"]]
            spec = event_spec(self.registry.get(rec["tag"], {}), event)
            self.definitions[key] = (
                None
                if spec is None
                else (
                    spec,
                    state_definition(
                        rec["tag"],
                        self.registry[rec["tag"]],
                        spec,
                        attrs=rec["attrs"],
                        registry=self.registry,
                    ),
                )
            )
        return self.definitions[key]

    def step(self, event: dict) -> None:
        if undoes := event.get("undoes"):
            self.in_force.withdraw(undoes)
            return
        kind = event["kind"]
        if kind != "note" and kind not in self.writers:
            return
        if self.upto is not None and event["revision"] > self.upto:
            return
        if kind == "note":
            if self.retracting:
                self.in_force.restate(event)
            for identity in note_settlements(event, "report"):
                if (coordinate := self.report_at.pop(identity, None)) is not None:
                    del self.reports[coordinate][identity]
            return
        if event["widget"] not in self.byid:
            return
        definition = self._definition(event)
        if definition is None:
            return
        spec, current = definition
        recorded = event["meaning"].get("state")
        if not same_state_operation(recorded, current):
            return
        # Admission already checked this payload. Only a changed domain needs
        # the validator again; it may broaden without losing the old operation.
        if not same_state_definition(
            recorded.get("detail"), current["detail"]
        ) and schema_error(current["detail"], event["detail"]):
            return
        coordinate = event_coordinate(event)
        entry = (event, spec)
        self.position[event["id"]] = len(self.classified)
        self.classified[event["id"]] = (coordinate, entry)
        if kind == "action":
            if self.in_force.admit(event):
                self.specs[event["id"]] = spec
            if event["meaning"].get("among") is not None:
                if self._orders is None:
                    self._orders = AuthoredOrders(self.byid, self.registry)
                if move_absorbed(event, spec, self._orders):
                    self.absorbed.add(event["id"])
        else:
            self.reports.setdefault(coordinate, {})[event["id"]] = entry
            self.report_at[event["id"]] = coordinate

    def reading(self) -> StateProjection:
        actions = {
            coordinate: (winner, self.specs[winner["id"]])
            for coordinate, winner in self.in_force.winners().items()
        }
        reports = {
            coordinate: list(entries.values())
            for coordinate, entries in sorted(
                ((c, entries) for c, entries in self.reports.items() if entries),
                key=lambda item: self.position[next(iter(item[1]))],
            )
        }
        desired = {coordinate: entries[-1] for coordinate, entries in reports.items()}
        desired.update(actions)
        return StateProjection(
            actions,
            reports,
            desired,
            dict(self.classified),
            frozenset(self.absorbed),
            self.in_force.ids(),
        )


def with_action(
    projection: StateProjection, event: dict, spec: dict
) -> StateProjection:
    """The projection with one newer action in force at its admitted coordinate.

    An action made against the window this projection folds is the latest at its
    coordinate and no floor of that window can have retracted it, so admission
    reads a candidate this way instead of folding the whole log again."""
    coordinate = event_coordinate(event)
    entry = (event, spec)
    return replace(
        projection,
        actions={**projection.actions, coordinate: entry},
        desired={**projection.desired, coordinate: entry},
        in_force=projection.in_force | {event["id"]},
    )


def frozen_thread_reading(
    events: list, registry: dict, *, anchor: object | None = None
) -> FrozenThreadReading:
    """Project every frozen message fragment through one shared reading. Given
    `anchor`, a reading whose registry is `registry`, the walk is kept with a page's
    log (`event_log.folded`)."""
    return folded(
        events, anchor, ("frozen", id(registry)), lambda: FrozenFold(registry)
    )


class FrozenFold:
    """`frozen_thread_reading`'s walk over the log, one event at a time.

    The panel's document is the markup the log's messages froze, so each message
    carrying markup adds its fragment (`logged_fragment`) as it arrives, and the
    projection steps on against the document as it then stands (`ProjectionFold.grow`):
    an action names a widget a message logged before it declared, and no fragment
    declares an id another already holds (`validation.admission.check_markup`).
    For the same reasons each message's thread and each widget's are read where
    they fall, as `thread_names` and `thread_widgets` read them from the whole log."""

    def __init__(self, registry: dict):
        self.registry = registry
        self.ids: set[str] = set()
        self.fragments: dict[str, SourceDocument] = {}
        self.spoken: dict = {}
        self.names: dict[str, str] = {}
        self.widgets: dict[str, str] = {}
        self.projection = ProjectionFold({}, {}, registry, None, retracting=False)

    def step(self, event: dict) -> None:
        kind = event["kind"]
        if kind == "comment":
            self.names[event["id"]] = event["id"]
        elif kind == "reply":
            self.names[event["id"]] = self.names[event["parent"]]
        if event.get("markup"):
            fragment = logged_fragment(event)
            spoken = SourceReading(fragment, self.registry).spoken
            self.fragments[event["id"]] = fragment
            self.ids.update(fragment.ids)
            self.spoken.update(spoken)
            self.projection.grow(fragment.by_id, spoken)
            thread = self.names.get(event["id"])
            for widget in fragment.by_id:
                if thread is None:
                    self.widgets.pop(widget, None)
                else:
                    self.widgets[widget] = thread
        self.projection.step(event)

    def reading(self) -> FrozenThreadReading:
        return FrozenThreadReading(
            ThreadStructure(
                set(self.ids), dict(self.projection.byid), dict(self.fragments)
            ),
            dict(self.spoken),
            dict(self.names),
            dict(self.widgets),
            self.projection.reading(),
        )

    def copy(self) -> "FrozenFold":
        twin = copy(self)
        twin.ids = set(self.ids)
        twin.fragments = dict(self.fragments)
        twin.spoken = dict(self.spoken)
        twin.names = dict(self.names)
        twin.widgets = dict(self.widgets)
        twin.projection = self.projection.copy()
        return twin


def projected_action_holders(
    projection: StateProjection, byid: dict, registry: dict
) -> dict[str, dict]:
    """Unit id → its enclosing vocabulary widget after position records in force
    no later revision has absorbed; an absorbed move leaves its unit where the
    markup has it. Only units `byid` holds are read."""
    holders = {}
    for unit, unit_rec in byid.items():
        for event, spec in projection.desired_by_unit.get(unit, ()):
            record = spec.get("record") or {}
            if record.get("kind") != "position" or event["id"] in projection.absorbed:
                continue
            target = byid.get(event["detail"]["value"])
            if target:
                holder = target if target["tag"] in registry else target.get("holder")
                permitted = (registry.get(unit_rec["tag"]) or {}).get("x-owners", [])
                if holder and holder["tag"] in permitted:
                    holders[unit] = holder
    return holders


def recorded_owner(
    unit: str, record: dict, byid: dict, registry: dict, *, holders: dict | None = None
):
    """The nearest ancestor recording this physical member-state slot.

    Attribute sets own one attribute; positions own one place. Other attributes
    and record kinds coexist, including scalar state on a member or container.
    A member's own records never claim its membership from its parent. Optional
    holder overrides read current membership after position records in force.
    """
    holders = holders or {}
    node = byid.get(unit)
    while node is not None:
        node = holders.get(node["attrs"].get("id"), node.get("holder"))
        if node is None:
            break
        entry = registry.get(node["tag"], {})
        if any(
            (spec.get("record") or {}).get("kind") == record["kind"]
            and (spec.get("record") or {}).get("attr") == record.get("attr")
            for _, spec in state_specs(entry)
        ):
            return node["attrs"].get("id")
    return None


def attribute_marks(byid: dict, spk: dict, registry: dict) -> dict[str, dict]:
    """What one version's markup shows for every attribute record at once: attribute
    → owner id → the ids inside the owner that carry the attribute and whose nearest
    ancestor recording it (`recorded_owner`) is that owner, sorted.

    Read once per document by whoever asks `markup_value` about many units, so each
    question reads its own owner's marks rather than every element of the page."""
    declared = {
        attr
        for tag, entry in registry.items()
        if not tag.startswith("$")
        for _verb, spec in state_specs(entry)
        if (record := spec.get("record") or {}).get("kind") == "attribute"
        and (attr := record.get("attr")) is not None
    }
    marks: dict[str, dict[str, list[str]]] = {}
    for oid, orec in byid.items():
        for attr in declared.intersection(orec["attrs"]):
            owner = recorded_owner(
                oid, {"kind": "attribute", "attr": attr}, byid, registry
            )
            if owner is not None and owner in spk.get(oid, EMPTY).within[:-1]:
                marks.setdefault(attr, {}).setdefault(owner, []).append(oid)
    for owners in marks.values():
        for ids in owners.values():
            ids.sort()
    return marks


def markup_value(unit: str, spec: dict, byid: dict, marks: dict):
    """What one version's markup shows for a unit's declared record form: every
    element inside it carrying the attribute, the unit's own attribute's value, or
    its body's words — the empty list where the markup shows no pick. A unit's
    place is read against the whole fold instead (`recorded_state`). `marks` is the
    same version's `attribute_marks`.

    An attribute record is a set, never one element: a group taking several
    picks marks several options, and one shape for both is what lets the fold
    compare like with like whatever the group allows."""
    record = spec.get("record")
    if not record:
        return NO_RECORD
    if record["kind"] == "position":
        raise ValueError("a position is read against the whole fold: recorded_state")
    if record["kind"] == "attribute":
        return list(marks.get(record["attr"], {}).get(unit, ()))
    if record["kind"] == "value":
        rec = byid.get(unit)
        return rec["attrs"].get(record["attr"]) if rec else None
    rec = byid.get(unit)
    return rec["body"] if rec else ""  # "body"


_POSITION = {"kind": "position"}


class AuthoredOrders:
    """Where one version's markup puts every position owner's units, read in one
    pass over the document, so a reading that asks about many owners, such as a page
    of boards, reads the page once rather than once per owner.

    A container belongs to its nearest ancestor recording positions
    (`recorded_owner`). Every caller reads the lists `of` returns and none changes
    them."""

    def __init__(self, byid: dict, registry: dict):
        within = {
            record["within"]
            for tag, entry in registry.items()
            if not tag.startswith("$")
            for _verb, spec in state_specs(entry)
            if (record := spec.get("record") or {}).get("kind") == "position"
        }
        containers = {}
        for cid, rec in byid.items():
            if rec["tag"] in within and (
                owner := recorded_owner(cid, _POSITION, byid, registry)
            ):
                containers[cid] = (rec, owner)
        self._orders: dict[tuple[str, str], dict[str, list[str]]] = {}
        for cid, (rec, owner) in containers.items():
            self._orders.setdefault((owner, rec["tag"]), {})[cid] = []
        for uid, rec in byid.items():
            holder = rec["holder"]
            held = containers.get(holder["attrs"].get("id")) if holder else None
            if held is not None and held[0] is holder:
                self._orders[held[1], holder["tag"]][holder["attrs"]["id"]].append(uid)

    def of(self, owner: str, record: dict) -> dict[str, list[str]]:
        """Container id → the ids of its units in markup order, for each
        `record["within"]` container `owner` records positions in."""
        return self._orders.get((owner, record["within"]), {})


def move_absorbed(event: dict, spec: dict, orders: AuthoredOrders) -> bool:
    """Whether this document, whose `AuthoredOrders` are `orders`, authors a move's
    container differently from the revision the move was made on: other units, or
    the same in another order, than the move's `meaning.among`. The rank lies among
    those authored units, so it lands in the gap the user chose only while they
    stand as they did; a document that changes them has written the unit itself
    (`page check`)."""
    among = event["meaning"].get("among")
    if among is None:
        return False
    container = event["detail"]["value"]
    return orders.of(event["widget"], spec["record"]).get(container) != among


def folded_positions(
    owner: str,
    verb: str,
    record: dict,
    orders: AuthoredOrders,
    projection: StateProjection,
) -> dict[str, list[str]]:
    """Container id → its units in the order the fold leaves on the markup whose
    `AuthoredOrders` are `orders`.

    Authored units rank by authored index; each move in force this markup has not
    absorbed (`move_absorbed`) puts its unit in its container at the rank it names,
    and a container lists its units by rank, ties by id. `projection/model.js`'s
    `foldWidgetStates` is the browser's reading of the same rule."""
    order = orders.of(owner, record)
    ranks = {
        unit: authored_rank(index)
        for units in order.values()
        for index, unit in enumerate(units)
    }
    where = {unit: container for container, units in order.items() for unit in units}
    moves = sorted(
        (
            (unit, entry)
            for (_owner, unit, action), entry in projection.desired_by_owner.get(
                owner, ()
            )
            if action == verb
        ),
        key=lambda item: item[1][0]["seq"],
    )
    for unit, (event, spec) in moves:
        destination = event["detail"]["value"]
        if (
            destination not in order
            or unit not in ranks
            or move_absorbed(event, spec, orders)
        ):
            continue
        where[unit] = destination
        ranks[unit] = event["detail"]["rank"]
    placed = {container: [] for container in order}
    for unit, container in where.items():
        placed[container].append(unit)
    return {
        container: sorted(units, key=lambda unit: (ranks[unit], unit))
        for container, units in placed.items()
    }


class Placement(NamedTuple):
    """Where one unit stands: its container, and the nearest unit both documents
    list before it there, None where no shared unit precedes it."""

    container: str | None
    after: str | None


def _placements(order: dict, shared: set) -> dict[str, Placement]:
    """Each unit of an order → its `Placement` there."""
    placements = {}
    for container, units in order.items():
        after = None
        for unit in units:
            placements.setdefault(unit, Placement(container, after))
            if unit in shared:
                after = unit
    return placements


def recorded_state(
    coordinate: tuple,
    event: dict,
    spec: dict,
    markup: tuple,
    projection: StateProjection,
    placements: dict,
):
    """What one version's markup shows at a coordinate in force, beside the state
    the fold leaves there: a pair the caller compares, or NO_RECORD for a verb with
    no record form. `markup` is a document's `(byid, attribute_marks,
    AuthoredOrders)`, and the fold is `projection` read on that document.

    Most record forms are the event's own detail. A position is a `Placement`,
    read on both sides from the whole fold: the unit's container and the nearest
    unit both documents list before it, which is the gap the user dropped it into.
    A version may add or drop cards around it, or rearrange cards away from it, and
    still say the same. `placements` caches each owner's placements on both sides
    across the calls one reading makes."""
    widget, unit, verb = coordinate
    record = spec.get("record")
    if not record:
        return NO_RECORD
    byid, marks, orders = markup
    if record["kind"] != "position":
        return markup_value(unit, spec, byid, marks), folded_value(event, spec)
    if (widget, verb) not in placements:
        shown = orders.of(widget, record)
        left = folded_positions(widget, verb, record, orders, projection)
        shared = {i for units in shown.values() for i in units} & {
            i for units in left.values() for i in units
        }
        placements[widget, verb] = (
            _placements(shown, shared),
            _placements(left, shared),
        )
    shown, left = placements[widget, verb]
    nowhere = Placement(None, None)
    return shown.get(unit, nowhere), left.get(unit, nowhere)


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


def obligation_value(
    owner, verb, spec, byid, marks, orders, projection, *, answered=False, unit=None
):
    """Read an obligation's typed value and presence from the canonical state fold.
    `marks` and `orders` are the document's `attribute_marks` and `AuthoredOrders`.

    Widget units use their declared record or custom action detail. Member units
    form one mapping, or the exact member when `unit` is supplied; positions retain
    every container, including empty ones.
    Empty authored values need completion to count as an answer; a value
    action in force counts even while completion is outstanding. Null never holds a value.
    """
    record = spec.get("record")
    # The owner's coordinates of this verb, or the one member's when `unit` names it.
    if unit is None:
        actions = {
            coordinate: held
            for coordinate, held in projection.actions_by_owner.get(owner, {}).items()
            if coordinate[2] == verb
        }
    else:
        held = projection.actions.get((owner, unit, verb))
        actions = {} if held is None else {(owner, unit, verb): held}
    if unit is not None:
        held = actions.get((owner, unit, verb))
        value = (folded_value(*held) if record else held[0]["detail"]) if held else None
    elif spec["unit"] == "widget":
        held = actions.get((owner, owner, verb))
        value = (
            (folded_value(*held) if record else held[0]["detail"])
            if held is not None
            else markup_value(owner, spec, byid, marks)
        )
    elif (record or {}).get("kind") == "position":
        value = folded_positions(owner, verb, record, orders, projection)
    else:
        value = {
            coordinate[1]: folded_value(*held) if record else held[0]["detail"]
            for coordinate, held in sorted(actions.items())
        }
    present = (
        value is not NO_RECORD
        and value is not None
        and (value not in ("", [], {}) or answered or bool(actions))
    )
    return (value if value is not NO_RECORD else None), present


def page_reading(
    reading: SourceReading,
    events: list,
    revision: int,
    *,
    revisions: Iterable[int] = (),
    revision_reader: Callable[[int], SourceReading] | None = None,
) -> PageReading:
    """Read one page's markup and log window through one construction.

    Document inspection and the passage readings used by `leaf thread create` and
    `page check` share declarations, floors, and the log window. The document's
    own reading (`SourceReading`) travels with the projection for callers that need
    its authored construction; a stored revision's is held across reads, and so is
    the fold over its page's log, which each read steps through what was appended
    since (`state_projection`). Revision history is optional transaction
    input: this owner selects predecessors newest first and reads each under its
    captured vocabulary, lazily when obligation registration needs it."""
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
            anchor=reading,
        ),
        (
            lambda: (
                (previous, revision_reader(previous))
                for previous in sorted(revisions, reverse=True)
                if revision_reader is not None and previous < revision
            )
        )
        if revision_reader is not None
        else None,
    )


def rewritten_bodies(actions: dict) -> dict:
    """id → (verb, text): the user's current rewrite of each element whose
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
    """Owner id → the children that creating actions in force supply, in log order.

    Each created child is its action's fold unit, so it stands on a coordinate of its
    own: a later action of another verb leaves it in force, and only an undo or a
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
    record: dict,
    projection: StateProjection,
    byid: dict,
    registry: dict,
) -> dict[str, set]:
    """Owner id → the current members the attribute `record` lets it name,
    including created children, for every owner `byid` holds, read in one pass over
    the document and its owners' coordinates.

    Position records in force determine membership, so moving a member changes the
    container that can select it in the same authoritative reading.
    """
    holders = projected_action_holders(projection, byid, registry)
    members: dict[str, set] = {}
    for oid in byid:
        if owner := recorded_owner(oid, record, byid, registry, holders=holders):
            members.setdefault(owner, set()).add(oid)
    for owner in byid:
        created = {
            coordinate[1]
            for coordinate, (_event, spec) in projection.desired_by_owner.get(owner, ())
            if spec.get("creates") and coordinate[1] not in byid
        }
        if created:
            members.setdefault(owner, set()).update(created)
    return members


def retirement_outcomes(actions: dict) -> dict:
    """widget id → the outcome its deciding action in force names.

    The registry explicitly marks the deciding verb (`decides`), whose `outcome`
    value `x-retired-when` and
    `x-withdrawn-as` name, so nothing here knows a widget or verb by name."""
    return {
        widget: e["detail"]["outcome"]
        for (widget, _unit, _verb), (e, spec) in actions.items()
        if decides(spec)
    }
