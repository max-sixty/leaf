"""Declaration-driven page and thread ask projections."""

from leaf.projection import (
    FrozenThreadReading,
    StateProjection,
    enclosing_widgets,
    folded_value,
    frozen_thread_reading,
    markup_value,
)
from leaf.schema import MESSAGE_KINDS


def local_ask_entry(entry: dict) -> bool:
    """Whether one widget declaration originates an ask rather than aggregating it."""
    awaits = entry.get("x-awaits")
    return (awaits is not None and not awaits.get("rollup")) or entry.get(
        "x-request", {}
    ).get("ask") is True


def asking(attrs: dict, when: dict) -> bool:
    """Every attribute `when` names holds one of the values that ask, a flag's
    two values being its presence and its absence."""
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
    one coordinate over a standing report, and independent verbs coexist."""
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
            attrs = {**attrs, spec["record"]["attr"]: folded_value(e, spec)}
    return attrs


def answer_verbs(entry: dict) -> dict:
    """Each x-state verb whose standing state answers this widget's local Ask,
    mapped to the condition that state has to meet (x-awaits.answered)."""
    return (entry.get("x-awaits") or {}).get("answered") or {}


def answers_ask(record: dict, entry: dict, verb: str) -> bool:
    """Whether a user's verb on one authored widget is part of that widget's own
    Ask's answer: the authored instance asks, and x-awaits names the verb among
    those whose state answers it. Every swipe on a deck is part of the answer the
    last one completes, and so is a pick on a group whose Done answers it. A
    roll-up originates no Ask."""
    awaits = entry.get("x-awaits") or {}
    if awaits.get("rollup") or not asking(record["attrs"], awaits.get("when")):
        return False
    return verb in answer_verbs(entry)


def verb_answers(
    rec: dict,
    entry: dict,
    verb: str,
    projection: StateProjection,
    byid: dict,
    spk: dict,
    registry: dict,
    holders: dict[str, dict],
) -> bool:
    """Whether one answering verb's declared condition holds for this widget now.

    The condition reads standing state and nothing else. `empty` asks the projected
    containment the verb's position records leave; an attribute or value record reads
    through authored markup as well as the fold, so a version that honors the answer
    keeps it answered and a cleared value opens the Ask again; any other verb answers
    while one of its actions stands on the widget.
    """
    condition = answer_verbs(entry)[verb]
    if not asking(replayed_attrs(rec, projection), condition.get("when")):
        return False
    if empty := condition.get("empty"):
        return container_empty(rec, empty, byid, registry, holders)
    # A condition without `empty` names a widget-unit verb (registry validation), so
    # its standing action is the one at the widget's own coordinate for the verb.
    unit = rec["attrs"].get("id")
    held = projection.actions.get((unit, unit, verb))
    spec = entry["x-state"][verb]
    record = spec.get("record")
    if record and record["kind"] in ("attribute", "value"):
        value = (
            folded_value(*held)
            if held
            else markup_value(unit, spec, byid, spk, registry)
        )
        return value not in (None, "", [])
    return held is not None


def ask_answered(
    rec: dict,
    entry: dict,
    projection: StateProjection,
    byid: dict,
    spk: dict,
    registry: dict,
    holders: dict[str, dict] | None = None,
) -> bool:
    """Whether the user's own state answers this Ask: one of its answering verbs'
    conditions holds."""
    if holders is None:
        holders = projected_action_holders(projection, byid, registry)
    return any(
        verb_answers(rec, entry, verb, projection, byid, spk, registry, holders)
        for verb in answer_verbs(entry)
    )


def seat_with_agent(
    rec: dict, entry: dict, projection: StateProjection, with_agent: set[str]
) -> bool:
    """Whether this widget's own conversation seat holds a thread now with the agent.

    Declaration-driven at both ends: a widget with no x-conversation offers no
    seat, and one whose attributes miss the predicate has none placed on this
    instance either — so an element anchor written onto some other widget reaches
    nothing here. The seat's placement asks the same question of the same
    declaration, so the cell the user can see and the request this takes off their
    list are one."""
    declaration = entry.get("x-conversation")
    unit = rec["attrs"].get("id")
    return bool(
        declaration
        and unit in with_agent
        and asking(replayed_attrs(rec, projection), declaration.get("when", {}))
    )


def quoted_in(rec: dict, registry: dict) -> bool:
    """Inside an element the registry marks x-exhibit, a widget is a mention
    rather than a use, and asks nothing.

    The holder chain answers it, which is the walk `enclosing_slot` makes and the
    one `quotedBy` makes over the DOM for a descriptor's own `quoted` flag. Asked of
    `spoken` instead, containment became a question about the page's words: the
    reading that says what stands around one widget walks every character of the
    version to do it, so an action POST on a 90KB page spent forty milliseconds
    finding out what a single id sat in. It reads a record rather than an id for the
    same reason `quotedBy` takes an element — an element the author left unnamed
    stands where it stands."""
    return any(
        (registry.get(node["tag"]) or {}).get("x-exhibit")
        for node in enclosing_widgets(rec)
    )


def projected_action_holders(
    projection: StateProjection, byid: dict, registry: dict
) -> dict[str, dict]:
    """Unit id → its enclosing vocabulary widget after standing position records."""
    holders = {}
    for (_owner, unit, _verb), (event, spec) in projection.desired.items():
        record = spec.get("record") or {}
        if record.get("kind") != "position":
            continue
        target = byid.get(event["detail"][record["value"]])
        unit_rec = byid.get(unit)
        if target and unit_rec:
            holder = target if target["tag"] in registry else target.get("holder")
            permitted = (registry.get(unit_rec["tag"]) or {}).get("x-owners", [])
            if holder and holder["tag"] in permitted:
                holders[unit] = holder
    return holders


def container_empty(
    owner: dict,
    empty: dict,
    byid: dict,
    registry: dict,
    holders: dict[str, dict],
) -> bool:
    """Whether the one member container `empty` names inside `owner` holds no
    vocabulary members under the projected holder relation.

    A predicate over the same containment the position records change, so undoing
    or superseding one moves the arrangement and the answer in one operation.
    """

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


def answering_action(
    rec: dict,
    entry: dict,
    verb: str,
    projection: StateProjection,
    byid: dict,
    spk: dict,
    registry: dict,
) -> bool:
    """Whether an action of `verb`, standing in `projection`, answers its widget's
    Ask: the instance asks, and the verb's own condition holds with it in place.
    Admission stamps `meaning.answer` on exactly these."""
    awaits = entry.get("x-awaits") or {}
    return (
        verb in answer_verbs(entry)
        and not awaits.get("rollup")
        and asking(replayed_attrs(rec, projection), awaits.get("when"))
        and verb_answers(
            rec,
            entry,
            verb,
            projection,
            byid,
            spk,
            registry,
            projected_action_holders(projection, byid, registry),
        )
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
        *,
        thread: bool,
        request_phases: dict[str, str] | None = None,
    ):
        self.projection = projection
        self.byid = byid
        self.spk = spk
        self.registry = registry
        self.thread = thread
        self.request_phases = request_phases or {}
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

    def _answered(self, record, with_agent):
        entry = self._entry(record)
        if self._is_request(record):
            return not self.local[id(record)]
        if self.thread and not entry.get("x-state"):
            return True
        return ask_answered(
            record,
            entry,
            self.projection,
            self.byid,
            self.spk,
            self.registry,
            self.positioned_holders,
        ) or seat_with_agent(
            record,
            entry,
            self.projection,
            with_agent,
        )

    def _rollup_owner(self, record):
        record = self._holder(record)
        while record:
            if self._declaration(record).get("rollup"):
                return record
            record = self._holder(record)
        return None

    def _awaits(self, record, with_agent, values):
        key = id(record)
        if key in values:
            return values[key]
        if not self.exists[key]:
            values[key] = False
            return False
        declaration = self._declaration(record)
        if not declaration.get("rollup"):
            values[key] = self.local[key] and not self._answered(record, with_agent)
            return values[key]
        descendants = self.direct.get(key, [])
        values[key] = any(
            self._awaits(candidate, with_agent, values) for candidate in descendants
        )
        return values[key]

    def _surfaces(self, records):
        """Each visible ask as `(surface, source)`.

        The surface is the reading and arrival region the user is sent to; the
        source is the widget that answers. They are the same record unless an
        `x-ask-surface` holder encloses it. One surface stands for one ask, so a
        later source inside a region already listed is dropped.
        """
        visible = [
            record for record in records if not self._declaration(record).get("rollup")
        ]
        pairs = []
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
                pairs.append((surface, record))
        return pairs

    def inventory(self, settled_away: set[str]) -> list:
        """Every active Ask, including ones the user has answered.

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
                unit in settled_away
                and not self._is_request(record)
                and self._local(record)
                and self._answered(record, set())
            ):
                active.append(record)
        return self._items(self._surfaces(active))

    def _items(self, pairs):
        return [
            {
                "id": surface["attrs"].get("id"),
                "tag": surface["tag"],
                "source": source["attrs"].get("id"),
                "source_tag": source["tag"],
                "conversation": None,
            }
            for surface, source in pairs
        ]

    def result(self, with_agent: set[str]) -> tuple[list, dict[str, bool]]:
        values: dict[int, bool] = {}
        surfaces = self._surfaces(
            record
            for record in self.records
            if self._awaits(record, with_agent, values)
        )
        return (
            self._items(surfaces),
            {
                record["attrs"]["id"]: values[id(record)]
                for record in self.records
                if record["attrs"].get("id")
            },
        )


