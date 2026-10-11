"""The work queues: what is on the user, what is on the agent, and what is done.

Questions, explicit tasks and response workflows are separate readings; this is the
one selection that adds them up. A Question is never a task: its source owns its
answer, and only an explicit user task ends at the user's Done. A browser view serves
these lists and `page state` prints them, so the banner's counts, the Questions
panel and an agent picking the page up read one selection. The browser places its own
unresolved sends against the served lists (`build/browser/application.ts`,
`localQueues`); it never selects them again.

An item names its subject and the thread it stands in. A Question item keeps its
canonical record, and a task item the task's fields a row draws. Each done item adds
how it ended (`state`), when (`ended`), and the outcome's detail.
"""

from .work import at_work


def _task_item(task: dict) -> dict:
    """One task as an item on the queue of its `owner`."""
    return {
        "kind": "task",
        "id": task["id"],
        "owner": task["owner"],
        "subject": task["subject"],
        "thread": task["thread"],
        "title": task["title"],
        "running": task["running"],
        "agent": task["agent"],
        "session": task["session"],
        "ends": task["ends"],
    }


def _question_item(question: dict) -> dict:
    """One Question on a work queue; it retains its canonical record."""
    source = question["source"]
    subject = (
        {"kind": "widget", "id": source["id"]}
        if source["kind"] == "widget"
        else {"kind": "page"}
        if source["kind"] == "approval"
        else {"kind": "thread", "id": question["thread"]}
    )
    return {
        "kind": "question",
        "id": question["id"],
        "owner": "user",
        "subject": subject,
        "thread": question["thread"],
        "title": question["prompt"]["text"],
        "running": None,
        "agent": None,
        "session": None,
        "ends": source["kind"],
        "question": question,
    }


def queues(
    threads: list[dict],
    workflows: list[dict],
    tasks: list[dict],
    ended_tasks: list[dict],
    questions: dict,
) -> dict:
    """Select Question obligations, explicit tasks and response recovery once.

    `threads` carry their attention, `workflows` are served strongest first, `tasks`
    are the open tasks on either side and `ended_tasks` the ended ones, and
    `questions` is a `questions.collection`. A Question's canonical next actor
    selects its queue; explicit work and delivery recovery keep their own completion
    routes. A move handed back in a thread is that thread's recovery item, and one
    handed back outside any thread is its own."""
    on_you = [_question_item(question) for question in questions["user"]]
    on_you += [_task_item(task) for task in tasks if task["owner"] == "user"]
    on_you += [
        {
            "kind": "recovery",
            "id": thread["id"],
            "subject": {"kind": "thread", "id": thread["id"]},
            "thread": thread["id"],
        }
        for thread in threads
        if thread["attention"] is not None
        and thread["attention"]["kind"] == "needs_user"
        and thread["attention"]["reason"] == "recovery"
    ]
    on_agent = []
    for workflow in workflows:
        item = {
            "id": workflow["id"],
            "subject": workflow["subject"],
            "thread": workflow["thread"],
        }
        if workflow["next_actor"] == "user":
            if workflow["thread"] is None:
                on_you.append({"kind": "recovery", **item})
        elif workflow["answer"] is not None:
            on_agent.append(
                {
                    "kind": "answer",
                    **item,
                    "answer": workflow["answer"],
                    "stage": workflow["stage"],
                }
            )
        elif at_work(workflow):
            on_agent.append({"kind": "work", **item, "detail": workflow["detail"]})
    on_agent += [_task_item(task) for task in tasks if task["owner"] == "agent"]
    done = [
        {
            **_question_item(question),
            "state": "done" if question["status"] == "answered" else "dropped",
            "ended": ((question["answer"] or {}).get("event") or {}).get("ts"),
            "detail": None,
        }
        for question in questions["all"]
        if question["status"] != "open"
    ]
    done += [
        {
            **_task_item(task),
            "state": task["state"],
            "ended": (task["outcome"] or {}).get("ts"),
            "detail": (task["outcome"] or {}).get("detail"),
        }
        for task in ended_tasks
    ]
    return {"on_you": on_you, "on_agent": on_agent, "done": done}
