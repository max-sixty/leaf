"""Document-scoped browser projection and undo readings."""

from ..document_reading import read_document
from ..events import (
    action_retracted,
    taken_back,
    undo_error,
)
from ..projection import StateProjection
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
    document = read_document(
        html, events, registry, revision, threads, prepared=prepared
    )
    return (
        {
            "revision": revision,
            "projection": _browser_projection(
                document.projection,
                scope="document",
                within=document.within,
                floors=document.floors,
            ),
            "decisions": document.decisions,
            "requests": document.requests,
        },
        document.projection,
        document.within,
        document.floors,
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
