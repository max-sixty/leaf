"""Tests scheduled by the measured cost of their boundary."""

import re

from browser.startup.test_changes_in_place import (
    BETA,
    DELTA,
    PAGE,
    marked_ids,
    revise,
    revised,
)
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    compare_with,
    expect_panel_says,
    open_page,
    panel_field,
    show_changes,
    stamp_page,
    wait_for_revision,
)

from leaf.source.render_checks import rendered


def test_g_V_v_marks_what_changed_since_the_latest_version_and_takes_marks_off(
    browser, serve
):
    """`g V v` compares with the newest version older than the one being read, and
    takes any comparison off again, one another Compare in Versions started included,
    since Versions opens on the version compared with. The field's standing words say the
    comparison, and a notice that none is marked goes as soon as one marks some."""
    url = live_url(serve(PAGE))
    d = serve.page_dir
    page = open_page(browser, url)
    stamp_page(d, revised(PAGE, BETA), "rewrote Beta")
    wait_for_revision(page, 2)
    revise(d, DELTA)
    wait_for_revision(page, 3)
    marked = page.locator("main .lf-ins-block")
    # The arrivals' news passes first, so what follows is the presses' alone.
    expect(panel_field(page)).to_have_attribute("data-lf-says", "status")
    page.keyboard.press("h")
    expect_panel_says(page, "No changes marked")
    # Since v2, not v1: only Delta changed. The field's standing words say the
    # comparison at once, and a listener hears it; no notice repeats them, read once
    # the press has drawn, while its notice's moment still stands.
    show_changes(page)
    expect(page.locator('.lf-change-bar[data-lf-for="d"]')).to_have_count(1)
    assert marked_ids(page) == ["d"]
    rendered(page)
    assert re.match(
        r"1 change since v2 · ", panel_field(page).get_attribute("placeholder") or ""
    ), panel_field(page).get_attribute("placeholder")
    expect(panel_field(page)).to_have_attribute("data-lf-says", "status")
    expect(page.locator(".lf-live")).to_have_text("1 change since v2")
    show_changes(page)
    expect(marked).to_have_count(0)
    # A screen reader hears the marks go.
    expect(page.locator(".lf-live")).to_have_text("Changes hidden")
    expect_panel_says(page, "since v2", says=False)
    compare_with(page, 1)
    page.keyboard.press("Escape")
    expect(marked).to_have_count(2)
    show_changes(page)
    expect(marked).to_have_count(0)
