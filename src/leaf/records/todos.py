"""To-dos, the work the agent owes, and the item the agent is working on.

A to-do is work the agent owes, on its On <agent> list: an obligation record whose
source is the agent's own promise (`source.kind` `todo`), which says where it stands as
every record does (`standing`). Nothing is a to-do on the
user: everything On Me is an obligation whose source says how the user answers it,
a widget's own controls or a reply in a thread (`obligations`), so Leaf adds no Done
of its own to any of them. The user chose this over a to-do on the user
(`leaf task create --on user`): the widget or thread
an ask stands on is sovereign over how it is answered, and a step such as trying a
build is asked in a thread, which the user's reply answers, in words or a reaction.

An item on the agent's list is either an update it owes an answer, whose id is the
update's event id (`workflows`), or a to-do it opened. `leaf task start` writes a
`start` event naming one item and the line the page's status shows as Working, and the
item is in hand from then on. An ephemeral reply writes the same start, with its text
as the line, on an owed update it addresses, or on the open to-do an answer opened,
addressed by that answer's update or the to-do's own message (`thread.post_reply`), so
the thread and the Working line show the same words.

A to-do is on a thread, a page widget, an element, or the whole page.
`leaf task create` writes a `todo` event. A reply that promises work it doesn't
deliver carries the to-do's title as `todo`, which opens a to-do on the reply's
thread under the reply's id (`todo_reading`), so one write answers the message and
keeps the work on the agent. The to-do stays open until a `todo_end` gives it an
outcome, `done`, `failed` or `dropped`, with a detail saying where the result is or
why there is none, or until a stamped version naming its widget with `--completes`
ends it `done`. A reply, a resolution, another version, or the end of the session
that opened it leaves it open; that is what a to-do adds over an update, which its
answer settles. An open to-do keeps its thread the agent's (`standing.leading`),
counts under `queues.on_agent` in `page state`, and shows in the page's status.
`../../../skills/leaf/references/conversation-loop.md` tells the agent which work gets a to-do.

A to-do may name, in the agent's words, what its work waits on that the agent doesn't
control (`waiting_on`), such as the user's pick elsewhere on the page or another
change landing. The record carries it until the first start on the to-do, which
says the agent has taken the work up, so a later lapse reads stalled rather than
waiting again, or until the to-do ends. Leaf reads nothing from the words: it shows them, and never decides
the wait is over. They are words rather than the id of a record on the page, since
what work waits on is as often off the page, such as a review or another session's
change. So that the agent needn't remember a held to-do across a long session, each
delivery from the page lists it (`delivery.batch_data`, `held`), and the agent
judges at each input whether that input ends the wait.

A `todo_end` names only a to-do. A question the agent asked in a thread, which the
user answered elsewhere or which no longer applies, ends when the agent resolves the
thread (`obligations`).

A start lasts until its item ends: the to-do's end, or for an update, the reply or
stamped version that answers it (`workflows.handed_over`). It is a lease on the item,
held by the turn that wrote it: the item reads `running` while that turn runs, and once
the turn ends with the item still in hand, `blocked` (`activity`). Work that outlives
the turn is whatever else holds the lease, another session's start or the claimant's
background work (`standing`). A later start on the same item
replaces it, which is how the next turn takes the item up again. The `status` event
that `leaf page open` and `leaf page close` write puts down every earlier start
(`item_starts`), leaving their to-dos open with nothing running; admission, which
reads only the document and the log, sees it there. A start on a page declared
`idle` reopens the page (`activity.declaration`).

Any agent session can end any open to-do, whoever opened or last started it: a
start shows who is at work, and gives no right over the to-do's end. The user
decided this. Letting only the session that last started a to-do end it would
make another session start the to-do first, a step that protects nothing.

Admission (`todo_error`) accepts a `todo` on a thread, the page, any element, or a
widget the newest revision declares (`work.widget_seat_error`). It accepts a `start` on an open to-do or an owed update,
and a `todo_end` of an open to-do.
`TodoReading` reads the log's to-dos, starts and ends, and `work_state` serves
each standing as `activity` reads it. The `leaf task` commands that write them are
`tasks`'.

A plan (`plans`) arranges to-dos and obligations into an outline without owning them, so no
rule here reads it.

Experimental: to-dos and the two lists are new, and their shape is expected to
change a lot. Change them freely; nothing outside this repository depends on them.
"""

from dataclasses import dataclass
from functools import cached_property

from leaf.base.findings import Finding
from leaf.base.standing import ended, is_open, on
from leaf.log.events import note_settlements, taken_back, unshown
from leaf.log.thread_context import thread_ids, thread_names

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


