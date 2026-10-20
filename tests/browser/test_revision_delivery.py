"""Captured dependency addresses are independent of the document's public URL."""

import base64
import io
import struct

import pytest
from leaf import exporting as exporting_model
from leaf.revision_delivery import (
    media_size,
)
from PIL import Image
from render_cases_layout import SHOT_SRC, SHOTS
from render_harness import leaf_page, open_page


def test_delivery_reads_an_image_s_size_as_the_browser_decodes_it(browser):
    """The frame a page lays out for its media is only the images' shape if delivery
    reads the size a browser decodes, so each format a browser encodes here is read
    back against the canvas it was drawn from. A GIF, which no canvas encodes, states
    its size in the same fixed place for every encoder."""
    page = browser.new_page()
    encoded = page.evaluate(
        """async () => {
            const canvas = document.createElement('canvas');
            canvas.width = 321;
            canvas.height = 123;
            canvas.getContext('2d').fillRect(0, 0, 10, 10);
            const bytes = {};
            for (const type of ['image/png', 'image/jpeg', 'image/webp']) {
                const blob = await new Promise((done) => canvas.toBlob(done, type));
                bytes[type] = [...new Uint8Array(await blob.arrayBuffer())];
            }
            return bytes;
        }"""
    )
    assert {kind: media_size(bytes(data)) for kind, data in encoded.items()} == {
        "image/png": (321, 123),
        "image/jpeg": (321, 123),
        "image/webp": (321, 123),
    }
    assert media_size(b"GIF89a" + struct.pack("<HH", 321, 123)) == (321, 123)
    # A phone's portrait photo is stored on its side with an EXIF orientation that
    # turns it upright, and browsers draw it turned.
    photo = io.BytesIO()
    exif = Image.Exif()
    exif[0x0112] = 6
    Image.new("RGB", (321, 123)).save(photo, "JPEG", exif=exif)
    drawn = page.evaluate(
        """async (url) => {
            const image = new Image();
            image.src = url;
            await image.decode();
            return [image.naturalWidth, image.naturalHeight];
        }""",
        "data:image/jpeg;base64," + base64.b64encode(photo.getvalue()).decode(),
    )
    assert media_size(photo.getvalue()) == tuple(drawn) == (123, 321)
    assert media_size(b'<svg xmlns="http://www.w3.org/2000/svg"/>') is None
    # An upload is checked by its signature alone, so a file cut short after it is a
    # file delivery still serves.
    assert media_size(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR") is None


def test_a_page_image_draws_at_its_file_s_size_and_shape(browser, serve, tmp_path):
    """A page image draws at its file's size and shape, so a page gives it no
    attributes. An unmarked capture draws at its pixels, and one named `@2x` at half
    of them, so it stays sharp and as large as it was on the captured screen. A width
    the author gives sizes it, and a height that misstates the file's shape (copied
    from another capture, once) can't stretch it; each holds at a phone's width."""
    twice = SHOT_SRC["before"].replace(".png", "@2x.png")
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Captures",
                f'<h1>Captures</h1><img id="plain" src="{SHOT_SRC["before"]}" alt="A">'
                f'<img id="twice" src="{twice}" alt="B">'
                f'<img id="misstated" src="{SHOT_SRC["before"]}" width="500"'
                ' height="400" alt="C">',
            ),
            media={SHOT_SRC["before"]: SHOTS["before"], twice: SHOTS["before"]},
        ),
    )
    page.set_viewport_size({"width": 1200, "height": 800})
    page.wait_for_function("[...document.images].every((image) => image.complete)")
    sizes = {
        name: page.locator(f"#{name}").bounding_box()
        for name in ("plain", "twice", "misstated")
    }
    assert [(box["width"], box["height"]) for box in sizes.values()] == [
        (600, 300),
        (300, 150),
        (500, 250),
    ], sizes
    page.set_viewport_size({"width": 390, "height": 800})
    for name in ("plain", "misstated"):
        box = page.locator(f"#{name}").bounding_box()
        assert box["width"] < 390
        assert box["width"] / box["height"] == pytest.approx(2, abs=0.02), (name, box)
    # On a 1x screen too, where a browser would read `src` as a 1x candidate, and in
    # an export, which carries the mark as delivery wrote it.
    out = tmp_path / "captures.html"
    exporting_model.cmd_export(serve.page_dir, out, None)
    for scale in (1, 2):
        exported = browser.new_page(device_scale_factor=scale)
        exported.goto(out.as_uri(), wait_until="load")
        assert exported.locator("#twice").bounding_box()["width"] == 300, scale
        exported.close()
