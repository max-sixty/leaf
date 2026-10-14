"""The two lists, On me (`on_user`) and On <agent> (`on_agent`): what is on the user,
what is on the agent, and what each has finished (`done`).

Asks, to-dos and response workflows are separate readings; this is the one selection
that adds them up. An ask is never a to-do: its source owns its answer, and only a
to-do on the user, which the agent opened, ends at their Done. A browser view serves
these lists and `page state` prints them, so the banner's counts, the On panel
and an agent picking the page up read one selection. The browser places its own
unresolved sends against the served lists (`build/browser/application.ts`,
`localQueues`); it never selects them again.

On me holds asks, to-dos on the user and resends; On <agent> holds answers the agent
owes, work in hand on an update, and the agent's to-dos. An item names its kind, its
subject, the list it stands on (`owner`), the thread it stands in, and whether the
agent has it in hand now (`live`): a to-do a start holds, or an update the agent is at
work on whose work has not gone quiet or stopped. An ask item keeps its canonical record, and a to-do item
the fields a row draws.

An item that leaves a list lands in that list's Done, which its `owner` names: On me's
holds the asks the user answered, here or elsewhere, or the agent withdrew, and the
to-dos the user ended; On <agent>'s holds the replies the agent sent, each the answer
it listed for the input the reply responds to, and the to-dos it ended. Each done item adds how it
ended (`state`: `done`, or `dropped` for a withdrawn ask, or a to-do's outcome), when
(`ended`), and the outcome's detail, which for an ask is its agent end's. Done is
served newest first, and an item without a time goes last. An answer the agent owes
in markup settles when a version writes the action in, which is the ask's Done, not a
reply, so it lands in none.
"""

from ..registry.schema import aware_instant
from ..thread import is_answer


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
    """One ask on the user's list, On me; it retains its canonical record."""
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
    is an `asks.collection`. An ask's canonical next actor selects its list;
    to-dos and resends keep their own completion routes. An update handed back in a
    thread is that thread's resend, and one handed back outside any thread is its
    own."""
    on_user = [_ask_item(ask) for ask in asks["user"]]
    on_user += [_todo_item(todo) for todo in todos if todo["owner"] == "user"]
    on_user += [
        {
            "kind": "resend",
            "id": thread["id"],
            "owner": "user",
            "subject": {"kind": "thread", "id": thread["id"]},
            "thread": thread["id"],
            "live": False,
        }
        for thread in threads
        if thread["attention"] is not None
        and thread["attention"]["kind"] == "needs_user"
        and thread["attention"]["reason"] == "resend"
    ]
    on_agent = []
    for workflow in workflows:
        item = {
            "id": workflow["id"],
            "subject": workflow["subject"],
            "thread": workflow["thread"],
            "live": workflow["at_work"] and workflow["condition"] is None,
        }
        if workflow["next_actor"] == "user":
            if workflow["thread"] is None:
                on_user.append({"kind": "resend", **item, "owner": "user"})
        elif workflow["answer"] is not None:
            on_agent.append(
                {
                    "kind": "answer",
                    **item,
                    "owner": "agent",
                    "answer": workflow["answer"],
                    "stage": workflow["stage"],
                }
            )
        elif workflow["at_work"]:
            on_agent.append(
                {"kind": "work", **item, "owner": "agent", "detail": workflow["detail"]}
            )
    on_agent += [_todo_item(todo) for todo in todos if todo["owner"] == "agent"]
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
    # A reply the agent sent is the answer On <agent> listed for the input it responds
    # to. The input's first answer takes that answer's identity, so the item keeps its
    # key as it moves; any later answer to the same input is its own item.
    answered = set()

    def answer_id(message: dict) -> str:
        first = message["responds"] not in answered
        answered.add(message["responds"])
        return message["responds"] if first else message["id"]

    done += [
        {
            "kind": "answer",
            "id": answer_id(message),
            "owner": "agent",
            "subject": {"kind": "thread", "id": thread["id"]},
            "thread": thread["id"],
            "live": False,
            "answer": {
                "kind": "reply",
                "for": message["responds"],
                "message": message["id"],
            },
            "state": "done",
            "ended": message["ts"],
            "detail": None,
        }
        for thread in threads
        for message in thread["msgs"]
        if is_answer(message)
    ]
    done.sort(
        key=lambda item: (
            item["ended"] is not None,
            aware_instant(item["ended"]) if item["ended"] else None,
        ),
        reverse=True,
    )
    return {"on_user": on_user, "on_agent": on_agent, "done": done}
