"""Read the leaf mark and its focus outline from captured pixels, and sample them while
the floating panel folds and unfolds.

Geometry alone misses clipping and compositor paint defects. The floating panel's
settled check (`tests/browser/test_render_floating_panel.py`) reads these colour bounds
once the motion ends. `run` is a probe journey that reads them from each frame
Chromium's screencast delivers while the panel folds and unfolds by pointer and by
keyboard:

    uv run leaf-dev probe SOURCE --journey dev/leaf_dev/panel_paint.py [--base]

It makes the page's own content transparent, so on any SOURCE only the panel's pixels
count, and returns, for each route, the frames captured, how many distinct mark positions fell
between the two resting places, the frames missing the mark or the ring, and the
greatest distance between the mark's centre and the ring's, with the load average
before and after. Frame delivery depends on scheduling: no intermediate positions
means the sample cannot judge the motion, not that the product failed. Run it on a
quiet host and compare the reported load. Firefox screencasts can omit fixed layers
(notes/browser-support.md), so keep probe's default Chromium.
"""

from io import BytesIO

from PIL import Image, ImageChops, ImageColor
from playwright.sync_api import expect

from leaf.render_checks import one_frame, rendered


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
    """Fold and unfold the panel by each route under the screencast, and read the mark
    and its ring from every frame."""
    from leaf_dev.arms import load_average

    before = load_average()
    # Authored ink can share the mark's or the ring's colour. The chrome stands beside
    # the body, so a transparent body leaves only the panel's paint.
    page.evaluate("() => { document.body.style.opacity = '0'; }")
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
          mark: getComputedStyle(node.querySelector('svg[data-lf-icon=leaf]')).color
        })""")
        colours = {name: ImageColor.getrgb(value) for name, value in colours.items()}
        start = leaf.bounding_box()
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
        end = leaf.bounding_box()
        ends = sorted(box["x"] + box["width"] / 2 for box in (start, end))
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
    return {"load_before": before, "load_after": load_average(), "routes": readings}
