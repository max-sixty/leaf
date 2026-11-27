"The floating panel: Leaf's one chrome, a box over the page's foot.\n\nEach test is one journey a user takes through the panel: writing a page comment and replying in the same field, settling the thread, finding\nthreads and taking in news, answering obligations, travelling between versions, and\nfolding the panel to the leaf in the window's corner and back."

import re
from datetime import datetime, timedelta

import pytest
from browser.test_render_floating_panel import (
    GROWTH,
    ROW_CENTRES,
    SEATS,
    SEEK_HELD,
    field,
    finish_held,
    floating,
    held_motion,
    hold_motion,
    risen,
    settled,
)
from interact_support import declare
from playwright.sync_api import expect
from render_harness import (
    EDITOR_ROOTS,
    LONG_PAGE,
    PREVIEW,
    latest_press,
    open_page,
    panel_menu,
    panel_settled,
    resized,
    stamp_page,
    ticked,
    write,
)
from render_harness import leaf_page as titled_page

from leaf.agents import thread as thread_model
from leaf.source.render_checks import wait_until_ready
from leaf_dev import browser as dev_browser


def test_a_long_draft_fades_where_words_run_past_the_field(browser, serve):
    """A draft taller than the field shows no scrollbar, whose overlay flashed with each
    line; its words fade at whichever edge they run past."""
    page = floating(browser, serve(LONG_PAGE))
    field(page).click()
    for line in range(30):
        page.keyboard.type(f"line {line}")
        page.keyboard.press("Shift+Enter")

    def shows(states):
        page.wait_for_function(
            f"() => document.querySelector('.lf-fp-field leaf-text').matches('{states}')"
        )

    expect(field(page)).to_have_css("scrollbar-width", "none")
    shows(":state(more-above):not(:state(more-below))")
    field(page).evaluate("box => box.scrollTop = 0")
    shows(":state(more-below):not(:state(more-above))")
    field(page).evaluate("box => box.scrollTop = 100")
    shows(":state(more-below):state(more-above)")


from browser.test_render_floating_panel import (
    CUT_STATUS,
    FOOT,
)
from interact_support import (
    append_carried_log_record,
    working,
)
from render_cases_interaction import (
    panel_comment,
)
from render_harness import (
    all_pages_offered,
    clocked,
    dwelt,
    long_press,
    open_threads,
    panel_view,
    sending,
    show_resolved,
    told,
    undo,
)

from leaf.log import event_log as events_model
from leaf.source.render_checks import rendered


def test_nothing_lies_over_a_view_s_foot_but_new_reply(browser, serve):
    """An open view's foot keeps no room for anything but its padding, and nothing lies
    over it: not the line over the field, which would repeat where the words go, nor
    news arriving in it, which the view shows. At the view's end a long Threads list's
    last row stands just above its padding, and the last words of a long thread the user
    types at the end of stand a message's gap above the field, as over a next message.
    New reply alone stands at its foot, on the panel's ground and inside the view, clear
    of the user's own last turn while the answer to it waits below."""
    url = serve(LONG_PAGE, comments=12)
    long_root = panel_comment(serve.page_dir, "Walk me through the whole rollout.")
    for step in range(8):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Claude",
                "parent": long_root,
                "revision": 1,
                "text": f"Step {step}. "
                + "The cohort widens once the alarms hold. " * 4,
            },
        )
    page = floating(browser, url)

    def at_end(parts, *, gap=False):
        page.locator(".lf-fp-view").evaluate(
            "view => view.scrollTop = view.scrollHeight"
        )
        settled(page)
        foot = page.evaluate(FOOT, [parts, 0])
        assert foot["said"] == [], foot
        room = foot["gap"] - foot["pad"] if gap else 0
        assert 0 <= foot["below"] - room < 10, foot

    open_threads(page)
    inventory = page.locator(panel_view("threads"))
    expect(inventory.locator(".lf-fp-thread")).to_have_count(13)
    field(page).click()
    page.keyboard.type("Could")
    expect(page.locator(".lf-fp-field .lf-compose-submit")).to_be_visible()
    at_end(".lf-fp-thread")

    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.press("Backspace")
    inventory.locator(".lf-fp-thread", has_text="Walk me through").click()
    reader = page.locator(panel_view("thread"))
    expect(reader.locator(".lf-msg")).to_have_count(9)
    field(page).click()
    page.keyboard.type("Could")
    expect(page.locator(".lf-fp-field .lf-compose-submit")).to_be_visible()
    at_end(".lf-msg", gap=True)

    # The answer to the user's turn waits below the fold behind New reply, and its
    # arrival goes unsaid over the view that holds it.
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("And the weekend?")
    with sending(page, "the reply"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect(reader.locator(".lf-msg")).to_have_count(10)
    settled(page)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": long_root,
            "revision": 1,
            "text": "It would. "
            + "Someone stays on call through Sunday, and Monday too. " * 40,
        },
    )
    told(page)
    expect(reader.locator(".lf-new-reply")).to_have_text("New reply")
    settled(page)
    # The user's own turn, the last message but the answer below the fold.
    foot = page.evaluate(FOOT, [".lf-msg-text", 1])
    assert foot["said"] == [], foot
    assert foot["press"]["over"] >= 0, foot
    assert foot["press"]["under"] >= 0, foot


