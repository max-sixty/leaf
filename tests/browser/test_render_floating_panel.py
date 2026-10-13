"""The floating panel: Leaf's chrome as one box over the page's foot, where the reader
chose it (`lf-chrome`, prepaint.js), in place of the banner and the bottom bar.

Each test is one journey a user takes through the panel, which the suite's pages
choose here, since they otherwise read with the bars (`watched`):
writing a page comment and replying in the same field, settling the thread, finding
threads and taking in news, answering asks, travelling between versions, and
folding the panel to the leaf in the window's corner and back."""

import re

import pytest
from interact_support import append_carried_log_record, declare_idle, working
from leaf import event_log as events_model
from model_folds import leaf_page
from playwright.sync_api import expect
from render_cases_interaction import panel_comment
from render_harness import LONG_PAGE, open_page, sending, stamp_page, told, write

from browser.test_render_controls import leaf_page as titled_page

# A sample's child is an opaque origin with no storage, so the script asks nothing of it.
FLOATING = "try { localStorage.setItem('lf-chrome', 'floating') } catch {}"
SIGN_OFF = LONG_PAGE.replace(
    "<title>long</title>",
    '<title>long</title><meta name="lf-review" content="sign-off">',
)
ASK_PAGE = leaf_page(
    "ask",
    """<h1 id="t">Ask</h1>
<lf-ask id="schema-decision"><h3>How should the schema migrate?</h3>
<lf-options id="schema" choose>
  <lf-option id="shim"><strong>Shim the old schema</strong> Fastest to ship.</lf-option>
  <lf-option id="stage"><strong>Migrate in stages</strong> Table by table.</lf-option>
</lf-options></lf-ask>
<lf-ask id="queue-decision"><h3>Which queue takes the retries?</h3>
<lf-options id="queues" choose>
  <lf-option id="fast"><strong>The fast queue</strong> Shared.</lf-option>
  <lf-option id="slow"><strong>The slow queue</strong> Its own.</lf-option>
</lf-options></lf-ask>""",
)


def floating(browser, url):
    page = open_page(browser, url, init_script=FLOATING)
    expect(page.locator(".lf-floating-panel")).to_be_visible()
    return page


def settled(page):
    """Wait until the panel's motion has finished, so a box read is where it rests."""
    page.wait_for_function(
        "() => ['.lf-floating-panel', '.lf-fp-ground'].every(s =>"
        " !document.querySelector(s).getAnimations({subtree: true}).length)"
    )


def field(page):
    """The editor standing in the panel's field now: the page's, or a thread's."""
    return page.locator(".lf-fp-field leaf-text")


