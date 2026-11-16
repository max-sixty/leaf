"""Tests scheduled by the measured cost of their boundary."""

import pytest
from browser.controls.test_status_and_news import LEAVES
from interact_support import declare, declare_work, end_work
from playwright.sync_api import expect
from render_harness import (
    LONG_PAGE,
    all_pages_offered,
    expect_preview_words,
    open_page,
    panel_settled,
)

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_panel_row_follows_its_pages_status_live(
    browser, serve, other_leaf, tmp_path
):
    """All pages is a status surface, not a snapshot: a neighbour's declaration
    changing on disk repaints its row at the next poll, in place, and the row's
    hover follows it, being the same account written where there is room for it
    whole."""
    _, other_dir = other_leaf
    page = open_page(browser, serve(LONG_PAGE))
    all_pages_offered(page)
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    panel_settled(page, view="leaves")
    row = page.locator(f"{LEAVES} a.lf-fp-page")
    expect(row).to_contain_text("running the suite")
    declare_work(other_dir, "recording the demo")
    expect(row).to_contain_text("recording the demo")
    # A neighbour waiting on its own user says so in this seat's shorter words, and
    # in the same term its own status uses: All pages is where a user picks which
    # page to go to. The row's preview holds it whole, since the line ellipsizes at
    # the panel's width, and no part of the row has a title of its own, whose
    # tooltip the browser would show in its place.
    end_work(other_dir)
    declare(other_dir, "waiting")
    expect(row).to_contain_text("Ready")
    expect_preview_words(row, f"The other leaf\n{tmp_path / 'other-work'}\nReady")
    assert row.locator("[title]").count() == 0, (
        "a part of the row carries a tooltip of its own, which wins under the pointer "
        "over the row's whole account"
    )


def test_a_closed_leaf_clears_itself_off_all_pages(browser, serve, other_leaf):
    """A closed leaf leaves All pages on the poll that says so. Its server stays
    up — a persistent one for good — so the row would otherwise stand forever and the
    list a user glances at to find who needs them would become a tally of
    everything that has ever run here. This page's own row never drops — a user
    looking at a closed page is still looking at it — so a list with nothing live left
    on it still says where the user is."""
    _, other_dir = other_leaf
    page = open_page(browser, serve(LONG_PAGE))
    all_pages_offered(page)
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    panel_settled(page, view="leaves")
    view = page.locator(LEAVES)
    rows = view.locator("a.lf-fp-page")
    expect(rows).to_have_count(1)
    rows.first.focus()
    declare(other_dir, "idle")
    expect(rows).to_have_count(0)
    expect(view.locator(".lf-fp-page")).to_contain_text("long")
    assert view.evaluate("view => view.contains(document.activeElement)"), (
        "the leaving row dropped the user out of All pages"
    )
