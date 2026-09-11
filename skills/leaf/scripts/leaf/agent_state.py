"""Agent-facing projected page state."""

import json
from pathlib import Path

from .asks import thread_asks
from .construction import constructed_content
from .data import read_data
from .data_contracts import measurement_lag_entries, page_data_binding_inventory
from .delivery import current_responses
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
    page_reading,
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


def standing_entry(coordinate, e: dict, conversation: str | None = None) -> dict:
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
        "conversation": conversation,
    }


def cmd_page_state(page_dir: Path) -> None:
    """Print the agent-side state from one transaction-consistent snapshot."""
    with PageTransaction(page_dir) as page:
        activation = activate_source(page_dir, page.events)
        _write_page_state(page_dir, page.events, activation.error)


def _conversation_target(target: dict) -> dict:
    """Expose one protocol target without rewriting user-owned detail data."""
    return {
        **target,
        "kind": "conversation" if target["kind"] == "thread" else target["kind"],
    }


def _conversation_interaction(item: dict) -> dict:
    translated = {**item, "target": _conversation_target(item["target"])}
    coordinate = translated.get("coordinate")
    if coordinate and coordinate[0] == "thread":
        translated["coordinate"] = ["conversation", *coordinate[1:]]
    return translated


def _conversation_activity(activity: dict, responses: dict[str, dict]) -> dict:
    """Translate only Leaf-owned protocol fields in the shared browser reading."""
    interactions = [
        _conversation_interaction(item) for item in activity["interactions"]
    ]
    standing = {item["id"] for item in activity["obligations"]}
    obligations = [item for item in interactions if item["id"] in standing]
    for item in obligations:
        if response := responses.get(item.get("event")):
            item["response"] = response
    return {
        **activity,
        "interactions": interactions,
        "obligations": obligations,
    }


def _conversation_update(update: dict) -> dict:
    return {**update, "target": _conversation_target(update["target"])}


def cmd_conversation_read(
    page_dir: Path,
    conversation_id: str,
    *,
    after: int = 0,
    limit: int = 50,
) -> None:
    """Print one exact current conversation and one bounded history page."""
    with PageTransaction(page_dir) as page:
        activation = activate_source(page_dir, page.events)
        _write_page_state(
            page_dir,
            page.events,
            activation.error,
            conversation_id=conversation_id,
            after=after,
            limit=limit,
        )


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
    page = page_reading(html, events, registry, revision)
    threads = build_threads(events, page.within)
    return read_document(page, threads)


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
        # `events --conversation`; keeping its sequence list here would make this
        # default snapshot grow with every conversation turn. A reaction nobody
        # has replied to opened no conversation: it is paint on the page and
        # stands under `reactions` below.
        "conversations": [
            {
                "id": root,
                "anchor": thread["anchor"],
                "resolved": thread["resolved"] and thread["resolved"]["author"],
            }
            for root, thread in threads.items()
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
                    "conversation": root,
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
            "conversation": None,
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
            "conversation": thread_of[widget],
        }
        for widget, record in thread_byid.items()
    ]
    state["elements"].sort(
        key=lambda element: (element["conversation"] or "", element["line"])
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
    conversation_id: str | None = None,
    after: int = 0,
    limit: int = 50,
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
    state["activity"] = _conversation_activity(
        activity, current_responses(page_dir, events)
    )
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
    state["asks"] = [
        {
            key if key != "thread" else "conversation": value
            for key, value in ask.items()
        }
        for ask in state["asks"]
    ]
    state["updates"] = [
        _conversation_update(update)
        for update in canonical_updates(
            document.projection if document is not None else None,
            claims,
            threads,
            events,
        )
    ]
    _apply_thread_state(state, thread_reading)
    if conversation_id is not None:
        selected = next(
            (
                conversation
                for conversation in state["conversations"]
                if conversation["id"] == conversation_id
            ),
            None,
        )
        if selected is None:
            raise SystemExit(f"unknown conversation {conversation_id!r}")
        elements = [
            element
            for element in state["elements"]
            if element["conversation"] == conversation_id
        ]
        standing = [
            reading
            for reading in state["state"]
            if reading["conversation"] == conversation_id
        ]
        asks = [ask for ask in state["asks"] if ask["conversation"] == conversation_id]
        updates = [
            update
            for update in state["updates"]
            if (
                update["target"] == {"kind": "conversation", "id": conversation_id}
                or (
                    update["target"]["kind"] == "widget"
                    and thread_reading.thread_by_widget.get(update["target"]["id"])
                    == conversation_id
                )
            )
        ]
        reactions = [
            reaction
            for reaction in state["reactions"]
            if reaction["conversation"] == conversation_id
        ]
        requests = [
            request
            for request in state["requests"]
            if thread_reading.thread_by_widget.get(request["seat"]["widget"])
            == conversation_id
        ]
        content = []
        content_source = {
            "kind": "conversation",
            "conversation": conversation_id,
            "vocabulary": str(page_dir / "registry.json"),
        }
        matching = [
            event for event in threads[conversation_id]["msgs"] if event["seq"] > after
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
                    "kind": "conversation",
                    "conversation": conversation_id,
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
                "initiates",
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
                event["markup"],
                registry,
                retirement_outcomes(thread_reading.projection.actions, registry),
            )
            message["content"] = constructed_content(
                fragment,
                thread_reading.projection,
                thread_reading.spoken,
                registry,
                stored_data,
                page_dir,
                editable=False,
                retired=set(passages.retired) | set(passages.gone),
                conversation=conversation_id,
            )
        widget_ids = {element["id"] for element in elements}

        def belongs(interaction: dict) -> bool:
            target = interaction["target"]
            return target == {"kind": "conversation", "id": conversation_id} or (
                target["kind"] == "widget" and target["id"] in widget_ids
            )

        interactions = [
            interaction
            for interaction in state["activity"]["interactions"]
            if belongs(interaction)
        ]
        obligations = {item["id"] for item in state["activity"]["obligations"]}
        state = {
            "page": str(page_dir),
            "conversation": selected,
            "history": history,
            "content_source": content_source,
            "content": content,
            "elements": elements,
            "state": standing,
            "asks": asks,
            "requests": requests,
            "reactions": reactions,
            "updates": updates,
            "activity": {
                "interactions": interactions,
                "obligations": [
                    item for item in interactions if item["id"] in obligations
                ],
            },
        }
    print(json.dumps(state, indent=2, ensure_ascii=False))
