"""Thread-scoped browser projection."""

from ..asks import thread_ask_readings, thread_awaits_user
from ..events import (
    active_summaries,
    awaits_agent,
    bare_reaction,
    seat_root,
    spoken_turns,
    standing_approvals,
    unanswered_agent_turn,
)
from ..projection import FrozenThreadReading, frozen_thread_reading
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
    events: list,
    registry: dict,
    threads: dict,
    live_reply: dict | None = None,
) -> tuple[dict, FrozenThreadReading]:
    """The threads' browser reading. Whose turn each thread is reaches the browser
    only as its `attention`, which `served_state.browser` attaches from this
    reading's Asks and `user_prompt` and the page's workflows. Each message, and the
    event that closed a thread, carries as `agent` the name it is shown under
    (`agent_name`), so the browser keeps no fallback name of its own."""
    settled = {identity for identity, thread in threads.items() if thread["resolved"]}
    reading = frozen_thread_reading(events, registry)
    asks = thread_ask_readings(events, registry, settled, reading=reading)
    awaiting = asks["awaiting"]
    unread = unread_content(
        events, threads, reading.thread_by_name, reading.thread_by_widget
    )
    open_ask_threads = {ask["thread"] for ask in asks["user"]}
    summaries_for = active_summaries(events, threads)
    rendered_threads = []
    for thread_id, thread in threads.items():
        awaits_user, user_prompt = thread_awaits_user(
            thread_id,
            thread,
            registry,
            awaiting,
            reading.structure,
            open_ask_threads,
        )
        protected = set()
        turns = spoken_turns(thread)
        if awaits_agent(thread):
            protected.add(unanswered_agent_turn(thread)["id"])
        if awaits_user and turns:
            protected.add(turns[-1]["id"])
        ask_sources = {
            ask["source"] for ask in asks["unanswered"] if ask["thread"] == thread_id
        }
        for message_id, fragment in reading.structure.fragments.items():
            if ask_sources.intersection(fragment.by_id):
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
                "user_prompt": user_prompt,
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
            "asks": {key: asks[key] for key in ("all", "user", "unanswered")},
            "threads": rendered_threads,
            # What the banner's own button reads to say whether the version has
            # been signed off.
            "done": standing_approvals(events),
        },
        reading,
    )