def test_a_long_draft_offers_more_room_at_a_press(browser, serve):
    """Past three lines the field offers more room, by a press rather than on its own:
    a mark stands over the leaf, beside the field's first line, taking no room of its
    own, including with a view open. Pressing it widens the panel, keeps the field at
    least as tall as the draft stood, without standing a short draft half the window
    tall, and keeps the caret in the words; emptying the field folds it back."""
    page = floating(browser, serve(LONG_PAGE))
    panel = page.locator(".lf-floating-panel")
    expand = page.locator(".lf-fp-expand")
    field(page).click()
    page.keyboard.type("A line of words long enough to wrap in the panel's field, " * 2)
    expect(expand).to_be_hidden()
    narrow = panel.bounding_box()["width"]
    page.keyboard.type("A line of words long enough to wrap in the panel's field, " * 2)
    expect(expand).to_be_visible()
    words = page.locator(".lf-fp-field").bounding_box()
    leaf = page.locator(".lf-fp-leaf").bounding_box()
    mark = expand.bounding_box()
    assert words["x"] + words["width"] <= mark["x"] + 0.5, (words, mark)
    assert words["y"] <= mark["y"] + 0.5, (words, mark)
    assert mark["y"] + mark["height"] <= leaf["y"] + 0.5, (leaf, mark)
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("Shift+T")
    expect(page.locator(panel_view("threads"))).to_be_visible()
    expect(expand).to_be_visible()
    words = page.locator(".lf-fp-field").bounding_box()
    leaf = page.locator(".lf-fp-leaf").bounding_box()
    mark = expand.bounding_box()
    assert words["x"] + words["width"] <= mark["x"] + 0.5, (words, mark)
    assert mark["y"] + mark["height"] <= leaf["y"] + 0.5, (leaf, mark)
    page.keyboard.press("Escape")
    field(page).click()
    expect(expand).to_have_attribute("aria-pressed", "false")
    before = field(page).bounding_box()["height"]
    expand.click()
    expect(expand).to_have_attribute("aria-pressed", "true")
    expect(field(page)).to_be_focused()
    settled(page)
    assert panel.bounding_box()["width"] > narrow + 100
    tall = field(page).bounding_box()["height"]
    assert before - 1 <= tall < page.viewport_size["height"] / 3, (before, tall)
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.press("Backspace")
    expect(expand).to_be_hidden()
    settled(page)
    assert panel.bounding_box()["width"] == pytest.approx(narrow, abs=1)


def test_more_room_on_a_phone_keeps_the_panel_its_width(browser, serve):
    """On a phone the panel already spans the window less its gutter, so more room to
    write leaves it as wide as it was. The wider panel's own width named the desktop's
    24px gutter rather than the phone's 20px, so pressing for more room narrowed it."""
    context = browser.new_context(viewport={"width": 390, "height": 800})
    page = open_page(browser, serve(LONG_PAGE), context=context)
    panel = page.locator(".lf-floating-panel")
    expand = page.locator(".lf-fp-row > .lf-fp-expand")
    field(page).click()
    page.keyboard.type("A line of words long enough to wrap in the panel's field, " * 4)
    expect(expand).to_be_visible()
    settled(page)
    narrow = panel.bounding_box()["width"]
    expand.click()
    expect(expand).to_have_attribute("aria-pressed", "true")
    settled(page)
    assert panel.bounding_box()["width"] == pytest.approx(narrow, abs=0.5)


