"""Widget-work seats and projected work subjects."""

import sys
from pathlib import Path

from .asks import quoted_in
from .events import build_threads, note_settlements
from .files import latest_revision
from .passages import page_passages
from .projection import (
    StateProjection,
    frozen_thread_reading,
    page_reading,
    retirement_outcomes,
    rewritten_bodies,
)
from .registry.storage import require_registry
from .revision_artifact import read_revision
from .workflows import canonical_workflows


def standing_work_claims(status: dict, events: list) -> list:
    """The transient work claims the durable exchange has not ended.

    A claim starts after one exact log sequence. Thread work ends at the agent's
    next reply in that thread; widget work ends at a later version note
    that explicitly settles its id. The sequence boundary matters in both
    directions: renewing work after an answer creates a new claim, and an old
    answer cannot settle it merely because it names the same subject.

    A reply and a widget settlement are permanent log answers, and they are the
    whole test. Resolution is not one: it only hides a thread claim and an
    unresolve shows it again, so both callers asked for the resolved threads back
    and the question was never really being asked. What this reading wants of a
    thread is who has spoken in it since the claim, so it reads the
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
                and msg["author"] == "agent"
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


def widget_work_without_targets(
    document,
    projection: "StateProjection",
    events: list,
    status: dict,
    registry: dict,
    ignored=(),
) -> list[str]:
    """Standing widget work with no live page target for its target margin entry."""
    ignored = set(ignored)
    decided = retirement_outcomes(projection.actions)
    passages = page_passages(
        document, registry, decided, rewritten_bodies(projection.actions)
    )
    missing = []
    for claim in standing_work_claims(status, events):
        subject = claim["subject"]
        if subject["kind"] != "widget" or subject["id"] in ignored:
            continue
        widget = subject["id"]
        rec = document.by_id.get(widget)
        if not (
            rec
            and rec["tag"] in registry
            and widget not in passages.retired
            and widget not in passages.gone
            and not quoted_in(rec, registry)
        ):
            missing.append(widget)
    return sorted(missing)


def work_subject(page_dir: Path, events: list, target: str, *, standing: list) -> dict:
    """Resolve one bare CLI id to a typed, locally renderable work subject.

    Any id a delivery names as an event's address resolves: a page widget, or a
    thread by its root, by any message in it, or by a widget frozen into its
    markup. A thread claim also names an input the thread holds, a message or a
    move on its frozen widgets, and that exact input reads Working
    (`workflows.canonical_workflows`). Renewing a claim keeps the input the
    `standing` claim on that thread names while the thread still holds it, so
    Working stays beside what prompted the work; otherwise it names the newest."""
    widget = None
    widget_revision = None
    widget_projection = None
    registry = None
    page = None
    html = None
    widget_revision = latest_revision(page_dir)
    if widget_revision is not None:
        registry = require_registry(page_dir)
        page = page_reading(
            read_revision(page_dir, widget_revision).under(registry),
            events,
            widget_revision,
        )
        document = page.document
        html = document.html
        widget_projection = page.projection
        rec = page.document.by_id.get(target)
        if rec and rec["tag"] in registry:
            widget = rec

    # Against the page this command has already read: it loads the vendored
    # registry above and raises where that gate refuses, so folding threads
    # against no page here bought nothing and could answer differently from
    # `page state` for the same thread.
    threads = build_threads(events, page.within if page is not None else {})
    thread_of = {
        message["id"]: root
        for root, thread in threads.items()
        for message in thread["msgs"]
    }
    frozen = frozen_thread_reading(events, registry) if registry is not None else None
    thread_id = thread_of.get(target)
    if thread_id is None and frozen is not None:
        thread_id = frozen.thread_by_widget.get(target)
    thread = threads.get(thread_id) if thread_id is not None else None

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
        work = {
            "subject": {"kind": "thread", "id": thread_id},
            "after": events[-1]["seq"] if events else 0,
        }
        widgets = frozen.thread_by_widget if frozen is not None else {}

        def holder(subject: dict) -> str | None:
            if subject["kind"] == "thread":
                return subject["id"]
            return widgets.get(subject["id"])

        held = [
            item
            for item in canonical_workflows(
                [], threads, frozen, page=page, events=events
            )
            if item["next_actor"] == "agent" and holder(item["subject"]) == thread_id
        ]
        inputs = [item["input"] for item in sorted(held, key=lambda item: item["seq"])]
        kept = next(
            (
                claim.get("event")
                for claim in standing
                if claim["subject"] == work["subject"]
            ),
            None,
        )
        if kept in inputs:
            work["event"] = kept
        elif inputs:
            work["event"] = inputs[-1]
        return work
    if widget is not None:
        assert (
            registry is not None and widget_projection is not None and html is not None
        )
        decided = retirement_outcomes(widget_projection.actions)
        passages = page_passages(
            document,
            registry,
            decided,
            rewritten_bodies(widget_projection.actions),
        )
        if target in passages.retired or target in passages.gone:
            sys.exit(f"{target} is not visible under the page's standing outcomes")
        if quoted_in(widget, registry):
            sys.exit(f"{target} is quoted exhibit content, not a live page widget")
        has_receipt = any(
            item["input"] is not None
            and item["subject"] == {"kind": "widget", "id": target}
            for item in canonical_workflows([], threads, None, page=page)
        )
        if not registry[widget["tag"]].get("x-work") and not has_receipt:
            sys.exit(
                f"{target} has no local work seat; its widget declares no x-work "
                "and it has no unsettled action receipt"
            )
        return {
            "subject": {"kind": "widget", "id": target},
            "after": events[-1]["seq"] if events else 0,
            "revision": widget_revision,
        }
    sys.exit(f"{target} is not a comment thread or local page widget on this page")
