"""Later: the user setting obligations on them aside until a condition brings them back.

A `later` event is the user's gesture. It names the obligation records it sets aside
(`obligations`, the records one On me row or one deck card carries) and one condition:
`until`, an instant, or `after`, an item on the agent's list, which is an open agent
to-do's id or the id of an update record the agent owes (`update:<event>`). The newest
`later` in force on a record decides it, so choosing again replaces the condition, and
an `undo` withdraws it as it does any gesture.

While its condition doesn't hold, a record the user owed stays open but has no next
actor, so every reader of whose move it is (On me, the tally, a deck, a thread's
attention, the Stop hook) leaves it out without knowing about Later. The condition
holds once the instant has passed, or once the agent's item is no longer the agent's:
its to-do ended, or the update was answered or handed back. The record then returns
to the user as it stood, still carrying `later` with `returned` true, so a surface can
say it came back. A record that is no longer open, or that the agent holds, keeps its
own next actor whatever the condition.

Nothing here wakes the agent: admission compares readings without Later
(`work_reading.WorkReading.inventory`), since setting a question aside asks the agent
for nothing. A time condition changes the reading with no file moving, so this reading
names each pending instant (`wakes`), and the activity fold serves the earliest as
`next_transition_at`, at which every reader asks again (`activity.canonical_activity`).

Rejected: keeping Later in the browser, as the deck's plain Later does, which lost the
condition on reload and couldn't take the item off On me in another tab; and a
reminder sent to the agent, which would spend a turn on every Later."""

from collections.abc import Callable
from datetime import datetime

from leaf.findings import Finding
from leaf.obligations import event_reference
from leaf.registry.schema import aware_instant


def laters_in_force(events: list, withdrawn: set) -> dict[str, dict]:
    """The newest `later` in force on each record it names, by the record's id."""
    return {
        identity: event
        for event in events
        if event["kind"] == "later" and event["id"] not in withdrawn
        for identity in event["obligations"]
    }


def agent_item_finished(todos: list[dict], updates: list[dict]) -> Callable:
    """Whether an item on the agent's list (`after`) is no longer the agent's: an
    agent to-do that ended, or an update record the agent no longer owes."""
    open_todos = {
        todo["id"]
        for todo in todos
        if todo["owner"] == "agent" and todo["state"] == "open"
    }
    owed = {
        record["id"]
        for record in updates
        if record["status"] == "open" and record["next_actor"] == "agent"
    }
    return lambda item: item not in open_todos and item not in owed


def later_reading(
    records: list[dict],
    laters: dict[str, dict],
    *,
    finished: Callable[[str], bool],
    now: datetime,
) -> tuple[list[dict], list[datetime]]:
    """`records` with each Later in force applied, and the instants at which a Later
    still setting a record aside comes due."""
    result = []
    wakes = []
    for record in records:
        event = laters.get(record["id"])
        if event is None:
            result.append(record)
            continue
        until = event.get("until")
        due = aware_instant(until) if until else None
        returned = due <= now if due else finished(event["after"])
        record = {
            **record,
            "later": {
                "event": event_reference(event),
                "until": until,
                "after": event.get("after"),
                "returned": returned,
            },
        }
        if (
            not returned
            and record["status"] == "open"
            and record["next_actor"] == "user"
        ):
            record["next_actor"] = None
            if due:
                wakes.append(due)
        result.append(record)
    return result, wakes


def later_error(
    event: dict, records: list[dict], finished: Callable[[str], bool], now: datetime
) -> Finding | None:
    """Why a `later` may not set its records aside: each must be open with the move the
    user's (`records` is the inventory before Later), and its condition must not
    already hold, since a Later that came straight back would set nothing aside."""
    if event["kind"] != "later":
        return None
    owed = {
        record["id"]
        for record in records
        if record["status"] == "open" and record["next_actor"] == "user"
    }
    for identity in event["obligations"]:
        if identity not in owed:
            return Finding("later-obligation", values={"obligation": identity})
    if "until" in event:
        if aware_instant(event["until"]) <= now:
            return Finding("later-past", values={"until": event["until"]})
    elif finished(event["after"]):
        return Finding("later-after", values={"after": event["after"]})
    return None