def test_an_answer_the_user_waits_for_grows_the_view_up_to_its_cap(browser, serve):
    """The agent's answer to the user's own last turn grows the thread's view to hold
    it: the field stays where it is, and the thread's head line, its name and presses,
    rises with the view's top. Past the view's cap the answer goes on below the
    fold behind New reply, with the user's own turn wholly in sight above it, its head
    included, and nothing of the answer showing below the press; a press brings the
    answer's start into sight. A reply that follows the agent's own turn below that
    fold moves nothing the user sees, so it joins there at once, as on a card; one that
    would move what is in sight is held behind the thread's notice
    (`test_held_news_reads_whole_among_the_thread_s_controls`)."""
    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir,
        "Walk me through the whole rollout: "
        + "which cohorts go first, and what holds the next wave back. " * 3,
    )
    page = floating(browser, url)

    def answer(text):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Claude",
                "parent": root,
                "revision": 1,
                "text": text,
            },
        )
        told(page)

    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(panel_view("thread"))
    messages = view.locator(".lf-msg")
    expect(messages).to_have_count(1)
    settled(page)
    seats = page.evaluate(SEATS)
    stood = page.evaluate(GROWTH)

    answer("Internal first. " + "The second wave waits for the alarms to hold. " * 3)
    expect(messages).to_have_count(2)
    settled(page)
    grown = page.evaluate(GROWTH)
    by = grown["view"] - stood["view"]
    assert by < -40, (stood, grown)
    assert grown["field"] == stood["field"]
    assert grown["bottom"] == stood["bottom"]
    assert risen(seats, page.evaluate(SEATS), by), (seats, by)
    assert grown["turn"][0] >= 0 and grown["turn"][1] >= 0, grown
    expect(view.locator(".lf-new-reply")).to_have_count(0)
    expect(page.locator(".lf-fp-head .lf-thread-news:visible")).to_have_count(0)

    write(field(page), "And the weekend?")
    with sending(page, "the reply"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect(messages).to_have_count(3)
    settled(page)

    answer("It would. " + "Someone stays on call through Sunday, and Monday too. " * 80)
    press = view.locator(".lf-new-reply")
    expect(press).to_have_text("New reply")
    expect(messages).to_have_count(4)
    settled(page)
    capped = page.evaluate(GROWTH)
    assert abs(capped["height"] - capped["cap"]) < 1, capped
    assert capped["field"] == stood["field"]
    # The user's turn stands wholly between the view's top and New reply's ground,
    # which reaches the view's foot, so nothing scrolls by under the press.
    assert capped["turn"][0] >= 0 and capped["turn"][1] >= 0, capped
    assert abs(capped["foot"] - capped["bottom"]) < 0.5, capped

    press.click()
    expect(press).to_have_count(0)
    settled(page)
    shown, box = messages.last.bounding_box(), view.bounding_box()
    assert box["y"] <= shown["y"] < box["y"] + box["height"] - 40, (shown, box)

    seats = page.evaluate(SEATS)
    read = page.evaluate(GROWTH)
    answer("One more thing: the alarms page the on-call too.")
    expect(messages).to_have_count(5)
    settled(page)
    expect(page.locator(".lf-fp-head .lf-thread-news:visible")).to_have_count(0)
    assert page.evaluate(SEATS) == seats
    assert page.evaluate(GROWTH)["turn"] == read["turn"]


def test_a_folded_status_keeps_its_reading_until_the_next_exposure(
    browser, serve, request
):
    """A clock tick cannot move tooltip words, and reopening reads current status. A
    notice answering a gesture still shows immediately."""
    from browser.threads import claim_for_codex

    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Can we simplify the logging?")
    claim_for_codex(serve.page_dir, request)
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press(".")
    progress = thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "Reading the diagnostic transport.",
        ephemeral=True,
        identity={"agent": "Codex", "session": "codex-thread"},
    )
    told(page)
    # The folded leaf's status is its preview (annotations/preview.js).
    peek = page.locator(PREVIEW)
    leaf = page.locator(".lf-fp-leaf")
    leaf.hover()
    expect(peek).to_contain_text("Reading the diagnostic transport.")
    words = peek.inner_text()
    before = peek.bounding_box()
    now = datetime.fromisoformat(progress["ts"]) + timedelta(minutes=1)

    # The response uses the same advanced time, so later state reads cannot
    # recalibrate the browser back across the shared clock's age boundary.
    def aged_state(route):
        response = route.fetch()
        state = response.json()
        state["now"] = now.isoformat()
        route.fulfill(response=response, json=state)

    page.route("**/api/state*", aged_state)
    page.clock.set_fixed_time(now)
    ticked(page)
    assert peek.inner_text() == words
    assert peek.bounding_box() == before
    page.mouse.move(5, 5)
    expect(peek).to_be_hidden()
    leaf.hover()
    expect(peek).to_contain_text("(1m ago)")
    # A hidden tab ends this exposure even when the pointer never leaves the leaf.
    page.evaluate("""() => {
      window.__lfTestVisibility = 'hidden';
      Object.defineProperty(document, 'visibilityState', {
        configurable: true, get: () => window.__lfTestVisibility,
      });
      document.dispatchEvent(new Event('visibilitychange'));
    }""")
    thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "Tracing the reply acknowledgements.",
        ephemeral=True,
        identity={"agent": "Codex", "session": "codex-thread"},
    )
    expect(peek).to_be_hidden()
    with page.expect_request("**/api/news"):
        page.evaluate("""() => {
          window.__lfTestVisibility = 'visible';
          document.dispatchEvent(new Event('visibilitychange'));
        }""")
    told(page)
    page.mouse.move(5, 5)
    leaf.hover()
    expect(peek).to_contain_text("Tracing the reply acknowledgements.")
    ticked(page)
    words = peek.inner_text()
    now += timedelta(minutes=1)
    page.clock.set_fixed_time(now)
    ticked(page)
    assert peek.inner_text() == words
    page.evaluate("async () => (await window.__lfCheckApi()).notice('Saved for later')")
    expect(page.locator(".lf-fp-peek")).to_have_text("Saved for later")


