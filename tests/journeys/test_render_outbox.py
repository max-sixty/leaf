"""Undo, refusal, outbox, and reconciliation tests."""

import re

import pytest
from playwright.sync_api import expect
from render_harness import (
    AVAILABLE_COMMANDS,
    BOARD_PAGE,
    INLINE_PAGE,
    PANEL_THREAD,
    CutOff,
    _traffic,
    _until,
    consume_browser_errors,
    http_error_console,
    open_page,
    page_comment,
    panel_menu,
    round_trip,
    told,
    write,
)

from leaf import event_log as events_model

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_tab_whose_key_is_refused_keeps_its_moves_and_names_the_link(browser, serve):
    """A refused key judges nothing the user did, so it cannot cost them anything.

    A server restarted onto a different key cookie refused every request from a tab
    left open, and the tab folded each refused send as the server's verdict on it: the
    comment came out of its thread and the pick unticked, under a status that said the
    server was offline and reconnecting when it was up and never would. The tab here
    loses its key the way that one did, from its cookie jar, and opening the printed
    link in another tab is the recourse the status names, so the moves it held go out
    without the user doing them again."""
    url = serve(INLINE_PAGE)
    context = browser.new_context(viewport={"width": 1200, "height": 900})
    page = open_page(browser, url, context=context)
    context.clear_cookies()

    def refused(response):
        return "/api/event" in response.url and response.status == 401

    pick = page.locator("#opt-a .lf-pick")
    with page.expect_response(refused):
        pick.click()
    field = page_comment(page)
    write(field, "Words the server never read")
    field.press("ControlOrMeta+Enter")
    # Retried rather than dropped: the same send goes out again on the outbox's clock.
    with page.expect_response(refused):
        pass
    leaf = page.locator(".lf-fp-leaf")
    expect(leaf).to_have_attribute(
        "aria-label", "Page menu · This tab lost access — open the link again"
    )
    expect(page.locator(PANEL_THREAD)).to_contain_text("Words the server never read")
    # The leaf's menu says what the user can do about it, and that the tab stays open.
    expect(panel_menu(page).locator(".lf-fp-state")).to_have_text(
        "This tab lost access — open the link again"
        "Keep this tab open so changes made here go through."
    )
    leaf.click()
    expect(pick).to_have_attribute("aria-checked", "true")
    assert len(_traffic(page).pending) == 2
    assert [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "comment"
    ] == []

    open_page(browser, url, context=context)
    round_trip(page)
    logged = events_model.read_events(serve.page_dir)
    assert [e["text"] for e in logged if e["kind"] == "comment"] == [
        "Words the server never read"
    ]
    assert [e["detail"] for e in logged if e["kind"] == "action"] == [
        {"value": ["opt-a"]}
    ]
    expect(pick).to_have_attribute("aria-checked", "true")
    expect(leaf).not_to_have_attribute("aria-label", re.compile("This tab lost access"))
    consume_browser_errors(
        page,
        http_error_console(401),
        "Leaf interaction log rejected",
    )


def test_a_withdrawal_restores_what_still_stands_not_what_stood_then(browser, serve):
    """An undo names a gesture, and what the page owes afterwards is the unit's state
    *now* — the fold minus that gesture — not the state that stood before it at the
    time. The two differ whenever the withdrawn action is no longer the unit's last
    word, which two tabs reach without trying: one presses `z` on the move it knows
    about while the other has already moved the same card past it, and the door takes
    it, recency not being a thing an event can be checked for.

    The tab that hears it then paints the older reading over the move in force. Which
    tab shows the damage is the part worth arranging: the tab that *made* the later
    move painted it itself, so replay never marked it applied and the next poll lays
    it down again, healing the page by luck. A tab that got that move through replay
    has it marked applied and will never lay it down again — so it holds the wrong
    board for the rest of its life, disagreeing with every fresh load of the same
    log."""
    url = serve(BOARD_PAGE)
    order = "#col-todo > lf-card", "e => e.map(c => c.id)"
    stale = open_page(browser, url)
    mover = open_page(browser, url)

    stale.locator("#card-baffle .lf-grip").focus()
    for key in ["Enter", "ArrowRight", "Enter"]:
        stale.keyboard.press(key)
    round_trip(stale)
    expect(mover.locator("#col-done #card-baffle")).to_have_count(1)

    # Hold the first tab's reading of the log where it is, so its `z` names the move
    # it knows about while the second tab moves the same card on past it.
    cut = CutOff().hold(stale)
    # Back to the list it came from and up past its neighbour, which is neither where
    # the first move put it nor where the version wrote it: a second move that landed
    # on the authored placement would make the wrong restore a no-op by luck, and the
    # test would pass on a page doing the wrong thing.
    mover.locator("#card-baffle .lf-grip").focus()
    for key in ["Enter", "ArrowLeft", "ArrowUp", "Enter"]:
        mover.keyboard.press(key)
    round_trip(mover)
    in_force = ["card-baffle", "card-heater"]
    assert mover.eval_on_selector_all(*order) == in_force

    # The tab the damage shows in: it reads the second move off the log rather than
    # making it, so replay has it marked applied and will not lay it down twice.
    heard = open_page(browser, url)
    assert heard.eval_on_selector_all(*order) == in_force

    # Not undo(): the helper ends in round_trip, and this tab's polls are stopped, so
    # what it sends can never come back to it. The offer the helper waits on first is
    # the part that still applies — a press made before the dispatcher takes `z` is one
    # it refuses.
    stale.evaluate(AVAILABLE_COMMANDS)
    stale.wait_for_function(
        "() => window.__lfAvailableCommands()['history.undo']?.includes('z') ?? false"
    )
    stale.keyboard.press("z")
    # The server answering the post is the fact this wait consumes.
    _until(stale, lambda t: t.acked >= 2, "heard the server take the undo")
    cut.restore()
    told(heard)
    told(heard)

    assert heard.eval_on_selector_all(*order) == in_force, (
        "a tab that heard the undo painted the state that stood before the move it "
        "named, over the move that still stands"
    )
    fresh = open_page(browser, url)
    assert fresh.eval_on_selector_all(*order) == in_force, (
        "a tab reading the log fresh disagrees with the tab that heard the undo"
    )
