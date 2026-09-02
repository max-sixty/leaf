"""Conversation-scoped browser projection."""

from ..decisions import local_decision_entry, thread_decision_projection
from ..events import (
    awaits_agent,
    bare_reaction,
    is_reaction,
    seat_root,
    spoken_turns,
    taken_back,
)
from ..projection import FrozenThreadReading, frozen_thread_reading
from ..requests import request_lifecycles_for, request_phases
from .wire import _browser_projection


def _thread_awaits_reader(
    thread_id: str,
    thread: dict,
    registry: dict,
    awaiting: dict[str, bool],
    structure,
    open_decision_threads: set[str],
) -> bool:
    if thread["resolved"]:
        return False
    if thread_id in open_decision_threads:
        return True
    turns = spoken_turns(thread)
    if not turns or turns[-1]["author"] != "claude":
        return False
    last = turns[-1]
    if last["kind"] == "reply":
        fragment = structure.fragments.get(last["id"])
        decisions = [
            rec["attrs"].get("id")
            for rec in (fragment.lf_elements if fragment else [])
            if local_decision_entry(registry.get(rec["tag"]) or {})
        ]
        structural = (
            any(awaiting.get(identity, False) for identity in decisions)
            if decisions
            else None
        )
        if structural is False or (structural is None and not last.get("awaits")):
            return False
    tokens = registry.get("$reactions", {}).get("tokens", {})
    return not any(
        is_reaction(message)
        and message["author"] == "user"
        and message.get("parent") == last["id"]
        and (tokens.get(message["token"]) or {}).get("settles")
        for message in thread["msgs"]
    )


def _browser_conversation(
    events: list, registry: dict, threads: dict
) -> tuple[dict, FrozenThreadReading]:
    settled = {identity for identity, thread in threads.items() if thread["resolved"]}
    reading = frozen_thread_reading(events, registry)
    requests = request_lifecycles_for(
        events,
        reading.elements,
        registry,
        {"kind": "thread"},
    )
    decisions, awaiting = thread_decision_projection(
        events,
        registry,
        settled,
        reading=reading,
        request_phases=request_phases(requests),
    )
    open_decision_threads = {decision["thread"] for decision in decisions}
    rendered_threads = [
        {
            **thread,
            "awaits_agent": awaits_agent(thread),
            "awaits_reader": _thread_awaits_reader(
                thread_id,
                thread,
                registry,
                awaiting,
                reading.structure,
                open_decision_threads,
            ),
            "bare_reaction": bare_reaction(thread),
            "seat": seat_root(thread),
        }
        for thread_id, thread in threads.items()
    ]
    withdrawn = taken_back(events)
    return (
        {
            "projection": _browser_projection(
                reading.projection, scope="conversation", within={}, floors={}
            ),
            "decisions": {
                "reader": decisions,
                "unanswered": decisions,
                "awaiting": awaiting,
            },
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
