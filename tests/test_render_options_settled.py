"""Settled-options disclosure and presentation tests."""

import re

import pytest
from leaf import event_log as events_model
from leaf import render_checks as render_checks_model
from playwright.sync_api import expect
from render_support import (
    ASK_SHAPES_PAGE,
    SETTLED_ASK_PAGE,
    SETTLED_PAGE,
    composer_quote,
    live_url,
    open_page,
    page_registry,
    panel_settled,
    round_trip,
    select,
    undo,
)

pytestmark = pytest.mark.nightly


def test_a_reconnected_settled_ask_restores_its_diff_watcher(browser, serve):
    """Moving the widget restores comparison updates without duplicating its row."""
    page, errors = open_page(browser, serve(SETTLED_PAGE))
    page.evaluate("""() => {
        const group = document.getElementById("transport");
        group.remove();
        document.querySelector("main").append(group);
        const insertion = document.createElement("span");
        insertion.className = "lf-ins-block";
        group.querySelector("lf-option").append(insertion);
        document.dispatchEvent(new CustomEvent("lf-comparison"));
    }""")

    expect(page.locator("#transport > .lf-settled")).to_have_count(1)
    expect(page.locator("#transport .lf-settled-diff")).to_have_text("Δ1")
    assert errors == []
    page.close()


def test_settled_options_collapse_without_going_out_of_reach(browser, serve):
    """A settled decision reads as one line and the cards behind it stop spending
    the page's height — but they are hidden, not gone, so everything that used to
    reach them still does: the disclosure opens them, and a comment anchored in
    one opens the group on its way to the passage. A collapse a comment can't see
    through is worse than no collapse at all, because the thread still lists the
    quote and clicking it lands nowhere.

    The line itself is in reach too, which is the harder half: while the group is
    collapsed it is the only place the decision is stated, and it is written into a
    disclosure — chrome, and a control. And naming the card there means the page now
    says the card's lede twice, so the third part asks the one thing that buys: a
    comment made on the card lands on the card.

    Which way the disclosure stands is the row's own expanded state and nothing
    besides: the group's markup is the author's, and opening a settled decision is
    reading rather than editing, so no version and no log has a word to say about
    it.
    """
    page, errors = open_page(
        browser, serve(SETTLED_PAGE, anchored=[("opt-strict", "arrives logged out")])
    )
    group = page.locator("#transport")
    height = "el => Math.round(el.getBoundingClientRect().height)"

    assert errors == []
    collapsed = group.evaluate(height)
    assert page.locator("#transport lf-option:visible").count() == 0
    row = page.locator("#transport .lf-settled")
    assert row.inner_text().startswith("Settled: Lax cookie")
    assert row.get_attribute("aria-expanded") == "false"

    row.focus()
    page.keyboard.press("?")
    page.keyboard.press("?")
    settled_help = page.locator(".lf-help-section").filter(
        has=page.get_by_role("heading", name="In a settled ask", exact=True)
    )
    expect(
        settled_help.get_by_text("Open or close the settled ask", exact=True)
    ).to_have_count(1)
    expect(settled_help).not_to_contain_text(re.compile(r"decision", re.IGNORECASE))
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")

    row.click()
    opened = group.evaluate(height)
    assert page.locator("#transport lf-option:visible").count() == 3
    assert opened > collapsed * 3, (
        f"collapsing saved {opened - collapsed}px of {opened}px — a settled group "
        f"that still costs most of its open height isn't a sweep"
    )
    # Open is the row's own expanded state and nothing else. The group wore an `open`
    # attribute here too, in a namespace its entry closes, which no version carries and
    # no consumer reads — while shallowSigs, whose exclusion list is exactly what no
    # version can assert, counted it as state the author had written. The render gate
    # asks the same of every example and cannot reach this moment: a group arrives
    # closed, and nothing it does opens one.
    assert row.get_attribute("aria-expanded") == "true"
    assert (
        render_checks_model.evaluate_probe(page, "undeclaredAttrs", page_registry(page))
        == []
    ), "opening the group left an attribute on a widget its entry never declared"

    row.click()  # closed again, so the reveal below has something to open

    # While it is closed the row is the decision's only visible statement, so the part of
    # it naming the card has to be quotable — and a drag across it must not toggle the
    # disclosure it lives in, which is the mouseup of that drag.
    title = page.locator("#transport .lf-settled [data-lf-said]")
    box = title.bounding_box()
    y = box["y"] + box["height"] / 2
    select(page, (box["x"] + 2, y), (box["x"] + box["width"] - 2, y))
    expect(page.locator("#lf-composer-quote")).to_have_text("“Settled: Lax cookie”")
    expect(page.locator(".lf-fab-input")).not_to_be_focused()
    assert composer_quote(page)["text"].strip("“”") == "Settled: Lax cookie"
    expect(page.locator("#opt-strict")).to_be_hidden()
    expect(page.locator(".lf-composer")).to_be_visible()
    assert composer_quote(page)["text"].strip("“”") == "Settled: Lax cookie"
    page.keyboard.press("Escape")

    # The row names the chosen card, so the page now says "Lax cookie" twice and both
    # copies are quotable. A comment on the card's own lede has to land on the card —
    # the row comes first in document order, which is where a search on the quote alone
    # would put it.
    #
    # Dropping the selection first is the user's own next move: a press that lands
    # inside a live selection is that selection's, so the row would not open under it.
    page.locator("#lede").click()
    row.click()
    expect(page.locator("#opt-lax")).to_be_visible()
    lede = page.locator("#opt-lax > strong")
    box = lede.bounding_box()
    y = box["y"] + box["height"] / 2
    select(page, (box["x"] + 2, y), (box["x"] + box["width"] - 2, y))
    page.locator(".lf-fab-input").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    page.locator(".lf-composer textarea").fill("which copy is this on?")
    page.keyboard.press("ControlOrMeta+Enter")
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) >= 2")
    assert sorted(
        page.evaluate(
            "() => [...CSS.highlights.get('lf-mark')].map(r => "
            "r.startContainer.parentElement.closest('[id]').id)"
        )
    ) == [
        "opt-lax",
        "opt-strict",
    ], "the comment landed on the summary line rather than the card it was made on"
    row.click()

    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-panel .lf-quote", has_text="arrives logged out").click()
    assert page.locator("#opt-strict").is_visible(), (
        "clicking a thread's quote must open the group holding it"
    )
    page.close()


