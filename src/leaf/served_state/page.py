"""The state response for one served page, whole; the page server sends a tab that
holds an earlier reading only what changed since (`tail.py`).

`state.schema.json` beside this module declares its shape and is each field's home: a
field's meaning is its description there. The tests hold real readings to it
(`interact_support.served_state_error`), and the browser build generates the type the
runtime and the Worker read it by."""

from datetime import timedelta
from pathlib import Path
from typing import NamedTuple

from ..activity import WORKING_GRACE
from ..files import revision_labels
from ..read_state import seen_revision
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
    """The whole answer."""
    active = context.active
    projected = project_browser_state(context, view_revision)
    browser, reading = projected if projected is not None else (None, None)
    work = context.work
    state = {
        "now": context.now,
        "working_grace_ms": WORKING_GRACE // timedelta(milliseconds=1),
        "taken": context.taken,
        "active": active,
        "versions": list(context.versions),
        "revision_labels": {
            str(revision): label
            for revision, label in revision_labels(
                context.events,
                sorted(
                    context.revisions
                    | {
                        event["revision"]
                        for event in context.events
                        if "revision" in event
                    }
                ),
            ).items()
        },
        # What the page's own user last saw; a hosted copy's reader is someone else.
        "seen": (
            context.descriptor(seen)
            if not publication and (seen := seen_revision(context.events)) is not None
            else None
        ),
        "source_error": source_error,
        "data": context.data,
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


def served_layer_identity(context: PageRead, view_revision: int | None) -> dict:
    """The identity of the layer the shown revision was read under, or the page's
    before a revision exists, with the fingerprint of the layer this Leaf composes to
    serve it (`registry.storage.served_layer`). The serving route adds it to the
    page's reading (`read_served_page`), because the fingerprint digests every file
    the layer serves, and a reader of the page's state such as `leaf page state` has
    no use for it."""
    active = context.active
    if active is None:
        return context.layer
    shown = context.revision(view_revision or active["revision"]).registry
    return context.serve_layer(shown["$layer"])
