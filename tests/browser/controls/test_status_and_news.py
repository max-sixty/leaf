"""The panel's status and the other pages it lists, and the chrome holding still
through news: the agent's state announced in its own words, the row's controls left
where they stood when news arrives, and All pages following each page's status."""

import os

import pytest
from interact_support import (
    append_carried_log_record,
    append_command,
    declare,
    declare_work,
    end_work,
    record_claim,
    working,
)
from playwright.sync_api import expect
from render_cases_interaction import SUGGESTION_PAGE
from render_cases_layout import (
    CHROME_WATCH,
    DEFINE_BOXES,
    NEIGHBOUR,
    NEIGHBOURHOOD,
    displaced,
    page_at_rest,
)
from render_harness import (
    LONG_PAGE,
    consume_browser_errors,
    expect_open_threads,
    http_error_console,
    nudge,
    open_page,
    panel_field,
    panel_settled,
    panel_view,
    refuse,
    stamp_page,
    told,
)

from leaf import leases as leases_model
from leaf import service as service_model

pytestmark = pytest.mark.shifts_unsurveyed


# The panel's All pages view, which `g L` opens while other pages are live.
LEAVES = panel_view("leaves")


def test_a_status_kind_change_is_announced_in_the_status_s_own_words(browser, serve):
    """The dot going red is not an announcement.

    The chrome once flipped to the offline colour and rewrote its line while the live
    region went on holding whatever it last said, so a user who is not watching the
    chrome learned nothing. A kind changing — work starting, a turn ending, the server
    going, then refusing this tab's key — is what is worth interrupting for, and what it says is the status's own
    sentence rather than a second account of it. The age moving and a count turning over
    are not kinds and stay out of the region."""
    url = serve(SUGGESTION_PAGE)
    # The agent has the page in hand when the user opens it.
    working(serve.page_dir, "Writing the page")
    page = open_page(browser, url)
    live = page.locator(".lf-live")
    expect(page.locator(".lf-fp-leaf .lf-dot.working")).to_be_visible()
    # The page arriving is the document's own announcement, not a change in it.
    assert live.text_content() == "", (
        f"the status announced its first reading: {live.text_content()!r}"
    )

    claim = record_claim(serve.page_dir, id="s", pid=os.getpid())
    lease_path = leases_model.waiter_lease_path(serve.page_dir, claim["id"])
    assert lease_path is not None
    lease = leases_model.take_wait_lease(lease_path)
    assert lease
    with service_model.PageTransaction(serve.page_dir) as transaction:
        transaction.set_stream_activity(
            claim["id"], "provider-turn", {"kind": "awaiting_input"}
        )
    told(page)
    expect(live).to_contain_text("Input needed in the terminal")
    announced_wait = live.text_content()

    with service_model.PageTransaction(serve.page_dir) as transaction:
        transaction.set_stream_activity(
            claim["id"], "provider-turn", {"kind": "tool", "detail": "Checking"}
        )
    told(page)
    assert live.text_content() == announced_wait

    with service_model.PageTransaction(serve.page_dir) as transaction:
        transaction.set_stream_activity(
            claim["id"], "provider-turn", {"kind": "awaiting_approval"}
        )
    told(page)
    expect(live).to_contain_text("Approval needed in the terminal")
    leases_model.release_lease(lease)

    page.route("**/api/**", refuse)
    try:
        # A healthy page never asks without news, so give it one: the read that follows
        # is the one the route refuses.
        nudge(serve.page_dir)
        # An unreachable server turns the leaf red, and the field says it as a status
        # rather than an error.
        expect(live).to_contain_text("Lost the connection")
        expect(page.locator(".lf-fp-leaf .lf-dot.blocked")).to_be_visible()
        expect(panel_field(page)).to_have_attribute("data-says", "status")
        # The server coming back to refuse this tab's key asks something new of the
        # user, which only they can end, so it is heard and the field says it as an
        # error.
        page.route("**/api/state*", lambda route: route.fulfill(status=401, body="{}"))
        expect(live).to_contain_text("This tab lost access")
        expect(panel_field(page)).to_have_attribute("data-says", "error")
        # A server that answers with an error of its own is up and failing, which is
        # neither offline nor a key to replace: the status says its words.
        page.route(
            "**/api/state*",
            lambda route: route.fulfill(
                status=500, json={"error": "projection failed"}
            ),
        )
        expect(live).to_contain_text("Hit a problem: projection failed")
        # The refused and failed reads recur on the page's clock until it closes.
        page.close()
        consume_browser_errors(page, http_error_console(401), http_error_console(500))
    finally:
        if not page.is_closed():
            page.unroute("**/api/**")


