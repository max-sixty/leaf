"""What waits on the user: the `m` queue, the panel's On Me count and its On view,
and tallies."""

import re

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import live_url, panel_comment
from render_harness import (
    PANEL,
    PREVIEW,
    expect_obligations_answered,
    expect_panel_says,
    field_press,
    holding,
    leaf_page,
    open_page,
    panel_settled,
    panel_view,
    resized,
    round_trip,
    scroll_settled,
    sending,
    show_done,
    stamp_page,
    wait_for_revision,
    without_end_room,
    write,
)

from browser.navigation import expect_walk_position, walk_position
from leaf.log import event_log as events_model
from leaf.source.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


# What waits on the user, as On Me counts it (panel/floating-panel.js, `onUserCount`): the
# queue's own reading, since a gesture's next step can stand in the marks' place.
ON_ME = """async () => {
  const {readQueues} = await window.__lfWidgetApi();
  window.__lfOnMe = () => {
    const queues = readQueues();
    return queues.phase === "ready" ? queues.on_user.length : null;
  };
}"""


def expect_on_me(page, count):
    """Wait until On Me counts `count` obligations waiting on the user."""
    page.evaluate(ON_ME)
    page.wait_for_function("count => window.__lfOnMe() === count", arg=count)


QUEUE_PAGE = leaf_page(
    "What waits on you",
    '<h1 id="h">Release</h1><p id="cadence">We publish a build every week.</p>'
    '<lf-group id="channel-ask" label="Which channel first?"><h2 id="channel-ask-h">Which channel first?</h2>'
    '<lf-options id="channel"><lf-option id="beta">Beta first</lf-option>'
    '<lf-option id="both">Both at once</lf-option></lf-options></lf-group>'
    '<p id="notes">Release notes come from merged titles.</p>',
)


def test_m_keeps_its_position_at_a_chrome_stop_without_a_page_target(browser, serve):
    source = leaf_page(
        "Chrome queue stops",
        "<h1>Release</h1><p>Review the release.</p>",
    )
    url = serve(source)
    comment = append_carried_log_record(
        serve.page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Ready?"},
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Agent",
            "parent": comment["id"],
            "responds": comment["id"],
            "revision": 1,
            "text": "Which channel?",
            "obligation": True,
        },
    )
    page = open_page(browser, url)
    page.evaluate("getSelection().removeAllRanges()")
    page.keyboard.press("m")
    rendered(page)
    assert page.evaluate(
        "id => document.activeElement.closest('[data-lf-thread]')?.dataset.lfThread === id",
        comment["id"],
    )
    position = walk_position(page)
    assert position is not None
    assert position["text"] == "1 of 1 waiting on me"


def test_m_walks_what_waits_on_you_and_on_me_counts_it(browser, serve):
    """`m` stops, in page order, at a thread whose question waits on the user as well
    as at an open obligation, and passes a thread waiting on the agent; `t` still walks both
    threads. The panel's leaf counts what waits on the user. A reply the user
    sends takes its thread off that count and out of the walk once the server has read
    the reply."""
    url = serve(QUEUE_PAGE)
    d = serve.page_dir
    asked = append_carried_log_record(
        d,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Weekly?",
            "anchor": {"section": "cadence"},
        },
    )
    question = append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Agent",
            "parent": asked["id"],
            "responds": asked["id"],
            "revision": 1,
            "text": "Weekly or daily?",
            "obligation": True,
        },
    )
    owed = append_carried_log_record(
        d,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Tighten this.",
            "anchor": {"section": "notes"},
        },
    )
    page = open_page(browser, url)

    def counts(you):
        expect_on_me(page, you)

    counts(2)

    thread = page.locator(f'.lf-page-thread[data-lf-thread="{asked["id"]}"]')
    message = thread.locator(f'.lf-msg[data-lf-event="{question["id"]}"]')
    page.keyboard.press("m")
    expect_walk_position(page, "1 of 2 waiting on me")
    expect(message).to_be_focused()
    page.keyboard.press("m")
    expect_walk_position(page, "2 of 2 waiting on me")
    expect(page.locator("#channel-ask")).to_be_focused()
    page.keyboard.press("m")
    expect_walk_position(page, "1 of 2 waiting on me")
    expect(message).to_be_focused()
    page.keyboard.press("Shift+m")
    expect_walk_position(page, "2 of 2 waiting on me")
    expect(page.locator("#channel-ask")).to_be_focused()
    page.keyboard.press("Shift+m")
    expect_walk_position(page, "1 of 2 waiting on me")
    expect(message).to_be_focused()

    page.keyboard.press("Enter")
    box = thread.locator("leaf-text")
    write(box, "Weekly.")
    # The reply is the agent's to answer in the turn it is sent; which question it
    # answers is the server's reading, which takes the thread off the user's count.
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the reply")
    counts(2)
    page.unroute("**/api/event")
    for route in held:
        route.continue_()
    round_trip(page)
    counts(1)
    page.locator("#h").click()
    page.keyboard.press("m")
    expect_walk_position(page, "1 of 1 waiting on me")
    page.locator("#h").click()
    page.keyboard.press("t")
    expect_walk_position(page, "Thread 1 of 2")

    # A follow-up in a thread the agent already owes is still one answer owed: the
    # server owes a thread one answer, to its latest move, so the count holds while the
    # follow-up is in flight and after.
    page.keyboard.press("t")
    expect_walk_position(page, "Thread 2 of 2")
    notes = page.locator(f'.lf-page-thread[data-lf-thread="{owed["id"]}"]')
    expect(notes).to_be_focused()
    page.keyboard.press("Enter")
    write(notes.locator("leaf-text"), "And the second line.")
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the follow-up")
    counts(1)
    page.unroute("**/api/event")
    for route in held:
        route.continue_()
    round_trip(page)
    counts(1)


