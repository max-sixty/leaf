"""Tasks, the one item on both queues, and the item the agent has in hand.

A task is something owed, and its `owner` says by whom: the agent or the user. How
it ends follows from its owner and what it stands on, so no field records it.

The agent's tasks are in the log. An item on the agent's queue is either a user move
it owes an answer, whose id is the move's event id (`workflows`), or a task it
opened. Working always names one of them: `leaf task start` writes a `start` event
naming the item with the line the banner shows, and the item is in hand, running,
from then on.

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

The user's tasks come from three places, and their owner and subject say how each
ends. Each Ask in the markup is one, under the Ask's id, from the version that adds
it, ended `done` when its widget is answered (`asks`); each agent turn in a thread
that asks the user (`asks.thread_awaits_user`) is one, under that turn's id, ended by
the user's reply there or a settling reaction; the document starts state, so neither
writes an event, and `page_tasks` reads them. The third is a `task` event the agent
writes with `--on user` on a widget, an element or the page, never a thread, where
the question is the task. Nothing else answers it, so it ends at the user's Done,
their own `task_end`, which `undo` takes back. The agent can end any task on the
user but an Ask's, which the markup holds and a version retires: ending a question's
settles it, since the prompt reading takes an ended one off the user (`task_ends`).

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
on them (`task_error`). Every reader takes the log's tasks from `canonical_tasks`,
every task on the page from `page_tasks` and `ask_tasks`, and starts from
`item_starts`.

Not yet: a task whose session has ended reads open until another session ends it.

Experimental: tasks and the two queues are new, and their shape is expected to
change a lot (notes/what-needs-you/). Change them freely; nothing outside this
repository depends on them.
"""

import sys
from pathlib import Path

from .events import conversation_turns, is_reaction, note_settlements, taken_back

OUTCOMES = ("done", "failed", "dropped")

# What `task open` takes for the page as a whole; any other id names a thread, a
# widget, or an element of the page.
PAGE_SUBJECT = "page"


def item_starts(events: list) -> dict[str, dict]:
    """The start standing on each item, by the item's id: the newest naming it, unless
    a `put_down` came after it."""
    starts: dict[str, dict] = {}
    for event in events:
        if event["kind"] == "start":
            starts[event["item"]] = event
        elif event["kind"] == "put_down":
            starts.clear()
    return starts


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


def canonical_tasks(events: list) -> list[dict]:
    """Every task the log holds, oldest first, with its current state and the start
    running on it while it is open. An ending naming no task the log holds is skipped,
    as other folds skip a lost line, and so is a task with no `owner`, which an earlier
    Leaf wrote."""
    tasks: dict[str, dict] = {}
    withdrawn = taken_back(events)

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
    standing = item_starts(events)
    for task in tasks.values():
        if task["state"] == "open" and task["id"] in standing:
            task["running"] = running(standing[task["id"]])
    return list(tasks.values())


def task_ends(events: list) -> dict[str, dict]:
    """Each task id a `task_end` names, to how it ended. The user's tasks that an Ask
    or a thread's question holds have no `task` event, so their ending is read here,
    and the readings of those Asks and questions take an ended one off the user. The
    user's Done taken back with `undo` ends nothing."""
    withdrawn = taken_back(events)
    return {
        event["task"]: {
            "state": event["outcome"],
            **_outcome(event, event.get("detail")),
        }
        for event in events
        if event["kind"] == "task_end" and event["id"] not in withdrawn
    }


def owed_tasks(events: list) -> list[dict]:
    """The agent's tasks nothing has ended: the work it still owes."""
    return [
        task
        for task in canonical_tasks(events)
        if task["state"] == "open" and task["owner"] == "agent"
    ]


def log_tasks_open(events: list) -> list[dict]:
    """The log's tasks nothing has ended, on either side: what a version or a layer
    must leave a target for (`work.tasks_without_targets`)."""
    return [task for task in canonical_tasks(events) if task["state"] == "open"]


