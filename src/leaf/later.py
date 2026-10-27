"""Later: the user setting obligations on them aside until a condition brings them back.

A `later` event is the user's gesture. It names the obligation records it sets aside
(`obligations`, the records one On me row or one deck card carries, an update handed
back to send again among them) and one condition: `until`, an instant, or `after`, an
item on the agent's list, which is an open agent to-do's id or the id of an update
record the agent owes (`update:<input>`). The newest `later` in force on a record
decides it, so choosing again replaces the condition, and an `undo` withdraws it as it
does any gesture, which leaves the one beneath in force. Each record serves its Laters
as a chain, the newest first with the one it replaced as `beneath`, so the browser can
draw an undo's result without reading the log.

While its condition doesn't hold, a record the user owed stays open but has no next
actor, so every reader of whose move it is (On me, the tally, a deck, a thread's
attention) leaves it out without knowing about Later. The condition holds once the
instant has passed, or once the agent's item is no longer the agent's: its to-do
ended, or the update was answered or handed back. A follow-up the user sends in that
thread moves the owed record to the newest input, and the older input's workflow then
names it (`workflows.handed_over`), so `after` follows that succession and waits for
the reply that answers the follow-up too. The record then returns to the user as it
stood, its `later` saying `returned`, so a surface can say it came back. A record that
is no longer open, or that the agent holds, keeps its own next actor whatever the
condition.

A Later ends once the user acts on what it set aside: an action on its widget, an end
of its to-do or its question, or the answer it records, even where an undo later takes
that act back. So a widget answered and then undone, or a decision a version reopens
after the user answered it, waits on the user again rather than hiding under a Later
the user has already come back from.

Nothing here wakes the agent, and nothing the agent reads changes: admission, delivery
and agent-facing readings read the inventory without Later
(`work_reading.WorkReading.inventory`, `updates`), since setting a question aside asks
the agent for nothing. A time condition changes the reading with no file moving, so
this reading names each pending instant (`wakes`), and the activity fold serves the
earliest as `next_transition_at`, at which every reader asks again
(`activity.canonical_activity`).

Rejected: keeping Later in the browser, as the deck's plain Later does, which lost the
condition on reload and couldn't take the item off On me in another tab; and a
reminder sent to the agent, which would spend a turn on every Later."""

from collections.abc import Callable
from datetime import datetime

from leaf.findings import Finding
from leaf.obligations import event_reference
from leaf.registry.schema import aware_instant


def set_aside(record: dict) -> bool:
    """Whether a Later that hasn't brought it back sets this record aside."""
    later = record.get("later")
    return (
        record["status"] == "open"
        and record["next_actor"] is None
        and later is not None
        and not later["returned"]
    )


def agent_item_finished(
    todos: list[dict], updates: list[dict], workflows: list[dict]
) -> Callable:
    """Whether an item on the agent's list (`after`) is no longer the agent's: an
    agent to-do that ended, or an update the agent no longer owes, read through the
    workflow of the input it names, which names the newest record a follow-up moved
    the debt to."""
    open_todos = {
        todo["id"]
        for todo in todos
        if todo["owner"] == "agent" and todo["state"] == "open"
    }
    owing = {
        record["id"]
        for record in updates
        if record["status"] == "open" and record["next_actor"] == "agent"
    }
    owed = owing | {
        f"update:{workflow['input']}"
        for workflow in workflows
        if workflow["obligation"] in owing
    }
    return lambda item: item not in open_todos and item not in owed


def _acts(events: list, records: list[dict]) -> dict[str, int]:
    """The seq of the user's latest act on each record, withdrawn or not: an action on
    its widget (on its unit, for a record of one), a `todo_end` on its to-do or
    question, or the answer or ending the record carries."""
    by_widget: dict[tuple[str, str | None], list[str]] = {}
    by_ended: dict[str, list[str]] = {}
    acts: dict[str, int] = {}
    for record in records:
        source = record["source"]
        if source["kind"] == "widget":
            by_widget.setdefault((source["id"], source.get("unit")), []).append(
                record["id"]
            )
        by_ended.setdefault(source["id"], []).append(record["id"])
        by_ended.setdefault(record["id"], []).append(record["id"])
        for done in (record.get("answer"), record.get("end")):
            event = (done or {}).get("event")
            if event:
                acts[record["id"]] = max(acts.get(record["id"], 0), event["seq"])
    for event in events:
        if event["kind"] == "action" and event["author"] == "user":
            touched = by_widget.get((event["widget"], None), []) + by_widget.get(
                (event["widget"], event["meaning"]["unit"]), []
            )
        elif event["kind"] == "todo_end":
            touched = by_ended.get(event["todo"], [])
        else:
            continue
        for identity in touched:
            acts[identity] = max(acts.get(identity, 0), event["seq"])
    return acts


def later_reading(
    records: list[dict],
    events: list,
    withdrawn: set,
    *,
    finished: Callable[[str], bool],
    now: datetime,
) -> tuple[list[dict], list[datetime]]:
    """`records` with the Laters in force on each applied, and the instants at which a
    Later still setting a record aside comes due."""
    acts = _acts(events, records)
    laters: dict[str, list[dict]] = {}
    for event in events:
        if event["kind"] == "later" and event["id"] not in withdrawn:
            for identity in event["obligations"]:
                laters.setdefault(identity, []).insert(0, event)

    def chain(events: list[dict]) -> dict | None:
        if not events:
            return None
        event, *older = events
        until = event.get("until")
        due = aware_instant(until) if until else None
        return {
            "event": event_reference(event),
            "until": until,
            "after": event.get("after"),
            "returned": due <= now if due else finished(event["after"]),
            "beneath": chain(older),
        }

    result = []
    wakes = []
    for record in records:
        acted = acts.get(record["id"], 0)
        standing = [
            event for event in laters.get(record["id"], []) if event["seq"] > acted
        ]
        later = chain(standing)
        if later is None:
            result.append(record)
            continue
        record = {**record, "later": later}
        if (
            not later["returned"]
            and record["status"] == "open"
            and record["next_actor"] == "user"
        ):
            record["next_actor"] = None
            if later["until"]:
                wakes.append(aware_instant(later["until"]))
        result.append(record)
    return result, wakes


def later_error(
    event: dict, records: list[dict], finished: Callable[[str], bool], now: datetime
) -> Finding | None:
    """Why a `later` may not set its records aside: each must be open with the move the
    user's (`records` is every record before Later, updates included), and its condition
    must not already hold, since a Later that came straight back would set nothing
    aside."""
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
