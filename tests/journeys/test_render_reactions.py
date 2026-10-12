"""Reactions: one-press tokens on a passage, an item, or a reply."""

import re

import pytest
from leaf import event_log as events_model
from playwright.sync_api import expect
from render_cases_interaction import (
    PANEL_PAGE,
)
from render_cases_navigation import (
    TARGETS_PAGE,
)
from render_harness import (
    RELEASE_FOCUS,
    open_page,
    panel_settled,
    resized,
    sending,
)

pytestmark = pytest.mark.shifts_unsurveyed

from browser.test_render_reactions import _thread, hint_code, painted


def test_a_target_hint_opens_comment_and_a_token_seats_only_its_glyph(browser, serve):
    """Keyboard target choosing opens Comment. Choosing a token puts an
    element anchor in the log, which paints a glyph seated at the element's first line.
    The returned focus rings the element until focus leaves; the reaction adds no
    standing contour to it."""
    page = open_page(browser, serve(TARGETS_PAGE))
    page.keyboard.type(hint_code(page, "#prose", 3))
    bar = page.locator(".lf-fab-bar")
    expect(bar).to_be_visible()
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(bar.locator(".lf-fab-input")).to_be_focused()
    page.keyboard.press("Tab")
    with sending(page, "the prioritize reaction"):
        bar.locator('.lf-react[data-token="prioritize"]').click()
    sent = events_model.read_events(serve.page_dir)[-1]
    assert sent["token"] == "prioritize" and sent["anchor"] == {"section": "prose"}
    shown = painted(page, [["prose", "prioritize"]])
    assert shown["projected"] == 0 and shown["washed"] == "", shown
    expect(page.locator("#prose")).to_be_focused()
    expect(page.locator("#prose")).to_have_attribute("data-lf-focus", "")
    expect(page.locator("#prose")).to_have_css("outline-style", "solid")
    page.evaluate(RELEASE_FOCUS)
    expect(page.locator("#prose")).to_have_css("outline-style", "none")


def test_a_reply_s_reactions_keep_their_keys_in_a_covering_threads_panel(
    browser, serve
):
    """At a phone's width the Threads panel covers the page, and the keyboard answers only
    what stands inside it. The reaction mode stood nowhere, so every one of its rows fell
    below the panel's floor: an arrow reached no row, read as a stray key, and closed the
    list the user was walking. The open list is where the mode stands."""
    url = serve(PANEL_PAGE)
    _, reply = _thread(serve.page_dir)
    page = open_page(browser, url)
    resized(page, 390, 844)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-summary").click()
    strip = page.locator(f'.lf-msg[data-mid="{reply}"] .lf-react-strip')
    strip.locator(".lf-react-trigger").click()
    choices = strip.locator(".lf-react-palette > .lf-react")
    expect(choices.nth(0)).to_be_focused()
    page.keyboard.press("ArrowRight")
    expect(choices.nth(1)).to_be_focused()
    expect(strip).to_have_class(re.compile(r"\blf-react-open\b"))
    page.keyboard.press("ArrowLeft")
    expect(choices.nth(0)).to_be_focused()
    page.keyboard.press("Escape")
    expect(strip).not_to_have_class(re.compile(r"\blf-react-open\b"))
    expect(strip.locator(".lf-react-trigger")).to_be_focused()
