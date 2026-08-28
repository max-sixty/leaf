"""Agent-facing projected page state."""

import json
from pathlib import Path
from typing import NamedTuple, Protocol

from .data import measurement_lag_entries, page_data_binding_inventory, read_data
from .events import (
    bare_reaction,
    build_threads,
    is_reaction,
    seats_with_agent,
    thread_digest,
)
from .files import (
    active_descriptor,
    latest_revision,
    revision_path,
    version_descriptors,
)
from .passages import enclosing_of, page_passages
from .projection import (
    StateProjection,
    canonical_updates,
    decisions,
    page_asks,
    page_projection,
    record_lag_entries,
    thread_asks,
)
from .registry import described, require_registry
from .revisioning import activate_source
from .served_state import presence
from .service import PageTransaction, running_server, unacknowledged
from .validation import thread_state


def standing_entry(coordinate, e: dict, thread: str | None = None) -> dict:
    """One standing action, in the shape `page state` reports every one of them.

    `revision` is the exact document the action was taken on, which for a widget an agent
    sent is a fact about the gesture and none about the widget: thread markup is
    frozen in the log, so no version bounds one of these and none can ever record
    it, which is why `lag` says nothing about them.
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


def cmd_page_state(page_dir: Path) -> None:
    """Print the agent-side state from one transaction-consistent snapshot."""
    with PageTransaction(page_dir) as page:
        activation = activate_source(page_dir, page.events)
        _write_page_state(page_dir, page.events, activation.error)


class _DocumentParser(Protocol):
    by_id: dict
    title: str
    lf_elements: list[dict]


class _DocumentReading(NamedTuple):
    html: str
    parser: _DocumentParser
    projection: StateProjection
    spoken: dict


def _active_revision(page_dir: Path, events: list) -> tuple[int | None, dict | None]:
    # Every markup-derived reading is of the latest valid revision, because that
    # is the page the live root shows and the user acts on.
    try:
        return latest_revision(page_dir), active_descriptor(page_dir, events)
    except SystemExit:
        return None, None


def _read_active_document(
    page_dir: Path, events: list, registry: dict, revision: int | None
) -> _DocumentReading | None:
    if revision is None:
        return None
    html = revision_path(page_dir, revision).read_text(encoding="utf-8")
    projection, parser, spoken = page_projection(html, events, registry, revision)
    return _DocumentReading(html, parser, projection, spoken)


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
        "title": "",
        "active": active,
        "versions": versions,
        "source_error": source_error,
        **presence_reading,
        # The watcher's number where `pending` is the reader's: everything a
        # wait would still print, workers' reports included.
        "unacked": len(unacknowledged(events, presence_reading["cursor"])),
        "server": running_server(page_dir),
        "elements": [],
        "state": [],
        "updates": [],
        "data": stored_data,
        "data_bindings": page_data_binding_inventory(page_dir, registry, events),
        "measurement_lag": [],
        "asks": [],
        # Whole, through the same digest a delivery carries: a session picking
        # the page up is in the position this reading exists for, and a count of
        # messages it cannot read tells it a conversation happened without
        # letting it answer one.
        # A reaction nobody has replied to opened no conversation: it is
        # paint on the page, and stands under `reactions` below.
        "threads": [
            thread_digest(thread)
            for thread in threads.values()
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
        "lag": [],
    }


def _apply_document_state(
    state: dict,
    document: _DocumentReading,
    threads: dict,
    stored_data: dict,
    registry: dict,
) -> None:
    parser = document.parser
    projection = document.projection
    byid = parser.by_id
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
    # An ask standing in a slot the log has retired — a group inside the lf-new
    # of a rejected suggestion — left the page with the slot, so it is nobody's
    # to answer; the passage reading already knows which ids a decision dropped.
    passages = page_passages(
        document.html, registry, decisions(projection.actions, registry)
    )
    state["asks"] = page_asks(
        parser,
        projection,
        byid,
        document.spoken,
        registry,
        set(passages.retired) | set(passages.gone),
        # A session picking the page up wants the reader's list, so a request
        # whose own seat conversation is with this agent is not on it: the next
        # word there is owed by the agent, and the stop hook says so.
        seats_with_agent(threads),
    )
    state["lag"] = record_lag_entries(projection, byid, document.spoken, registry)
    state["measurement_lag"] = measurement_lag_entries(
        parser.lf_elements, registry, stored_data
    )


def _apply_thread_state(state: dict, events: list, registry: dict) -> None:
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
    thread_actions, thread_byid, thread_of = thread_state(events, registry)
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
    page_dir: Path, events: list, source_error: str | None = None
) -> None:
    """Where the page stands, as one JSON object — the agent-side twin of the
    browser's /api/state, folded rather than raw. /api/state ships the log and
    lets the runtime replay it; a session picking a page up owes the same
    reading, and doing it in-head over `leaf events` is how a standing decision
    gets missed. So this prints the readings the runtime derives, from the same
    constructions it derives them with: the active revision's elements, the
    projection of the user's standing state and the reports standing on the agent
    channel, where the record lags either (`record_lag_entries`), authored
    measurements whose live source has run again (`measurement_lag_entries`), the
    open asks on the page and in threads (the banner's own count), each comment
    thread's exchange,
    and presence beside what answers for it. Computed on demand from the log,
    revision, registry, and source store — no derived reading is stored, so there
    is no second copy of the truth to reconcile.

    Every markup-derived reading is of the latest valid revision, because that
    is the page the live root shows and the user acts on. An invalid source save
    appears only as `source_error` while that revision remains active."""
    registry = require_registry(page_dir)
    versions = version_descriptors(page_dir, events)
    revision, active = _active_revision(page_dir, events)
    presence_reading = presence(page_dir, events)
    claims = presence_reading.pop("claims")
    document = _read_active_document(page_dir, events, registry, revision)
    spoken = document.spoken if document is not None else {}
    threads = build_threads(events, enclosing_of(spoken))
    stored_data = read_data(page_dir)
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
    )
    if document is not None:
        _apply_document_state(state, document, threads, stored_data, registry)
    state["asks"] += thread_asks(
        events,
        registry,
        {root for root, thread in threads.items() if thread["resolved"]},
    )
    state["updates"] = canonical_updates(
        document.projection if document is not None else None,
        claims,
        threads,
        events,
    )
    _apply_thread_state(state, events, registry)
    print(json.dumps(state, indent=2, ensure_ascii=False))
