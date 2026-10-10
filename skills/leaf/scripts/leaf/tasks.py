"""Tasks, the one item on both queues, and the item the agent has in hand.

A task is something owed, and its `owner` says by whom: the agent or the user. How
it ends follows from its owner and what it stands on, so no field records it.

The agent's tasks are in the log. An item on the agent's queue is either a user move
it owes an answer, whose id is the move's event id (`workflows`), or a task it
opened. Working always names one of them: `leaf task start` writes a `start` event
naming the item with the line the banner shows, and the item is in hand, running,
from then on. An ephemeral reply to a move the agent owes writes the same start, its
text the line (`take_in_hand`), so the words the user reads in the thread and the
Working line are one write.

The agent's task is work it owes on a thread, a page widget, an element of the page,
or the page as a whole. `leaf task open` writes a `task` event, and it stands until a
`task_end` gives it one outcome, `done`, `failed` or `dropped`, with a detail saying
where the result is or why there is none, or until a stamped version that names its
widget with `--completes` ends it `done`, the note citing that version. A reply, a
resolution, another version, or the end of the session that opened it leaves it
open: that is what a task adds over a move, which its answer settles. Work that
outlasts the turn that took it on, such as a worker's build, a CI wait, or a change
promised for the next version, so stays on the agent's side: an open task holds its
thread `waiting` (`served_state.browser`), counts under `on_agent` in `page state`,
and is named in the banner. Work no user move asked for, such as writing or revising
the page on the agent's own initiative, is a task the agent opens on the page or the
widget or section it concerns; housekeeping, such as re-vendoring or restarting the
server, owes the user nothing and is no item.

Tasks on the user are explicit `task` events opened with `--on user`, ending at
Done or an agent end. Questions are separate canonical records (`questions`),
selected directly by work queues, never synthesized into tasks. The existing
`task_end` write can also withdraw an open prose request by its Question id or
source-message id; that withdraws the request without recording a user answer.
A stamped document declaring `lf-review=sign-off` adds an approval Question
for that exact public version; only its unwithdrawn approval answers it.

A start lasts until its item ends: a task's end, or for a move the reply or stamped
version that answers it (`workflows.canonical_workflows`), and it holds its item
only for the turn that wrote it. It names that turn, and once the turn ends with the
item still running, the activity fold reads it stalled (`activity`). A later start on
the same item replaces it, which is how the next turn takes the item in hand again.
A `waiting` or `idle` declaration puts down every start written before it: the
moves those started are no longer in hand, and the tasks stay open with nothing
running on them. The put-down is a `put_down` event in the log, which `leaf status`
writes ahead of the declaration whenever a start stands (`put_down`), so admission,
which reads only the document and the log, sees it as every other reader does. A
start on a page declared `idle` reopens the page with a bare `waiting` after it,
which writes no `put_down`.

The door admits the agent's task on an open thread, on a live page widget that
declares `x-work` or holds an unsettled move (`work.widget_seat_error`), on any
element of the page, or on the page, and a task on the user on any of those but a
thread, a widget needing no seat; a start on an open task of the agent's or a move
the agent owes; and an end of an open task, the user's only of one the agent opened
on them (`task_error`). `TaskReading` holds the log's tasks, starts and endings
for one event basis; `canonical_tasks` supplies the same fold to standalone callers.
`WorkReading.page_tasks` attaches thread and activity readings to explicit tasks.

Not yet: a task whose session has ended reads open until another session ends it.

Experimental: tasks and the two queues are new, and their shape is expected to
change a lot (notes/what-needs-you/). Change them freely; nothing outside this
repository depends on them.
"""

import sys
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from .events import note_settlements, taken_back

OUTCOMES = ("done", "failed", "dropped")

# What `task open` takes for the page as a whole; any other id names a thread, a
# widget, or an element of the page.
PAGE_SUBJECT = "page"


def start_reading(event: dict) -> dict | None:
    """One work-start reading, from an explicit start or addressed progress reply.

    A progress reply retains its message identity and history while atomically
    taking the declared input in hand. Its text is the same visible Working line.
    """
    if event["kind"] == "start":
        return event
    if event["kind"] == "reply" and "start" in event:
        return {**event, "kind": "start", **event["start"]}
    return None


def item_starts(events: list) -> dict[str, dict]:
    """The start standing on each item, by the item's id: the newest naming it, unless
    a `put_down` came after it."""
    starts: dict[str, dict] = {}
    for event in events:
        if start := start_reading(event):
            starts[start["item"]] = start
        elif event["kind"] == "put_down":
            starts.clear()
    return starts


