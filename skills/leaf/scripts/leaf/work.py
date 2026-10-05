"""The subjects the agent's work stands on: what an id names, which widgets seat a
task, and which widget tasks a version would leave without a target."""

from pathlib import Path

from .asks import quoted_in
from .files import latest_revision
from .passages import page_passages
from .projection import (
    PageReading,
    StateProjection,
    frozen_thread_reading,
    retirement_outcomes,
    rewritten_bodies,
)
from .registry.storage import require_registry
from .revision_artifact import read_revision
from .thread_context import id_subject


def widget_seat_error(page: PageReading, widget: str, moves: list[dict]) -> str | None:
    """Why `widget` cannot seat a task on `page`, or None.

    A task on a widget stands beside that widget at the page edge, so the widget must
    be live on the page: present under the page's standing outcomes and not quoted
    exhibit content. And it must be a seat for work: its tag declares `x-work`, or it
    holds an unsettled move, among `moves` (`workflows.canonical_workflows`)."""
    rec = page.document.by_id.get(widget)
    if rec is None or rec["tag"] not in page.registry:
        return f"{widget!r} is not a widget on this page"
    passages = page_passages(
        page.document,
        page.registry,
        retirement_outcomes(page.projection.actions),
        rewritten_bodies(page.projection.actions),
    )
    if widget in passages.retired or widget in passages.gone:
        return f"{widget} is not visible under the page's standing outcomes"
    if quoted_in(rec, page.registry):
        return f"{widget} is quoted exhibit content, not a live page widget"
    held = any(item["subject"] == {"kind": "widget", "id": widget} for item in moves)
    if not page.registry[rec["tag"]].get("x-work") and not held:
        return (
            f"{widget} has no work seat; its widget declares no x-work and it holds "
            "no unsettled move"
        )
    return None


def widget_tasks_without_targets(
    document,
    projection: StateProjection,
    tasks: list[dict],
    registry: dict,
    ignored=(),
) -> list[str]:
    """The widgets of open `tasks` that `document` would leave with no live target
    for their margin entry, apart from `ignored`."""
    ignored = set(ignored)
    passages = page_passages(
        document,
        registry,
        retirement_outcomes(projection.actions),
        rewritten_bodies(projection.actions),
    )
    missing = set()
    for task in tasks:
        subject = task["subject"]
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
            missing.add(widget)
    return sorted(missing)


def page_element(page_dir: Path, name: str) -> dict | None:
    """`{"kind": "element", "id"}` where `name` is the id of an element of the newest
    revision that names no thread or widget, such as a section, which a task may stand
    on; else None."""
    revision = latest_revision(page_dir)
    if revision is None or name not in read_revision(page_dir, revision).document.ids:
        return None
    return {"kind": "element", "id": name}


def page_subject(page_dir: Path, events: list, name: str) -> dict | None:
    """What `name` names (`thread_context.id_subject`), against the page the user is
    looking at: the newest revision's widgets, and the widgets its threads' messages
    froze. Every command that takes an id reads it here, so each resolves it alike."""
    revision = latest_revision(page_dir)
    if revision is None:
        return id_subject(events, set(), {}, {}, name)
    registry = require_registry(page_dir)
    return id_subject(
        events,
        {
            element
            for element, rec in read_revision(page_dir, revision).document.by_id.items()
            if rec["tag"] in registry
        },
        frozen_thread_reading(events, registry).thread_by_widget,
        read_revision(page_dir, revision).enclosing,
        name,
    )
