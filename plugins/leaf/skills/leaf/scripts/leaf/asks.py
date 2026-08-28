"""Declaration-driven page and thread ask projections."""

from leaf.passages import page_passages, spoken
from leaf.projection import (
    StateProjection,
    decisions,
    enclosing_widgets,
    folded_facet,
    markup_facet,
    state_coordinate,
    state_projection,
)
from leaf.thread_context import thread_roots, thread_structure


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
    """Whether one verb's own durable facet answers this widget."""
    unit = rec["attrs"].get("id")
    spec = (entry.get("x-state") or {}).get(verb)
    if not spec or not unit:
        return False
    held = projection.actions.get(state_coordinate(unit, unit, spec))
    record = spec.get("record")
    if record and record["kind"] in ("attribute", "value"):
        facet = (
            folded_facet(*held)
            if held
            else markup_facet(unit, spec, byid, spk, registry)
        )
        return facet not in (None, "", [])
    return bool(held and held[0]["action"] == verb)


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


class _AskReducer:
    """One page or frozen-thread request fold over a shared state projection."""

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
    ):
        self.projection = projection
        self.byid = byid
        self.spk = spk
        self.registry = registry
        self.with_agent = with_agent
        self.thread = thread
        elements = source.lf_elements if hasattr(source, "lf_elements") else source
        self.records = [
            record
            for record in elements
            if (registry.get(record["tag"]) or {}).get("x-awaits") is not None
        ]
        self.positioned_holders = projected_action_holders(projection, byid, registry)

        self.exists: dict[int, bool] = {}
        self.local: dict[int, bool] = {}
        for record in self.records:
            unit = record["attrs"].get("id")
            self.exists[id(record)] = not (
                (unit and unit in dropped) or quoted_in(record, registry)
            )
            self.local[id(record)] = self.exists[id(record)] and asking(
                replayed_attrs(record, projection),
                self._entry(record)["x-awaits"].get("when"),
            )

        self.direct: dict[int, list] = {}
        for record in self.records:
            if owner := self._rollup_owner(record):
                self.direct.setdefault(id(owner), []).append(record)
        self.values: dict[int, bool] = {}

    def _entry(self, record):
        return self.registry[record["tag"]]

    def _holder(self, record):
        unit = record["attrs"].get("id")
        return self.positioned_holders.get(unit, record.get("holder"))

    def _contains(self, ancestor, record):
        while record:
            if record is ancestor:
                return True
            record = self._holder(record)
        return False

    def _answered(self, record):
        entry = self._entry(record)
        if self.thread:
            if not entry.get("x-state"):
                return True
            until = entry["x-awaits"].get("until")
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
            if (
                (self.registry.get(record["tag"]) or {})
                .get("x-awaits", {})
                .get("rollup")
            ):
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
        if not self.local[key]:
            self.values[key] = False
            return False
        declaration = self._entry(record)["x-awaits"]
        if not declaration.get("rollup"):
            self.values[key] = not self._answered(record)
            return self.values[key]
        descendants = self.direct.get(key, [])
        interventions = [
            candidate
            for candidate in descendants
            if not self._entry(candidate)["x-awaits"].get("rollup")
            and self.local[id(candidate)]
        ]
        if interventions:
            self.values[key] = any(
                self._awaits(candidate) for candidate in interventions
            )
            return self.values[key]
        children = [
            candidate
            for candidate in descendants
            if self._entry(candidate)["x-awaits"].get("rollup")
        ]
        self.values[key] = (
            any(self._awaits(candidate) for candidate in children)
            if children
            else not self._answered(record)
        )
        return self.values[key]

    def _surfaces(self):
        open_records = [record for record in self.records if self._awaits(record)]
        visible = [
            record
            for record in open_records
            if not self._entry(record)["x-awaits"].get("rollup")
            or not any(
                inner is not record and self._contains(record, inner)
                for inner in open_records
            )
        ]
        surfaces = []
        seen = set()
        for record in visible:
            surface = record
            holder = self._holder(record)
            while holder:
                if (self.registry.get(holder["tag"]) or {}).get("x-ask"):
                    surface = holder
                    break
                holder = self._holder(holder)
            if id(surface) not in seen:
                seen.add(id(surface))
                surfaces.append(surface)
        return surfaces

    def result(self) -> tuple[list, dict[str, bool]]:
        surfaces = self._surfaces()
        return (
            [
                {
                    "id": record["attrs"].get("id"),
                    "tag": record["tag"],
                    "thread": None,
                }
                for record in surfaces
            ],
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
) -> tuple[list, dict[str, bool]]:
    """The page's visible asks and exact awaiting value for every declared target.

    An ordinary x-awaits instance is its local condition minus an explicit answer.
    A roll-up projects the same fact through a nested plan: a false local condition
    stops; direct ordinary interventions take precedence;
    otherwise child roll-ups recurse; a matching leaf waits. The browser implements
    this reducer over the DOM and the same standing fold.

    `with_agent` chooses which question this answers, and is the whole of the
    difference between the two. Given `seats_with_agent`, it is the reader's list: a
    request whose own conversation seat holds a thread the agent owes an answer to is
    not one the reader has to deal with, whatever its state. Given an empty set, it is
    whether the request is answered at all, which is what an action's `requires` asks
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
    ).result()


def page_asks(
    parser,
    projection,
    byid,
    spk,
    registry: dict,
    dropped: set,
    with_agent: set[str],
) -> list:
    return page_ask_projection(
        parser, projection, byid, spk, registry, dropped, with_agent
    )[0]


def page_awaiting_values(html, parser, projection, spk, registry: dict) -> dict:
    """Each current page request's declaration-driven awaiting value."""
    passages = page_passages(html, registry, decisions(projection.actions, registry))
    return page_ask_projection(
        parser,
        projection,
        parser.by_id,
        spk,
        registry,
        set(passages.retired) | set(passages.gone),
        set(),
    )[1]


