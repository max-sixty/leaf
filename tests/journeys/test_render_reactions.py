"""Reactions: one-press tokens on a passage, an item, or a reply."""

import pytest
from playwright.sync_api import expect
from render_cases_navigation import (
    TARGETS_PAGE,
)
from render_harness import (
    RELEASE_FOCUS,
    open_page,
    sending,
)

from leaf import event_log as events_model

pytestmark = pytest.mark.shifts_unsurveyed

from browser.test_render_reactions import hint_code, painted


def test_a_target_hint_opens_comment_and_a_token_seats_only_its_glyph(browser, serve):
    """Keyboard target choosing opens Comment. Choosing a token puts an
    element anchor in the log, which paints a glyph seated at the element's first line.
    The returned focus rings the element until focus leaves; the reaction adds no
    current-location contour to it."""
    page = open_page(browser, serve(TARGETS_PAGE))
    page.keyboard.type(hint_code(page, "#prose", 3))
    bar = page.locator(".lf-fab-bar")
    expect(bar).to_be_visible()
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(bar.locator(".lf-fab-input")).to_be_focused()
    page.keyboard.press("Tab")
    reaction = bar.locator('.lf-react[data-token="prioritize"]')
    reaction.focus()
    expect(reaction).to_be_focused()
    with sending(page, "the prioritize reaction"):
        page.keyboard.press("Space")
    sent = events_model.read_events(serve.page_dir)[-1]
    assert sent["token"] == "prioritize" and sent["anchor"] == {"section": "prose"}
    shown = painted(page, [["prose", "prioritize"]])
    assert shown["projected"] == 0 and shown["washed"] == "", shown
    expect(page.locator("#prose")).to_be_focused()
    expect(page.locator("#prose")).to_have_attribute("data-lf-focus", "")
    expect(page.locator("#prose")).to_have_css("outline-style", "solid")
    page.evaluate(RELEASE_FOCUS)
    expect(page.locator("#prose")).to_have_css("outline-style", "none")
