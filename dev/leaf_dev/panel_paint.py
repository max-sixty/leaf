"""Read the leaf mark and its focus outline from captured pixels, and sample them while
the floating panel folds and unfolds.

Geometry alone misses clipping and compositor paint defects. The floating panel's
settled check (`tests/browser/test_render_floating_panel.py`) reads these colour bounds
once the motion ends. `run` is a probe journey that reads them from each frame
Chromium's screencast delivers while the panel folds and unfolds by pointer and by
keyboard:

    uv run leaf-dev probe SOURCE --journey dev/leaf_dev/panel_paint.py [--base]

It returns, for each route, the frames swapped between its input and the end of its
motion, how many distinct mark positions fell between the two resting places, the
frames missing the mark or the ring, and the greatest distance between the mark's
centre and the ring's, with the load average before and after. It makes the page's own
content transparent, so the page's ink can't pass for the mark or the ring on any
SOURCE. Leaf's chrome stays painted, so chrome near the window's foot in the mark's or
the ring's colour, such as a margin marker, reads as part of them.

Frame delivery depends on scheduling: no intermediate positions means the sample
cannot judge the motion, not that the product failed. Run it on a quiet host and
compare the reported load. Firefox screencasts can omit fixed layers
(notes/browser-support.md), so keep probe's default Chromium.
"""

import time
from io import BytesIO

from PIL import Image, ImageChops, ImageColor
from playwright.sync_api import expect

from leaf.render_checks import one_frame, rendered

ROUTES = (
    ("pointer", ".lf-fp-minimize"),
    ("pointer", ".lf-fp-leaf"),
    ("keyboard", "."),
    ("keyboard", "Enter"),
)


def settled(page):
    """Wait until layout has started the panel's motion and that motion has finished,
    so a box read is where it rests."""
    rendered(page)
    page.wait_for_function(
        "() => ['.lf-floating-panel', '.lf-fp-ground'].every(s =>"
        " !document.querySelector(s).getAnimations({subtree: true}).some(a =>"
        " Number.isFinite(a.effect?.getComputedTiming().endTime)))"
    )


def ink_box(image, colour):
    difference = ImageChops.difference(image, Image.new("RGB", image.size, colour))
    channels = [
        channel.point(lambda value: 255 if value < 30 else 0)
        for channel in difference.split()
    ]
    return ImageChops.darker(ImageChops.darker(*channels[:2]), channels[2]).getbbox()


def run(page):
    """Fold and unfold the panel by each route under one screencast, and read the mark
    and its ring from the frames each route's input painted."""
    from leaf_dev.arms import load_average

    before = load_average()
    # Authored ink can share the mark's or the ring's colour. The chrome stands beside
    # the body, so a transparent body leaves only Leaf's chrome painted.
    page.evaluate("() => { document.body.style.opacity = '0'; }")
    leaf = page.locator(".lf-fp-leaf")
    viewport = page.viewport_size
    frames, routes = [], []
    # A screencast's first frame can show the page from before it started, stamped
    # with its start, so one screencast spans every route, and each route reads the
    # frames swapped from its input until its motion settled.
    with page.screencast.start(
        on_frame=lambda frame: frames.append(frame), quality=100, size=viewport
    ):
        for route, action in ROUTES:
            if action == ".lf-fp-minimize":
                card = page.locator(".lf-fp-card").bounding_box()
                page.mouse.move(card["x"] + card["width"] - 20, card["y"] + 6)
            if route == "keyboard" and action == ".":
                page.locator(".lf-fp-field leaf-text").click()
                page.keyboard.press("Shift+Tab")
                expect(leaf).to_be_focused()
            # What the setup drew, such as the field's focus outline, rests before
            # the route's clock starts.
            settled(page)
            colours = leaf.evaluate("""node => ({
              ring: getComputedStyle(node).outlineColor,
              mark: getComputedStyle(node.querySelector('svg[data-lf-icon=leaf]')).color
            })""")
            start = leaf.bounding_box()
            began = time.time() * 1000
            if route == "keyboard":
                page.keyboard.press(action)
            else:
                page.locator(action).hover()
                page.mouse.down()
                one_frame(page)
                page.mouse.up()
            settled(page)
            window = (began, time.time() * 1000)
            routes.append(
                (route, action, colours, (start, leaf.bounding_box()), window)
            )
        # Frames reach Python after their swap, and stopping drops any still on the
        # way, so wait for the last ones before the screencast stops.
        page.wait_for_timeout(1500)
    return {
        "load_before": before,
        "load_after": load_average(),
        "routes": [
            reading(
                viewport,
                route,
                action,
                colours,
                boxes,
                [f for f in frames if began <= f["timestamp"] <= ended],
            )
            for route, action, colours, boxes, (began, ended) in routes
        ],
    }


def reading(viewport, route, action, colours, boxes, frames) -> dict:
    """What `frames` show of the mark between its resting places in `boxes` and, on a
    keyboard route, of its ring."""
    colours = {name: ImageColor.getrgb(value) for name, value in colours.items()}
    ends = sorted(box["x"] + box["width"] / 2 for box in boxes)
    centers, separation = [], []
    missing_mark = missing_ring = 0
    for frame in frames:
        pixels = (
            Image.open(BytesIO(frame["data"]))
            .convert("RGB")
            .crop((0, viewport["height"] - 70, viewport["width"], viewport["height"]))
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
                    max(abs(a - b) for a, b in zip(center, ring_center, strict=True))
                )
    return {
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