@pytest.mark.parametrize("route", ["finger", "key"])
def test_versions_opens_beside_the_version_the_page_shows(browser, serve, route):
    """Reopened from an older version, a list too long for the panel opens with the
    version shown in view, whichever way it opens, so Showing doesn't start out of
    sight. A key lands on the version before it, the one Versions offers, and a
    finger's opening leaves focus on the list."""
    url = serve(LONG_PAGE)
    note = "Moved the rollout decision into its own section. " * 3
    for revision in range(12):
        stamp_page(
            serve.page_dir,
            LONG_PAGE.replace("Paragraph 0.", f"Paragraph {revision} revised."),
            note,
        )
    finger = route == "finger"
    # Under a mouse a row holds one line, so a shorter window makes the list too long.
    context = browser.new_context(
        viewport={"width": 390, "height": 844 if finger else 480},
        has_touch=finger,
        is_mobile=finger,
    )
    page = open_page(browser, url, context=context)
    view = page.locator(panel_view("versions"))
    panel_menu(page, "versions", touch=finger)
    older = view.locator(".lf-fp-version > .lf-fp-item").filter(
        has_text=re.compile(r"^\s*v2\b")
    )
    older.tap() if finger else older.click()
    expect(page).to_have_url(re.compile(r"/versions/v2\b"))
    wait_until_ready(page)

    if finger:
        panel_menu(page, "versions", touch=True)
    else:
        page.locator("body").focus()
        page.keyboard.press("g")
        page.keyboard.press("Shift+V")
    panel_settled(page, view="versions")
    assert view.evaluate("view => view.scrollHeight > view.clientHeight")
    shown = view.locator(".lf-fp-version[data-lf-current]")
    expect(shown).to_contain_text("Showing")
    assert shown.evaluate("""row => {
      const list = row.closest('.lf-fp-view').getBoundingClientRect();
      const box = row.getBoundingClientRect();
      return box.top >= list.top - 0.5 && box.bottom <= list.bottom + 0.5;
    }""")
    offered = view.locator(".lf-fp-version > .lf-fp-item").last
    expect(offered if not finger else view).to_be_focused()


def test_an_older_version_says_so_in_the_row_and_one_press_opens_the_latest(
    browser, serve
):
    """While the page shows a version older than the latest, the field's words say which
    before the status, and its end offers Open latest in Comment's place, so nothing in
    the row moves and the leaf keeps its place; the press opens the latest, and the
    words and the press go with it: in place on a tab the agent has since revised, and
    from a version the user travelled back to, where the press wears its keys, Versions'
    `g V` and then its `l`, which make it too, leaving Versions."""
    url = serve(LONG_PAGE)
    page = floating(browser, url)
    latest = latest_press(page)
    marks = page.locator(".lf-fp-leaf")
    settled(page)
    seats = marks.bounding_box()
    expect(latest).to_have_count(0)

    # The agent revises the page under the open tab, which keeps what it shows.
    stamp_page(
        serve.page_dir, LONG_PAGE.replace("Paragraph 0.", "Paragraph zero."), "two"
    )
    told(page)
    expect(field(page)).to_have_attribute("placeholder", re.compile(r"^v1 of 2 · "))
    expect(latest).to_be_visible()
    settled(page)
    assert marks.bounding_box() == seats
    latest.click()
    expect(page.locator("main")).to_contain_text("Paragraph zero.")
    expect(latest).to_have_count(0)
    expect(field(page)).not_to_have_attribute("placeholder", re.compile(r"of 2"))

    panel_menu(page, "versions").locator(
        ".lf-fp-version:not([data-lf-current]) .lf-fp-label"
    ).click()
    expect(page).to_have_url(re.compile(r"/versions/v1\b"))
    expect(field(page)).to_have_attribute("placeholder", re.compile(r"^v1 of 2 · "))
    expect(latest).to_be_visible()
    expect(latest.locator("kbd")).to_have_text(["g", "V", "l"])
    page.locator("body").focus()
    page.keyboard.press("g")
    page.keyboard.press("Shift+v")
    panel_settled(page, view="versions")
    page.keyboard.press("l")
    expect(page).not_to_have_url(re.compile(r"/versions/"))
    expect(page.locator("main")).to_contain_text("Paragraph zero.")
    expect(latest).to_have_count(0)


def test_all_pages_in_the_menu_counts_the_pages_it_lists(
    browser, serve, other_leaf, live_leaf
):
    """The menu's All pages row says how many pages its view lists, this page
    included, and follows the page list while it stands open: a neighbour that closes leaves the count."""
    _, closing_dir = live_leaf("closing", "The closing leaf")
    page = floating(browser, serve(LONG_PAGE))
    all_pages_offered(page)
    row = panel_menu(page, "navigate").locator('.lf-fp-item[data-lf-row="leaves"]')
    expect(row.locator(".lf-fp-value")).to_have_text("3")
    declare(closing_dir, "idle")
    expect(row.locator(".lf-fp-value")).to_have_text("2")


