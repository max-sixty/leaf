"""Where navigation leaves the user: a comparison result's comment destination, the PR
walkthrough's inline diff thread, a thread card that leaves and returns with its anchor,
and addressed and external links."""

import pytest
from journeys.test_render_navigation import go_to_passage
from playwright.sync_api import expect
from render_cases_interaction import (
    WORKSHOP_THREAD_EVENTS,
    WORKSHOP_THREADS_PAGE,
    live_url,
)
from render_harness import (
    expect_comment_notes,
    open_page,
    pane_scroll_behavior,
    resized,
    scroll_settled,
)

from leaf_dev.browser import text_field
from leaf_dev.example_data import named_source

pytestmark = pytest.mark.shifts_unsurveyed


def test_each_comparison_result_keeps_its_own_comment_destination(browser, serve):
    """Each policy owns a separate anchor and pane-local return route."""
    example = named_source("current-proposed-comparison")
    page = open_page(
        browser,
        serve(
            example,
            anchored=[
                (
                    "comparison-current-behavior",
                    "starts its own credential refresh",
                ),
                (
                    "comparison-proposed-behavior",
                    "Other calls in that tab wait for it",
                ),
            ],
        ),
    )
    resized(page, 1600, 700)
    pane_scroll_behavior(page, page.locator("#comparison-current"), "bounded")
    current = page.locator("#comparison-current > :not(header, footer)")
    proposed = page.locator("#comparison-proposed > :not(header, footer)")
    expect(page.locator(".lf-mark-note")).to_have_count(2)
    expect_comment_notes(page, "#comparison-current", 1)
    expect_comment_notes(page, "#comparison-proposed", 1)
    initial_scrolls = page.evaluate("""() => {
        const panes = ["comparison-current", "comparison-proposed"].map(id =>
            document.querySelector(`#${id} > :not(header, footer)`));
        for (const pane of panes) pane.scrollTop = pane.scrollHeight;
        return panes.map(pane => pane.scrollTop);
    }""")
    assert min(initial_scrolls) > 0

    go_to_passage(page, serve.page_dir, "starts its own credential refresh")
    expect(page.locator("#comparison-current-behavior")).to_be_in_viewport()
    scroll_settled(page, "#comparison-current > :not(header, footer)")
    current_after_current = current.evaluate("el => el.scrollTop")
    proposed_after_current = proposed.evaluate("el => el.scrollTop")
    assert current_after_current < initial_scrolls[0]
    assert proposed_after_current == initial_scrolls[1]

    go_to_passage(page, serve.page_dir, "Other calls in that tab wait for it")
    expect(page.locator("#comparison-proposed-behavior")).to_be_in_viewport()
    scroll_settled(page, "#comparison-proposed > :not(header, footer)")
    assert proposed.evaluate("el => el.scrollTop") < proposed_after_current
    assert current.evaluate("el => el.scrollTop") == current_after_current


def test_thread_navigation_lands_after_resizing_an_open_reply(browser, serve):
    """A reply open in a card goes on in the floating panel once the window narrows to a
    phone's, and the walk back lands in the panel's view of the previous thread, with
    its reply in view."""
    page = open_page(
        browser,
        live_url(serve(WORKSHOP_THREADS_PAGE, events=WORKSHOP_THREAD_EVENTS)),
    )
    resized(page, 1280, 720)
    card = page.locator(".lf-margin-preview")
    thread = card.get_by_role("group", name="Thread, Is lunch provided", exact=False)
    # The walk reaches the lunch thread wherever the walk's order puts it.
    for _ in range(3):
        page.keyboard.press("t")
        scroll_settled(page)
        if thread.count() and thread.evaluate("el => el === document.activeElement"):
            break
    expect(thread).to_be_focused()
    page.keyboard.press("t")
    expect(
        card.get_by_role("group", name="Thread, Workshop room photo")
    ).to_be_focused()
    scroll_settled(page)
    page.keyboard.press("Enter")
    expect(text_field(page, name="Reply", exact=True)).to_be_focused()
    resized(page, 390, 844)
    scroll_settled(page)
    expect(card).to_be_hidden()
    reply = page.locator(".lf-fp-field leaf-text")
    expect(reply).to_be_focused()
    page.keyboard.press("Escape")
    page.keyboard.press("Shift+t")
    view = page.locator(".lf-fp-view")
    expect(view).to_be_focused()
    expect(view).to_contain_text("Is lunch provided")
    page.keyboard.press("c")
    expect(reply).to_be_focused()
    scroll_settled(page)
    expect(reply).to_be_in_viewport(ratio=1)
