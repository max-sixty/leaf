"""Ephemeral servers for exact candidate documents."""

import contextlib
from pathlib import Path

from leaf.hosting import TemporaryPageServer
from leaf.leases import page_locked
from leaf.page_snapshot import capture_page_snapshot
from leaf.refusals import Refused
from leaf.render_checks import ProbesUnlinked
from leaf.revision_artifact import RevisionArtifact
from leaf.structure import SourceDocument


@contextlib.contextmanager
def preview_server(
    page_dir: Path,
    document: SourceDocument,
    revision: int,
    *,
    transition_held: bool = False,
    artifact: RevisionArtifact | None = None,
    through_seq: int | None = None,
):
    """Serve one exact document without changing the page's durable state, against
    the log through `through_seq` when given (`PageRead.through`).

    Its own key, not the machine's: this server is loopback-only and lives for the
    length of a `with`, so it neither needs nor should mint the access every page
    here is read with. The listener owns its cookie name, so opening a preview
    does not replace another same-host server's key in the browser's jar.

    The gate's probe modules are this Leaf's (`page_snapshot`), and they import the
    runtime out of the page by name, so a page another Leaf vendored at this
    protocol is read whenever its runtime has every name they import. Where it
    lacks one, the probes fail to link, and the gate refuses naming the re-vendor
    rather than the missing export.
    """
    transition = contextlib.nullcontext() if transition_held else page_locked(page_dir)
    with transition:
        snapshot = capture_page_snapshot(
            page_dir, document, revision, url="/", artifact=artifact
        )
        if through_seq is not None:
            snapshot = snapshot.through(through_seq)
        server = TemporaryPageServer(page_dir, page_options={"page_snapshot": snapshot})
        try:
            with server:
                yield server.url
        except ProbesUnlinked as error:
            raise Refused(
                f"this Leaf's render checks could not load against {page_dir}'s "
                f"runtime: {error}. Where another Leaf vendored the page, its runtime "
                f"lacks a name they import; re-vendor it with "
                f"`leaf page init {page_dir}`."
            ) from error
