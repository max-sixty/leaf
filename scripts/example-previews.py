#!/usr/bin/env python3
"""Regenerate the public catalog's stills from the live example routes.

The public gallery shows a real first viewport for each example, but the site build
deliberately needs no browser. These JPEGs live in max-sixty/leaf-assets so binary
history does not ship with Leaf. This command captures them through the website's Leaf
server, publishes the asset commit, updates Leaf's exact pin and catalog links, then
rebuilds the site from the pinned bytes.

Usage: wt refresh-previews
"""

import hashlib
import importlib.util
import io
import json
import re
import subprocess
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from example_assets import specification
from leaf.hosting import server_at
from PIL import Image
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
LOCK = ROOT / "example-previews.lock"
VIEWPORT = {"width": 1120, "height": 700}
OUTPUT_SIZE = (896, 560)
REQUIRED_FONTS = {
    ".sitenote p": ".SF NS",
    ".lede": "Charter",
}
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
_server_spec = importlib.util.spec_from_file_location(
    "website_server", ROOT / "worker" / "server.py"
)
website_server = importlib.util.module_from_spec(_server_spec)
_server_spec.loader.exec_module(website_server)


@contextmanager
def serve_examples(site: Path) -> Iterator[str]:
    """Host a built site's examples through the production route adapter."""
    website_server.page_binding.cache_clear()
    server = server_at("127.0.0.1", 0, website_server.handler_for(site / "examples"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def require_capture_fonts(page: Page) -> None:
    """Refuse a host whose fallbacks would redefine the checked-in image corpus."""
    session = page.context.new_cdp_session(page)
    try:
        session.send("DOM.enable")
        session.send("CSS.enable")
        document = session.send("DOM.getDocument")["root"]["nodeId"]
        missing = {}
        for selector, required in REQUIRED_FONTS.items():
            node = session.send(
                "DOM.querySelector", {"nodeId": document, "selector": selector}
            )["nodeId"]
            actual = {
                font["familyName"]
                for font in session.send(
                    "CSS.getPlatformFontsForNode", {"nodeId": node}
                )["fonts"]
            }
            if required not in actual:
                missing[selector] = {"required": required, "actual": sorted(actual)}
    finally:
        session.detach()
    if missing:
        raise RuntimeError(
            "catalog previews require the macOS Charter and San Francisco fonts; "
            f"rendered fonts were {missing}"
        )


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


def run(*args: str, cwd: Path) -> str:
    """Run a Git command and keep its failure attached to the operation."""
    completed = subprocess.run(
        args, cwd=cwd, check=False, capture_output=True, text=True
    )
    if completed.returncode:
        output = f"{completed.stdout}{completed.stderr}".strip()
        raise RuntimeError(f"{' '.join(args)} failed:\n{output}")
    return completed.stdout.strip()


def stage(captures: dict[str, bytes], staging: Path) -> Path:
    """Put the complete preview set in a fresh checkout for verification."""
    repository, _ = specification()
    checkout = staging / "leaf-assets"
    run(
        "git",
        "clone",
        f"https://github.com/{repository}.git",
        str(checkout),
        cwd=staging,
    )
    previews = checkout / "examples"
    previews.mkdir(exist_ok=True)
    for stale in previews.glob("example-*.jpg"):
        if stale.name not in captures:
            stale.unlink()
    for name, content in captures.items():
        (previews / name).write_bytes(content)
    return checkout


def publish(checkout: Path) -> str:
    """Commit and push a verified preview set, then update Leaf's exact pin."""
    repository, _ = specification()
    run("git", "add", "-A", cwd=checkout)
    if run("git", "status", "--porcelain", cwd=checkout):
        run("git", "commit", "-m", "Refresh generated example previews", cwd=checkout)
        run("git", "push", cwd=checkout)
    revision = run("git", "rev-parse", "HEAD", cwd=checkout)
    LOCK.write_text(
        json.dumps({"repository": repository, "revision": revision}, indent=2) + "\n",
        encoding="utf-8",
    )
    return revision


def main() -> None:
    # The first build may be the one creating previews that the catalog already names.
    # Its other links still resolve; the ordinary verified rebuild below checks all of
    # them once the new bytes exist.
    captures: dict[str, bytes] = {}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            site_build.build(site_build.OUT, verify_links=False, browser=browser)
            with serve_examples(site_build.OUT) as origin:
                page = browser.new_page(viewport=VIEWPORT, color_scheme="light")
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                for source in site_build.worked_example_sources():
                    errors.clear()
                    page.goto(f"{origin}/examples/{source.stem}/", wait_until="load")
                    page.wait_for_function(READY)
                    if not captures:
                        require_capture_fonts(page)
                    png = page.screenshot(animations="disabled", caret="hide")
                    image = Image.open(io.BytesIO(png)).convert("RGB")
                    image = image.resize(OUTPUT_SIZE, Image.Resampling.LANCZOS)
                    target = f"example-{source.stem}.jpg"
                    output = io.BytesIO()
                    image.save(
                        output, "JPEG", quality=82, optimize=True, progressive=True
                    )
                    if errors:
                        raise RuntimeError(f"{source.name}: {errors[:3]}")
                    captures[target] = output.getvalue()

            with tempfile.TemporaryDirectory(prefix="leaf-assets-") as raw:
                checkout = stage(captures, Path(raw))
                previews = set((checkout / "examples").glob("example-*.jpg"))
                update_catalog(previews)
                site_build.build(
                    site_build.OUT,
                    browser=browser,
                    catalog_previews=checkout / "examples",
                )
                revision = publish(checkout)
                print(f"  max-sixty/leaf-assets@{revision}")
        finally:
            browser.close()
    print(f"✓ {len(site_build.worked_example_sources())} previews")


if __name__ == "__main__":
    main()
