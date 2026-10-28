"The floating panel: Leaf's one chrome, a box over the page's foot.\n\nEach test is one journey a user takes through the panel: writing a page comment and replying in the same field, settling the thread, finding\nthreads and taking in news, answering obligations, travelling between versions, and\nfolding the panel to the leaf in the window's corner and back."

import pytest
from browser.test_render_floating_panel import field, floating, settled
from playwright.sync_api import expect
from render_harness import (
    LONG_PAGE,
    open_page,
)


def test_more_room_on_a_phone_keeps_the_panel_its_width(browser, serve):
    """On a phone the panel already spans the window less its gutter, so more room to
    write leaves it as wide as it was. The wider panel's own width named the desktop's
    24px gutter rather than the phone's 20px, so pressing for more room narrowed it."""
    context = browser.new_context(viewport={"width": 390, "height": 800})
    page = open_page(browser, serve(LONG_PAGE), context=context)
    panel = page.locator(".lf-floating-panel")
    expand = page.locator(".lf-fp-row > .lf-fp-expand")
    field(page).click()
    page.keyboard.type("A line of words long enough to wrap in the panel's field, " * 4)
    expect(expand).to_be_visible()
    settled(page)
    narrow = panel.bounding_box()["width"]
    expand.click()
    expect(expand).to_have_attribute("aria-pressed", "true")
    settled(page)
    assert panel.bounding_box()["width"] == pytest.approx(narrow, abs=0.5)


def test_a_long_draft_fades_where_words_run_past_the_field(browser, serve):
    """A draft taller than the field shows no scrollbar, whose overlay flashed with each
    line; its words fade at whichever edge they run past, read from the field's scroll
    rather than a scroll timeline, which Firefox lacks."""
    page = floating(browser, serve(LONG_PAGE))
    field(page).click()
    for line in range(30):
        page.keyboard.type(f"line {line}")
        page.keyboard.press("Shift+Enter")

    def shows(states):
        page.wait_for_function(
            f"() => document.querySelector('.lf-fp-field leaf-text').matches('{states}')"
        )

    expect(field(page)).to_have_css("scrollbar-width", "none")
    shows(":state(more-above):not(:state(more-below))")
    field(page).evaluate("box => box.scrollTop = 0")
    shows(":state(more-below):not(:state(more-above))")
    field(page).evaluate("box => box.scrollTop = 100")
    shows(":state(more-below):state(more-above)")
