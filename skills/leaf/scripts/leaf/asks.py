"""Declaration-driven page and thread ask projections."""

from leaf.passages import page_passages
from leaf.projection import (
    FrozenThreadReading,
    StateProjection,
    enclosing_widgets,
    folded_facet,
    frozen_thread_reading,
    markup_facet,
    retirement_outcomes,
)


def local_ask_entry(entry: dict) -> bool:
    """Whether one widget entry originates an ask rather than aggregating it."""
    awaits = entry.get("x-awaits")
    return (awaits is not None and not awaits.get("rollup")) or entry.get(
        "x-request", {}
    ).get("ask") is True


def asking(attrs: dict, when: dict) -> bool:
    """The runtime's `asking`: every attribute `when` names holds one of the
    values that ask, a flag's two values being its presence and its absence."""
    return all(
        any(
            (attr in attrs) == value
            if isinstance(value, bool)
            else attrs.get(attr) == value
            for value in values
        )
        for attr, values in (when or {}).items()
    )


def replayed_attrs(rec: dict, projection: StateProjection) -> dict:
    """An element's attributes under the declared standing projection: authored
    markup overlaid with every surviving value record. The user's action holds
    one coordinate over a standing report, and independent facets coexist."""
    attrs = rec["attrs"]
    unit = attrs.get("id")
    if not unit:
        return attrs
    held = [
        winner
        for coordinate, winner in projection.desired.items()
        if coordinate[1] == unit
    ]
    for e, spec in sorted(held, key=lambda item: item[0]["seq"]):
        if (spec.get("record") or {}).get("kind") == "value":
            attrs = {**attrs, spec["record"]["attr"]: folded_facet(e, spec)}
    return attrs


def answered_verb(
    rec: dict,
    projection: StateProjection,
    verb: str,
    entry: dict,
    byid: dict,
    spk: dict,
    registry: dict,
) -> bool:
    """Whether one verb's own durable facet answers this widget.

    Most asks fold one widget-wide value. A completion gesture can instead
    leave its whole durable result on a named part (for example, the final card's
    destination); the owner coordinate and verb still identify that answer
    without a second private completion flag.
    """
    unit = rec["attrs"].get("id")
    spec = (entry.get("x-state") or {}).get(verb)
    if not spec or not unit:
        return False
    held = next(
        (
            winner
            for coordinate, winner in projection.actions.items()
            if coordinate[0] == unit and winner[0]["action"] == verb
        ),
        None,
    )
    record = spec.get("record")
    if spec["unit"] == "widget" and record and record["kind"] in ("attribute", "value"):
        facet = (
            folded_facet(*held)
            if held
            else markup_facet(unit, spec, byid, spk, registry)
        )
        return facet not in (None, "", [])
    return bool(
        held
        and held[0]["action"] == verb
        and completion_met(rec, spec, projection, byid, registry)
    )


def answered_ask(
    rec: dict,
    entry: dict,
    projection: StateProjection,
    byid: dict,
    spk: dict,
    registry: dict,
) -> bool:
    """Whether one of this request's explicit answer verbs stands."""
    return any(
        answered_verb(rec, projection, verb, entry, byid, spk, registry)
        for verb in (entry.get("x-awaits") or {}).get("answers", [])
    )


def seat_with_agent(
    rec: dict, entry: dict, projection: StateProjection, with_agent: set[str]
) -> bool:
    """Whether this widget's own conversation seat holds a thread now with the agent.

    Declaration-driven at both ends, the runtime's `seatWithAgent`: a widget with no
    x-conversation offers no seat, and one whose attributes miss the predicate has none
    placed on this instance either — so an element anchor written onto some other widget
    reaches nothing here. The seat's placement asks the same question of the same
    declaration, so the cell the reader can see and the request this takes off their
    list are one."""
    declaration = entry.get("x-conversation")
    unit = rec["attrs"].get("id")
    return bool(
        declaration
        and unit in with_agent
        and asking(replayed_attrs(rec, projection), declaration.get("when", {}))
    )


def quoted_in(rec: dict, registry: dict) -> bool:
    """The runtime's `quoted`: inside an element the registry marks x-exhibit,
    a widget is a mention rather than a use, and asks nothing.

    The holder chain answers it, which is the walk `enclosing_slot` makes and the
    one the runtime makes over the DOM. Asked of `spoken` instead, containment
    became a question about the page's words: the reading that says what stands
    around one widget walks every character of the version to do it, so an action
    POST on a 90KB page spent forty milliseconds finding out what a single id sat
    in. It reads a record rather than an id for the same reason the runtime takes
    an element — an element the author left unnamed stands where it stands."""
    return any(
        (registry.get(node["tag"]) or {}).get("x-exhibit")
        for node in enclosing_widgets(rec)
    )


