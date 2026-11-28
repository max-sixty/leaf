"""Wire serialization for one declared state projection."""

from leaf.log.events import restated_under
from leaf.log.projection import StateProjection, folded_value


def browser_projection(
    projection: StateProjection,
    *,
    scope: str,
    within: dict,
    floors: dict,
) -> dict:
    """Serialize one declared projection without making the wire its authority.

    Each entry carries the event as the log holds it, and `value`, its record as it
    stands, which a version that rewrote a member of the set it records narrows
    (`events.InForce`): the value the browser folds."""
    entries = []
    for coordinate, (event, spec) in projection.classified.values():
        standing = projection.in_force.get(event["id"], event)
        entries.append(
            {
                "event": event,
                "coordinate": list(coordinate),
                "spec": spec,
                "value": folded_value(standing, spec) if spec.get("record") else None,
                "scope": scope,
                "restated": restated_under(event, floors, within)
                if event["kind"] == "action"
                else [],
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
