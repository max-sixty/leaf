"""Document-scoped browser projection and undo readings."""

from ..asks import page_ask_projection
from ..events import (
    action_retracted,
    retractions,
    seats_with_agent,
    taken_back,
    undo_error,
)
from ..passages import enclosing_of, page_passages
from ..projection import StateProjection, decisions, page_projection
from ..requests import request_lifecycles_for, request_phases
from .wire import _browser_projection


def _browser_document(
    html: str,
    events: list,
    registry: dict,
    revision: int,
    threads: dict,
    *,
    prepared: tuple | None = None,
) -> tuple[dict, StateProjection, dict, dict]:
    projection, parser, spk = prepared or page_projection(
        html, events, registry, revision
    )
    passages = page_passages(html, registry, decisions(projection.actions, registry))
    dropped = set(passages.retired) | set(passages.gone)
    requests = request_lifecycles_for(
        events,
        parser.lf_elements,
        registry,
        {"kind": "page", "revision": revision},
    )
    phases = request_phases(requests)
    reader_asks, reader_awaiting = page_ask_projection(
        parser,
        projection,
        parser.by_id,
        spk,
        registry,
        dropped,
        seats_with_agent(threads),
        request_phases=phases,
    )
    unanswered_asks, unanswered_awaiting = page_ask_projection(
        parser,
        projection,
        parser.by_id,
        spk,
        registry,
        dropped,
        set(),
        request_phases=phases,
    )
    within = enclosing_of(spk)
    floors = retractions(events, revision)
    return (
        {
            "revision": revision,
            "projection": _browser_projection(
                projection,
                scope="document",
                within=within,
                floors=floors,
            ),
            "asks": {
                "reader": reader_asks,
                "unanswered": unanswered_asks,
                "awaiting": reader_awaiting,
                "unanswered_awaiting": unanswered_awaiting,
            },
            "requests": requests,
        },
        projection,
        within,
        floors,
    )


def _restores_desired(
    event: dict,
    coordinate: tuple,
    projection: StateProjection,
    withdrawn: set,
    within: dict,
    floors: dict,
) -> bool:
    """Whether withdrawing one action exposes another durable value there."""
    desired = projection.desired.get(coordinate)
    if desired and desired[0]["id"] != event["id"]:
        return True
    if projection.reports.get(coordinate):
        return True
    return any(
        candidate_coordinate == coordinate
        and candidate["kind"] == "action"
        and candidate["id"] != event["id"]
        and candidate["id"] not in withdrawn
        and not action_retracted(candidate, floors, within)
        for candidate_coordinate, (candidate, _spec) in projection.classified.values()
    )


def _browser_undo_candidates(
    events: list,
    within: dict,
    document_within: dict,
    document_floors: dict,
    document_projection: StateProjection,
    conversation_projection: StateProjection,
) -> list[dict]:
    classified = {
        **document_projection.classified,
        **conversation_projection.classified,
    }
    candidates = []
    withdrawn = taken_back(events)
    for event in reversed(events):
        if (
            event.get("author") != "user"
            or event["kind"] == "undo"
            or event["id"] in withdrawn
        ):
            continue
        if undo_error({"undoes": event["id"]}, events, within):
            continue
        item = {"event": event}
        if event["kind"] == "action" and event["id"] in classified:
            coordinate, _entry = classified[event["id"]]
            item["coordinate"] = list(coordinate)
            if event["id"] in document_projection.classified:
                projection = document_projection
                action_within = document_within
                floors = document_floors
            else:
                projection = conversation_projection
                action_within = {}
                floors = {}
            item["restores_desired"] = _restores_desired(
                event,
                coordinate,
                projection,
                withdrawn,
                action_within,
                floors,
            )
        candidates.append(item)
    return candidates