def projected_action_holders(
    projection: StateProjection, byid: dict, registry: dict
) -> dict[str, dict]:
    """Unit id → its enclosing vocabulary widget after standing position records."""
    holders = {}
    for (_owner, unit, _facet), (event, spec) in projection.desired.items():
        record = spec.get("record") or {}
        if record.get("kind") != "position":
            continue
        target = byid.get(event["detail"][record["value"]])
        unit_rec = byid.get(unit)
        if target and unit_rec:
            holder = target if target["tag"] in registry else target.get("holder")
            permitted = (registry.get(unit_rec["tag"]) or {}).get("x-parent", [])
            if holder and holder["tag"] in permitted:
                holders[unit] = holder
    return holders


def completion_met(
    owner: dict,
    spec: dict,
    projection: StateProjection,
    byid: dict,
    registry: dict,
    positioned_holders: dict[str, dict] | None = None,
) -> bool:
    """Whether an answer's standing record leaves its declared completion state.

    Completion is a predicate over the same projected holder relation the position
    record changes. It is not another folded value: undoing or superseding the record
    therefore changes both the durable arrangement and whether the Ask is answered
    in one operation.
    """
    completion = spec.get("completion")
    if not completion:
        return True
    holders = (
        positioned_holders
        if positioned_holders is not None
        else projected_action_holders(projection, byid, registry)
    )

    def holder(record: dict):
        unit = record["attrs"].get("id")
        return holders.get(unit, record.get("holder"))

    def inside(record: dict, ancestor: dict) -> bool:
        seen = set()
        while record is not None and id(record) not in seen:
            if record is ancestor:
                return True
            seen.add(id(record))
            record = holder(record)
        return False

    empty = completion["empty"]
    containers = [
        record
        for record in byid.values()
        if record["tag"] == empty["within"]
        and inside(record, owner)
        and asking(record["attrs"], empty["when"])
    ]
    if len(containers) != 1:
        return False
    container = containers[0]
    return not any(
        record is not container
        and record["tag"] in registry
        and holder(record) is container
        for record in byid.values()
    )


