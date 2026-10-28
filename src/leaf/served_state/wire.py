"""Wire serialization for one declared state projection."""

from ..events import action_rests_on
from ..projection import StateProjection, folded_value


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
                "spec": spec,
                "value": folded_value(event, spec) if spec.get("record") else None,
                "scope": scope,
                "restated": restated,
                "absorbed": event["id"] in projection.absorbed,
                "stands": event["id"] in projection.in_force,
            }
        )
    return {
        "entries": entries,
        "actions": [event["id"] for event, _spec in projection.actions.values()],
        "reports": [
            event["id"]
            for reports in projection.reports.values()
            for event, _spec in reports
        ],
        "desired": [event["id"] for event, _spec in projection.desired.values()],
    }