def test_one_field_starts_a_thread_takes_its_reply_and_settles_it(browser, serve):
    """The field clicked at rest is the field written in. Sending a page comment opens
    its new thread above the row, the same field now replying there, and the thread is
    resolved and reopened from the thread's head. The focused field names where the
    words go, and once they hide that, the line above it does. The banner and the
    bottom bar are gone, and Escape puts the thread away."""
    page = floating(browser, serve(LONG_PAGE))
    expect(page.locator(".lf-banner")).to_be_hidden()
    expect(page.locator(".lf-shortcut-bar")).to_be_hidden()

    write(field(page), "Could the rollback cover the weekend?")
    expect(page.locator(".lf-fp-context")).to_contain_text("Comment on the page")
    with sending(page, "the page comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    comment = events_model.read_events(serve.page_dir)[-1]
    assert (comment["kind"], comment["text"]) == (
        "comment",
        "Could the rollback cover the weekend?",
    )
    expect(page.locator(".lf-fp-view[data-view=thread]")).to_contain_text(
        "Could the rollback cover the weekend?"
    )
    expect(field(page)).to_be_focused()
    expect(field(page)).to_have_attribute(
        "placeholder", re.compile("^Reply in this thread")
    )

    write(field(page), "And the mobile cohort too.")
    expect(page.locator(".lf-fp-context")).to_contain_text("Reply in")
    with sending(page, "the reply"):
        page.keyboard.press("ControlOrMeta+Enter")
    reply = events_model.read_events(serve.page_dir)[-1]
    assert (reply["kind"], reply["parent"]) == ("reply", comment["id"])
    # The reply the user just sent stands in the thread's view, which grew room for it.
    page.wait_for_function(
        """() => {
            const view = document.querySelector('.lf-fp-view[data-view=thread]');
            const sent = [...view.querySelectorAll('.lf-msg')].find(m =>
                m.textContent.includes('And the mobile cohort too.'));
            if (!sent) return false;
            const v = view.getBoundingClientRect(), r = sent.getBoundingClientRect();
            return r.top >= v.top - 1 && r.bottom <= v.bottom + 1;
        }"""
    )
    # The box empties as the reply leaves, and the counts take Send's place again.
    expect(page.locator(".lf-fp-send")).to_be_hidden()
    expect(page.locator(".lf-fp-on-user")).to_be_visible()

    settle = page.locator(".lf-fp-settle")
    with sending(page, "the resolve"):
        settle.click()
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "resolve"
    expect(settle).to_have_text(re.compile("Reopen"))
    with sending(page, "the reopen"):
        settle.click()
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "unresolve"
    expect(settle).to_have_text(re.compile("Resolve"))

    field(page).focus()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-fp-view")).to_have_count(0)


def test_threads_filter_in_place_and_hold_news_until_asked(browser, serve):
    """The thread mark opens Threads at Unread while a thread has news, and the
    inventory keeps its height whichever filter stands, and as a thread arrives, so the
    filter just pressed, and Close at the view's head, stay under the pointer. A reply
    that arrives while its thread is open waits behind New reply."""
    url = serve(LONG_PAGE, comments=3)
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
    page.locator(".lf-fp-threads").click()
    inventory = page.locator(".lf-fp-view[data-view=threads]")
    expect(page.locator(".lf-fp-filters [aria-pressed=true]")).to_have_text(
        re.compile(r"^\s*Unread\b")
    )
    expect(inventory.locator(".lf-fp-thread")).to_have_count(1)
    settled(page)
    unread_box = inventory.bounding_box()
    all_filter = page.locator(".lf-fp-filters button", has_text="Open")
    before = all_filter.bounding_box()
    all_filter.click()
    expect(inventory.locator(".lf-fp-thread")).to_have_count(4)
    settled(page)
    assert inventory.bounding_box() == unread_box
    assert all_filter.bounding_box() == before
    close = page.locator(".lf-fp-close").bounding_box()
    panel_comment(serve.page_dir, "Who watches the weekend?")
    told(page)
    expect(inventory.locator(".lf-fp-thread")).to_have_count(5)
    settled(page)
    assert page.locator(".lf-fp-close").bounding_box() == close

    inventory.locator(".lf-fp-thread", has_text="Is the window long enough?").click()
    reader = page.locator(".lf-fp-view[data-view=thread]")
    expect(reader.locator(".lf-msg")).to_have_count(2)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": root,
            "revision": 1,
            "text": "The weekend would need someone on call.",
        },
    )
    told(page)
    held = reader.locator(".lf-primary-news:visible")
    expect(held).to_be_visible()
    expect(reader.locator(".lf-msg")).to_have_count(2)
    held.click()
    expect(reader.locator(".lf-msg")).to_have_count(3)


THREAD_FIT = """() => {
  const view = document.querySelector('.lf-fp-view[data-view=thread]');
  const box = view.getBoundingClientRect();
  const messages = [...view.querySelectorAll('.lf-msg')];
  return {
    height: box.height,
    scrolls: view.scrollHeight > view.clientHeight + 1,
    below: box.bottom - messages.at(-1).getBoundingClientRect().bottom,
    first: messages[0].getBoundingClientRect().top,
    panel: document.querySelector('.lf-fp-card').getBoundingClientRect().top,
  };
}"""


