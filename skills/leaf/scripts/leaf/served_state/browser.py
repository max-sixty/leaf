"""Assemble browser state from requested documents and the standing log."""

from typing import NamedTuple

from ..asks import approval_blocking, collection
from ..document_reading import DocumentReading
from ..events import UndoReading
from ..files import stamped_version
from ..gesture_words import GestureWords, RevisionReader
from ..history import history, wants_history
from ..passages import SourceReading
from ..projection import (
    FrozenThreadReading,
    canonical_reports,
    page_reading,
)
from ..schema import WIDGET_KINDS
from ..thread_context import thread_memberships
from ..work_reading import WorkReading
from .context import PageRead
from .document import browser_document, browser_undo_candidates
from .queues import queues
from .thread import browser_thread
from .work import WorkState, work_state


class BrowserReading(NamedTuple):
    """The semantic readings one browser state serializes.

    A Python reader of the same snapshot selects from these rather than folding the
    log again: the page's threads, the frozen thread document as the active revision
    reads it, and each projected view's document reading, keyed by revision.
    """

    threads: dict
    thread: FrozenThreadReading
    documents: dict[int, DocumentReading]


def _thread_attention(
    thread: dict, owed: bool, candidates: list[dict], todos: list[dict]
) -> dict | None:
    """Whose turn one thread is: `needs_user` while an ask in it is the user's
    (`owed`), or for an update the user must send again (`resend`); `waiting` while a
    workflow holds the thread with the agent, which covers every input
    `events.unanswered_turns` holds, or while a to-do the agent opened on it stands;
    else None, as for every resolved thread. `candidates` are the thread's
    `served_workflows`, strongest first, so the first that qualifies is the one the
    thread waits on, and a workflow speaks before a to-do. `todos` are the agent's
    open to-dos, each stamped with its `thread`."""
    if thread["resolved"]:
        return None
    if owed:
        return {"kind": "needs_user", "reason": "ask", "workflow": None}
    if resend := next(
        (workflow for workflow in candidates if workflow["next_actor"] == "user"),
        None,
    ):
        return {"kind": "needs_user", "reason": "resend", "workflow": resend["id"]}
    if waiting := next(
        (workflow for workflow in candidates if workflow["holds_thread"]), None
    ):
        return {
            "kind": "waiting",
            "reason": "uncertain" if waiting["condition"] else "workflow",
            "workflow": waiting["id"],
        }
    if todo := next((todo for todo in todos if todo["thread"] == thread["id"]), None):
        return {
            "kind": "waiting",
            "reason": "todo",
            "workflow": None,
            # The line of the start running on it, while one holds it.
            "todo": {
                "id": todo["id"],
                "title": todo["title"],
                "line": todo["running"]["text"] if todo["running"] else None,
            },
        }
    return None