def _end(event: dict, detail: str | None) -> dict:
    """How an event ended a to-do, as a record's `end`: the detail it gave, and which
    event, when and by whom."""
    return {
        "detail": detail,
        "event": {key: event[key] for key in ("id", "seq", "ts", "author")},
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
        """The `todo_end` in force on each to-do it names, by the to-do's id."""
        return {
            event["todo"]: {
                "outcome": event["outcome"],
                "detail": event.get("detail"),
                **{key: event[key] for key in ("id", "seq", "ts", "author")},
            }
            for event in self.events
            if event["kind"] == "todo_end" and event["id"] not in self.withdrawn
        }

    @cached_property
    def todos(self) -> list[dict]:
        return _todos(self.events, self.ends, self.starts)

    @property
    def owed(self) -> list[dict]:
        return [todo for todo in self.todos if is_open(todo)]


def _todos(events: list, ends: dict, starts: dict) -> list[dict]:
    """Every to-do the log opened, as the obligation record it is: its title as the
    prompt, what it waits on until a start takes it up or it ends (`waiting_on`), the start in
    force on an open one as its `line`, and how it ended, by its
    `todo_end` in force (`ends`) or by the first stamped version whose `--completes`
    names it, whichever came first. Its `thread` is the one it was opened on; a reader
    holding the thread markup adds a widget's (`work_state.work_state`)."""
    todos: dict[str, dict] = {}
    threads = thread_names(events)
    for event in events:
        if opened := todo_reading(event, threads):
            subject = opened["subject"]
            todos[opened["id"]] = {
                "id": opened["id"],
                "source": {"kind": "todo", "id": opened["id"], "subject": subject},
                "thread": subject["id"] if subject["kind"] == "thread" else None,
                "message": None,
                "prompt": {"text": opened["title"], "target": subject.get("id")},
                "answer": None,
                "end": None,
                **on("agent"),
                "waiting_on": opened.get("waiting_on"),
                "line": None,
                "seq": opened["seq"],
                "ts": opened["ts"],
                "agent": opened.get("agent"),
                "session": opened.get("session"),
                "revision": opened.get("revision"),
            }
        elif (start := start_reading(event)) and start["item"] in todos:
            todos[start["item"]]["waiting_on"] = None
        elif event["kind"] == "note":
            for identity in note_settlements(event, "todo"):
                todo = todos.get(identity)
                closed = ends.get(identity)
                if (
                    todo is not None
                    and is_open(todo)
                    and (closed is None or closed["seq"] > event["seq"])
                ):
                    todo.update(ended("done"))
                    todo["end"] = _end(event, f"v{event['version']}")
    for todo in todos.values():
        if is_open(todo) and (closed := ends.get(todo["id"])):
            todo.update(ended(closed["outcome"]))
            todo["end"] = _end(closed, closed["detail"])
        if is_open(todo) and todo["id"] in starts:
            todo["line"] = running(starts[todo["id"]])
        if not is_open(todo):
            todo["waiting_on"] = None
    return list(todos.values())


def todo_error(
    event: dict,
    log: TodoReading,
    *,
    seat_error,
    element_error,
    owed: set[str],
    items,
) -> Finding | None:
    """Why the append door refuses a to-do, start or completion, or None.

    A to-do stands on an admitted thread, widget, page element or page. Replies can
    also open work on their own thread (`todo_reading`). A start names an open to-do or
    an owed update. An end names an open to-do, and one naming one of the user's
    obligations is refused with how that obligation ends.
    """
    kind = event["kind"]
    if kind == "todo":
        subject = event["subject"]
        if subject["kind"] == "thread":
            if subject["id"] not in thread_ids(log.events) or subject["id"] in unshown(
                log.events, log.withdrawn
            ):
                return Finding("missing-thread", values={"thread": subject["id"]})
            return None
        if subject["kind"] == "widget":
            return seat_error(subject["id"])
        if subject["kind"] == "element":
            return element_error(subject["id"])
        return None
    if kind == "start":
        item = event["item"]
        if item in owed or any(todo["id"] == item for todo in log.owed):
            return None
        return Finding("unowed-start", values={"item": item})
    if kind != "todo_end":
        return None
    identity = event["todo"]
    named = {"todo": identity}
    todo = next((todo for todo in log.todos if todo["id"] == identity), None)
    if todo is None:
        item = next((item for item in items() if identity == item["id"]), None)
        if item is not None:
            return Finding(
                "obligation-end",
                values={**named, "message": item["message"]},
            )
        if closed := log.ends.get(identity):
            return Finding("ended-todo", values={**named, "state": closed["outcome"]})
        return Finding("unknown-todo", values=named)
    if not is_open(todo):
        return Finding("ended-todo", values={**named, "state": todo["outcome"]})
    return None
