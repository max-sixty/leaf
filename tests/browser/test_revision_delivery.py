"""Captured dependency addresses are independent of the document's public URL."""

import struct

import pytest
from leaf.revision_delivery import (
    media_size,
)
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
    assert media_size(b'<svg xmlns="http://www.w3.org/2000/svg"/>') is None
    # An upload is checked by its signature alone, so a file cut short after it is a
    # file delivery still serves.
    assert media_size(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR") is None


def test_a_page_image_keeps_its_file_s_shape_when_its_attributes_misstate_it(
    browser, serve
):
    """An image's width and height attributes hold its room before it loads, and an
    agent types them by hand, so a pair copied from another capture once stretched a
    600 by 300 capture to its neighbour's shape. Delivery reads the file's own size,
    so the image draws at that shape, at the attribute's width or squeezed to a
    phone's column."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Captures",
                f'<h1>Captures</h1><img id="misstated" src="{SHOT_SRC["before"]}"'
                ' width="500" height="400" alt="A panel">',
            ),
            media={SHOT_SRC["before"]: SHOTS["before"]},
        ),
    )
    image = page.locator("#misstated")
    for width in (1200, 390):
        page.set_viewport_size({"width": width, "height": 800})
        box = image.bounding_box()
        assert box["width"] <= 500
        assert box["width"] / box["height"] == pytest.approx(2, abs=0.02), (width, box)