def test_a_thread_s_view_is_as_tall_as_its_messages(browser, serve):
    """An opened view is as tall as what it holds. A page comment opens its thread one
    message tall; a reply that arrives waits behind New reply, moving nothing, and
    opening it grows the view to show it whole. A long thread reads in most of the
    window's height, leaving a band of the page above the panel, before it scrolls."""
    url = serve(LONG_PAGE)
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
    write(field(page), "Could the rollback cover the weekend?")
    with sending(page, "the page comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    root = events_model.read_events(serve.page_dir)[-1]["id"]
    view = page.locator(".lf-fp-view[data-view=thread]")
    expect(view.locator(".lf-msg")).to_have_count(1)
    settled(page)
    short = page.evaluate(THREAD_FIT)
    assert not short["scrolls"]
    assert short["below"] < 16, short

    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": root,
            "revision": 1,
            "text": "It would, with someone on call.",
        },
    )
    told(page)
    held = view.locator(".lf-primary-news:visible")
    expect(held).to_be_visible()
    assert page.evaluate(THREAD_FIT) == short
    held.click()
    expect(view.locator(".lf-msg")).to_have_count(2)
    settled(page)
    grown = page.evaluate(THREAD_FIT)
    assert grown["height"] > short["height"], (short, grown)
    assert not grown["scrolls"]
    assert grown["below"] < 16, grown

    page.keyboard.press("Escape")
    page.locator(".lf-fp-threads").click()
    page.locator(".lf-fp-filters button", has_text="Open").click()
    page.locator(".lf-fp-thread", has_text="Walk me through the whole rollout.").click()
    expect(view.locator(".lf-msg")).to_have_count(9)
    settled(page)
    long = page.evaluate(THREAD_FIT)
    assert long["height"] > 600, long
    assert long["panel"] >= 100, long


def test_an_open_view_covers_the_page_beneath_it(browser, serve):
    """What a view open above the row stands over is hidden from every reading of what
    the user sees (geometry.js, `declareOccluder`): a paragraph under it reads as seen
    only beside it, and whole again once the view is put away."""
    page = floating(browser, serve(LONG_PAGE, comments=12))
    seen = """async () => {
      const {seenRect} = await window.__lfCheckApi();
      const view = document.querySelector('.lf-fp-view').getBoundingClientRect();
      const under = [...document.querySelectorAll('main p')].find(p => {
        const box = p.getBoundingClientRect();
        return box.top > view.top + 20 && box.bottom < view.bottom - 20;
      });
      window.under = under;
      const shown = seenRect(under, new Map());
      return {view: {left: view.left, top: view.top, right: view.right,
                     bottom: view.bottom}, shown};
    }"""
    page.locator(".lf-fp-threads").click()
    page.locator(".lf-fp-filters button", has_text="Open").click()
    expect(page.locator(".lf-fp-thread")).to_have_count(12)
    settled(page)
    reading = page.evaluate(seen)
    view, shown = reading["view"], reading["shown"]
    assert shown, reading
    assert shown["right"] <= view["left"] or shown["left"] >= view["right"], reading

    page.keyboard.press("Escape")
    expect(page.locator(".lf-fp-view")).to_have_count(0)
    whole = page.evaluate(
        """async () => {
          const {seenRect} = await window.__lfCheckApi();
          const box = window.under.getBoundingClientRect();
          const shown = seenRect(window.under, new Map());
          return shown.right - shown.left >= box.width - 1;
        }"""
    )
    assert whole


def test_a_reader_who_chose_nothing_reads_with_the_classic_chrome(browser, serve):
    """A reader without a chrome preference sees the banner and bottom bar. An unknown
    stored value stands for no choice, overriding the test suite's own preference."""
    page = open_page(
        browser,
        serve(LONG_PAGE),
        init_script="try { localStorage.setItem('lf-chrome', '') } catch {}",
    )
    expect(page.locator(".lf-floating-panel")).to_be_hidden()
    expect(page.locator(".lf-banner")).to_be_visible()
    expect(page.locator(".lf-shortcut-bar")).to_be_visible()


def test_a_page_s_own_conversation_reader_takes_the_panel_s_threads(browser, serve):
    """A package that draws the page's conversations itself keeps that place under the
    panel (application.js, `registerThreadPresentation`, `yields`): the page starts
    without a fault, and a thread opened from the panel's Threads opens in the
    package's reader rather than above the row."""
    from browser.test_render_application_boundary import package_workspace

    page = floating(browser, package_workspace(serve))
    workspace = page.locator("#workspace")
    page.locator(".lf-fp-threads").click()
    inventory = page.locator(".lf-fp-view[data-view=threads]")
    page.locator(".lf-fp-filters button", has_text="Open").click()
    inventory.locator(".lf-fp-thread", has_text="Keep it concise.").click()
    expect(workspace.get_by_text("One paragraph.")).to_be_visible()
    expect(page.locator(".lf-fp-view[data-view=thread]")).to_have_count(0)
    expect(inventory).to_have_count(0)


