"""Agent-facing projected page state."""

import json
from pathlib import Path

from .asks import thread_asks
from .construction import constructed_content
from .data import read_data
from .data_contracts import measurement_lag_entries, page_data_binding_inventory
from .document_reading import DocumentReading, read_document
from .events import bare_reaction, build_threads, is_reaction
from .files import (
    active_descriptor,
    revision_path,
    version_descriptors,
)
from .passages import enclosing_of, page_passages
from .projection import (
    FrozenThreadReading,
    canonical_updates,
    frozen_thread_reading,
    page_projection,
    retirement_outcomes,
)
from .registry.reactions import described
from .registry.storage import layer_metadata, require_registry
from .requests import request_lifecycles, request_lifecycles_for, request_phases
from .revisioning import activate_source
from .schema import DATA_FILE
from .served_state.page import full_state
from .server import running_server
from .service import PageTransaction, unacknowledged


def standing_entry(coordinate, e: dict, thread: str | None = None) -> dict:
    """One standing action, in the shape `page state` reports every one of them.

    `revision` is the exact document the action was taken on, which for a widget an agent
    sent is a fact about the gesture and none about the widget: thread markup is
    frozen in the log, so no page version bounds one of these.
    """
    widget, unit, facet = coordinate
    return {
        "widget": widget,
        "unit": unit,
        "facet": facet,
        "action": e["action"],
        "detail": e["detail"],
        "revision": e["revision"],
        "seq": e["seq"],
        "thread": thread,
    }


def cmd_page_state(page_dir: Path, *, thread_id: str | None = None) -> None:
    """Print the agent-side state from one transaction-consistent snapshot."""
    with PageTransaction(page_dir) as page:
        activation = activate_source(page_dir, page.events)
        _write_page_state(page_dir, page.events, activation.error, thread_id=thread_id)


def _active_revision(page_dir: Path, events: list) -> tuple[int | None, dict | None]:
    # Every markup-derived reading is of the latest valid revision, because that
    # is the page the live root shows and the user acts on.
    active = active_descriptor(page_dir, events)
    if active is None:
        return None, None
    revision = active["revision"]
    active["file"] = revision_path(page_dir, revision).relative_to(page_dir).as_posix()
    return revision, active


def _read_active_document(
    page_dir: Path, events: list, registry: dict, revision: int | None
) -> DocumentReading | None:
    if revision is None:
        return None
    html = revision_path(page_dir, revision).read_text(encoding="utf-8")
    prepared = page_projection(html, events, registry, revision)
    threads = build_threads(events, enclosing_of(prepared[2]))
    return read_document(html, events, registry, revision, threads, prepared=prepared)


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
    requests: list,
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
        # The watcher's number where `pending` is the reader's: everything a
        # wait would still print, workers' reports included.
        "unacked": len(unacknowledged(events, presence_reading["cursor"])),
        # The last physical log record folded into this transaction-consistent
        # snapshot. This is the continuation boundary for `events --after`, not
        # the watcher's acknowledgement cursor above.
        "event_seq": events[-1]["seq"] if events else 0,
        "server": running_server(page_dir),
        "elements": [],
        "content": [],
        "state": [],
        "updates": [],
        "requests": requests,
        "data": {"file": DATA_FILE, "revision": stored_data["revision"]},
        "data_bindings": page_data_binding_inventory(page_dir, registry, events),
        "measurement_lag": [],
        "asks": [],
        # Current semantic facts only. Exact raw history belongs to
        # `events --thread`; keeping its sequence list here would make this
        # default snapshot grow with every conversation turn. A reaction nobody
        # has replied to opened no conversation: it is paint on the page and
        # stands under `reactions` below.
        "threads": [
            {
                "id": root,
                "anchor": thread["anchor"],
                "resolved": thread["resolved"] and thread["resolved"]["author"],
            }
            for root, thread in threads.items()
            if not bare_reaction(thread)
        ],
        # Every reaction still standing — the agent-side reading of the marks
        # the page paints, each explained (`means`) off this page's vocabulary.
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
                    "thread": root,
                    "revision": message.get("revision"),
                    "seq": message["seq"],
                },
                registry,
            )
            for root, thread in threads.items()
            if not thread["resolved"]
            for message in thread["msgs"]
            if is_reaction(message)
        ],
    }


def _apply_document_state(
    state: dict,
    document: DocumentReading,
    events: list,
    revision: int,
    threads: dict,
    stored_data: dict,
    registry: dict,
) -> None:
    parser = document.parser
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
    state["asks"] = document.asks["reader"]
    page_dir = Path(state["page"])
    state["content_source"] = {
        "file": str(page_dir / state["active"]["file"]),
        "revision": revision,
        "edit_file": str(page_dir / "index.html"),
        "matches_active": state["source"]["live"],
        "vocabulary": str(page_dir / "registry.json"),
    }
    state["content"] = constructed_content(
        parser,
        projection,
        document.spoken,
        registry,
        stored_data,
        page_dir,
        editable=state["source"]["live"],
        retired=set(document.passages.retired) | set(document.passages.gone),
    )
    state["measurement_lag"] = measurement_lag_entries(
        parser.lf_elements, registry, stored_data
    )


