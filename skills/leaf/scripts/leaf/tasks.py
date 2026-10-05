"""The agent's queue as the log holds it: the tasks it opens and the item it has in hand.

An item on the agent's queue is either a user move it owes an answer, whose id is the
move's event id (`workflows`), or a task it opened. Working always names one of them:
`leaf task start` writes a `start` event naming the item with the line the banner
shows, and the item is in hand, running, from then on.

A task is work the agent owes on a thread, a page widget, or the page as a whole.
`leaf task open` writes a `task` event, and it stands until a `task_end` gives it one
outcome, `done`, `failed` or `dropped`, with a detail saying where the result is or
why there is none, or until a stamped version that names its widget with
`--completes` ends it `done`, the note citing that version. A reply, a resolution,
another version, or the end of the session that opened it leaves it open: that is
what a task adds over a move, which its answer settles. Work that outlasts the turn
that took it on, such as a worker's build, a CI wait, or a change promised for the
next version, so stays on the agent's side: an open task holds its thread `waiting`
(`served_state.browser`), counts under `on_agent` in `page state`, and is named in
the banner. Work no user move asked for, such as writing or revising the page on the
agent's own initiative, is a task the agent opens on the page or the widget it
concerns; housekeeping, such as re-vendoring or restarting the server, owes the user
nothing and is no item.

A start lasts until its item ends: a task's end, or for a move the reply or stamped
version that answers it (`workflows.canonical_workflows`), and it holds its item
only for the turn that wrote it. It names that turn, and once the turn ends with the
item still running, the activity fold reads it stalled (`activity`). A later start on
the same item replaces it, which is how the next turn takes the item in hand again.
A `waiting` or `idle` declaration puts down every start written before it: the
moves those started are no longer in hand, and the tasks stay open with nothing
running on them (`workflows.canonical_workflows`, `put_down`). A start on a page
declared `idle` reopens the page with a bare `waiting` just before it.

The door admits a task on an open thread, on a live page widget that declares
`x-work` or holds an unsettled move (`work.widget_seat_error`), or on the page; a
start on an open task or a move the agent owes. Every reader takes tasks from
`canonical_tasks` and starts from `item_starts`.

Not yet: a task whose session has ended reads open until another session ends it.

Experimental: tasks and the two queues are new, and their shape is expected to
change a lot (notes/what-needs-you/). Change them freely; nothing outside this
repository depends on them.
"""

import sys
from pathlib import Path

from .events import note_settlements

OUTCOMES = ("done", "failed", "dropped")

# What `task open` takes for the page as a whole; an element id names a widget.
PAGE_SUBJECT = "page"


def item_starts(events: list) -> dict[str, dict]:
    """The newest `start` naming each item, by the item's id."""
    return {event["item"]: event for event in events if event["kind"] == "start"}


def last_start(events: list) -> str | None:
    """When the agent last took an item in hand, which renews the turn that did."""
    return next(
        (event["ts"] for event in reversed(events) if event["kind"] == "start"), None
    )


def running(start: dict) -> dict:
    """The reading a start gives the item it names: the line, when and by whom, and
    the turn it holds the item for (`turn` is None for a start another session
    wrote)."""
    return {
        "id": start["id"],
        "item": start["item"],
        "text": start["text"],
        "seq": start["seq"],
        "ts": start["ts"],
        "agent": start.get("agent"),
        "session": start.get("session"),
        "turn": start.get("turn"),
    }


def canonical_tasks(events: list) -> list[dict]:
    """Every task the log holds, oldest first, with its current state and the start
    running on it while it is open. An ending naming no task the log holds is skipped,
    as other folds skip a lost line."""
    tasks: dict[str, dict] = {}

    def end(task: dict, state: str, event: dict, detail: str | None) -> None:
        task["state"] = state
        task["running"] = None
        task["outcome"] = {
            "id": event["id"],
            "seq": event["seq"],
            "ts": event["ts"],
            "detail": detail,
            "agent": event.get("agent"),
            "session": event.get("session"),
        }

    for event in events:
        if event["kind"] == "task":
            tasks[event["id"]] = {
                "id": event["id"],
                "subject": event["subject"],
                "title": event["title"],
                "state": "open",
                "seq": event["seq"],
                "ts": event["ts"],
                "agent": event.get("agent"),
                "session": event.get("session"),
                "revision": event.get("revision"),
                "running": None,
                "outcome": None,
            }
            continue
        if event["kind"] == "start":
            task = tasks.get(event["item"])
            if task is not None and task["state"] == "open":
                task["running"] = running(event)
        elif event["kind"] == "task_end" and event["task"] in tasks:
            end(tasks[event["task"]], event["outcome"], event, event.get("detail"))
        elif event["kind"] == "note":
            for identity in note_settlements(event, "task"):
                task = tasks.get(identity)
                if task is not None and task["state"] == "open":
                    end(task, "done", event, f"v{event['version']}")
    return list(tasks.values())