# How a task ends, the one reading of it every reader takes (`ends` on each task):
# the agent's at its `task_end` or a version's `--completes`, an Ask's when its widget
# answers it, a question's at the user's reply or a settling reaction, and any other
# task on the user at their Done.
ENDS_BY_AGENT = "agent"
ENDS_BY_WIDGET = "widget"
ENDS_BY_REPLY = "reply"
ENDS_BY_DONE = "done"


def _log_task(task: dict) -> dict:
    """One of the log's tasks as `page_tasks` serves it, with how it ends."""
    return {
        **task,
        "ends": ENDS_BY_AGENT if task["owner"] == "agent" else ENDS_BY_DONE,
        "ask": None,
    }


def _derived(
    identity: str,
    subject: dict,
    thread: str | None,
    state: str,
    ends: str,
    *,
    ended: dict | None = None,
    ask: dict | None = None,
    message: dict | None = None,
) -> dict:
    """A task on the user that the page's markup or a thread's question holds rather
    than a `task` event, in the shape of the log's: it has no title of its own, and
    nobody opened it. `ended` is the `task_end` that ended it (`task_ends`), if one
    did."""
    return {
        "id": identity,
        "owner": "user",
        "subject": subject,
        "thread": thread,
        "title": None,
        "state": ended["state"] if ended else state,
        "seq": message["seq"] if message else None,
        "ts": message["ts"] if message else None,
        "agent": message.get("agent") if message else None,
        "session": message.get("session") if message else None,
        "revision": None,
        "running": None,
        "outcome": {key: value for key, value in ended.items() if key != "state"}
        if ended
        else None,
        "ends": ends,
        "ask": ask,
    }


def ask_tasks(asks: dict) -> tuple[list[dict], list[dict]]:
    """The user's tasks one Ask reading holds (`{all, user, unanswered}`,
    `asks.page_ask_readings` or `asks.thread_ask_readings`), as the open ones and the
    ended ones.

    Each Ask is a task on the user under the Ask's own id, open while it is
    unanswered and `done` once its widget answers it, with `ask` naming the widget
    that answers and whether a thread in that widget's seat holds it with the agent
    (`held_by_seat`), which takes it off the user's queue meanwhile. The markup holds
    it, so nothing else ends it: a version that removes the Ask, or marks it
    `restated`, retires it. A document's Asks are read with the document, so a page's
    are served with the version they stand in (`served_state.document`), and the
    queues read those of the version shown."""
    unanswered = {ask["id"] for ask in asks["unanswered"]}
    on_user = {ask["id"] for ask in asks["user"]}
    standing: list[dict] = []
    ended: list[dict] = []
    for ask in asks["all"]:
        task = _derived(
            ask["id"],
            {"kind": "widget", "id": ask["id"]},
            ask["thread"],
            "open" if ask["id"] in unanswered else "done",
            ENDS_BY_WIDGET,
            ask={
                "tag": ask["tag"],
                "widget": ask["source"],
                "widget_tag": ask["source_tag"],
                "held_by_seat": ask["id"] in unanswered and ask["id"] not in on_user,
            },
        )
        (standing if task["state"] == "open" else ended).append(task)
    return standing, ended


