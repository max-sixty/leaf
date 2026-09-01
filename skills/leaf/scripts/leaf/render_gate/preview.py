"""Ephemeral servers for exact candidate documents."""

import contextlib
import secrets
import threading
from pathlib import Path

from leaf.event_log import flocked, now_iso, read_events
from leaf.files import revision_label, version_name
from leaf.hosting import LeafHTTPServer
from leaf.http import handler_for
from leaf.leases import transition_lock


@contextlib.contextmanager
def preview_server(
    page_dir: Path,
    source: bytes,
    revision: int,
    *,
    version: int | None = None,
    handler_factory=None,
    server_type=None,
    transition_held: bool = False,
):
    """Serve one exact document without changing the page's durable state.

    Its own key, not the machine's: this server is loopback-only and lives for the
    length of a `with`, so it neither needs nor should mint the access every page
    here is read with. It sets that key under the one cookie name, which would sign
    a reader out of every page on 127.0.0.1 — except that both callers drive
    Playwright, whose browser brings its own jar.
    """
    handler_factory = handler_for if handler_factory is None else handler_factory
    server_type = LeafHTTPServer if server_type is None else server_type
    transition = (
        contextlib.nullcontext()
        if transition_held
        else flocked(transition_lock(page_dir))
    )
    with transition:
        token = secrets.token_urlsafe(16)
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
        httpd = server_type(
            ("127.0.0.1", 0),
            handler_factory(
                page_dir,
                token,
                preview_source={"data": source, "active": active},
            ),
        )
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            yield f"http://127.0.0.1:{httpd.server_address[1]}/?t={token}"
        finally:
            httpd.shutdown()