def test_a_conversation_reader_arriving_later_takes_the_open_thread(browser, serve):
    """A page's own reader registered while the panel shows a thread takes that thread
    (application.js, `yielded`): the panel's view goes and the reader is asked to show
    it, at the message the user stood on, rather than the panel standing open on a
    conversation it no longer draws."""
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Is the window long enough?")
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(".lf-fp-view[data-view=thread]")
    expect(view.locator(".lf-msg")).to_contain_text("Is the window long enough?")
    # The user stands on a message, which goes with the panel's reader.
    view.get_by_role("button", name="Edit message").focus()
    stood_on = view.locator(".lf-msg").first.get_attribute("data-message")
    assert stood_on
    page.evaluate(
        """async () => {
          const api = await window.__lfWidgetApi();
          const host = document.createElement('div');
          document.querySelector('main').append(host);
          window.revealed = [];
          api.registerThreadPresentation(host, {
            render: () => {},
            reveal: (key, request) => { window.revealed.push(request); },
          });
        }"""
    )
    expect(view).to_have_count(0)
    page.wait_for_function("() => window.revealed.length === 1")
    # It takes the user's place too: the message they stood on, with focus.
    asked = page.evaluate(
        "() => ({focus: window.revealed[0].focus, part: window.revealed[0].part,"
        " message: window.revealed[0].message})"
    )
    assert asked["focus"] is not False
    assert asked["part"] == "message"
    assert asked["message"] == stood_on


def test_a_reader_arriving_later_leaves_focus_the_user_moved_elsewhere(browser, serve):
    """The reader taking the panel's thread takes the user's place in it only where they
    stood in the panel: focus they moved to the page stays there."""
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Is the window long enough?")
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    expect(page.locator(".lf-fp-view[data-view=thread]")).to_be_visible()
    page.evaluate(
        """async () => {
          const box = document.createElement('input');
          box.id = 'elsewhere';
          document.querySelector('main').prepend(box);
          box.focus();
          const api = await window.__lfWidgetApi();
          const host = document.createElement('div');
          document.querySelector('main').append(host);
          api.registerThreadPresentation(host, { render: () => {}, reveal: () => {} });
        }"""
    )
    expect(page.locator(".lf-fp-view[data-view=thread]")).to_have_count(0)
    expect(page.locator("#elsewhere")).to_be_focused()


def test_the_empty_field_says_the_agent_s_status_until_the_caret_is_in(browser, serve):
    """At rest the empty field says what the agent is doing, in the banner's words and
    dimmer than anything written there, and while the work runs it carries the one sheen
    that marks work under way, standing still under reduced motion and once the work
    ends. Clicking in gives the placeholder to where the words go and the line above to
    who they go to; once words hide the placeholder, that line names where as well."""
    url = serve(LONG_PAGE)
    working(serve.page_dir, "Drafting the rollout")
    page = floating(browser, url)
    status = re.compile(r"^Agent working — Drafting the rollout")
    expect(field(page)).to_have_attribute("placeholder", status)
    # The sheen runs on the field's placeholder, inside the field's closed tree, where
    # no animation list reaches: the words it paints over turn to their gradient, and
    # the field reads differently from one moment to the next.
    words = page.locator(".lf-fp-field .lf-compose-placeholder > span")
    ink = """node => getComputedStyle(node).color"""

    def sheen(running):
        page.wait_for_function(
            """running => (getComputedStyle(document.querySelector(
              '.lf-fp-field .lf-compose-placeholder > span')).color
              === 'rgba(0, 0, 0, 0)') === running""",
            arg=running,
        )

    sheen(True)
    box = page.locator(".lf-fp-field").bounding_box()
    first = page.screenshot(clip=box)
    page.wait_for_timeout(400)
    assert page.screenshot(clip=box) != first, "the working status stands still"
    # Still under reduced motion, in a face well short of the ink words are written in.
    page.emulate_media(reduced_motion="reduce")
    sheen(False)
    alpha = float(re.search(r"/\s*([\d.]+)\)$", words.evaluate(ink)).group(1))
    assert alpha < 0.5, f"the resting status reads at {alpha:.0%} of ink"
    page.emulate_media(reduced_motion="no-preference")
    sheen(True)

    field(page).click()
    expect(field(page)).to_have_attribute(
        "placeholder", re.compile("^Comment on the page")
    )
    sheen(False)
    destination = page.locator(".lf-fp-dest")
    expect(destination).to_have_text("To Agent")
    page.keyboard.type("Could")
    expect(destination).to_have_text("Comment on the page · to Agent")
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.press("Backspace")
    expect(destination).to_have_text("To Agent")

    page.mouse.click(5, 5)
    expect(field(page)).to_have_attribute("placeholder", status)
    sheen(True)
    declare_idle(serve.page_dir)
    told(page)
    expect(field(page)).not_to_have_attribute("placeholder", status)
    sheen(False)