FILLER = "".join(
    f"<p>Step {i} of the release, written out long enough to wrap onto a second "
    "line at a desktop width.</p>"
    for i in range(14)
)
# Two choices waiting on the user: one the walk can land clear above an open view, and
# one at the page's foot, which no scroll brings above it.
UNDER_PANEL_PAGE = leaf_page(
    "Stops under the panel",
    '<h1 id="h">Release</h1>'
    + FILLER
    + '<lf-group id="mid-ask" label="Which channel first?"><h2 id="mid-ask-h">Which channel first?</h2>'
    '<lf-options id="channel"><lf-option id="beta">Beta first</lf-option>'
    '<lf-option id="both">Both at once</lf-option></lf-options></lf-group>'
    + FILLER
    + '<lf-group id="foot-ask" label="Ship notes with it?"><h2 id="foot-ask-h">Ship notes with it?</h2>'
    '<lf-options id="notes"><lf-option id="yes">Yes</lf-option>'
    '<lf-option id="no">No</lf-option></lf-options></lf-group>'
    '<p id="tail">The notes go out with the build.</p>',
)

# How much of an element the user sees, as the runtime reads it (dom/geometry.js,
# `seenRect`), the open view taken away from what it stands over.
SEEN_SHARE = """async (selector) => {
  const {seenRect} = await window.__lfCheckApi();
  const node = document.querySelector(selector);
  const box = node.getBoundingClientRect();
  const seen = seenRect(node, new Map());
  return seen
    ? ((seen.right - seen.left) * (seen.bottom - seen.top)) / (box.width * box.height)
    : 0;
}"""


def test_the_field_s_end_offers_next_on_me_while_on_me_lists_anything(browser, serve):
    """While anything waits on the user, the panel field's end offers Next On Me with
    `m`, and still does once an answer leaves one item there, the send leaving the user
    on the thread, where `m` walks. With the caret back in the card's reply box, where
    `m` is a letter typed, the field's end shows nothing, and the press and its key
    stand again once the caret leaves. Once nothing is On Me, the field's end offers it
    no more."""
    url = serve(QUEUE_PAGE)
    d = serve.page_dir
    asked = append_carried_log_record(
        d,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Weekly?",
            "anchor": {"section": "cadence"},
        },
    )
    append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Agent",
            "parent": asked["id"],
            "responds": asked["id"],
            "revision": 1,
            "text": "Weekly or daily?",
            "obligation": True,
        },
    )
    page = open_page(browser, url)
    expect_on_me(page, 2)
    press = field_press(page)
    expect(press.locator(".lf-compose-press-word")).to_have_text("Next On Me")
    expect(press.locator("kbd")).to_have_text("m")
    page.keyboard.press("m")
    expect_walk_position(page, "1 of 2 waiting on me")
    page.keyboard.press("Enter")
    thread = page.locator(f'.lf-page-thread[data-lf-thread="{asked["id"]}"]')
    box = thread.locator("leaf-text")
    write(box, "Weekly.")
    with sending(page, "the reply"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect_on_me(page, 1)
    expect(press.locator(".lf-compose-press-word")).to_have_text("Next On Me")
    expect(thread).to_be_focused()
    expect(press.locator("kbd")).to_have_text("m")
    page.keyboard.press("c")
    expect(box).to_be_focused()
    expect(press).to_have_count(0)
    page.locator("h1").click()
    expect(press.locator(".lf-compose-press-word")).to_have_text("Next On Me")
    expect(press.locator("kbd")).to_have_text("m")
    press.click()
    expect(page.locator("#channel-ask")).to_be_focused()

    with sending(page, "the pick"):
        page.locator("#beta").click()
    expect_on_me(page, 0)
    round_trip(page)
    expect(press).to_have_count(0)


def test_travel_puts_away_a_panel_view_standing_over_where_it_lands(browser, serve):
    """Travel shows the place it takes the user to (panel/floating-panel.js, `clearFor`). `m`
    from a thread the panel opened to a place the landing brings clear above the view
    leaves the thread open, and the field names the stop rather than the thread's turn;
    to one at the page's foot, which the view would stand over, it puts the view away."""
    url = serve(UNDER_PANEL_PAGE)
    asked = append_carried_log_record(
        serve.page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Ready?"},
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Agent",
            "parent": asked["id"],
            "responds": asked["id"],
            "revision": 1,
            "text": "Which way should the rollout go first?",
            "obligation": True,
        },
    )
    page = open_page(browser, url)
    # The foot of a page with no room below it, which no scroll lifts clear of a view.
    without_end_room(page)
    resized(page, 1280, 900)
    page.evaluate("getSelection().removeAllRanges()")
    thread = page.locator(panel_view("thread"))

    def lands_whole(selector):
        expect(page.locator(selector)).to_be_focused()
        scroll_settled(page)
        assert page.evaluate(SEEN_SHARE, selector) > 0.99

    for at in (1, 2, 3):
        page.keyboard.press("m")
        expect_walk_position(page, f"{at} of 3 waiting on me")
    panel_settled(page, view="thread")

    page.keyboard.press("m")
    expect_walk_position(page, "1 of 3 waiting on me")
    lands_whole("#mid-ask")
    expect(thread).to_have_count(1)
    expect(page.locator(".lf-fp-field .lf-compose-placeholder-lead")).to_have_text(
        "1 of 3 waiting on me"
    )

    page.keyboard.press("m")
    expect_walk_position(page, "2 of 3 waiting on me")
    panel_settled(page, open=False)
    lands_whole("#foot-ask")


