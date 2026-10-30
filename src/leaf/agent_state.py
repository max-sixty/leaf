"""Agent-facing page state: the On me and On <agent> lists, and the obligations and to-dos
they select from.

The reading uses one transaction and holds the two lists the active view serves
(`served_state.queues`): On me (`on_user`) holds the open obligations on the user, the
updates handed back to them among them, then the to-dos on the user; On <agent>
(`on_agent`) holds the updates the agent owes an answer and its to-dos. The obligation
inventory (`obligations`) also retains finished records, whatever their `status`.
`activity.obligations` names each answer the agent owes: its update's record `id` and,
as `answer`, the operation that answers it with the reference its delivery gave, so an
agent recovers what it owes without the delivery. `source` states whether a document
is live and whether an invalid source save leaves the last valid version active. Its
`digest` identifies the current index.html and complete page/ tree, even when invalid,
for `page stamp --replace`. Before the first valid revision, an invalid candidate
registry leaves no active document or readable vocabulary; its
source error still remains readable. A page at a protocol this Leaf cannot
serve (`layer.incompatible_layer`) is still read, its `source.error` the refusal
naming `page init`: the reading gives the agent the page's context, and the error
says not to act on it before `page init`.
"""

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
from .publishing import authored_digest, authored_files
from .refusals import Refused
from .registry.storage import layer_metadata
from .revision_artifact import active_enclosing
from .revisioning import activate_source
from .schema import DATA_DIR
from .served_state.context import read_page
from .served_state.page import read_served_page
from .server import running_server
from .service import PageTransaction, unacknowledged
from .user_views import read_user_views, viewed_at
from .validation.admission import logged_id
from .work import page_subject

# How many of a thread's messages one `page state PAGE MESSAGE` prints by default.
HISTORY_LIMIT = 50


