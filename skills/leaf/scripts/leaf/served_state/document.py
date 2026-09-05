"""Document-scoped browser projection and undo readings."""

from ..document_reading import read_document
from ..events import (
    UndoReading,
    action_retracted,
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
    standing_actions: dict[tuple, set[str]],
) -> bool:
    """Whether withdrawing one action exposes another durable value there."""
    desired = projection.desired.get(coordinate)
    if desired and desired[0]["id"] != event["id"]:
        return True
    if projection.reports.get(coordinate):
        return True
    return any(
        candidate_id != event["id"]
        for candidate_id in standing_actions.get(coordinate, ())
    )


def _standing_actions_by_coordinate(
    classified: dict,
    withdrawn: set,
    within: dict,
    floors: dict,
) -> dict[tuple, set[str]]:
    """Index surviving actions by coordinate for one retraction reading."""
    standing = {}
    for coordinate, (event, _spec) in classified.values():
        if (
            event["kind"] == "action"
            and event["id"] not in withdrawn
            and not action_retracted(event, floors, within)
        ):
            standing.setdefault(coordinate, set()).add(event["id"])
    return standing


def _browser_undo_candidates(
    events: list,
    document_within: dict,
    document_floors: dict,
    document_projection: StateProjection,
    conversation_projection: StateProjection,
    *,
    undo_reading: UndoReading,
) -> list[dict]:
    classified = {
        **document_projection.classified,
        **conversation_projection.classified,
    }
    candidates = []
    withdrawn = undo_reading.withdrawn
    document_standing = _standing_actions_by_coordinate(
        document_projection.classified,
        withdrawn,
        document_within,
        document_floors,
    )
    conversation_standing = _standing_actions_by_coordinate(
        conversation_projection.classified,
        withdrawn,
        {},
        {},
    )
    for event in reversed(events):
        if (
            event.get("author") != "user"
            or event["kind"] == "undo"
            or event["id"] in withdrawn
        ):
            continue
        if undo_reading.error({"undoes": event["id"]}):
            continue
        item = {"event": event}
        if event["kind"] == "action" and event["id"] in classified:
            coordinate, _entry = classified[event["id"]]
            item["coordinate"] = list(coordinate)
            if event["id"] in document_projection.classified:
                projection = document_projection
            else:
                projection = conversation_projection
            item["restores_desired"] = _restores_desired(
                event,
                coordinate,
                projection,
                document_standing
                if event["id"] in document_projection.classified
                else conversation_standing,
            )
        candidates.append(item)
    return candidates