def open_tasks(events: list) -> list[dict]:
    """The tasks nothing has ended."""
    return [task for task in canonical_tasks(events) if task["state"] == "open"]


def task_error(
    event: dict, events: list, threads: dict, seat_error, owed: set[str]
) -> str | None:
    """Why the append door refuses a task event, or None.

    A task stands on an open thread of `threads` (`events.build_threads`), on a widget
    `seat_error` admits, or on the page; an outcome ends a task still open; a start
    names an open task or a move in `owed`, the inputs of the moves on the agent."""
    kind = event["kind"]
    if kind == "task":
        subject = event["subject"]
        if subject["kind"] == "widget":
            return seat_error(subject["id"])
        if subject["kind"] == "page":
            return None
        thread = threads.get(subject["id"])
        if thread is None:
            return f"{subject['id']!r} is not a thread on this page"
        if thread["resolved"]:
            return f"thread {subject['id']!r} is resolved; reopen it before a task"
        return None
    if kind == "start":
        item = event["item"]
        if item in owed or any(task["id"] == item for task in open_tasks(events)):
            return None
        return (
            f"{item!r} is neither an open task nor a move you owe; start the id a "
            "delivered move or `leaf task open` gave you"
        )
    if kind != "task_end":
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
    """Open a task titled `title` on what `subject` names: a thread, by any message in
    it or a widget frozen in it, a page widget, or `page` for the page as a whole;
    the record."""
    from .event_contracts import append_admitted
    from .harness import message_identity
    from .leases import contract_writer
    from .revisioning import activate_source
    from .service import PageTransaction
    from .work import page_subject

    @contract_writer
    def write(page_dir: Path) -> dict:
        with PageTransaction(page_dir) as page:
            activate_source(page_dir, transaction=page)
            named = (
                {"kind": "page"}
                if subject == PAGE_SUBJECT
                else page_subject(page_dir, page.events, subject)
            )
            if named is None:
                sys.exit(
                    f"{subject!r} names no thread or widget on this page; "
                    f"`{PAGE_SUBJECT}` names the page as a whole"
                )
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


def cmd_start(page_dir: Path, item: str, text: str) -> dict:
    """Take `item`, a move's event id or an open task's id, in hand for this turn with
    `text` as its line; the record.

    The start names the claimant's turn when the posting session holds the page, which
    is what lets that turn end over the move it started (`activity.started_in_turn`)
    and what ends the start's hold with the turn. Another session's start names none: a
    Claude Code subagent runs as its parent's session, so workers leave starts to the
    session driving the page."""
    from .event_contracts import append_admitted
    from .harness import message_identity
    from .leases import contract_writer
    from .revisioning import activate_source
    from .service import PageTransaction

    # The banner's dot already says the agent is working; the line is the whole of
    # what a start adds, and one sentence is what the banner has room for.
    if not text.strip() or "\n" in text or "\r" in text:
        sys.exit(
            "a start's line names the work and its subject in one sentence, such as "
            '"running the browser suite against the new banner"'
        )

    @contract_writer
    def write(page_dir: Path) -> dict:
        with PageTransaction(page_dir) as page:
            activate_source(page_dir, transaction=page)
            identity = message_identity()
            claim = page.claim
            turn = (
                claim.get("turn")
                if claim and claim["id"] == identity.get("session")
                else None
            )
            record = append_admitted(
                page,
                {
                    "kind": "start",
                    "author": "agent",
                    **identity,
                    "item": item,
                    "text": text,
                    **({"turn": turn} if turn else {}),
                },
            )
            # Work in hand reopens a page the agent had closed: `idle` says it was
            # done with the page, and every carrier stands down for an idle page. The
            # reopening `waiting` stands just before this start, which it would
            # otherwise put down.
            if page.status["state"] == "idle":
                page.set_status("waiting", "", after=record["seq"] - 1)
            return record

    return write(page_dir)


def cmd_end(page_dir: Path, task: str, outcome: str, detail: str | None) -> dict:
    """End `task` with `outcome`, `detail` saying where the result is or why there
    is none; the record."""
    from .event_contracts import append_admitted
    from .harness import message_identity
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