def test_a_notice_stays_in_sight_over_words_in_the_field(browser, serve):
    """A passing notice is said in the empty field's place, and once the field holds
    words, which hide that, on the line above it, so a refused send's reason is seen
    beside the words it returned; on a folded panel, the leaf's peek says it."""
    page = floating(browser, serve(LONG_PAGE))
    say = """async (text) => (await window.__lfWidgetApi())
      .notice(text)"""
    page.evaluate(say, "Saved for later")
    expect(field(page)).to_have_attribute(
        "placeholder", re.compile(r"^Saved for later")
    )
    write(field(page), "Could the rollback cover the weekend?")
    page.evaluate(say, "Not sent: the page is offline")
    expect(page.locator(".lf-fp-dest")).to_have_text("Not sent: the page is offline")

    # Folded to the leaf, the panel has no field, and the leaf's peek says it.
    page.locator("body").focus()
    page.keyboard.press(".")
    expect(page.locator(".lf-floating-panel")).to_have_attribute("data-rest", "mark")
    page.evaluate(say, "Reconnected")
    expect(page.locator(".lf-fp-peek")).to_be_visible()
    expect(page.locator(".lf-fp-peek")).to_have_text("Reconnected")


def test_question_mark_opens_the_command_reference_at_once(browser, serve):
    """Under the panel no shortcut bar is drawn to expand, so the first `?` opens the
    command reference."""
    page = floating(browser, serve(LONG_PAGE))
    page.locator("body").focus()
    page.keyboard.press("?")
    expect(page.locator(".lf-command-reference")).to_be_visible()


def test_the_room_the_page_shows_stands_between_the_walk_and_the_panel(browser, serve):
    """What the page reveals, places and reports as shown keeps to the room the window's
    chrome leaves (geometry.js, `shownWindow`): under the walk's position, which stands at
    the window's head, and over the panel at its foot, as it kept under the banner and over
    the bottom bar."""
    page = floating(browser, serve(ASK_PAGE))
    room = """async () => {
      const shown = (await window.__lfWidgetApi()).shownWindow();
      return {top: shown.top, bottom: shown.bottom};
    }"""
    foot = page.locator(".lf-fp-row").bounding_box()["y"]
    assert page.evaluate(room)["bottom"] == pytest.approx(foot, abs=1)

    page.locator("body").focus()
    page.keyboard.press("m")
    position = page.locator(".lf-walk-position")
    expect(position).to_contain_text("1 of 2")
    head = page.locator(".lf-bottom-status").bounding_box()
    shown = page.evaluate(room)
    assert shown["top"] == pytest.approx(head["y"] + head["height"], abs=1), shown
    assert shown["bottom"] == pytest.approx(foot, abs=1), shown


def test_the_leaf_s_menu_stays_in_the_window_over_a_tall_view(browser, serve):
    """The leaf's menu stands over the leaf, its trigger, however tall the view open
    above the row, and within a short window it keeps every row reachable."""
    page = floating(browser, serve(LONG_PAGE, comments=20))
    page.set_viewport_size({"width": 1280, "height": 360})
    page.locator(".lf-fp-threads").click()
    expect(page.locator(".lf-fp-view[data-view='threads']")).to_be_visible()
    settled(page)
    page.locator(".lf-fp-leaf").click()
    menu = page.locator(".lf-fp-menu")
    expect(menu.locator(".lf-fp-item").first).to_be_visible()
    box = menu.bounding_box()
    leaf = page.locator(".lf-fp-leaf").bounding_box()
    assert box["y"] >= 0, f"the menu's top stands {-box['y']:.0f}px above the window"
    assert box["y"] + box["height"] <= leaf["y"], "the menu covers the leaf"
    last = menu.locator(".lf-fp-item").last
    last.scroll_into_view_if_needed()
    expect(last).to_be_in_viewport()