def page_tasks(
    log: list[dict], thread_asks: dict, threads: list[dict], ends: dict[str, dict]
) -> tuple[list[dict], list[dict]]:
    """Every task the page holds beside the page version's own Asks
    (`ask_tasks`), as the open ones and the ended ones, each with its `owner`, how it
    `ends`, and the `thread` it stands in.

    `log` is the log's tasks (`canonical_tasks`), each stamped with its thread, the
    agent's open ones as the activity fold aged them. `thread_asks` is the frozen
    threads' Ask reading, and `threads` the served threads, whose `user_prompt` names
    the agent turn a thread's question stands on: a thread whose agent turn asks the
    user in prose is a task on the user under that turn's id, open until the user
    answers it in the thread, settles it with a reaction, or the agent ends it with a
    `task_end` in `ends`. An answered question is done, its outcome the user's move
    that answered it (`_answer`), so the Queue panel lists it with the other ended
    tasks."""
    standing, ended = ask_tasks(thread_asks)
    held = {task["id"] for task in log}
    for thread in threads:
        prompt = thread["user_prompt"]
        for message in thread["msgs"]:
            if prompt is not None and message["id"] == prompt["message"]:
                outcome = None
            elif message["id"] in ends and message["id"] not in held:
                outcome = ends[message["id"]]
            elif message.get("awaits") and (answer := _answer(thread, message)):
                outcome = {"state": "done", **_outcome(answer, None)}
            else:
                continue
            task = _derived(
                message["id"],
                {"kind": "thread", "id": thread["id"]},
                thread["id"],
                "open",
                ENDS_BY_REPLY,
                ended=outcome,
                message=message,
            )
            (standing if task["state"] == "open" else ended).append(task)
    for task in log:
        task = _log_task(task)
        (standing if task["state"] == "open" else ended).append(task)
    return standing, ended


def _answer(thread: dict, question: dict) -> dict | None:
    """The user's move that answered a question asked with `--awaits` and no longer
    standing: their next turn in its thread, or their reaction on it. A question the
    agent asked again before the user moved has none until the user answers the later
    one, which answers both."""
    return next(
        (
            message
            for message in thread["msgs"]
            if message["author"] == "user"
            and message["seq"] > question["seq"]
            and (
                message.get("parent") == question["id"]
                if is_reaction(message)
                else message in conversation_turns(thread)
            )
        ),
        None,
    )


def task_error(
    event: dict,
    events: list,
    threads: dict,
    *,
    seat_error,
    element_error,
    user_widget_error,
    owed: set[str],
    tasks,
) -> str | None:
    """Why the append door refuses a task event, or None.

    The agent's task stands on an open thread of `threads` (`events.build_threads`),
    on a widget `seat_error` admits, on an element `element_error` admits, or on the
    page. A task it puts on the user stands on an element `element_error` admits, a
    widget `user_widget_error` admits, which is no Ask, since an Ask already is a task
    on the user, or the page, and not on a thread, where a question asked with
    `--awaits` is the task on the user. A start names an open task of the agent's or a
    move in `owed`, the inputs of the moves on the agent.

    An outcome ends a task still open, one of `tasks()`, every task on the page
    (`page_tasks`), read only for an outcome. Who may end it is how it `ends`: the
    agent its own and any on the user but an Ask's, which the markup holds; the user
    only one their Done ends."""
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
        item = event["item"]
        if item in owed or any(task["id"] == item for task in owed_tasks(events)):
            return None
        return (
            f"{item!r} is neither an open task of yours nor a move you owe; start the "
            "id a delivered move or `leaf task open` gave you"
        )
    if kind != "task_end":
        return None
    identity = event["task"]
    task = next((task for task in tasks() if task["id"] == identity), None)
    if task is None:
        if ended := task_ends(events).get(identity):
            return f"task {identity!r} has already ended ({ended['state']})"
        return f"unknown task {identity!r}"
    if task["ends"] == ENDS_BY_WIDGET:
        return (
            f"task {identity!r} is an Ask's, which ends when its widget answers it; "
            "to retire the Ask, leave it out of a stamped version, or mark it "
            "`restated` there"
        )
    if task["state"] != "open":
        return f"task {identity!r} has already ended ({task['state']})"
    if event["author"] == "user" and task["ends"] != ENDS_BY_DONE:
        return (
            f"task {identity!r} is the agent's; the user ends only a task on them"
            if task["ends"] == ENDS_BY_AGENT
            else f"task {identity!r} is a question in its thread, which the user's "
            "reply or a settling reaction answers"
        )
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
            # reopening is a bare declaration, with no `put_down` to take this start
            # back.
            if page.status["state"] == "idle":
                page.set_status("waiting", "")
            return record

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
