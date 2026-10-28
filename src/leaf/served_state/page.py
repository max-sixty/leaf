"""The complete state response for one served page.

`state.schema.json` beside this module declares its shape and is each field's home: a
field's meaning is its description there. The tests hold real readings to it
(`interact_support.served_state_error`), and the browser build generates the type the
runtime and the Worker read it by."""

from datetime import timedelta
from pathlib import Path
from typing import NamedTuple

from ..activity import WORKING_GRACE
from ..data import browser_data_from
from ..files import revision_label
from .browser import BrowserReading, project_browser_state
from .context import PageRead, read_page


class ServedPage(NamedTuple):
    """One served state answer and what it was serialized from in the same snapshot:
    the semantic readings, and the page's stored external data.

    `reading` is None before the page has an active revision, when there is no
    document to read threads, obligations, or widgets against.
    """

    state: dict
    reading: BrowserReading | None
    data: dict


def full_state(
    page_dir: Path,
    events: list,
    *,
    layer_identity: dict | None = None,
    now: str | None = None,
) -> dict:
    """The live state reading for callers already holding the page transaction."""
    return read_served_page(
        read_page(page_dir, events, layer_identity=layer_identity, now=now)
    ).state


def read_served_page(
    context: PageRead,
    *,
    preview: dict | None = None,
    publication: dict | None = None,
    source_error: str | None = None,
    view_revision: int | None = None,
) -> ServedPage:
    active = context.active
    projected = project_browser_state(context, view_revision)
    browser, reading = projected if projected is not None else (None, None)
    work = context.work
    selected_registry = (
        context.revision(view_revision or active["revision"]).registry
        if active is not None
        else context.registry
    )
    identity = (
        context.serve_layer(selected_registry["$layer"])
        if active is not None
        else context.layer
    )
    state = {
        "layer": identity,
        "now": context.now,
        "working_grace_ms": WORKING_GRACE // timedelta(milliseconds=1),
        "taken": context.taken,
        "active": active,
        "versions": list(context.versions),
        "revision_labels": {
            str(revision): revision_label(context.events, revision)
            for revision in sorted(
                context.revisions
                | {event["revision"] for event in context.events if "revision" in event}
            )
        },
        "source_error": source_error,
        "data": browser_data_from(context.data, selected_registry),
        "files": context.bound_files(),
        **context.presence,
        "activity": {
            **{
                key: value
                for key, value in work.activity.items()
                if key not in {"workflows", "todos", "obligations"}
            },
            # The records of the updates the agent owes an answer, by id; their
            # workflows are `workflows`, and the records each view's `obligations`.
            "obligations": [item["obligation"] for item in work.obligations],
        },
        "workflows": work.workflows,
        "browser": browser,
        "events": context.events,
        **({"preview": preview} if preview else {}),
        # Whoever answers a hosted copy is the host's agent, before its first comment
        # too, not the voice that last wrote the page (`presence.page_agent`).
        **(
            {"publication": publication, "agent": publication["agent"]}
            if publication
            else {}
        ),
    }
    return ServedPage(state, reading, context.data)
