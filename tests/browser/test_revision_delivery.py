"""Captured dependency addresses are independent of the document's public URL."""

import json
import struct
import subprocess
from urllib.parse import quote

import pytest
from conftest import LEAF_COMMAND
from playwright.sync_api import expect
from render_harness import leaf_page, open_page

from leaf.revision_delivery import (
    media_size,
)


@pytest.mark.parametrize(
    ("name", "src"),
    [
        ("my 100%20state.mjs", "page/app.mjs"),
        ("?state.mjs", " \tpage/ap\np.mjs \t"),
        ("#state.mjs", r"page\app.mjs"),
    ],
)
def test_module_filename_decodes_once_when_the_browser_loads_it(
    browser, serve, name, src
):
    source = leaf_page("Module filename", '<h1 id="title">Module filename</h1>')
    source = source.replace(
        "</head>", f'<script type="module" src="{src}"></script></head>'
    )
    url = serve(
        source,
        packages=(),
        page_files={
            "app.mjs": f'import {{ title }} from "./{quote(name, safe="")}"; document.title = title;',
            name: 'export const title = "Exact file loaded";',
        },
    )
    page = open_page(browser, url)
    expect(page).to_have_title("Exact file loaded")


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


@pytest.mark.parametrize("src", [" page/image.svg ", r"page\image.svg"])
def test_image_reference_capture_matches_browser_delivery(browser, serve, src):
    source = leaf_page(
        "Image reference",
        f'<h1 id="title">Image</h1><img id="image" src="{src}" alt="Image">',
    )
    url = serve(
        source,
        packages=(),
        page_files={
            "image.svg": '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="7"/>'
        },
    )
    page = open_page(browser, url)
    expect(page.locator("#image")).to_have_js_property("naturalWidth", 13)


def test_page_code_fetches_a_page_file_nothing_names(browser, serve):
    """A revision holds every file under page/, so a module fetching one by a URL it
    computes draws it, in a served version and under `page check --render`."""
    source = leaf_page(
        "Page data", '<h1 id="title">Page data</h1><p id="message">Waiting</p>'
    )
    source = source.replace(
        "</head>", '<script type="module" src="/page/app.js"></script></head>'
    )
    url = serve(
        source,
        packages=(),
        page_files={
            "app.js": """
const url = new URL("./tables/data.json", import.meta.url);
const response = await fetch(url);
if (!response.ok) throw new Error(`${url}: ${response.status}`);
document.getElementById("message").textContent = (await response.json()).message;
""",
            "tables/data.json": '{"message": "Drawn from page data"}',
        },
    )
    page = open_page(browser, url)
    expect(page.locator("#message")).to_have_text("Drawn from page data")

    checked = subprocess.run(
        [*LEAF_COMMAND, "page", "check", str(serve.page_dir), "--render"],
        capture_output=True,
        text=True,
        check=False,
    )
    report = json.loads(checked.stdout)
    assert report["browser"]["ran"] == ["page code", "render check"], report
    assert [f for f in report["findings"] if f["severity"] == "error"] == []
