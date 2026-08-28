"""Browser projections from page documents and the standing event log."""

from pathlib import Path

from ..asks import page_ask_projection, thread_ask_projection
from ..events import (
    action_rests_on,
    action_retracted,
    awaits_agent,
    bare_reaction,
    build_threads,
    is_reaction,
    retractions,
    seat_root,
    seats_with_agent,
    spoken_turns,
    taken_back,
    undo_error,
)
from ..files import list_revisions, revision_path
from ..passages import enclosing_of, page_passages, spoken
from ..projection import (
    StateProjection,
    canonical_updates,
    decisions,
    folded_facet,
    page_projection,
    state_projection,
)
from ..registry.contract import RegistryError
from ..registry.storage import load_registry
from ..thread_context import thread_roots, thread_structure


def _browser_projection(
    projection: StateProjection,
    *,
    scope: str,
    within: dict,
    floors: dict,
) -> dict:
    """Serialize one declared projection without making the wire its authority."""
    entries = []
    for coordinate, (event, spec) in projection.classified.values():
        restated = []
        if event["kind"] == "action":
            restated = [
                identity
                for identity in action_rests_on(event, within)
                if floors.get(identity, 0) > event["revision"]
            ]
        entries.append(
            {
                "event": event,
                "coordinate": list(coordinate),
                "value": folded_facet(event, spec) if spec.get("record") else None,
                "scope": scope,
                "restated": restated,
            }
        )
    return {
        "entries": entries,
        "actions": [event["id"] for event, _spec in projection.actions.values()],
        "reports": [
            event["id"]
            for standing in projection.reports.values()
            for event, _spec in standing
        ],
        "desired": [event["id"] for event, _spec in projection.desired.values()],
    }


def _thread_projection(events: list, registry: dict):
    structure = thread_structure(events)
    roots = thread_roots(events)
    byid, spk = {}, {}
    for event in events:
        if markup := event.get("markup"):
            fragment = structure.fragments[event["id"]]
            byid.update(fragment.by_id)
            spk.update(spoken(markup, registry))
    projection = state_projection(events, byid, spk, registry, None, floors={})
    return projection, byid, spk, roots, structure


def _thread_awaits_reader(
    thread: dict,
    registry: dict,
    awaiting: dict[str, bool],
    structure,
) -> bool:
    if thread["resolved"]:
        return False
    turns = spoken_turns(thread)
    if not turns or turns[-1]["author"] != "claude":
        return False
    last = turns[-1]
    if last["kind"] == "reply":
        fragment = structure.fragments.get(last["id"])
        asks = [
            rec["attrs"].get("id")
            for rec in (fragment.lf_elements if fragment else [])
            if (registry.get(rec["tag"]) or {}).get("x-awaits") is not None
        ]
        structural = (
            any(awaiting.get(identity, False) for identity in asks) if asks else None
        )
        if structural is False or (structural is None and not last.get("awaits")):
            return False
    tokens = registry.get("$reactions", {}).get("tokens", {})
    return not any(
        is_reaction(message)
        and message["author"] == "user"
        and message.get("parent") == last["id"]
        and (tokens.get(message["token"]) or {}).get("settles")
        for message in thread["msgs"]
    )


def _browser_conversation(
    events: list, registry: dict, threads: dict
) -> tuple[dict, StateProjection]:
    settled = {identity for identity, thread in threads.items() if thread["resolved"]}
    prepared = _thread_projection(events, registry)
    projection, _byid, _spk, _roots, structure = prepared
    asks, awaiting = thread_ask_projection(events, registry, settled, prepared=prepared)
    rendered_threads = [
        {
            **thread,
            "awaits_agent": awaits_agent(thread),
            "awaits_reader": _thread_awaits_reader(
                thread, registry, awaiting, structure
            ),
            "bare_reaction": bare_reaction(thread),
            "seat": seat_root(thread),
        }
        for thread in threads.values()
    ]
    return (
        {
            "projection": _browser_projection(
                projection, scope="conversation", within={}, floors={}
            ),
            "asks": {"reader": asks, "unanswered": asks, "awaiting": awaiting},
            "threads": rendered_threads,
            "done": [event for event in events if event["kind"] == "done"],
        },
        projection,
    )


def _browser_document(
    html: str,
    events: list,
    registry: dict,
    revision: int,
    threads: dict,
    *,
    prepared: tuple | None = None,
) -> tuple[dict, StateProjection, dict, dict]:
    projection, parser, spk = prepared or page_projection(
        html, events, registry, revision
    )
    passages = page_passages(html, registry, decisions(projection.actions, registry))
    dropped = set(passages.retired) | set(passages.gone)
    reader_asks, reader_awaiting = page_ask_projection(
        parser,
        projection,
        parser.by_id,
        spk,
        registry,
        dropped,
        seats_with_agent(threads),
    )
    unanswered_asks, unanswered_awaiting = page_ask_projection(
        parser,
        projection,
        parser.by_id,
        spk,
        registry,
        dropped,
        set(),
    )
    within = enclosing_of(spk)
    floors = retractions(events, revision)
    return (
        {
            "revision": revision,
            "projection": _browser_projection(
                projection,
                scope="document",
                within=within,
                floors=floors,
            ),
            "asks": {
                "reader": reader_asks,
                "unanswered": unanswered_asks,
                "awaiting": reader_awaiting,
                "unanswered_awaiting": unanswered_awaiting,
            },
        },
        projection,
        within,
        floors,
    )


