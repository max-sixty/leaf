"""Compile admitted widget commands into durable semantic facts.

The log keeps direct identities, never a snapshot of their ancestor tree. A
projection tests those identities against the document it reads, so moving a
referenced element still changes containment without changing an old event.
"""

from functools import cached_property

from leaf.asks import answer_verbs, answering_action
from leaf.events import event_document
from leaf.projection import (
    authored_positions,
    frozen_thread_reading,
    page_reading,
    with_action,
)
from leaf.registry.contract import state_definition
from leaf.thread_context import thread_structure


class AdmissionReadings:
    """The page and frozen-thread readings one admission folds, each built once.

    The contract gates and the meaning stamped after them read the same log, so
    they share one fold of it rather than each paying for their own."""

    def __init__(self, view, events: list, registry: dict):
        self.view = view
        self.events = events
        self.registry = registry
        self._pages: dict = {}

    @cached_property
    def log(self):
        from .tasks import TaskReading

        return TaskReading(self.events)

    @cached_property
    def work(self):
        from .work_reading import WorkReading

        revisions = self.view.revisions
        return WorkReading(
            self.events,
            self.registry,
            self.page(revisions[-1]) if revisions else None,
            thread=self.thread,
            log=self.log,
        )

    @cached_property
    def thread(self):
        return frozen_thread_reading(
            self.events, self.registry, withdrawn=self.log.withdrawn
        )

    def page(self, revision: int):
        if revision not in self._pages:
            self._pages[revision] = page_reading(
                self.view.reading(revision, self.registry),
                self.events,
                revision,
                withdrawn=self.log.withdrawn,
            )
        return self._pages[revision]


def direct_dependencies(event: dict, spec: dict) -> list[str]:
    """The owner, fold unit, and recorded identities before canonical ordering."""
    detail = event["detail"]
    owner = event["widget"]
    unit = owner if spec["unit"] == "widget" else detail[spec["unit"]]
    dependencies = [owner, unit]
    if (spec.get("record") or {}).get("kind") in {"attribute", "position"}:
        value = detail["value"]
        dependencies.extend(value if isinstance(value, list) else [value])
    return dependencies


def state_meaning(event: dict, entry: dict, scope: str, origin: str) -> dict:
    """Resolve one validated verb using its sending document's declaration.

    The event records the fold unit, direct dependencies, created child tag,
    and the semantic definition of the operation. The scope with its revision
    names the sending document. A later registry may change that operation;
    the old event remains history instead of being read as the new operation."""
    spec = entry["x-state"][event["action"]]
    dependencies = direct_dependencies(event, spec)
    meaning = {
        "scope": scope,
        "unit": dependencies[1],
        "depends": sorted(set(dependencies)),
        "state": state_definition(origin, entry, spec),
    }
    # A created child's unit is new, so no document may yet hold it. Stamping its
    # tag lets registry-free readers keep the action resting on it regardless.
    if creates := spec.get("creates"):
        meaning["creates"] = creates["child"]
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
        reading = readings.page(event["revision"])
        byid = sender.by_id
    else:
        reading = readings.thread
        byid = reading.by_id
    candidate = {
        **event,
        "seq": readings.events[-1]["seq"] + 1 if readings.events else 1,
    }
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
    admitted["meaning"] = state_meaning(event, entry, scope, record["tag"])
    position = entry["x-state"][event["action"]].get("record") or {}
    if position.get("kind") == "position":
        # The authored units the rank lies among, in their order on the sending
        # document: a later document that authors them differently has placed
        # the unit itself (`projection.move_absorbed`).
        reading = (
            readings.page(event["revision"]) if scope == "page" else readings.thread
        )
        byid = reading.document.by_id if scope == "page" else reading.by_id
        admitted["meaning"]["among"] = authored_positions(
            event["widget"], position, byid, reading.spoken, registry
        )[event["detail"]["value"]]
    answers, closes = answer_meaning(sender, record, admitted, readings)
    if answers:
        admitted["meaning"]["answer"] = closes
    return admitted