# A choice at the end of a bounded block at the page's foot: landing on it scrolls the
# block and then the page, and no scroll brings it above an open view.
BOUNDED_FOOT_PAGE = leaf_page(
    "A choice in a bounded block",
    '<h1 id="h">Release</h1>'
    + FILLER
    + FILLER
    + '<section id="bounded" data-bound="start" style="height: 220px">'
    + "".join(f"<p>Log line {i} of the bounded block.</p>" for i in range(12))
    + '<lf-group id="bound-ask" label="Ship notes with it?"><h2 id="bound-ask-h">Ship notes with it?</h2>'
    '<lf-options id="bound"><lf-option id="yes">Yes</lf-option>'
    '<lf-option id="no">No</lf-option></lf-options></lf-group></section>'
    '<p id="end">The end.</p>',
)


def test_travel_reads_the_landing_through_every_region_it_scrolls(browser, serve):
    """Whether the open view would cover a destination is read where the whole landing
    leaves it, the page's scroll after its bounded block's included: `m` from a panel
    thread, with the page scrolled back to its top, to a choice at the end of a
    bounded block at the page's foot puts the view away."""
    url = serve(BOUNDED_FOOT_PAGE)
    asked = append_carried_log_record(
        serve.page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Ready?"},
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Agent",
            "parent": asked["id"],
            "responds": asked["id"],
            "revision": 1,
            "text": "Which way should the rollout go first?",
            "obligation": True,
        },
    )
    page = open_page(browser, url)
    # The foot of a page with no room below it, which no scroll lifts clear of a view.
    without_end_room(page)
    resized(page, 1280, 900)
    page.evaluate("getSelection().removeAllRanges()")
    page.keyboard.press("m")
    expect_walk_position(page, "1 of 2 waiting on me")
    page.keyboard.press("m")
    expect_walk_position(page, "2 of 2 waiting on me")
    panel_settled(page, view="thread")
    page.evaluate("document.scrollingElement.scrollTo({top: 0, behavior: 'instant'})")
    scroll_settled(page)
    page.keyboard.press("m")
    expect_walk_position(page, "1 of 2 waiting on me")
    expect(page.locator("#bound-ask")).to_be_focused()
    panel_settled(page, open=False)
    scroll_settled(page)
    assert page.evaluate(SEEN_SHARE, "#bound-ask") > 0.99


def test_on_me_stays_over_only_the_items_it_lists(browser, serve):
    """On Me stays open over a place `m` reaches, whose card it rings, and gives way to
    one it doesn't list: `t` to a thread at the page's foot, which On Me would stand
    over, puts it away (panel/floating-panel.js, `clearFor`). Opened by a key, On Me stands on
    its first row, the channel question, so `m` steps on from it to the second."""
    url = serve(UNDER_PANEL_PAGE, anchored=[("tail", "The notes go out")])
    page = open_page(browser, url)
    # The foot of a page with no room below it, which no scroll lifts clear of a view.
    without_end_room(page)
    resized(page, 1280, 900)
    on_me = page.locator(panel_view("queue"))
    page.locator("#h").click()
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel_settled(page, view="queue")
    page.keyboard.press("m")
    expect_walk_position(page, "2 of 2 waiting on me")
    expect(page.locator("#foot-ask")).to_be_focused()
    expect(on_me).to_have_count(1)
    page.keyboard.press("t")
    expect(page.locator(".lf-margin-preview .lf-page-thread")).to_be_focused()
    panel_settled(page, open=False)
    scroll_settled(page)
    assert page.evaluate(SEEN_SHARE, "#tail") > 0.99


