"""Keyboard semantic-selection browser journeys."""

import pytest
from leaf import event_log as events_model
from playwright.sync_api import expect
from render_cases_layout import (
    banner_control,
)
from render_cases_navigation import (
    UNDO_PAGE,
)
from render_harness import (
    open_page,
    sending,
    write,
)

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_finger_reaches_the_page_commands_its_keys_reach(browser, serve):
    """Undo, Draw mode, Design mode and search have no key under a finger, so More holds
    each, read off the command's own row, and what a finger does inside one stands on the
    banner's row while it holds. Design mode leaves Leaf's own chrome working, that step
    included."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, serve(UNDO_PAGE), context=context)
    menu = page.locator(".lf-banner-menu")
    row = page.locator(".lf-banner-actions")
    undo_entry = menu.get_by_role(
        "button", name="Undo", exact=True, include_hidden=True
    )
    expect(undo_entry).to_be_disabled()

    with sending(page, "the pick"):
        page.locator("#opt-a").tap()
    expect(page.locator("lf-option[chosen]")).to_have_attribute("id", "opt-a")
    banner_control(page, ".lf-banner-menu .lf-btn:text-is('Undo')")
    expect(undo_entry).to_be_enabled()
    with sending(page, "the withdrawal"):
        undo_entry.tap()
    expect(menu).to_be_hidden()
    expect(page.locator("lf-option[chosen]")).to_have_attribute("id", "opt-b")
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "undo"

    for entry, root, mode, exit_step in (
        ("Draw mode", "html", "data-lf-draw-mode", "Exit Draw mode"),
        ("Design mode", "body", "data-lf-design-mode", "Exit Design mode"),
    ):
        banner_control(page, f".lf-banner-menu .lf-btn:text-is('{entry}')").tap()
        expect(page.locator(root)).to_have_attribute(mode, "")
        step = row.get_by_role("button", name=exit_step, exact=True)
        expect(step).to_be_visible()
        expect(page.locator(".lf-threads-toggle")).to_be_hidden()
        step.tap()
        expect(page.locator(root)).not_to_have_attribute(mode, "")
        expect(step).to_have_count(0)
        expect(page.locator(".lf-threads-toggle")).to_be_visible()
    expect(page.locator(".lf-fab-input")).to_be_hidden()

    # The picker ignores presses on the chrome, so More stays open to a finger while it
    # stands; entering Design mode from there puts the picker away rather than stacking.
    banner_control(page, ".lf-banner-menu .lf-btn:text-is('Select element')").tap()
    cancel = row.get_by_role("button", name="Cancel selection", exact=True)
    expect(cancel).to_be_visible()
    banner_control(page, ".lf-banner-menu .lf-btn:text-is('Design mode')").tap()
    expect(page.locator(".lf-live")).to_contain_text("Exit Design mode leaves.")
    expect(cancel).to_have_count(0)
    expect(page.locator(".lf-target-picker-hint")).to_have_count(0)
    exit_design = row.get_by_role("button", name="Exit Design mode", exact=True)

    # The mode is about what the agent made, so Leaf's own chrome stays a finger's: More
    # opens to a tap, and the panel a design comment's send opens over the whole phone
    # closes to one, where the banner beneath it has gone inert.
    door = page.locator(".lf-banner-more")
    door.tap()
    expect(menu.get_by_role("button", name="Undo", exact=True)).to_be_visible()
    door.tap()
    expect(menu).to_be_hidden()
    page.locator("#h").tap()
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    write(field, "The heading sits too close to the banner.")
    with sending(page, "the design comment"):
        page.locator(".lf-fab-bar .lf-compose-submit").tap()
    assert events_model.read_events(serve.page_dir)[-1]["about"] == "design"
    panel = page.locator(".lf-thread-panel")
    expect(panel).to_be_visible()
    panel.get_by_role("button", name="Close threads").tap()
    expect(panel).to_be_hidden()
    expect(page.locator("body")).to_have_attribute("data-lf-design-mode", "")
    # A finger does not hover, so no name stays where the last tap was.
    expect(page.locator(".lf-inspect")).to_be_hidden()

    # Prose still selects in Design mode. The selection is the nearer gesture, so its step
    # takes the narrowest phone row until the words are let go, and the mode's returns.
    page.set_viewport_size({"width": 320, "height": 700})
    page.locator("#h").evaluate("el => getSelection().selectAllChildren(el)")
    comment = row.get_by_role("button", name="Comment on selection", exact=True)
    expect(comment).to_be_visible()
    expect(exit_design).to_be_hidden()
    page.evaluate("getSelection().removeAllRanges()")
    expect(comment).to_be_hidden()
    exit_design.tap()
    expect(page.locator("body")).not_to_have_attribute("data-lf-design-mode", "")

    # Selecting words reaches only what is on screen; search finds the rest, and its
    # walk stands on the row beside its way out.
    banner_control(page, ".lf-banner-menu .lf-btn:text-is('Search page')").tap()
    box = page.get_by_role("searchbox", name="Search page text")
    expect(box).to_be_focused()
    box.fill("mounts")
    expect(page.locator(".lf-page-search-match")).not_to_have_count(0)
    next_match = row.get_by_role("button", name="Next", exact=True)
    expect(row.get_by_role("button", name="Previous", exact=True)).to_be_visible()
    assert row.evaluate("el => el.scrollWidth <= el.clientWidth"), (
        "search's steps overflow a 320px row"
    )
    next_match.tap()
    expect(page.locator(".lf-live")).to_contain_text("Match 2 of 3")
    # Select takes the match as the selection, whose own step then stands on the row.
    row.get_by_role("button", name="Select", exact=True).tap()
    expect(box).to_be_hidden()
    expect(next_match).to_have_count(0)
    expect(comment).to_be_visible()
    assert page.evaluate("getSelection().toString()") == "mounts"
    page.evaluate("getSelection().removeAllRanges()")
    expect(comment).to_be_hidden()

    # Searching inside a mode puts search's steps on the row in place of the mode's, and
    # the mode's way out returns when search closes.
    banner_control(page, ".lf-banner-menu .lf-btn:text-is('Draw mode')").tap()
    exit_draw = row.get_by_role("button", name="Exit Draw mode", exact=True)
    expect(exit_draw).to_be_visible()
    banner_control(page, ".lf-banner-menu .lf-btn:text-is('Search page')").tap()
    expect(next_match).to_be_visible()
    expect(exit_draw).to_be_hidden()
    expect(row.locator(".lf-btn:visible:not(.lf-banner-more)")).to_have_text(
        ["Select", "Previous", "Next", "Close search"]
    )
    row.get_by_role("button", name="Close search", exact=True).tap()
    exit_draw.tap()
    expect(page.locator("html")).not_to_have_attribute("data-lf-draw-mode", "")
