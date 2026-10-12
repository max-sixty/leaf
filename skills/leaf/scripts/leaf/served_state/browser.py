"""Assemble browser state from requested documents and the standing log."""

from typing import NamedTuple

from ..document_reading import DocumentReading, read_document
from ..events import UndoReading, is_reaction
from ..files import stamped_version
from ..gesture_words import GestureWords, RevisionReader
from ..history import history, wants_history
from ..passages import SourceReading
from ..projection import (
    FrozenThreadReading,
    canonical_reports,
    page_reading,
)
from ..questions import approval_blocking, collection
from ..schema import WIDGET_KINDS
from ..thread_context import thread_memberships
from .context import PageRead
from .document import browser_document, browser_undo_candidates
from .queues import queues
from .thread import browser_thread
from .work import WorkState, served_workflows, work_state


class BrowserReading(NamedTuple):
    """The semantic readings one browser state serializes.

    A Python reader of the same snapshot selects from these rather than folding the
    log again: the page's threads, the frozen thread document, and each projected
    view's document reading, keyed by revision.
    """

    threads: dict
    thread: FrozenThreadReading
    documents: dict[int, DocumentReading]


def _thread_attention(
    thread: dict, owed: bool, candidates: list[dict], tasks: list[dict]
) -> dict | None:
    """Whose turn one thread is: `needs_user` while a Question in it is the user's
    (`owed`), or for a response the user must recover; `waiting` while a workflow
    holds the thread with the agent, which covers every input `events.unanswered_turns`
    holds, or while a task the agent opened on it stands; else None, as for every
    resolved thread. `candidates` are the thread's `served_workflows`, strongest first,
    so the first that qualifies is the one the thread waits on, and a workflow speaks
    before a task. `tasks` are the agent's open tasks, each stamped with its
    `thread`."""
    if thread["resolved"]:
        return None
    if owed:
        return {"kind": "needs_user", "reason": "question", "workflow": None}
    if recovery := next(
        (workflow for workflow in candidates if workflow["next_actor"] == "user"),
        None,
    ):
        return {"kind": "needs_user", "reason": "recovery", "workflow": recovery["id"]}
    if waiting := next(
        (workflow for workflow in candidates if workflow["holds_thread"]), None
    ):
        return {
            "kind": "waiting",
            "reason": "uncertain" if waiting["condition"] else "workflow",
            "workflow": waiting["id"],
        }
    if task := next((task for task in tasks if task["thread"] == thread["id"]), None):
        return {
            "kind": "waiting",
            "reason": "task",
            "workflow": None,
            # The line of the start running on it, while one holds it.
            "task": {
                "id": task["id"],
                "title": task["title"],
                "line": task["running"]["text"] if task["running"] else None,
            },
        }
    return None


def _readings(
    threads, questions: dict, workflows: list[dict], tasks: list[dict]
) -> dict[str, tuple[dict | None, list[str]]]:
    """Each thread's attention and the Questions in it the user owes, by thread id."""
    owed: dict[str, list[str]] = {}
    for question in questions["user"]:
        if question["thread"] is not None:
            owed.setdefault(question["thread"], []).append(question["id"])
    by_thread: dict[str, list[dict]] = {}
    for workflow in workflows:
        if workflow["thread"] is not None:
            by_thread.setdefault(workflow["thread"], []).append(workflow)
    return {
        thread["id"]: (
            _thread_attention(
                thread,
                thread["id"] in owed,
                by_thread.get(thread["id"], []),
                tasks,
            ),
            owed.get(thread["id"], []),
        )
        for thread in threads
    }


# The gestures a user makes on a thread whose effect on its attention and Questions
# only the log can read, each supposed on the threads where it is possible.
_SUPPOSED = ("reply", "edit", "resolve", "unresolve", "react")


def _supposed(
    kind: str, thread: dict, seq: int, prompt: str | None, settling: str | None
) -> dict | None:
    """The user's `kind` gesture on `thread`, as the log would hold it, or None where
    the thread offers none: a rewrite needs words of the user's to rewrite, a
    settlement goes the way the thread does not stand, and `react`, a reaction with
    the `settling` token on the agent turn whose question the user owes (`prompt`),
    needs both."""
    gesture = {
        "id": f"supposed-{kind}:{thread['id']}",
        "kind": kind,
        "author": "user",
        "seq": seq,
        "ts": thread["msgs"][-1]["ts"] if thread["msgs"] else None,
    }
    if kind == "reply":
        return {**gesture, "parent": thread["root"]["id"], "text": "…"}
    if kind == "edit":
        mine = next(
            (
                message
                for message in reversed(thread["msgs"])
                if message["author"] == "user"
                and not is_reaction(message)
                and message.get("text")
            ),
            None,
        )
        return mine and {**gesture, "message": mine["id"], "text": "…"}
    if kind == "react":
        return (
            prompt
            and settling
            and {**gesture, "kind": "reply", "parent": prompt, "token": settling}
        )
    if (kind == "resolve") == bool(thread["resolved"]):
        return None
    return {**gesture, "parent": thread["root"]["id"]}


