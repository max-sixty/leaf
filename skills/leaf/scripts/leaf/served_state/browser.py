"""Assemble browser state from requested documents and the standing log."""

from typing import NamedTuple

from ..document_reading import DocumentReading, read_document
from ..events import UndoReading
from ..files import stamped_version
from ..gesture_words import GestureWords, RevisionReader
from ..history import history, wants_history
from ..passages import SourceReading
from ..projection import FrozenThreadReading, canonical_updates, page_reading
from .context import PageRead
from .document import browser_document, browser_undo_candidates
from .thread import browser_thread
from .work import WorkState, work_state


class BrowserReading(NamedTuple):
    """The semantic readings one browser state serializes.

    A Python reader of the same snapshot selects from these rather than folding the
    log again: the page's threads, the frozen thread document, and each projected
    view's document reading, keyed by revision.
    """

    threads: dict
    thread: FrozenThreadReading
    documents: dict[int, DocumentReading]


def _apply_thread_attention(
    threads: list[dict], asks: dict, workflows: list[dict], tasks: list[dict]
) -> None:
    """Attach the shared attention aggregate, with user Asks taking precedence.

    This is the browser's one reading of whose turn a thread is: `needs_user` for
    an open Ask or a question the agent's latest turn leaves (`user_prompt`), or a
    response the user must recover; `waiting` while a workflow holds the thread with
    the agent, which covers every input `events.unanswered_turns` holds, or while a
    task the agent opened on it stands; else None. `workflows` are
    `served_workflows`, so the first that qualifies is the one the thread waits on,
    and a workflow speaks before a task. `tasks` are the agent's open tasks, each
    stamped with its `thread`."""
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
        elif task := next(
            (task for task in tasks if task["thread"] == thread["id"]), None
        ):
            thread["attention"] = {
                "kind": "waiting",
                "reason": "task",
                "workflow": None,
                # The line of the start running on it, while that start holds.
                "task": {
                    "id": task["id"],
                    "title": task["title"],
                    "line": task["running"]["text"]
                    if task["running"] and task["running"]["condition"] is None
                    else None,
                },
            }
        else:
            thread["attention"] = None


def browser_state(
    readings: dict[int, SourceReading],
    events: list,
    active_revision: int,
    present: dict,
    active: dict,
    view_revisions: set[int],
    now: str,
    live_stream: dict | None = None,
    revisions: RevisionReader | None = None,
    *,
    work: WorkState | None = None,
) -> tuple[dict, BrowserReading]:
    """The browser's derived reading of one transaction-consistent page snapshot.

    Documents and the append-only log remain the authorities. Each of `readings`
    is one revision's document under the registry it is read in. This object is an
    ephemeral transport projection, keyed by the exact log sequence and revisions
    from which it was read. `revisions` reads a revision a gesture names that is
    not among `readings`; without it every such revision must be there.
    """
    through_seq = events[-1]["seq"] if events else 0

    work = work or work_state(
        events, readings[active_revision], active_revision, present, now, live_stream
    )
    durable = work.durable
    active_page = durable.page
    active_registry = active_page.registry
    withdrawn = durable.log.withdrawn
    threads = durable.threads
    undo_reading = UndoReading(
        events,
        threads=threads,
        withdrawn=withdrawn,
        absorbed=active_page.projection.absorbed,
    )
    thread, thread_reading = browser_thread(durable, work.live_reply)
    thread_projection = thread_reading.projection

    views = {}
    documents = {}
    for revision in sorted(view_revisions):
        page = (
            active_page
            if revision == active_revision
            else page_reading(readings[revision], events, revision, withdrawn=withdrawn)
        )
        reading = (
            durable.document
            if revision == active_revision
            else read_document(page, threads)
        )
        document = browser_document(reading, revision)
        documents[revision] = reading
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
            "updates": canonical_updates(projection),
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
    activity = {
        key: value
        for key, value in work.activity.items()
        if key not in {"workflows", "tasks"}
    }
    workflows = work.workflows
    tasks, ended_tasks = durable.page_tasks(work.activity["tasks"])
    _apply_thread_attention(
        thread["threads"],
        thread["asks"],
        workflows,
        [task for task in tasks if task["owner"] == "agent"],
    )
    if wants_history(readings[revision] for revision in view_revisions):
        words = GestureWords(events, active_registry, revisions or readings.__getitem__)
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
        "tasks": tasks,
        "ended_tasks": ended_tasks,
        "receipts": [event for event in events if event.get("attempt")],
        "version_notes": {
            str(event["version"]): event["text"]
            for event in events
            if event["kind"] == "note"
        },
    }
    return wire, BrowserReading(threads, thread_reading, documents)


def project_browser_state(
    context: PageRead,
    view_revision: int | None = None,
    *,
    include_active_view: bool = True,
) -> tuple[dict, BrowserReading] | None:
    """Project only the documents one browser reading can consume.

    A normal state needs the shown and active revisions. Comparison bases and
    historical gesture words use the same context at the requested log boundary.
    """
    active = context.active
    if active is None:
        return None
    active_revision = active["revision"]
    requested_revision = view_revision or active_revision
    if requested_revision not in context.revisions:
        raise ValueError(f"unknown view revision r{requested_revision}")
    wanted = {requested_revision, active_revision}
    return browser_state(
        {revision: context.revision(revision) for revision in sorted(wanted)},
        context.events,
        active_revision,
        context.presence,
        active,
        wanted if include_active_view else {requested_revision},
        context.now,
        context.live_stream,
        context.revision,
        work=context.work,
    )
