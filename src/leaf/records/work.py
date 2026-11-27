"""The subjects to-dos stand on and the widgets that admit new to-dos."""

from pathlib import Path

from leaf.base.files import latest_revision
from leaf.base.findings import Finding
from leaf.log.events import thread_structure
from leaf.log.projection import PageReading
from leaf.log.thread_context import id_subject, thread_names, thread_widgets
from leaf.source.revision_artifact import read_revision


def widget_seat_error(page: PageReading, widget: str) -> Finding | None:
    """Why `widget` cannot seat a to-do on `page`, or None: it names no widget the
    page declares. A to-do on a widget stands beside that widget at the page edge, as
    one on any other element does, wherever the page shows it."""
    rec = page.document.by_id.get(widget)
    if rec is None or rec["tag"] not in page.registry:
        return Finding("not-a-widget", values={"widget": widget})
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
    hold. Every command that takes an id reads it here, so each resolves it alike."""
    revision = latest_revision(page_dir)
    if revision is None:
        return id_subject(events, set(), {}, {}, name)
    reading = read_revision(page_dir, revision)
    return id_subject(
        events,
        {
            element
            for element, rec in reading.document.by_id.items()
            if rec["tag"] in reading.registry
        },
        thread_widgets(thread_structure(events), thread_names(events)),
        reading.enclosing,
        name,
    )
