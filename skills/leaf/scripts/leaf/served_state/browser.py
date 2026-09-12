"""Assemble browser state from requested documents and the standing log."""

from pathlib import Path

from ..acknowledgments import canonical_acknowledgments
from ..activity import canonical_activity
from ..events import UndoReading, build_threads, taken_back
from ..files import list_revisions, revision_path
from ..projection import canonical_updates, page_reading
from ..registry.contract import RegistryError
from ..registry.storage import load_registry
from ..structure import SourceDocument
from .conversation import browser_conversation
from .document import browser_document, browser_undo_candidates


def browser_state(
    documents: dict[int, SourceDocument],
    events: list,
    registry: dict,
    active_revision: int,
    present: dict,
    active: dict,
    view_revisions: set[int],
    now: str,
    live_stream: dict | None = None,
) -> dict:
    """The browser's derived reading of one transaction-consistent page snapshot.

    Documents and the append-only log remain the authorities. This object is an
    ephemeral transport projection, keyed by the exact log sequence and revisions
    from which it was read.
    """
    through_seq = events[-1]["seq"] if events else 0
    active_document = documents[active_revision]
    active_page = page_reading(active_document, events, registry, active_revision)
    active_within = active_page.within
    withdrawn = taken_back(events)
    threads = build_threads(events, active_within, withdrawn=withdrawn)
    undo_reading = UndoReading(events, threads=threads, withdrawn=withdrawn)
    conversation, conversation_reading = browser_conversation(events, registry, threads)
    conversation_projection = conversation_reading.projection

    views = {}
    for revision in sorted(view_revisions):
        document = documents[revision]
        page = (
            active_page
            if revision == active_revision
            else page_reading(document, events, registry, revision)
        )
        document, projection = browser_document(page, threads)
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
            "updates": canonical_updates(
                projection, present["claims"], threads, events
            ),
            "undo": browser_undo_candidates(
                events,
                projection,
                conversation_projection,
                undo_reading=undo_reading,
            ),
            "coverage": coverage,
            "published_at": published_at,
        }
    interaction_evidence = canonical_acknowledgments(
        present["claims"],
        threads,
        conversation_reading,
        page=active_page,
    )
    return {
        "basis": {"through_seq": through_seq},
        "views": views,
        "conversation": conversation,
        "activity": canonical_activity(
            present,
            interaction_evidence,
            now,
            (live_stream or {}).get("activity"),
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
    present: dict,
    now: str,
    *,
    documents_override: dict[int, SourceDocument] | None = None,
    registry_override: dict | None = None,
    include_active_view: bool = True,
    live_stream: dict | None = None,
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
    revisions = (
        set(documents_override)
        if documents_override is not None
        else set(list_revisions(page_dir))
    )
    if requested_revision not in revisions:
        raise ValueError(f"unknown view revision r{requested_revision}")
    wanted = {requested_revision, active_revision}
    documents = {}
    for revision in sorted(wanted):
        if documents_override is not None:
            documents[revision] = documents_override[revision]
        else:
            documents[revision] = SourceDocument(
                revision_path(page_dir, revision).read_text(encoding="utf-8")
            )
    if registry_override is not None:
        registry = registry_override
    else:
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
        present,
        active,
        wanted if include_active_view else {requested_revision},
        now,
        live_stream,
    )
