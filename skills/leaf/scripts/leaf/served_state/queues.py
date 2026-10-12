"""The two lists, Questions and Tasks: what is on the user, what is on the agent,
and what is done.

Asks, to-dos and response workflows are separate readings; this is the one selection
that adds them up. An ask is never a to-do: its source owns its answer, and only a
to-do on the user, which the agent opened, ends at their Done. A browser view serves
these lists and `page state` prints them, so the banner's counts, the Questions panel
and an agent picking the page up read one selection. The browser places its own
unresolved sends against the served lists (`build/browser/application.ts`,
`localQueues`); it never selects them again.

Questions holds asks, to-dos on the user and resends; Tasks holds answers the agent
owes, work in hand on an update, and the agent's to-dos. An item names its kind, its
subject and the thread it stands in, and whether the agent has it in hand now
(`live`): a to-do a start holds, or an update the agent is at work on whose work has
not gone quiet or stopped. An ask item keeps its canonical record, and a to-do item
the fields a row draws. Each done item adds how it ended (`state`: an ask the user
answered, here or elsewhere, is `done`, a withdrawn one `dropped`), when (`ended`),
and the outcome's detail, which for an ask is its agent end's.
"""


def _todo_item(todo: dict) -> dict:
    """One to-do as an item on the list of its `owner`."""
    return {
        "kind": "todo",
        "id": todo["id"],
        "owner": todo["owner"],
        "subject": todo["subject"],
        "thread": todo["thread"],
        "title": todo["title"],
        "running": todo["running"],
        "live": todo["running"] is not None,
        "agent": todo["agent"],
        "session": todo["session"],
    }


def _ask_item(ask: dict) -> dict:
    """One ask on Questions; it retains its canonical record."""
    source = ask["source"]
    subject = (
        {"kind": "widget", "id": source["id"]}
        if source["kind"] == "widget"
        else {"kind": "page"}
        if source["kind"] == "approval"
        else {"kind": "thread", "id": ask["thread"]}
    )
    return {
        "kind": "ask",
        "id": ask["id"],
        "owner": "user",
        "subject": subject,
        "thread": ask["thread"],
        "title": ask["prompt"]["text"],
        "running": None,
        "live": False,
        "agent": None,
        "session": None,
        "ask": ask,
    }


def queues(
    threads: list[dict],
    workflows: list[dict],
    todos: list[dict],
    ended_todos: list[dict],
    asks: dict,
) -> dict:
    """Select asks, to-dos, resends and response obligations once.

    `threads` carry their attention, `workflows` are served strongest first, `todos`
    are the open to-dos on either side and `ended_todos` the ended ones, and `asks`
    is a `questions.collection`. An ask's canonical next actor selects its list;
    to-dos and resends keep their own completion routes. An update handed back in a
    thread is that thread's resend, and one handed back outside any thread is its
    own."""
    questions = [_ask_item(ask) for ask in asks["user"]]
    questions += [_todo_item(todo) for todo in todos if todo["owner"] == "user"]
    questions += [
        {
            "kind": "resend",
            "id": thread["id"],
            "subject": {"kind": "thread", "id": thread["id"]},
            "thread": thread["id"],
            "live": False,
        }
        for thread in threads
        if thread["attention"] is not None
        and thread["attention"]["kind"] == "needs_user"
        and thread["attention"]["reason"] == "resend"
    ]
    tasks = []
    for workflow in workflows:
        item = {
            "id": workflow["id"],
            "subject": workflow["subject"],
            "thread": workflow["thread"],
            "live": workflow["at_work"] and workflow["condition"] is None,
        }
        if workflow["next_actor"] == "user":
            if workflow["thread"] is None:
                questions.append({"kind": "resend", **item})
        elif workflow["answer"] is not None:
            tasks.append(
                {
                    "kind": "answer",
                    **item,
                    "answer": workflow["answer"],
                    "stage": workflow["stage"],
                }
            )
        elif workflow["at_work"]:
            tasks.append({"kind": "work", **item, "detail": workflow["detail"]})
    tasks += [_todo_item(todo) for todo in todos if todo["owner"] == "agent"]
    done = [
        {
            **_ask_item(ask),
            "state": "dropped" if ask["status"] == "withdrawn" else "done",
            "ended": ((ask["end"] or ask["answer"] or {}).get("event") or {}).get("ts"),
            "detail": ask["end"]["detail"] if ask["end"] else None,
        }
        for ask in asks["all"]
        if ask["status"] != "open"
    ]
    done += [
        {
            **_todo_item(todo),
            "state": todo["state"],
            "ended": (todo["outcome"] or {}).get("ts"),
            "detail": (todo["outcome"] or {}).get("detail"),
        }
        for todo in ended_todos
    ]
    return {"questions": questions, "tasks": tasks, "done": done}