def page_ask_readings(
    source,
    projection,
    byid,
    spk,
    registry: dict,
    dropped: set,
    with_agent: set[str],
    *,
    request_phases: dict[str, str] | None = None,
    settled_away: set[str] | None = None,
) -> dict:
    """Every ask reading of one document, folded over one shared setup.

    A document is read for three answers at once: the user's own list, the same
    question with no conversation seats (whether each Ask is answered at all, which
    a sign-off reads), and the inventory of every active Ask. They differ only in `with_agent` and
    `settled_away`; the declared records, their holders, and their local conditions
    are one computation behind all three.

    `with_agent` is what separates the user's list from the rest. Given
    `seats_with_agent`, an ask whose own conversation seat holds a thread the agent
    owes an answer to is not one the user has to deal with, whatever its state.
    The same fold with no seats says whether the ask is answered at all: a
    conversation does not answer a question the widget still holds no state for, and
    refusing the pick over the user's own remark would refuse them the answer they
    were asked for.
    """
    reducer = _AskReducer(
        source,
        projection,
        byid,
        spk,
        registry,
        dropped,
        thread=False,
        request_phases=request_phases,
    )
    user, awaiting = reducer.result(with_agent)
    unanswered, _ = reducer.result(set())
    return {
        "all": reducer.inventory(settled_away or set()),
        "user": user,
        "unanswered": unanswered,
        "awaiting": awaiting,
    }


