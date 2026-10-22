"""The two lists, On me (`on_user`) and On <agent> (`on_agent`): what is on the user,
what is on the agent, and what each has finished (`done`).

Every row but a to-do is an obligation record (`obligations.py`): a widget's, a version's
sign-off, or an update the user handed over (`workflows.handed_over`). This is the one
selection that lists them by their next actor beside the to-dos. An obligation is never
a to-do: its source owns its answer, and only a to-do on the user, which the agent
opened, ends at their Done. A browser view serves these lists and `page state` prints
them, so the panel's counts, its On lists and an agent picking the page up read one
selection. The browser places its own unresolved sends against the served lists
(`browser/framework/application.ts`, `localQueues`); it never selects them again.

On me holds the open records whose next actor is the user, which are the obligations
widgets and sign-off ask and the updates handed back for the user to send again, then the
to-dos on the user. On <agent> holds the open update records whose next actor is the
agent, which are the answers it owes, then the agent's to-dos. A widget's obligation
is the agent's only while a thread about it awaits the agent's word, and that thread's
newest unanswered turn already publishes an update record there; so On <agent> lists
update records alone, and the comment's row stands for the widget's side
(`obligations.anchors_with_agent`, `thread_obligation_readings`).

A row names its kind (its record's `source.kind`, or `todo`), its subject, the list it
stands on (`owner`), the thread it stands in, and whether the agent has it in hand now
(`live`): a to-do a start holds, or an update the agent is at work on whose work has not
gone quiet or stopped. A row names its record by `id` and carries no copy of it: the
view serves each obligation record once, in `obligations`, the page serves each to-do
once, in `todos`, and the browser's publisher joins the row to its current record. On <agent>
orders the updates by their strongest workflow (`work.served_workflows`), the order
every surface showing one of several reads.

A row that leaves a list lands in Done, whose `owner` names the list: the records no
longer open, which an update's is when the agent's reply answered it and a widget's or
sign-off's when the user answered it, here or elsewhere, or it was withdrawn; and the
ended to-dos. Each done row adds how it ended (`state`: `done`, or `dropped` for a
withdrawn record, or a to-do's outcome), when (`ended`), and the outcome's detail,
which for a record is its agent end's. Done is served newest first, and a row without a
time goes last. An answer the agent owes in markup settles when a version writes the
action in, and its widget's record carries that ending, so the update's leaves the
inventory and lands in no Done.
"""

from ..registry.schema import aware_instant


def _todo_item(todo: dict) -> dict:
    """One to-do on the list of its `owner`. It names the to-do by `id`; the record is
    the page's `todos` entry."""
    return {
        "kind": "todo",
        "id": todo["id"],
        "owner": todo["owner"],
        "subject": todo["subject"],
        "thread": todo["thread"],
        "live": todo["running"] is not None,
    }


def _subject(record: dict) -> dict:
    """What a record's row stands on: an update's own subject, a widget, or the page."""
    source = record["source"]
    if source["kind"] == "update":
        return source["subject"]
    if source["kind"] == "widget":
        return {"kind": "widget", "id": source["id"]}
    return {"kind": "page"}


def _record_row(record: dict, owner: str, live: bool = False) -> dict:
    """One record's row on `owner`'s list, by its source's kind. It names the record by
    `id`; the record is the view's `obligations` entry."""
    return {
        "kind": record["source"]["kind"],
        "id": record["id"],
        "owner": owner,
        "subject": _subject(record),
        "thread": record["thread"],
        "live": live,
    }


def queues(workflows: list[dict], todos: list[dict], records: list[dict]) -> dict:
    """Select records and to-dos once, by next actor.

    `workflows` are served strongest first, `todos` are every to-do on either side,
    open and ended, and `records` are the view's obligation records, the user's updates'
    included, in inventory order."""
    open_todos = [todo for todo in todos if todo["state"] == "open"]
    users = [record for record in records if record["next_actor"] == "user"]
    # What the page asks, then the to-dos, then the updates to send again.
    on_user = [
        *(
            _record_row(record, "user")
            for record in users
            if record["source"]["kind"] != "update"
        ),
        *(_todo_item(todo) for todo in open_todos if todo["owner"] == "user"),
        *(
            _record_row(record, "user")
            for record in users
            if record["source"]["kind"] == "update"
        ),
    ]
    owing = {
        record["id"]: record
        for record in records
        if record["next_actor"] == "agent" and record["source"]["kind"] == "update"
    }
    serving: dict[str, list[dict]] = {}
    for workflow in workflows:
        if workflow["obligation"] in owing:
            serving.setdefault(workflow["obligation"], []).append(workflow)
    on_agent = [
        _record_row(
            owing[identity],
            "agent",
            any(item["at_work"] and item["condition"] is None for item in held),
        )
        for identity, held in serving.items()
    ]
    on_agent += [_todo_item(todo) for todo in open_todos if todo["owner"] == "agent"]
    done = [
        {
            **_record_row(
                record, "agent" if record["source"]["kind"] == "update" else "user"
            ),
            "state": "dropped" if record["status"] == "withdrawn" else "done",
            "ended": ((record["end"] or record["answer"] or {}).get("event") or {}).get(
                "ts"
            ),
            "detail": record["end"]["detail"] if record["end"] else None,
        }
        for record in records
        if record["status"] != "open"
    ]
    done += [
        {
            **_todo_item(todo),
            "state": todo["state"],
            "ended": (todo["outcome"] or {}).get("ts"),
            "detail": (todo["outcome"] or {}).get("detail"),
        }
        for todo in todos
        if todo["state"] != "open"
    ]
    done.sort(
        key=lambda item: (
            item["ended"] is not None,
            aware_instant(item["ended"]) if item["ended"] else None,
        ),
        reverse=True,
    )
    return {"on_user": on_user, "on_agent": on_agent, "done": done}
