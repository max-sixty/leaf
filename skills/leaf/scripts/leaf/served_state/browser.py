"""Assemble browser state from requested documents and the standing log."""

from pathlib import Path

from ..acknowledgments import canonical_acknowledgments
from ..events import build_threads
from ..files import list_revisions, revision_path
from ..passages import enclosing_of
from ..projection import canonical_updates, page_projection
from ..registry.contract import RegistryError
from ..registry.storage import load_registry
from .conversation import _browser_conversation
from .document import _browser_document, _browser_undo_candidates


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
    conversation, conversation_reading = _browser_conversation(
        events, registry, threads
    )
    conversation_projection = conversation_reading.projection

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
        "acknowledgments": canonical_acknowledgments(
            events,
            claims,
            threads,
            active_projection,
            active_parser,
            active_spk,
            conversation_reading,
            registry,
            active_revision,
        ),
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
