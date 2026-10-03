"""Disposable readings of the user's actual browser views, for the authoring agent.

Each document has a random session id and increasing report sequence. Reports
replace that session's observation; reordered reports cannot renew it or resurrect
a hidden view. Several visible documents remain separate rather than choosing a
single width for the user. Server receipt time establishes freshness, not the
browser's clock. A missed hide expires after 45 seconds.

Checks retain their own revision, log position, viewport, scheme and sequence.
Their first server receipt is preserved when later context reports repeat them;
a fresh context can therefore carry older checks. These observations are neither
events nor obligations and cannot affect semantic state or document activation.
The replaceable record is independently locked, pruned on writes after one day,
and ignored when its format does not belong to this implementation.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from leaf.files import read_json
from leaf.registry.schema import aware_instant, schema_error
from leaf.schema import USER_VIEWS_FILE, USER_VIEWS_LOCK
from leaf.state import flocked, write_json

FRESH_FOR_S = 45
RETAIN_FOR = timedelta(days=1)
FORMAT = "leaf-user-views-v1"


def _object(properties: dict) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


_NUMBER = {"type": "number"}
_POSITIVE = {"type": "number", "exclusiveMinimum": 0}
_NONNEGATIVE = {"type": "number", "minimum": 0}
_REVISION = {"type": "integer", "minimum": 1}
_SEQUENCE = {"type": "integer", "minimum": 1}
_THROUGH_SEQ = {"type": ["integer", "null"], "minimum": 0}
_SCHEME = {"enum": ["light", "dark"]}
_VIEWPORT = _object({"width": _POSITIVE, "height": _POSITIVE})
_VISUAL_VIEWPORT = _object(
    {
        "width": _POSITIVE,
        "height": _POSITIVE,
        "offset_left": _NUMBER,
        "offset_top": _NUMBER,
        "scale": _POSITIVE,
    }
)
_SHOWN_WINDOW = _object(
    {"x": _NUMBER, "y": _NUMBER, "width": _NONNEGATIVE, "height": _NONNEGATIVE}
)
_CHECK_BASIS = {
    "revision": _REVISION,
    "through_seq": _THROUGH_SEQ,
    "viewport": _VIEWPORT,
    "visual_viewport": _VISUAL_VIEWPORT,
    "shown_window": _SHOWN_WINDOW,
    "color_scheme": _SCHEME,
}
_CHECKS = _object(
    {"sequence": _SEQUENCE, **_CHECK_BASIS, "reading": {"type": "object"}}
)
_PROPERTIES = {
    "session": {"type": "string", "pattern": "^[0-9a-f]{32}$"},
    "sequence": _SEQUENCE,
    "visible": {"type": "boolean"},
    "revision": _REVISION,
    "through_seq": _THROUGH_SEQ,
    "viewport": _VIEWPORT,
    "visual_viewport": _VISUAL_VIEWPORT,
    "shown_window": _SHOWN_WINDOW,
    "color_scheme": _SCHEME,
    "reduced_motion": {"type": "boolean"},
    "pointer": {"enum": ["coarse", "fine"]},
    "scroll": _object({"x": _NUMBER, "y": _NUMBER}),
    "visible_regions": {
        "type": "array",
        "items": {"type": "string", "minLength": 1, "maxLength": 1024},
        "maxItems": 2048,
        "uniqueItems": True,
    },
    "checks": {"anyOf": [{"type": "null"}, _CHECKS]},
}
_PAYLOAD = _object(_PROPERTIES)
_INSTANT = {"type": "string", "format": "date-time"}
_RECORD = _object(
    {
        **_PROPERTIES,
        "received_at": _INSTANT,
        "checks": {
            "anyOf": [
                {"type": "null"},
                _object({**_CHECKS["properties"], "checked_at": _INSTANT}),
            ]
        },
    }
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _records(page_dir: Path) -> dict:
    stored = read_json(page_dir / USER_VIEWS_FILE)
    if (
        not isinstance(stored, dict)
        or stored.get("format") != FORMAT
        or not isinstance(stored.get("sessions"), dict)
    ):
        return {}
    return {
        session: record
        for session, record in stored["sessions"].items()
        if schema_error(_RECORD, record) is None and record["session"] == session
    }


def observe_user_view(page_dir: Path, payload: dict) -> bool:
    """Validate and accept a newer report, returning whether it replaced a view.

    The HTTP boundary owns authentication, body size and revision existence.
    Checks may lag context, but their sample sequence cannot name a future report.
    An omitted reading is represented by null; it does not erase prior checks.
    """
    error = schema_error(_PAYLOAD, payload)
    if error:
        raise ValueError(f"invalid user view: {error}")
    try:
        # Besides strict JSON numbers, this detaches callers' mutable observations.
        record = json.loads(json.dumps(payload, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid user view JSON: {exc}") from exc
    if record["checks"] and record["checks"]["sequence"] > record["sequence"]:
        raise ValueError("user view checks sequence exceeds report sequence")
    now = _now()
    with flocked(page_dir / USER_VIEWS_LOCK):
        records = _records(page_dir)
        previous = records.get(record["session"])
        if previous is not None and record["sequence"] <= previous["sequence"]:
            return False
        records = {
            session: value
            for session, value in records.items()
            if now - aware_instant(value["received_at"]) <= RETAIN_FOR
        }
        record["received_at"] = now.isoformat()
        checks = record["checks"]
        previous_checks = previous["checks"] if previous is not None else None
        if previous_checks and (
            checks is None or checks["sequence"] <= previous_checks["sequence"]
        ):
            record["checks"] = previous_checks
        elif checks is not None:
            checks["checked_at"] = record["received_at"]
        records[record["session"]] = record
        write_json(page_dir / USER_VIEWS_FILE, {"format": FORMAT, "sessions": records})
    return True


def read_user_views(page_dir: Path, active_revision: int | None) -> dict:
    """Read every retained document's context with explicit recency and scope.

    Freshness states recency; visibility independently says whether the document
    remains on screen. A hidden report remains factual context.
    Checks carry their own timestamp and scope, even when the context has moved.
    Reading never renews attention or prunes storage.
    """
    now = _now()
    sessions = []
    for record in _records(page_dir).values():
        age = (now - aware_instant(record["received_at"])).total_seconds()
        if age > RETAIN_FOR.total_seconds():
            continue
        checks = record["checks"]
        if checks is not None:
            checks = {
                **checks,
                "freshness": (
                    "fresh"
                    if (now - aware_instant(checks["checked_at"])).total_seconds()
                    <= FRESH_FOR_S
                    else "stale"
                ),
                "matches_view": all(checks[key] == record[key] for key in _CHECK_BASIS),
            }
        sessions.append(
            {
                **record,
                "checks": checks,
                "freshness": "fresh" if age <= FRESH_FOR_S else "stale",
                "matches_active_revision": record["revision"] == active_revision,
            }
        )
    sessions.sort(
        key=lambda record: (record["received_at"], record["session"]), reverse=True
    )
    return {"fresh_for_s": FRESH_FOR_S, "sessions": sessions}
