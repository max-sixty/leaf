"""Document-scoped browser projection and undo readings."""

from ..document_reading import read_document
from ..events import UndoReading
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
) -> tuple[dict, StateProjection]:
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
            "asks": document.asks,
            "requests": document.requests,
        },
        document.projection,
    )


def _browser_undo_candidates(
    events: list,
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
        candidates.append(item)
    return candidates
