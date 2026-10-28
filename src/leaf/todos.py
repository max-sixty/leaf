"""To-dos, the one kind of item on both lists, and the item the agent is working on.

A to-do is work someone owes. Its `owner` is the agent, whose to-dos are on its
On <agent> list, or the user, whose to-dos are on their On me list. How a to-do ends
follows from its owner and what it is on, so no field records that.

An item on the agent's list is either an update it owes an answer, whose id is the
update's event id (`workflows`), or a to-do it opened. `leaf task start` writes a
`start` event naming one item and the line the page's status shows as Working, and the
item is in hand from then on. An ephemeral reply to an owed update writes the same
start, with its text as the line (`take_in_hand`), so the thread and the Working
line show the same words.

The agent's to-do is on a thread, a page widget, an element, or the whole page.
`leaf task create` writes a `todo` event. A reply that promises work it doesn't
deliver carries the to-do's title as `todo`, which opens a to-do on the reply's
thread under the reply's id (`todo_reading`), so one write answers the message and
keeps the work on the agent. The to-do stays open until a `todo_end` gives it an
outcome, `done`, `failed` or `dropped`, with a detail saying where the result is or
why there is none, or until a stamped version naming its widget with `--completes`
ends it `done`. A reply, a resolution, another version, or the end of the session
that opened it leaves it open; that is what a to-do adds over an update, which its
answer settles. An open to-do keeps its thread `waiting` (`served_state.browser`),
counts under `queues.on_agent` in `page state`, and shows in the page's status.
`../../skills/leaf/references/conversation-loop.md` tells the agent which work gets a to-do.

A to-do on the user is a `todo` event opened with `--on user`, ended by the user's
Done or by the agent. It publishes a canonical obligation (`obligations`) that the
lists read directly. Its explicit completion remains owned by this fold. The agent's `todo_end` can also close an open
question the user answers in words, a message sent with `--obligation`, by its obligation id:
`done` when the user answered it elsewhere, `dropped` when it no longer applies,
never `failed`. Neither records an answer from the user (`obligations.settle_by_words`).

A start lasts until its item ends: the to-do's end, or for an update, the reply or
stamped version that answers it (`workflows.handed_over`). It names the turn
that wrote it and holds its item only for that turn; once that turn ends with the
item still running, `activity` shows it stalled. A later start on the same item
replaces it, which is how the next turn takes the item up again. The `status` event
that `leaf page open` and `leaf page close` write puts down every earlier start
(`item_starts`), leaving their to-dos open with nothing running; admission, which
reads only the document and the log, sees it there. A start on a page declared
`idle` reopens the page (`activity.declaration`).

Only the session that wrote an agent to-do's latest start can end it, by `todo_end`
or a stamp's `--completes` (`TodoReading.completion_error`), and a later start from
another session moves that right. Putting work down changes activity, not this
right: neither a turn ending nor a change of claim gives it back to an earlier
session, and the same session can still end the to-do in a later turn. Before any
start, any agent session can end it. Commands run outside a harness all share one
empty session identity, so Leaf can't tell them apart.

Admission (`todo_error`) accepts an agent's `todo` on the page, on any element, or
on a live widget that declares `x-work` or holds an unsettled action
(`work.widget_seat_error`), and a to-do on the user on a thread, any element or a widget
with no open obligation. It accepts a `start` on an open agent to-do or an owed update, and
a `todo_end` of an open to-do; the user ends only a to-do opened on them.
`TodoReading` reads the log's to-dos, starts and ends, and `WorkReading.page_todos`
adds their thread and activity readings.

A plan (`plans`) arranges to-dos and obligations into an outline without owning them, so no
rule here reads it.

Experimental: to-dos and the two lists are new, and their shape is expected to
change a lot. Change them freely; nothing outside this repository depends on them.
"""

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from .events import note_settlements, taken_back
from .findings import Finding, Rejected
from .obligations import answered_in_words
from .thread_context import thread_ids, thread_names

# What `task create` takes for the page as a whole; any other id names a widget or an
# element of the page.
PAGE_SUBJECT = "page"