def test_o_presses_the_leaf_and_the_arrows_turn_the_on_view_s_tabs(browser, serve):
    """`o` presses the leaf, which names it, so with a question waiting it opens On Me
    with the question's card under the user, and a second `o` puts the view away,
    leaving the user on the page rather than on nothing. ← and → turn the view's tabs
    round from either end, landing on each list as a key opening it lands, or, from the
    tab strip, on the tab, stepping from the tab focus stands on. A tab the view
    doesn't show names the door that opens its list. `g A` opens the agent's list as
    `g M` opens the user's, and closes it again."""
    page = open_page(browser, serve(QUEUE_PAGE))
    shown = page.locator(".lf-fp-view")
    tab = page.locator('.lf-fp-tab[aria-pressed="true"]')
    agent = re.compile(r"On (?!Me\b)\w")
    on_page = "() => document.activeElement?.closest('main') !== null"
    expect(page.locator(".lf-fp-leaf")).to_have_attribute("aria-keyshortcuts", "o")
    page.locator("#h").click()
    page.keyboard.press("o")
    expect(tab).to_contain_text("On Me")
    expect(page.locator(".lf-fp-on-item").first).to_be_focused()
    for name, route in (
        (agent, "queue"),
        ("Threads", "threads"),
        ("Menu", "menu"),
        ("On Me", "queue"),
    ):
        page.keyboard.press("ArrowRight")
        expect(tab).to_contain_text(name)
        expect(shown).to_have_attribute("data-lf-route", route)
        expect(page.locator(f"{PANEL} .lf-fp-tab:focus")).to_have_count(0)
    page.keyboard.press("ArrowLeft")
    expect(tab).to_contain_text("Menu")
    menu_row = page.locator(f"{panel_view('menu')} .lf-fp-item:not(:disabled)")
    expect(menu_row.first).to_be_focused()
    page.keyboard.press("o")
    expect(shown).to_have_count(0)
    # Escape's landing, on the page, so Tab goes on from what is read there rather than
    # from the panel's row.
    page.keyboard.press("Tab")
    page.wait_for_function(on_page)
    # A tab pressed keeps the user on it; Tab moves to the next tab, On Me, without
    # turning to it, and → turns to the tab after the one focus stands on.
    page.keyboard.press("o")
    page.locator(".lf-fp-tab", has_text="Menu").click()
    expect(tab).to_contain_text("Menu")
    page.keyboard.press("Tab")
    expect(page.locator(".lf-fp-tab", has_text="On Me")).to_be_focused()
    page.keyboard.press("ArrowRight")
    expect(tab).to_contain_text(agent)
    expect(tab).to_be_focused()
    page.keyboard.press("ArrowLeft")
    page.keyboard.press("ArrowLeft")
    expect(tab).to_contain_text("Menu")
    expect(tab).to_be_focused()
    # A tab the view doesn't show names the door that opens its list from anywhere,
    # after the list's name, which its count beside it is no part of.
    page.mouse.move(2, 2)
    page.locator(".lf-fp-tab", has_text=agent).hover()
    expect(page.locator(f"{PREVIEW} .lf-preview-keys kbd")).to_have_text(["g", "A"])
    expect(page.locator(f"{PREVIEW} .lf-preview-word")).to_have_text(
        re.compile(r"^On (?!Me\b)\w+$")
    )
    page.keyboard.press("g")
    page.keyboard.press("Shift+a")
    expect(tab).to_contain_text(agent)
    page.keyboard.press("g")
    page.keyboard.press("Shift+a")
    expect(shown).to_have_count(0)