def _apply_thread_attention(work: WorkState, threads: list[dict], tasks: list[dict]):
    """Attach each served thread's `attention`, and `after`: the attention and owed
    Questions each gesture of the user's would leave it with.

    A reply answers the prose Questions before it and no widget Question, a rewrite
    answers none, either reopens a resolved thread and supersedes a failed response
    to a thread input, a reopening brings back what its resolution suppressed, such
    as a failed pick or an Ask, and a reaction whose token settles (`$reactions`)
    answers the question the turn it marks asks, which `react` supposes on the turn
    whose question the user owes. Rather than restate those rules, each `after`
    reading is the log's own: the same reading of the work, folded with that gesture
    supposed on every thread where it is possible (threads are independent, so one
    fold serves them all), and the same `_thread_attention`. `after[kind]` is
    `{attention, owed}`, or None where the thread offers no such gesture. A waiting
    attention's `workflow` is null where it waits on the supposed gesture itself,
    which the browser draws as its own send. Delivery liveness, which activity adds
    to served workflows from claims and the clock, is not supposed, so where it would
    mark an earlier input uncertain the reading names the gesture's own wait instead;
    which actor owes the thread, and what, are the log's either way.

    The browser reads `after` while a gesture it sent is unanswered, so its thread
    attention and Questions agree with the reading the log gives back
    (`thread/model.js`, `foldThreads`)."""
    durable = work.durable
    for thread in threads:
        thread["after"] = {}
    current = _readings(threads, durable.questions, work.workflows, tasks)
    for thread in threads:
        thread["attention"] = current[thread["id"]][0]
    base = durable.events[-1]["seq"] if durable.events else 0
    held = durable.threads
    tokens = durable.registry.get("$reactions", {}).get("tokens", {})
    settling = next(
        (name for name, token in tokens.items() if token.get("settles")), None
    )
    prompts = {
        identity: reading.prompt["message"] if reading.prompt else None
        for identity, reading in durable.thread_questions.items()
    }
    for kind in _SUPPOSED:
        supposed = {
            identity: gesture
            for at, (identity, thread) in enumerate(held.items(), start=1)
            if (
                gesture := _supposed(
                    kind, thread, base + at, prompts[identity], settling
                )
            )
            is not None
        }
        if not supposed:
            for thread in threads:
                thread["after"][kind] = None
            continue
        reading = durable.supposing(list(supposed.values()))
        workflows = served_workflows(reading.workflows, reading.thread)
        after = _readings(reading.threads.values(), reading.questions, workflows, tasks)
        for thread in threads:
            gesture = supposed.get(thread["id"])
            if gesture is None:
                thread["after"][kind] = None
                continue
            attention, owed = after[thread["id"]]
            if attention is not None and attention["workflow"] == gesture["id"]:
                attention = {**attention, "workflow": None}
            thread["after"][kind] = {"attention": attention, "owed": owed}


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
    thread, thread_reading = browser_thread(durable, work.live_reply)
    thread_projection = thread_reading.projection

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
        reading = (
            durable.document
            if revision == active_revision
            else read_document(page, threads)
        )
        stamp = stamped_version(events, revision)
        document = browser_document(reading, revision)
        documents[revision] = reading
        projection = reading.projection
        classified = {
            **projection.classified,
            **thread_projection.classified,
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
        views[str(revision)] = {
            "basis": {"revision": revision, "through_seq": through_seq},
            "document": document,
            "reports": canonical_reports(projection),
            "undo": browser_undo_candidates(
                events,
                reading,
                thread_projection,
                undo_reading=undo_reading,
                stamp=stamp,
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
        work, thread["threads"], [task for task in tasks if task["owner"] == "agent"]
    )
    # Each view's Questions are its own document's beside the frozen thread's, so
    # each view carries the queues they add up to and the ones approving it waits on.
    for view in views.values():
        questions = view["document"]["questions"]["all"] + thread["questions"]["all"]
        view["queues"] = queues(
            thread["threads"], workflows, tasks, ended_tasks, collection(questions)
        )
        view["approval_blocking"] = [
            question["id"] for question in approval_blocking(questions)
        ]
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
        # Every thread whose history each logged event changes
        # (`thread_context.thread_memberships`), which the browser reads for the
        # gesture an unsent undo takes back or an unsent action replaces.
        "thread_memberships": {
            identity: threads
            for identity, threads in thread_memberships(
                events,
                thread_reading.thread_by_name,
                thread_reading.thread_by_widget,
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
        revision_ids=context.revisions,
    )