def test_the_panel_folds_to_the_leaf_and_stays_folded(browser, serve):
    """Folding to the leaf, from the leaf's menu or its key, is a choice the panel
    keeps across a reload, until the leaf is pressed again; `c` still reaches the
    page's field, and Go-to's Threads door opens the panel's own Threads."""
    url = serve(LONG_PAGE, comments=1)
    page = floating(browser, url)
    page.locator(".lf-fp-leaf").click()
    page.locator(".lf-fp-item", has_text="Fold to the leaf").click()
    panel = page.locator(".lf-floating-panel")
    expect(panel).to_have_attribute("data-rest", "mark")
    expect(page.locator(".lf-fp-field")).to_be_hidden()
    expect(page.locator(".lf-fp-quick")).to_be_hidden()

    page.reload()
    expect(panel).to_have_attribute("data-rest", "mark")
    page.locator(".lf-fp-leaf").click()
    expect(panel).to_have_attribute("data-rest", "row")
    expect(page.locator(".lf-fp-menu")).to_be_hidden()

    page.locator("body").focus()
    page.keyboard.press(".")
    expect(panel).to_have_attribute("data-rest", "mark")
    page.keyboard.press(".")
    expect(panel).to_have_attribute("data-rest", "row")
    page.keyboard.press("c")
    expect(field(page)).to_be_focused()
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("Shift+T")
    expect(page.locator(".lf-fp-view[data-view=threads]")).to_be_visible()
    expect(page.locator(".lf-thread-panel")).not_to_have_class("open")


def test_asks_are_answered_where_they_are_read_on_me(browser, serve):
    """On me lists what waits on the user, and each ask takes its answer there, by the
    widget's own choice: the event is the widget's action. The answered card keeps its
    place and height, so the next ask does not move under the pointer, and
    Undo takes the answer back."""
    page = floating(browser, serve(ASK_PAGE))
    chip = page.locator(".lf-fp-on-user")
    expect(chip).to_contain_text("2")
    chip.click()
    view = page.locator(".lf-fp-view[data-view=on]")
    cards = view.locator(".lf-fp-on-item")
    expect(cards).to_have_count(2)
    expect(cards.first).to_contain_text("How should the schema migrate?")
    settled(page)
    first, second = cards.first.bounding_box(), cards.nth(1).bounding_box()
    with sending(page, "the answer"):
        cards.first.locator(".lf-fp-answer", has_text="Shim").click()
    answer = events_model.read_events(serve.page_dir)[-1]
    assert (answer["kind"], answer["widget"]) == ("action", "schema")
    expect(cards.first).to_contain_text("Answered")
    expect(chip).to_contain_text("1")
    assert cards.first.bounding_box() == first
    assert cards.nth(1).bounding_box() == second

    with sending(page, "the undo"):
        cards.first.get_by_role("button", name="Undo").click()
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "undo"
    expect(cards.first.locator(".lf-fp-answer", has_text="Shim")).to_be_visible()
    expect(chip).to_contain_text("2")
    # The pressed Undo is gone, and Escape still puts the view away.
    page.keyboard.press("Escape")
    expect(view).to_have_count(0)


def test_versions_travel_and_approval_open_in_the_panel(browser, serve):
    """Version travel opens the panel's Versions, whatever route asks for the versions
    menu: it lists each version, marks the one shown, travels to another, and holds the
    page's approval, which records the sign-off."""
    url = serve(SIGN_OFF)
    stamp_page(
        serve.page_dir, SIGN_OFF.replace("Paragraph 0.", "Paragraph zero."), "two"
    )
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("g")
    page.keyboard.press("Shift+V")
    view = page.locator(".lf-fp-view[data-view=versions]")
    expect(view).to_be_visible()
    expect(page.locator("#lf-versions")).to_be_hidden()
    expect(view.locator(".lf-fp-version")).to_have_count(2)
    expect(view.locator(".lf-fp-version[data-current]")).to_contain_text("Showing")

    with sending(page, "the approval"):
        view.locator(".lf-fp-item", has_text="Approve version").click()
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "done"

    other = view.locator(".lf-fp-version:not([data-current]) .lf-fp-label")
    number = re.search(r"v\d+", other.inner_text()).group(0)
    other.click()
    expect(page).to_have_url(re.compile(rf"/versions/{number}\b"))


