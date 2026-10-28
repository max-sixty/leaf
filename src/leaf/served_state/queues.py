"""The two lists, On me (`on_user`) and On <agent> (`on_agent`): what is on the user,
what is on the agent, and what each has finished (`done`).

Every user row is an obligation record (`obligations.py`): a message request,
a user task, a widget's input, or an update handed back for
resending (`workflows.handed_over`). Each source owns completion: conversational
requests take a reply, tasks take explicit Done, widgets take their declared answer.
A browser view serves these lists and `page state` prints them, so their counts and
membership agree. The browser places its own unresolved sends against the served
lists (`browser/runtime/framework/application.js`, `localQueues`); it never selects
them again.

On me holds records whose next actor is the user. On <agent> holds the open update
records the agent owes, then the agent's to-dos. A widget's obligation becomes the
agent's while a thread about it awaits the agent's word, and that thread's newest
unanswered turn already publishes an update record there; On <agent> lists that
update alone (`obligations.anchors_with_agent`, `thread_obligation_readings`).

On me has one row per place the user has a move at, since the walk over it (`m`)
stops once at each place and the panel draws a card per row. The records the user
answers in words in one thread, its asking messages, are answered by one reply, so they share the thread's row, the first of them leading.
That row joins the row of an open obligation on the page the thread is about
(`obligations.thread_topics`, the relation that hands such an obligation to the agent
while the thread awaits its word), since an obligation and the thread about it are one
place: an answer about a decision rides on the decision's row. Each record still settles
by its own rule, so a decision answered leaves the thread's records on a row of their own
until the user replies or resolves the thread. A user's to-do keeps a row of its own,
since it takes its own Done.

A row names its kind (its record's `source.kind`, or `todo`), its subject, the list it
stands on (`owner`), the thread it stands in, the records it carries beside its own
(`also`), and whether the agent has it in hand now (`live`): a to-do a start holds, or
an update the agent is at work on whose work has not gone quiet or stopped. A row names
its record by `id` and carries no copy of it: the view serves each obligation record in
`obligations`; an agent to-do row instead reads the page's `todos`. The browser's publisher joins each row to its current record. On <agent>
orders the updates by their strongest workflow (`work.served_workflows`), the order
every surface showing one of several reads.

A row that leaves a list lands in Done, whose `owner` names the list: the records no
longer open, which an update's is when the agent's reply answered it and a widget's
when the user answered it, here or elsewhere, or it was withdrawn; and the
ended to-dos. Each done row adds how it ended (`state`: `done`, or `dropped` for a
withdrawn record, or a to-do's outcome), when (`ended`), and the outcome's detail,
which for a record is its agent end's. Done is served newest first, and a row without a
time goes last. An answer the agent owes in markup settles when a version writes the
action in, and its widget's record carries that ending, so the update's leaves the
inventory and lands in no Done.
"""

from ..obligations import answered_in_words, thread_topics
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
    if source["kind"] in {"update", "todo"}:
        return source["subject"]
    if source["kind"] == "message":
        return {"kind": "thread", "id": record["thread"]}
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
        "also": [],
        "live": live,
    }


def _on_user(records: list[dict], threads: dict, within: dict) -> list[dict]:
    """On me's rows, one per place the user has a move at: requests and explicit tasks,
    then the updates to send again."""
    users = [record for record in records if record["next_actor"] == "user"]
    rows = []
    in_thread: dict[str, dict] = {}
    for record in sorted(
        users, key=lambda record: record["source"]["kind"] == "update"
    ):
        thread = record["thread"]
        if thread is not None and answered_in_words(record):
            if thread in in_thread:
                in_thread[thread]["also"].append(record["id"])
                continue
            in_thread[thread] = _record_row(record, "user")
            rows.append(in_thread[thread])
        else:
            rows.append(_record_row(record, "user"))
    page = [
        record
        for record in records
        if record["thread"] is None and record["source"]["kind"] == "widget"
    ]
    asks = {
        row["id"]: row
        for row in rows
        if row["kind"] == "widget" and row["thread"] is None
    }
    topics = thread_topics({key: threads[key] for key in in_thread}, page, within)
    for identity, row in in_thread.items():
        joined = next(
            (asks[record["id"]] for record in topics[identity] if record["id"] in asks),
            None,
        )
        if joined is not None:
            joined["also"] += [row["id"], *row["also"]]
            rows.remove(row)
    return rows


def queues(
    workflows: list[dict],
    todos: list[dict],
    records: list[dict],
    threads: dict,
    within: dict,
) -> dict:
    """Select records and to-dos once, by next actor.

    `workflows` are served strongest first, `todos` are every to-do on either side,
    open and ended, and `records` are the view's obligation records, the user's updates'
    included, in inventory order. `threads` are the page's threads by id and `within`
    the document's containment, which say what a thread is about."""
    open_todos = [todo for todo in todos if todo["state"] == "open"]
    on_user = _on_user(records, threads, within)
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
            "state": "dropped"
            if record["status"] == "withdrawn"
            else (
                record["answer"]["value"]
                if record["source"]["kind"] == "todo"
                else "done"
            ),
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
        if todo["state"] != "open" and todo["owner"] == "agent"
    ]
    done.sort(
        key=lambda item: (
            item["ended"] is not None,
            aware_instant(item["ended"]) if item["ended"] else None,
        ),
        reverse=True,
    )
    return {"on_user": on_user, "on_agent": on_agent, "done": done}
