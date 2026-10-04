"""Agent-facing projected page state."""

import json
from pathlib import Path

from .construction import constructed_content
from .data import data_errors
from .data_contracts import measurement_lag_entries, page_data_binding_inventory
from .delivery import current_responses
from .document_reading import DocumentReading
from .events import bare_reaction, is_reaction
from .files import revision_path
from .passages import page_passages
from .projection import FrozenThreadReading, retirement_outcomes
from .registry.reactions import described
from .registry.storage import layer_metadata, require_registry
from .revision_artifact import active_enclosing
from .revisioning import activate_source
from .schema import DATA_DIR, DATA_FILE
from .served_state.browser import at_work
from .served_state.context import read_page
from .served_state.page import read_served_page
from .server import running_server
from .service import PageTransaction, unacknowledged
from .user_views import read_user_views
from .validation.admission import logged_id
from .work import page_subject

# How many of a thread's messages one `page state PAGE THREAD` prints by default.
HISTORY_LIMIT = 50


def standing_entry(coordinate, e: dict, thread: str | None = None) -> dict:
    """One standing action, in the shape `page state` reports every one of them.

    `revision` is the exact document the action was taken on, which for a widget an agent
    sent is a fact about the gesture and none about the widget: thread markup is
    frozen in the log, so no page version bounds one of these.
    """
    widget, unit, _verb = coordinate
    return {
        "widget": widget,
        "unit": unit,
        "action": e["action"],
        "detail": e["detail"],
        "revision": e["revision"],
        "seq": e["seq"],
        "thread": thread,
    }


def cmd_page_state(
    page_dir: Path,
    target: str | None = None,
    *,
    after: int | None = None,
    limit: int | None = None,
) -> None:
    """Print the agent-side state from one transaction-consistent snapshot: the
    page's, or the part `target` names — a thread with a page of its history, or a
    widget."""
    with PageTransaction(page_dir) as page:
        activation = activate_source(page_dir, transaction=page)
        _write_page_state(
            page_dir,
            page.events,
            activation.error,
            target=target,
            after=after,
            limit=limit,
        )


def _base_state(
    page_dir: Path,
    events: list,
    source_error: str | None,
    versions: list,
    active: dict | None,
    presence_reading: dict,
    threads: dict,
    stored_data: dict,
    registry: dict,
) -> dict:
    return {
        "page": str(page_dir),
        "layer": layer_metadata(page_dir),
        "title": "",
        "active": active,
        "versions": versions,
        "source": {
            "file": "index.html",
            "live": source_error is None and active is not None,
            "error": source_error,
        },
        **presence_reading,
        # The watcher's number where `pending` is the user's: everything a
        # wait would still print, workers' reports included.
        "unacked": len(unacknowledged(events, presence_reading["cursor"])),
        # The last physical log record folded into this transaction-consistent
        # snapshot. This is the continuation boundary for `page events --after`, not
        # the watcher's acknowledgement cursor above.
        "event_seq": events[-1]["seq"] if events else 0,
        "server": running_server(page_dir),
        "elements": [],
        "state": [],
        "updates": [],
        "data": {
            "file": DATA_FILE,
            "dir": DATA_DIR,
            "errors": data_errors(stored_data),
        },
        "data_bindings": page_data_binding_inventory(page_dir, registry, events),
        "measurement_lag": [],
        "asks": [],
        # What is on the user and what is on the agent, each item naming its
        # subject (`queues` below); and the tasks the agent has
        # open on the page (`tasks`).
        "queues": {"on_you": [], "on_agent": []},
        "tasks": [],
        # Current semantic facts only. A thread's history belongs to
        # `page state PAGE THREAD`; keeping its sequence list here would make this
        # default snapshot grow with every thread turn. A reaction nobody
        # has replied to opened no thread: it is paint on the page and
        # stands under `reactions` below.
        "threads": [
            {
                "id": thread_id,
                "title": thread["title"],
                "anchor": thread["anchor"],
                "detached_from": thread["detached_from"],
                "resolved": thread["resolved"] and thread["resolved"]["author"],
            }
            for thread_id, thread in threads.items()
            if not bare_reaction(thread)
        ],
        # Every reaction still standing — the agent-side reading of the marks
        # the page paints. A package may attach `means` to its own vocabulary.
        # On the page (`anchor`, or none for the page whole) while its thread is
        # unresolved; in a thread (`parent`) while that thread is open.
        "reactions": [
            described(
                {
                    "id": message["id"],
                    "token": message["token"],
                    "anchor": message.get("anchor"),
                    "about": message.get("about"),
                    "parent": message.get("parent"),
                    "thread": thread_id,
                    "revision": message.get("revision"),
                    "seq": message["seq"],
                },
                registry,
            )
            for thread_id, thread in threads.items()
            if not thread["resolved"]
            for message in thread["msgs"]
            if is_reaction(message)
        ],
    }