def test_a_tally_counts_its_regions_obligations_and_walks_them(browser, serve):
    """An `lf-tally` counts the obligations its region holds, by the rule a queue row's mark
    reads, and leaves out one outside it. Its Next On Me is `m` within the region: a
    press keeps the user located where they are and steps on, coming round at the end,
    and the walk announces its place among the region's obligations. Reached by Shift+Tab from
    an obligation, through the queue's own rows, Enter counts from that obligation, so the keyboard
    steps on too. An answer leaves the count once the log admits it; with none left the
    tally says so and Next On Me is disabled. One the user commented on is the agent's
    turn, which the tally names instead of calling it the user's to answer."""

    def item(key, label):
        return (
            f'<lf-tab id="t-{key}" label="{label}"><lf-group id="{key}-decision" label="Pick the {key}">'
            f'<h2 id="{key}-decision-h">Pick the {key}</h2><lf-options id="{key}">'
            f'<lf-option id="{key}-a">Alpha</lf-option>'
            f'<lf-option id="{key}-b">Beta</lf-option></lf-options></lf-group></lf-tab>'
        )

    page = open_page(
        browser,
        serve(
            leaf_page(
                "A tallied queue",
                '<header><h1>Queue</h1><p><lf-tally id="left" for="queue" next>'
                "</lf-tally></p></header>"
                '<lf-group id="outside-decision" label="Outside"><h2 id="outside-decision-h">Outside</h2>'
                '<lf-options id="outside"><lf-option id="outside-a">Out</lf-option>'
                "</lf-options></lf-group>"
                '<lf-tabs id="queue" list="side">'
                + item("first", "First")
                + item("second", "Second")
                + "</lf-tabs>",
            )
        ),
    )
    words = page.locator("#left .lf-tally-words")
    button = page.locator("#left").get_by_role("button", name="Next On Me")
    first, second = page.locator("#first-decision"), page.locator("#second-decision")
    expect(words).to_have_text("2 left to answer")
    count = page.locator("#left .lf-tally-count")
    waiting_color = count.evaluate("node => getComputedStyle(node).color")
    # Where the tally stands on the page, which a landing that scrolls leaves alone.
    tally_box = (
        "node => { const r = node.getBoundingClientRect();"
        " return [r.x, r.y + scrollY, r.width, r.height]; }"
    )
    box = page.locator("#left").evaluate(tally_box)

    # The row opens the obligation the user reads. Enter its obligation before deciding: the
    # strip itself precedes every panel in DOM order, but is not the walk's origin.
    page.get_by_role("tab", name="Second", exact=True).click()
    page.keyboard.press("Shift+m")
    expect(second).to_be_focused()
    page.get_by_role("tab", name="Second", exact=True).click()
    page.keyboard.press("m")
    expect(second).to_be_focused()
    with sending(page, "the second item's answer by digit"):
        page.keyboard.press("1")
    round_trip(page)
    expect(words).to_have_text("1 left to answer")
    answer = next(
        event
        for event in reversed(events_model.read_events(serve.page_dir))
        if event["kind"] == "action"
    )
    assert answer["widget"] == "second"
    button.click()
    expect(first).to_be_focused()
    # Next put the answer out of view in its tab, so the press takes it back and then
    # shows it there.
    with sending(page, "undo the second item's answer after Next"):
        page.keyboard.press("ControlOrMeta+z")
    round_trip(page)
    expect(page.locator("#second")).to_be_focused()
    expect(words).to_have_text("2 left to answer")
    assert events_model.read_events(serve.page_dir)[-1]["undoes"] == answer["id"]
    # Leave the next press at the region's start, as on initial arrival.
    page.get_by_role("tab", name="First", exact=True).click()

    def back_to_the_tally():
        for _ in range(30):
            if button.evaluate(
                "button => button === button.getRootNode().activeElement"
            ):
                return
            page.keyboard.press("Shift+Tab")
        raise AssertionError("Shift+Tab never reached Next On Me")

    button.click()
    expect(first).to_be_focused()
    expect_walk_position(page, "1 of 2 waiting on me here")
    button.click()
    expect(second).to_be_focused()
    expect_walk_position(page, "2 of 2 waiting on me here")
    back_to_the_tally()
    page.keyboard.press("Enter")
    expect(first).to_be_focused()
    back_to_the_tally()
    page.keyboard.press("Enter")
    expect(second).to_be_focused()

    with sending(page, "the answer to the second decision"):
        page.locator("#second-decision .lf-pick").first.click()
    round_trip(page)
    expect(words).to_have_text("1 left to answer")
    button.click()
    expect(first).to_be_focused()
    with sending(page, "the answer to the first decision"):
        page.locator("#first-decision .lf-pick").first.click()
    round_trip(page)
    expect(words).to_have_text("All 2 answered")
    expect(count).not_to_have_css("color", waiting_color)
    expect(button).to_be_disabled()
    with sending(page, "undo the first decision's answer"):
        page.keyboard.press("ControlOrMeta+z")
    round_trip(page)
    expect(words).to_have_text("1 left to answer")
    expect(count).to_have_css("color", waiting_color)
    expect(button).to_be_enabled()
    # A comment on the open obligation hands it to the agent until a reply: the tally and
    # the item's row say so rather than calling it the user's to answer, beside a
    # disabled Next On Me.
    panel_comment(serve.page_dir, "Why Alpha?", {"section": "first-decision"})
    expect(words).to_have_text("1 on Claude")
    expect(count).to_have_css("color", waiting_color)
    expect(page.locator("#queue .lf-tab-answer").first).to_have_text("On Claude")
    expect(button).to_be_disabled()
    assert page.locator("#left").evaluate(tally_box) == box


@pytest.mark.parametrize("idle_setup", ["at_rest", "layout_clamp"])
def test_an_idle_m_arrival_paints_in_its_first_frame(browser, serve, idle_setup):
    """`m` to an obligation already in view moves nothing, so the user is on it in the
    first frame after the press, also once a layout change has clamped the page's
    scroll back to where it stood."""
    page = open_page(browser, serve(QUEUE_PAGE))
    resized(page, 1280, 900)
    if idle_setup == "layout_clamp":
        # Content leaving below clamps the page only where no room is kept under it.
        without_end_room(page)
        page.evaluate("""() => {
          const tail = document.createElement('div');
          tail.id = 'temporary-tail';
          tail.style.height = '3000px';
          document.querySelector('main').append(tail);
          window.scrollTo({top: 1000, behavior: 'instant'});
        }""")
        scroll_settled(page)
        page.evaluate("document.querySelector('#temporary-tail').remove()")
        scroll_settled(page)
        assert page.evaluate("scrollY") == 0
    page.locator("#cadence").click()
    page.evaluate("""() => {
      document.addEventListener('keydown', function read(event) {
        if (event.key.toLowerCase() !== 'm') return;
        document.removeEventListener('keydown', read, true);
        requestAnimationFrame(() => {
          window.focusAtFirstFrame = document.activeElement.id;
        });
      }, true);
    }""")
    page.keyboard.press("m")
    expect_walk_position(page, "1 of 1 waiting on me")
    expect(page.locator("#channel-ask")).to_be_focused()
    assert page.evaluate("focusAtFirstFrame") == "channel-ask"


