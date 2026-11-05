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
The replaceable record (`USER_VIEWS`) is independently locked and pruned on
writes after one day.

The record also keeps `viewed`, when a report last said a document was visible, in
POSIX seconds, which outlives the pruning. A visible document reports at least
every ten seconds (`runtime/user-view.js`), so it is that fresh while a tab shows
the page; a hidden tab sends no heartbeat, so the stamp records attention rather
than tab lifetime. The agent reads it in `page state` (`viewed_at`).
"""

import copy
from datetime import UTC, datetime, timedelta
from pathlib import Path

from leaf.registry.schema import aware_instant, schema_error
from leaf.schema import USER_VIEWS_FILE, USER_VIEWS_LOCK
from leaf.state import Record, described, flocked, object_schema

FRESH_FOR_S = 45
RETAIN_FOR = timedelta(days=1)


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
_IDENTITY = {"type": "object"}
_CHECK_BASIS = {
    "identity": _IDENTITY,
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
    "identity": described(
        "The rendering identity captured by this document.", _IDENTITY
    ),
    "session": described(
        "The document's random session id.",
        {"type": "string", "pattern": "^[0-9a-f]{32}$"},
    ),
    "sequence": described("The report's place among its session's reports.", _SEQUENCE),
    "visible": described("Whether the document was visible.", {"type": "boolean"}),
    "revision": described("The revision the document shows.", _REVISION),
    "through_seq": described(
        "The log position the tab's latest server reading was taken through, or "
        "null before one arrives.",
        _THROUGH_SEQ,
    ),
    "viewport": described("The layout viewport, in CSS pixels.", _VIEWPORT),
    "visual_viewport": described(
        "The visual viewport, as `window.visualViewport` reports it.", _VISUAL_VIEWPORT
    ),
    "shown_window": _SHOWN_WINDOW,
    "color_scheme": described("The scheme the document is drawn in.", _SCHEME),
    "reduced_motion": described(
        "Whether the user prefers reduced motion.", {"type": "boolean"}
    ),
    "pointer": described(
        "Whether the primary pointer is coarse, as a finger is, or fine.",
        {"enum": ["coarse", "fine"]},
    ),
    "scroll": described(
        "The document's scroll offset.", _object({"x": _NUMBER, "y": _NUMBER})
    ),
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
        "received_at": described("When the server received the report.", _INSTANT),
        "checks": described(
            "The document's latest view checks, with the revision, log position, "
            "viewport and scheme they read, or null.",
            {
                **_object(
                    {
                        **_CHECKS["properties"],
                        "checked_at": described(
                            "When the server first received these checks.", _INSTANT
                        ),
                    }
                ),
                "type": ["object", "null"],
            },
        ),
    }
)


USER_VIEWS = Record(
    "user-views",
    described(
        "The user's browser views of a page, in the page directory's "
        "`user-views.json`.",
        object_schema(
            {
                "sessions": described(
                    "Each document's latest report, by its session id.",
                    {"type": "object", "additionalProperties": _RECORD},
                )
            },
            {
                "viewed": described(
                    "When a report last said a document was visible, in POSIX "
                    "seconds (`viewed_at`).",
                    {"type": "number"},
                )
            },
        ),
    ),
    since=27,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _stored(page_dir: Path) -> dict:
    return USER_VIEWS.read(page_dir / USER_VIEWS_FILE) or {"sessions": {}}


def viewed_at(page_dir: Path) -> float | None:
    """When a browser last showed the page, or None for a page nobody has viewed."""
    return _stored(page_dir).get("viewed")


def observe_user_view(page_dir: Path, payload: dict) -> bool:
    """Validate and accept a newer report, returning whether it replaced a view.

    The HTTP boundary owns authentication, body size and revision existence.
    Checks may lag context, but their sample sequence cannot name a future report.
    An omitted reading is represented by null; it does not erase prior checks.
    """
    error = schema_error(_PAYLOAD, payload)
    if error:
        raise ValueError(f"invalid user view: {error}")
    # The stamps below are the store's, so they go on a copy of the caller's report.
    record = copy.deepcopy(payload)
    if record["checks"] and record["checks"]["sequence"] > record["sequence"]:
        raise ValueError("user view checks sequence exceeds report sequence")
    now = _now()
    with flocked(page_dir / USER_VIEWS_LOCK):
        stored = _stored(page_dir)
        records = stored["sessions"]
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
        viewed = now.timestamp() if record["visible"] else stored.get("viewed")
        USER_VIEWS.write(
            page_dir / USER_VIEWS_FILE,
            {"sessions": records, **({} if viewed is None else {"viewed": viewed})},
        )
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
    for record in _stored(page_dir)["sessions"].values():
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