def _restores_desired(
    event: dict,
    coordinate: tuple,
    projection: StateProjection,
    withdrawn: set,
    within: dict,
    floors: dict,
) -> bool:
    """Whether withdrawing one action exposes another durable value there."""
    desired = projection.desired.get(coordinate)
    if desired and desired[0]["id"] != event["id"]:
        return True
    if projection.reports.get(coordinate):
        return True
    return any(
        candidate_coordinate == coordinate
        and candidate["kind"] == "action"
        and candidate["id"] != event["id"]
        and candidate["id"] not in withdrawn
        and not action_retracted(candidate, floors, within)
        for candidate_coordinate, (candidate, _spec) in projection.classified.values()
    )


def _browser_undo_candidates(
    events: list,
    within: dict,
    document_within: dict,
    document_floors: dict,
    document_projection: StateProjection,
    conversation_projection: StateProjection,
) -> list[dict]:
    classified = {
        **document_projection.classified,
        **conversation_projection.classified,
    }
    candidates = []
    withdrawn = taken_back(events)
    for event in reversed(events):
        if (
            event.get("author") != "user"
            or event["kind"] == "undo"
            or event["id"] in withdrawn
        ):
            continue
        if undo_error({"undoes": event["id"]}, events, within):
            continue
        item = {"event": event}
        if event["kind"] == "action" and event["id"] in classified:
            coordinate, _entry = classified[event["id"]]
            item["coordinate"] = list(coordinate)
            if event["id"] in document_projection.classified:
                projection = document_projection
                action_within = document_within
                floors = document_floors
            else:
                projection = conversation_projection
                action_within = {}
                floors = {}
            item["restores_desired"] = _restores_desired(
                event,
                coordinate,
                projection,
                withdrawn,
                action_within,
                floors,
            )
        candidates.append(item)
    return candidates


def browser_state(
    documents: dict[int, str],
    events: list,
    registry: dict,
    active_revision: int,
    claims: list,
    active: dict,
    view_revisions: set[int],
) -> dict:
    """The browser's derived reading of one transaction-consistent page snapshot.

    Documents and the append-only log remain the authorities. This object is an
    ephemeral transport projection, keyed by the exact log sequence and revisions
    from which it was read.
    """
    through_seq = events[-1]["seq"] if events else 0
    active_html = documents[active_revision]
    active_projection, active_parser, active_spk = page_projection(
        active_html, events, registry, active_revision
    )
    active_within = enclosing_of(active_spk)
    threads = build_threads(events, active_within)
    conversation, conversation_projection = _browser_conversation(
        events, registry, threads
    )

    views = {}
    for revision in sorted(view_revisions):
        html = documents[revision]
        document, projection, within, floors = _browser_document(
            html,
            events,
            registry,
            revision,
            threads,
            prepared=(active_projection, active_parser, active_spk)
            if revision == active_revision
            else None,
        )
        classified = {
            **projection.classified,
            **conversation_projection.classified,
        }
        coverage = []
        for event in events:
            if event["kind"] in {"action", "report"}:
                classified_entry = classified.get(event["id"])
            elif event["kind"] == "undo":
                classified_entry = classified.get(event["undoes"])
            else:
                continue
            coverage.append(
                {
                    "event": event,
                    "coordinate": (
                        list(classified_entry[0]) if classified_entry else None
                    ),
                }
            )
        published_at = next(
            (
                event["ts"]
                for event in reversed(events)
                if event["kind"] == "note" and event["revision"] == revision
            ),
            active.get("activated_at") if active_revision == revision else None,
        )
        views[str(revision)] = {
            "basis": {"revision": revision, "through_seq": through_seq},
            "document": document,
            "updates": canonical_updates(projection, claims, threads, events),
            "undo": _browser_undo_candidates(
                events,
                active_within,
                within,
                floors,
                projection,
                conversation_projection,
            ),
            "coverage": coverage,
            "published_at": published_at,
        }
    return {
        "basis": {"through_seq": through_seq},
        "views": views,
        "conversation": conversation,
        "receipts": [event for event in events if event.get("attempt")],
        "version_notes": {
            str(event["version"]): event["text"]
            for event in events
            if event["kind"] == "note"
        },
    }


def project_browser_state(
    page_dir: Path,
    events: list,
    view_revision: int | None,
    active: dict | None,
    claims: list,
    source_overrides: dict[int, str] | None = None,
    *,
    include_active_view: bool = True,
) -> dict | None:
    """Project only the documents one browser reading can consume.

    A normal state needs the revision the tab is showing and the active revision it
    may activate next. Older comparison bases are projected on demand at the tab's
    exact log boundary, rather than making every state poll parse every immutable
    revision the page has ever had.
    """
    if active is None:
        return None
    active_revision = active["revision"]
    requested_revision = view_revision or active_revision
    revisions = set(list_revisions(page_dir)) | set(source_overrides or {})
    if requested_revision not in revisions:
        raise ValueError(f"unknown view revision r{requested_revision}")
    wanted = {requested_revision, active_revision}
    documents = {}
    for revision in sorted(wanted):
        if source_overrides and revision in source_overrides:
            documents[revision] = source_overrides[revision]
        else:
            documents[revision] = revision_path(page_dir, revision).read_text(
                encoding="utf-8"
            )
    try:
        registry = load_registry(page_dir)
    except RegistryError:
        return None
    if registry is None:
        return None
    return browser_state(
        documents,
        events,
        registry,
        active_revision,
        claims,
        active,
        wanted if include_active_view else {requested_revision},
    )
