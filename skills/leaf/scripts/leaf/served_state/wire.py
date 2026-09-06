"""Wire serialization for one declared state projection."""

from ..events import action_rests_on
from ..projection import StateProjection, folded_facet


def browser_projection(
    projection: StateProjection,
    *,
    scope: str,
    within: dict,
    floors: dict,
) -> dict:
    """Serialize one declared projection without making the wire its authority."""
    entries = []
    for coordinate, (event, spec) in projection.classified.values():
        restated = []
        if event["kind"] == "action":
            restated = [
                identity
                for identity in action_rests_on(event, within)
                if floors.get(identity, 0) > event["revision"]
            ]
        entries.append(
            {
                "event": event,
                "coordinate": list(coordinate),
                "value": folded_facet(event, spec) if spec.get("record") else None,
                "scope": scope,
                "restated": restated,
            }
        )
    return {
        "entries": entries,
        "actions": [event["id"] for event, _spec in projection.actions.values()],
        "reports": [
            event["id"]
            for standing in projection.reports.values()
            for event, _spec in standing
        ],
        "desired": [event["id"] for event, _spec in projection.desired.values()],
    }