def last_start(events: list) -> str | None:
    """When the agent last took an item in hand, which renews the turn that did."""
    return next(
        (event["ts"] for event in reversed(events) if start_reading(event)), None
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


def _outcome(event: dict, detail: str | None) -> dict:
    """How an event ended a task: which, when, by whom, and the detail it gave."""
    return {
        "id": event["id"],
        "seq": event["seq"],
        "ts": event["ts"],
        "detail": detail,
        "author": event["author"],
        "agent": event.get("agent"),
        "session": event.get("session"),
    }


@dataclass(frozen=True)
class TaskReading:
    """Task facts for one admitted log. Consumers share this in-memory reading;
    no derived state survives the transaction or chooses a different event basis."""

    events: list

    @cached_property
    def withdrawn(self) -> set:
        return taken_back(self.events)

    @cached_property
    def starts(self) -> dict:
        return item_starts(self.events)

    @cached_property
    def tasks(self) -> list[dict]:
        return _tasks(self.events, self.withdrawn, self.starts)

    @cached_property
    def ends(self) -> dict:
        return _ends(self.events, self.withdrawn)

    @property
    def owed(self) -> list[dict]:
        return [
            task
            for task in self.tasks
            if task["state"] == "open" and task["owner"] == "agent"
        ]


def _tasks(events: list, withdrawn: set, standing: dict) -> list[dict]:
    tasks: dict[str, dict] = {}

    def end(task: dict, state: str, event: dict, detail: str | None) -> None:
        task["state"] = state
        task["outcome"] = _outcome(event, detail)

    for event in events:
        if event["kind"] == "task":
            if "owner" not in event:
                continue
            tasks[event["id"]] = {
                "id": event["id"],
                "owner": event["owner"],
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
        elif (
            event["kind"] == "task_end"
            and event["task"] in tasks
            and event["id"] not in withdrawn
        ):
            end(tasks[event["task"]], event["outcome"], event, event.get("detail"))
        elif event["kind"] == "note":
            for identity in note_settlements(event, "task"):
                task = tasks.get(identity)
                if task is not None and task["state"] == "open":
                    end(task, "done", event, f"v{event['version']}")
    for task in tasks.values():
        if task["state"] == "open" and task["id"] in standing:
            task["running"] = running(standing[task["id"]])
    return list(tasks.values())


def _ends(events: list, withdrawn: set) -> dict:
    return {
        event["task"]: {
            "state": event["outcome"],
            **_outcome(event, event.get("detail")),
        }
        for event in events
        if event["kind"] == "task_end" and event["id"] not in withdrawn
    }


def canonical_tasks(events: list) -> list[dict]:
    """Every logged task, including ended ones and the standing start on open ones.
    A task without an owner from an earlier runtime is absent."""
    return TaskReading(events).tasks


def owed_tasks(events: list) -> list[dict]:
    """The agent's tasks nothing has ended: the work it still owes."""
    return TaskReading(events).owed


def log_tasks_open(events: list) -> list[dict]:
    """The log's open tasks on either side, even when their targets are gone."""
    return [task for task in canonical_tasks(events) if task["state"] == "open"]


# Explicit committed work ends through its owner, independently of Questions.
ENDS_BY_AGENT = "agent"
ENDS_BY_DONE = "done"


def task_error(
    event: dict,
    log: TaskReading,
    threads: dict,
    *,
    seat_error,
    element_error,
    user_widget_error,
    owed: set[str],
    tasks,
    questions,
) -> str | None:
    """Why the append door refuses a task event, or None.

    Explicit work stands on an admitted widget, page element, page or open thread;
    user-owned work cannot stand on a thread. A start names an open agent task or
    an owed move. Either side can end explicit work within its ownership rules.
    An agent end may also withdraw an open prose Question by canonical id or source
    message id, while widget Questions remain owned by their declared state.
    """
    kind = event["kind"]
    if kind == "task":
        subject = event["subject"]
        if subject["kind"] == "widget":
            return (
                seat_error(subject["id"])
                if event["owner"] == "agent"
                else user_widget_error(subject["id"])
            )
        if subject["kind"] == "element":
            return element_error(subject["id"])
        if subject["kind"] == "page":
            return None
        if event["owner"] == "user":
            return (
                f"{subject['id']!r} is a thread, where a task on the user is a "
                "question: ask it there with `leaf thread reply --awaits`"
            )
        thread = threads.get(subject["id"])
        if thread is None:
            return f"{subject['id']!r} is not a thread on this page"
        if thread["resolved"]:
            return f"thread {subject['id']!r} is resolved; reopen it before a task"
        return None
    if kind == "start":
        if error := start_line_error(event["text"]):
            return error
        item = event["item"]
        if item in owed or any(task["id"] == item for task in log.owed):
            return None
        return (
            f"{item!r} is neither an open task of yours nor an update you owe an answer to; start the "
            "id a delivered update or `leaf task open` gave you"
        )
    if kind != "task_end":
        return None
    identity = event["task"]
    task = next((task for task in tasks() if task["id"] == identity), None)
    if task is None:
        question = next(
            (question for question in questions() if identity == question["id"]),
            None,
        )
        if question is not None:
            if question["source"]["kind"] == "approval":
                return (
                    f"Question {identity!r} requires the user's approval of "
                    f"v{question['source']['version']}; it ends at the page's Approval control"
                )
            if question["source"]["kind"] == "widget":
                return f"{identity!r} is a widget Question; its source owns the answer, so retire it in the document"
            if event["author"] != "agent":
                return "the user's reply or settling reaction answers a prose Question"
            if question["status"] != "open":
                return f"Question {identity!r} has already {question['status']}"
            return None
        if ended := log.ends.get(identity):
            return f"task {identity!r} has already ended ({ended['state']})"
        return f"unknown task {identity!r}"
    if task["state"] != "open":
        return f"task {identity!r} has already ended ({task['state']})"
    if event["author"] == "user" and task["ends"] != ENDS_BY_DONE:
        return f"task {identity!r} is the agent's; the user ends only a task on them"
    return None


def cmd_open(page_dir: Path, subject: str, title: str, owner: str) -> dict:
    """Open a task titled `title`, owed by `owner`, on what `subject` names: a thread,
    by any message in it or a widget frozen in it (the agent's own task only), a page
    widget, any other element of the page by its id, or `page` for the page as a
    whole; the record."""
    from .event_contracts import append_admitted
    from .harness import message_identity
    from .leases import contract_writer
    from .revisioning import activate_source
    from .service import PageTransaction
    from .work import page_element, page_subject

    @contract_writer
    def write(page_dir: Path) -> dict:
        with PageTransaction(page_dir) as page:
            activate_source(page_dir, transaction=page)
            named = (
                {"kind": "page"}
                if subject == PAGE_SUBJECT
                else page_subject(page_dir, page.events, subject)
                or page_element(page_dir, subject)
            )
            if named is None:
                sys.exit(
                    f"{subject!r} names no thread, widget or element on this page; "
                    f"`{PAGE_SUBJECT}` names the page as a whole"
                )
            return append_admitted(
                page,
                {
                    "kind": "task",
                    "author": "agent",
                    **message_identity(),
                    "owner": owner,
                    "subject": named,
                    "title": title,
                },
            )

    return write(page_dir)


def start_line_error(text: str) -> str | None:
    """Why `text` cannot be a start's line, or None. The banner's dot already says
    the agent is working; the line is the whole of what a start adds, and one
    sentence is what the banner has room for."""
    if not text.strip() or "\n" in text or "\r" in text:
        return (
            "a start's line names the work and its subject in one sentence, such as "
            '"running the browser suite against the new banner"'
        )
    return None


def take_in_hand(page, item: str, text: str, identity: dict) -> dict:
    """Append the start taking `item` in hand with `text` as its line, written as
    `identity`, within `page`, an open `service.PageTransaction`; the record.

    The start names the claimant's turn when the posting session holds the page, which
    is what lets that turn end over the move it started (`activity.started_in_turn`)
    and what ends the start's hold with the turn. Another session's start names none: a
    Claude Code subagent runs as its parent's session, so workers leave starts to the
    session driving the page. `leaf task start` writes this explicit event. Addressed ephemeral replies
    carry their start on the message itself (`thread.post_reply`), and every
    start consumer reads either form through `start_reading`."""
    from .event_contracts import append_admitted

    claim = page.claim
    turn = (
        claim.get("turn") if claim and claim["id"] == identity.get("session") else None
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
    # Work in hand reopens a page the agent had closed: `idle` says it was done with
    # the page, and every watcher stands down for an idle page. The reopening is a
    # bare declaration, with no `put_down` to take this start back.
    if page.status["state"] == "idle":
        page.set_status("waiting", "")
    return record


def cmd_start(page_dir: Path, item: str, text: str) -> dict:
    """Take `item`, a move's event id or an open task's id, in hand for this turn with
    `text` as its line (`take_in_hand`); the record."""
    from .harness import message_identity
    from .leases import contract_writer
    from .revisioning import activate_source
    from .service import PageTransaction

    if error := start_line_error(text):
        sys.exit(error)

    @contract_writer
    def write(page_dir: Path) -> dict:
        with PageTransaction(page_dir) as page:
            activate_source(page_dir, transaction=page)
            return take_in_hand(page, item, text, message_identity())

    return write(page_dir)


def put_down(page) -> dict | None:
    """Put down every start standing on the page `page`, an open
    `service.PageTransaction`, as `leaf status waiting` and `idle` do; the record, or
    None when no start stands and the log has nothing to add."""
    from .event_contracts import append_admitted
    from .harness import message_identity

    if not item_starts(page.events):
        return None
    return append_admitted(
        page, {"kind": "put_down", "author": "agent", **message_identity()}
    )


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
