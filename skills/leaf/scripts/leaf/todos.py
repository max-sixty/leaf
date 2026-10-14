"""To-dos, the one kind of item on both lists, and the item the agent is working on.

A to-do is work someone owes. Its `owner` is the agent, whose to-dos are on its
On <agent> list, or the user, whose to-dos are on their On me list. How a to-do ends
follows from its owner and what it is on, so no field records that.

An item on the agent's list is either an update it owes an answer, whose id is the
update's event id (`workflows`), or a to-do it opened. `leaf task start` writes a
`start` event naming one item and the line the banner shows as Working, and the
item is in hand from then on. An ephemeral reply to an owed update writes the same
start, with its text as the line (`take_in_hand`), so the thread and the Working
line show the same words.

The agent's to-do is on a thread, a page widget, an element, or the whole page.
`leaf task open` writes a `todo` event. A reply that promises work it doesn't
deliver carries the to-do's title as `todo`, which opens a to-do on the reply's
thread under the reply's id (`todo_reading`), so one write answers the message and
keeps the work on the agent. The to-do stays open until a `todo_end` gives it an
outcome, `done`, `failed` or `dropped`, with a detail saying where the result is or
why there is none, or until a stamped version naming its widget with `--completes`
ends it `done`. A reply, a resolution, another version, or the end of the session
that opened it leaves it open; that is what a to-do adds over an update, which its
answer settles. An open to-do keeps its thread `waiting` (`served_state.browser`),
counts under `queues.on_agent` in `page state`, and shows in the banner.
`../../references/conversation-loop.md` tells the agent which work gets a to-do.

A to-do on the user is a `todo` event opened with `--on user`, ended by the user's
Done or by the agent. Asks are separate records (`asks`) that the lists read
directly, never turned into to-dos. The agent's `todo_end` can also close an open
prose ask by its ask id: `done` when the user answered it elsewhere, `dropped` when
it no longer applies, never `failed`. Neither records an answer from the user
(`asks.thread_asks`). A stamped version declaring `lf-review=sign-off` adds an
approval ask for that version, which only an approval the user has not withdrawn
answers.

A start lasts until its item ends: the to-do's end, or for an update, the reply or
stamped version that answers it (`workflows.canonical_workflows`). It names the turn
that wrote it and holds its item only for that turn; once that turn ends with the
item still running, `activity` shows it stalled. A later start on the same item
replaces it, which is how the next turn takes the item up again. `leaf status
waiting` and `idle` first write a `put_down` event when any start is in force
(`put_down`). The `put_down` ends every earlier start, leaving their to-dos open
with nothing running. It is an event so that admission, which reads only the
document and the log, sees it. A start on a page declared `idle` reopens the page with a plain
`waiting` after it, which writes no `put_down`.

Only the session that wrote an agent to-do's latest start can end it, by `todo_end`
or a stamp's `--completes` (`TodoReading.completion_error`), and a later start from
another session moves that right. Putting work down changes activity, not this
right: neither a turn ending nor a change of claim gives it back to an earlier
session, and the same session can still end the to-do in a later turn. Before any
start, any agent session can end it. Commands run outside a harness all share one
empty session identity, so Leaf can't tell them apart.

Admission (`todo_error`) accepts an agent's `todo` on the page, on any element, or
on a live widget that declares `x-work` or holds an unsettled action
(`work.widget_seat_error`), and a to-do on the user on any element or on a widget
with no open ask. It accepts a `start` on an open agent to-do or an owed update, and
a `todo_end` of an open to-do; the user ends only a to-do opened on them.
`TodoReading` reads the log's to-dos, starts and ends, and `WorkReading.page_todos`
adds their thread and activity readings.

When `leaf task end` ends a to-do on an element `done`, and that element still shows
unfolded on the newest revision (not inside a closed details, a later tab or
[hidden]) with nothing on it or inside it on either list, the command advises moving
it
(`finished_in_view`), because agents had left pages that were mostly finished work.
The agent judges whether the element is finished work or the page's current
content.

Experimental: to-dos and the two lists are new, and their shape is expected to
change a lot (notes/what-needs-you/). Change them freely; nothing outside this
repository depends on them.
"""

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from .events import note_settlements, taken_back
from .findings import Finding, Rejected
from .thread_context import thread_names

