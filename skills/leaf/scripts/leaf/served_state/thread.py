"""Thread-scoped browser projection."""

from ..events import (
    active_summaries,
    awaits_agent,
    bare_reaction,
    seat_root,
    turn_message,
    unanswered_agent_turn,
)
from ..projection import FrozenThreadReading
from ..read_state import content_version, unread_content
from ..schema import agent_name
from ..thread import is_answer
from .wire import browser_projection


def _answers_live_reply(event: dict, live_reply: dict) -> bool:
    """Whether one logged event is the durable answer a provisional reply stands in for.

    A provisional reply is reserved under a delivery attempt and addressed to a
    response, and the durable answer names itself by either. Reading only the response
    address let an answer whose address had moved stand beside its own placeholder, and
    the panel drew the draft rather than the answer the log held. A draft this reading
    finds no identity on is one nothing in the log can answer, and it stands.
    """
    return any(
        live_reply.get(named) is not None and event.get(named) == live_reply[named]
        for named in ("attempt", "responds")
    )


def _response_key(responds: str) -> dict:
    """The name an agent's answer to `responds` is drawn under, provisional or durable.

    A provisional reply and the answer that retires it are one message to the reader,
    but the answer's own attempt need not be the one the provisional reply was reserved
    under: an explicit `response reply` takes an author's retry key from a namespace of
    its own, so it can never consume the provider final's append identity. The input
    they both answer is the identity they share. A failure receipt is no answer
    (`thread.is_answer`), so it keeps its own name. The log can hold a second answer to
    an input though no writer gives one; a name stands for one message, so only the
    input's first answer in the log takes it."""
    return {"key": f"response:{responds}"}


def _named(event: dict) -> dict:
    """One served thread event carrying the name it is shown under (`agent_name`)."""
    return {**event, "agent": agent_name(event)}


def _answer_key(event: dict, first_answers: dict[str, str]) -> dict:
    """The name of an input's first answer (`_response_key`), by `first_answers`, each
    input's first answer's id in log order; nothing for any other event."""
    if not is_answer(event) or first_answers[event["responds"]] != event["id"]:
        return {}
    return _response_key(event["responds"])


def browser_thread(
    work, live_reply: dict | None = None
) -> tuple[dict, FrozenThreadReading]:
    """Serialize the shared frozen-thread work reading, adding presentation only.
    Messages and closing events carry their canonical display name; provisional
    replies and unread/summary protection never become durable work authority.

    A provisional reply joins its thread once it has words. Before then the input's
    workflow says the agent is replying, and an empty message would only reserve a
    bubble with nothing in it."""
    events, threads = work.events, work.threads
    reading, widget_questions = work.thread, work.widget_questions
    unread = unread_content(
        events, threads, reading.thread_by_name, reading.thread_by_widget
    )
    summaries_for = active_summaries(events, threads)
    rendered_threads = []
    first_answers: dict[str, str] = {}
    for event in events:
        if is_answer(event):
            first_answers.setdefault(event["responds"], event["id"])
    for thread_id, thread in threads.items():
        questions = work.thread_questions[thread_id]
        protected = set()
        if awaits_agent(thread):
            protected.add(turn_message(unanswered_agent_turn(thread)))
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
        # Each message names its current content version (`read_state`), the one the
        # browser marks read once its words have been shown.
        messages = [
            {
                **_named(message),
                **_answer_key(message, first_answers),
                "content_version": content_version(message),
            }
            for message in thread["msgs"]
        ]
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
    if (
        live_reply is not None
        and live_reply.get("text")
        and not any(_answers_live_reply(event, live_reply) for event in events)
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
                    "content_version": f"stream:{live_reply['turn']}",
                    "attempt": live_reply["attempt"],
                    **_response_key(live_reply["responds"]),
                    "provisional": True,
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