class _AskReducer:
    """One page or frozen-thread ask fold over a shared state projection."""

    def __init__(
        self,
        source,
        projection,
        byid,
        spk,
        registry: dict,
        dropped: set,
        with_agent: set[str],
        *,
        thread: bool,
        request_phases: dict[str, str] | None = None,
        settled_away: set[str] | None = None,
    ):
        self.projection = projection
        self.byid = byid
        self.spk = spk
        self.registry = registry
        self.with_agent = with_agent
        self.thread = thread
        self.request_phases = request_phases or {}
        self.settled_away = settled_away or set()
        elements = source.lf_elements if hasattr(source, "lf_elements") else source
        self.records = [record for record in elements if self._is_declared(record)]
        self.positioned_holders = projected_action_holders(projection, byid, registry)

        self.exists: dict[int, bool] = {}
        self.local: dict[int, bool] = {}
        for record in self.records:
            unit = record["attrs"].get("id")
            self.exists[id(record)] = not (
                (unit and unit in dropped) or quoted_in(record, registry)
            )
            self.local[id(record)] = self.exists[id(record)] and self._local(record)

        self.direct: dict[int, list] = {}
        for record in self.records:
            if owner := self._rollup_owner(record):
                self.direct.setdefault(id(owner), []).append(record)
        self.values: dict[int, bool] = {}

    def _entry(self, record):
        return self.registry[record["tag"]]

    def _is_request(self, record):
        return self._entry(record).get("x-request", {}).get("ask") is True

    def _is_declared(self, record):
        entry = self.registry.get(record["tag"]) or {}
        return (
            entry.get("x-awaits") is not None
            or entry.get("x-request", {}).get("ask") is True
        )

    def _declaration(self, record):
        return self._entry(record).get("x-awaits", {})

    def _local(self, record):
        if self._is_request(record):
            return self.request_phases.get(record["attrs"].get("id")) == "ready"
        if self._declaration(record).get("rollup"):
            return False
        return asking(
            replayed_attrs(record, self.projection),
            self._declaration(record).get("when"),
        )

    def _holder(self, record):
        unit = record["attrs"].get("id")
        return self.positioned_holders.get(unit, record.get("holder"))

    def _answered(self, record):
        entry = self._entry(record)
        if self._is_request(record):
            return not self.local[id(record)]
        if self.thread:
            if not entry.get("x-state"):
                return True
            until = self._declaration(record).get("until")
            attrs = replayed_attrs(record, self.projection)
            if until and asking(attrs, until["when"]):
                unit = record["attrs"].get("id")
                return any(
                    action["widget"] == unit and action["action"] == until["verb"]
                    for action, _spec in self.projection.actions.values()
                )
        return answered_ask(
            record,
            entry,
            self.projection,
            self.byid,
            self.spk,
            self.registry,
        ) or seat_with_agent(
            record,
            entry,
            self.projection,
            self.with_agent,
        )

    def _rollup_owner(self, record):
        record = self._holder(record)
        while record:
            if self._declaration(record).get("rollup"):
                return record
            record = self._holder(record)
        return None

    def _awaits(self, record):
        key = id(record)
        if key in self.values:
            return self.values[key]
        if not self.exists[key]:
            self.values[key] = False
            return False
        declaration = self._declaration(record)
        if not declaration.get("rollup"):
            self.values[key] = self.local[key] and not self._answered(record)
            return self.values[key]
        descendants = self.direct.get(key, [])
        self.values[key] = any(self._awaits(candidate) for candidate in descendants)
        return self.values[key]

    def _surfaces(self, records):
        visible = [
            record for record in records if not self._declaration(record).get("rollup")
        ]
        surfaces = []
        seen = set()
        for record in visible:
            surface = record
            holder = self._holder(record)
            while holder:
                if (self.registry.get(holder["tag"]) or {}).get("x-ask-surface"):
                    surface = holder
                    break
                holder = self._holder(holder)
            if id(surface) not in seen:
                seen.add(id(surface))
                surfaces.append(surface)
        return surfaces

    def inventory(self) -> list:
        """Every active Ask, including ones the reader has answered.

        An action Ask remains active while its authored `when` holds, even after
        one of its answer verbs has state. A request Ask remains the instruction
        the page asked throughout its one lifecycle; accepting it changes who owns the
        turn rather than erasing the Ask. Roll-ups continue to aggregate without
        originating a visible Ask of their own.
        """
        active = []
        for record in self.records:
            if self.exists[id(record)] and (
                self._is_request(record) or self.local[id(record)]
            ):
                active.append(record)
                continue
            # An ask that retires its own last visible slot still has a receipt
            # and Undo control in the margin. Keep that completed route until a new
            # revision removes the authored source. A source retired by some other
            # ask is absent rather than reviewable, and is not in settled_away.
            unit = record["attrs"].get("id")
            if (
                unit in self.settled_away
                and not self._is_request(record)
                and self._local(record)
                and self._answered(record)
            ):
                active.append(record)
        return self._items(self._surfaces(active))

    def _items(self, surfaces):
        return [
            {
                "id": record["attrs"].get("id"),
                "tag": record["tag"],
                "thread": None,
            }
            for record in surfaces
        ]

    def result(self) -> tuple[list, dict[str, bool]]:
        surfaces = self._surfaces(
            record for record in self.records if self._awaits(record)
        )
        return (
            self._items(surfaces),
            {
                record["attrs"]["id"]: self.values[id(record)]
                for record in self.records
                if record["attrs"].get("id")
            },
        )


def page_ask_projection(
    source,
    projection,
    byid,
    spk,
    registry: dict,
    dropped: set,
    with_agent: set[str],
    *,
    thread: bool = False,
    request_phases: dict[str, str] | None = None,
) -> tuple[list, dict[str, bool]]:
    """The page's visible asks and exact awaiting value for every declared target.

    An ordinary x-awaits instance is its local condition minus an explicit answer.
    A roll-up projects the logical OR of its nearest local asks and child roll-ups
    through a nested plan without originating one.

    An x-request.ask instance is local exactly while its canonical lifecycle is ready.
    Its pending and completed phases hand the turn away from the reader; failure
    returns the lifecycle to ready and therefore reopens the ask.

    `with_agent` chooses which question this answers, and is the whole of the
    difference between the two. Given `seats_with_agent`, it is the reader's list: a
    ask whose own conversation seat holds a thread the agent owes an answer to is
    not one the reader has to deal with, whatever its state. Given an empty set, it is
    whether the ask is answered at all, which is what an action's `requires` asks
    — a conversation does not answer a question the widget still holds no state for,
    and refusing the pick over the reader's own remark would refuse them the answer
    they were asked for. Frozen thread markup seats no conversation either way.
    """
    return _AskReducer(
        source,
        projection,
        byid,
        spk,
        registry,
        dropped,
        with_agent,
        thread=thread,
        request_phases=request_phases,
    ).result()


