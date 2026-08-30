"""The real-browser gate the everyday suite keeps."""

from pathlib import Path

import render_support
from leaf.render_gate import version as render_gate_model
from playwright.sync_api import expect

serve = render_support.serve
open_page = render_support.open_page

ROOT = Path(__file__).parent.parent


def test_a_shipped_page_passes_the_real_browser_gate(browser, serve):
    example = ROOT / "examples" / "ship-review.html"
    assert render_gate_model.render_version(browser, serve(example)) == []


def test_ship_review_asks_are_directly_answerable(browser, serve):
    example = ROOT / "examples" / "ship-review.html"
    page, errors = open_page(browser, serve(example))

    expect(page.locator(".lf-decisions")).to_have_text("Asks (9)")
    for options in ["off-workaround-review", "off-copy-review"]:
        expect(page.locator(f"#{options} .lf-pick")).to_have_count(2)
        expect(page.locator(f"#{options} .lf-pick").first).to_be_visible()

    assert errors == []
    page.close()
