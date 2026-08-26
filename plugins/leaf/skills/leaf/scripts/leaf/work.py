"""Widget-work seats and projected work subjects."""

import sys
from pathlib import Path

from .events import build_threads, standing_work_claims
from .files import published_versions, version_path
from .passages import page_passages
from .projection import (
    StateProjection,
    asking,
    decisions,
    page_projection,
    quoted_in,
    replayed_attrs,
    rewritten_bodies,
)
from .registry import require_registry


def widget_work_seat(
    rec: dict, projection: "StateProjection", registry: dict
) -> str | None:
    """The active, validated local-work seat declared by this widget's layer."""
    entry = registry.get(rec["tag"]) or {}
    work = entry.get("x-work")
    attrs = replayed_attrs(rec, projection)
    if not work or not asking(attrs, work.get("when", {})):
        return None
    if work["seat"] == "conversation" and not asking(
        attrs, entry["x-conversation"].get("when", {})
    ):
        return None
    return work["seat"]


def widget_work_without_seats(
    html: str,
    parser,
    projection: "StateProjection",
    events: list,
    status: dict,
    registry: dict,
    ignored=(),
) -> list[str]:
    """Standing widget work the given document and vocabulary cannot show locally."""
    ignored = set(ignored)
    decided = decisions(projection.actions, registry)
    passages = page_passages(
        html, registry, decided, rewritten_bodies(projection.actions)
    )
    missing = []
    for claim in standing_work_claims(status, events, include_resolved=True):
        subject = claim["subject"]
        if subject["kind"] != "widget" or subject["id"] in ignored:
            continue
        widget = subject["id"]
        rec = parser.by_id.get(widget)
        if not (
            rec
            and rec["tag"] in registry
            and widget not in passages.retired
            and widget not in passages.gone
            and not quoted_in(rec, registry)
            and widget_work_seat(rec, projection, registry)
        ):
            missing.append(widget)
    return sorted(missing)


def work_subject(page_dir: Path, events: list, target: str) -> dict:
    """Resolve one bare CLI id to a typed, locally renderable work subject."""
    threads = build_threads(events, {})
    thread = threads.get(target)

    widget = None
    widget_version = None
    widget_projection = None
    registry = None
    html = None
    published = published_versions(page_dir, events)
    if published:
        widget_version = published[-1]
        html = version_path(page_dir, widget_version).read_text(encoding="utf-8")
        registry = require_registry(page_dir)
        widget_projection, parser, _spk = page_projection(
            html, events, registry, widget_version
        )
        rec = parser.by_id.get(target)
        if rec and rec["tag"] in registry:
            widget = rec

    if thread is not None and widget is not None:
        sys.exit(
            f"{target} names both a comment thread and a page widget; "
            "rename one so --on has one subject"
        )
    if thread is not None:
        if thread["resolved"]:
            sys.exit(
                f"{target} is a resolved comment thread; reopen it before claiming work"
            )
        return {
            "subject": {"kind": "thread", "id": target},
            "after": events[-1]["seq"] if events else 0,
        }
    if widget is not None:
        assert (
            registry is not None and widget_projection is not None and html is not None
        )
        decided = decisions(widget_projection.actions, registry)
        passages = page_passages(
            html,
            registry,
            decided,
            rewritten_bodies(widget_projection.actions),
        )
        if target in passages.retired or target in passages.gone:
            sys.exit(f"{target} is not visible under the page's standing decisions")
        if quoted_in(widget, registry):
            sys.exit(f"{target} is quoted exhibit content, not a live page widget")
        if not widget_work_seat(widget, widget_projection, registry):
            sys.exit(
                f"{target} has no local work seat; its widget declaration "
                "does not provide one in this state"
            )
        return {
            "subject": {"kind": "widget", "id": target},
            "after": events[-1]["seq"] if events else 0,
        }
    sys.exit(f"{target} is not a comment thread or local page widget on this page")