def _apply_document_state(
    state: dict,
    document: DocumentReading,
    stored_data: dict,
    registry: dict,
) -> None:
    parser = document.document
    projection = document.projection
    state["title"] = parser.title.strip()
    state["elements"] = [
        {
            "tag": record["tag"],
            "id": record["attrs"].get("id"),
            "line": record["line"],
            "thread": None,
        }
        for record in parser.lf_elements
    ]
    state["state"] = [
        standing_entry(coordinate, event)
        for coordinate, (event, _) in projection.actions.items()
    ]
    state["asks"] = document.asks["user"]
    state["measurement_lag"] = measurement_lag_entries(
        parser.lf_elements, registry, stored_data
    )


def _apply_thread_state(state: dict, thread: FrozenThreadReading) -> None:
    # The panel's own document, listed and projected the way the version's is, and
    # for the same reason: a widget an agent sent is a widget, and the user
    # answering one is answering the page. The projection above is of the published
    # version's elements alone, so a press on an AskUserQuestion resolved no
    # declaration and stood nowhere — a session picking the page up read the user's
    # answer to its own question as an answer nobody had given, with `asks` reporting
    # the same question answered.
    #
    # `thread` is the one key that separates them, present on every entry so a
    # reader of this can take the two halves the same way, and the elements come along
    # so nothing here names a widget the same object never lists. Both lists are then
    # in one order rather than two sorted halves.
    thread_actions = thread.projection
    thread_byid = thread.by_id
    thread_of = thread.thread_by_widget
    state["elements"] += [
        {
            "tag": record["tag"],
            "id": widget,
            "line": record["line"],
            "thread": thread_of[widget],
        }
        for widget, record in thread_byid.items()
    ]
    state["elements"].sort(
        key=lambda element: (element["thread"] or "", element["line"])
    )
    state["state"] += [
        standing_entry(coordinate, event, thread_of[coordinate[0]])
        for coordinate, (event, _) in thread_actions.actions.items()
    ]
    state["state"].sort(
        key=lambda reading: (reading["widget"], reading["unit"], reading["action"])
    )


def _widget_state(state: dict, page_dir: Path, widget: str, enclosing: dict) -> dict:
    """The page reading narrowed to one widget on the page and what it holds: its
    element, the moves and reports standing on it or on anything inside it, the Asks
    and workflows there, the updates aimed at them, and the tasks open on them. An
    Ask names the choice that answers it, so narrowing to the Ask carries the pick
    standing on that choice."""

    def inside(element: str | None) -> bool:
        return element is not None and widget in enclosing.get(element, ())

    workflows = [
        item
        for item in state["workflows"]
        if item["subject"]["kind"] == "widget" and inside(item["subject"]["id"])
    ]
    obligations = set(state["activity"]["obligations"])
    return {
        "page": str(page_dir),
        "widget": next(
            element
            for element in state["elements"]
            if element["id"] == widget and element["thread"] is None
        ),
        "state": [
            reading
            for reading in state["state"]
            if reading["thread"] is None
            and (inside(reading["widget"]) or inside(reading["unit"]))
        ],
        "asks": [
            ask
            for ask in state["asks"]
            if ask["thread"] is None and (inside(ask["id"]) or inside(ask["source"]))
        ],
        "updates": [
            update
            for update in state["updates"]
            if update["target"]["kind"] == "widget" and inside(update["target"]["id"])
        ],
        "activity": {
            "obligations": [
                item["id"] for item in workflows if item["id"] in obligations
            ],
        },
        "workflows": workflows,
        "tasks": [
            task
            for task in state["tasks"]
            if task["subject"]["kind"] == "widget" and inside(task["subject"]["id"])
        ],
    }


