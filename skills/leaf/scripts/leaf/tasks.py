"""Tasks: work the agent has taken on, held in the log until it ends.

A task is one thing the agent owes on a thread the user can see. `leaf task open`
writes a `task` event naming the thread, and `leaf task end` a `task_end` naming the
task with one outcome, `done`, `failed` or `dropped`, and a detail saying where the
result is or why there is none. Nothing else ends a task. A reply, a resolution, a
version or the end of the session that opened it leaves it open, which is what a task
adds over a reply's obligation (`workflows`) and a status claim (`work`): a reply
settles the move it answers and a claim lapses with its turn, while a task stands
until its outcome is written. Work that outlasts the turn that took it on, such as a
worker's build, a CI wait or a change promised for the next version, so stays on
the agent's side: an open task holds its thread `waiting` (`served_state.browser`),
counts under `on_agent` in `page state`, and is named in the banner.

A task opens on an open thread, by any message in it or a widget frozen in its
markup; the door refuses a resolved thread and anything else. The fold is the log's
alone, so every reader takes it from `canonical_tasks`.

Not yet: a task whose session has ended reads open until another session ends it.
"""

import sys
from pathlib import Path

OUTCOMES = ("done", "failed", "dropped")


def canonical_tasks(events: list) -> list[dict]:
    """Every task the log holds, oldest first, with its current state. An outcome
    naming no task the log holds is skipped, as other folds skip a lost line."""
    tasks: dict[str, dict] = {}
    for event in events:
        if event["kind"] == "task":
            tasks[event["id"]] = {
                "id": event["id"],
                "subject": event["subject"],
                "title": event["title"],
                "state": "open",
                "seq": event["seq"],
                "ts": event["ts"],
                "agent": event["agent"],
                "session": event["session"],
                "outcome": None,
            }
        elif event["kind"] == "task_end" and event["task"] in tasks:
            tasks[event["task"]]["state"] = event["outcome"]
            tasks[event["task"]]["outcome"] = {
                "id": event["id"],
                "seq": event["seq"],
                "ts": event["ts"],
                "detail": event.get("detail"),
                "agent": event["agent"],
                "session": event["session"],
            }
    return list(tasks.values())


def open_tasks(events: list) -> list[dict]:
    """The tasks no `task_end` has ended."""
    return [task for task in canonical_tasks(events) if task["state"] == "open"]


def task_error(event: dict, events: list, threads: dict) -> str | None:
    """Why the append door refuses a task event: a task stands on an open thread
    of `threads` (`events.build_threads`), and an outcome ends a task still open."""
    if event["kind"] == "task":
        subject = event["subject"]
        thread = threads.get(subject["id"]) if subject["kind"] == "thread" else None
        if thread is None:
            return f"a task stands on a thread; {subject['id']!r} is not one"
        if thread["resolved"]:
            return f"thread {subject['id']!r} is resolved; reopen it before a task"
        return None
    if event["kind"] != "task_end":
        return None
    task = next(
        (task for task in canonical_tasks(events) if task["id"] == event["task"]),
        None,
    )
    if task is None:
        return f"unknown task {event['task']!r}"
    if task["state"] != "open":
        return f"task {event['task']!r} has already ended ({task['state']})"
    return None


def cmd_open(page_dir: Path, subject: str, title: str) -> dict:
    """Open a task on the thread `subject` names, by any message in it or a widget
    frozen in it, in the posting session's voice; the record."""
    from .event_contracts import append_admitted
    from .host import message_identity
    from .leases import contract_writer
    from .service import PageTransaction
    from .work import page_subject

    @contract_writer
    def write(page_dir: Path) -> dict:
        with PageTransaction(page_dir) as page:
            named = page_subject(page_dir, page.events, subject)
            if named is None or named["kind"] != "thread":
                sys.exit(f"{subject!r} names no thread on this page")
            return append_admitted(
                page,
                {
                    "kind": "task",
                    "author": "agent",
                    **message_identity(),
                    "subject": named,
                    "title": title,
                },
            )

    return write(page_dir)


def cmd_end(page_dir: Path, task: str, outcome: str, detail: str | None) -> dict:
    """End `task` with `outcome`, `detail` saying where the result is or why there
    is none; the record."""
    from .event_contracts import append_admitted
    from .host import message_identity
    from .leases import contract_writer
    from .service import PageTransaction

    @contract_writer
    def write(page_dir: Path) -> dict:
        with PageTransaction(page_dir) as page:
            return append_admitted(
                page,
                {
                    "kind": "task_end",
                    "author": "agent",
                    **message_identity(),
                    "task": task,
                    "outcome": outcome,
                    **({"detail": detail} if detail is not None else {}),
                },
            )

    return write(page_dir)