# What `task open` takes for the page as a whole; any other id names a widget or an
# element of the page.
PAGE_SUBJECT = "page"


def todo_reading(event: dict, threads: dict[str, str]) -> dict | None:
    """One to-do-opening reading, from a `todo` event or a reply that carries one.

    `threads` is `thread_context.thread_names`, which names the thread a reply's
    to-do stands on. A reply's to-do keeps the reply's identity, as its start does."""
    if event["kind"] == "todo":
        return event if "owner" in event else None
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
    def todos(self) -> list[dict]:
        return _todos(self.events, self.withdrawn, self.starts)

    @cached_property
    def ends(self) -> dict:
        return _ends(self.events, self.withdrawn)

    @property
    def owed(self) -> list[dict]:
        return [
            todo
            for todo in self.todos
            if todo["state"] == "open" and todo["owner"] == "agent"
        ]

    def completion_error(self, event: dict, todo: dict) -> Finding | None:
        """Whether the writer can end this agent to-do under its latest start.

        Read the log rather than `starts`, whose in-hand reading a `put_down`
        clears. Admission alone checks authority; projections consume admitted
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


def _todos(events: list, withdrawn: set, starts: dict) -> list[dict]:
    todos: dict[str, dict] = {}

    def end(todo: dict, state: str, event: dict, detail: str | None) -> None:
        todo["state"] = state
        todo["outcome"] = _outcome(event, detail)

    threads = thread_names(events)
    for event in events:
        if opened := todo_reading(event, threads):
            event = opened
            todos[event["id"]] = {
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
            event["kind"] == "todo_end"
            and event["todo"] in todos
            and event["id"] not in withdrawn
        ):
            end(todos[event["todo"]], event["outcome"], event, event.get("detail"))
        elif event["kind"] == "note":
            for identity in note_settlements(event, "todo"):
                todo = todos.get(identity)
                if todo is not None and todo["state"] == "open":
                    end(todo, "done", event, f"v{event['version']}")
    for todo in todos.values():
        if todo["state"] == "open" and todo["id"] in starts:
            todo["running"] = running(starts[todo["id"]])
    return list(todos.values())


def _ends(events: list, withdrawn: set) -> dict:
    return {
        event["todo"]: {
            "state": event["outcome"],
            **_outcome(event, event.get("detail")),
        }
        for event in events
        if event["kind"] == "todo_end" and event["id"] not in withdrawn
    }


def owed_todos(events: list) -> list[dict]:
    """The agent's to-dos nothing has ended: the work it still owes."""
    return TodoReading(events).owed


def todo_error(
    event: dict,
    log: TodoReading,
    *,
    seat_error,
    element_error,
    user_widget_error,
    owed: set[str],
    todos,
    asks,
) -> Finding | None:
    """Why the append door refuses a to-do, start or completion, or None.

    A to-do stands on an admitted widget, page element or page; a to-do on a
    thread is opened by the reply that promises it (`todo_reading`), which the
    schema keeps off a `todo` event. A start names an open agent to-do or an owed
    update. Both completion carriers share `TodoReading.completion_error`.
    Either side can end a to-do within its ownership rules. An agent end may
    also withdraw an open prose ask by canonical id or source message id, while
    widget asks remain owned by their declared state.
    """
    kind = event["kind"]
    if kind == "todo":
        subject = event["subject"]
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
    todo = next((todo for todo in todos() if todo["id"] == identity), None)
    if todo is None:
        ask = next(
            (ask for ask in asks() if identity == ask["id"]),
            None,
        )
        if ask is not None:
            if ask["source"]["kind"] == "approval":
                return Finding(
                    "approval-ask",
                    values={**named, "version": ask["source"]["version"]},
                )
            if ask["source"]["kind"] == "widget":
                return Finding("widget-ask", values=named)
            if event["author"] != "agent":
                return Finding("users-prose-ask", values=named)
            if ask["status"] != "open":
                return Finding("ended-ask", values={**named, "status": ask["status"]})
            if event["outcome"] == "failed":
                return Finding("failed-prose-ask", values=named)
            return None
        if ended := log.ends.get(identity):
            return Finding("ended-todo", values={**named, "state": ended["state"]})
        return Finding("unknown-todo", values=named)
    if todo["state"] != "open":
        return Finding("ended-todo", values={**named, "state": todo["state"]})
    if event["author"] == "user" and todo["owner"] != "user":
        return Finding("agents-todo", values=named)
    return log.completion_error(event, todo)


