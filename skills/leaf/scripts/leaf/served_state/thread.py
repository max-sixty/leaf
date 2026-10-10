"""Thread-scoped browser projection."""

from ..events import (
    active_summaries,
    awaits_agent,
    bare_reaction,
    seat_root,
    unanswered_agent_turn,
)
from ..projection import FrozenThreadReading
from ..read_state import unread_content
from ..schema import agent_name
from .wire import browser_projection


def _answers_live_reply(event: dict, live_reply: dict) -> bool:
    """Whether one logged event is the durable answer a provisional reply stands in for.

    A provisional reply is reserved under a delivery attempt and addressed to a
    response, and the durable answer names itself by either. Reading only the response
    address let an answer whose address had moved stand beside its own placeholder — and
    since every consumer keys a message on its attempt, the two collided on one key and
    the panel drew the empty draft rather than the answer the log held. A draft this
    reading finds no identity on is one nothing in the log can answer, and it stands.
    """
    return any(
        live_reply.get(named) is not None and event.get(named) == live_reply[named]
        for named in ("attempt", "responds")
    )


def _named(event: dict) -> dict:
    """One served thread event carrying the name it is shown under (`agent_name`)."""
    return {**event, "agent": agent_name(event)}


def browser_thread(
    work, live_reply: dict | None = None
) -> tuple[dict, FrozenThreadReading]:
    """Serialize the shared frozen-thread work reading, adding presentation only.
    Messages and closing events carry their canonical display name; provisional
    replies and unread/summary protection never become durable work authority."""
    events, threads = work.events, work.threads
    reading, widget_questions = work.thread, work.widget_questions
    unread = unread_content(
        events, threads, reading.thread_by_name, reading.thread_by_widget
    )
    summaries_for = active_summaries(events, threads)
    rendered_threads = []
    for thread_id, thread in threads.items():
        questions = work.thread_questions[thread_id]
        protected = set()
        if awaits_agent(thread):
            protected.add(unanswered_agent_turn(thread)["id"])
        if questions.prompt is not None:
            protected.add(questions.prompt["message"])
        question_sources = {
            question["source"]["id"]
            for question in widget_questions["unanswered"]
            if question["thread"] == thread_id
        }
        for message_id, fragment in reading.structure.fragments.items():
            if question_sources.intersection(fragment.by_id):
                protected.add(message_id)
        summaries = summaries_for[thread_id]
        for summary in summaries:
            summary["protected"] = [
                identity for identity in summary["covers"] if identity in protected
            ]
        messages = [_named(message) for message in thread["msgs"]]
        rendered_threads.append(
            {
                **thread,
                "msgs": messages,
                "root": next(
                    message
                    for message in messages
                    if message["id"] == thread["root"]["id"]
                ),
                "resolved": thread["resolved"] and _named(thread["resolved"]),
                "user_prompt": questions.prompt,
                "bare_reaction": bare_reaction(thread),
                "seat": seat_root(thread),
                "summaries": summaries,
                "unread": unread[thread_id],
            }
        )
    if live_reply is not None and not any(
        _answers_live_reply(event, live_reply) for event in events
    ):
        target = next(
            (
                thread
                for thread in rendered_threads
                if any(
                    message["id"] == live_reply.get("reply_to")
                    for message in thread["msgs"]
                )
            ),
            None,
        )
        if target is not None:
            target["msgs"] = [
                *target["msgs"],
                {
                    "id": f"stream:{live_reply['turn']}",
                    "attempt": live_reply["attempt"],
                    "kind": "reply",
                    "addressable": False,
                    "author": "agent",
                    "agent": live_reply["agent"],
                    "parent": live_reply["reply_to"],
                    "text": live_reply.get("text", ""),
                    "ts": live_reply["ts"],
                    "pending": live_reply.get("state") == "active",
                },
            ]
    return (
        {
            "projection": browser_projection(
                reading.projection, scope="thread", within={}, floors={}
            ),
            "questions": work.questions,
            "threads": rendered_threads,
            # Standing approvals across every stamp, for Threads' event timeline.
            # Current-version approval state lives only in its Question.
            "approval_history": work.approvals,
        },
        reading,
    )
