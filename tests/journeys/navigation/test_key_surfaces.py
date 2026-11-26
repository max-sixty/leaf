"""The passing words the panel says: news from the user's own act takes the seat from
background news, which comes back once the user's has passed."""

import re

import pytest
from playwright.sync_api import expect
from render_cases_navigation import NOTED_PAGE
from render_harness import (
    expect_panel_says,
    open_page,
    panel_field,
)

from leaf.source.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


def test_user_news_interrupts_and_then_restores_background_news(browser, serve):
    """User news takes the panel's seat for passing words over background news, which
    comes back after it without being announced twice; the live region is retained
    through every change, and the user stays where they stood."""
    page = open_page(browser, serve(NOTED_PAGE))
    page.locator(".lf-fp-leaf").focus()
    page.evaluate(
        """async () => {
          window.__lfStatusNodes = {'.lf-live': document.querySelector('.lf-live')};
          window.__lfNoticeFocus = document.activeElement;
          window.__lfLiveChanges = [];
          new MutationObserver(() => {
            const words = document.querySelector('.lf-live').textContent;
            if (words) window.__lfLiveChanges.push(words);
          }).observe(document.querySelector('.lf-live'), {
            childList: true,
            subtree: true,
          });
          const {notice} = await window.__lfCheckApi();
          notice('Agent replied — open Threads', {background: true});
        }"""
    )
    live = page.locator(".lf-live")
    notice = panel_field(page)
    expect(live).to_have_text("Agent replied — open Threads")
    # The placeholder ends with Comment, and the key that enters the field where keys
    # are shown.
    expect(notice).to_have_attribute(
        "placeholder", re.compile(r"^Agent replied — open Threads · Comment…( c)?$")
    )
    rendered(page)
    assert page.evaluate(
        """() => Object.entries(window.__lfStatusNodes).every(
          ([selector, node]) => document.querySelector(selector) === node
        )"""
    ), "a shared repaint replaced the retained live region"

    page.evaluate("async () => (await window.__lfCheckApi()).notice('Saved')")
    expect(live).to_have_text("Saved")
    expect(notice).to_have_attribute(
        "placeholder", re.compile(r"^Saved · Comment…( c)?$")
    )
    expect(notice).to_have_attribute(
        "placeholder", re.compile(r"^Agent replied — open Threads · Comment…( c)?$")
    )
    assert (
        page.evaluate(
            "() => window.__lfLiveChanges.filter("
            "words => words === 'Agent replied — open Threads').length"
        )
        == 1
    ), "restoring background news announced it again"
    # Go-to takes the seat, so the background news gives way to the sequence's word.
    page.keyboard.press("g")
    expect_panel_says(page, "Agent replied — open Threads", says=False)
    assert page.evaluate(
        """() => Object.entries(window.__lfStatusNodes).every(
          ([selector, node]) => document.querySelector(selector) === node
        ) && document.activeElement === window.__lfNoticeFocus"""
    ), "notice transitions replaced the live region or moved the user"
