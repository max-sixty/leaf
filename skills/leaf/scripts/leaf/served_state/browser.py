"""Assemble browser state from requested documents and the standing log."""

from pathlib import Path
from typing import NamedTuple

from ..activity import canonical_activity, canonical_stream_reply
from ..document_reading import DocumentReading
from ..events import UndoReading, build_threads, taken_back
from ..files import list_revisions, stamped_version
from ..gesture_words import GestureWords, RevisionReader, revisions_on_disk
from ..history import history, wants_history
from ..projection import FrozenThreadReading, canonical_updates, page_reading
from ..revision_artifact import read_registry
from ..structure import SourceDocument, parse_revision
from ..workflows import canonical_workflows
from .document import browser_document, browser_undo_candidates
from .thread import browser_thread


class BrowserReading(NamedTuple):
    """The semantic readings one browser state serializes.

    A Python reader of the same snapshot selects from these rather than folding the
    log again: the page's threads, the frozen thread document, and each projected
    view's document reading, keyed by revision.
    """

    threads: dict
    thread: FrozenThreadReading
    documents: dict[int, DocumentReading]


# Delivery progress, furthest last. `answered` is only ever the retained failed
# response, so within its category it is the furthest a move has come.
_STAGE_RANK = {
    "sent": 0,
    "queued": 1,
    "picked_up": 2,
    "working": 3,
    "replying": 4,
    "answered": 5,
}


def _at_work(workflow: dict) -> bool:
    return workflow["stage"] in {"working", "replying"}


def _strength(workflow: dict) -> tuple:
    """How strongly a workflow speaks for any surface that shows one of several: a
    move handed back to the user first, then work under way, then an uncertain or
    stopped one, then plain delivery; within each the further stage, then the newer
    input."""
    if workflow["condition"] is not None:
        category = 2
    elif _at_work(workflow):
        category = 3
    elif workflow["stage"] == "answered":
        category = 0
    else:
        category = 1
    return (
        workflow["next_actor"] == "user",
        category,
        _STAGE_RANK[workflow["stage"]],
        workflow["seq"],
    )


def served_workflows(
    workflows: list[dict], thread_reading: FrozenThreadReading
) -> list[dict]:
    """The page's workflows as the browser and `page state` read them, strongest
    first, each stamped with the two thread facts only the frozen thread document
    knows.

    `thread` is the thread the workflow stands in: a thread input's own, a widget
    frozen into a message's thread, or null for a page widget. `holds_thread` is
    whether it keeps that thread the agent's turn: every one of the thread's own
    inputs and claims, and a widget move frozen into it while the move is owed or
    the agent is at work on it. A frozen move that owes nothing shows its receipt on
    its message and leaves the thread nobody's turn.

    The order is the one comparator: whatever shows one workflow of several, a
    thread's attention, its card's secondary status, a message's receipt, takes the
    first. A reader that selects keeps the order; the browser places its own
    unresolved sends against it."""
    for workflow in workflows:
        thread = thread_reading.subject_thread(workflow["subject"])
        workflow["thread"] = thread
        workflow["holds_thread"] = thread is not None and (
            workflow["subject"]["kind"] == "thread"
            or workflow["answer"] is not None
            or _at_work(workflow)
        )
    return sorted(workflows, key=_strength, reverse=True)


def _apply_thread_attention(
    threads: list[dict], asks: dict, workflows: list[dict]
) -> None:
    """Attach the shared attention aggregate, with user Asks taking precedence.

    This is the browser's one reading of whose turn a thread is: `needs_user` for
    an open Ask or a question the agent's latest turn leaves (`user_prompt`), or a
    response the user must recover; `waiting` while a workflow holds the thread with
    the agent, which covers every input `events.unanswered_turns` holds and any work
    claimed on the thread after it was answered; else None. `workflows` are
    `served_workflows`, so the first that qualifies is the one the thread waits on."""
    user_threads = {ask["thread"] for ask in asks["user"]}
    by_thread: dict[str, list[dict]] = {}
    for workflow in workflows:
        if workflow["thread"] is not None:
            by_thread.setdefault(workflow["thread"], []).append(workflow)
    for thread in threads:
        if thread["resolved"]:
            thread["attention"] = None
            continue
        if thread["id"] in user_threads or thread["user_prompt"]:
            thread["attention"] = {
                "kind": "needs_user",
                "reason": "ask",
                "workflow": None,
            }
            continue
        candidates = by_thread.get(thread["id"], [])
        if recovery := next(
            (workflow for workflow in candidates if workflow["next_actor"] == "user"),
            None,
        ):
            thread["attention"] = {
                "kind": "needs_user",
                "reason": "recovery",
                "workflow": recovery["id"],
            }
        elif waiting := next(
            (workflow for workflow in candidates if workflow["holds_thread"]), None
        ):
            thread["attention"] = {
                "kind": "waiting",
                "reason": "uncertain" if waiting["condition"] else "workflow",
                "workflow": waiting["id"],
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
    revisions: RevisionReader | None = None,
) -> tuple[dict, BrowserReading]:
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
        events, active_registry, threads, live_reply
    )
    thread_projection = thread_reading.projection

    views = {}
    readings = {}
    for revision in sorted(view_revisions):
        document = documents[revision]
        page = (
            active_page
            if revision == active_revision
            else page_reading(document, events, registry_for(revision), revision)
        )
        document, reading = browser_document(page, threads)
        readings[revision] = reading
        projection = reading.projection
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
                reading,
                thread_projection,
                undo_reading=undo_reading,
                stamp=stamped_version(events, revision),
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
    workflows = served_workflows(activity.pop("workflows"), thread_reading)
    _apply_thread_attention(thread["threads"], thread["asks"], workflows)
    served = [(revision, documents[revision]) for revision in view_revisions]
    if wants_history(served, registry_for):
        words = GestureWords(
            events,
            active_registry,
            revisions
            or (lambda revision: (documents[revision], registry_for(revision))),
        )
        page_history = {
            "history": history(
                events,
                threads,
                words,
                thread_reading.thread_by_name,
                thread_reading.thread_by_widget,
            )
        }
    else:
        page_history = {}
    wire = {
        "basis": {"through_seq": through_seq},
        **page_history,
        "views": views,
        "thread": thread,
        "activity": activity,
        "workflows": workflows,
        "receipts": [event for event in events if event.get("attempt")],
        "version_notes": {
            str(event["version"]): event["text"]
            for event in events
            if event["kind"] == "note"
        },
    }
    return wire, BrowserReading(threads, thread_reading, readings)


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
) -> tuple[dict, BrowserReading] | None:
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
        revisions_on_disk(page_dir),
    )