def test_the_neighbour_reading_detects_a_whole_row_moving_on_press(browser):
    """Moving the containing row must not cancel a control's screen displacement."""
    page = browser.unwatched.new_page()
    page.set_viewport_size({"width": 800, "height": 600})
    page.set_content("""
      <div class="lf-playground-actions">
        <button id="move" onclick="this.parentElement.style.transform =
          this.parentElement.style.transform ? 'translate(2000px, 24px)' :
            'translate(32px, 24px)'">Move row</button>
        <button>Neighbour</button>
      </div>
    """)
    page.evaluate(DEFINE_BOXES)
    before = page.locator("#move").evaluate(NEIGHBOURHOOD, NEIGHBOUR)
    assert before["names"] == ['button "Neighbour"']
    assert displaced(before, page.evaluate("() => window.__lfBoxes()")) == []

    page.locator("#move").click()
    assert displaced(before, page.evaluate("() => window.__lfBoxes()")) == [
        'button "Neighbour" moved by [32, 24, 0, 0] (left, top, width, height)'
    ]
    # Moving beyond the viewport is displacement too, not hiding the control.
    page.locator("#move").click()
    assert page.get_by_role("button", name="Neighbour").bounding_box()["x"] > 800
    assert displaced(before, page.evaluate("() => window.__lfBoxes()")) == [
        'button "Neighbour" moved by [2000, 24, 0, 0] (left, top, width, height)'
    ]


def test_the_poll_leaves_the_panel_where_it_was(browser, serve):
    """The other half of the same rule, for the changes nobody asked for.

    A press has a line — the row the pressed control stands on, where the next gesture
    is already aimed — and below it the page is content and may move. News arriving on
    the poll has no gesture at all, so there is no line to draw: the user was
    somewhere else entirely, and every control in the chrome is a control they are
    holding. The document may still change under them, because a fact arriving is what
    they are here to see; its resulting destination may not be. A control whose own words
    the news rewrote may grow or shrink into free room, as the status press does when the
    sentence it carries changes; nothing else may move for it.

    The panel's row is where all of it lands. On the banner `Threads: 9` becoming
    `Threads: 10` — a comment posted from the terminal while the user reads — slid
    the version picker 6px left, and the Accept all a second tab's decision put away
    took the New-version chip with it; the row's notice for a new version takes its
    room from the field, so the marks keep their seats.

    Driven by writing the events a real one would leave, since that is what the page
    reads either way, and there is no other way to reach this half: every gesture the
    press sweep above can make is one the user made, and none of these are."""
    # Three pending suggestions, so On me's count has somewhere to go before they run
    # out; nine comments already, so the tenth crosses a digit; and pinned, so a v2
    # landing leaves the page where it is and offers the row's notice rather than
    # following it.
    html = SUGGESTION_PAGE
    url = serve(html, comments=9)
    d = serve.page_dir
    page = open_page(browser, url, pin=True)
    on_me = "document.querySelector('.lf-fp-on-user').getAttribute('aria-label')"
    # What the mark counts, less the news its name goes on to say.
    owing = f"{on_me}.split(', ')[0]"
    expect_open_threads(page, 9)
    page_at_rest(page)
    owed = int(page.evaluate(f"() => {on_me}").removeprefix("On me: "))

    def publish_v2():
        stamp_page(d, html, "two")

    # The same events a second tab's presses would have posted, which is the only way one
    # user's browser hears about another's decisions.
    def decide(*widgets):
        for widget in widgets:
            append_command(
                d,
                {
                    "kind": "action",
                    "author": "user",
                    "revision": 1,
                    "widget": widget,
                    "action": "decide",
                    "detail": {"outcome": "accept"},
                },
            )

    for what, drive, arrived in [
        (
            "an agent's comment arrives, dotting the mark with news",
            lambda: append_carried_log_record(
                d,
                {
                    "kind": "comment",
                    "author": "agent",
                    "agent": "Claude",
                    "revision": 1,
                    "text": "A tenth.",
                },
            ),
            f"() => {on_me}.endsWith('1 thread with news')",
        ),
        (
            "a new version is published",
            publish_v2,
            "() => document.querySelector('.lf-fp-row-notice')?.checkVisibility()",
        ),
        (
            "another tab decides two of the three pending suggestions",
            lambda: decide("sug-refill", "sug-thistle"),
            f"() => {owing} === 'On me: {owed - 2}'",
        ),
        (
            "another tab decides the last one",
            lambda: decide("sug-in-card"),
            f"() => {owing} === '{'On me: ' + str(owed - 3) if owed > 3 else 'On me'}'",
        ),
    ]:
        page.evaluate(DEFINE_BOXES)
        before = page.evaluate(CHROME_WATCH, NEIGHBOUR)
        assert len(before["names"]) >= 3, (
            f"before {what} the panel was showing only {before['names']}, which is "
            "fewer controls than its row always has — this step asserts almost nothing"
        )
        drive()
        page.wait_for_function(arrived)
        page_at_rest(page)
        moved = displaced(before, page.evaluate("() => window.__lfBoxes()"), news=True)
        assert not moved, f"{what} and the panel moved:\n  " + "\n  ".join(moved)