def test_the_row_s_marks_and_presses_share_the_words_line(browser, serve):
    """Everything in the row stands on the one line the words are written on: the
    leaf at rest, Dictate as the user opens the field, and Send while
    they type, each centred on the field's last line of words, however many lines it
    holds. Send floats in the field's end corner, as an anchored comment box's does,
    and under a mouse the words take its column (drafts/test_send_corner.py follows
    Send out of their way)."""
    page = open_page(browser, serve(LONG_PAGE), init_script=EDITOR_ROOTS)
    settled(page)
    seats = page.evaluate(ROW_CENTRES)
    assert abs(seats["leaf"] - seats["line"]) < 0.5, seats
    field(page).click()
    settled(page)
    seats = page.evaluate(ROW_CENTRES)
    for mark in ("leaf", "dictate"):
        assert abs(seats[mark] - seats["line"]) < 0.5, (mark, seats)
    page.keyboard.type(
        "Could the rollback cover the weekend, and the mobile cohort as well, and"
        " every one of the regions the first wave reaches?"
    )
    settled(page)
    seats = page.evaluate(ROW_CENTRES)
    assert field(page).bounding_box()["height"] > 40, "the words wrapped"
    for mark in ("leaf", "send"):
        assert abs(seats[mark] - seats["line"]) < 0.5, (mark, seats)
    assert seats["press"]["right"] == pytest.approx(seats["field"], abs=1), seats
    column = field(page).evaluate(
        """host => window.editorRoots.get(host).querySelector('.cm-content')
          .getBoundingClientRect().right"""
    )
    assert column > seats["press"]["left"], (column, seats)


def test_a_view_s_close_ends_its_controls_and_the_field_the_row(browser, serve):
    """With a view open, its Close ends its controls and the field reaches the leaf at
    the row's end, at rest and widened alike, so widening the field leaves Close beside
    the controls."""
    page = floating(browser, serve(LONG_PAGE))
    page.keyboard.press("g")
    page.keyboard.press("Shift+T")
    expect(page.locator(panel_view("threads"))).to_be_visible()
    field(page).click()
    page.keyboard.type("A line of words long enough to wrap in the panel's field, " * 4)
    close = page.locator(".lf-fp-close")
    expect(close).to_have_count(1)
    expect(page.locator(".lf-fp-controls .lf-fp-close")).to_be_visible()

    def reaches_the_leaf():
        settled(page)
        leaf = page.locator(".lf-fp-leaf").bounding_box()
        words = page.locator(".lf-fp-field").bounding_box()
        assert leaf["x"] - (words["x"] + words["width"]) < 12, (leaf, words)

    reaches_the_leaf()
    page.locator(".lf-fp-expand").click()
    expect(page.locator(".lf-fp-controls .lf-fp-close")).to_be_visible()
    reaches_the_leaf()
    page.locator(".lf-fp-expand").click()
    expect(page.locator(".lf-fp-controls .lf-fp-close")).to_be_visible()
    close.click()
    expect(page.locator(panel_view("threads"))).to_be_hidden()


