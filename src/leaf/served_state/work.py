"""Semantic work with the live claim/turn evidence used by every transport.

The durable reading remains separate from activity's liveness and reply reservations.
Delivery and status never need browser serialization or history. Record obligations
read their current bound data through the same canonical work reading.
A serving context holds this result once; its browser selects the same objects.
"""

from datetime import datetime
from typing import NamedTuple

from ..activity import (
    Turn,
    canonical_activity,
    canonical_stream_reply,
    current_turn,
    declared_at,
)
from ..events import awaits_agent, unanswered_turns
from ..projection import ThreadMarkupReading, page_reading
from ..service import no_stream
from ..todos import TodoReading
from ..work_reading import WorkReading


class WorkState(NamedTuple):
    durable: WorkReading
    activity: dict
    workflows: list[dict]
    live_reply: dict | None
    presence: dict
    # The claimant's turn as activity reads it (`activity.current_turn`), which says
    # whether the turn that wrote a progress message still runs (`activity.turn_runs`).
    turn: Turn

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


def _strength(workflow: dict, records: dict[str, dict]) -> tuple:
    """How strongly a workflow speaks for any surface that shows one of several: an
    update handed back to the user first (its record's next actor), then work under
    way, then an uncertain or stopped one, then plain delivery; within each the further
    stage, then the newer input."""
    if workflow["condition"] is not None:
        category = 2
    elif workflow["at_work"]:
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


def lined(threads: dict[str, dict]) -> frozenset[str]:
    """The user's turns waiting in `threads` (`events.unanswered_turns`) that a
    progress message of the agent's came after, as the line a line fork posts
    (`forks.py`): those older than the newest the agent hasn't taken back in their
    thread, until the agent answers them."""
    found: set[str] = set()
    for thread in threads.values():
        if not awaits_agent(thread):
            continue
        working = max(
            (
                message["seq"]
                for message in thread["msgs"]
                if message["author"] == "agent"
                and message.get("ephemeral")
                and "withdrawn" not in message
            ),
            default=0,
        )
        found.update(
            turn["id"] for turn in unanswered_turns(thread) if turn["seq"] < working
        )
    return frozenset(found)


def served_workflows(
    workflows: list[dict],
    thread_reading: ThreadMarkupReading,
    records: dict,
    on_it: frozenset[str],
) -> list[dict]:
    """The page's workflows as the browser and `page state` read them, strongest
    first, each stamped with what its thread and its activity say.

    `at_work` is whether the agent is at work on it whatever its condition, which
    every surface reads rather than restating stages: at `working` or `replying`, or
    its input among `on_it`, the waiting turns a progress message of the agent's came
    after (`lined`), which the page words On it while its delivery stands. Every
    reader that ages, nudges or holds a turn reads the stage alone.
    `thread` is the thread the workflow stands in: a thread input's own, a widget
    in a message's thread, or null for a page widget. Whose turn the thread
    is reads the records in it, which `records` (`workflows.handed_over`) holds.

    The order is the one comparator: whatever shows one workflow of several, a
    thread's attention, its card's secondary status, a message's receipt, an On
    list's row, takes the first. A reader that selects keeps the order; the browser
    places its own unresolved sends against it."""
    by_id = {record["id"]: record for record in records["all"]}
    for workflow in workflows:
        workflow["at_work"] = (
            workflow["stage"] in {"working", "replying"} or workflow["input"] in on_it
        )
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
        served_workflows(
            activity["workflows"],
            durable.thread,
            durable.updates,
            # With no live claimant, no progress message speaks for the page.
            lined(durable.threads) if present["session_alive"] is True else frozenset(),
        )
        if source
        else activity["workflows"]
    )
    turn, _ = current_turn(
        present,
        declared_at(present, events),
        stream["activity"],
        datetime.fromisoformat(now),
    )
    return WorkState(durable, activity, workflows, reply, present, turn)
