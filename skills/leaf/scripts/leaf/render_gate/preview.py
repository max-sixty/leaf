"""Ephemeral servers for exact candidate documents."""

import contextlib
from pathlib import Path

from leaf.event_log import flocked, now_iso, read_events
from leaf.files import revision_label, version_name
from leaf.hosting import TemporaryPageServer
from leaf.leases import transition_lock


@contextlib.contextmanager
def preview_server(
    page_dir: Path,
    source: bytes,
    revision: int,
    *,
    version: int | None = None,
    transition_held: bool = False,
):
    """Serve one exact document without changing the page's durable state.

    Its own key, not the machine's: this server is loopback-only and lives for the
    length of a `with`, so it neither needs nor should mint the access every page
    here is read with. It sets that key under the one cookie name, which would sign
    a reader out of every page on 127.0.0.1 — except that both callers drive
    Playwright, whose browser brings its own jar.
    """
    transition = (
        contextlib.nullcontext()
        if transition_held
        else flocked(transition_lock(page_dir))
    )
    with transition:
        events = read_events(page_dir)
        active = {
            "revision": revision,
            "version": version,
            "url": (
                f"/versions/{version_name(version)}" if version is not None else "/"
            ),
            "label": (
                f"v{version}"
                if version is not None
                else revision_label(events, revision)
            ),
            "activated_at": now_iso(),
        }
        server = TemporaryPageServer(
            page_dir,
            handler_options={"preview_source": {"data": source, "active": active}},
        )
        with server:
            yield server.url