def todo_reading(event: dict, threads: dict[str, str]) -> dict | None:
    """One to-do-opening reading, from a `todo` event or a reply that carries one.

    `threads` is `thread_context.thread_names`, which names the thread a reply's
    to-do stands on. A reply's to-do keeps the reply's identity, as its start does."""
    if event["kind"] == "todo":
        return event
    if event["kind"] == "reply" and "todo" in event:
        return {
            **event,
            "kind": "todo",
            "owner": "agent",
            "subject": {"kind": "thread", "id": threads[event["id"]]},
            "title": event["todo"],
        }
    return None


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
    """The start in force on each item, by the item's id: the newest naming it, unless
    a `status` declaration came after it."""
    starts: dict[str, dict] = {}
    for event in events:
        if start := start_reading(event):
            starts[start["item"]] = start
        elif event["kind"] == "status":
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
    """How an event ended a to-do: which, when, by whom, and the detail it gave."""
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
class TodoReading:
    """To-do facts for one admitted log. Consumers share this in-memory reading;
    no derived state survives the transaction or chooses a different event basis."""

    events: list

    @cached_property
    def withdrawn(self) -> set:
        return taken_back(self.events)

    @cached_property
    def starts(self) -> dict:
        return item_starts(self.events)

    @cached_property
    def ends(self) -> dict:
        """The `todo_end` in force on each id it names, by that id: a to-do's, or an
        obligation's the agent ended unanswered (`obligations.settle_by_words`)."""
        return {
            event["todo"]: {
                "state": event["outcome"],
                **_outcome(event, event.get("detail")),
            }
            for event in self.events
            if event["kind"] == "todo_end" and event["id"] not in self.withdrawn
        }

    @cached_property
    def todos(self) -> list[dict]:
        return _todos(self.events, self.ends, self.starts)

    @property
    def owed(self) -> list[dict]:
        return [
            todo
            for todo in self.todos
            if todo["state"] == "open" and todo["owner"] == "agent"
        ]

    def completion_error(self, event: dict, todo: dict) -> Finding | None:
        """Whether the writer can end this agent to-do under its latest start.

        Read the log rather than `starts`, whose in-hand reading a `status`
        declaration clears. Admission alone checks authority; projections consume admitted
        endings without reclassifying them against later activity or claims.
        """
        if todo["owner"] != "agent":
            return None
        latest = next(
            (
                start
                for logged in reversed(self.events)
                if (start := start_reading(logged)) and start["item"] == todo["id"]
            ),
            None,
        )
        if latest is not None and latest.get("session") != event.get("session"):
            return Finding(
                "todo-execution",
                values={
                    "todo": todo["id"],
                    "start": latest["id"],
                    "session": latest.get("session"),
                },
            )
        return None


def _todos(events: list, ends: dict, starts: dict) -> list[dict]:
    """Every to-do the log opened, with how it ended: by its `todo_end` in force
    (`ends`) or by the first stamped version whose `--completes` names it, whichever
    came first."""
    todos: dict[str, dict] = {}
    threads = thread_names(events)
    for event in events:
        if opened := todo_reading(event, threads):
            todos[opened["id"]] = {
                "id": opened["id"],
                "owner": opened["owner"],
                "subject": opened["subject"],
                "title": opened["title"],
                "state": "open",
                "seq": opened["seq"],
                "ts": opened["ts"],
                "agent": opened.get("agent"),
                "session": opened.get("session"),
                "revision": opened.get("revision"),
                "running": None,
                "outcome": None,
            }
        elif event["kind"] == "note":
            for identity in note_settlements(event, "todo"):
                todo = todos.get(identity)
                ended = ends.get(identity)
                if (
                    todo is not None
                    and todo["state"] == "open"
                    and (ended is None or ended["seq"] > event["seq"])
                ):
                    todo["state"] = "done"
                    todo["outcome"] = _outcome(event, f"v{event['version']}")
    for todo in todos.values():
        if todo["state"] == "open" and (ended := ends.get(todo["id"])):
            todo["state"] = ended["state"]
            todo["outcome"] = {key: ended[key] for key in ended if key != "state"}
        if todo["state"] == "open" and todo["id"] in starts:
            todo["running"] = running(starts[todo["id"]])
    return list(todos.values())


