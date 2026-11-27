"""Keyboard semantic-selection browser journeys."""

import re

import pytest
from playwright.sync_api import expect
from render_cases_navigation import (
    UNDO_PAGE,
)
from render_harness import (
    DESIGN_LEGEND,
    PANEL,
    expect_design_mode,
    expect_panel_offers,
    open_page,
    panel_control,
    panel_field,
    panel_settled,
    panel_view,
    resized,
    selection_field,
    sending,
    write,
)

from leaf.log import event_log as events_model
from leaf.source.render_checks import rendered
from leaf_dev.browser import PANEL_THREAD

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_finger_reaches_the_page_commands_its_keys_reach(browser, serve):
    """Undo, Draw mode, Design mode and search have no key under a finger, so the leaf's
    menu holds each, read off the command's own row. Inside a mode, the panel's row is
    the mode's: its way out is the ✕ before the leaf, with
    the mode's name beside it, while the field quotes words a finger selects, in a mode
    too; a tap on those comments on them. Search owns the field, so its way out is that
    ✕ too. Design mode leaves Leaf's own chrome working, its way out included."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, serve(UNDO_PAGE), context=context)
    host = page.locator(PANEL)
    row = page.locator(".lf-fp-row")
    leaf = page.locator(".lf-fp-leaf")

    def leave(name):
        return row.locator(f'.lf-fp-exit[aria-label="{name}"]')

    expect_panel_offers(page, "command:history.undo", offered=False)

    with sending(page, "the pick"):
        page.locator("#opt-a").tap()
    expect(page.locator("lf-option[selected]")).to_have_attribute("id", "opt-a")
    expect_panel_offers(page, "command:history.undo")
    with sending(page, "the withdrawal"):
        panel_control(page, "command:history.undo").tap()
    expect(host).not_to_have_attribute("data-lf-open", re.compile("."))
    expect(page.locator("lf-option[selected]")).to_have_attribute("id", "opt-b")
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "undo"
    # The undo reopens the question, since the markup's pick answers nothing, and the
    # leaf opens On Me while it waits. Answering it again leaves the leaf its menu.
    with sending(page, "the second pick"):
        page.locator("#opt-a").tap()

    # A mode offers no step of its own: a stroke's undo is on its drawing's composer, so
    # each mode's way out is the ✕ before the leaf, its name beside it.
    for entry, stands, name in (
        ("command:draw.mode.enter", "html[data-lf-draw-mode]", "Draw"),
        ("command:design.mode.enter", DESIGN_LEGEND, "Design"),
    ):
        panel_control(page, entry, at="annotate").tap()
        expect(page.locator(stands).first).to_be_attached()
        way_out = leave(f"Exit {name} mode")
        expect(way_out).to_be_visible()
        expect(row.locator(".lf-fp-mode")).to_have_text(name)
        expect(leaf).to_be_visible()
        way_out.tap()
        expect(page.locator(stands)).to_have_count(0)
        expect(way_out).to_have_count(0)
        expect(leaf).to_be_visible()
    expect(page.locator(".lf-fab-input")).to_be_hidden()

    panel_control(page, "command:design.mode.enter", at="annotate").tap()
    # A touchscreen hears what the mode does and no key; the ✕ beside its name leaves it.
    expect(page.locator(".lf-live")).to_have_text(
        "Design mode: a click comments on what it lands on — a widget, a control, a picture."
    )
    exit_design = leave("Exit Design mode")

    # The mode is about what the agent made, so Leaf's own chrome stays a finger's: the
    # leaf's menu opens to a tap, and the thread a design comment's send opens in the
    # panel closes to one.
    leaf = page.locator(".lf-fp-leaf")
    leaf.tap()
    expect(
        page.locator(panel_view("menu")).locator('[data-lf-row="command:history.undo"]')
    ).to_be_visible()
    leaf.tap()
    expect(host).not_to_have_attribute("data-lf-open", re.compile("."))
    page.locator("#h").tap()
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    write(field, "The heading sits too close to the top.")
    with sending(page, "the design comment"):
        page.locator(".lf-fab-bar .lf-compose-submit").tap()
    assert events_model.read_events(serve.page_dir)[-1]["about"] == "design"
    thread = page.locator(PANEL_THREAD)
    expect(thread).to_be_visible()
    page.locator(".lf-fp-close").tap()
    expect(thread).to_have_count(0)
    expect_design_mode(page)
    # A finger does not hover, so no name stays where the last tap was.
    expect(page.locator(".lf-inspect")).to_be_hidden()

    # Prose still selects in Design mode. On the narrowest phone row the panel's field
    # quotes the words beside the mode's name and ✕, says the status once they are let
    # go, and a tap on it while they stand comments on them.
    resized(page, 320, 700)
    field = panel_field(page)
    page.locator("#h").evaluate("el => getSelection().selectAllChildren(el)")
    comment = selection_field(page)
    expect(comment).to_have_attribute("placeholder", re.compile("^“Undo”"))
    expect(exit_design).to_be_visible()
    # The row is measured at rest: the panel's parts slide to their new places, past
    # the row's end on the way.
    panel_settled(page, open=False)
    assert row.evaluate("el => el.scrollWidth <= el.clientWidth"), (
        "the selection's field overflows a 320px row"
    )
    page.evaluate("getSelection().removeAllRanges()")
    expect(comment).to_have_count(0)
    expect(field).to_have_attribute("data-lf-says", "status")
    expect(exit_design).to_be_visible()
    panel_settled(page, open=False)
    assert row.evaluate("el => el.scrollWidth <= el.clientWidth"), (
        "the mode's way out overflows a 320px row"
    )
    page.locator("#h").evaluate("el => getSelection().selectAllChildren(el)")
    comment.tap()
    composer = page.locator(".lf-fab-input")
    expect(composer).to_be_focused()
    expect(exit_design).to_be_visible()
    page.keyboard.press("Escape")
    expect(composer).to_be_hidden()
    exit_design.tap()
    expect_design_mode(page, on=False)

    # Selecting words reaches only what is on screen; search finds the rest, and its
    # walk stands in its own box, beside the count, with the box still taking letters.
    panel_control(page, "command:page.search.open", at="navigate").tap()
    box = page.get_by_role("searchbox", name="Search page text")
    expect(box).to_be_focused()
    box.fill("mounts")
    expect(page.locator(".lf-page-search-match")).not_to_have_count(0)
    next_match = row.get_by_role("button", name="Next match")
    expect(row.get_by_role("button", name="Previous match")).to_be_visible()
    assert row.evaluate("el => el.scrollWidth <= el.clientWidth"), (
        "search's steps overflow a 320px row"
    )
    next_match.tap()
    expect(page.locator(".lf-live")).to_contain_text("Match 2 of 3")
    expect(box).to_be_focused()
    # A press on the marked match takes it as the selection, which the panel's field
    # then quotes. The live region says the step on a timer of its own, which can
    # fire before the rendering update that moves the mark onto the match.
    rendered(page)
    mark = page.locator(".lf-page-search-match").first.bounding_box()
    page.touchscreen.tap(mark["x"] + mark["width"] / 2, mark["y"] + mark["height"] / 2)
    expect(box).to_be_hidden()
    expect(next_match).to_be_hidden()
    # The match's position leads the quote only for its step's moment.
    expect(comment).to_have_attribute("placeholder", re.compile("“mounts”$"))
    assert page.evaluate("getSelection().toString()") == "mounts"
    page.evaluate("getSelection().removeAllRanges()")
    expect(comment).to_be_hidden()

    # Searching inside a mode puts search's ✕ in place of the mode's: it closes
    # search, after which the mode's ✕ leaves the mode.
    panel_control(page, "command:draw.mode.enter", at="annotate").tap()
    exit_draw = leave("Exit Draw mode")
    expect(exit_draw).to_be_visible()
    panel_control(page, "command:page.search.open", at="navigate").tap()
    expect(next_match).to_be_visible()
    expect(exit_draw).to_have_count(0)
    expect(leaf).to_be_visible()
    leave("Close search").tap()
    exit_draw.tap()
    expect(page.locator("html")).not_to_have_attribute("data-lf-draw-mode", "")

    # Picking an element has no `s` under a finger, and selecting words picks no
    # widget; Annotations holds Select mode, named beside the ✕ that closes it, and a
    # tap on an element chooses it for a comment.
    panel_control(page, "command:target.picker.open", at="annotate").tap()
    cancel = row.locator(":scope > .lf-fp-exit")
    expect(row.locator(".lf-fp-mode")).to_have_text("Select")
    expect(cancel).to_be_visible()
    cancel.tap()
    expect(cancel).to_have_count(0)
    panel_control(page, "command:target.picker.open", at="annotate").tap()
    expect(cancel).to_be_visible()
    page.locator("#note-cli").tap()
    expect(page.locator(".lf-fab-input")).to_be_visible()
    expect(cancel).to_have_count(0)
