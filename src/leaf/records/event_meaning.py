"""Compile admitted widget commands into durable semantic facts.

The log keeps direct identities, never a snapshot of their ancestor tree. A
projection tests those identities against the document it reads, so moving a
referenced element still changes containment without changing an old event.
"""

from functools import cached_property

from leaf.log.events import event_document
from leaf.log.obligations import gesture_answers, replayed_attrs
from leaf.log.projection import (
    page_reading,
    thread_markup_reading,
    with_action,
)
from leaf.log.thread_context import thread_structure
from leaf.source.registry.contract import (
    deciding_verb,
    matches_when,
    state_definition,
    withdrawing_outcome,
)


class AdmissionReadings:
    """The page and thread-markup readings one admission folds, each built once.

    The contract gates and the meaning stamped after them read the same log, so
    they share one fold of it rather than each paying for their own."""

    def __init__(self, view, events: list, registry: dict):
        self.view = view
        self.events = events
        self.registry = registry
        self._pages: dict = {}

    @cached_property
    def log(self):
        from leaf.records.todos import TodoReading

        return TodoReading(self.events)

    @cached_property
    def work(self):
        from leaf.records.work_reading import WorkReading

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
        return thread_markup_reading(
            self.events, self.registry, withdrawn=self.log.withdrawn
        )

    def page(self, revision: int):
        if revision not in self._pages:
            self._pages[revision] = page_reading(
                self.view.reading(revision, self.registry),
                self.events,
                revision,
                withdrawn=self.log.withdrawn,
                revisions=self.view.revisions,
                revision_reader=lambda previous: self.view.reading(
                    previous, self.view.registry(previous)
                ),
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


def state_meaning(event: dict, record: dict, registry: dict, scope: str) -> dict:
    """Resolve one validated verb using its sending document's declaration.

    The event records the fold unit, direct dependencies, created child tag,
    and the semantic definition of the operation. The scope with its revision
    names the sending document. A later registry may change that operation;
    the old event remains history instead of being read as the new operation."""
    origin = record["tag"]
    entry = registry[origin]
    spec = entry["verbs"][event["action"]]
    dependencies = direct_dependencies(event, spec)
    meaning = {
        "scope": scope,
        "unit": dependencies[1],
        "depends": sorted(set(dependencies)),
        "state": state_definition(
            origin, entry, spec, attrs=record["attrs"], registry=registry
        ),
    }
    # A created child's unit is new, so no document may yet hold it. Stamping its
    # tag lets registry-free readers keep the action resting on it regardless.
    if creates := spec.get("creates"):
        meaning["creates"] = creates["child"]
    return meaning


def answer_meaning(
    record: dict, event: dict, readings: AdmissionReadings
) -> tuple[bool, str | None]:
    """Whether this admitted action answers its widget's obligation, and the thread it closes.

    The widget says whether its obligation is answered on each gesture
    (`obligations.gesture_answers`). The answering action is one that says it is while
    the widget asks or keeps an earlier registration, and either records the answer
    itself (its verb is `awaits.value`) or turns the obligation from open to answered,
    as Done on a multiple choice does. So adding an option to a question already
    answered answers nothing. The widget's `when` is read with the candidate in force
    in the fold of its own document. The thread it closes is the widget's authored
    `resolves`, read from the immutable document that sent it rather than carried in the
    command. A decision whose outcome is the one its verb `withdraws` leaves the page as
    if nothing had been proposed, so it answers the obligation and closes no thread:
    turning a fix down leaves the question it was written for open. A registered source
    may retain answer provenance after its request is withdrawn; only a source currently
    asking can close the thread it declares."""
    entry = readings.registry[record["tag"]]
    awaits = entry.get("awaits")
    if event["kind"] != "action" or not awaits or not event.get("answered"):
        return False, None
    withdrawn = withdrawing_outcome(entry)
    declined = (
        event["action"] == deciding_verb(entry)
        and withdrawn is not None
        and event["detail"]["outcome"] == withdrawn
    )
    reading = (
        readings.page(event["revision"])
        if event_document(event)["kind"] == "page"
        else readings.thread
    )
    candidate = {
        **event,
        "seq": readings.events[-1]["seq"] + 1 if readings.events else 1,
    }
    projection = with_action(
        reading.projection, candidate, entry["verbs"][event["action"]]
    )
    asking = matches_when(replayed_attrs(record, projection), awaits.get("when"))
    answers = (
        asking
        or any(
            item["source"]["kind"] == "widget"
            and item["source"]["id"] == event["widget"]
            for item in readings.work.all_obligations["all"]
        )
    ) and (
        event["action"] == awaits["value"]
        or not gesture_answers(readings.events, reading.projection).get(
            event["widget"], False
        )
    )
    return answers, (
        record["attrs"].get("resolves") if answers and not declined and asking else None
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
    admitted = dict(event)
    admitted["meaning"] = state_meaning(event, record, registry, scope)
    answers, closes = answer_meaning(record, admitted, readings)
    if answers:
        admitted["meaning"]["answer"] = closes
    return admitted