def test_the_on_me_walk_arrives_at_the_approval_in_the_panel(browser, serve):
    """The version's approval waits on the user in On me, and `m` arrives at it where
    this chrome shows it: the panel's On view, standing on its Approve."""
    url = serve(SIGN_OFF)
    stamp_page(serve.page_dir, SIGN_OFF, "one")
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("m")
    approve = page.locator(".lf-fp-view[data-view=on] [data-approval] .lf-fp-answer")
    expect(approve).to_be_focused()
    expect(page.locator(".lf-walk-position")).to_contain_text("Approval")

    # Answered, it is still arrived at: on its card in Done, at its Undo.
    with sending(page, "the approval"):
        page.keyboard.press("Enter")
    page.keyboard.press("Escape")
    # A page's own control arrives at it, as a widget's script would.
    page.evaluate(
        """async () => {
          const api = await window.__lfWidgetApi();
          const go = document.createElement('button');
          go.id = 'to-approval';
          go.textContent = 'To the approval';
          go.onclick = () => api.askActions.open(
            api.readAsks().all.find((ask) => ask.source.kind === 'approval').id);
          go.style.cssText = 'position: fixed; top: 0; left: 0';
          document.body.append(go);
        }"""
    )
    page.locator("#to-approval").click()
    card = page.locator(".lf-fp-view[data-view=on] [data-approval]")
    expect(card.get_by_role("button", name="Undo")).to_be_focused()


def test_the_approval_is_arrived_at_in_sight_below_many_asks(browser, serve):
    """With more asks than On me shows at once, arriving at the approval
    scrolls its card into the view, so the Approve the user stands on is in sight."""
    asks = "".join(
        f'<lf-ask id="ask-{n}"><h3>Question {n}?</h3><lf-options id="o-{n}" choose>'
        f'<lf-option id="y-{n}">Yes</lf-option><lf-option id="n-{n}">No</lf-option>'
        "</lf-options></lf-ask>"
        for n in range(12)
    )
    source = leaf_page("many", f"<h1>Many</h1>{asks}").replace(
        "<title>many</title>",
        '<title>many</title><meta name="lf-review" content="sign-off">',
    )
    url = serve(source)
    stamp_page(serve.page_dir, source, "one")
    page = floating(browser, url)
    page.evaluate(
        """async () => {
          const api = await window.__lfWidgetApi();
          const go = document.createElement('button');
          go.id = 'to-approval';
          go.textContent = 'To the approval';
          go.onclick = () => api.askActions.open(
            api.readAsks().all.find((ask) => ask.source.kind === 'approval').id);
          go.style.cssText = 'position: fixed; top: 0; left: 0';
          document.body.append(go);
        }"""
    )
    page.locator("#to-approval").click()
    view = page.locator(".lf-fp-view[data-view=on]")
    approve = view.locator("[data-approval] .lf-fp-answer")
    expect(approve).to_be_focused()
    expect(approve).to_be_in_viewport()
    box, room = approve.bounding_box(), view.bounding_box()
    assert (
        room["y"] <= box["y"]
        and box["y"] + box["height"] <= room["y"] + room["height"] + 1
    ), (box, room)


def test_a_mode_entered_from_the_panel_offers_its_way_out_in_the_row(browser, serve):
    """The pen opens Annotations, whose Draw mode, while it holds the banner's gesture
    seat, stands its steps in the row in the counts' place; Exit leaves the mode and
    the counts return. Picking an element is left to the page, where selecting words
    or pressing `s` starts it, so Annotations doesn't list it."""
    page = floating(browser, serve(LONG_PAGE, comments=1))
    page.locator(".lf-fp-annotate").click()
    expect(page.locator(".lf-fp-item", has_text="Capture area")).to_be_visible()
    expect(page.locator(".lf-fp-item", has_text="Select element")).to_have_count(0)
    page.locator(".lf-fp-item", has_text="Draw mode").click()
    exit_step = page.locator(".lf-fp-step", has_text="Exit Draw mode")
    expect(exit_step).to_be_visible()
    expect(page.locator(".lf-fp-on-user")).to_have_count(0)
    exit_step.click()
    expect(page.locator(".lf-fp-step")).to_have_count(0)
    expect(page.locator(".lf-fp-annotate")).to_be_visible()


