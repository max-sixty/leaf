"""Keyboard semantic-selection browser journeys."""

import re

import pytest
from playwright.sync_api import expect
from render_cases_navigation import (
    UNDO_PAGE,
)
from render_harness import (
    PANEL,
    PANEL_THREAD,
    expect_panel_offers,
    open_page,
    panel_control,
    panel_field,
    selection_field,
    sending,
    write,
)

from leaf import event_log as events_model

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_finger_reaches_the_page_commands_its_keys_reach(browser, serve):
    """Undo, Draw mode, Design mode and search have no key under a finger, so the leaf's
    menu holds each, read off the command's own row. Inside one, the panel's row keeps
    its marks, and the way out of each is one ✕ at the row's end. Words a finger selects, in a mode too,
    are quoted in the panel's field, a tap on which comments on them. Design mode
    leaves Leaf's own chrome working, that ✕ included."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, serve(UNDO_PAGE), context=context)
    host = page.locator(PANEL)
    row = page.locator(".lf-fp-row")
    on_me = page.locator(".lf-fp-on-user")

    def leave(name):
        return row.locator(f'.lf-fp-exit[aria-label="{name}"]')

    expect_panel_offers(page, "command:history.undo", offered=False)

    with sending(page, "the pick"):
        page.locator("#opt-a").tap()
    expect(page.locator("lf-option[chosen]")).to_have_attribute("id", "opt-a")
    expect_panel_offers(page, "command:history.undo")
    with sending(page, "the withdrawal"):
        panel_control(page, "command:history.undo").tap()
    expect(host).not_to_have_attribute("data-menu", "")
    expect(page.locator("lf-option[chosen]")).to_have_attribute("id", "opt-b")
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "undo"

    # A mode offers no step of its own: a stroke's undo is on its drawing's composer, so
    # each mode's ✕ stands in the On me mark's seat, and the mark comes back after it.
    for entry, root, mode, exit_name in (
        ("command:draw.mode.enter", "html", "data-lf-draw-mode", "Exit Draw mode"),
        (
            "command:design.mode.enter",
            "body",
            "data-lf-design-mode",
            "Exit Design mode",
        ),
    ):
        panel_control(page, entry, at="annotate").tap()
        expect(page.locator(root)).to_have_attribute(mode, "")
        expect(leave(exit_name)).to_be_visible()
        expect(on_me).to_have_count(0)
        leave(exit_name).tap()
        expect(page.locator(root)).not_to_have_attribute(mode, "")
        expect(leave(exit_name)).to_have_count(0)
        expect(on_me).to_be_visible()
    expect(page.locator(".lf-fab-input")).to_be_hidden()

    panel_control(page, "command:design.mode.enter", at="annotate").tap()
    expect(page.locator(".lf-live")).to_contain_text("Exit Design mode leaves.")
    exit_design = leave("Exit Design mode")

    # The mode is about what the agent made, so Leaf's own chrome stays a finger's: the
    # leaf's menu opens to a tap, and the thread a design comment's send opens in the
    # panel closes to one.
    leaf = page.locator(".lf-fp-leaf")
    leaf.tap()
    expect(
        page.locator(".lf-fp-menu").locator('[data-row="command:history.undo"]')
    ).to_be_visible()
    leaf.tap()
    expect(host).not_to_have_attribute("data-menu", "")
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
    expect(page.locator("body")).to_have_attribute("data-lf-design-mode", "")
    # A finger does not hover, so no name stays where the last tap was.
    expect(page.locator(".lf-inspect")).to_be_hidden()

    # Prose still selects in Design mode. On the narrowest phone row the panel's field
    # names the mode before the quoted words, beside the mode's way out, until the
    # words are let go, and a tap on it comments on them.
    page.set_viewport_size({"width": 320, "height": 700})
    field = panel_field(page)
    page.locator("#h").evaluate("el => getSelection().selectAllChildren(el)")
    comment = selection_field(page)
    expect(comment).to_have_attribute(
        "placeholder", re.compile("^In Design mode · “Undo”")
    )
    expect(exit_design).to_be_visible()
    assert row.evaluate("el => el.scrollWidth <= el.clientWidth"), (
        "the selection's field overflows a 320px row"
    )
    page.evaluate("getSelection().removeAllRanges()")
    expect(comment).to_have_count(0)
    expect(field).to_have_attribute("placeholder", re.compile("^In Design mode"))
    expect(exit_design).to_be_visible()
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
    expect(page.locator("body")).not_to_have_attribute("data-lf-design-mode", "")

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
    # then quotes.
    mark = page.locator(".lf-page-search-match").first.bounding_box()
    page.touchscreen.tap(mark["x"] + mark["width"] / 2, mark["y"] + mark["height"] / 2)
    expect(box).to_be_hidden()
    expect(next_match).to_be_hidden()
    expect(comment).to_have_attribute("placeholder", "Match 2 of 3 · “mounts”")
    assert page.evaluate("getSelection().toString()") == "mounts"
    page.evaluate("getSelection().removeAllRanges()")
    expect(comment).to_be_hidden()

    # Searching inside a mode puts search's ✕ in place of the mode's: it closes search,
    # after which the ✕ leaves the mode.
    panel_control(page, "command:draw.mode.enter", at="annotate").tap()
    exit_draw = leave("Exit Draw mode")
    expect(exit_draw).to_be_visible()
    panel_control(page, "command:page.search.open", at="navigate").tap()
    expect(next_match).to_be_visible()
    expect(exit_draw).to_have_count(0)
    expect(on_me).to_have_count(0)
    leave("Close search").tap()
    exit_draw.tap()
    expect(page.locator("html")).not_to_have_attribute("data-lf-draw-mode", "")

    # Picking an element has no `s` under a finger, and selecting words picks no
    # widget; Annotations holds Comment on an element, whose ✕ closes it, and a tap on an
    # element chooses it for a comment.
    panel_control(page, "command:target.picker.open", at="annotate").tap()
    cancel = leave("Close picker")
    expect(cancel).to_be_visible()
    cancel.tap()
    expect(cancel).to_have_count(0)
    panel_control(page, "command:target.picker.open", at="annotate").tap()
    expect(cancel).to_be_visible()
    page.locator("#note-cli").tap()
    expect(page.locator(".lf-fab-input")).to_be_visible()
    expect(cancel).to_have_count(0)
