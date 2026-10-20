"""Keyboard semantic-selection browser journeys."""

import re

import pytest
from leaf import event_log as events_model
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

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_finger_reaches_the_page_commands_its_keys_reach(browser, serve):
    """Undo, Draw mode, Design mode and search have no key under a finger, so the leaf's
    menu holds each, read off the command's own row. What a finger does inside one
    stands as a step in the panel's row, in the marks' place, while it holds, and the
    way out of each is one ✕ at the row's end. Words a finger selects, in a mode too,
    are quoted in the panel's field, a tap on which comments on them. Design mode
    leaves Leaf's own chrome working, that ✕ included."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, serve(UNDO_PAGE), context=context)
    host = page.locator(PANEL)
    row = page.locator(".lf-fp-row")
    marks = page.locator(".lf-fp-threads")

    def step(name):
        return row.locator(".lf-fp-step").filter(has_text=name)

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

    # Draw mode's Undo stroke is a step, which takes the marks' place; Design mode has
    # none, so its ✕ stands beside the marks.
    for entry, root, mode, exit_name, steps in (
        ("command:draw.mode.enter", "html", "data-lf-draw-mode", "Exit Draw mode", 1),
        (
            "command:design.mode.enter",
            "body",
            "data-lf-design-mode",
            "Exit Design mode",
            0,
        ),
    ):
        panel_control(page, entry, at="annotate").tap()
        expect(page.locator(root)).to_have_attribute(mode, "")
        expect(leave(exit_name)).to_be_visible()
        expect(row.locator(".lf-fp-step")).to_have_count(steps)
        if steps:
            expect(marks).to_be_hidden()
        else:
            expect(marks).to_be_visible()
        leave(exit_name).tap()
        expect(page.locator(root)).not_to_have_attribute(mode, "")
        expect(leave(exit_name)).to_have_count(0)
        expect(marks).to_be_visible()
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
    # quotes the words in the mode's name's place, beside the mode's way out, until the
    # words are let go, and a tap on it comments on them.
    page.set_viewport_size({"width": 320, "height": 700})
    field = panel_field(page)
    page.locator("#h").evaluate("el => getSelection().selectAllChildren(el)")
    comment = selection_field(page)
    expect(comment).to_have_attribute("placeholder", re.compile("^“"))
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
    # walk stands on the row beside its ✕.
    panel_control(page, "command:page.search.open", at="navigate").tap()
    box = page.get_by_role("searchbox", name="Search page text")
    expect(box).to_be_focused()
    box.fill("mounts")
    expect(page.locator(".lf-page-search-match")).not_to_have_count(0)
    next_match = step("Next")
    expect(step("Previous")).to_be_visible()
    assert row.evaluate("el => el.scrollWidth <= el.clientWidth"), (
        "search's steps overflow a 320px row"
    )
    next_match.tap()
    expect(page.locator(".lf-live")).to_contain_text("Match 2 of 3")
    # Select takes the match as the selection, which the panel's field then quotes.
    step("Select").tap()
    expect(box).to_be_hidden()
    expect(next_match).to_have_count(0)
    expect(comment).to_have_attribute("placeholder", "“mounts”")
    assert page.evaluate("getSelection().toString()") == "mounts"
    page.evaluate("getSelection().removeAllRanges()")
    expect(comment).to_be_hidden()

    # Searching inside a mode puts search's steps on the row in place of the mode's, and
    # its ✕ closes search, after which the ✕ leaves the mode.
    panel_control(page, "command:draw.mode.enter", at="annotate").tap()
    exit_draw = leave("Exit Draw mode")
    expect(exit_draw).to_be_visible()
    panel_control(page, "command:page.search.open", at="navigate").tap()
    expect(next_match).to_be_visible()
    expect(exit_draw).to_have_count(0)
    expect(row.locator(".lf-fp-step:visible")).to_have_text(
        ["Select", "Previous", "Next"]
    )
    leave("Close search").tap()
    exit_draw.tap()
    expect(page.locator("html")).not_to_have_attribute("data-lf-draw-mode", "")

    # Picking an element has no `s` under a finger, and selecting words picks no
    # widget, so Annotations holds Select element; its ✕ closes it, and a tap on an
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