def test_a_settled_ask_reconciles_added_options_into_its_disclosure(browser, serve):
    """A replayed option stays inside the settled disclosure it belongs to.

    The disclosure's count and controls describe the complete current option set,
    including options reconstructed from the standing action and their later undo.
    """
    page, errors = open_page(browser, serve(SETTLED_ASK_PAGE))
    group = page.locator("#jobs")
    row = group.locator(":scope > .lf-settled")

    row.click()
    field = group.get_by_role("textbox", name="Another option", exact=True)
    field.fill("Insulate the camera battery")
    group.get_by_role("button", name="Add option", exact=True).click()
    round_trip(page)
    added = group.locator(":scope > lf-option[data-lf-added]")
    added_id = added.get_attribute("id")
    expect(added).to_be_visible()

    row.click()
    page.reload(wait_until="load")
    page.wait_for_function(
        "() => document.body.getAttribute('data-lf-presented') === '1'"
    )
    row = group.locator(":scope > .lf-settled")
    expect(row).to_have_attribute("aria-expanded", "false")
    expect(group.locator(":scope > lf-option:visible")).to_have_count(0)
    expect(row.locator(".lf-settled-count")).to_have_text("4 options")
    assert row.get_attribute("aria-controls").split() == [
        "job-mounts",
        "job-heater",
        "job-camera",
        added_id,
    ]

    undo(page)
    expect(group.locator(":scope > lf-option[data-lf-added]")).to_have_count(0)
    expect(row.locator(".lf-settled-count")).to_have_text("3 options")
    assert row.get_attribute("aria-controls").split() == [
        "job-mounts",
        "job-heater",
        "job-camera",
    ]
    assert errors == []
    page.close()


def test_a_printed_page_says_which_option_carries_the_pick(browser, serve):
    """Print drops the dead controls but retains the selected option's check."""
    page, errors = open_page(browser, serve(SETTLED_PAGE))
    row = page.locator("#transport .lf-settled")
    expect(row).to_contain_text("Settled: Lax cookie")
    expect(page.locator(".lf-banner")).to_be_visible()

    pick = page.locator("#opt-lax .lf-pick")
    page.emulate_media(media="print")
    expect(page.locator(".lf-banner")).to_be_hidden()
    expect(row).to_be_hidden()
    expect(pick).to_be_hidden()
    expect(page.locator("#opt-strict .lf-pick")).to_be_hidden()
    after = "el => getComputedStyle(el, '::after').content"
    assert page.locator("#opt-lax").evaluate(after) == '"✓"'
    assert page.locator("#opt-strict").evaluate(after) == "none"
    assert errors == []
    page.close()


def test_a_settled_ask_keeps_its_heading_above_the_answer(browser, serve):
    """A settled answer still follows the authored question, on-page and in a reply."""
    url = serve(ASK_SHAPES_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "claude",
            "revision": 1,
            "text": "And settled in here.",
            "markup": '<lf-ask id="th-done-decision"><h3>Where, again?</h3>'
            '<lf-options id="th-done" choose settled>'
            '<lf-option id="th-redis" chosen><strong>Redis</strong></lf-option>'
            '<lf-option id="th-pg"><strong>Postgres</strong></lf-option>'
            "</lf-options></lf-ask>",
        },
    )
    page, errors = open_page(browser, live_url(url))
    page.keyboard.press("c")
    expect(page.locator(".lf-panel")).to_be_visible()

    top = "el => el.getBoundingClientRect().top"
    for ask, group in (("done-decision", "done"), ("th-done-decision", "th-done")):
        expect(page.locator(f"#{group} .lf-settled")).to_have_count(1)
        question = page.locator(f"#{ask} > :is(h1, h2, h3, h4, h5, h6)").evaluate(top)
        summary = page.locator(f"#{group} .lf-settled").evaluate(top)
        assert question < summary, (
            f"#{group}'s question is drawn at {question:.0f} and its answer at "
            f"{summary:.0f}, so the group states what it settled before what it asked"
        )
    assert errors == []
    page.close()
