"""Tests scheduled by the measured cost of their boundary."""

import pytest
from playwright.sync_api import expect
from render_harness import open_page, resized, scroll_settled

from leaf_dev.example_data import named_source

pytestmark = pytest.mark.shifts_unsurveyed


def test_merge_film_phone_holds_readable_outcomes_and_preserves_them_on_reflow(
    browser, serve
):
    """The same merge story fits a phone without shrinking its labels or losing refs."""
    source = named_source("wt-merge")
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, serve(source), context=context)
    film = page.locator("#merge-film")
    expect(film).to_have_attribute("data-phone", "")
    labels = page.locator(".film-phone svg text")
    sizes = labels.evaluate_all(
        "nodes => nodes.filter(n => n.textContent !== 'fork').map(n => "
        "parseFloat(getComputedStyle(n).fontSize) * n.getScreenCTM().a)"
    )
    assert min(sizes) >= 14
    for _ in range(5):
        page.get_by_role("button", name="Next step", exact=True).tap()
    expect(page.locator("#step-merge")).to_have_attribute("data-now", "")
    # Main and feature now name the same commit; both labels must remain legible.
    refs = page.locator('.film-phone [data-label^="ref "]')
    visible = refs.evaluate_all(
        "nodes => nodes.filter(n=>Number(n.getAttribute('opacity')) >= .3)"
        ".map(n=>({label:n.dataset.label, top:n.getBoundingClientRect().top}))"
    )
    assert {ref["label"] for ref in visible} == {"ref main", "ref feature"}
    assert abs(visible[0]["top"] - visible[1]["top"]) >= 20
    page.locator(".film-settings summary").tap()
    page.locator("input[name=film-flag-ff]").tap()
    expect(page.locator("#step-merge")).to_have_attribute("data-now", "")
    expect(page.locator('.film-phone [data-label="commit cc2c26f"]')).to_be_visible()
    expect(page.locator(".film-phone-latest")).to_contain_text("Merged to main")
    page.locator(".film-settings summary").tap()

    position = page.locator(".film-scrub").input_value()
    resized(page, 1440, 900)
    expect(film).not_to_have_attribute("data-phone", "")
    assert page.locator(".film-scrub").input_value() == position
    expect(page.locator("#step-merge")).to_have_attribute("data-now", "")
    resized(page, 320, 844)
    expect(film).to_have_attribute("data-phone", "")
    assert page.locator(".film-scrub").input_value() == position
    # The focused settings control remains exposed across the round trip.
    expect(page.locator(".film-settings")).to_have_attribute("open", "")
    page.locator("input[name=film-flag-hookFails]").tap()
    page.locator(".film-scrub").focus()
    page.keyboard.press("End")
    expect(page.locator("#step-premerge")).to_have_attribute("data-state", "fail")
    expect(page.locator('.film-phone [data-label="commit e90b4f6"]')).to_be_visible()
    expect(page.locator('.film-phone-tree[data-gone="true"]')).to_have_count(0)
    page.locator("#step-setup button").tap()
    scroll_settled(page)
    assert film.bounding_box()["y"] >= 0
    expect(page.locator(".film-settings")).not_to_have_attribute("open", "")
    expect(page.locator('.film-phone-tree[data-gone="true"]')).to_have_count(0)
    expect(page.locator('.film-phone [data-label="commit b72c9e4"]')).to_be_visible()
    expect(page.locator(".film-play")).to_have_text("Play")
