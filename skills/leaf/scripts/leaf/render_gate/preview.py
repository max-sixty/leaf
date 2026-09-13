"""Ephemeral servers for exact candidate documents."""

import contextlib
from pathlib import Path

from leaf.event_log import flocked
from leaf.files import version_name
from leaf.hosting import TemporaryPageServer
from leaf.leases import transition_lock
from leaf.page_snapshot import capture_page_snapshot
from leaf.revision_artifact import RevisionArtifact
from leaf.structure import SourceDocument


@contextlib.contextmanager
def preview_server(
    page_dir: Path,
    document: SourceDocument,
    revision: int,
    *,
    version: int | None = None,
    transition_held: bool = False,
    artifact: RevisionArtifact | None = None,
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
        active = {
            "revision": revision,
            "version": version,
            "url": (
                f"/versions/{version_name(version)}" if version is not None else "/"
            ),
        }
        snapshot = capture_page_snapshot(page_dir, document, active, artifact=artifact)
        server = TemporaryPageServer(
            page_dir, handler_options={"page_snapshot": snapshot}
        )
        with server:
            yield server.url
