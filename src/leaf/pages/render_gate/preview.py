"""Ephemeral servers for exact candidate documents."""

import contextlib
from pathlib import Path

from leaf.pages.hosting import TemporaryPageServer
from leaf.pages.page_snapshot import PageSnapshot


@contextlib.contextmanager
def preview_server(
    page_dir: Path,
    snapshot: PageSnapshot,
):
    """Serve a captured reading without holding a mutable page's locks.

    Its own key, not the machine's: this server is loopback-only and lives for the
    length of a `with`, so it neither needs nor should mint the access every page
    here is read with. The listener owns its cookie name, so opening a preview
    does not replace another same-host server's key in the browser's jar.

    The server runs this Leaf's runtime and serves its probes beside it
    (`runtime_selection`), so the probes read the runtime they were written for
    whichever Leaf initialized the page.

    Nothing replaces this server while a reader holds it, so a page that says it
    cannot start will never start. A reader therefore opens the page at
    `asked_again` and passes `fixed_server` to its waits
    (`render_checks.wait_until_ready`). Each wait then ends as soon as the page says
    so, and raises with the page's reason.
    """
    with TemporaryPageServer(
        page_dir, page_options={"page_snapshot": snapshot}
    ) as server:
        yield server.url
