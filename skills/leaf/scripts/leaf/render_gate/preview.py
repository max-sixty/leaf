"""Ephemeral servers for exact candidate documents."""

import contextlib
import sys
from pathlib import Path

from leaf.event_log import flocked
from leaf.files import version_name
from leaf.hosting import TemporaryPageServer
from leaf.layer import payload_runtime_fingerprint
from leaf.leases import transition_lock
from leaf.page_snapshot import capture_page_snapshot
from leaf.registry.storage import layer_metadata
from leaf.revision_artifact import RevisionArtifact
from leaf.structure import SourceDocument


def _refuse_a_foreign_runtime(page_dir: Path) -> None:
    """Refuse to instrument a page whose runtime came from another Leaf.

    The gates serve their probe modules from the Leaf running the command and the
    runtime those modules import from the page, so the two have to come from one
    kernel. Where they do not, the browser reports an export the page's older runtime
    does not have, which reads as a defect in the page.
    """
    vendored = layer_metadata(page_dir).get("runtime")
    running = payload_runtime_fingerprint()
    if vendored == running:
        return
    sys.exit(
        f"{page_dir} was vendored from another Leaf's runtime modules — its layer "
        f"names {vendored or 'no runtime identity'} where this Leaf's are {running}. "
        "The browser gate loads the page's runtime into its own probe modules, so "
        f"re-vendor with `leaf page init {page_dir}` — stopping its server first if "
        "one is running."
    )


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
        _refuse_a_foreign_runtime(page_dir)
        active = {
            "revision": revision,
            "version": version,
            "url": (
                f"/versions/{version_name(version)}" if version is not None else "/"
            ),
        }
        snapshot = capture_page_snapshot(page_dir, document, active, artifact=artifact)
        server = TemporaryPageServer(page_dir, page_options={"page_snapshot": snapshot})
        with server:
            yield server.url