def test_a_page_thread_opens_in_the_panel_from_the_page_s_routes(browser, serve):
    """The panel is the page's thread reader for threads about the whole page: the `t`
    walk opens one there, drawn by Leaf's own reader."""
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Is the window long enough?")
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    reader = page.locator(".lf-fp-view[data-view=thread]")
    expect(reader).to_be_visible()
    expect(reader.locator(".lf-msg")).to_contain_text("Is the window long enough?")
    expect(page.locator(".lf-thread-panel")).not_to_have_class(re.compile("open"))


def test_send_stands_in_the_counts_place_while_the_user_types(browser, serve):
    """Typing puts Send where the counts stood, and a press that takes the caret away
    brings the counts back while the words, and the line naming where they go, stay
    where they were."""
    page = floating(browser, serve(LONG_PAGE))
    field(page).click()
    page.keyboard.type("Could the rollback cover the weekend?")
    send = page.locator(".lf-fp-send")
    expect(send).to_be_visible()
    expect(page.locator(".lf-fp-on-user")).to_be_hidden()
    settled(page)
    words = field(page).bounding_box()
    page.mouse.click(5, 5)
    expect(field(page)).not_to_be_focused()
    expect(send).to_be_hidden()
    expect(page.locator(".lf-fp-on-user")).to_be_visible()
    expect(page.locator(".lf-fp-context")).to_be_visible()
    settled(page)
    after = field(page).bounding_box()
    assert (after["x"], after["y"]) == (words["x"], words["y"])


def test_writing_reaches_the_field_however_the_panel_stands(browser, serve):
    """Asking to write reaches the panel's field from any state it stands in: `c`
    unfolds a panel folded to the leaf, and Resume writing comes back to a reply left
    unsent in a thread the user has since closed, in the same field."""
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Is the window long enough?")
    page = floating(browser, url)
    page.locator(".lf-fp-leaf").click()
    page.locator(".lf-fp-item", has_text="Fold to the leaf").click()
    panel = page.locator(".lf-floating-panel")
    expect(panel).to_have_attribute("data-rest", "mark")
    page.locator("body").focus()
    page.keyboard.press("c")
    expect(panel).to_have_attribute("data-rest", "row")
    expect(field(page)).to_be_focused()
    page.keyboard.press("Escape")

    page.locator("body").focus()
    page.keyboard.press("t")
    expect(page.locator(".lf-fp-view[data-view=thread]")).to_be_visible()
    field(page).click()
    page.keyboard.type("Make it the weekend.")
    page.locator(".lf-fp-close").click()
    expect(page.locator(".lf-fp-view")).to_have_count(0)
    page.locator("body").focus()
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(page.locator(".lf-fp-view[data-view=thread]")).to_be_visible()
    expect(field(page)).to_be_focused()
    expect(field(page)).to_have_js_property("value", "Make it the weekend.")
    page.wait_for_timeout(300)
    expect(page.get_by_text("That writing place is unavailable")).to_have_count(0)


@pytest.mark.parametrize(
    ("chrome", "panel", "banner"), [("floating", 1, 0), ("classic", 0, 1)]
)
def test_a_window_sample_reads_with_the_chrome_its_element_names(
    browser, serve, chrome, panel, banner
):
    """A window sample shows its child page in the chrome its element names, whatever
    the reader's own, so a review page can show classic and floating side by side."""
    page = open_page(
        browser,
        serve(
            titled_page(
                "A chrome named",
                f"""
<h1>Containing page</h1>
<lf-sample id="practice" label="Practice" window chrome="{chrome}">
  <template id="practice-source" data-sample><h1>Practice</h1></template>
</lf-sample>
""",
            )
        ),
        init_script=FLOATING if chrome == "classic" else None,
    )
    page.locator("#practice").evaluate("async sample => await sample.ready")
    child = page.frame_locator("#practice iframe")
    expect(child.locator(".lf-floating-panel:visible")).to_have_count(panel)
    expect(child.locator(".lf-banner:visible")).to_have_count(banner)