def state_entry(coordinate, e: dict, thread: str | None = None) -> dict:
    """One action in force, in the shape `page state` reports every one of them.

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
) -> dict:
    """The agent-side state from one transaction-consistent snapshot: the page's,
    or the part `target` names — a thread with a page of its history, or a
    widget. Paging with no thread named is refused before the page is read."""
    if target is None and (after is not None or limit is not None):
        raise Refused("--after and --limit page a thread; name one as ID")
    with PageTransaction(page_dir) as page:
        activation = activate_source(page_dir, transaction=page)
        return page_state(
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
    registry: dict | None,
) -> dict:
    return {
        "page": str(page_dir),
        "layer": layer_metadata(page_dir),
        "title": "",
        "active": active,
        "versions": versions,
        "source": {
            "file": "index.html",
            "digest": authored_digest(
                authored_files(page_dir / "index.html", page_dir / "page")
            ),
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
        "reports": [],
        "data": {
            "dir": DATA_DIR,
            "errors": data_errors(stored_data),
        },
        "data_bindings": (
            page_data_binding_inventory(page_dir, registry, events)
            if registry is not None
            else {}
        ),
        "measurement_lag": [],
        # What is on the user (On me) and what is on the agent (On <agent>), each item
        # naming its kind and subject (`served_state.queues`); the to-dos on either
        # side; the agent's plan, which arranges them (`plans`); and the complete
        # canonical obligation inventory those lists select from, whose records an obligation's
        # row names by `id`.
        "queues": {"on_user": [], "on_agent": []},
        "todos": [],
        "plan": None,
        "obligations": [],
        # Current semantic facts only. A thread's history belongs to
        # `page state PAGE MESSAGE`; keeping its sequence list here would make this
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
        # Every reaction still in force — the agent-side reading of the marks
        # the page paints. On the page (`anchor`, or none for the page whole) while
        # its thread is unresolved; in a thread (`parent`) while that thread is open.
        "reactions": [
            {
                "id": message["id"],
                "token": message["token"],
                "anchor": message.get("anchor"),
                "about": message.get("about"),
                "parent": message.get("parent"),
                "thread": thread_id,
                "revision": message.get("revision"),
                "seq": message["seq"],
            }
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
    state["title"] = parser.authoring.title.strip()
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
        state_entry(coordinate, event)
        for coordinate, (event, _) in projection.actions.items()
    ]
    state["measurement_lag"] = measurement_lag_entries(
        parser.lf_elements, registry, stored_data
    )


def _apply_thread_state(state: dict, thread: FrozenThreadReading) -> None:
    # The panel's own document, listed and projected the way the version's is, and
    # for the same reason: a widget an agent sent is a widget, and the user
    # answering one is answering the page. The projection above is of the published
    # version's elements alone, so a press on an AskUserQuestion resolved no
    # declaration and stood nowhere — a session picking the page up read the user's
    # answer to its own question as an answer nobody had given, while the question's
    # task read answered.
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
        state_entry(coordinate, event, thread_of[coordinate[0]])
        for coordinate, (event, _) in thread_actions.actions.items()
    ]
    state["state"].sort(
        key=lambda reading: (reading["widget"], reading["unit"], reading["action"])
    )


def _widget_state(state: dict, page_dir: Path, widget: str, enclosing: dict) -> dict:
    """The page reading narrowed to one widget on the page and what it holds: its
    element, the actions and reports in force on it or on anything inside it, the
    workflows there, the reports aimed at them, the to-dos open on them, and the
    obligations sourced by them."""

    def inside(element: str | None) -> bool:
        return element is not None and widget in enclosing.get(element, ())

    workflows = [
        item
        for item in state["workflows"]
        if item["subject"]["kind"] == "widget" and inside(item["subject"]["id"])
    ]
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
        "reports": [
            report
            for report in state["reports"]
            if report["target"]["kind"] == "widget" and inside(report["target"]["id"])
        ],
        "activity": {
            "obligations": [
                item
                for item in state["activity"]["obligations"]
                if item["id"] in {workflow["obligation"] for workflow in workflows}
            ],
        },
        "workflows": workflows,
        "obligations": [
            item
            for item in state["obligations"]
            if item["thread"] is None
            and (
                item["source"]["kind"] == "widget"
                and (inside(item["source"]["id"]) or inside(item["prompt"]["target"]))
                or item["source"]["kind"] in {"update", "todo"}
                and item["source"]["subject"]["kind"] == "widget"
                and inside(item["source"]["subject"]["id"])
            )
        ],
        "todos": [
            todo
            for todo in state["todos"]
            if todo["thread"] is None
            and (todo["subject"]["kind"] == "widget" and inside(todo["subject"]["id"]))
        ],
    }


def page_state(
    page_dir: Path,
    events: list,
    source_error: str | None = None,
    *,
    target: str | None = None,
    after: int | None = 0,
    limit: int | None = None,
) -> dict:
    """Where the page stands, as one JSON object — the agent-facing projection
    beside the browser projection in /api/state. A session picking a page up needs
    the same reading; doing it in-head over `leaf page events` is how a decision
    in force gets missed. So this holds the active revision's elements, the projection of
    the user's current state and the reports in force on the agent channel,
    authored measurements whose live source has run again
    (`measurement_lag_entries`), each comment thread's current state, attention, and
    the agent messages in it the user has not read, every open to-do on either side,
    the obligations, the two lists, On me and On <agent>, that they and the workflows add up
    to (`served_state.queues`, the panel's own counts), and presence beside what
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
    context = read_page(page_dir, events)
    registry = context.registry
    served, reading, stored_data = read_served_page(context)
    active = served["active"]
    if active is not None:
        active["file"] = (
            revision_path(page_dir, active["revision"]).relative_to(page_dir).as_posix()
        )
    activity = served["activity"]
    # Select presence from the served reading instead of gathering mutable claim and
    # lease evidence a second time. When a browser last showed the page is the agent's
    # alone; the browser never reads it.
    presence_reading = {
        **{
            key: served[key]
            for key in (
                "status",
                "listening",
                "cursor",
                "pending",
                "agent",
                "session_alive",
                "claim_session",
                "session_name",
                "session_cwd",
                "turn",
                "turn_closed",
            )
        },
        "viewed": viewed_at(page_dir),
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
        "obligations": [
            {"id": item["obligation"], "answer": item["answer"]}
            for item in context.work.activity["obligations"]
        ],
    }
    # Each answer owed names its update's record, in `obligations`; the workflows that
    # name the same record (`obligation`) carry its delivery stage and subject, and
    # `response` the provisional response progress.
    state["workflows"] = served["workflows"]
    state["user_views"] = read_user_views(
        page_dir, active["revision"] if active is not None else None
    )
    # Before a first revision there is no document, so no thread, obligation, widget, or
    # claim subject either: every reading below keeps its empty default.
    if reading is not None:
        assert active is not None and registry is not None
        browser = served["browser"]
        view = browser["views"][str(active["revision"])]
        _apply_document_state(
            state, reading.documents[active["revision"]], stored_data, registry
        )
        state["reports"] = view["reports"]
        _apply_thread_state(state, reading.thread)
        served_threads = {thread["id"]: thread for thread in view["thread"]["threads"]}
        # The user's side between their updates: which of your messages they have not
        # taken in yet, at their current content version.
        for thread in state["threads"]:
            thread["unread"] = [
                item["message"] for item in served_threads[thread["id"]]["unread"]
            ]
            thread["attention"] = served_threads[thread["id"]]["attention"]
        state["obligations"] = view["obligations"]
        state["todos"] = [todo for todo in browser["todos"] if todo["state"] == "open"]
        state["plan"] = browser["plan"]
        served_queues = view["queues"]
        state["queues"] = {
            side: served_queues[side] for side in ("on_user", "on_agent")
        }
    subject = None
    if target is not None:
        subject = page_subject(page_dir, events, target)
        if subject is None:
            held = logged_id(
                page_dir, events, target, current_responses(page_dir, events)
            )
            raise Refused(
                f"{target!r} names no thread or widget on this page"
                + (f"; {held}" if held else "")
            )
    if subject is not None and subject["kind"] == "widget":
        if after is not None or limit is not None:
            raise Refused(f"{target!r} is a widget; --after and --limit page a thread")
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
            raise Refused(f"{target!r} names no thread or widget on this page")
        # A thread is listed only where the page has a document, so the readings
        # stand here.
        assert reading is not None and registry is not None
        thread_reading = reading.thread
        selected["summaries"] = served_threads[thread_id]["summaries"]
        elements = [
            element for element in state["elements"] if element["thread"] == thread_id
        ]
        in_force = [
            reading for reading in state["state"] if reading["thread"] == thread_id
        ]
        reports = [
            report
            for report in state["reports"]
            if thread_reading.subject_thread(report["target"]) == thread_id
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
                "ephemeral",
                "revision",
                "edited",
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
        state = {
            "page": str(page_dir),
            "thread": selected,
            "history": history,
            "content_source": content_source,
            "content": content,
            "elements": elements,
            "state": in_force,
            "reactions": reactions,
            "reports": reports,
            "activity": {
                "obligations": [
                    item
                    for item in state["activity"]["obligations"]
                    if item["id"] in {workflow["obligation"] for workflow in workflows}
                ],
            },
            "workflows": workflows,
            "todos": [todo for todo in state["todos"] if todo["thread"] == thread_id],
            "obligations": [
                item for item in state["obligations"] if item["thread"] == thread_id
            ],
        }
    return state
