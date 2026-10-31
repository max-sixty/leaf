"""Sample the leaf mark and its focus ring while the panel folds and unfolds.

    uv run leaf-dev bench-panel-motion

Reports each route's captured frames, intermediate mark positions, missing paint
and greatest mark/ring centre separation. Frame delivery depends on scheduling;
no intermediate positions means the sample cannot judge motion, not a product
failure. Run on a quiet host and compare the reported load. Firefox screencasts
can omit fixed layers (notes/browser-support.md), so this uses Chromium.
"""

import json
import tempfile
from io import BytesIO
from pathlib import Path

import click
from PIL import Image, ImageColor
from playwright.sync_api import expect

from leaf.render_checks import one_frame
from leaf_dev import ROOT
from leaf_dev.arms import load_average, serving_source
from leaf_dev.browser import headless_shell, load, tab
from leaf_dev.panel_paint import ink_box, settled


def sample(page):
    leaf = page.locator(".lf-fp-leaf")
    viewport = page.viewport_size
    readings = []
    for route, action in (
        ("pointer", ".lf-fp-minimize"),
        ("pointer", ".lf-fp-leaf"),
        ("keyboard", "."),
        ("keyboard", "Enter"),
    ):
        if action == ".lf-fp-minimize":
            card = page.locator(".lf-fp-card").bounding_box()
            page.mouse.move(card["x"] + card["width"] - 20, card["y"] + 6)
        if route == "keyboard" and action == ".":
            page.locator(".lf-fp-field leaf-text").click()
            page.keyboard.press("Shift+Tab")
            expect(leaf).to_be_focused()
        colours = leaf.evaluate("""node => ({
          ring: getComputedStyle(node).outlineColor,
          mark: getComputedStyle(node.querySelector('.lf-dot')).backgroundColor
        })""")
        colours = {name: ImageColor.getrgb(value) for name, value in colours.items()}
        before = leaf.bounding_box()
        frames = []
        with page.screencast.start(
            on_frame=lambda frame, frames=frames: frames.append(frame),
            quality=100,
            size=viewport,
        ):
            if route == "keyboard":
                page.keyboard.press(action)
            else:
                page.locator(action).hover()
                page.mouse.down()
                one_frame(page)
                page.mouse.up()
            settled(page)
        after = leaf.bounding_box()
        ends = sorted(box["x"] + box["width"] / 2 for box in (before, after))
        centers, separation = [], []
        missing_mark = missing_ring = 0
        for frame in frames:
            pixels = (
                Image.open(BytesIO(frame["data"]))
                .convert("RGB")
                .crop(
                    (0, viewport["height"] - 70, viewport["width"], viewport["height"])
                )
            )
            mark = ink_box(pixels, colours["mark"])
            missing_mark += mark is None
            if mark is not None:
                center = ((mark[0] + mark[2]) / 2, (mark[1] + mark[3]) / 2)
                centers.append(center[0])
            if route == "keyboard":
                ring = ink_box(pixels, colours["ring"])
                missing_ring += ring is None
                if mark is not None and ring is not None:
                    ring_center = ((ring[0] + ring[2]) / 2, (ring[1] + ring[3]) / 2)
                    separation.append(
                        max(
                            abs(a - b) for a, b in zip(center, ring_center, strict=True)
                        )
                    )
        readings.append(
            {
                "route": route,
                "action": action,
                "frames": len(frames),
                "intermediate_positions": len(
                    {x for x in centers if ends[0] + 2 < x < ends[1] - 2}
                ),
                "missing_mark": missing_mark,
                "missing_ring": missing_ring if route == "keyboard" else None,
                "max_ring_separation_px": max(separation, default=None),
            }
        )
    return readings


@click.command()
def bench_panel_motion():
    """Report sampled fold/unfold paint without a frame-timing pass/fail gate."""
    before = load_average()
    with tempfile.TemporaryDirectory(prefix="leaf-panel-motion-") as directory:
        scratch = Path(directory)
        source = scratch / "fold.html"
        source.write_text(
            '<!doctype html><html lang="en"><head><title>Fold</title></head>'
            '<body><main class="layout-column"><h1 id="title">Fold</h1></main></body></html>'
        )
        with (
            serving_source(ROOT, source, scratch / "served") as address,
            headless_shell() as browser,
            tab(browser, motion="no-preference") as page,
        ):
            load(page, address)
            readings = sample(page)
    click.echo(
        json.dumps(
            {"load_before": before, "load_after": load_average(), "routes": readings}
        )
    )