def queues(
    asks: list[dict], threads: list[dict], workflows: list[dict], tasks: list[dict]
) -> dict:
    """What is on the user and what is on the agent, as two lists of items.

    `on_you` holds each open Ask on the page or in a thread (`ask`); then each
    other thread whose attention is the user's, once however many moves it holds
    for them: for a question its agent turn leaves in prose (`question`), or for a
    move whose response failed, to send again (`recovery`); then each page widget
    move whose response failed (`recovery`). A thread holding an open Ask is that
    Ask's item alone. `on_agent` holds each move the agent owes an answer
    (`answer`), each move it has in hand that owes nothing (`work`), and each open
    task (`task`). Every item names its `subject` and the `thread` it
    stands in, or null on the page. Each is selected from a reading the served
    state already made: the Asks, each thread's `attention`, the workflows, and the
    open tasks.

    The browser selects the same two lists from its own reading of these four
    (`runtime/queues.js`), with the tab's unresolved sends already folded into the
    threads' attention and the workflows, and a thread message the tab is still
    sending counted on the agent; `served_records.py` holds a reading the two must
    agree on."""
    asked = {ask["thread"] for ask in asks}
    on_you = [
        {
            "kind": "ask",
            "id": ask["id"],
            "subject": {"kind": "widget", "id": ask["id"]},
            "thread": ask["thread"],
        }
        for ask in asks
    ]
    on_you += [
        {
            "kind": "question"
            if thread["attention"]["reason"] == "ask"
            else "recovery",
            "id": thread["id"],
            "subject": {"kind": "thread", "id": thread["id"]},
            "thread": thread["id"],
        }
        for thread in threads
        if thread["attention"] is not None
        and thread["attention"]["kind"] == "needs_user"
        and thread["id"] not in asked
    ]
    on_agent = []
    for workflow in workflows:
        item = {
            "id": workflow["id"],
            "subject": workflow["subject"],
            "thread": workflow["thread"],
        }
        # A move handed back in a thread is that thread's item above.
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
    on_agent += [
        {
            "kind": "task",
            "id": task["id"],
            "subject": task["subject"],
            "thread": task["thread"],
            "title": task["title"],
            "running": task["running"],
            "agent": task["agent"],
            "session": task["session"],
        }
        for task in tasks
    ]
    return {"on_you": on_you, "on_agent": on_agent}