def test_an_m_step_newer_focus_cancels_at_a_thread_claims_no_arrival(browser, serve):
    """`m` arriving at a thread with the panel shut opens it on the page, and the
    opening can wait on the page. Focus the user moves meanwhile cancels the arrival:
    focus stays where they put it and the walk says nothing about the thread."""
    url = serve(QUEUE_PAGE)
    asked = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Weekly?",
            "anchor": {"section": "cadence"},
        },
    )
    question = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Agent",
            "parent": asked["id"],
            "responds": asked["id"],
            "revision": 1,
            "text": "Weekly or daily?",
            "obligation": True,
        },
    )
    page = open_page(browser, url)
    page.evaluate(
        """() => {
          const held = new Promise(resolve => { window.releaseThreadReveal = resolve; });
          held.then(() => { window.threadRevealSettled = true; });
          // Revealing the thread's passage waits for its update, which the test holds.
          const passage = document.querySelector('#cadence');
          passage.hidden = 'until-found';
          passage.addEventListener('beforematch', () => {
            passage.updateComplete = held;
            window.threadRevealStarted = true;
          }, {once: true});
        }"""
    )

    page.keyboard.press("m")
    page.wait_for_function("window.threadRevealStarted === true")
    page.locator(".lf-fp-leaf").focus()
    expect(page.locator(".lf-fp-leaf")).to_be_focused()
    page.evaluate("releaseThreadReveal()")
    page.wait_for_function("window.threadRevealSettled === true")
    rendered(page)

    expect(page.locator(".lf-fp-leaf")).to_be_focused()
    assert walk_position(page) is None
    # The control: the same press left alone arrives and says where.
    page.locator("#h").click()
    page.keyboard.press("m")
    expect_walk_position(page, "1 of 2 waiting on me")
    expect(page.locator(f'.lf-msg[data-lf-event="{question["id"]}"]')).to_be_focused()


@pytest.mark.parametrize("width", [1200, 390])
def test_a_completed_obligation_stays_reachable_through_on_me(browser, serve, width):
    """An answered obligation stays in On Me under Done, which closes and reopens through
    its routes, and finishing the page preserves the route back through the answer. The
    answer that leaves nothing on the user has the panel say so, unasked."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "One decision",
                '<h1>One decision</h1><lf-group id="only-decision" label="Pick one"><h2 id="only-decision-h">Pick one</h2>'
                '<lf-options id="only">'
                '<lf-option id="first">First</lf-option>'
                '<lf-option id="second">Second</lf-option></lf-options></lf-group>',
            )
        ),
    )

    resized(page, width, 844)
    # `m` travels to the obligation and Tab steps onto a mark, whose digit answers it. Tab
    # rather than the digit straight off the arrival, because where an arrival lands is
    # not this test's subject and it should not go red when that moves.
    page.keyboard.press("m")
    expect(page.locator("#only-decision")).to_be_focused()
    page.keyboard.press("Tab")
    expect(page.locator("#only .lf-pick").first).to_be_focused()
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("1")
    holding(page, held, 1, "the option answer")
    pending = page.evaluate(
        """async () => {
          const {readObligations} = await window.__lfWidgetApi();
          const reading = readObligations();
          const item = reading.all.find(q => q.id === 'widget:only');
          return {
            value: item.answer.value,
            state: item.state,
            unanswered: reading.unanswered.some(q => q.id === item.id),
          };
        }"""
    )
    # The press answers the question in its own task, before the server's reading.
    assert pending == {"value": ["first"], "state": "done", "unanswered": False}
    page.unroute("**/api/event")
    for route in held:
        route.continue_()
    round_trip(page)
    expect_on_me(page, 0)
    expect_panel_says(page, "Nothing waiting on me")

    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel_settled(page, view="queue")
    done = show_done(page)
    expect(done).to_have_count(1)
    expect(done).to_contain_text("Pick one")
    expect(done).to_contain_text("First")
    expect(page.locator('.lf-fp-on-item[data-lf-list="you"]')).to_have_count(0)

    reading = page.evaluate(
        """async () => {
          const {readObligations} = await window.__lfWidgetApi();
          const item = readObligations().all.find(q => q.id === 'widget:only');
          return {
            id: item.id,
            source: item.source,
            prompt: item.prompt,
            value: item.answer.value,
            answered: item.answered,
          };
        }"""
    )
    assert reading == {
        "id": "widget:only",
        "source": {"kind": "widget", "id": "only", "tag": "lf-options"},
        "prompt": {"text": "Pick one", "target": "only-decision"},
        "value": ["first"],
        "answered": True,
    }

    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel_settled(page, open=False)

    # With nothing left on the user, On Me opens on its folded Done.
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel_settled(page, view="queue")
    expect(show_done(page)).to_have_count(1)
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel_settled(page, open=False)

    page.locator("h1").focus()
    assert page.evaluate(
        """async () => {
          const {obligationActions} = await window.__lfWidgetApi();
          return obligationActions.open('widget:only');
        }"""
    )
    expect(page.locator("#only-decision")).to_be_focused()


def test_going_to_an_obligation_by_name_says_its_place_in_on_me(browser, serve):
    """A press naming one obligation, as a Page Map row or a deck's arrival does, says
    where it stands in On Me as `m` landing there says it, counting the same list: with
    the first of three questions answered, the third is the second of three, beside the
    proposal still open. An answered question inside that proposal has no place in On
    Me, so it says how it ended rather than the proposal's place, and the proposal's
    place, said a moment before, stands no longer."""
    asks = "".join(
        f"""<lf-group id="ask-{index}" label="Question {index}"><h2>Question {index}</h2>
