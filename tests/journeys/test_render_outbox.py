"""Undo, refusal, outbox, and reconciliation tests."""

import re

import pytest
from leaf import event_log as events_model
from playwright.sync_api import expect
from render_cases_navigation import (
    composer_quote,
    pending_text,
)
from render_harness import (
    BOARD_PAGE,
    INLINE_PAGE,
    CutOff,
    _traffic,
    _until,
    banner_control,
    consume_browser_errors,
    expect_banner_control_offered,
    navigate,
    open_page,
    page_comment,
    panel_settled,
    round_trip,
    stamp_page,
    told,
    wait_for_revision,
    write,
)

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_tab_whose_key_is_refused_keeps_its_moves_and_names_the_link(browser, serve):
    """A refused key judges nothing the user did, so it cannot cost them anything.

    A server restarted onto a different key cookie refused every request from a tab
    left open, and the tab folded each refused send as the server's verdict on it: the
    comment came out of its thread and the pick unticked, under a banner that said the
    server was offline and reconnecting when it was up and never would. The tab here
    loses its key the way that one did, from its cookie jar, and opening the printed
    link in another tab is the recourse the banner names, so the moves it held go out
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
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    field = page_comment(page)
    write(field, "Words the server never read")
    field.press("ControlOrMeta+Enter")
    # Retried rather than dropped: the same send goes out again on the outbox's clock.
    with page.expect_response(refused):
        pass
    expect(page.locator(".lf-status-text")).to_have_text(
        "Key refused — open Leaf's link in a new tab"
    )
    expect(page.locator(".lf-notice")).to_contain_text("open Leaf's link in a new tab")
    expect(page.locator(".lf-status-detail")).to_contain_text(
        "Open the link Leaf printed in a new tab"
    )
    expect(page.locator(".lf-thread")).to_contain_text("Words the server never read")
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
    expect(page.locator(".lf-status-text")).not_to_contain_text("Key refused")
    consume_browser_errors(page, "401", "Leaf interaction log rejected")


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
    # the part that still applies — the line and the dispatcher ask one predicate, so
    # a press made before it stands is one the dispatcher refuses.
    expect(stale.locator(".lf-shortcut-bar")).to_contain_text("undo")
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


def test_a_draft_that_outlives_its_passage_returns_with_that_passage(browser, serve):
    """A draft survives the version it was written against even when that version's
    replacement removes its passage. The editor stays available without attaching to
    the rewritten words, and the draft returns to its passage when that version does."""
    url = serve(INLINE_PAGE)
    page = open_page(browser, url)

    page.locator("#p").click(click_count=3)
    page.locator(".lf-fab-input").click()
    write(
        page.locator(".lf-composer leaf-text"),
        "half-written when the version turned over",
    )
    passage = " ".join(page.locator("#p").inner_text().split())
    assert not composer_quote(page)["shown"], "the passage is right here, and marked"

    # Claude ships a version that rewrites the passage out. The page holds still — a
    # draft is mid-composition — and offers the new version as a chip, which the
    # user takes.
    d = serve.page_dir
    rewritten = INLINE_PAGE.replace(
        "A paragraph carrying <strong>bold text</strong> and <em>emphasis</em> inside it,\n"
        "so that a selection across the middle of it lands in more than one text node.",
        "Rewritten, with nothing left of the sentence the draft was about.",
    )
    stamp_page(d, rewritten, "two")
    told(page)
    expect_banner_control_offered(page.locator(".lf-latest-chip"))
    banner_control(page, ".lf-latest-chip").click()
    wait_for_revision(page, 2)
    expect(page).not_to_have_url(re.compile("/versions/"))
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-fab-input")).to_have_js_property(
        "value", "half-written when the version turned over"
    )
    expect(page.locator("#lf-composer-quote")).to_have_text(f"“{passage}”")
    assert pending_text(page) == "", (
        "v2 rewrote the passage and the page marked it anyway"
    )

    # Through the page's own readiness rather than the paragraph's arrival in markup:
    # the restore of an open draft is part of presenting the page, and a gesture made
    # before that is a gesture the user could not have made.
    navigate(page, url)
    page.locator("#p").click(click_count=3)
    expect(page.locator("#lf-composer-quote")).to_have_text(f"“{passage}”")
    expect(page.locator(".lf-fab-input")).to_have_js_property(
        "value", "half-written when the version turned over"
    )
    # The words come back; the user's keyboard does not go with them.
    expect(page.locator(".lf-fab-input")).not_to_be_focused()
    quote = composer_quote(page)
    assert quote["text"] == f"“{passage}”", f"the quote says {quote['text']!r}"
