"""Tests scheduled by the measured cost of their boundary."""

import pytest
from interact_support import append_command
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import leaf_page, open_page, stamp_page, told, wait_for_revision

from leaf.render_checks import wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed


def test_activity_counts_arrivals_while_closed_and_draws_them_while_open(
    browser, serve
):
    """A closed feed counts what arrives and moves nothing; an open one draws each
    arrival as it comes, with the user kept on the row they were on. The control is a
    button of fixed size, worked here by the keyboard; a tap activates the same
    button."""
    html = leaf_page(
        "History",
        '<h1>History</h1><section id="recent"><h2>Recent</h2>'
        '<lf-activity id="feed"></lf-activity></section><section id="policy">'
        '<h2>Policy</h2><p id="reading">Keep this visible line where it stands.</p></section>',
    )
    url = live_url(serve(html))
    page = open_page(browser, url)
    control = page.locator("#feed .lf-activity-news")
    rows = page.locator("#feed .lf-activity-row")
    line = page.locator("#reading")
    expect(control).to_have_text("Show activity")
    before = line.bounding_box()
    first = append_command(
        serve.page_dir,
        {
            "revision": 1,
            "kind": "comment",
            "author": "user",
            "anchor": {"section": "policy"},
            "text": "First incoming update",
        },
    )
    told(page)
    expect(control).to_have_text("Show activity · 1 new")
    expect(rows).to_have_count(1)
    assert line.bounding_box()["y"] == pytest.approx(before["y"], abs=0.5)
    control.press("Tab")
    page.keyboard.press("Shift+Tab")
    expect(control).to_be_focused()
    control.press("Enter")
    expect(rows).to_have_count(2)
    expect(control).to_have_text("Hide activity")
    page.keyboard.press("Tab")
    focused_row = page.locator("#feed .lf-activity-target:focus")
    expect(focused_row).to_have_count(1)
    held = focused_row.evaluate("node => (window.heldRow = node, node.textContent)")
    trigger = control.bounding_box()
    append_command(
        serve.page_dir,
        {
            "revision": 1,
            "kind": "reply",
            "author": "agent",
            "parent": first["id"],
            "text": "A second arrival with enough words to visibly grow the feed.",
        },
    )
    told(page)
    expect(rows).to_have_count(3)
    expect(rows.first).to_contain_text("A second arrival")
    expect(control).to_have_text("Hide activity")
    assert control.bounding_box() == trigger
    assert page.evaluate("() => document.activeElement === window.heldRow")
    assert focused_row.text_content() == held

    # A revision that replaces the document keeps the feed open and the user on its
    # control.
    original_document = page.evaluate("performance.timeOrigin")
    control.focus()
    expect(control).to_be_focused()
    fresh = html.replace("Keep this visible", "Still keep this visible").replace(
        "</head>", '<script type="module">void 0;</script></head>'
    )
    stamp_page(serve.page_dir, fresh, "Replace executable inputs")
    wait_for_revision(page, 2)
    wait_until_ready(page)
    expect(control).to_have_attribute("aria-expanded", "true")
    assert page.evaluate("performance.timeOrigin") != original_document
    expect(control).to_be_focused()
