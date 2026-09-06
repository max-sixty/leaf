#!/usr/bin/env python3
"""Regenerate the public catalog's stills from the standalone example routes.

The public gallery shows a real first viewport for each example, but the site build
deliberately needs no browser. These checked-in JPEGs bridge that boundary. Capture
them over HTTP from the built static site, never from the raw example files: that is
the route a visitor receives, including the runtime, site note, seeded log, and data.

Usage: example-previews.py  (writes docs/example-*.jpg, updates the catalog, and rebuilds .tmp/site)
"""

import hashlib
import importlib.util
import io
import re
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from leaf.render_gate.browser import launch_browser
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
VIEWPORT = {"width": 1120, "height": 700}
OUTPUT_SIZE = (896, 560)
READY = (
    "() => document.body.dataset.lfUpgraded === '1'"
    " && document.body.dataset.lfApplied !== undefined"
    " && document.body.dataset.lfPresented === '1'"
)

_spec = importlib.util.spec_from_file_location(
    "leaf_site", ROOT / "scripts" / "site.py"
)
site_build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(site_build)


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def update_catalog(previews: set[Path]) -> None:
    """Point each example card at the content address of its new still."""
    catalog = DOCS / "examples.html"
    markup = catalog.read_text(encoding="utf-8")
    for preview in sorted(previews):
        stem = preview.stem.removeprefix("example-")
        address = hashlib.sha256(preview.read_bytes()).hexdigest()[:16]
        pattern = re.compile(
            rf'(<a class="example-link" href="/examples/{re.escape(stem)}/">\s*'
            rf'<span class="example-preview">\s*<img src=")'
            rf'/media/[0-9a-f]{{16}}\.jpg(")'
        )
        markup, count = pattern.subn(rf"\g<1>/media/{address}.jpg\g<2>", markup)
        if count != 1:
            raise RuntimeError(f"{stem}: expected one catalog preview")
    catalog.write_text(markup, encoding="utf-8")


def main() -> None:
    # The first build may be the one creating previews that the catalog already names.
    # Its other links still resolve; the ordinary verified rebuild below checks all of
    # them once the new bytes exist.
    expected = {
        DOCS / f"example-{source.stem}.jpg" for source in site_build.example_sources()
    }
    update_catalog({preview for preview in expected if preview.is_file()})
    site_build.build(site_build.OUT, verify_links=False)
    handler = partial(Quiet, directory=str(site_build.OUT))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_address[1]}"
    previews = set()

    try:
        with sync_playwright() as playwright:
            browser, _ = launch_browser(playwright)
            page = browser.new_page(viewport=VIEWPORT, color_scheme="light")
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            for source in site_build.example_sources():
                errors.clear()
                page.goto(f"{origin}/examples/{source.stem}/", wait_until="load")
                page.wait_for_function(READY)
                png = page.screenshot(animations="disabled", caret="hide")
                image = Image.open(io.BytesIO(png)).convert("RGB")
                image = image.resize(OUTPUT_SIZE, Image.Resampling.LANCZOS)
                target = DOCS / f"example-{source.stem}.jpg"
                image.save(target, "JPEG", quality=82, optimize=True, progressive=True)
                if errors:
                    raise RuntimeError(f"{source.name}: {errors[:3]}")
                previews.add(target)
                print(f"  {target.relative_to(ROOT)}")
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

    for stale in set(DOCS.glob("example-*.jpg")) - previews:
        stale.unlink()
        print(f"  removed {stale.relative_to(ROOT)}")
    update_catalog(previews)
    site_build.build(site_build.OUT)
    print(f"✓ {len(site_build.example_sources())} previews")


if __name__ == "__main__":
    main()
