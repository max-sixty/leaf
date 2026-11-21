"""Tests scheduled by the measured cost of their boundary."""

import pytest
from browser.projection.test_visual_review import SELECTED, VISUAL_REVIEW_GALLERY
from playwright.sync_api import expect
from render_harness import expect_on_me, open_page, sending, undo

pytestmark = pytest.mark.shifts_unsurveyed


def test_visual_review_cases_are_independent_on_me_obligations(browser, serve):
    """The global work walk reaches hidden cases, and approval answers only that case."""
    page = open_page(browser, serve(VISUAL_REVIEW_GALLERY))
    widget = page.locator("#visual-review-run")
    case = widget.locator(SELECTED)
    count = page.locator(".lf-fp-leaf")
    expect_on_me(page, 3)
    first = "open-mobile-package-catalog"
    second = "keep-mobile-destinations"
    third = "check-desktop-navigation"
    case.get_by_role("checkbox", name="Looks right").focus()
    page.keyboard.press("m")
    expect(case).to_have_attribute("data-lf-datum", second)
    expect(case).to_be_focused()
    page.keyboard.press("m")
    expect(case).to_have_attribute("data-lf-datum", third)
    expect(case).to_be_focused()
    page.keyboard.press("Shift+m")
    expect(case).to_have_attribute("data-lf-datum", second)
    with sending(page, "approve one independent case"):
        page.keyboard.press("a")
    expect(case.get_by_role("checkbox", name="Looks right")).to_be_checked()
    expect_on_me(page, 2)
    undo(page)
    expect_on_me(page, 3)
    expect(case.get_by_role("checkbox", name="Looks right")).not_to_be_checked()

    # The On Me row uses the same destination, even while another case is shown.
    count.click()
    card = page.locator(".lf-fp-on-item").filter(
        has=page.get_by_text("Optional packages get focused destinations", exact=True)
    )
    expect(card).to_be_visible()
    card.get_by_role("button", name="Show", exact=True).click()
    expect(case).to_have_attribute("data-lf-datum", first)
    expect(case).to_be_focused()
    page.keyboard.press("c")
    field = case.locator(".lf-fab-input")
    expect(field).to_be_focused()
    page.keyboard.type("m means mobile")
    expect(field).to_have_js_property("value", "m means mobile")
    expect(case).to_have_attribute("data-lf-datum", first)
    with sending(page, "hand feedback on this case to the agent"):
        page.keyboard.press("Enter")
    expect_on_me(page, 2)
    case.get_by_role("checkbox", name="Looks right").focus()
    page.keyboard.press("m")
    expect(case).to_have_attribute("data-lf-datum", second)
