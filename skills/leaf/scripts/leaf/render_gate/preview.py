"""Ephemeral servers for exact candidate documents."""

import contextlib
from pathlib import Path

from leaf.files import version_name
from leaf.hosting import TemporaryPageServer
from leaf.leases import page_locked
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
    through_seq: int | None = None,
):
    """Serve one exact document without changing the page's durable state, against
    the log through `through_seq` when given (`capture_page_snapshot`).

    Its own key, not the machine's: this server is loopback-only and lives for the
    length of a `with`, so it neither needs nor should mint the access every page
    here is read with. The listener owns its cookie name, so opening a preview
    does not replace another same-host server's key in the browser's jar.

    Like every page server it refuses a page vendored from another Leaf's runtime
    (`layer.foreign_runtime`), which the gate needs on its own account too: its probe
    modules come from this Leaf and import the runtime out of the page.
    """
    transition = contextlib.nullcontext() if transition_held else page_locked(page_dir)
    with transition:
        active = {
            "revision": revision,
            "version": version,
            "url": (
                f"/versions/{version_name(version)}" if version is not None else "/"
            ),
        }
        snapshot = capture_page_snapshot(
            page_dir, document, active, artifact=artifact, through_seq=through_seq
        )
        server = TemporaryPageServer(page_dir, page_options={"page_snapshot": snapshot})
        with server:
            yield server.url