<lf-options id="pick-{index}">
  <lf-option id="pick-{index}-yes">Yes</lf-option>
  <lf-option id="pick-{index}-no">No</lf-option>
</lf-options></lf-group>"""
        for index in range(1, 4)
    )
    proposal = """<lf-suggestion id="plan"><lf-old><p>The old plan reads this way.</p></lf-old>
<lf-new><p>The new plan reads another way.</p>
<lf-group id="step-ask" label="Keep the new step?"><lf-options id="step">
  <lf-option id="step-keep">Keep it</lf-option>
  <lf-option id="step-drop">Drop it</lf-option>
</lf-options></lf-group></lf-new></lf-suggestion>"""
    page = open_page(
        browser,
        serve(leaf_page("three questions", f"<h1>Questions</h1>{asks}{proposal}")),
    )

    def open_obligation(id_):
        assert page.evaluate(
            """async id => (await window.__lfWidgetApi()).obligationActions.open(id)""",
            id_,
        )

    page.keyboard.press("m")
    expect(page.locator("#ask-1")).to_be_focused()
    page.keyboard.press("1")
    expect_obligations_answered(page, "1/5")
    page.keyboard.press("Escape")
    open_obligation("widget:pick-3")
    expect(page.locator("#ask-3")).to_be_focused()
    expect_walk_position(page, "2 of 4 waiting on me")

    page.locator("#step .lf-pick").first.click()
    expect_obligations_answered(page, "2/5")
    page.keyboard.press("Escape")
    open_obligation("widget:plan")
    expect_walk_position(page, "3 of 3 waiting on me")
    open_obligation("widget:step")
    expect(page.locator("#step-ask")).to_be_focused()
    expect(page.locator(".lf-live")).to_have_text("Answered: Keep it")
    expect_walk_position(page, None)


def test_the_page_s_press_holds_under_a_resting_pointer_until_a_key(browser, serve):
    """While the pointer rests on the panel, a revision that empties On Me leaves Next
    On Me where the user may be about to press it; their next key, here an arrow that
    scrolls the page and paints nothing in the panel, takes it away."""
    source = leaf_page(
        "One decision",
        '<h1>One decision</h1><lf-group id="only-decision" label="Pick one"><h2 id="only-decision-h">Pick one</h2>'
        '<lf-options id="only">'
        '<lf-option id="first">First</lf-option>'
        '<lf-option id="second">Second</lf-option></lf-options></lf-group>',
    )
    url = serve(source)
    page = open_page(browser, live_url(url))
    press = field_press(page)
    expect(press.locator(".lf-compose-press-word")).to_have_text("Next On Me")
    box = page.locator(".lf-fp-field").bounding_box()
    assert box
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)

    stamp_page(
        serve.page_dir,
        leaf_page("No decisions", "<h1>No decisions remain</h1>"),
        "remove the last obligation",
    )
    wait_for_revision(page, 2)
    expect_on_me(page, 0)
    expect(press.locator(".lf-compose-press-word")).to_have_text("Next On Me")
    page.keyboard.press("ArrowDown")
    expect(press).to_have_count(0)


def test_on_me_says_when_a_revision_removes_its_last_obligation(browser, serve):
    """An empty On Me list says the panel rendered, rather than looking broken."""
    source = leaf_page(
        "One decision",
        '<h1>One decision</h1><lf-group id="only-decision" label="Pick one"><h2 id="only-decision-h">Pick one</h2>'
        '<lf-options id="only">'
        '<lf-option id="first">First</lf-option>'
        '<lf-option id="second">Second</lf-option></lf-options></lf-group>',
    )
    url = serve(source)
    page = open_page(browser, live_url(url))
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel_settled(page, view="queue")
    cards = page.locator('.lf-fp-on-item[data-lf-list="you"]')
    expect(cards).to_have_count(1)
    note = page.locator(f"{panel_view('queue')} .lf-rows-empty")
    expect(note).to_have_count(0)

    stamp_page(
        serve.page_dir,
        leaf_page("No decisions", "<h1>No decisions remain</h1>"),
        "remove the last obligation",
    )
    wait_for_revision(page, 2)
    expect(cards).to_have_count(0)
    expect(page.locator(PANEL)).to_have_attribute("data-lf-open", "queue")
    expect(note).to_be_visible()
    expect(note).to_have_text("Nothing waiting on me.")
    # The agent's tab says the same of its list.
    page.locator(".lf-fp-filters button").nth(2).click()
    expect(page.locator(".lf-fp-view .lf-rows-empty")).to_have_text(
        re.compile(r"Nothing waiting on \S+\.")
    )


# The motion the panel's leaf plays, named by the turn it reaches first
# (panel/floating-panel.js, `MOTIONS`).
LEAF_MOTIONS = {
    "rotate(-12deg) scale(1.15)": "nod",
    "translateX(-3px) rotate(-5deg)": "shake",
    "translateY(-3px) scale(1.14)": "perk",
    "rotate(10deg)": "sway",
    "rotate(180deg) scale(1.15)": "twirl",
    "rotate(14deg) translateX(1px)": "beckon",
}


def test_the_leaf_answers_each_moment_with_its_gesture(browser, serve):
    """The panel's leaf nods at each step of `m`, a second over the one item waiting
    included, though nothing else moves, twirls when the user's answer empties On Me,
    and nods at `m` over the empty list, once each, however often the field leaves a
    notice's words and comes back to them."""
    source = leaf_page(
        "One decision",
        '<h1>One decision</h1><lf-group id="only-decision" label="Pick one"><h2 id="only-decision-h">Pick one</h2>'
        '<lf-options id="only">'
        '<lf-option id="first">First</lf-option>'
        '<lf-option id="second">Second</lf-option></lf-options></lf-group>',
    )
    page = open_page(browser, serve(source))
    # The sequence of motions the leaf's mark starts, each by the turn it reaches first.
    page.evaluate(
        """() => {
          window.__lfLeaf = [];
          const animate = Element.prototype.animate;
          Element.prototype.animate = function (keyframes, options) {
            if (this.matches('.lf-fp-leaf > svg'))
              window.__lfLeaf.push(keyframes[1].transform);
            return animate.call(this, keyframes, options);
          };
        }"""
    )

    def gestures(count):
        page.wait_for_function(f"() => window.__lfLeaf.length >= {count}")
        return [LEAF_MOTIONS[turn] for turn in page.evaluate("() => window.__lfLeaf")]

    page.keyboard.press("m")
    expect(page.locator("#only-decision")).to_be_focused()
    assert gestures(1) == ["nod"]
    page.keyboard.press("m")
    assert gestures(2) == ["nod", "nod"]

    page.keyboard.press("Tab")
    expect(page.locator("#only .lf-pick").first).to_be_focused()
    page.keyboard.press("1")
    round_trip(page)
    expect_panel_says(page, "Nothing waiting on me")
    assert gestures(3) == ["nod", "nod", "twirl"]

    page.keyboard.press("m")
    assert gestures(4) == ["nod", "nod", "twirl", "nod"]

    # The field says the selected words, then the notice's again once they go.
    page.locator("h1").select_text()
    expect_panel_says(page, "One decision")
    page.evaluate("() => getSelection().removeAllRanges()")
    expect_panel_says(page, "One decision", says=False)
    page.evaluate(
        "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
    )
    assert gestures(4) == ["nod", "nod", "twirl", "nod"]


