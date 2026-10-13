"""The subjects to-dos stand on and the widgets that admit new to-dos."""

from pathlib import Path

from .asks import quoted_in
from .files import latest_revision, list_revisions
from .findings import Finding
from .passages import page_passages
from .projection import (
    PageReading,
    retirement_outcomes,
    rewritten_bodies,
)
from .registry.storage import require_registry
from .revision_artifact import read_revision
from .thread_context import (
    effective_thread_events,
    id_subject,
    thread_names,
    thread_structure,
    thread_widgets,
)


def widget_seat_error(
    page: PageReading, widget: str, workflows: list[dict]
) -> Finding | None:
    """Why `widget` cannot seat a to-do on `page`, or None.

    A to-do on a widget stands beside that widget at the page edge, so the widget must
    be live on the page: present under the page's standing outcomes and not quoted
    exhibit content. And it must be a seat for work: its tag declares `x-work`, or it
    holds an unsettled action, among `workflows` (`workflows.canonical_workflows`)."""
    named = {"widget": widget}
    rec = page.document.by_id.get(widget)
    if rec is None or rec["tag"] not in page.registry:
        return Finding("not-a-widget", values=named)
    passages = page_passages(
        page.document,
        page.registry,
        retirement_outcomes(page.projection.actions),
        rewritten_bodies(page.projection.actions),
    )
    if widget in passages.retired or widget in passages.gone:
        return Finding("hidden-widget", values=named)
    if quoted_in(rec, page.registry):
        return Finding("quoted-seat", values=named)
    held = any(
        item["subject"] == {"kind": "widget", "id": widget} for item in workflows
    )
    if not page.registry[rec["tag"]].get("x-work") and not held:
        return Finding("no-work-seat", values=named)
    return None


def page_element(page_dir: Path, name: str) -> dict | None:
    """`{"kind": "element", "id"}` where `name` is the id of an element of the newest
    revision that names no thread or widget, such as a section, which a to-do may stand
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
    events = effective_thread_events(events, list_revisions(page_dir))
    return id_subject(
        events,
        {
            element
            for element, rec in read_revision(page_dir, revision).document.by_id.items()
            if rec["tag"] in registry
        },
        thread_widgets(thread_structure(events), thread_names(events)),
        read_revision(page_dir, revision).enclosing,
        name,
    )
