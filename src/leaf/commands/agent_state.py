"""Agent-facing page state: the On Me and On <agent> lists, and the obligations they
select from.

The reading uses one transaction and holds the two lists the active view serves
(`served_state.queues`): On Me (`on_user`) holds the open obligations on the user, the
updates handed back to them among them; On <agent>
(`on_agent`) holds the updates the agent owes an answer and its to-dos. The obligation
inventory (`obligations`) holds every record, the agent's to-dos and finished ones
included, each saying where it stands (`standing`).
`activity.obligations` names each answer the agent owes: its update's record `id` and,
as `answer`, the operation that answers it with the reference its delivery gave, so an
agent recovers what it owes without the delivery. `source` states whether a document
is live and whether an invalid source save leaves the last valid version active. Its
`digest` identifies the current index.html and complete page/ tree, even when invalid,
for `page stamp --replace`. Before the first valid revision, an invalid candidate
registry leaves no active document or readable vocabulary; its
source error still remains readable. `page state` refuses a page at a protocol
this Leaf cannot serve and names its repair, since reading the page's layer record
refuses it (`registry.storage.layer_record`). Printing the reading anyway, with the
refusal as `source.error`, would give the agent the page's context, but computed from
a log this Leaf may misread.

`turn_end_facts` reads this state for each page a session holds and hands it to the
clerk, which selects from it what the turn-end check's fork is shown
(`clerk.page_facts`).
"""

from pathlib import Path

from leaf.agents.clerk import page_facts
from leaf.agents.delivery import current_responses
from leaf.base.files import revision_path
from leaf.base.refusals import Refused
from leaf.base.schema import DATA_DIR
from leaf.base.server import running_server
from leaf.log.construction import constructed_content
from leaf.log.projection import (
    AuthoredOrders,
    StateProjection,
    ThreadMarkupReading,
    folded_positions,
    retirement_outcomes,
)
from leaf.records.authored_checks.admission import logged_id
from leaf.records.document_reading import DocumentReading
from leaf.records.event_facts import EventFacts
from leaf.records.page_data import page_data_binding_inventory
from leaf.records.publishing import authored_digest, authored_files
from leaf.records.render_reading import drawn_visuals
from leaf.records.revisioning import activate_source
from leaf.records.transaction import PageTransaction, owned_pages, unacknowledged
from leaf.records.work import page_subject
from leaf.serving.served_state.context import read_page
from leaf.serving.served_state.page import read_served_page
from leaf.serving.user_views import read_user_views, viewed_at
from leaf.source.data import data_errors
from leaf.source.data_contracts import measurement_lag_entries
from leaf.source.file_bindings import bound_paths, granted_files
from leaf.source.passages import page_passages
from leaf.source.registry.contract import state_specs
from leaf.source.registry.storage import IncompatibleLayer, layer_metadata
from leaf.source.revision_artifact import active_enclosing, read_revision

# How many of a thread's messages one `page state PAGE MESSAGE` prints by default.
HISTORY_LIMIT = 50


