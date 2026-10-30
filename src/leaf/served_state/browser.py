"""Assemble browser state from requested documents and the current log."""

from typing import NamedTuple

from ..document_reading import DocumentReading
from ..events import UndoReading
from ..gesture_words import GestureWords, RevisionReader
from ..history import history, wants_history
from ..passages import SourceReading
from ..projection import (
    FrozenThreadReading,
    canonical_reports,
    page_reading,
)
from ..registry.kernel import verb_writers
from ..thread_context import thread_memberships
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
    thread: dict, records: list[dict], candidates: list[dict], todos: list[dict]
) -> dict | None:
    """Whose turn one thread is, read from the open obligation records in it
    (`records`): `needs_user` while one is the user's, a request (`obligation`) ahead of an
    update handed back to them to send again (`resend`); else `waiting` while one is
    the agent's, or while a to-do the agent opened on it stands; else None, as for
    every resolved thread.

    `candidates` are the thread's `served_workflows`, strongest first, so the first
    serving the record that decides is the one the thread waits on, and names its
    stage. A widget's record turns the agent's only while the thread's newest
    unanswered turn publishes an update record (`queues`), so a waiting thread always
    has a workflow to name. `todos` are the agent's open to-dos, each stamped with its
    `thread`, and `todo` names the one the thread waits on by id."""
    if thread["resolved"]:
        return None

    def serving(kept) -> dict | None:
        held = {record["id"] for record in records if kept(record)}
        return next(
            (workflow for workflow in candidates if workflow["obligation"] in held),
            None,
        )

    if any(
        record["next_actor"] == "user" and record["source"]["kind"] != "update"
        for record in records
    ):
        return {"kind": "needs_user", "reason": "obligation", "workflow": None}
    if resend := serving(
        lambda record: (
            record["next_actor"] == "user" and record["source"]["kind"] == "update"
        )
    ):
        return {"kind": "needs_user", "reason": "resend", "workflow": resend["id"]}
    if waiting := serving(lambda record: record["next_actor"] == "agent"):
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
            "todo": todo["id"],
        }
    return None


def _apply_thread_attention(
    records: list[dict], workflows: list[dict], threads: list[dict], todos: list[dict]
):
    """Attach each served thread's `attention`, the browser's one reading of whose turn
    it is. `records` are the obligation records of the view these threads are served
    in, so a pinned revision's threads take the attention its own vocabulary reads;
    `workflows` are the page's, enriched with delivery liveness."""
    open_records: dict[str, list[dict]] = {}
    for record in records:
        if record["thread"] is not None and record["status"] == "open":
            open_records.setdefault(record["thread"], []).append(record)
    by_thread: dict[str, list[dict]] = {}
    for workflow in workflows:
        if workflow["thread"] is not None:
            by_thread.setdefault(workflow["thread"], []).append(workflow)
    for thread in threads:
        thread["attention"] = _thread_attention(
            thread,
            open_records.get(thread["id"], []),
            by_thread.get(thread["id"], []),
            todos,
        )


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
    assert active_page is not None
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
    todos = durable.page_todos(work.activity["todos"])
    agent_todos = [
        todo for todo in todos if todo["owner"] == "agent" and todo["state"] == "open"
    ]

    words = GestureWords(events, active_registry, revisions or readings.__getitem__)
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
        # The view's own reading of the log: its document, and the frozen thread
        # widgets with the obligations and attention they give, under its registry.
        viewed = durable.viewing(page)
        reading = viewed.document
        thread, thread_reading = browser_thread(viewed, work.live_reply)
        # The view's obligations are its own document's beside its frozen thread's, and
        # the page's updates', served once: a list row names a
        # record by its id.
        items = viewed.all_obligations["all"] + durable.updates["all"]
        _apply_thread_attention(items, workflows, thread["threads"], agent_todos)
        documents[revision] = reading
        projection = reading.projection
        classified = {
            **projection.classified,
            **thread_reading.projection.classified,
        }
        coverage = []
        for event in events:
            if event["kind"] in verb_writers():
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
            "document": browser_document(reading, revision),
            "thread": thread,
            "obligations": items,
            "reports": canonical_reports(projection),
            "undo": browser_undo_candidates(
                events,
                reading,
                thread_reading.projection,
                undo_reading=undo_reading,
                words=words,
            ),
            "coverage": coverage,
            "published_at": published_at,
            "queues": queues(workflows, todos, items, threads, reading.within),
        }
    if wants_history(readings[revision] for revision in view_revisions):
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
        "todos": todos,
        "plan": durable.plan,
        "receipts": [event for event in events if event.get("attempt")],
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
