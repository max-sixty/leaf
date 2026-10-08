"""Semantic work with the live claim/turn evidence used by every transport.

The durable reading remains separate from activity's liveness and response binding.
Delivery and status never need browser serialization, external data, or history.
A serving context holds this result once; its browser selects the same objects.
"""

from pathlib import Path
from typing import NamedTuple

from ..activity import canonical_activity, canonical_stream_reply
from ..files import active_descriptor
from ..presence import presence_with_activity
from ..projection import FrozenThreadReading, page_reading
from ..revision_artifact import read_revision
from ..state import now_iso
from ..tasks import TaskReading
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
# response, so within its category it is the furthest a move has come.
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


def _strength(workflow: dict) -> tuple:
    """How strongly a workflow speaks for any surface that shows one of several: a
    move handed back to the user first, then work under way, then an uncertain or
    stopped one, then plain delivery; within each the further stage, then the newer
    input."""
    if workflow["condition"] is not None:
        category = 2
    elif at_work(workflow):
        category = 3
    elif workflow["stage"] == "answered":
        category = 0
    else:
        category = 1
    return (
        workflow["next_actor"] == "user",
        category,
        _STAGE_RANK[workflow["stage"]],
        workflow["seq"],
    )


def served_workflows(
    workflows: list[dict], thread_reading: FrozenThreadReading
) -> list[dict]:
    """The page's workflows as the browser and `page state` read them, strongest
    first, each stamped with the two thread facts only the frozen thread document
    knows.

    `thread` is the thread the workflow stands in: a thread input's own, a widget
    frozen into a message's thread, or null for a page widget. `holds_thread` is
    whether it keeps that thread the agent's turn: every one of the thread's own
    inputs, and a widget move frozen into it while the move is owed or the agent is
    at work on it. A frozen move that owes nothing shows its receipt on
    its message and leaves the thread nobody's turn.

    The order is the one comparator: whatever shows one workflow of several, a
    thread's attention, its card's secondary status, a message's receipt, takes the
    first. A reader that selects keeps the order; the browser places its own
    unresolved sends against it."""
    for workflow in workflows:
        thread = thread_reading.subject_thread(workflow["subject"])
        workflow["thread"] = thread
        workflow["holds_thread"] = thread is not None and (
            workflow["subject"]["kind"] == "thread"
            or workflow["answer"] is not None
            or at_work(workflow)
        )
    return sorted(workflows, key=_strength, reverse=True)


def work_state(events, source, revision, present, now, live_stream=None) -> WorkState:
    """Fold exact admitted inputs, then enrich once with claim and stream evidence."""
    log = TaskReading(events)
    page = (
        page_reading(source, events, revision, withdrawn=log.withdrawn)
        if source
        else None
    )
    durable = WorkReading(events, source.registry if source else {}, page, log=log)
    stream = live_stream or {}
    reply = canonical_stream_reply(present, now, stream.get("reply"))
    activity = canonical_activity(
        present,
        durable.workflows,
        events,
        now,
        stream.get("activity"),
        reply,
        stream.get("reply_bindings"),
        task_reading=log,
    )
    workflows = (
        served_workflows(activity["workflows"], durable.thread)
        if source
        else activity["workflows"]
    )
    return WorkState(durable, activity, workflows, reply, present)


def live_work(page_dir: Path, events: list, *, now: str | None = None) -> WorkState:
    """Read work inside the caller's transaction, without preparing a browser response."""
    active = active_descriptor(page_dir, events)
    present, stream = presence_with_activity(page_dir, events)
    return work_state(
        events,
        read_revision(page_dir, active["revision"]) if active else None,
        active["revision"] if active else None,
        present,
        now or now_iso(),
        stream,
    )
