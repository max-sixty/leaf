"""Semantic work with the live claim/turn evidence used by every transport.

The durable reading remains separate from activity's liveness and reply reservations.
Delivery and status never need browser serialization or history. Record obligations
read their current bound data through the same canonical work reading.
A serving context holds this result once; its browser selects the same objects.
"""

from typing import NamedTuple

from ..activity import canonical_activity, canonical_stream_reply
from ..projection import FrozenThreadReading, page_reading
from ..service import no_stream
from ..todos import TodoReading
from ..work_reading import WorkReading


class WorkState(NamedTuple):
    durable: WorkReading
    activity: dict
    workflows: list[dict]
    live_reply: dict | None
    presence: dict

    @property
    def obligations(self) -> list[dict]:
        return self.activity["obligations"]


# Delivery progress, furthest last. `answered` is only ever the retained failed
# response, so within its category it is the furthest an update has come.
_STAGE_RANK = {
    "sent": 0,
    "queued": 1,
    "picked_up": 2,
    "working": 3,
    "replying": 4,
    "answered": 5,
}


def at_work(workflow: dict) -> bool:
    return workflow["stage"] in {"working", "replying"}


def _strength(workflow: dict, records: dict[str, dict]) -> tuple:
    """How strongly a workflow speaks for any surface that shows one of several: an
    update handed back to the user first (its record's next actor), then work under
    way, then an uncertain or stopped one, then plain delivery; within each the further
    stage, then the newer input."""
    if workflow["condition"] is not None:
        category = 2
    elif at_work(workflow):
        category = 3
    elif workflow["stage"] == "answered":
        category = 0
    else:
        category = 1
    record = records.get(workflow["obligation"])
    return (
        record is not None and record["next_actor"] == "user",
        category,
        _STAGE_RANK[workflow["stage"]],
        workflow["seq"],
    )


def served_workflows(
    workflows: list[dict], thread_reading: FrozenThreadReading, records: dict
) -> list[dict]:
    """The page's workflows as the browser and `page state` read them, strongest
    first, each stamped with what its thread and its activity say.

    `at_work` is whether the agent is at work on it, at `working` or `replying`
    whatever its condition, the stage set every surface reads rather than restates.
    `thread` is the thread the workflow stands in: a thread input's own, a widget
    frozen into a message's thread, or null for a page widget. Whose turn the thread
    is reads the records in it, which `records` (`workflows.handed_over`) holds.

    The order is the one comparator: whatever shows one workflow of several, a
    thread's attention, its card's secondary status, a message's receipt, an On
    list's row, takes the first. A reader that selects keeps the order; the browser
    places its own unresolved sends against it."""
    by_id = {record["id"]: record for record in records["all"]}
    for workflow in workflows:
        workflow["at_work"] = at_work(workflow)
        workflow["thread"] = thread_reading.subject_thread(workflow["subject"])
    return sorted(
        workflows, key=lambda workflow: _strength(workflow, by_id), reverse=True
    )


def work_state(
    events,
    source,
    revision,
    present,
    now,
    live_stream=None,
    *,
    revisions=(),
    revision_reader=None,
    data=None,
) -> WorkState:
    """Fold exact admitted inputs, then enrich once with claim and stream evidence."""
    log = TodoReading(events)
    page = (
        page_reading(
            source,
            events,
            revision,
            withdrawn=log.withdrawn,
            revisions=revisions,
            revision_reader=revision_reader,
        )
        if source
        else None
    )
    durable = WorkReading(
        events, source.registry if source else {}, page, log=log, data=data
    )
    stream = live_stream or no_stream()
    reply = canonical_stream_reply(present, now, stream["reply"])
    activity = canonical_activity(
        present,
        durable.workflows,
        events,
        now,
        stream["activity"],
        reply,
        stream["reply_reservations"],
        todo_reading=log,
        updates=durable.updates,
    )
    workflows = (
        served_workflows(activity["workflows"], durable.thread, durable.updates)
        if source
        else activity["workflows"]
    )
    return WorkState(durable, activity, workflows, reply, present)
