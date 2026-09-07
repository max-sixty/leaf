"""The real-browser gate the everyday suite keeps."""

from pathlib import Path

import render_support
from leaf.render_gate import version as render_gate_model
from playwright.sync_api import expect

serve = render_support.serve
open_page = render_support.open_page
BOTH_STAMPS = render_support.BOTH_STAMPS
FEATURE_GALLERY = render_support.FEATURE_GALLERY

ROOT = Path(__file__).parent.parent


def test_a_shipped_page_passes_the_real_browser_gate(browser, serve):
    example = ROOT / "examples" / "ship-review.html"
    assert render_gate_model.render_version(browser, serve(example)) == []


def test_ship_review_asks_are_directly_answerable(browser, serve):
    example = ROOT / "examples" / "ship-review.html"
    page, errors = open_page(browser, serve(example))

    expect(page.locator(".lf-asks")).to_have_text("Asks 1/2")
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


def test_contained_gallery_pages_leave_the_outer_reader_standing(browser, serve):
    """Contained Leaf pages neither restore state nor take focus from their holder."""
    page, errors = open_page(browser, serve(FEATURE_GALLERY))
    page.locator(".lf-threads-toggle").click()
    expect(page.locator(".lf-panel")).to_be_visible()

    page.reload(wait_until="load")
    page.wait_for_function(BOTH_STAMPS)
    for example in ("comment", "threads"):
        frame = page.locator(f"#bg-interaction-{example} [data-interaction-frame]")
        expect(frame).to_have_attribute("data-interaction-ready", "")
        expect(frame.content_frame.locator("body")).not_to_have_attribute(
            "data-lf-panel", ""
        )

    expect(page.locator("body")).to_have_attribute("data-lf-panel", "")
    assert page.evaluate("() => document.activeElement?.tagName") != "IFRAME"
    assert errors == []
    page.close()
