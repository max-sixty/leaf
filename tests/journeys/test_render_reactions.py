"""Reactions: one-press emoji on a passage, an item, or a reply."""

import re

import pytest
from browser.test_render_reactions import hint_code, painted
from playwright.sync_api import expect
from render_cases_layout import MARK
from render_cases_navigation import (
    TARGETS_PAGE,
)
from render_harness import (
    RELEASE_FOCUS,
    open_page,
    sending,
)

from leaf.log import event_log as events_model

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_target_hint_opens_comment_and_a_reaction_seats_only_its_glyph(
    browser, serve
):
    """Keyboard target choosing opens Comment. Choosing a reaction puts an
    element anchor in the log, which paints a glyph seated at the element's first line.
    The returned focus rings the element until focus leaves; the reaction itself
    leaves only its seated glyph, with no wash or persistent contour."""
    page = open_page(browser, serve(TARGETS_PAGE))
    page.keyboard.type(hint_code(page, "#prose", 3))
    bar = page.locator(".lf-fab-bar")
    expect(bar).to_be_visible()
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(bar.locator(".lf-fab-input")).to_be_focused()
    page.keyboard.press("Tab")
    reaction = bar.locator('.lf-react[data-lf-emoji="🎯"]')
    reaction.focus()
    expect(reaction).to_be_focused()
    with sending(page, "the 🎯 reaction"):
        page.keyboard.press("Space")
    sent = events_model.read_events(serve.page_dir)[-1]
    assert sent["emoji"] == "🎯" and sent["anchor"] == {"section": "prose"}
    shown = painted(page, [["prose", "🎯"]])
    assert shown["washed"] == "", shown
    expect(page.locator("#prose")).to_be_focused()
    prose = page.locator("#prose")
    expect(prose).to_have_attribute("data-lf-mark", re.compile(r"\bfocus\b"))
    ring = prose.evaluate(MARK)
    assert ring and ring["style"] == "solid" and not ring["brackets"], ring
    assert shown["projected"] == 1, shown
    page.evaluate(RELEASE_FOCUS)
    expect(page.locator("[data-lf-mark]")).to_have_count(0)
    assert painted(page, [["prose", "🎯"]])["washed"] == ""
