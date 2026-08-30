#!/usr/bin/env python3
"""Regenerate the public catalog's stills from the standalone example routes.

The public gallery shows a real first viewport for each example, but the site build
deliberately needs no browser. These checked-in JPEGs bridge that boundary. Capture
them over HTTP from the built static site, never from the raw example files: that is
the route a visitor receives, including the runtime, site note, seeded log, and data.

Usage: example-previews.py  (writes docs/example-*.jpg and rebuilds .tmp/site)
"""

import hashlib
import importlib.util
import io
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
MANIFEST = DOCS / "example-previews.json"
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


def capture_input_files() -> list[Path]:
    """Every checked-in input that can change a captured standalone page."""
    example_files = [
        path
        for path in (ROOT / "examples").rglob("*")
        if path.is_file()
        and path.name not in {"CLAUDE.md", "corpus.html", "corpus.data.json"}
    ]
    selected = json.loads((ROOT / "examples" / "layer.json").read_text())
    roots = [
        ROOT / "skills" / "leaf" / "assets",
        ROOT / "skills" / "leaf" / "packages" / "default",
        *(ROOT / "skills" / "leaf" / "packages" / name for name in selected),
    ]
    layer_files = [path for root in roots for path in root.rglob("*") if path.is_file()]
    site_files = [
        DOCS / "leaf.js",
        DOCS / "session.js",
        DOCS / "sitenote.js",
        ROOT / "scripts" / "example-previews.py",
        ROOT / "scripts" / "example_data.py",
        ROOT / "scripts" / "site.py",
    ]
    return sorted(set(example_files + layer_files + site_files))


def digest(paths: list[Path]) -> str:
    value = hashlib.sha256()
    for path in paths:
        value.update(path.relative_to(ROOT).as_posix().encode())
        value.update(b"\0")
        value.update(path.read_bytes())
        value.update(b"\0")
    return value.hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    # The first build may be the one creating previews that the catalog already names.
    # Its other links still resolve; the ordinary verified rebuild below checks all of
    # them once the new bytes exist.
    site_build.build(site_build.OUT, verify_links=False)
    handler = partial(Quiet, directory=str(site_build.OUT))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_address[1]}"
    previews = {}

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome")
            page = browser.new_page(viewport=VIEWPORT, color_scheme="light")
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            for source in site_build.example_sources():
                errors.clear()
                page.goto(
                    f"{origin}/examples/{source.stem}/versions/v1.html",
                    wait_until="load",
                )
                page.wait_for_function(READY)
                png = page.screenshot(animations="disabled", caret="hide")
                image = Image.open(io.BytesIO(png)).convert("RGB")
                image = image.resize(OUTPUT_SIZE, Image.Resampling.LANCZOS)
                target = DOCS / f"example-{source.stem}.jpg"
                image.save(target, "JPEG", quality=82, optimize=True, progressive=True)
                if errors:
                    raise RuntimeError(f"{source.name}: {errors[:3]}")
                previews[source.stem] = target
                print(f"  {target.relative_to(ROOT)}")
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

    expected = set(previews.values())
    for stale in set(DOCS.glob("example-*.jpg")) - expected:
        stale.unlink()
        print(f"  removed {stale.relative_to(ROOT)}")
    MANIFEST.write_text(
        json.dumps(
            {
                "inputs_sha256": digest(capture_input_files()),
                "previews": {
                    stem: {
                        "file": path.name,
                        "sha256": file_digest(path),
                        "width": OUTPUT_SIZE[0],
                        "height": OUTPUT_SIZE[1],
                    }
                    for stem, path in sorted(previews.items())
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    site_build.build(site_build.OUT)
    print(f"✓ {len(site_build.example_sources())} previews")


if __name__ == "__main__":
    main()