def _thread_ask_records(
    events: list, settled: set, reading: FrozenThreadReading
) -> tuple[list, dict]:
    records = []
    for e in events:
        if e["kind"] not in MESSAGE_KINDS:
            continue
        markup = e.get("markup")
        if not markup or reading.roots[e["id"]] in settled:
            continue
        fragment = reading.structure.fragments[e["id"]]
        records.extend((reading.roots[e["id"]], rec) for rec in fragment.lf_elements)
    return records, {rec["attrs"].get("id"): thread for thread, rec in records}


def thread_ask_readings(
    events: list,
    registry: dict,
    settled: set,
    *,
    reading: FrozenThreadReading | None = None,
    request_phases: dict[str, str] | None = None,
) -> dict:
    """Every ask reading of the open frozen thread markup, over one shared fold.

    A fragment is frozen: no version answers it and no `restated`
    retracts it, so every action on its widgets stands (no floors, no window).
    A widget with an action ask or request ask can stand in a thread. An action
    ask is answered by the same declared state condition as on the page, while a
    request ask follows its frozen-document request lifecycle.

    Frozen thread markup seats no conversation of its own — the thread's reply box
    is already where the user answers — so the user's list and the unanswered
    list are one reading here. `page_ask_readings` is where the seats separate them.

    `settled` is the root ids of the closed threads, whose asks went with them —
    the question was the thread's, and the panel's own reading takes a closed
    thread's mark off the page for the same reason. Without it, a question the
    agent asked and then withdrew by resolving stays on the banner's count for
    the life of the page, and the walk that steps to it lands in a shut
    disclosure.
    """
    thread_reading = reading or frozen_thread_reading(events, registry)
    records, thread_by_id = _thread_ask_records(events, settled, thread_reading)
    reducer = _AskReducer(
        [rec for _thread, rec in records],
        thread_reading.projection,
        thread_reading.by_id,
        thread_reading.spoken,
        registry,
        set(),
        thread=True,
        request_phases=request_phases,
    )
    asks, awaiting = reducer.result(set())

    def seated(items: list) -> list:
        return [{**ask, "conversation": thread_by_id[ask["source"]]} for ask in items]

    return {
        "all": seated(reducer.inventory(set())),
        "user": seated(asks),
        "unanswered": seated(asks),
        "awaiting": awaiting,
    }