def page_asks(
    parser,
    projection,
    byid,
    spk,
    registry: dict,
    dropped: set,
    with_agent: set[str],
    request_phases: dict[str, str] | None = None,
) -> list:
    return page_ask_projection(
        parser,
        projection,
        byid,
        spk,
        registry,
        dropped,
        with_agent,
        request_phases=request_phases,
    )[0]


def page_awaiting_values(
    html,
    parser,
    projection,
    spk,
    registry: dict,
    request_phases: dict[str, str] | None = None,
) -> dict:
    """Each current page ask's declaration-driven awaiting value."""
    passages = page_passages(
        html, registry, retirement_outcomes(projection.actions, registry)
    )
    return page_ask_projection(
        parser,
        projection,
        parser.by_id,
        spk,
        registry,
        set(passages.retired) | set(passages.gone),
        set(),
        request_phases=request_phases,
    )[1]


def page_ask_inventory(
    source,
    projection,
    byid,
    spk,
    registry: dict,
    dropped: set,
    *,
    thread: bool = False,
    request_phases: dict[str, str] | None = None,
    settled_away: set[str] | None = None,
) -> list:
    """Every active Ask surface, answered or not, for progress and review."""
    return _AskReducer(
        source,
        projection,
        byid,
        spk,
        registry,
        dropped,
        set(),
        thread=thread,
        request_phases=request_phases,
        settled_away=settled_away,
    ).inventory()


def _thread_ask_records(
    events: list, settled: set, reading: FrozenThreadReading
) -> tuple[list, dict]:
    records = []
    for e in events:
        if e["kind"] not in ("comment", "reply"):
            continue
        markup = e.get("markup")
        if not markup or reading.roots[e["id"]] in settled:
            continue
        fragment = reading.structure.fragments[e["id"]]
        records.extend((reading.roots[e["id"]], rec) for rec in fragment.lf_elements)
    return records, {rec["attrs"].get("id"): thread for thread, rec in records}


def thread_ask_projection(
    events: list,
    registry: dict,
    settled: set,
    *,
    reading: FrozenThreadReading | None = None,
    request_phases: dict[str, str] | None = None,
) -> tuple[list, dict]:
    """Open Asks standing in thread markup, read from the log.

    A fragment is frozen: no version answers it and no `restated`
    retracts it, so every action on its widgets stands (no floors, no window).
    A widget with an action ask or request ask can stand in a thread. `until`
    holds a matching action ask open until the reader has posted the verb it names,
    while a request ask follows its frozen-document request lifecycle.

    `settled` is the root ids of the closed threads, whose asks went with them —
    the question was the thread's, and the panel's own reading takes a closed
    thread's mark off the page for the same reason. Without it, a question the
    agent asked and then withdrew by resolving stays on the banner's count for
    the life of the page, and the walk that steps to it lands in a shut
    disclosure."""
    thread_reading = reading or frozen_thread_reading(events, registry)
    records, thread_by_id = _thread_ask_records(events, settled, thread_reading)

    asks, values = page_ask_projection(
        [rec for _thread, rec in records],
        thread_reading.projection,
        thread_reading.by_id,
        thread_reading.spoken,
        registry,
        dropped=set(),
        # Frozen thread markup seats no conversation of its own: the thread's reply
        # box is already where the reader answers, so only an action closes a request
        # here.
        with_agent=set(),
        thread=True,
        request_phases=request_phases,
    )
    return (
        [{**ask, "thread": thread_by_id[ask["id"]]} for ask in asks],
        values,
    )


def thread_ask_inventory(
    events: list,
    registry: dict,
    settled: set,
    *,
    reading: FrozenThreadReading | None = None,
    request_phases: dict[str, str] | None = None,
) -> list:
    """Every active Ask in unresolved frozen thread markup."""
    thread_reading = reading or frozen_thread_reading(events, registry)
    records, thread_by_id = _thread_ask_records(events, settled, thread_reading)
    asks = page_ask_inventory(
        [rec for _thread, rec in records],
        thread_reading.projection,
        thread_reading.by_id,
        thread_reading.spoken,
        registry,
        set(),
        thread=True,
        request_phases=request_phases,
    )
    return [{**ask, "thread": thread_by_id[ask["id"]]} for ask in asks]


def thread_asks(
    events: list,
    registry: dict,
    settled: set,
    request_phases: dict[str, str] | None = None,
    *,
    reading: FrozenThreadReading | None = None,
) -> list:
    return thread_ask_projection(
        events,
        registry,
        settled,
        reading=reading,
        request_phases=request_phases,
    )[0]
