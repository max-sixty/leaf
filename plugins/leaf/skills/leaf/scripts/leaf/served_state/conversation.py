"""Conversation-scoped browser projection."""

from ..asks import thread_ask_projection
from ..events import (
    awaits_agent,
    bare_reaction,
    is_reaction,
    seat_root,
    spoken_turns,
)
from ..passages import spoken
from ..projection import StateProjection, state_projection
from ..thread_context import thread_roots, thread_structure
from .wire import _browser_projection


def _thread_projection(events: list, registry: dict):
    structure = thread_structure(events)
    roots = thread_roots(events)
    byid, spk = {}, {}
    for event in events:
        if markup := event.get("markup"):
            fragment = structure.fragments[event["id"]]
            byid.update(fragment.by_id)
            spk.update(spoken(markup, registry))
    projection = state_projection(events, byid, spk, registry, None, floors={})
    return projection, byid, spk, roots, structure


def _thread_awaits_reader(
    thread: dict,
    registry: dict,
    awaiting: dict[str, bool],
    structure,
) -> bool:
    if thread["resolved"]:
        return False
    turns = spoken_turns(thread)
    if not turns or turns[-1]["author"] != "claude":
        return False
    last = turns[-1]
    if last["kind"] == "reply":
        fragment = structure.fragments.get(last["id"])
        asks = [
            rec["attrs"].get("id")
            for rec in (fragment.lf_elements if fragment else [])
            if (registry.get(rec["tag"]) or {}).get("x-awaits") is not None
        ]
        structural = (
            any(awaiting.get(identity, False) for identity in asks) if asks else None
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
) -> tuple[dict, StateProjection]:
    settled = {identity for identity, thread in threads.items() if thread["resolved"]}
    prepared = _thread_projection(events, registry)
    projection, _byid, _spk, _roots, structure = prepared
    asks, awaiting = thread_ask_projection(events, registry, settled, prepared=prepared)
    rendered_threads = [
        {
            **thread,
            "awaits_agent": awaits_agent(thread),
            "awaits_reader": _thread_awaits_reader(
                thread, registry, awaiting, structure
            ),
            "bare_reaction": bare_reaction(thread),
            "seat": seat_root(thread),
        }
        for thread in threads.values()
    ]
    return (
        {
            "projection": _browser_projection(
                projection, scope="conversation", within={}, floors={}
            ),
            "asks": {"reader": asks, "unanswered": asks, "awaiting": awaiting},
            "threads": rendered_threads,
            "done": [event for event in events if event["kind"] == "done"],
        },
        projection,
    )