def _apply_thread_attention(
    durable: WorkReading, workflows: list[dict], threads: list[dict], todos: list[dict]
):
    """Attach each served thread's `attention`, the browser's one reading of whose turn
    it is, and its `todos`, the agent's to-dos still open on it. `durable` combines the
    viewed page's vocabulary with each message's captured vocabulary, so pinning
    another page revision does not reclassify frozen asks. `workflows` are the
    page's, enriched with delivery liveness."""
    owed = {ask["thread"] for ask in durable.asks["user"]}
    by_thread: dict[str, list[dict]] = {}
    for workflow in workflows:
        if workflow["thread"] is not None:
            by_thread.setdefault(workflow["thread"], []).append(workflow)
    for thread in threads:
        thread["attention"] = _thread_attention(
            thread, thread["id"] in owed, by_thread.get(thread["id"], []), todos
        )
        # The agent's open to-dos on the thread, each with the line of the start
        # running on it: a reply that promised one says it is still open (a to-do a
        # reply opens takes the reply's id, `todos.py`), and a running one is work
        # the thread's working message reads whoever's turn the thread is.
        thread["todos"] = [
            {
                "id": todo["id"],
                "title": todo["title"],
                "line": todo["running"]["text"] if todo["running"] else None,
            }
            for todo in todos
            if todo["thread"] == thread["id"]
        ]


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
    revision_ids: set[int] | frozenset[int] | None = None,
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
        events,
        readings[active_revision],
        active_revision,
        present,
        now,
        live_stream,
        revisions=revision_ids if revision_ids is not None else readings,
        revision_reader=revisions or readings.__getitem__,
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
    workflows = work.workflows
    todos, ended_todos = durable.page_todos(work.activity["todos"])
    agent_todos = [todo for todo in todos if todo["owner"] == "agent"]

    views = {}
    documents = {}
    for revision in sorted(view_revisions):
        page = (
            active_page
            if revision == active_revision
            else page_reading(
                readings[revision],
                events,
                revision,
                withdrawn=withdrawn,
                revisions=revision_ids if revision_ids is not None else readings,
                revision_reader=revisions or readings.__getitem__,
            )
        )
        # Read the page under its vocabulary and each frozen message under the
        # vocabulary captured when that message was admitted.
        viewed = durable.viewing(page)
        reading = viewed.document
        thread, thread_reading = browser_thread(viewed, work.live_reply)
        _apply_thread_attention(viewed, workflows, thread["threads"], agent_todos)
        stamp = stamped_version(events, revision)
        documents[revision] = reading
        projection = reading.projection
        classified = {
            **projection.classified,
            **thread_reading.projection.classified,
        }
        coverage = []
        for event in events:
            if event["kind"] in WIDGET_KINDS:
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
        document = browser_document(reading, revision)
        # The view's asks are its own document's beside its frozen thread's, so it
        # carries the lists they add up to and the asks approving it waits on.
        asks = document["asks"]["all"] + thread["asks"]["all"]
        views[str(revision)] = {
            "basis": {"revision": revision, "through_seq": through_seq},
            "document": document,
            "thread": thread,
            "reports": canonical_reports(projection),
            "undo": browser_undo_candidates(
                events,
                reading,
                thread_reading.projection,
                undo_reading=undo_reading,
                stamp=stamp,
            ),
            "coverage": coverage,
            "published_at": published_at,
            "queues": queues(
                thread["threads"], workflows, todos, ended_todos, collection(asks)
            ),
            "approval_blocking": [ask["id"] for ask in approval_blocking(asks)],
        }
    activity = {
        key: value
        for key, value in work.activity.items()
        if key not in {"workflows", "todos"}
    }
    if wants_history(readings[revision] for revision in view_revisions):
        words = GestureWords(
            events,
            active_registry,
            revisions or readings.__getitem__,
            available_revisions=(
                revision_ids if revision_ids is not None else readings.keys()
            ),
        )
        page_history = {
            "history": history(
                events,
                threads,
                words,
                durable.thread.thread_by_name,
                durable.thread.thread_by_widget,
            )
        }
    else:
        page_history = {}
    wire = {
        "basis": {"through_seq": through_seq},
        **page_history,
        "views": views,
        # Standing approvals across every stamp, for Threads' event timeline.
        # Current-version approval state lives only in its ask.
        "approval_history": durable.approvals,
        "activity": activity,
        "workflows": workflows,
        "todos": todos,
        "ended_todos": ended_todos,
        "receipts": [event for event in events if event.get("attempt")],
        # Every thread whose history each logged event changes
        # (`thread_context.thread_memberships`), which the browser reads for the
        # gesture an unsent undo takes back or an unsent action replaces.
        "thread_memberships": {
            identity: threads
            for identity, threads in thread_memberships(
                events,
                durable.thread.thread_by_name,
                durable.thread.thread_by_widget,
                active_page.within,
            ).items()
            if threads
        },
        "version_notes": {
            str(event["version"]): event["text"]
            for event in events
            if event["kind"] == "note"
        },
    }
    return wire, BrowserReading(threads, durable.thread, documents)


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
        revision_ids=context.revisions,
    )
