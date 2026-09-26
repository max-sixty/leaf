"""Assemble browser state from requested documents and the standing log."""

from pathlib import Path

from ..activity import canonical_activity, canonical_stream_reply
from ..events import UndoReading, build_threads, taken_back
from ..files import list_revisions
from ..gesture_words import GestureWords, RevisionReader, revisions_on_disk
from ..history import history, wants_history
from ..projection import canonical_updates, page_reading
from ..requests import request_outcomes
from ..revision_artifact import read_registry
from ..structure import SourceDocument, parse_revision
from ..workflows import canonical_workflows
from .document import browser_document, browser_undo_candidates
from .thread import browser_thread


def _apply_thread_attention(
    threads: list[dict],
    asks: dict,
    workflows: list[dict],
    thread_by_widget: dict[str, str],
) -> None:
    """Attach the shared attention aggregate, with user Asks taking precedence."""
    user_threads = {ask["thread"] for ask in asks["user"]}
    stage_rank = {
        "sent": 0,
        "queued": 1,
        "picked_up": 2,
        "working": 3,
        "replying": 4,
        "answered": 5,
    }

    def at_work(workflow: dict) -> bool:
        return workflow["stage"] in {"working", "replying"}

    def holds_thread(workflow: dict) -> bool:
        """Whether this workflow keeps its thread the agent's turn: every one of the
        thread's own inputs and claims, and a widget move frozen into it while the
        move is owed or the agent is at work on it. A frozen move that owes nothing
        shows its receipt on its message and leaves the thread nobody's turn."""
        return (
            workflow["subject"]["kind"] == "thread"
            or workflow["answer"] is not None
            or at_work(workflow)
        )

    def priority(workflow: dict) -> tuple:
        if workflow["condition"] is not None:
            category = 2
        elif at_work(workflow):
            category = 3
        elif workflow["stage"] == "answered":
            category = 0
        else:
            category = 1
        return category, stage_rank[workflow["stage"]], workflow["seq"]

    by_thread: dict[str, list[dict]] = {}
    for workflow in workflows:
        subject = workflow["subject"]
        thread_id = (
            subject["id"]
            if subject["kind"] == "thread"
            else thread_by_widget.get(subject["id"])
            if subject["kind"] == "widget"
            else None
        )
        if thread_id is not None:
            by_thread.setdefault(thread_id, []).append(workflow)
    for thread in threads:
        if thread["resolved"]:
            thread["attention"] = None
            continue
        if thread["root"]["id"] in user_threads or thread["awaits_user"]:
            thread["attention"] = {
                "kind": "needs_user",
                "reason": "ask",
                "workflow": None,
            }
            continue
        candidates = by_thread.get(thread["root"]["id"], [])
        if recovery := [
            workflow for workflow in candidates if workflow["next_actor"] == "user"
        ]:
            workflow = max(recovery, key=priority)
            thread["attention"] = {
                "kind": "needs_user",
                "reason": "recovery",
                "workflow": workflow["id"],
            }
        elif waiting := [workflow for workflow in candidates if holds_thread(workflow)]:
            workflow = max(waiting, key=priority)
            thread["attention"] = {
                "kind": "waiting",
                "reason": "uncertain" if workflow["condition"] else "workflow",
                "workflow": workflow["id"],
            }
        else:
            thread["attention"] = None


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
    registries: dict[int, dict] | None = None,
    data: dict | None = None,
    revisions: RevisionReader | None = None,
) -> dict:
    """The browser's derived reading of one transaction-consistent page snapshot.

    Documents and the append-only log remain the authorities. This object is an
    ephemeral transport projection, keyed by the exact log sequence and revisions
    from which it was read. `revisions` reads a revision a gesture names that is
    not among `documents`; without it every such revision must be there.
    """
    through_seq = events[-1]["seq"] if events else 0

    def registry_for(revision):
        return (registries or {}).get(revision, registry)

    active_document = documents[active_revision]
    active_registry = registry_for(active_revision)
    active_page = page_reading(
        active_document, events, active_registry, active_revision
    )
    active_within = active_page.within
    withdrawn = taken_back(events)
    threads = build_threads(events, active_within, withdrawn=withdrawn)
    undo_reading = UndoReading(
        events,
        threads=threads,
        withdrawn=withdrawn,
        absorbed=active_page.projection.absorbed,
    )
    live_reply = canonical_stream_reply(present, now, (live_stream or {}).get("reply"))
    thread, thread_reading = browser_thread(
        events, active_registry, threads, live_reply, data
    )
    thread_projection = thread_reading.projection

    views = {}
    for revision in sorted(view_revisions):
        document = documents[revision]
        page = (
            active_page
            if revision == active_revision
            else page_reading(document, events, registry_for(revision), revision)
        )
        document, projection = browser_document(page, threads, data or {"sources": {}})
        classified = {
            **projection.classified,
            **thread_projection.classified,
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
                thread_projection,
                undo_reading=undo_reading,
            ),
            "coverage": coverage,
            "published_at": published_at,
        }
    workflows = canonical_workflows(
        present["claims"],
        threads,
        thread_reading,
        page=active_page,
    )
    activity = canonical_activity(
        present,
        workflows,
        now,
        (live_stream or {}).get("activity"),
        live_reply,
        (live_stream or {}).get("reply_bindings"),
    )
    workflows = activity.pop("workflows")
    _apply_thread_attention(
        thread["threads"],
        thread["asks"],
        workflows,
        thread_reading.thread_by_widget,
    )
    served = [(revision, documents[revision]) for revision in view_revisions]
    if wants_history(served, registry_for):
        words = GestureWords(
            events,
            active_registry,
            revisions
            or (lambda revision: (documents[revision], registry_for(revision))),
        )
        page_history = {"history": history(events, threads, words)}
    else:
        page_history = {}
    return {
        "basis": {"through_seq": through_seq},
        **page_history,
        "views": views,
        "thread": thread,
        "activity": activity,
        "workflows": workflows,
        "request_outcomes": request_outcomes(events),
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
    registries_override: dict[int, dict] | None = None,
    include_active_view: bool = True,
    live_stream: dict | None = None,
    data: dict | None = None,
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
    documents = {
        revision: (
            documents_override[revision]
            if documents_override is not None
            else parse_revision(page_dir, revision)
        )
        for revision in sorted(wanted)
    }
    registries = registries_override
    if registries is None and registry_override is None:
        registries = {
            revision: read_registry(page_dir, revision) for revision in wanted
        }
    registry = (
        registry_override
        if registry_override is not None
        else registries[active_revision]
    )
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
        registries,
        data,
        revisions_on_disk(page_dir),
    )
