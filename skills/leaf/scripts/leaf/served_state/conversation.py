"""Conversation-scoped browser projection."""

from ..asks import local_ask_entry, thread_ask_readings
from ..events import (
    active_summaries,
    awaits_agent,
    bare_reaction,
    is_reaction,
    seat_root,
    spoken_turns,
    taken_back,
    unanswered_agent_turn,
)
from ..projection import FrozenThreadReading, frozen_thread_reading
from ..requests import request_lifecycles_for, request_phases
from .wire import browser_projection


def _thread_awaits_reader(
    thread_id: str,
    thread: dict,
    registry: dict,
    awaiting: dict[str, bool],
    structure,
    open_ask_threads: set[str],
) -> bool:
    if thread["resolved"]:
        return False
    if thread_id in open_ask_threads:
        return True
    turns = spoken_turns(thread)
    tokens = registry.get("$reactions", {}).get("tokens", {})
    for index in range(len(turns) - 1, -1, -1):
        message = turns[index]
        if message["author"] != "agent":
            continue
        later = turns[index + 1 :]
        if any(entry["author"] != "agent" for entry in later):
            continue
        fragment = structure.fragments.get(message["id"])
        asks = [
            rec["attrs"].get("id")
            for rec in (fragment.lf_elements if fragment else [])
            if local_ask_entry(registry.get(rec["tag"]) or {})
        ]
        structural = (
            any(awaiting.get(identity, False) for identity in asks) if asks else None
        )
        settled = any(
            is_reaction(reaction)
            and reaction["author"] == "user"
            and reaction.get("parent") == message["id"]
            and (tokens.get(reaction["token"]) or {}).get("settles")
            for reaction in thread["msgs"]
        )
        if message["kind"] != "reply":
            if structural is False:
                continue
            if not settled:
                return True
            continue
        if structural is False or (structural is None and not message.get("awaits")):
            continue
        if not settled:
            return True
    return False


def browser_conversation(
    events: list,
    registry: dict,
    threads: dict,
    live_reply: dict | None = None,
) -> tuple[dict, FrozenThreadReading]:
    settled = {identity for identity, thread in threads.items() if thread["resolved"]}
    reading = frozen_thread_reading(events, registry)
    requests = request_lifecycles_for(
        events,
        reading.elements,
        registry,
        {"kind": "thread"},
    )
    asks = thread_ask_readings(
        events,
        registry,
        settled,
        reading=reading,
        request_phases=request_phases(requests),
    )
    awaiting = asks["awaiting"]
    open_ask_threads = {ask["thread"] for ask in asks["reader"]}
    rendered_threads = []
    for thread_id, thread in threads.items():
        awaits_reader = _thread_awaits_reader(
            thread_id,
            thread,
            registry,
            awaiting,
            reading.structure,
            open_ask_threads,
        )
        awaits_agent_now = awaits_agent(thread)
        protected = set()
        turns = spoken_turns(thread)
        if awaits_agent_now:
            unanswered = unanswered_agent_turn(thread)
            if unanswered is not None:
                protected.add(unanswered["id"])
        if awaits_reader and turns:
            protected.add(turns[-1]["id"])
        ask_sources = {
            ask["source"] for ask in asks["unanswered"] if ask["thread"] == thread_id
        }
        for message_id, fragment in reading.structure.fragments.items():
            if ask_sources.intersection(fragment.by_id):
                protected.add(message_id)
        summaries = active_summaries(events, thread_id, thread)
        for summary in summaries:
            summary["protected"] = [
                identity for identity in summary["covers"] if identity in protected
            ]
        rendered_threads.append(
            {
                **thread,
                "awaits_agent": awaits_agent_now,
                "awaits_reader": awaits_reader,
                "bare_reaction": bare_reaction(thread),
                "seat": seat_root(thread),
                "summaries": summaries,
            }
        )
    if live_reply is not None and not any(
        event.get("responds") == live_reply.get("responds") for event in events
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
    withdrawn = taken_back(events)
    return (
        {
            "projection": browser_projection(
                reading.projection, scope="conversation", within={}, floors={}
            ),
            "asks": asks,
            "requests": requests,
            "threads": rendered_threads,
            # Through the withdrawal, like every other fold: an approval a reader
            # took back is not one, and this list is what the banner's own button
            # reads to say whether the version has been signed off.
            "done": [
                event
                for event in events
                if event["kind"] == "done" and event["id"] not in withdrawn
            ],
        },
        reading,
    )
