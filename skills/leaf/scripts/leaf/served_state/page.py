"""The complete state response for one served page."""

from datetime import timedelta
from pathlib import Path
from typing import NamedTuple

from ..activity import WORKING_GRACE, canonical_activity, canonical_stream_reply
from ..data import browser_data_from
from ..events import build_threads
from ..workflows import canonical_workflows
from .browser import BrowserReading, project_browser_state
from .context import PageRead, read_page


class ServedPage(NamedTuple):
    """One served state answer and what it was serialized from in the same snapshot:
    the semantic readings, and the page's stored external data.

    `reading` is None before the page has an active revision, when there is no
    document to read threads, Asks, or widgets against.
    """

    state: dict
    reading: BrowserReading | None
    data: dict


def project_activity(
    context: PageRead,
    browser: dict | None,
) -> dict:
    """Project activity even before the page has an active document."""
    if browser is not None:
        return browser.pop("activity")
    # No active document means no page containment; thread obligations remain.
    threads = build_threads(context.events, {})
    evidence = canonical_workflows(
        context.presence["claims"],
        threads,
        None,
        events=context.events,
    )
    return canonical_activity(
        context.presence,
        evidence,
        context.now,
        (context.live_stream or {}).get("activity"),
        canonical_stream_reply(
            context.presence, context.now, (context.live_stream or {}).get("reply")
        ),
        (context.live_stream or {}).get("reply_bindings"),
    )


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
    activity = project_activity(context, browser)
    selected_registry = (
        context.revision(view_revision or active["revision"]).registry
        if active is not None
        else context.registry
    )
    identity = selected_registry["$layer"] if active is not None else context.layer
    workflows = (
        browser.pop("workflows") if browser is not None else activity.pop("workflows")
    )
    state = {
        "layer": identity,
        # The clock every timestamp below was written by. A seat dating one reads
        # `Date.now()`, which is the user's own machine: a laptop an hour out
        # calls a claim made this minute an hour stale, on every seat at once, and
        # neither side can tell from the timestamp alone. Sent so the reading is
        # against the writer's clock rather than the user's.
        "now": context.now,
        # How long working may go unheard before it reads as quiet, measured on that
        # clock. Activity below is already read against it; a package dating a
        # worker's own reports asks `quietSince`, which reads this rather than a copy.
        "working_grace_ms": WORKING_GRACE // timedelta(milliseconds=1),
        # The moment this answer was taken, for a tab holding two. Answers cross — two
        # sockets, one held by a proxy or a test while a later one lands, a POST's
        # answer beside a read — and the log's sequence orders everything in a state
        # but the reading and its data, which are hashes with no order of their own.
        # Stamped inside the page transaction every served answer is built under,
        # so the order of these is the order the answers were taken in, whichever
        # order they land. The wall clock rather than a counter: a counter starts over
        # with the server, and a tab open across that restart would refuse every
        # answer until the count caught up.
        "taken": context.taken,
        "active": active,
        "versions": list(context.versions),
        "source_error": source_error,
        "data": browser_data_from(context.data, selected_registry),
        **context.presence,
        "activity": activity,
        "workflows": workflows,
        "browser": browser,
        # As logged: a message's text is Markdown the page's vendored runtime renders,
        # and its markup is the fragment the CLI gate validated. The wire adds nothing,
        # so the only vocabulary a page's frozen layer has to keep speaking is the
        # log's own, which $events already stamps.
        "events": context.events,
        **({"preview": preview} if preview else {}),
        **({"publication": publication} if publication else {}),
    }
    return ServedPage(state, reading, context.data)