def test_a_panel_row_follows_its_pages_status_live(
    browser, serve, other_leaf, tmp_path
):
    """All pages is a status surface, not a snapshot: a neighbour's declaration
    changing on disk repaints its row at the next poll, in place, and the row's
    hover follows it, being the same account written where there is room for it
    whole."""
    _, other_dir = other_leaf
    page = open_page(browser, serve(LONG_PAGE))
    told(page, until=lambda state: bool(state["others"]))
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    panel_settled(page, view="leaves")
    row = page.locator(f"{LEAVES} a.lf-fp-page")
    expect(row).to_contain_text("running the suite")
    declare_work(other_dir, "recording the demo")
    told(page)
    expect(row).to_contain_text("recording the demo")
    # A neighbour waiting on its own user says so in this seat's shorter words, and
    # in the same term its own status uses: All pages is where a user picks which
    # page to go to. The hover holds it whole, since the line ellipsizes at the
    # panel's width, and it is the row's hover and not a part's, the innermost title
    # winning where two overlap.
    end_work(other_dir)
    declare(other_dir, "waiting")
    told(page)
    expect(row).to_contain_text("Ready")
    expect(row).to_have_attribute(
        "title", f"The other leaf\n{tmp_path / 'other-work'}\nReady"
    )
    assert row.locator("[title]").count() == 0, (
        "a part of the row carries a tooltip of its own, which wins under the pointer "
        "over the row's whole account"
    )


def test_a_closed_leaf_clears_itself_off_all_pages(browser, serve, other_leaf):
    """A closed leaf leaves All pages on the poll that says so. Its server stays
    up — a persistent one for good — so the row would otherwise stand forever and the
    list a user glances at to find who needs them would become a tally of
    everything that has ever run here. This page's own row never drops — a user
    looking at a closed page is still looking at it — so a list with nothing live left
    on it still says where the user is."""
    _, other_dir = other_leaf
    page = open_page(browser, serve(LONG_PAGE))
    told(page, until=lambda state: bool(state["others"]))
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    panel_settled(page, view="leaves")
    view = page.locator(LEAVES)
    rows = view.locator("a.lf-fp-page")
    expect(rows).to_have_count(1)
    rows.first.focus()
    declare(other_dir, "idle")
    told(page)
    expect(rows).to_have_count(0)
    expect(view.locator(".lf-fp-page")).to_contain_text("long")
    assert view.evaluate("view => view.contains(document.activeElement)"), (
        "the leaving row dropped the user out of All pages"
    )