def todo_error(
    event: dict,
    log: TodoReading,
    *,
    seat_error,
    element_error,
    user_widget_error,
    owed: set[str],
    items,
    registry: dict,
) -> Finding | None:
    """Why the append door refuses a to-do, start or completion, or None.

    A to-do stands on an admitted thread, widget, page element or page.
    Replies can also open agent work on their own thread (`todo_reading`). A start names an open agent to-do or an owed
    update. Both completion carriers share `TodoReading.completion_error`.
    Either side can end a to-do within its ownership rules. An agent end may
    also end an open obligation the user answers in words (`obligations.answered_in_words`) by its id,
    while an obligation its widget's state answers stays owned by that state.
    """
    kind = event["kind"]
    if kind == "todo":
        subject = event["subject"]
        if subject["kind"] == "thread":
            if (
                subject["id"] not in thread_ids(log.events)
                or subject["id"] in log.withdrawn
            ):
                return Finding("missing-thread", values={"thread": subject["id"]})
            return None
        if subject["kind"] == "widget":
            return (
                seat_error(subject["id"])
                if event["owner"] == "agent"
                else user_widget_error(subject["id"])
            )
        if subject["kind"] == "element":
            return element_error(subject["id"])
        return None
    if kind == "start":
        item = event["item"]
        if item in owed or any(todo["id"] == item for todo in log.owed):
            return None
        return Finding("unowed-start", values={"item": item})
    if kind == "note":
        completed = note_settlements(event, "todo")
        for todo in log.owed:
            if todo["id"] in completed and (error := log.completion_error(event, todo)):
                return error
        return None
    if kind != "todo_end":
        return None
    identity = event["todo"]
    named = {"todo": identity}
    todo = next((todo for todo in log.todos if todo["id"] == identity), None)
    if todo is None:
        item = next(
            (item for item in items() if identity == item["id"]),
            None,
        )
        if item is not None:
            if not answered_in_words(item):
                return Finding("widget-obligation", values=named)
            if event["author"] != "agent":
                return Finding("users-question", values=named)
            if item["status"] != "open":
                return Finding(
                    "ended-obligation", values={**named, "status": item["status"]}
                )
            if event["outcome"] == "failed":
                return Finding("failed-question", values=named)
            return None
        if ended := log.ends.get(identity):
            return Finding("ended-todo", values={**named, "state": ended["state"]})
        return Finding("unknown-todo", values=named)
    if todo["state"] != "open":
        return Finding("ended-todo", values={**named, "state": todo["state"]})
    if event["author"] == "user" and todo["owner"] != "user":
        return Finding("agents-todo", values=named)
    return log.completion_error(event, todo)


def cmd_create(page_dir: Path, subject: str, title: str, owner: str) -> dict:
    """Create a to-do titled `title`, owed by `owner`, on what `subject` names: a page
    widget, thread, any other element of the page by its id, or `page` for the
    page as a whole; the record. A thread attachment supplies discussion context
    without making a reply complete the task."""
    from .event_contracts import append_admitted
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
                raise Rejected(
                    [
                        Finding(
                            "unknown-subject",
                            values={"subject": subject, "page": PAGE_SUBJECT},
                        )
                    ]
                )
            record, _ = append_admitted(
                page,
                {
                    "kind": "todo",
                    "author": "agent",
                    "owner": owner,
                    "subject": named,
                    "title": title,
                },
            )
            return record

    return write(page_dir)


def take_in_hand(page, item: str, text: str, identity: dict) -> dict:
    """Append the start taking `item` in hand with `text` as its line, written as
    `identity`, within `page`, an open `service.PageTransaction`; the record.

    The start names the claimant's turn when the posting session holds the page, which
    is what lets that turn end over the update it started (`activity.started_in_turn`)
    and what ends the start's hold with the turn. Another session's start names none: a
    Claude Code subagent runs as its parent's session, so workers leave starts to the
    session driving the page. `leaf task start` writes this explicit event. Addressed ephemeral replies
    carry their start on the message itself (`thread.post_reply`), and every
    start consumer reads either form through `start_reading`. A start on a page
    declared `idle` reopens it (`activity.declaration`)."""
    from .event_contracts import append_admitted

    claim = page.claim
    turn = claim["turn"] if claim and claim["id"] == identity.get("session") else None
    record, _ = append_admitted(
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
    return record


def cmd_start(page_dir: Path, item: str, text: str) -> dict:
    """Take `item`, an update's event id or an open to-do's id, in hand for this turn with
    `text` as its line (`take_in_hand`); the record."""
    from .harness import message_identity
    from .leases import contract_writer
    from .revisioning import activate_source
    from .service import PageTransaction

    @contract_writer
    def write(page_dir: Path) -> dict:
        with PageTransaction(page_dir) as page:
            activate_source(page_dir, transaction=page)
            return take_in_hand(page, item, text, message_identity())

    return write(page_dir)


def cmd_end(page_dir: Path, todo: str, outcome: str, detail: str | None) -> dict:
    """End `todo` with `outcome`, `detail` saying where the result is or why there
    is none; the record."""
    from .event_contracts import append_admitted
    from .leases import contract_writer
    from .revisioning import activate_source
    from .service import PageTransaction

    @contract_writer
    def write(page_dir: Path) -> dict:
        with PageTransaction(page_dir) as page:
            activate_source(page_dir, transaction=page)
            record, _ = append_admitted(
                page,
                {
                    "kind": "todo_end",
                    "author": "agent",
                    "todo": todo,
                    "outcome": outcome,
                    **({"detail": detail} if detail is not None else {}),
                },
            )
            return record

    return write(page_dir)