def state_entry(coordinate, e: dict, facts: dict, thread: str | None = None) -> dict:
    """One action in force, in the shape `page state` reports every one of them,
    with the facts its delivery carried about it (`event_facts`).

    `revision` is the exact document the action was taken on, which for a widget an agent
    sent is a fact about the gesture and none about the widget: no page version
    bounds thread markup.
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
        **facts,
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


def turn_end_facts(session_id: str) -> list[dict]:
    """What the turn-end check's fork is shown of each page `session_id` holds
    (`clerk.page_facts`), each page read in one transaction. A page this Leaf can't
    read is left out: one whose files are gone, and one at another page protocol
    (`registry.storage.layer_record`), where this Leaf could write nothing the fork
    finds."""
    facts = []
    for page_dir in owned_pages(session_id):
        try:
            with PageTransaction(page_dir) as page:
                state = page_state(page_dir, page.events)
                facts.append(page_facts(page_dir, state, page.events))
        except (FileNotFoundError, IncompatibleLayer):
            continue
    return facts


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
        # The files the page's editors edit, each by its binding (`granted_files`).
        "files": granted_files(page_dir),
        # What is on the user (On Me) and what is on the agent (On <agent>), each item
        # naming its kind and subject (`served_state.queues`); the agent's plan, which
        # arranges them (`plans`); and the complete canonical obligation inventory
        # those lists select from, whose records a row names by `id`.
        "queues": {"on_user": [], "on_agent": []},
        "plan": None,
        "obligations": [],
        # Current semantic facts only. A thread's history belongs to
        # `page state PAGE MESSAGE`; keeping its sequence list here would make this
        # default snapshot grow with every thread turn.
        "threads": [
            {
                "id": thread_id,
                "title": thread["title"],
                "anchor": thread["anchor"],
                "detached_from": thread["detached_from"],
                # The passage a version rewrote, which left the thread on its section:
                # the words the thread is about once the page no longer shows them.
                "rewritten_from": thread["rewritten_from"],
                "resolved": thread["resolved"] and thread["resolved"]["author"],
            }
            for thread_id, thread in threads.items()
        ],
    }


def _orders(
    record: dict, orders: AuthoredOrders, projection: StateProjection, registry: dict
) -> dict | None:
    """Each position verb the element `record` owns → container id → its units in
    the order the page draws them (`folded_positions`), or None for an element that
    records no positions. A version that changes a container writes each moved unit
    where this order puts it (`package-data.md`, "User state")."""
    owner = record["attrs"].get("id")
    specs = [
        (verb, spec["record"])
        for verb, spec in state_specs(registry.get(record["tag"], {}))
        if (spec.get("record") or {}).get("kind") == "position"
    ]
    if owner is None or not specs:
        return None
    return {
        verb: folded_positions(owner, verb, position, orders, projection)
        for verb, position in specs
    }


def _element(
    record: dict,
    thread: str | None,
    order: dict | None,
    identity=None,
    parts: list[dict] | None = None,
) -> dict:
    element = {
        "tag": record["tag"],
        "id": identity or record["attrs"].get("id"),
        "line": record["line"],
        "thread": thread,
    }
    if order is not None:
        element["order"] = order
    if parts is not None:
        element["parts"] = parts
    return element


def _apply_document_state(
    state: dict,
    document: DocumentReading,
    stored_data: dict,
    registry: dict,
    facts: EventFacts,
    drawn: dict[str, dict],
) -> None:
    """The version's elements, each visual among them with the `parts` it drew where
    the page's render reading read this version with the data the page holds now
    (`render_reading.drawn_visuals`), and the state in force on them."""
    parser = document.document
    projection = document.projection
    state["title"] = parser.authoring.title.strip()
    orders = AuthoredOrders(parser.by_id, registry)
    state["elements"] = [
        _element(
            record,
            None,
            _orders(record, orders, projection, registry),
            parts=visual["parts"]
            if (visual := drawn.get(record["attrs"].get("id", "")))
            else None,
        )
        for record in parser.lf_elements
    ]
    in_force = projection.actions.items()
    read = facts([event for _, (event, _) in in_force])
    state["state"] = [
        state_entry(coordinate, event, read[event["id"]])
        for coordinate, (event, _) in in_force
    ]
    state["measurement_lag"] = measurement_lag_entries(
        parser.lf_elements, registry, stored_data
    )


def _apply_thread_state(
    state: dict, thread: ThreadMarkupReading, registry: dict, facts: EventFacts
) -> None:
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
    orders = AuthoredOrders(thread_byid, registry)
    state["elements"] += [
        _element(
            record,
            thread_of[widget],
            _orders(record, orders, thread_actions, registry),
            widget,
        )
        for widget, record in thread_byid.items()
    ]
    state["elements"].sort(
        key=lambda element: (element["thread"] or "", element["line"])
    )
    in_force = thread_actions.actions.items()
    read = facts([event for _, (event, _) in in_force])
    state["state"] += [
        state_entry(coordinate, event, read[event["id"]], thread_of[coordinate[0]])
        for coordinate, (event, _) in in_force
    ]
    state["state"].sort(
        key=lambda reading: (reading["widget"], reading["unit"], reading["action"])
    )


def _widget_state(state: dict, page_dir: Path, widget: str, enclosing: dict) -> dict:
    """The page reading narrowed to one widget on the page and what it holds: its
    element, the actions and reports in force on it or on anything inside it, the
    workflows there, the reports aimed at them, and the obligations sourced by them,
    the to-dos opened on them included."""

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
                (item["source"]["kind"] == "widget" and inside(item["source"]["id"]))
                or (
                    item["source"]["kind"] in {"update", "todo"}
                    and item["source"]["subject"]["kind"] == "widget"
                    and inside(item["source"]["subject"]["id"])
                )
            )
        ],
    }


def page_state(
    page_dir: Path,
    events: list,
    source_error: str | None = None,
    *,
    target: str | None = None,
    after: int | None = None,
    limit: int | None = None,
) -> dict:
    """Where the page stands, as one JSON object — the agent-facing projection
    beside the browser projection in /api/state. A session picking a page up needs
    the same reading; doing it in-head over `leaf page events` is how a decision
    in force gets missed. So this holds the active revision's elements, each visual
    with the parts it drew where the page's render reading read that revision with
    the page's current data (`render_reading.drawn_visuals`), the projection of the
    user's current state and the reports in force on the agent channel, authored
    measurements whose live
    source has run again
    (`measurement_lag_entries`), each comment thread's current state, attention, and
    the agent messages in it the user has not read, the obligations, the agent's
    to-dos among them, the two lists, On Me and On <agent>, that they and the workflows
    add up to (`served_state.queues`, the panel's own counts), and presence beside what
    answers for it. It is a
    selection from the reading /api/state serves (`read_served_page`), with the parts,
    computed on demand from the log, revision, registry, source store and render
    reading — no derived reading is stored, and none is folded a second time here, so there is no second copy of the
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
    folded = context.work.activity
    state["activity"] = {
        **activity,
        "obligations": [
            {"id": item["obligation"], "answer": item["answer"]}
            for item in folded["obligations"]
        ],
    }
    # Each answer owed names its update's record, in `obligations`; the workflows that
    # name the same record (`obligation`) carry each input's delivery and subject, and
    # `response` the provisional response progress.
    state["workflows"] = served["workflows"]
    state["user_views"] = read_user_views(
        page_dir, active["revision"] if active is not None else None
    )
    # The newest revision a tab showed the user, recorded as they left it
    # (`read_state.seen_revision`).
    seen = served["seen"]
    state["seen"] = (
        {"revision": seen["revision"], "label": seen["label"]} if seen else None
    )
    # Before a first revision there is no document, so no thread, obligation, widget, or
    # claim subject either: every reading below keeps its empty default.
    if reading is not None:
        assert active is not None and registry is not None
        browser = served["browser"]
        view = browser["views"][str(active["revision"])]
        facts = EventFacts(page_dir, events, registry, browser["thread_memberships"])
        _apply_document_state(
            state,
            reading.documents[active["revision"]],
            stored_data,
            registry,
            facts,
            drawn_visuals(
                page_dir,
                read_revision(page_dir, active["revision"]).digest,
                stored_data["version"],
            ),
        )
        state["reports"] = view["reports"]
        _apply_thread_state(state, reading.thread, registry, facts)
        served_threads = {thread["id"]: thread for thread in view["thread"]["threads"]}
        # The user's side between their updates: which of your messages they have not
        # taken in yet, at their current content version.
        for thread in state["threads"]:
            thread["unread"] = list(served_threads[thread["id"]]["unread"])
            thread["attention"] = served_threads[thread["id"]]["attention"]
        state["obligations"] = view["obligations"]
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
        # Read once for every message shown, whose passages and construction use it.
        outcomes = retirement_outcomes(thread_reading.projection.actions)
        # Each message as it now reads, with the facts its delivery carried.
        message_facts = facts(shown)
        granted = bound_paths(page_dir)
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
                "ts",
                "author",
                "agent",
                "session",
                "parent",
                "responds",
                "ephemeral",
                "revision",
                "edited",
                "withdrawn",
                "suggestion",
                "viewing",
            ):
                if key in event:
                    message[key] = event[key]
            for key in ("text", "emoji"):
                if key in event:
                    message[key] = event[key]
            if "drawing" in event:
                message["drawing"] = event["drawing"]
            message.update(message_facts[event["id"]])
            content.append(message)
            if fragment is None:
                continue
            passages = page_passages(fragment, registry, outcomes)
            message["content"] = constructed_content(
                fragment,
                thread_reading.projection,
                thread_reading.spoken,
                registry,
                stored_data,
                page_dir,
                files=granted,
                outcomes=outcomes,
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
            "reports": reports,
            "activity": {
                "obligations": [
                    item
                    for item in state["activity"]["obligations"]
                    if item["id"] in {workflow["obligation"] for workflow in workflows}
                ],
            },
            "workflows": workflows,
            "obligations": [
                item for item in state["obligations"] if item["thread"] == thread_id
            ],
        }
    return state
