"""Document-scoped browser projection and undo readings."""

from ..decisions import page_decision_inventory, page_decision_projection
from ..events import (
    UndoReading,
    action_retracted,
    retractions,
    seats_with_agent,
)
from ..passages import enclosing_of, page_passages
from ..projection import StateProjection, page_projection, retirement_outcomes
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
    passages = page_passages(
        html, registry, retirement_outcomes(projection.actions, registry)
    )
    dropped = set(passages.retired) | set(passages.gone)
    requests = request_lifecycles_for(
        events,
        parser.lf_elements,
        registry,
        {"kind": "page", "revision": revision},
    )
    phases = request_phases(requests)
    reader_decisions, reader_awaiting = page_decision_projection(
        parser,
        projection,
        parser.by_id,
        spk,
        registry,
        dropped,
        seats_with_agent(threads),
        request_phases=phases,
    )
    unanswered_decisions, unanswered_awaiting = page_decision_projection(
        parser,
        projection,
        parser.by_id,
        spk,
        registry,
        dropped,
        set(),
        request_phases=phases,
    )
    all_decisions = page_decision_inventory(
        parser,
        projection,
        parser.by_id,
        spk,
        registry,
        dropped,
        request_phases=phases,
        settled_away=set(passages.gone),
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
            "decisions": {
                "all": all_decisions,
                "reader": reader_decisions,
                "unanswered": unanswered_decisions,
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