def test_a_long_reply_takes_its_room_from_the_thread_s_top(browser, serve):
    """Once the panel reaches the window's top, each line a reply gains takes its room
    from the open thread's view, which gives way at its top and keeps the message the
    user is answering beside the field; taking the lines away gives the room back the
    same way. A view that kept its scroll and gave way at its foot would let a long
    reply cover the agent's last line."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Which job comes first?")
    thread_model.post_reply(
        serve.page_dir, {"responds": root}, "The mounts come first. " * 120
    )
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(panel_view("thread"))
    expect(view.locator(".lf-msg")).to_have_count(2)
    view.hover()
    page.mouse.wheel(0, 10000)
    page.wait_for_function(
        "v => v.scrollTop > 0 && v.scrollTop + v.clientHeight >= v.scrollHeight - 1",
        arg=view.element_handle(),
    )
    settled(page)
    beside = """v => v.getBoundingClientRect().bottom
      - [...v.querySelectorAll('.lf-msg')].at(-1).getBoundingClientRect().bottom"""
    stood = view.evaluate(beside)
    room = view.evaluate("v => v.clientHeight")
    field(page).click()
    page.keyboard.type("Line 1")
    for n in range(2, 13):
        page.keyboard.press("Shift+Enter")
        page.keyboard.type(f"Line {n}")
        settled(page)
        assert view.evaluate(beside) == pytest.approx(stood, abs=1), n
    assert view.evaluate("v => v.clientHeight") < room - 60
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.press("Backspace")
    settled(page)
    assert view.evaluate("v => v.clientHeight") == room
    assert view.evaluate(beside) == pytest.approx(stood, abs=1)


def test_all_pages_is_a_view_of_the_panel(browser, serve, other_leaf):
    """All pages, from the leaf's menu under Navigate or by `g L`, opens a view above
    the row listing the pages live on this machine, this one first and marked as this
    page, each other one a link that opens it in a tab of its own. `g L` puts it away
    again."""
    page = floating(browser, serve(LONG_PAGE))
    all_pages_offered(page)
    pages = page.locator(panel_view("leaves"))
    panel_menu(page, "navigate").locator('.lf-fp-item[data-lf-row="leaves"]').click()
    expect(page.locator(".lf-fp-title")).to_have_text("All pages")
    expect(page.locator(".lf-fp-controls")).to_be_hidden()
    expect(page.locator(".lf-fp-head .lf-fp-close")).to_be_visible()
    rows = pages.locator(".lf-fp-page")
    expect(rows).to_have_count(2)
    expect(rows.first).to_contain_text("This page")
    expect(rows.first).not_to_have_attribute("href", re.compile("."))
    other = pages.locator("a.lf-fp-page", has_text="The other leaf")
    expect(other).to_have_attribute("target", "_blank")
    page.keyboard.press("Escape")
    expect(pages).to_have_count(0)

    page.locator("body").focus()
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    expect(pages).to_be_visible()
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    expect(pages).to_have_count(0)


def test_a_finger_reads_a_neighbouring_page_s_whole_account(
    browser, serve, live_leaf, tmp_path
):
    """All pages cuts a row's words to the panel's width and says the whole account on
    hover, where a finger never is. Under one, each row's title and what its agent is
    doing stand whole, with where its session works under them, which is what tells two
    pages of one title apart."""
    title = (
        "The other leaf, whose title runs well past what one line of the panel holds"
    )
    live_leaf("other", title)
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, serve(LONG_PAGE), context=context)
    all_pages_offered(page)
    panel_menu(page, "navigate", touch=True).locator(
        '.lf-fp-item[data-lf-row="leaves"]'
    ).tap()
    panel_settled(page, view="leaves")
    row = page.locator(f"{panel_view('leaves')} a.lf-fp-page")
    expect(row.locator(".lf-fp-label")).to_have_text(title)
    expect(row.locator(".lf-fp-page-rest")).to_have_text(str(tmp_path / "other-work"))
    expect(row.locator(".lf-fp-page-rest")).to_be_visible()
    for words in (".lf-fp-label", ".lf-fp-value", ".lf-fp-page-rest"):
        assert row.locator(words).evaluate(
            "el => el.scrollWidth <= el.clientWidth + 1"
            " && el.scrollHeight <= el.clientHeight + 1"
        ), words


def test_a_sample_shows_its_threads_in_its_panel(browser, serve):
    """A live sample's host asking for the panel (`surface: "panel"`) shows the thread
    it names in the child's panel, or its Threads with none named. A narrow Full view
    keeps resolved threads, search and Close reachable inside the child's panel."""
    url = serve(
        titled_page(
            "A sample's threads",
            """
<style>#sample { height: 400px; }</style><h1>Containing page</h1>
<button id="show-thread" type="button">Show the thread</button>
<button id="show-threads" type="button">Show Threads</button>
<script id="history" type="application/json">
[{"id":"question","kind":"comment","author":"user","text":"Can we schedule lunch?"},
 {"id":"answered","kind":"comment","author":"user","text":"Is the room booked?"},
 {"id":"settled","kind":"resolve","author":"user","parent":"answered"}]
</script>
<lf-sample id="sample" window>
  <template id="sample-page" data-sample data-sample-events="history">
    <h1>Schedule</h1><p>Lunch is the remaining question.</p>
  </template>
</lf-sample>
<script type="module">
  const sample = document.querySelector('#sample');
  document.querySelector('#show-thread').onclick = () =>
    sample.showThread('question', {surface: 'panel'});
  document.querySelector('#show-threads').onclick = () =>
    sample.showThread(undefined, {surface: 'panel'});
</script>
    """,
        )
    )
    page = open_page(browser, url)
    page.locator("#sample").evaluate("async sample => await sample.ready")
    child = page.frame_locator("#sample iframe")
    page.locator("#show-thread").click()
    reader = child.locator(panel_view("thread"))
    expect(reader.locator(".lf-msg")).to_contain_text("Can we schedule lunch?")
    # Seat the embedded panel above the containing page's floating controls.
    page.locator("#sample").evaluate(
        "element => element.scrollIntoView({block: 'start'})"
    )
    child.locator(".lf-fp-close").click()
    expect(reader).to_have_count(0)
    page.locator("#show-threads").click()
    expect(child.locator(panel_view("threads"))).to_be_visible()
    resized(page, 390, 844)
    page.get_by_role("button", name="Full view", exact=True).click()
    controls = child.locator(".lf-fp-controls")
    close = child.get_by_role("button", name="Close", exact=True)
    bounds = controls.bounding_box()
    button = close.bounding_box()
    assert bounds["x"] <= button["x"]
    assert button["x"] + button["width"] <= bounds["x"] + bounds["width"]
    threads = child.locator(panel_view("threads"))
    expect(threads.locator(".lf-fp-thread:not([data-lf-resolved])")).to_contain_text(
        "Can we schedule lunch?"
    )
    resolved = dev_browser.show_resolved(child)
    expect(resolved).to_contain_text("Is the room booked?")
    resolved.click()
    expect(reader.locator(".lf-msg")).to_contain_text("Is the room booked?")
    expect(child.get_by_role("button", name="Reopen", exact=True)).to_be_visible()
    child.get_by_role("button", name="Back to Threads").click()
    expect(threads).to_be_visible()
    child.get_by_role("button", name="Find a thread or message", exact=True).click()
    search = child.get_by_role("searchbox", name="Search threads")
    assert search.bounding_box()["width"] > 0
    search.fill("schedule")
    expect(child.locator(".lf-fp-thread")).to_have_count(1)
    expect(child.locator(".lf-fp-thread")).to_contain_text("Can we schedule lunch?")
    search.fill("booked")
    expect(child.locator(".lf-fp-thread")).to_have_count(1)
    expect(child.locator(".lf-fp-thread")).to_contain_text("Is the room booked?")
    child.get_by_role("button", name="Close search", exact=True).click()
    expect(threads.locator(".lf-fp-thread")).to_have_count(2)
    close.click()
    expect(child.locator(panel_view("threads"))).to_have_count(0)


