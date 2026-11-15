"""Captured dependency addresses are independent of the document's public URL."""

import struct
from urllib.parse import quote

from playwright.sync_api import expect
from render_harness import leaf_page, open_page

from leaf.revision_delivery import (
    media_size,
)


def test_a_written_address_decodes_once_when_the_browser_loads_it(
    browser, serve, subtests
):
    """Each spelling an author can write names the one file the browser loads: a module
    whose import escapes a filename, whichever way its script's address is written, and
    an image whose address the browser strips or normalizes."""
    modules = {
        "encoded": ("my 100%20state.mjs", "page/encoded.mjs"),
        "spaced": ("?state.mjs", " \tpage/spa\nced.mjs \t"),
        "backslashed": ("#state.mjs", r"page\backslashed.mjs"),
    }
    source = leaf_page(
        "Written addresses",
        '<h1 id="title">Written addresses</h1>'
        + "".join(f'<p id="{key}">Waiting</p>' for key in modules)
        + '<img id="image-spaced" src=" page/image.svg " alt="Image">'
        + '<img id="image-backslashed" src="page\\image.svg" alt="Image">',
    )
    source = source.replace(
        "</head>",
        "".join(
            f'<script type="module" src="{src}"></script>'
            for _, src in modules.values()
        )
        + "</head>",
    )
    files = {
        "image.svg": '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="7"/>'
    }
    for key, (name, _) in modules.items():
        files[f"{key}.mjs"] = (
            f'import {{ title }} from "./{quote(name, safe="")}"; '
            f'document.getElementById("{key}").textContent = title;'
        )
        files[name] = 'export const title = "Exact file loaded";'
    page = open_page(browser, serve(source, packages=(), page_files=files))
    for key in modules:
        with subtests.test(module=key):
            expect(page.locator(f"#{key}")).to_have_text("Exact file loaded")
    for image in ("image-spaced", "image-backslashed"):
        with subtests.test(image=image):
            expect(page.locator(f"#{image}")).to_have_js_property("naturalWidth", 13)


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
