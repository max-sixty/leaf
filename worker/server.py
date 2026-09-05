"""Serve the published examples through Leaf's canonical HTTP handler.

The Cloudflare Worker selects one container filesystem per browser session. This
adapter selects a complete page directory by its clean public route, then hands the
request to the same Handler and EventEndpoint as a locally served Leaf. It owns no
projection, browser state, or event semantics of its own.
"""

from __future__ import annotations

import os
import re
from functools import cache
from pathlib import Path
from urllib.parse import urlsplit

from leaf.event_endpoint import EventEndpoint
from leaf.hosting import server_at
from leaf.http import Handler, canonical_script_offset
from leaf.registry.storage import layer_metadata
from leaf.server import preview_metadata

PORT = 8080
EXAMPLE_PRESENTATION = {"install_url": "/#install"}
EXAMPLE_ROUTE = re.compile(r"^/examples/(?P<slug>[a-z0-9-]+)(?P<inside>/.*)?$")


@cache
def page_binding(page_dir: Path) -> tuple[EventEndpoint, dict, str, dict | None]:
    """Read immutable delivery metadata once per published page and process."""
    return (
        EventEndpoint(page_dir),
        layer_metadata(page_dir),
        (page_dir / "runtime" / "bootstrap.js").read_text(encoding="utf-8"),
        preview_metadata(page_dir),
    )


def with_sitenote(document: bytes, page_root: str) -> bytes:
    """Insert website chrome at the canonical runtime boundary."""
    source = document.decode()
    offset = canonical_script_offset(source)
    site_script = (
        f'<script type="module" src="{page_root}/sitenote.js" data-lf-site></script>'
    )
    return (source[:offset] + site_script + source[offset:]).encode()


class WebsiteExampleHandler(Handler):
    """Bind a clean website route to one initialized page directory."""

    examples_root: Path
    sitenote: bytes
    protocol_version = "HTTP/1.1"
    layer = ""

    def authorized(self) -> bool:
        # The outer Worker has already selected this browser's isolated container.
        return True

    def _send(self, status: int, ctype: str, body: bytes) -> None:
        if status == 200 and ctype.startswith("text/html"):
            body = with_sitenote(body, self.page_root)
        super()._send(status, ctype, body)

    def _get(self) -> None:
        if urlsplit(self.path).path == "/sitenote.js":
            self._send(200, "text/javascript; charset=utf-8", self.sitenote)
            return
        super()._get()

    def _select_page(self) -> bool:
        external = urlsplit(self.path)
        match = EXAMPLE_ROUTE.fullmatch(external.path)
        if match is None:
            return False
        page_dir = self.examples_root / match.group("slug")
        if not (page_dir / "events.jsonl").is_file():
            return False

        endpoint, identity, bootstrap, preview = page_binding(page_dir)
        self.page_dir = page_dir
        self.event_endpoint = endpoint
        self.layer = identity["generation"]
        self.layer_identity = identity
        self.bootstrap = bootstrap
        self.preview = preview
        self.example = EXAMPLE_PRESENTATION
        self.page_root = f"/examples/{match.group('slug')}"
        inside = match.group("inside") or "/"
        self.path = inside + (f"?{external.query}" if external.query else "")
        return True

    def _not_found(self) -> None:
        # An unread POST body makes an HTTP/1.1 connection unsafe to reuse.
        if self.command == "POST":
            self.close_connection = True
        self._json({"error": "not found"}, 404)

    def _select_or_answer(self) -> bool | None:
        try:
            return self._select_page()
        except Exception as error:  # noqa: BLE001 - outer HTTP route boundary
            if self.command == "POST":
                self.close_connection = True
            try:
                self._json({"error": f"{type(error).__name__}: {error}"}, 500)
            except OSError:
                pass
            return None

    def do_GET(self) -> None:
        if urlsplit(self.path).path == "/health":
            self._send(200, "text/plain; charset=utf-8", b"ok\n")
            return
        selected = self._select_or_answer()
        if selected is None:
            return
        if not selected:
            self._not_found()
            return
        super().do_GET()

    def do_POST(self) -> None:
        selected = self._select_or_answer()
        if selected is None:
            return
        if not selected:
            self._not_found()
            return
        super().do_POST()


def handler_for(examples_root: Path) -> type[WebsiteExampleHandler]:
    """Make one process handler over the page directories in a site build."""
    root = examples_root.resolve()
    return type(
        "PublishedExampleHandler",
        (WebsiteExampleHandler,),
        {
            "examples_root": root,
            "sitenote": (root.parent / "sitenote.js").read_bytes(),
        },
    )


def main() -> None:
    site_root = Path(os.environ.get("LEAF_SITE_ROOT", "/app/site"))
    httpd = server_at("0.0.0.0", PORT, handler_for(site_root / "examples"))
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
