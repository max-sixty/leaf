"""The complete state response for one served page."""

import time
from pathlib import Path

from ..data import browser_data
from ..event_log import now_iso
from ..files import active_descriptor, version_descriptors
from ..presence import presence
from ..registry.contract import RegistryError
from ..registry.storage import layer_metadata, load_registry
from .browser import project_browser_state


def full_state(
    page_dir: Path,
    events: list,
    layer_identity: dict | None = None,
    preview: dict | None = None,
    source_error: str | None = None,
    view_revision: int | None = None,
    active_override: dict | None = None,
    source_overrides: dict[int, str] | None = None,
) -> dict:
    if active_override is not None:
        active = active_override
    else:
        try:
            active = active_descriptor(page_dir, events)
        except SystemExit:
            active = None
    present = presence(page_dir, events)
    browser = project_browser_state(
        page_dir,
        events,
        view_revision,
        active,
        present["claims"],
        source_overrides,
    )
    try:
        registry = load_registry(page_dir)
    except RegistryError:
        registry = None
    identity = layer_identity or layer_metadata(page_dir)
    return {
        "layer": identity,
        # The clock every timestamp below was written by. A seat dating one reads
        # `Date.now()`, which is the reader's own machine: a laptop an hour out
        # calls a claim made this minute an hour stale, on every seat at once, and
        # neither side can tell from the timestamp alone. Sent so the reading is
        # against the writer's clock rather than the reader's.
        "now": now_iso(),
        # The moment this answer was taken, for a tab holding two. Answers cross — two
        # sockets, one held by a proxy or a test while a later one lands, a POST's
        # answer beside a read — and the log's sequence and the data's revision order
        # everything in a state but the reading, which is a hash with no order of its
        # own. Stamped inside the page transaction every served answer is built under,
        # so the order of these is the order the answers were taken in, whichever
        # order they land. The wall clock rather than a counter: a counter starts over
        # with the server, and a tab open across that restart would refuse every
        # answer until the count caught up.
        "taken": time.time(),
        "active": active,
        "versions": version_descriptors(page_dir, events),
        "source_error": source_error,
        "data": browser_data(page_dir, registry),
        **present,
        "browser": browser,
        # As logged: a message's text is Markdown the page's vendored runtime renders,
        # and its markup is the fragment the CLI gate validated. The wire adds nothing,
        # so the only vocabulary a page's frozen layer has to keep speaking is the
        # log's own, which $events already stamps.
        "events": events,
        **({"preview": preview} if preview else {}),
    }