def cmd_open(page_dir: Path, subject: str, title: str, owner: str) -> dict:
    """Open a to-do titled `title`, owed by `owner`, on what `subject` names: a page
    widget, any other element of the page by its id, or `page` for the page as a
    whole; the record. A thread takes its work from the reply that promises it, and
    its ask for the user from a reply that asks it."""
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
                    **message_identity(),
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
    start consumer reads either form through `start_reading`."""
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
    # Work in hand reopens a page the agent had closed: `idle` says it was done with
    # the page, and every watcher stands down for an idle page. The reopening is a
    # bare declaration, with no `put_down` to take this start back.
    if page.status["state"] == "idle":
        page.set_status("waiting", "")
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


def put_down(page) -> dict | None:
    """Put down every start in force on the page `page`, an open
    `service.PageTransaction`, as `leaf status waiting` and `idle` do; the record, or
    None when no start stands and the log has nothing to add."""
    from .event_contracts import append_admitted
    from .harness import message_identity

    if not item_starts(page.events):
        return None
    record, _ = append_admitted(
        page, {"kind": "put_down", "author": "agent", **message_identity()}
    )
    return record


def finished_in_view(page_dir: Path, end: dict) -> Finding | None:
    """Advice naming the element a `done` end finished, where it still stands among
    the open work (`work.open_ids`) and nothing on it or inside it, a thread anchored
    there included, is on either list; else None."""
    from .event_log import read_events
    from .served_state.context import read_page
    from .served_state.page import read_served_page
    from .work import open_ids

    if end["outcome"] != "done":
        return None
    events = read_events(page_dir)
    subject = next(
        (
            todo["subject"]
            for todo in TodoReading(events).todos
            if todo["id"] == end["todo"]
        ),
        None,
    )
    if subject is None or subject["kind"] != "element":
        return None
    within = open_ids(page_dir, subject["id"])
    if within is None:
        return None
    served, _, _ = read_served_page(read_page(page_dir, events))
    view = served["browser"]["views"][str(served["active"]["revision"])]
    # A thread item stands where its thread is anchored.
    anchored = {
        thread["id"]: thread["anchor"].get("section")
        for thread in view["thread"]["threads"]
        if thread["anchor"]
    }
    if any(
        (
            anchored.get(item["subject"]["id"])
            if item["subject"]["kind"] == "thread"
            else item["subject"].get("id")
        )
        in within
        for side in ("on_user", "on_agent")
        for item in view["queues"][side]
    ):
        return None
    return Finding(
        "finished-in-view", values={"element": subject["id"]}, severity="advice"
    )


def cmd_end(page_dir: Path, todo: str, outcome: str, detail: str | None) -> dict:
    """End `todo` with `outcome`, `detail` saying where the result is or why there
    is none; the record."""
    from .event_contracts import append_admitted
    from .harness import message_identity
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
                    **message_identity(),
                    "todo": todo,
                    "outcome": outcome,
                    **({"detail": detail} if detail is not None else {}),
                },
            )
            return record

    return write(page_dir)