def _write_page_state(
    page_dir: Path,
    events: list,
    source_error: str | None = None,
    *,
    target: str | None = None,
    after: int = 0,
    limit: int | None = None,
) -> None:
    """Where the page stands, as one JSON object — the agent-facing projection
    beside the browser projection in /api/state. A session picking a page up needs
    the same reading; doing it in-head over `leaf page events` is how a standing
    decision gets missed. So this prints the active revision's elements, the projection of
    the user's standing state and the reports standing on the agent channel,
    authored measurements whose live source has run again
    (`measurement_lag_entries`), the open Asks on the page and in threads (the
    banner's own count), each comment thread's current state, attention, and the
    agent messages in it the user has not read, the agent's open tasks, the two
    queues they and the workflows add up to (`queues`), and presence beside what
    answers for it. It is a
    selection from the reading /api/state serves (`read_served_page`), computed on
    demand from the log, revision, registry, and source store — no derived reading is
    stored, and none is folded a second time here, so there is no second copy of the
    truth to reconcile.

    Every markup-derived reading is of the latest valid revision, because that
    is the page the live root shows and the user acts on. An invalid source save
    appears under `source.error` while that revision remains active. The document
    itself is not repeated here: `active.file` is its HTML, which an agent reads
    beside `state`."""
    registry = require_registry(page_dir)
    served, reading, stored_data = read_served_page(read_page(page_dir, events))
    active = served["active"]
    if active is not None:
        active["file"] = (
            revision_path(page_dir, active["revision"]).relative_to(page_dir).as_posix()
        )
    activity = served["activity"]
    # Select presence from the served reading instead of gathering mutable claim and
    # lease evidence a second time.
    presence_reading = {
        key: served[key]
        for key in (
            "status",
            "listening",
            "cursor",
            "pending",
            "agent",
            "session_alive",
            "claim_session",
            "claim_turn",
            "turn_closed",
            "viewed",
            "session_cwd",
        )
    }
    state = _base_state(
        page_dir,
        events,
        source_error,
        served["versions"],
        active,
        presence_reading,
        reading.threads if reading is not None else {},
        stored_data,
        registry,
    )
    state["activity"] = {
        **activity,
        "obligations": [item["id"] for item in activity["obligations"]],
    }
    # Every obligation is one of these workflows, so an agent reads it by id: its
    # stage, subject and `answer` — the operation that settles it — are canonical,
    # while `response` carries provisional response progress.
    state["workflows"] = served["workflows"]
    state["user_views"] = read_user_views(
        page_dir, active["revision"] if active is not None else None
    )
    # Before a first revision there is no document, so no thread, Ask, widget, or
    # claim subject either: every reading below keeps its empty default.
    if reading is not None:
        browser = served["browser"]
        _apply_document_state(
            state, reading.documents[active["revision"]], stored_data, registry
        )
        state["asks"] += browser["thread"]["asks"]["user"]
        state["updates"] = browser["views"][str(active["revision"])]["updates"]
        _apply_thread_state(state, reading.thread)
        served_threads = {
            thread["id"]: thread for thread in browser["thread"]["threads"]
        }
        # The user's side between their moves: which of your messages they have not
        # taken in yet, at their current content version.
        for thread in state["threads"]:
            thread["unread"] = [
                item["message"] for item in served_threads[thread["id"]]["unread"]
            ]
            thread["attention"] = served_threads[thread["id"]]["attention"]
        state["tasks"] = browser["tasks"]
        state["queues"] = queues(
            state["asks"],
            browser["thread"]["threads"],
            state["workflows"],
            state["tasks"],
        )
    subject = None
    if target is not None:
        subject = page_subject(page_dir, events, target)
        if subject is None:
            held = logged_id(events, target, current_responses(page_dir, events))
            raise SystemExit(
                f"{target!r} names no thread or widget on this page"
                + (f"; {held}" if held else "")
            )
    if subject is not None and subject["kind"] == "widget":
        if after is not None or limit is not None:
            raise SystemExit(
                f"{target!r} is a widget; --after and --limit page a thread"
            )
        state = _widget_state(
            state, page_dir, subject["id"], active_enclosing(page_dir)
        )
    elif subject is not None:
        thread_id = subject["id"]
        selected = next(
            (thread for thread in state["threads"] if thread["id"] == thread_id),
            None,
        )
        if selected is None:
            raise SystemExit(f"{target!r} names no thread or widget on this page")
        # A thread is listed only where the page has a document, so the readings
        # stand here.
        thread_reading = reading.thread
        selected["summaries"] = served_threads[thread_id]["summaries"]
        elements = [
            element for element in state["elements"] if element["thread"] == thread_id
        ]
        standing = [
            reading for reading in state["state"] if reading["thread"] == thread_id
        ]
        asks = [ask for ask in state["asks"] if ask["thread"] == thread_id]
        updates = [
            update
            for update in state["updates"]
            if thread_reading.subject_thread(update["target"]) == thread_id
        ]
        reactions = [
            reaction
            for reaction in state["reactions"]
            if reaction["thread"] == thread_id
        ]
        content = []
        content_source = {
            "kind": "thread",
            "thread": thread_id,
            "vocabulary": str(page_dir / "registry.json"),
        }
        after = after or 0
        limit = limit or HISTORY_LIMIT
        matching = [
            event
            for event in reading.threads[thread_id]["msgs"]
            if event["seq"] > after
        ]
        shown = matching[:limit]
        history = {
            "after": after,
            "limit": limit,
            "next_after": shown[-1]["seq"] if len(matching) > limit else None,
        }
        for event in shown:
            fragment = thread_reading.structure.fragments.get(event["id"])
            message = {
                "message": event["id"],
                "source": {
                    "kind": "message",
                    "event": event["id"],
                    "seq": event["seq"],
                },
                "edit": {
                    "kind": "thread",
                    "thread": thread_id,
                },
                "content": [],
            }
            for key in (
                "kind",
                "author",
                "agent",
                "session",
                "parent",
                "responds",
                "revision",
            ):
                if key in event:
                    message[key] = event[key]
            if "text" in event:
                message["text"] = event["text"]
            if "drawing" in event:
                message["drawing"] = event["drawing"]
            content.append(message)
            if fragment is None:
                continue
            passages = page_passages(
                fragment,
                registry,
                retirement_outcomes(thread_reading.projection.actions),
            )
            message["content"] = constructed_content(
                fragment,
                thread_reading.projection,
                thread_reading.spoken,
                registry,
                stored_data,
                page_dir,
                retired=set(passages.retired) | set(passages.gone),
                thread=thread_id,
            )
        workflows = [
            workflow
            for workflow in state["workflows"]
            if workflow["thread"] == thread_id
        ]
        obligations = set(state["activity"]["obligations"])
        state = {
            "page": str(page_dir),
            "thread": selected,
            "history": history,
            "content_source": content_source,
            "content": content,
            "elements": elements,
            "state": standing,
            "asks": asks,
            "reactions": reactions,
            "updates": updates,
            "activity": {
                "obligations": [
                    item["id"] for item in workflows if item["id"] in obligations
                ],
            },
            "workflows": workflows,
            "tasks": [task for task in state["tasks"] if task["thread"] == thread_id],
        }
    print(json.dumps(state, indent=2, ensure_ascii=False))