def _apply_thread_state(state: dict, thread: FrozenThreadReading) -> None:
    # The panel's own document, listed and projected the way the version's is, and
    # for the same reason: a widget an agent sent is a widget, and the reader
    # answering one is answering the page. The projection above is of the published
    # version's elements alone, so a press on an AskUserQuestion resolved no
    # declaration and stood nowhere — a session picking the page up read the reader's
    # answer to its own question as an answer nobody had given, with `asks` reporting
    # the same question answered.
    #
    # `thread` is the one key that separates them, present on every entry so a reader
    # of this can take the two halves the same way, and the elements come along so
    # nothing here names a widget the same object never lists. Both lists are then in
    # one order rather than two sorted halves.
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
        key=lambda reading: (reading["widget"], reading["unit"], reading["facet"])
    )


def _write_page_state(
    page_dir: Path,
    events: list,
    source_error: str | None = None,
    *,
    thread_id: str | None = None,
) -> None:
    """Where the page stands, as one JSON object — the agent-facing projection
    beside the browser projection in /api/state. A session picking a page up needs
    the same reading; doing it in-head over `leaf events` is how a standing decision
    gets missed. So this prints the active revision's elements, the
    projection of the user's standing state and the reports standing on the agent
    channel, the effective construction and its mutation owners, authored
    measurements whose live source has run again (`measurement_lag_entries`), the
    open Asks on the page and in threads (the banner's own count), each comment
    thread's current state,
    and presence beside what answers for it. Computed on demand from the log,
    revision, registry, and source store — no derived reading is stored, so there
    is no second copy of the truth to reconcile.

    Every markup-derived reading is of the latest valid revision, because that
    is the page the live root shows and the user acts on. An invalid source save
    appears under `source.error` while that revision remains active."""
    registry = require_registry(page_dir)
    versions = version_descriptors(page_dir, events)
    revision, active = _active_revision(page_dir, events)
    served = full_state(page_dir, events)
    activity = served["activity"]
    claims = served["claims"]
    # Agent state and browser state are two views of one snapshot. Select the
    # presence portion from the already-projected server reading instead of
    # gathering mutable claim and lease evidence a second time.
    presence_reading = {
        key: served[key]
        for key in (
            "status",
            "listening",
            "cursor",
            "pending",
            "agent",
            "host",
            "session_alive",
            "claim_session",
            "claim_turn",
            "turn_closed",
            "viewed",
            "session_cwd",
        )
    }
    document = _read_active_document(page_dir, events, registry, revision)
    spoken = document.spoken if document is not None else {}
    threads = build_threads(events, enclosing_of(spoken))
    stored_data = read_data(page_dir)
    thread_reading = frozen_thread_reading(events, registry)
    requests = request_lifecycles(events)
    state = _base_state(
        page_dir,
        events,
        source_error,
        versions,
        active,
        presence_reading,
        threads,
        stored_data,
        registry,
        requests,
    )
    state["activity"] = activity
    if document is not None:
        _apply_document_state(
            state, document, events, revision, threads, stored_data, registry
        )
    thread_requests = request_lifecycles_for(
        events,
        thread_reading.elements,
        registry,
        {"kind": "thread"},
    )
    state["asks"] += thread_asks(
        events,
        registry,
        {root for root, thread in threads.items() if thread["resolved"]},
        request_phases=request_phases(thread_requests),
        reading=thread_reading,
    )
    state["updates"] = canonical_updates(
        document.projection if document is not None else None,
        claims,
        threads,
        events,
    )
    _apply_thread_state(state, thread_reading)
    if thread_id is not None:
        if thread_id not in threads:
            raise SystemExit(f"unknown thread {thread_id!r}")
        state["content"] = []
        state["selection"] = {"kind": "thread", "id": thread_id}
        state["content_source"] = {
            "kind": "conversation",
            "thread": thread_id,
            "vocabulary": str(page_dir / "registry.json"),
        }
    for event in threads[thread_id]["msgs"] if thread_id is not None else []:
        fragment = thread_reading.structure.fragments.get(event["id"])
        message = {
            "message": event["id"],
            "source": {"kind": "message", "event": event["id"], "seq": event["seq"]},
            "edit": {"kind": "conversation", "thread": thread_id},
            "content": [],
        }
        if "text" in event:
            message["text"] = event["text"]
        if "drawing" in event:
            message["drawing"] = event["drawing"]
        state["content"].append(message)
        if fragment is None:
            continue
        passages = page_passages(
            event["markup"],
            registry,
            retirement_outcomes(thread_reading.projection.actions, registry),
        )
        content = constructed_content(
            fragment,
            thread_reading.projection,
            thread_reading.spoken,
            registry,
            stored_data,
            page_dir,
            editable=False,
            retired=set(passages.retired) | set(passages.gone),
            thread=thread_id,
        )
        message["content"] = content
    print(json.dumps(state, indent=2, ensure_ascii=False))