def thread_ask_projection(
    events: list, registry: dict, settled: set
) -> tuple[list, dict]:
    """Asks standing in thread markup — the runtime's `answeredThreadAsk` read
    from the log. A fragment is frozen: no version answers it and no `restated`
    retracts it, so every action on its widgets stands (no floors, no window).
    Only a widget with an action channel asks in a thread at all, and `until`
    holds a matching ask open until the reader has posted the verb it names.

    `settled` is the root ids of the closed threads, whose asks went with them —
    the question was the thread's, and the panel's own reading takes a closed
    thread's mark off the page for the same reason. Without it, a question the
    agent asked and then withdrew by resolving stays on the banner's count for
    the life of the page, and the walk that steps to it lands in a shut
    disclosure."""
    structure = thread_structure(events)
    records, byid, spk = [], {}, {}
    thread_of = thread_roots(events)
    for e in events:
        if e["kind"] not in ("comment", "reply"):
            continue
        markup = e.get("markup")
        if not markup or thread_of[e["id"]] in settled:
            continue
        frag = structure.fragments[e["id"]]
        byid.update(frag.by_id)
        spk.update(spoken(markup, registry))
        records.extend((thread_of[e["id"]], rec) for rec in frag.lf_elements)
    projection = state_projection(events, byid, spk, registry, None, {})

    asks, values = page_ask_projection(
        [rec for _thread, rec in records],
        projection,
        byid,
        spk,
        registry,
        dropped=set(),
        # Frozen thread markup seats no conversation of its own: the thread's reply
        # box is already where the reader answers, so only an action closes a request
        # here.
        with_agent=set(),
        thread=True,
    )
    thread_by_id = {rec["attrs"].get("id"): thread for thread, rec in records}
    return ([{**ask, "thread": thread_by_id[ask["id"]]} for ask in asks], values)


def thread_asks(events: list, registry: dict, settled: set) -> list:
    return thread_ask_projection(events, registry, settled)[0]
