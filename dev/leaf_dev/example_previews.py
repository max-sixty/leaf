"""Regenerate the public catalog's stills from the live example routes.

The public gallery shows a real first viewport for each example, but the site build
deliberately needs no browser. These JPEGs live under `examples/` in
max-sixty/leaf-assets (`leaf_dev.leaf_assets`). This command captures them through the
website's Leaf server with an isolated state home, publishes the asset commit, updates
Leaf's exact pin and catalog links, then rebuilds the site from the pinned bytes. Host
pages are not part of the captured scene.

    uv run leaf-dev refresh-previews    (or `wt refresh-previews`)
"""

import io
import os
import shutil
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import click
import leaf_website
from leaf.hosting import LeafHTTPServer
from leaf.render_checks import wait_until_ready
from PIL import Image
from playwright.sync_api import Page, sync_playwright

from leaf_dev import site as site_build
from leaf_dev.example_data import catalog_sources
from leaf_dev.leaf_assets import pinned_assets, publish, stage

VIEWPORT = {"width": 1120, "height": 700}
# docs/index.html and docs/examples.html reserve this 8:5 box before a preview loads.
OUTPUT_SIZE = (896, 560)
REQUIRED_FONTS = {
    ".lf-status-text": ".SF NS",
    ".lede": "Charter",
}


@contextmanager
def serve_examples(site: Path) -> Iterator[str]:
    """Host the capture scene through the production route adapter in isolation."""
    # As in the demo recorder, the host's open pages are not part of the scene.
    # Isolate their discovery before serving so `All leaves` cannot change the
    # captured banner or expose the host's page titles.
    previous_state_home = os.environ.get("XDG_STATE_HOME")
    with tempfile.TemporaryDirectory(prefix="leaf-preview-state-") as state_home:
        os.environ["XDG_STATE_HOME"] = state_home
        try:
            server = LeafHTTPServer(("127.0.0.1", 0), leaf_website.site_endpoint(site))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                yield f"http://127.0.0.1:{server.server_address[1]}"
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
        finally:
            if previous_state_home is None:
                os.environ.pop("XDG_STATE_HOME")
            else:
                os.environ["XDG_STATE_HOME"] = previous_state_home


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


def bootstrap_assets(target: Path) -> Path:
    """Copy the pinned assets, supplying a preview for every route before newly added
    stills exist."""
    shutil.copytree(pinned_assets(), target)
    previews = target / "examples"
    fallback = next(iter(sorted(previews.glob("example-*.jpg"))), None)
    if fallback is None:
        raise RuntimeError("the pinned asset revision contains no catalog preview")
    for source in catalog_sources():
        preview = previews / f"example-{source.stem}.jpg"
        if not preview.is_file():
            shutil.copy2(fallback, preview)
    return target


@click.command("refresh-previews")
def refresh_previews() -> None:
    """Recapture, publish and repin the catalog previews."""
    captures: dict[str, bytes] = {}

    with (
        tempfile.TemporaryDirectory(prefix="leaf-preview-site-") as raw_site,
        sync_playwright() as playwright,
    ):
        staging = Path(raw_site)
        assets = bootstrap_assets(staging / "assets")
        site = staging / "site"
        site_build.build_examples(site, assets=assets)
        browser = playwright.chromium.launch()
        try:
            with serve_examples(site) as origin:
                page = browser.new_page(viewport=VIEWPORT, color_scheme="light")
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                for source in catalog_sources():
                    errors.clear()
                    page.goto(f"{origin}/examples/{source.stem}/", wait_until="load")
                    wait_until_ready(page)
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
        finally:
            browser.close()

    with tempfile.TemporaryDirectory(prefix="leaf-assets-") as raw:
        checkout = stage("examples", captures, Path(raw))
        site_build.build(site_build.OUT, assets=checkout)
        revision = publish(checkout, "Refresh generated example previews")
        click.echo(f"  max-sixty/leaf-assets@{revision}")
    click.echo(f"✓ {len(catalog_sources())} previews")
