"""Semantic work with the live claim/turn evidence used by every transport.

The durable reading remains separate from activity's liveness and reply reservations.
Delivery and status never need browser serialization or history: they read
it from the page directory (`presence.read_work`). A serving context holds this
result once (`served_state.context.PageRead`); its browser selects the same objects.
"""

from datetime import datetime
from typing import NamedTuple

from leaf.base.service import no_stream
from leaf.base.standing import strength
from leaf.log.events import owed_turns
from leaf.log.projection import ThreadMarkupReading, page_reading
from leaf.records.activity import (
    Turn,
    canonical_activity,
    canonical_stream_reply,
    current_turn,
    declared_at,
)
from leaf.records.todos import TodoReading
from leaf.records.work_reading import WorkReading


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
    # The claimant's turn as activity reads it (`activity.current_turn`), which says
    # whether the turn that wrote a progress message still runs (`activity.turn_runs`).
    turn: Turn

    @property
    def obligations(self) -> list[dict]:
        return self.activity["obligations"]


def lined(threads: dict[str, dict]) -> frozenset[str]:
    """The user's turns the agent owes an answer in `threads` (`events.owed_turns`)
    that a progress message of the agent's came after, as the line a line fork posts
    (`forks.py`): those older than the newest the agent hasn't taken back in their
    thread, until the agent answers them. `activity` reads each as at work while its
    delivery stands."""
    found: set[str] = set()
    for thread in threads.values():
        owed = owed_turns(thread)
        if not owed:
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
        found.update(turn["id"] for turn in owed if turn["seq"] < working)
    return frozenset(found)


def served_workflows(
    workflows: list[dict], thread_reading: ThreadMarkupReading, records: dict
) -> list[dict]:
    """The page's workflows as the browser and `page state` read them, strongest
    first, each stamped with the thread it stands in: a thread input's own, a widget
    in a message's thread, or null for a page widget. Whose turn the thread
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
    durable = WorkReading(events, source.registry if source else {}, page, log=log)
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
        # With no live claimant, no progress message speaks for the page.
        on_it=lined(durable.threads)
        if source and present["session_alive"] is True
        else frozenset(),
    )
    workflows = (
        served_workflows(activity["workflows"], durable.thread, durable.updates)
        if source
        else activity["workflows"]
    )
    turn, _ = current_turn(
        present,
        declared_at(present, events),
        stream["activity"],
        datetime.fromisoformat(now),
    )
    # An open to-do stands where `activity` read it; one a widget in a message opened
    # stands in that message's thread.
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
        durable,
        activity,
        workflows,
        activity["records"] + todos,
        reply,
        present,
        turn,
    )
