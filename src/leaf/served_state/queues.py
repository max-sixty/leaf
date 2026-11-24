"""The two lists, On Me (`on_user`) and On <agent> (`on_agent`): what is on the user,
what is on the agent, and what each has finished (`done`).

Every row is an obligation record (`obligations.py`). A user row is a message
request, a widget's input, or an update handed back for resending
(`workflows.handed_over`); an agent row is an update it owes or a to-do it opened.
Each source owns completion: conversational requests take a reply, widgets take their
declared answer, and only the agent ends a to-do.
A browser view serves these lists and `page state` prints them, so their counts and
membership agree. The browser places its own unresolved sends against the served
lists (`browser/runtime/framework/application.js`, `localQueues`); it never selects
them again.

On Me holds records whose next actor is the user. On <agent> holds the open update
records the agent owes, then the agent's to-dos. A widget's obligation becomes the
agent's while a thread about it awaits the agent's word, and that thread's newest
unanswered turn already publishes an update record there; On <agent> lists that
update alone (`obligations.anchors_with_agent`, `thread_obligation_readings`).

On Me has one row per place the user has a move at, since the walk over it (`m`)
stops once at each place and the panel draws a card per row. The records the user
answers in words in one thread, its asking messages, are answered by one reply, so they share the thread's row, the first of them leading.
That row joins the row of an open obligation on the page the thread is about
(`obligations.thread_topics`, the relation that hands such an obligation to the agent
while the thread awaits its word), since an obligation and the thread about it are one
place: an answer about a decision rides on the decision's row. Each record still settles
by its own rule, so a decision answered leaves the thread's records on a row of their own
until the user replies or resolves the thread.

A row names its kind (its record's `source.kind`), its subject, the list it stands on
(`owner`), the thread it stands in, and the records it carries beside its own (`also`).
A row names its record by `id` and carries no copy of it: the view serves each
obligation record in `obligations`, and the record says where it stands (`standing`),
so a row's reader takes whether the agent has it in hand, and how a done one ended,
from there. The browser's publisher joins each row to its current record. On <agent>
orders the updates by their strongest workflow (`work.served_workflows`), the order
every surface showing one of several reads.

A row that leaves a list lands in Done, whose `owner` names the list: the records no
longer open, which an update's is when the agent's reply answered it, a widget's
when the user answered it, here or elsewhere, or it was withdrawn, and a to-do's when
the agent ended it. Done is served newest first by when each ended, and a row without a
time goes last. An answer the agent owes in markup settles when a version writes the
action in, and its widget's record carries that ending, so the update's leaves the
inventory and lands in no Done.
"""

from ..obligations import answered_in_words, thread_topics
from ..registry.schema import aware_instant
from ..standing import is_open


def _subject(record: dict) -> dict:
    """What a record's row stands on: an update's or a to-do's own subject, a widget,
    or the page."""
    source = record["source"]
    if source["kind"] in {"update", "todo"}:
        return source["subject"]
    if source["kind"] == "message":
        return {"kind": "thread", "id": record["thread"]}
    if source["kind"] == "widget":
        return {"kind": "widget", "id": source["id"]}
    return {"kind": "page"}


def _record_row(record: dict, owner: str) -> dict:
    """One record's row on `owner`'s list, by its source's kind. It names the record by
    `id`; the record is the view's `obligations` entry."""
    return {
        "kind": record["source"]["kind"],
        "id": record["id"],
        "owner": owner,
        "subject": _subject(record),
        "thread": record["thread"],
        "also": [],
    }


def _ended_at(record: dict) -> str | None:
    """When a done record ended: its agent end's time, or its answer's."""
    return ((record["end"] or record["answer"] or {}).get("event") or {}).get("ts")


def _on_user(records: list[dict], threads: dict, within: dict) -> list[dict]:
    """On Me's rows, one per place the user has a move at: requests, then the updates
    to send again."""
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
    workflows: list[dict], records: list[dict], threads: dict, within: dict
) -> dict:
    """Select records once, by next actor.

    `workflows` are served strongest first, and `records` are the view's obligation
    records, the user's updates' and the agent's to-dos included, in inventory order.
    `threads` are the page's threads by id and `within` the document's containment,
    which say what a thread is about."""
    on_user = _on_user(records, threads, within)
    owing = {
        record["id"]: record
        for record in records
        if record["next_actor"] == "agent" and record["source"]["kind"] == "update"
    }
    served = dict.fromkeys(
        workflow["obligation"]
        for workflow in workflows
        if workflow["obligation"] in owing
    )
    on_agent = [_record_row(owing[identity], "agent") for identity in served]
    on_agent += [
        _record_row(record, "agent")
        for record in records
        if record["source"]["kind"] == "todo" and is_open(record)
    ]
    ended = sorted(
        (record for record in records if not is_open(record)),
        key=lambda record: (
            (at := _ended_at(record)) is not None,
            aware_instant(at) if at else None,
        ),
        reverse=True,
    )
    done = [
        _record_row(
            record,
            "agent" if record["source"]["kind"] in {"update", "todo"} else "user",
        )
        for record in ended
    ]
    return {"on_user": on_user, "on_agent": on_agent, "done": done}
