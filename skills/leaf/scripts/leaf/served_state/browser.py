"""Assemble browser state from requested documents and the standing log."""

from typing import NamedTuple

from ..asks import approval_blocking, collection
from ..document_reading import DocumentReading
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
from ..schema import WIDGET_KINDS
from ..thread_context import thread_memberships
from ..work_reading import WorkReading
from .context import PageRead
from .document import browser_document, browser_undo_candidates
from .queues import queues
from .thread import browser_thread
from .work import WorkState, served_workflows, work_state


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


def _readings(
    threads, asks: dict, workflows: list[dict], todos: list[dict]
) -> dict[str, tuple[dict | None, list[str]]]:
    """Each thread's attention and the asks in it the user owes, by thread id."""
    owed: dict[str, list[str]] = {}
    for ask in asks["user"]:
        if ask["thread"] is not None:
            owed.setdefault(ask["thread"], []).append(ask["id"])
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
                todos,
            ),
            owed.get(thread["id"], []),
        )
        for thread in threads
    }


# The gestures a user makes on a thread whose effect on its attention and asks
# only the log can read, each supposed on the threads where it is possible.
_SUPPOSED = ("reply", "edit", "resolve", "unresolve", "react", "unreact")


def _supposed(
    kind: str, thread: dict, seq: int, prompt: str | None, settling: tuple[str, ...]
) -> dict | None:
    """The user's `kind` gesture on `thread`, as the log would hold it, or None where
    the thread offers none: a rewrite needs words of the user's to rewrite, a
    settlement goes the way the thread does not stand, `react`, a reaction with a
    `settling` token on the agent turn whose ask the user owes (`prompt`), needs
    both, and `unreact`, taking back the newest reaction with such a token on an
    agent turn the log holds, needs one."""
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
        token = settling[0] if settling else None
        return (
            prompt
            and token
            and {**gesture, "kind": "reply", "parent": prompt, "token": token}
        )
    if kind == "unreact":
        # Only a reaction on an agent turn settles anything; a bare one is its own
        # thread, which taking it back removes.
        turns = {
            message["id"] for message in thread["msgs"] if message["author"] == "agent"
        }
        reaction = next(
            (
                message
                for message in reversed(thread["msgs"])
                if message["author"] == "user"
                and is_reaction(message)
                and message["token"] in settling
                and message.get("parent") in turns
            ),
            None,
        )
        return reaction and {**gesture, "kind": "undo", "undoes": reaction["id"]}
    if (kind == "resolve") == bool(thread["resolved"]):
        return None
    return {**gesture, "parent": thread["root"]["id"]}


def _apply_thread_attention(
    durable: WorkReading, workflows: list[dict], threads: list[dict], todos: list[dict]
):
    """Attach each served thread's `attention`, and `after`: the attention and owed
    asks each gesture of the user's would leave it with.

    A reply answers the prose asks before it and no widget ask, a rewrite
    answers none, either reopens a resolved thread and supersedes a failed response
    to a thread input, a reopening brings back what its resolution suppressed, such
    as a failed pick or an ask, and a reaction whose token settles (`$reactions`)
    answers the question the turn it marks asks, which `react` supposes on the turn
    whose ask the user owes, and taking such a reaction back reopens what it
    answered, which `unreact` supposes of the newest the thread holds, naming it as
    `undoes`. Rather than restate those rules, each `after`
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
    attention and asks agree with the reading the log gives back
    (`thread/model.js`, `foldThreads`).

    `durable` is the reading of the view these threads are served in, so a pinned
    revision's threads take the attention its own vocabulary reads; `workflows` are
    the page's, enriched with delivery liveness."""
    for thread in threads:
        thread["after"] = {}
    current = _readings(threads, durable.asks, workflows, todos)
    for thread in threads:
        thread["attention"] = current[thread["id"]][0]
    base = durable.events[-1]["seq"] if durable.events else 0
    held = durable.threads
    tokens = durable.registry.get("$reactions", {}).get("tokens", {})
    settling = tuple(name for name, token in tokens.items() if token.get("settles"))
    prompts = {
        identity: reading.prompt["message"] if reading.prompt else None
        for identity, reading in durable.thread_asks.items()
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
        after = _readings(reading.threads.values(), reading.asks, workflows, todos)
        for thread in threads:
            gesture = supposed.get(thread["id"])
            if gesture is None:
                thread["after"][kind] = None
                continue
            attention, owed = after[thread["id"]]
            if attention is not None and attention["workflow"] == gesture["id"]:
                attention = {**attention, "workflow": None}
            thread["after"][kind] = {
                "attention": attention,
                "owed": owed,
                **({"undoes": gesture["undoes"]} if kind == "unreact" else {}),
            }


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
        # The view's own reading of the log: its document, and the frozen thread
        # widgets with the asks and attention they give, under its registry.
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
        words = GestureWords(events, active_registry, revisions or readings.__getitem__)
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
