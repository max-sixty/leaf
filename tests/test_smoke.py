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

    expect(page.locator(".lf-decisions")).to_have_text("Asks 1/2")
    expect(page.locator("#off-workaround-review .lf-pick")).to_have_count(2)
    expect(page.locator("#off-workaround-review .lf-pick").first).to_be_visible()
    expect(page.locator("#off-workaround-approve .lf-pick")).to_have_attribute(
        "aria-checked", "true"
    )
    # A key line with no rows in it is silent: the chrome paints, the console stays
    # clean, and every other everyday assertion holds while no reader can see a key.
    # The boot's own failure is loud and covered by `errors` below, so what is asked
    # for here is the rows — the More control's keycap is static and would show
    # whatever happened. At rest a page shows `c` and `r`.
    expect(page.locator(".lf-keyline .lf-key:not([hidden])")).not_to_have_count(0)

    assert errors == []
    page.close()