def test_m_lands_what_it_reaches_above_the_open_on_me_view(browser, serve):
    """With On Me open, `m` lands a suggestion the view would cover above the view,
    since every landing clears the panel's whole box rather than its row alone
    (dom/geometry.js, `footCover`). The suggestion ends a paragraph whose start the
    arrival aligns, as the feature gallery's "A pencil is useful too." does; the asks
    after it fill the list, so the view stands most of the window tall. Opened by a
    key, On Me stands on its first row, the suggestion, so `m` steps on to the first
    ask and `Shift+m` walks back to the suggestion."""
    filler = "".join(f"<p>Paragraph {n} of the release notes.</p>" for n in range(30))
    asks = "".join(
        f'<lf-group id="ask-{n}" label="Question {n}"><h2 id="ask-{n}-h">Question {n}</h2><lf-options id="pick-{n}">'
        f'<lf-option id="yes-{n}">Yes</lf-option><lf-option id="no-{n}">No</lf-option>'
        "</lf-options></lf-group>"
        for n in range(10)
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Suggestions",
                f"<h1>Suggestions</h1>{filler}"
                '<p id="forms">'
                + "".join(f"Line {n} of the packing list.<br>" for n in range(8))
                + 'Bring a notebook.<lf-suggestion id="insert"><lf-new> A pencil is '
                "useful too.</lf-new></lf-suggestion></p>"
                f"{filler}{asks}",
            )
        ),
    )
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel_settled(page, view="queue")
    card = page.locator(".lf-fp-card")
    suggestion = page.locator("#insert")
    page.keyboard.press("m")
    expect(page.locator("#ask-0")).to_be_focused()
    page.keyboard.press("Shift+m")
    expect(suggestion).to_be_focused()
    scroll_settled(page)
    box = suggestion.bounding_box()
    assert box["y"] >= 0
    assert box["y"] + box["height"] <= card.bounding_box()["y"]
