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
from ..standing import strength
from ..todos import TodoReading
from ..work_reading import WorkReading


class WorkState(NamedTuple):
    """`records` are the obligation records only the page's log and claim decide,
    standing as `activity` reads them: each update's, and each to-do's, open or
    ended. A view adds the records its own document and frozen threads publish."""

    durable: WorkReading
    activity: dict
    workflows: list[dict]
    records: list[dict]
    live_reply: dict | None
    presence: dict

    @property
    def obligations(self) -> list[dict]:
        return self.activity["obligations"]


def served_workflows(
    workflows: list[dict], thread_reading: FrozenThreadReading, records: dict
) -> list[dict]:
    """The page's workflows as the browser and `page state` read them, strongest
    first, each stamped with the thread it stands in: a thread input's own, a widget
    frozen into a message's thread, or null for a page widget. Whose turn the thread
    is reads the records in it, which `records` (`workflows.handed_over`) holds.

    The order is the one comparator: an update handed back to the user first (its
    record's next actor), then where it stands (`standing.strength`), then the newer
    input. Whatever shows one workflow of several, a message's receipt or an On
    list's row, takes the first. A reader that selects keeps the order; the browser
    places its own unresolved sends against it."""
    by_id = {record["id"]: record for record in records["all"]}
    for workflow in workflows:
        workflow["thread"] = thread_reading.subject_thread(workflow["subject"])

    def order(workflow: dict) -> tuple:
        record = by_id.get(workflow["obligation"])
        return (
            record is not None and record["next_actor"] == "user",
            strength(workflow),
            workflow["seq"],
        )

    return sorted(workflows, key=order, reverse=True)


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
    # An open to-do stands where `activity` read it; one frozen into a message's
    # widget stands in that message's thread.
    stood = {todo["id"]: todo for todo in activity["todos"]}
    todos = [
        {
            **stood.get(todo["id"], todo),
            **(
                {"thread": durable.thread.subject_thread(todo["source"]["subject"])}
                if source
                else {}
            ),
        }
        for todo in log.todos
    ]
    return WorkState(
        durable, activity, workflows, activity["records"] + todos, reply, present
    )