def test_lines_removed_below_the_field_s_cap_leave_the_rest_in_place(browser, serve):
    """A draft past the field's cap scrolls inside it; deleting its last lines until
    the rest fits stops that scroll, and the lines still shown stay where they stood
    on the tween's first frame, then travel down as the lines scrolled away come into
    view, carrying on from where they are drawn when another line goes midway."""
    page = open_page(browser, serve(LONG_PAGE), init_script=EDITOR_ROOTS)
    page.emulate_media(reduced_motion="no-preference")
    field(page).click()
    page.keyboard.type("Line 1")
    lines = 1
    while not field(page).evaluate("box => box.scrollTop > 40"):
        lines += 1
        page.keyboard.press("Shift+Enter")
        page.keyboard.type(f"Line {lines}")
    for extra in range(lines + 1, lines + 5):
        page.keyboard.press("Shift+Enter")
        page.keyboard.type(f"Line {extra}")
    settled(page)
    shown = f"Line {lines - 4}"
    where = """(host, words) => [...window.editorRoots.get(host).querySelectorAll('.cm-line')]
      .find((line) => line.textContent === words).getBoundingClientRect().top"""
    stood = field(page).evaluate(where, shown)
    hold_motion(page)
    # Back past the line that first made the field scroll, so the rest fits.
    for _ in range(7):
        page.keyboard.press("Shift+ArrowUp")
    page.keyboard.press("Backspace")
    held_motion(page)
    assert field(page).evaluate("box => box.scrollHeight <= box.clientHeight")
    assert field(page).evaluate(where, shown) == pytest.approx(stood, abs=1)
    page.evaluate(SEEK_HELD, 60)
    midway = field(page).evaluate(where, shown)
    page.keyboard.press("Shift+ArrowUp")
    page.keyboard.press("Backspace")
    # The second deletion's tween, held at its start beside the first's, cancelled.
    page.wait_for_function(
        "() => __lfHeld.some(motion => motion.playState !== 'idle'"
        " && motion.currentTime === 0 && motion.effect?.target?.matches?.('.lf-fp-ground'))"
    )
    assert field(page).evaluate(where, shown) == pytest.approx(midway, abs=1)
    finish_held(page)
    assert field(page).evaluate(where, shown) > stood + 20


