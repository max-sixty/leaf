"""Compile admitted widget commands into durable semantic facts.

The log keeps direct identities, never a snapshot of their ancestor tree. A
projection tests those identities against the document it reads, so moving a
referenced element still changes containment without changing an old event.
"""

from functools import cached_property

from leaf.asks import answer_verbs, answering_action
from leaf.events import event_document
from leaf.projection import frozen_thread_reading, page_reading, with_action
from leaf.thread_context import thread_structure


class AdmissionReadings:
    """The page and frozen-thread readings one admission folds, each built once.

    The contract gates and the meaning stamped after them read the same log, so
    they share one fold of it rather than each paying for their own."""

    def __init__(self, events: list, registry: dict):
        self.events = events
        self.registry = registry
        self._pages: dict = {}

    @cached_property
    def thread(self):
        return frozen_thread_reading(self.events, self.registry)

    def page(self, document, revision: int):
        if revision not in self._pages:
            self._pages[revision] = page_reading(
                document, self.events, self.registry, revision
            )
        return self._pages[revision]


def direct_dependencies(event: dict, spec: dict) -> list[str]:
    """The owner, fold unit, and recorded identities before canonical ordering."""
    detail = event["detail"]
    owner = event["widget"]
    unit = owner if spec["unit"] == "widget" else detail[spec["unit"]]
    fields = []
    record = spec.get("record") or {}
    if record.get("kind") in {"attribute", "position"}:
        fields.append(record["value"])
    dependencies = [owner, unit]
    for field in fields:
        value = detail.get(field)
        if value is not None:
            dependencies.extend(value if isinstance(value, list) else [value])
    return dependencies


def state_meaning(event: dict, entry: dict, scope: str) -> dict:
    """Resolve one validated verb using its sending document's declaration.

    Only what a registry-free reader cannot recover from the event is stored: the
    fold unit, the identities the declared record fields name, and a created
    child's tag. The owner and verb are the event's `widget` and `action`, and the
    scope with the event's revision names its document (`events.event_coordinate`,
    `events.event_document`)."""
    spec = entry["x-state"][event["action"]]
    dependencies = direct_dependencies(event, spec)
    meaning = {
        "scope": scope,
        "unit": dependencies[1],
        "depends": sorted(set(dependencies)),
    }
    # A created child's unit is new, so no document may yet hold it. Stamping its
    # tag lets registry-free readers keep the action resting on it regardless.
    if creates := spec.get("creates"):
        meaning["creates"] = creates["child"]
    # A move places its unit by a rank only until a version takes it in, and a
    # registry-free reader asks which actions those are (`UndoReading`).
    if (spec.get("record") or {}).get("kind") == "position":
        meaning["places"] = True
    return meaning


def answer_meaning(
    sender, record: dict, event: dict, readings: AdmissionReadings
) -> tuple[bool, str | None]:
    """Whether this admitted action answers its widget's Ask, and the thread it closes.

    The answering action is the one whose admission makes the Ask's declared state
    condition hold, so it is read with the candidate standing in the fold of its own
    document. The thread it closes is the widget's authored `resolves`, read from the
    immutable document that sent it rather than carried in the command. A decision
    whose outcome is the widget's `x-withdrawn-as` leaves the page as if nothing had
    been proposed, so it answers the Ask and closes no thread: turning a fix down
    leaves the question it was written for open."""
    registry = readings.registry
    entry = registry[record["tag"]]
    if event["kind"] != "action" or event["action"] not in answer_verbs(entry):
        return False, None
    withdrawn = entry.get("x-withdrawn-as")
    declined = withdrawn is not None and event["detail"].get("outcome") == withdrawn
    if event_document(event)["kind"] == "page":
        reading = readings.page(sender, event["revision"])
        byid = sender.by_id
    else:
        reading = readings.thread
        byid = reading.by_id
    candidate = {**event, "id": "pending", "seq": len(readings.events) + 1}
    projection = with_action(
        reading.projection, candidate, entry["x-state"][event["action"]]
    )
    return (
        answering_action(
            byid[event["widget"]],
            entry,
            event["action"],
            projection,
            byid,
            reading.spoken,
            registry,
        ),
        None if declined else record["attrs"].get("resolves"),
    )


def request_unit(event: dict, spec: dict) -> str:
    """The request seat uses the holder unless its verb names a detail field."""
    return event["detail"][spec["unit"]] if "unit" in spec else event["widget"]


def admit_widget_event(sender, event: dict, readings: AdmissionReadings) -> dict:
    """Stamp server-owned meaning after command validation, under the append lock.

    `sender` is the authored document of the revision the command names."""
    events, registry = readings.events, readings.registry
    record = sender.by_id.get(event["widget"])
    scope = "page"
    if record is None:
        record = thread_structure(events).by_id[event["widget"]]
        scope = "thread"
    entry = registry[record["tag"]]
    admitted = dict(event)
    if event["kind"] == "request":
        spec = entry["x-request"]["verbs"][event["action"]]
        unit = request_unit(event, spec)
        admitted["meaning"] = {"scope": scope, "unit": unit}
    else:
        admitted["meaning"] = state_meaning(event, entry, scope)
        answers, closes = answer_meaning(sender, record, admitted, readings)
        if answers:
            admitted["meaning"]["answer"] = closes
    return admitted


def admitted_contract_error(
    event: dict, page, thread, registry: dict, recorded_registry: dict, *, recorded_page
) -> str | None:
    """Reject a candidate registry that would read one admitted command differently.

    The stored meaning already fixes the identities admission derived, so no
    candidate can move those. What folds still read through the vocabulary is the
    verb's declaration — its fold unit, which decides the shape its state takes,
    its record form, created child, update field, or request binding — and that
    must stay what the event's own captured registry said. The
    candidate side comes from the document being checked, except that thread widgets
    live in their frozen markup for the page's whole lifetime.
    """
    if event_document(event)["kind"] == "page":
        record = page.by_id[event["widget"]]
        recorded = recorded_page.by_id[event["widget"]]
    else:
        record = recorded = thread.by_id[event["widget"]]
    entry = registry[record["tag"]]
    if event["kind"] == "request":
        before_request = recorded_registry[recorded["tag"]]["x-request"]
        after_request = entry["x-request"]
        before = before_request["verbs"][event["action"]]
        after = after_request["verbs"][event["action"]]
        if (
            before_request.get("records") != after_request.get("records")
            or before.get("bind") != after.get("bind")
            or before.get("unit") != after.get("unit")
        ):
            return f"request {event['id']} changes its admitted record binding"
        return None
    before = recorded_registry[recorded["tag"]]["x-state"][event["action"]]
    after = entry["x-state"][event["action"]]
    for field, label in (
        ("unit", "fold unit"),
        ("record", "record form"),
        ("creates", "creates declaration"),
        ("update", "update field"),
    ):
        if before.get(field) != after.get(field):
            return f"{event['kind']} {event['id']} changes its admitted {label}"
    return None
