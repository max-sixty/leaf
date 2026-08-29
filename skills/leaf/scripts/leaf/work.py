"""Widget-work seats and projected work subjects."""

import sys
from pathlib import Path

from .decisions import asking, quoted_in, replayed_attrs
from .events import build_threads, note_settlements
from .files import latest_revision, revision_path
from .passages import enclosing_of, page_passages
from .projection import (
    StateProjection,
    page_projection,
    retirement_outcomes,
    rewritten_bodies,
)
from .registry.storage import require_registry


def work_claim_revision(claim: dict, _events: list) -> int:
    """The exact working document on which widget work was claimed."""
    return claim["revision"]


def standing_work_claims(status: dict, events: list) -> list:
    """The transient work claims the durable exchange has not ended.

    A claim starts after one exact log sequence. Thread work ends at the agent's
    next reply in that conversation; widget work ends at a later version note
    that explicitly settles its id. The sequence boundary matters in both
    directions: renewing work after an answer creates a new claim, and an old
    answer cannot settle it merely because it names the same subject.

    A reply and a widget settlement are permanent log answers, and they are the
    whole test. Resolution is not one: it only hides a thread claim and an
    unresolve shows it again, so both callers asked for the resolved threads back
    and the question was never really being asked. What this reading wants of a
    conversation is who has spoken in it since the claim, so it reads the
    messages and never the resolution — which is why it names no page.
    """
    threads = build_threads(events, {})
    standing = []
    for claim in status.get("work", []):
        subject = claim["subject"]
        after = claim["after"]
        if subject["kind"] == "thread":
            thread = threads.get(subject["id"])
            if thread is None:
                continue
            replied = any(
                msg["kind"] == "reply"
                and msg["author"] == "claude"
                and msg["seq"] > after
                for msg in thread["msgs"]
            )
            if replied:
                continue
        elif subject["kind"] == "widget":
            if any(
                event["kind"] == "note"
                and event["seq"] > after
                and subject["id"] in note_settlements(event, "work")
                for event in events
            ):
                continue
        else:
            continue
        standing.append(claim)
    return standing


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
    decided = retirement_outcomes(projection.actions, registry)
    passages = page_passages(
        html, registry, decided, rewritten_bodies(projection.actions)
    )
    missing = []
    for claim in standing_work_claims(status, events):
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
    widget = None
    widget_revision = None
    widget_projection = None
    registry = None
    html = None
    spk: dict = {}
    try:
        widget_revision = latest_revision(page_dir)
    except SystemExit:
        widget_revision = None
    if widget_revision is not None:
        html = revision_path(page_dir, widget_revision).read_text(encoding="utf-8")
        registry = require_registry(page_dir)
        widget_projection, parser, spk = page_projection(
            html, events, registry, widget_revision
        )
        rec = parser.by_id.get(target)
        if rec and rec["tag"] in registry:
            widget = rec

    # Against the page this command has already read: it loads the vendored
    # registry above and raises where that gate refuses, so folding threads
    # against no page here bought nothing and could answer differently from
    # `page state` for the same conversation.
    thread = build_threads(events, enclosing_of(spk)).get(target)

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
        decided = retirement_outcomes(widget_projection.actions, registry)
        passages = page_passages(
            html,
            registry,
            decided,
            rewritten_bodies(widget_projection.actions),
        )
        if target in passages.retired or target in passages.gone:
            sys.exit(f"{target} is not visible under the page's standing outcomes")
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
            "revision": widget_revision,
        }
    sys.exit(f"{target} is not a comment thread or local page widget on this page")
