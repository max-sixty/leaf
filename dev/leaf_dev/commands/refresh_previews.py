"""Regenerate the public catalog's stills from the live example routes.

The public gallery shows a real first viewport for each example, but the site build
deliberately needs no browser. These JPEGs live under `examples/` in
max-sixty/leaf-assets (`leaf_dev.leaf_assets`). This command captures them through the
website's Leaf server with an isolated state home, builds the site from the draft
assets, whose catalog then names the new stills (`leaf_dev.docs`), then publishes the
asset commit and moves Leaf's exact pin. Host pages are not part of the captured
scene.

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
from PIL import Image
from playwright.sync_api import Page

from leaf.hosting import LeafHTTPServer
from leaf.render_gate.scheme import collect_page_exceptions
from leaf_dev.browser import headless_shell, load, tab
from leaf_dev.commands import site as site_build
from leaf_dev.example_data import catalog_sources
from leaf_dev.leaf_assets import pinned_assets, publish, stage

VIEWPORT = (1120, 700)
# docs/index.html and docs/examples.html reserve this 8:5 box before a preview loads.
OUTPUT_SIZE = (896, 560)
REQUIRED_FONTS = {
    # The floating panel's field, whose empty placeholder says the page's status.
    ".lf-fp-field .lf-compose-placeholder": ".SF NS",
    ".lede": "Charter",
}


@contextmanager
def serve_examples(site: Path) -> Iterator[str]:
    """Host the capture scene through the production route adapter in isolation."""
    # As in the demo recorder, the host's open pages are not part of the scene.
    # Isolate their discovery before serving so `All leaves` cannot change the
    # captured chrome or expose the host's page titles.
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
                thread.join()
                server.server_close()
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
    fallback = min(previews.glob("example-*.jpg"))
    for source in catalog_sources():
        preview = previews / f"example-{source.stem}.jpg"
        if not preview.is_file():
            shutil.copy2(fallback, preview)
    return target


@click.command()
def refresh_previews() -> None:
    """Recapture, publish and repin the catalog previews."""
    captures: dict[str, bytes] = {}

    with (
        tempfile.TemporaryDirectory(prefix="leaf-preview-site-") as raw_site,
        headless_shell() as browser,
    ):
        staging = Path(raw_site)
        assets = bootstrap_assets(staging / "assets")
        site = staging / "site"
        # `serve_examples` runs this checkout's website adapter, which serves only
        # pages at this checkout's page protocol.
        site_build.build_examples(site, site_build.checkout_leaf(), assets=assets)
        with serve_examples(site) as origin, tab(browser, VIEWPORT) as page:
            errors = []
            collect_page_exceptions(page, errors)
            for source in catalog_sources():
                errors.clear()
                load(page, f"{origin}/examples/{source.stem}/")
                if not captures:
                    require_capture_fonts(page)
                png = page.screenshot(animations="disabled", caret="hide")
                image = Image.open(io.BytesIO(png)).convert("RGB")
                image = image.resize(OUTPUT_SIZE, Image.Resampling.LANCZOS)
                target = f"example-{source.stem}.jpg"
                output = io.BytesIO()
                image.save(output, "JPEG", quality=82, optimize=True, progressive=True)
                if errors:
                    raise RuntimeError(
                        f"{source.name}: {'; '.join(map(str, errors[:3]))}"
                    )
                captures[target] = output.getvalue()

    with tempfile.TemporaryDirectory(prefix="leaf-assets-") as raw:
        checkout = stage("examples", captures, Path(raw))
        site_build.build(
            site_build.OUT,
            site_build.prepared_leaf(site_build.OUT),
            assets=checkout.path,
        )
        revision = publish(checkout, "Refresh generated example previews")
        click.echo(f"  max-sixty/leaf-assets@{revision}")
    click.echo(f"✓ {len(catalog_sources())} previews")