def test_a_thread_s_keys_answer_in_its_view(browser, serve):
    """The thread open in the panel answers the keys a card in Threads does, though its
    reply is the field and its Resolve stands on the view's head line: Enter on the
    view puts the caret back in the reply with its words, and so does `c`, from the
    view an Escape left the user on and from a message in it, the thread staying open.
    `r` resolves the thread from the view, a message in it or its Resolve and moves the
    user on, here back to Threads with no other thread open, ⌘Z takes the resolve back
    and opens the thread again, Enter on a resolved thread puts the caret in its reply,
    which a reply reopens, `r` there reopens it, and `e` on a message opens the agent's
    reactions."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Is the window long enough?")
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": root,
            "revision": 1,
            "text": "Forty-eight hours covers the first cohort.",
        },
    )
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    thread = page.locator(panel_view("thread"))
    settle = page.locator(".lf-fp-thread-controls :is(.lf-resolve, .lf-reopen)")
    expect(thread).to_be_visible()
    field(page).click()
    page.keyboard.type("Make it the weekend.")
    page.keyboard.press("Escape")
    expect(thread).to_be_focused()

    page.keyboard.press("Enter")
    expect(field(page)).to_be_focused()
    expect(field(page)).to_have_attribute("name", "reply")
    expect(field(page)).to_have_js_property("value", "Make it the weekend.")
    expect(thread).to_be_visible()

    page.keyboard.press("Escape")
    expect(thread).to_be_focused()
    page.keyboard.press("c")
    expect(field(page)).to_be_focused()
    expect(field(page)).to_have_attribute("name", "reply")
    expect(field(page)).to_have_js_property("value", "Make it the weekend.")
    expect(thread).to_be_visible()

    thread.locator(".lf-msg").first.focus()
    page.keyboard.press("c")
    expect(field(page)).to_be_focused()
    expect(field(page)).to_have_attribute("name", "reply")
    expect(thread).to_be_visible()

    page.keyboard.press("Escape")
    expect(thread).to_be_focused()
    threads = page.locator(panel_view("threads"))
    with sending(page, "the resolve"):
        page.keyboard.press("r")
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "resolve"
    expect(threads).to_be_visible()
    undo(page)
    expect(thread).to_be_focused()
    expect(settle).to_have_accessible_name("Resolve thread")

    # A click on a message's words stands on the thread drawing it.
    message = thread.locator(".lf-page-thread", has_text="Is the window long enough?")
    message.click()
    expect(message).to_be_focused()
    page.keyboard.press("e")
    strip = thread.locator(".lf-msg[data-lf-author=agent] > .lf-react-strip")
    expect(strip.locator(".lf-react-palette:popover-open")).to_have_count(1)
    page.keyboard.press("Escape")
    expect(strip.locator(".lf-react-palette:popover-open")).to_have_count(0)
    message.click()
    with sending(page, "the resolve from a message"):
        page.keyboard.press("r")
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "resolve"
    expect(threads).to_be_visible()

    # A resolved thread opened from under Threads' Resolved heading keeps its reply.
    show_resolved(page).first.click()
    expect(settle).to_have_accessible_name("Reopen")
    thread.focus()
    page.keyboard.press("Enter")
    expect(field(page)).to_be_focused()
    expect(field(page)).to_have_attribute("name", "reply")
    expect(settle).to_have_accessible_name("Reopen")
    page.keyboard.press("Escape")
    expect(thread).to_be_focused()
    with sending(page, "the reopen"):
        page.keyboard.press("r")
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "unresolve"
    expect(settle).to_have_accessible_name("Resolve thread")


def test_the_field_reads_a_status_it_cuts_short_whole(browser, serve):
    """A finger holding the panel's field reads the status whole where the field cuts it
    short, as a phone's field cuts most statuses, and the hold presses nothing; a
    pointer resting on the field reads it too. A status the field shows whole previews
    nothing, whoever says it, so the row repeats no words over the page and a hold
    there keeps the platform's own menu. A draft, which hides the status, previews
    nothing either."""
    url = serve(LONG_PAGE)
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    context.clock.install()
    phone = open_page(browser, url, context=context)
    cdp = context.new_cdp_session(phone)

    def hold():
        box = field(phone).bounding_box()
        point = {"x": box["x"] + 40, "y": box["y"] + box["height"] / 2}
        cdp.send(
            "Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [point]}
        )
        dwelt(phone, "HOLD")
        menu = long_press(phone, point)
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        rendered(phone)
        return menu

    # Leaf's own words, the status of a page no agent has opened.
    expect(field(phone)).to_have_attribute("placeholder", re.compile(r"^Away\b"))
    rendered(phone)
    assert hold() is True, "a hold on whole words kept the platform's menu shut"
    expect(phone.locator(PREVIEW)).to_be_hidden()
    # Chromium's injected touch, ending where no hold read, presses the field.
    field(phone).blur()

    working(serve.page_dir, CUT_STATUS)
    expect(field(phone)).to_have_attribute(
        "placeholder", re.compile(re.escape(CUT_STATUS))
    )
    assert hold() is False, "the platform's menu opened"
    expect(phone.locator(PREVIEW)).to_have_text(CUT_STATUS)
    expect(field(phone)).not_to_be_focused()
    context.close()

    page = floating(clocked(browser), url)
    preview = page.locator(PREVIEW)
    field(page).hover()
    dwelt(page)
    expect(preview).to_have_text(CUT_STATUS)

    page.mouse.move(5, 5)
    working(serve.page_dir, "Drafting the rollout")
    expect(field(page)).to_have_attribute(
        "placeholder", re.compile("^Drafting the rollout ")
    )
    field(page).hover()
    dwelt(page)
    expect(preview).to_be_hidden()

    page.mouse.move(5, 5)
    working(serve.page_dir, CUT_STATUS)
    expect(field(page)).to_have_attribute(
        "placeholder", re.compile(re.escape(CUT_STATUS))
    )
    write(field(page), "Keep my unfinished question")
    # The caret elsewhere, the field's words are the status again, under the draft.
    page.mouse.click(5, 5)
    field(page).hover()
    dwelt(page)
    expect(preview).to_be_hidden()
