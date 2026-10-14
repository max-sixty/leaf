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
from leaf import service as service_model
from leaf import thread as thread_model
from model_folds import leaf_page
from playwright.sync_api import expect
from render_cases_interaction import panel_comment
from render_harness import (
    LONG_PAGE,
    consume_browser_errors,
    open_page,
    sending,
    stamp_page,
    told,
    write,
)

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
    words go, and once they hide that, the line above it does, in the same words, while
    no view is open; over the thread, whose head names it, nothing does. The banner and
    the bottom bar are gone, and Escape, once the caret has left the field, puts the
    thread away."""
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
    expect(page.locator(".lf-fp-context")).to_be_hidden()
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
    expect(page.locator(".lf-fp-field .lf-compose-submit")).to_be_hidden()
    expect(page.locator(".lf-fp-on-user")).to_be_visible()

    settle = page.locator(".lf-fp-settle")
    with sending(page, "the resolve"):
        settle.click()
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "resolve"
    expect(settle).to_have_text("Reopen", use_inner_text=True)
    with sending(page, "the reopen"):
        settle.click()
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "unresolve"
    expect(settle).to_have_text("Resolve", use_inner_text=True)

    field(page).focus()
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-fp-view")).to_have_count(0)


def test_escape_leaves_the_field_before_it_puts_a_view_away(browser, serve):
    """The caret in the field is the innermost thing open, so the first Escape takes it
    out of the field and leaves the view and the draft standing: a reply returns to its
    thread, the page's field to the leaf. The next Escape puts the view away. The field
    never swaps its editor under a caret, so words typed after an Escape never go
    somewhere the user did not choose."""
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Is the window long enough?")
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    thread = page.locator(".lf-fp-view[data-view=thread]")
    expect(thread).to_be_visible()
    field(page).click()
    page.keyboard.type("Make it the weekend.")
    page.keyboard.press("Escape")
    expect(thread).to_be_visible()
    expect(thread).to_be_focused()
    expect(field(page)).to_have_attribute("name", "reply")
    expect(field(page)).to_have_js_property("value", "Make it the weekend.")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-fp-view")).to_have_count(0)
    expect(page.locator(".lf-fp-leaf")).to_be_focused()
    expect(field(page)).not_to_be_focused()

    page.locator(".lf-fp-threads").click()
    inventory = page.locator(".lf-fp-view[data-view=threads]")
    expect(inventory).to_be_visible()
    field(page).click()
    page.keyboard.press("Escape")
    expect(inventory).to_be_visible()
    expect(page.locator(".lf-fp-leaf")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-fp-view")).to_have_count(0)


def test_c_in_an_open_thread_returns_to_its_reply(browser, serve):
    """Standing anywhere in the thread open in the panel, `c` comments on that thread:
    from the view an Escape left the user on, and from a message in it, the caret
    returns to the thread's reply with its words, and the thread stays open."""
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Is the window long enough?")
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    thread = page.locator(".lf-fp-view[data-view=thread]")
    expect(thread).to_be_visible()
    field(page).click()
    page.keyboard.type("Make it the weekend.")
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


def test_a_thread_s_keys_answer_in_its_view(browser, serve):
    """The thread open in the panel answers the keys a card in Threads does, though its
    reply is the field and its Resolve stands in the view's head: Enter on the view puts
    the caret back in the reply with its words, Enter on a resolved thread reopens it,
    `r` settles the thread from the view, a message in it or its Resolve and leaves the
    user standing where they were, and `e` on a message opens the agent's reactions."""
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
    thread = page.locator(".lf-fp-view[data-view=thread]")
    settle = page.locator(".lf-fp-settle")
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
    with sending(page, "the resolve"):
        page.keyboard.press("r")
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "resolve"
    expect(settle).to_have_text("Reopen", use_inner_text=True)
    expect(thread).to_be_focused()

    with sending(page, "the reopen"):
        page.keyboard.press("Enter")
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "unresolve"
    expect(settle).to_have_text("Resolve", use_inner_text=True)

    # A click on a message's words stands on the part of the thread drawing it.
    message = thread.locator(".lf-primary-part", has_text="Is the window long enough?")
    message.click()
    expect(message).to_be_focused()
    page.keyboard.press("e")
    strip = thread.locator(".lf-msg.agent > .lf-react-strip")
    expect(strip).to_contain_class("lf-react-open")
    page.keyboard.press("Escape")
    expect(strip).not_to_contain_class("lf-react-open")
    message.click()
    with sending(page, "the resolve from a message"):
        page.keyboard.press("r")
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "resolve"
    expect(message).to_be_focused()

    settle.focus()
    with sending(page, "the reopen from Resolve's place"):
        page.keyboard.press("r")
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "unresolve"
    expect(settle).to_have_text("Resolve", use_inner_text=True)
    expect(settle).to_be_focused()
    # The head stands for the thread, whose messages are in the view below it.
    page.keyboard.press("e")
    expect(strip).to_contain_class("lf-react-open")
    page.keyboard.press("Escape")
    expect(strip).not_to_contain_class("lf-react-open")
    settle.focus()
    with sending(page, "the resolve from Resolve's place"):
        page.keyboard.press("r")
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "resolve"
    expect(settle).to_be_focused()


def test_the_field_is_the_thread_s_reply_box(browser, serve):
    """The field a thread opens with is that thread's reply box, as a card's is: a rewrite
    opened on a message is a rung below it, so Escape or Save hands the caret back to
    the field; ↑ from the empty field opens the rewrite of the user's last message, and
    ↑ from the start of an unchanged rewrite the message before. Resolve leaves the
    reply as a card's does, and the field says how to reopen the thread."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Is the window long enough?")
    for author, text in [
        ("agent", "Forty-eight hours covers the first cohort."),
        ("user", "What about the second cohort?"),
    ]:
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": author,
                **({"agent": "Claude"} if author == "agent" else {}),
                "parent": root,
                "revision": 1,
                "text": text,
            },
        )
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    thread = page.locator(".lf-fp-view[data-view=thread]")
    expect(thread).to_be_visible()
    rewrite = thread.locator(".lf-msg-editor leaf-text")

    # A rewrite opened on the message itself is a rung below the reply box too.
    thread.locator(".lf-msg-body", has_text="What about the second cohort?").dblclick()
    expect(rewrite).to_be_focused()
    page.keyboard.press("Escape")
    expect(rewrite).to_have_count(0)
    expect(field(page)).to_be_focused()

    page.keyboard.press("ArrowUp")
    expect(rewrite).to_be_focused()
    expect(rewrite).to_have_js_property("value", "What about the second cohort?")
    page.keyboard.press("Home")
    page.keyboard.press("ArrowUp")
    expect(rewrite).to_be_focused()
    expect(rewrite).to_have_js_property("value", "Is the window long enough?")
    page.keyboard.press("Escape")
    expect(rewrite).to_have_count(0)
    expect(field(page)).to_be_focused()
    expect(field(page)).to_have_attribute("name", "reply")

    page.keyboard.press("ArrowUp")
    page.keyboard.press("End")
    page.keyboard.type(" And the third?")
    with sending(page, "the rewrite"):
        page.keyboard.press("Enter")
    edit = events_model.read_events(serve.page_dir)[-1]
    assert (edit["kind"], edit["text"]) == (
        "edit",
        "What about the second cohort? And the third?",
    )
    expect(field(page)).to_be_focused()

    page.locator(".lf-fp-settle").focus()
    with sending(page, "the resolve"):
        page.keyboard.press("Enter")
    expect(field(page)).to_be_hidden()
    expect(page.locator(".lf-fp-resolved")).to_have_text("Resolved · reopen to reply")


def test_the_thread_walk_stands_on_each_thread_it_opens(browser, serve):
    """`t` opens the next thread in the panel and stands on it, as the walk stands on a
    card's title in Threads, so `t` and `T` go on walking from there rather than typing
    into its reply; showing an answer waiting below its fold stands on the thread too."""
    url = serve(LONG_PAGE)
    first = panel_comment(serve.page_dir, "Is the window long enough?")
    panel_comment(serve.page_dir, "Should the rollout pause on Fridays?")
    page = floating(browser, url)
    view = page.locator(".lf-fp-view[data-view=thread]:not([data-leaving])")
    title = page.locator(".lf-fp-title")
    page.locator("body").focus()
    page.keyboard.press("t")
    expect(title).to_have_text("Is the window long enough?")
    expect(view).to_be_focused()
    page.keyboard.press("t")
    expect(title).to_have_text("Should the rollout pause on Fridays?")
    expect(view).to_be_focused()
    page.keyboard.press("Shift+t")
    expect(title).to_have_text("Is the window long enough?")
    expect(view).to_be_focused()

    # An answer too long for the view waits below its fold behind New reply.
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": first,
            "revision": 1,
            "text": "The window covers it. " * 60,
        },
    )
    news = view.locator(".lf-fp-new-reply")
    expect(news).to_be_visible()
    news.focus()
    page.keyboard.press("Enter")
    expect(news).to_have_count(0)
    expect(view.get_by_text("The window covers it.").first).to_be_in_viewport()
    expect(view).to_be_focused()


def test_the_panel_names_the_agent_as_the_page_s_messages_do(browser, serve):
    """The agent has one name across the panel, the one the page gives it: on a page no
    session holds, the voice that last wrote there, so the On view says Claude where
    Claude's messages do."""
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
    page.locator(".lf-fp-on-user").click()
    expect(page.locator(".lf-fp-filters")).to_contain_text("On Claude")


def test_the_on_view_is_titled_by_its_tab_with_that_list_s_done_under_it(
    browser, serve
):
    """The On view has no name of its own: its title is the open tab's, On me or On
    Claude, which the tabs beside it already show, so the title names the view to
    assistive tech alone. Under each list stands what left it. A reply the agent sent
    leaves its list, so it stands under On Claude, said as sent. The On me mark opens
    the user's list, turning the view to it where it shows the agent's."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Is the window long enough?")
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": root,
            "responds": root,
            "revision": 1,
            "text": "Forty-eight hours covers the first cohort.",
        },
    )
    page = floating(browser, url)
    page.locator(".lf-fp-on-user").click()
    title = page.locator(".lf-fp-title")
    expect(title).to_have_text("On me")
    assert title.bounding_box()["width"] <= 1
    expect(page.locator(".lf-fp-filters button")).to_have_count(2)
    expect(page.locator(".lf-fp-on-done")).to_have_count(0)
    page.locator(".lf-fp-filters button", has_text="On Claude").click()
    expect(title).to_have_text("On Claude")
    expect(page.locator(".lf-fp-empty")).to_have_text("Nothing waiting on Claude.")
    expect(page.locator(".lf-fp-on-done")).to_have_text("Done")
    sent = page.locator(".lf-fp-on-item")
    expect(sent).to_have_count(1)
    expect(sent).to_contain_text("Forty-eight hours covers the first cohort.")
    expect(sent.locator(".lf-fp-said")).to_have_text(re.compile(r"^Sent"))
    # The On me mark turns the open view back to the user's list, and then closes it.
    page.locator(".lf-fp-on-user").click()
    expect(title).to_have_text("On me")
    page.locator(".lf-fp-on-user").click()
    expect(title).to_have_count(0)


def test_on_shows_an_ask_as_its_message_and_reply_comes_back(browser, serve):
    """A question the agent asked in a thread reads in the On view as its message, drawn
    whole as the thread draws it, so what it introduces after a colon is there with it.
    Reply opens its thread with On behind it, where the back link returns."""
    url = serve(LONG_PAGE)
    panel_comment(
        serve.page_dir,
        "Which build should ship? These are the candidates:\n\n- #4813 schedule\n"
        "- #4812 manual",
        author="agent",
    )
    page = floating(browser, url)
    page.locator(".lf-fp-on-user").click()
    card = page.locator(".lf-fp-on-item", has_text="Which build should ship?")
    expect(card.locator(".lf-msg")).to_have_count(1)
    expect(card.locator("li")).to_have_count(2)
    expect(card).to_contain_text("#4812 manual")

    card.locator(".lf-fp-answer", has_text="Reply").click()
    expect(page.locator(".lf-fp-view[data-view=thread]")).to_be_visible()
    back = page.locator(".lf-fp-back")
    expect(back).to_have_text("On me")
    back.click()
    expect(page.locator(".lf-fp-view[data-view=queue]")).to_be_visible()


def test_clicking_into_the_field_moves_nothing_at_an_open_view_s_head(browser, serve):
    """An open view stands right on the row, with no empty band between them. Clicking
    into the field shows nothing over it, since the keys that send are Send's hover
    name, and neither do words arriving, since the placeholder said where they go before
    they hid it, so its tabs and Close stay where the pointer may be about to press
    them."""
    page = floating(browser, serve(LONG_PAGE, comments=3))
    page.locator(".lf-fp-threads").click()
    view = page.locator(".lf-fp-view[data-view=threads]")
    expect(view).to_be_visible()
    settled(page)
    row = page.locator(".lf-fp-row")
    stands = view.bounding_box()
    band = row.bounding_box()["y"] - (stands["y"] + stands["height"])
    assert abs(band) < 0.5, f"{band:.0f}px stand between the view and the row"
    close = page.locator(".lf-fp-close").bounding_box()
    tab = page.locator(".lf-fp-filters button", has_text="Resolved").bounding_box()
    line = page.locator(".lf-fp-context")
    field(page).click()
    expect(line).to_be_hidden()
    settled(page)
    assert page.locator(".lf-fp-close").bounding_box() == close
    assert (
        page.locator(".lf-fp-filters button", has_text="Resolved").bounding_box() == tab
    )
    page.keyboard.type("Could")
    expect(page.locator(".lf-fp-send")).to_be_visible()
    expect(line).to_be_hidden()
    # Each platform spells Shift its own way (keyboard/bindings.js, `spell`).
    expect(page.locator(".lf-fp-send")).to_have_attribute(
        "title", re.compile(r"^Send \(⏎\) · (⇧|Shift\+)⏎ new line$")
    )
    settled(page)
    assert page.locator(".lf-fp-close").bounding_box() == close
    assert view.bounding_box() == stands


HEAD_SEATS = """() => {
  const head = document.querySelector('.lf-fp-head');
  const seat = (selector) => {
    const box = head.querySelector(selector)?.getBoundingClientRect();
    return box && [box.left, box.top, box.right, box.bottom];
  };
  return {
    back: seat('.lf-fp-back'),
    start: seat('.lf-fp-title')[0],
    where: seat('.lf-fp-where'),
    on: seat('.lf-fp-quiet'),
    settle: seat('.lf-fp-settle'),
    close: seat('.lf-fp-close'),
  };
}"""


def test_news_in_an_open_thread_moves_nothing_at_its_head(browser, serve):
    """A thread's head holds each control where it stood while the thread changes under
    it. Retitled long or short, the title gives or takes room at its own end, and Back,
    where the thread stands among the open ones, On the page, Resolve and Close stay
    put; detached by a revision, On the page leaves its seat empty; resolved by the
    agent, the thread's Reopen takes Resolve's seat."""
    url = serve(LONG_PAGE, comments=3, anchored=[("p3", "Paragraph 3.")])
    root = events_model.read_events(serve.page_dir)[-1]["id"]
    page = floating(browser, url)
    page.locator(".lf-fp-threads").click()
    page.locator(".lf-fp-filters button", has_text="Open").click()
    page.locator(".lf-fp-thread", has_text="About this bit.").click()
    title = page.locator(".lf-fp-head .lf-fp-title")
    expect(title).to_have_text("About this bit.")
    settled(page)
    seats = page.evaluate(HEAD_SEATS)
    assert all(seats.values()), seats

    def agent(event):
        append_carried_log_record(
            serve.page_dir, {"author": "agent", "agent": "Claude", **event}
        )
        told(page)

    for name in [
        "Whether the third paragraph's filler should stay in the published draft",
        "Filler",
    ]:
        agent({"kind": "thread_title", "thread": root, "title": name})
        expect(title).to_have_text(name)
        settled(page)
        assert page.evaluate(HEAD_SEATS) == seats

    # A revision that drops the passage detaches the thread: On the page has nowhere
    # to go, and its seat stands empty while the view does.
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reanchor",
            "author": "page",
            "revision": 1,
            "thread": root,
            "anchor": None,
        },
    )
    told(page)
    expect(page.locator(".lf-fp-head .lf-fp-quiet")).to_be_hidden()
    settled(page)
    assert page.evaluate(HEAD_SEATS) == seats

    agent({"kind": "resolve", "parent": root})
    expect(page.locator(".lf-fp-head .lf-reopen")).to_be_visible()
    settled(page)
    # A resolved thread stands nowhere among the open ones, so only its count goes.
    assert {**page.evaluate(HEAD_SEATS), "where": seats["where"]} == seats


def test_threads_is_as_tall_as_the_threads_it_first_shows(browser, serve):
    """Threads takes the height of the rows it first shows, not of threads a filter
    hides, so three open threads leave no blank row for a resolved fourth."""
    url = serve(LONG_PAGE, comments=3)
    settled_thread = panel_comment(serve.page_dir, "Is the window long enough?")
    append_carried_log_record(
        serve.page_dir, {"kind": "resolve", "author": "user", "parent": settled_thread}
    )
    page = floating(browser, url)
    page.locator(".lf-fp-threads").click()
    inventory = page.locator(".lf-fp-view[data-view=threads]")
    expect(inventory.locator(".lf-fp-thread")).to_have_count(3)
    settled(page)
    below, row = inventory.evaluate(
        """view => {
          const last = view.querySelector('.lf-fp-thread:last-child').getBoundingClientRect();
          return [view.getBoundingClientRect().bottom - last.bottom, last.height];
        }"""
    )
    assert below < row, f"{below:.0f}px stand empty under the last thread"


def test_about_s_rows_that_copy_say_what_they_copy(browser, serve):
    """A row of About whose press copies, such as the Leaf version's diagnostics, shows
    the text it copies beside Leaf's copy control, and names it. The control is the one
    a code block wears, an icon named for what it copies, and a press copies the text
    and says so."""
    page = floating(browser, serve(LONG_PAGE))
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.locator(".lf-fp-leaf").click()
    page.locator(".lf-fp-menu .lf-fp-item", has_text="About this page").click()
    version = page.locator(".lf-fp-copy", has_text="Leaf version")
    text = version.locator(".lf-fp-copy-text")
    expect(text).to_have_value(re.compile("^Leaf layer\n"))
    copy = version.locator("wa-copy-button")
    expect(copy).to_be_visible()
    copy.get_by_role("button", name="Copy Leaf version").click()
    expect(field(page)).to_have_attribute(
        "placeholder", re.compile("^Leaf version copied")
    )
    assert page.evaluate("navigator.clipboard.readText()") == text.input_value()


def test_copy_link_is_one_press_in_the_leaf_s_menu(browser, serve):
    """The page's link is copied from a row of the leaf's menu itself, in one press that
    puts the menu away and says in the field that the link was copied; its hover name
    says what the link grants. About keeps the Leaf version and no longer the link."""
    page = floating(browser, serve(LONG_PAGE))
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.locator(".lf-fp-leaf").click()
    row = page.locator(".lf-fp-menu").get_by_role("menuitem", name="Copy link")
    expect(row).to_have_attribute("title", re.compile("^Grants access"))
    row.click()
    expect(page.locator(".lf-fp-menu")).to_be_hidden()
    expect(field(page)).to_have_attribute("placeholder", re.compile("^Link copied"))
    assert re.match(
        r"^http://.*[?&]t=", page.evaluate("navigator.clipboard.readText()")
    )

    page.locator(".lf-fp-leaf").click()
    page.locator(".lf-fp-menu .lf-fp-item", has_text="About this page").click()
    about = page.locator(".lf-fp-view[data-view=group]")
    expect(about.locator(".lf-fp-copy", has_text="Leaf version")).to_be_visible()
    expect(about.get_by_label("Link", exact=True)).to_have_count(0)


def test_a_refused_copy_leaves_the_link_to_select_in_about(browser, serve):
    """A clipboard that refuses the write leaves the user the link all the same: the
    press opens About on the link, in a field they can select, and the field says the
    link was not copied."""
    refuses = (
        "Clipboard.prototype.writeText = () => Promise.reject(new Error('refused'));"
    )
    page = open_page(browser, serve(LONG_PAGE), init_script=f"{FLOATING}\n{refuses}")
    page.locator(".lf-fp-leaf").click()
    page.locator(".lf-fp-menu").get_by_role("menuitem", name="Copy link").click()
    about = page.locator(".lf-fp-view[data-view=group]")
    link = about.get_by_label("Link", exact=True)
    expect(link).to_have_value(re.compile(r"^http://.*[?&]t="))
    expect(page.locator(".lf-fp-head")).to_contain_text("About this page")
    expect(field(page)).to_have_attribute("placeholder", re.compile("^Link not copied"))


def test_page_search_stands_with_its_controls_at_the_panel(browser, serve):
    """Page search's box stands just over the panel's row, where its Previous, Next and
    Close search stand, rather than at the window's head."""
    page = floating(browser, serve(LONG_PAGE))
    page.locator("body").focus()
    page.keyboard.press("/")
    search = page.locator(".lf-page-search")
    expect(search).to_be_visible()
    expect(page.locator(".lf-fp-step", has_text="Close search")).to_be_visible()
    box = search.bounding_box()
    row = page.locator(".lf-fp-row").bounding_box()
    gap = row["y"] - (box["y"] + box["height"])
    assert 0 <= gap < 24, f"the search box stands {gap:.0f}px over the panel's row"


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
    room: parseFloat(getComputedStyle(view).paddingBottom),
    first: messages[0].getBoundingClientRect().top,
    panel: document.querySelector('.lf-fp-card').getBoundingClientRect().top,
  };
}"""


def test_a_thread_s_view_is_as_tall_as_its_messages(browser, serve):
    """An opened view is as tall as what it holds. A page comment opens its thread one
    message tall, and a long thread reads in most of the window's height, leaving a band
    of the page above the panel, before it scrolls."""
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
    view = page.locator(".lf-fp-view[data-view=thread]")
    expect(view.locator(".lf-msg")).to_have_count(1)
    settled(page)
    short = page.evaluate(THREAD_FIT)
    assert not short["scrolls"]
    # Nothing stands under its message but the view's padding.
    assert short["below"] - short["room"] < 10, short

    page.keyboard.press("Escape")
    page.locator(".lf-fp-threads").click()
    page.locator(".lf-fp-filters button", has_text="Open").click()
    page.locator(".lf-fp-thread", has_text="Walk me through the whole rollout.").click()
    expect(view.locator(".lf-msg")).to_have_count(9)
    settled(page)
    long = page.evaluate(THREAD_FIT)
    assert long["height"] > 600, long
    assert long["panel"] >= 100, long


def test_an_answer_the_user_waits_for_shows_at_once_where_it_fits(browser, serve):
    """The agent's answer to the user's own last turn is not held: where it fits in the
    view's height, the view's end follows it into sight at once, its earlier words
    scrolling up, and nothing at the view's head moves. Where it would not fit, the view
    keeps its height and the answer waits below the fold, with New reply at the view's
    foot, where it begins; a press grows the view and brings its start into sight. A
    reply that follows the agent's own turn is still held behind the thread's notice,
    since nobody was waiting for it."""
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
    view = page.locator(".lf-fp-view[data-view=thread]")
    messages = view.locator(".lf-msg")
    expect(messages).to_have_count(1)
    settled(page)
    seats = page.evaluate(HEAD_SEATS)
    stands = view.bounding_box()

    def in_sight(node):
        box, shown = node.bounding_box(), view.bounding_box()
        return box["y"] >= shown["y"] and box["y"] + box["height"] <= (
            shown["y"] + shown["height"] + 0.5
        )

    answer("Internal first.")
    expect(messages).to_have_count(2)
    settled(page)
    assert in_sight(messages.last)
    assert page.evaluate(HEAD_SEATS) == seats
    assert view.bounding_box() == stands
    expect(view.locator(".lf-fp-new-reply")).to_have_count(0)
    expect(view.locator(".lf-primary-news:visible")).to_have_count(0)

    write(field(page), "And the weekend?")
    with sending(page, "the reply"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect(messages).to_have_count(3)
    settled(page)
    seats = page.evaluate(HEAD_SEATS)
    stands = view.bounding_box()

    answer("It would. " + "Someone stays on call through Sunday, and Monday too. " * 40)
    press = view.locator(".lf-fp-new-reply")
    expect(press).to_have_text("New reply")
    expect(messages).to_have_count(4)
    settled(page)
    assert page.evaluate(HEAD_SEATS) == seats
    assert view.bounding_box() == stands
    assert messages.last.bounding_box()["y"] >= stands["y"] + stands["height"] - 40

    press.click()
    expect(press).to_have_count(0)
    settled(page)
    shown = messages.last.bounding_box()
    grown = view.bounding_box()
    assert grown["height"] > stands["height"], (stands, grown)
    assert grown["y"] <= shown["y"] < grown["y"] + grown["height"] - 40, (shown, grown)

    answer("One more thing: the alarms page the on-call too.")
    expect(view.locator(".lf-primary-news:visible")).to_contain_text("1 new reply")
    expect(messages).to_have_count(4)


def test_new_reply_leads_to_the_reply_once_one_follows_the_work(browser, serve):
    """Work under way that does not fit waits behind New update; the reply that follows
    it takes the press over, which then says New reply and brings the reply's start into
    sight, not the work before it."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Which job comes first?")
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(".lf-fp-view[data-view=thread]")
    expect(view.locator(".lf-msg")).to_have_count(1)
    settled(page)

    def say(text, **kwargs):
        thread_model.post_reply(
            serve.page_dir, {"to": root, "for": root}, text, **kwargs
        )
        told(page)

    press = view.locator(".lf-fp-new-reply")
    say("Reading the jobs, the mounts and the frost dates. " * 12, ephemeral=True)
    expect(press).to_have_text("New update")
    say("The mounts come first. " + "They need the frost to lift. " * 30)
    expect(press).to_have_text("New reply")
    press.click()
    expect(press).to_have_count(0)
    settled(page)
    reply = view.locator(".lf-msg", has_text="The mounts come first.")
    shown, box = reply.bounding_box(), view.bounding_box()
    assert box["y"] <= shown["y"] < box["y"] + box["height"] - 40, (shown, box)


def test_a_streaming_answer_follows_into_sight_until_it_outgrows_the_view(
    browser, serve, request
):
    """An answer the user waits for that streams in grows inside the view: while what
    each step adds fits, the view's end follows it, and nothing at the head moves; a
    step that would not fit, such as the durable answer completing it with longer words,
    leaves New reply at the view's foot."""
    # The threads suite imports this one, so its stream helpers come in at run time.
    from browser.test_render_threads import claim_for_codex, stream_reply

    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir,
        "Record the release on the board: "
        + "which build shipped, which checks passed, and who signed it off. " * 3,
    )
    claim_for_codex(serve.page_dir, request)
    stream_reply(serve.page_dir, root, "")
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(".lf-fp-view[data-view=thread]")
    messages = view.locator(".lf-msg")
    expect(messages).to_have_count(1)
    settled(page)
    seats = page.evaluate(HEAD_SEATS)
    stands = view.bounding_box()

    def streamed(text):
        stream_reply(serve.page_dir, root, text)
        told(page)
        expect(messages.last.locator(".lf-msg-text")).to_have_text(text)
        settled(page)
        assert page.evaluate(HEAD_SEATS) == seats
        assert view.bounding_box() == stands

    streamed("I'll")
    streamed("I'll record it on the board now.")
    shown, box = messages.last.bounding_box(), view.bounding_box()
    assert shown["y"] + shown["height"] <= box["y"] + box["height"] + 0.5
    expect(view.locator(".lf-fp-new-reply")).to_have_count(0)

    # The durable answer completes the streamed message with longer words.
    thread_model.post_reply(
        serve.page_dir,
        {"to": root, "for": root},
        "Recorded the release on the board. " + "Then I checked the totals. " * 40,
        attempt="leaf-response-explicit",
        identity={"agent": "Codex", "session": "codex-thread"},
    )
    with service_model.PageTransaction(serve.page_dir) as transaction:
        transaction.clear_stream_reply("codex-thread", "leaf-turn")
    told(page)
    expect(messages.last.locator(".lf-msg-text")).to_contain_text(
        "Recorded the release"
    )
    expect(view.locator(".lf-fp-new-reply")).to_have_text("New reply")
    settled(page)
    assert page.evaluate(HEAD_SEATS) == seats
    assert view.bounding_box() == stands


FOOT = """([parts, fromEnd]) => {
  const view = document.querySelector('.lf-fp-view:not([data-leaving])');
  const part = [...view.querySelectorAll(parts)].at(-1 - fromEnd).getBoundingClientRect();
  const box = view.getBoundingClientRect();
  const press = view.querySelector('.lf-fp-new-reply')?.getBoundingClientRect();
  return {
    below: box.bottom - part.bottom - parseFloat(getComputedStyle(view).paddingBottom),
    press: press && {over: press.top - part.bottom, under: box.bottom - press.bottom},
    said: [...document.querySelectorAll('.lf-fp-context, .lf-fp-peek')]
      .filter((node) => node.checkVisibility())
      .map((node) => node.textContent),
  };
}"""


def test_nothing_lies_over_a_view_s_foot_but_new_reply(browser, serve):
    """An open view's foot keeps no room for anything but its padding, and nothing lies
    over it: not the line over the field, which would repeat where the words go, nor
    news arriving in it, which the view shows. At the view's end its last words stand
    just above its padding, in a long Threads list and a long thread the user types at
    the end of. New reply alone stands at its foot, on the panel's ground and inside the
    view, clear of the user's own last turn while the answer to it waits below."""
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

    def at_end(parts):
        page.locator(".lf-fp-view:not([data-leaving])").evaluate(
            "view => view.scrollTop = view.scrollHeight"
        )
        settled(page)
        foot = page.evaluate(FOOT, [parts, 0])
        assert foot["said"] == [], foot
        assert 0 <= foot["below"] < 10, foot

    page.locator(".lf-fp-threads").click()
    page.locator(".lf-fp-filters button", has_text="Open").click()
    inventory = page.locator(".lf-fp-view[data-view=threads]")
    expect(inventory.locator(".lf-fp-thread")).to_have_count(13)
    field(page).click()
    page.keyboard.type("Could")
    expect(page.locator(".lf-floating-panel")).to_have_attribute("data-typing", "")
    at_end(".lf-fp-thread")

    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.press("Backspace")
    inventory.locator(".lf-fp-thread", has_text="Walk me through").click()
    reader = page.locator(".lf-fp-view[data-view=thread]")
    expect(reader.locator(".lf-msg")).to_have_count(9)
    field(page).click()
    page.keyboard.type("Could")
    expect(page.locator(".lf-floating-panel")).to_have_attribute("data-typing", "")
    at_end(".lf-msg")

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
    expect(reader.locator(".lf-fp-new-reply")).to_have_text("New reply")
    settled(page)
    # The user's own turn, the last message but the answer below the fold.
    foot = page.evaluate(FOOT, [".lf-msg-text", 1])
    assert foot["said"] == [], foot
    assert foot["press"]["over"] >= 0, foot
    assert foot["press"]["under"] >= 0, foot


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
    ends, and never hiding the words under forced colours. Clicking in gives the
    placeholder to where the words go; once words hide the placeholder, a line above the
    field says where they go. It never names who reads them, since every word here goes
    to the one agent."""
    url = serve(LONG_PAGE)
    # No session holds the page, so it names its agent by the voice that started the
    # work, the suite's Claude Code session (`presence.page_agent`).
    working(serve.page_dir, "Drafting the rollout")
    agent = "Claude"
    page = floating(browser, url)
    status = re.compile(rf"^{agent} working\b.* — Drafting the rollout")
    expect(field(page)).to_have_attribute("placeholder", status)
    # The sheen runs on the field's placeholder, inside the field's closed tree, where
    # no animation list reaches: the words it paints over turn to their gradient, and
    # the field reads differently from one moment to the next.
    words = page.locator(".lf-fp-field .lf-compose-placeholder > span")
    ink = """node => getComputedStyle(node).color"""

    def sheen(running):
        page.wait_for_function(
            """running => (getComputedStyle(document.querySelector(
              '.lf-fp-field .lf-compose-placeholder > span')).webkitTextFillColor
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
    # Forced colours drop the gradient but keep the animation, so the words keep
    # their fill rather than vanishing.
    page.emulate_media(forced_colors="active")
    sheen(False)
    page.emulate_media(forced_colors="none")
    sheen(True)

    field(page).click()
    expect(field(page)).to_have_attribute(
        "placeholder", re.compile("^Comment on the page")
    )
    sheen(False)
    line = page.locator(".lf-fp-context")
    expect(line).to_be_hidden()
    page.keyboard.type("Could")
    expect(line).to_have_text("Comment on the page")
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.press("Backspace")
    expect(line).to_be_hidden()

    page.mouse.click(5, 5)
    expect(field(page)).to_have_attribute("placeholder", status)
    sheen(True)
    declare_idle(serve.page_dir)
    told(page)
    expect(field(page)).not_to_have_attribute("placeholder", status)
    sheen(False)


def test_a_status_that_asks_the_user_to_act_stands_out(browser, serve):
    """A status that only reports reads in the dim face, and one that asks the user to
    act, here to open Leaf's link once the server refuses this tab's key, reads at full
    strength (`pageStatus`, `asks`). Pointing at the field says the status in full,
    where its room would cut it short."""
    url = serve(LONG_PAGE)
    working(serve.page_dir, "Drafting the rollout")
    page = floating(browser, url)
    words = page.locator(".lf-fp-field .lf-compose-placeholder > span")
    panel = page.locator(".lf-floating-panel")

    def alpha():
        color = words.evaluate("node => getComputedStyle(node).color")
        found = re.search(r"/\s*([\d.]+)\)$", color)
        return float(found.group(1)) if found else 1.0

    expect(field(page)).to_have_attribute("placeholder", re.compile("^Claude working"))
    expect(panel).not_to_have_attribute("data-asks", "")
    expect(page.locator(".lf-fp-field")).to_have_attribute(
        "title", re.compile("^Claude is working — Drafting the rollout")
    )

    page.route("**/api/state*", lambda route: route.fulfill(status=401, body="{}"))
    declare_idle(serve.page_dir)
    expect(field(page)).to_have_attribute("placeholder", re.compile("^Key refused"))
    expect(panel).to_have_attribute("data-asks", "")
    assert alpha() == 1.0, "the status asking the user to act reads dimmed"
    expect(page.locator(".lf-fp-field")).to_have_attribute(
        "title", re.compile("^The server no longer accepts this tab's key")
    )
    # Once the caret is in, the field says where words go, and the status's tooltip
    # goes with it.
    field(page).click()
    expect(page.locator(".lf-fp-field")).not_to_have_attribute("title", re.compile("."))
    assert alpha() < 0.5
    # The refused reads recur on the page's clock until it closes.
    page.close()
    consume_browser_errors(page, {"code": "failed-load", "status": 401})


def test_a_notice_stays_in_sight_over_words_in_the_field(browser, serve):
    """A passing notice is said in the empty field's place, and once the caret is in the
    field, whose placeholder then says where the words go, or once words hide that, on
    the line above it, so a refused send's reason is seen beside the words it returned.
    Over an open view, where that line never shows, the leaf's peek says it, above the
    leaf, inside the window and clear of the view's head; on a folded panel the peek
    says it too."""
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Is the window long enough?")
    page = floating(browser, url)
    say = """async (text) => (await window.__lfWidgetApi())
      .notice(text)"""
    line = page.locator(".lf-fp-context")
    peek = page.locator(".lf-fp-peek")
    page.evaluate(say, "Saved for later")
    expect(field(page)).to_have_attribute(
        "placeholder", re.compile(r"^Saved for later")
    )
    field(page).click()
    expect(field(page)).to_have_attribute(
        "placeholder", re.compile(r"^Comment on the page")
    )
    expect(line).to_have_text("Saved for later")
    write(field(page), "Could the rollback cover the weekend?")
    page.evaluate(say, "Not sent: the page is offline")
    expect(line).to_have_text("Not sent: the page is offline")
    expect(peek).to_be_hidden()

    # In a thread the focused field still says its words go there, and the peek says
    # the notice, as it does a refused send's reason over the words it returned.
    page.locator("body").focus()
    page.keyboard.press("t")
    expect(page.locator(".lf-fp-view[data-view=thread]")).to_be_visible()
    page.evaluate(say, "2 agent messages in 2 threads")
    field(page).click()
    expect(field(page)).to_have_attribute(
        "placeholder", re.compile(r"^Reply in this thread")
    )
    expect(peek).to_have_text("2 agent messages in 2 threads")
    write(field(page), "And the weekend?")
    page.evaluate(say, "Not sent: the page is offline")
    expect(peek).to_have_text("Not sent: the page is offline")
    expect(line).to_be_hidden()
    settled(page)
    seat = page.evaluate(
        """() => {
          const box = (selector) => document.querySelector(selector).getBoundingClientRect();
          const [peek, head, leaf] = ['.lf-fp-peek', '.lf-fp-head', '.lf-fp-leaf'].map(box);
          return {
            inWindow: peek.left >= 0 && peek.right <= innerWidth && peek.top >= 0,
            belowHead: peek.top - head.bottom,
            aboveLeaf: leaf.top - peek.bottom,
            fromLeaf: peek.left - leaf.left,
          };
        }"""
    )
    assert seat["inWindow"], seat
    assert seat["belowHead"] >= 0, seat
    assert seat["aboveLeaf"] >= 0, seat
    assert abs(seat["fromLeaf"]) < 0.5, seat
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")

    # Folded to the leaf, the panel has no field, and the leaf's peek says it.
    page.locator("body").focus()
    page.keyboard.press(".")
    expect(page.locator(".lf-floating-panel")).to_have_attribute("data-rest", "mark")
    page.evaluate(say, "Reconnected")
    expect(peek).to_be_visible()
    expect(peek).to_have_text("Reconnected")


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
    # Its mark is its own: the question mark is help's, as `?` and the menu's
    # Keyboard shortcuts row say.
    expect(chip.locator("svg")).not_to_have_attribute("data-lf-icon", "question")
    chip.click()
    view = page.locator(".lf-fp-view[data-view=queue]")
    cards = view.locator(".lf-fp-on-item")
    expect(cards).to_have_count(2)
    expect(cards.first).to_contain_text("How should the schema migrate?")
    settled(page)
    first, second = cards.first.bounding_box(), cards.nth(1).bounding_box()
    with sending(page, "the answer"):
        cards.first.locator(".lf-fp-answer", has_text="Shim").click()
    answer = events_model.read_events(serve.page_dir)[-1]
    assert (answer["kind"], answer["widget"]) == ("action", "schema")
    expect(cards.first.locator(".lf-fp-said")).to_have_text(
        re.compile(r"^Answered: Shim the old schema")
    )
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
    menu: the leaf's menu, whose row names the key as keys, apart from its value, and
    that key. It lists each version,
    marks the one shown, travels to another, and holds the page's approval, which
    records the sign-off."""
    url = serve(SIGN_OFF)
    stamp_page(
        serve.page_dir, SIGN_OFF.replace("Paragraph 0.", "Paragraph zero."), "two"
    )
    page = floating(browser, url)
    view = page.locator(".lf-fp-view[data-view=versions]")
    page.locator(".lf-fp-leaf").click()
    row = page.locator(".lf-fp-menu .lf-fp-item", has_text="Versions")
    expect(row.locator(".lf-fp-value")).to_have_text(re.compile(r"^v\d+$"))
    keys = row.locator(".lf-binding-sequence")
    expect(keys.locator("kbd.lf-key-badge")).to_have_text(["g", "V"])
    expect(keys).to_have_attribute("aria-label", "g then V")
    row.click()
    expect(view).to_be_visible()
    page.keyboard.press("Escape")
    expect(view).to_have_count(0)
    page.locator("body").focus()
    page.keyboard.press("g")
    page.keyboard.press("Shift+V")
    expect(view).to_be_visible()
    expect(page.locator("#lf-versions")).to_be_hidden()
    expect(view.locator(".lf-fp-version")).to_have_count(2)
    expect(view.locator(".lf-fp-version[data-current]")).to_contain_text("Showing")
    # The list is one stop for Tab, which the arrows walk through each version and its
    # Compare to the approval.
    stops = view.locator(".lf-fp-item:not(:disabled), .lf-fp-compare")
    view.focus()
    page.keyboard.press("ArrowDown")
    expect(stops.first).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(stops.nth(1)).to_be_focused()
    page.keyboard.press("End")
    expect(stops.last).to_be_focused()
    expect(view.locator("[tabindex='0']")).to_have_count(1)

    with sending(page, "the approval"):
        view.locator(".lf-fp-item", has_text="Approve version").click()
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "done"

    other = view.locator(".lf-fp-version:not([data-current]) .lf-fp-label")
    number = re.search(r"v\d+", other.inner_text()).group(0)
    other.click()
    expect(page).to_have_url(re.compile(rf"/versions/{number}\b"))


def test_an_older_version_says_so_in_the_row_and_one_press_opens_the_latest(
    browser, serve
):
    """While the page shows a version older than the latest, the row says which beside
    the marks, which keep their seats, since the field gives up the room; its one press,
    which the keyboard reaches in the row's order, opens the latest, and the notice goes
    with it: in place on a tab the agent has since revised, and from a version the user
    travelled back to."""
    url = serve(LONG_PAGE)
    page = floating(browser, url)
    notice = page.locator(".lf-fp-row-notice")
    marks = page.locator(".lf-fp-quick")
    settled(page)
    seats = marks.bounding_box()
    expect(notice).to_be_hidden()

    # The agent revises the page under the open tab, which keeps what it shows.
    stamp_page(
        serve.page_dir, LONG_PAGE.replace("Paragraph 0.", "Paragraph zero."), "two"
    )
    told(page)
    expect(notice).to_have_text(re.compile(r"^\s*v1 of 2\s*·\s*Latest\s*$"))
    settled(page)
    assert marks.bounding_box() == seats
    notice.locator("button").click()
    expect(page.locator("main")).to_contain_text("Paragraph zero.")
    expect(notice).to_be_hidden()

    page.locator(".lf-fp-leaf").click()
    page.locator(".lf-fp-menu .lf-fp-item", has_text="Versions").click()
    page.locator(".lf-fp-version:not([data-current]) .lf-fp-label").click()
    expect(page).to_have_url(re.compile(r"/versions/v1\b"))
    expect(notice).to_have_text(re.compile(r"^\s*v1 of 2\s*·\s*Latest\s*$"))
    page.locator(".lf-fp-on-user").focus()
    page.keyboard.press("Shift+Tab")
    expect(notice.locator("button")).to_be_focused()
    page.keyboard.press("Enter")
    expect(page).not_to_have_url(re.compile(r"/versions/"))
    expect(page.locator("main")).to_contain_text("Paragraph zero.")
    expect(notice).to_be_hidden()


def test_the_on_me_walk_arrives_at_the_approval_in_the_panel(browser, serve):
    """The version's approval waits on the user in On me, and `m` arrives at it where
    this chrome shows it: the panel's On view, standing on its Approve."""
    url = serve(SIGN_OFF)
    stamp_page(serve.page_dir, SIGN_OFF, "one")
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("m")
    approve = page.locator(".lf-fp-view[data-view=queue] [data-approval] .lf-fp-answer")
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
    card = page.locator(".lf-fp-view[data-view=queue] [data-approval]")
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
    view = page.locator(".lf-fp-view[data-view=queue]")
    approve = view.locator("[data-approval] .lf-fp-answer")
    expect(approve).to_be_focused()
    expect(approve).to_be_in_viewport()
    box, room = approve.bounding_box(), view.bounding_box()
    assert (
        room["y"] <= box["y"]
        and box["y"] + box["height"] <= room["y"] + room["height"] + 1
    ), (box, room)


def test_a_mode_entered_from_the_panel_offers_its_way_out_in_the_row(browser, serve):
    """Annotations, a row of the leaf's menu, opens a list whose Draw mode, while it
    holds the banner's gesture seat, stands its steps in the row in the counts' place;
    Exit leaves the mode and the counts return. Picking an element is left to the page,
    where selecting words or pressing `s` starts it, so Annotations doesn't list it."""
    page = floating(browser, serve(LONG_PAGE, comments=1))
    page.locator(".lf-fp-leaf").click()
    page.locator(".lf-fp-menu .lf-fp-item", has_text="Annotations").click()
    expect(page.locator(".lf-fp-item", has_text="Capture area")).to_be_visible()
    expect(page.locator(".lf-fp-item", has_text="Select element")).to_have_count(0)
    page.locator(".lf-fp-item", has_text="Draw mode").click()
    exit_step = page.locator(".lf-fp-step", has_text="Exit Draw mode")
    expect(exit_step).to_be_visible()
    expect(page.locator(".lf-fp-on-user")).to_have_count(0)
    exit_step.click()
    expect(page.locator(".lf-fp-step")).to_have_count(0)
    expect(page.locator(".lf-fp-on-user")).to_be_visible()


def test_the_leaf_s_menu_marks_what_opens_a_list_and_leaves_key_conveniences_out(
    browser, serve
):
    """The row holds the leaf, the field and the two counts, and the leaf's menu holds
    the rest. A menu row that opens a list of its own ends in a chevron. Navigate lists
    where a reader goes from a menu; the keyboard's conveniences for where they stand
    (Page Map, Resume writing, Restore selection, Align current item at top) keep their
    keys, and the menu leaves them out."""
    page = floating(browser, serve(LONG_PAGE, comments=1))
    expect(page.locator(".lf-fp-quick button")).to_have_count(2)
    page.locator(".lf-fp-leaf").click()
    menu = page.locator(".lf-fp-menu")
    for opens in ("Navigate", "Annotations", "About this page"):
        expect(menu.locator(".lf-fp-item[data-opens]", has_text=opens)).to_have_count(1)
    expect(
        menu.locator(".lf-fp-item[data-opens]", has_text="Keyboard shortcuts")
    ).to_have_count(0)
    menu.locator(".lf-fp-item", has_text="Navigate").click()
    listed = page.locator(".lf-fp-view[data-view=group] .lf-fp-label")
    expect(listed.filter(has_text="Search page")).to_have_count(1)
    assert set(listed.all_inner_texts()) <= {"All pages", "Search page"}


def test_every_chevron_in_the_menu_is_drawn_as_a_stroke_at_one_size(browser, serve):
    """A chevron is a Leaf icon like any other, drawn in the row's muted ink rather than
    filled in the browser's black, and at one size whatever its row ends with, so the
    chevrons stand in one column."""
    page = floating(browser, serve(LONG_PAGE, comments=1))
    page.locator(".lf-fp-leaf").click()
    drawn = page.locator(".lf-fp-menu .lf-fp-chevron").evaluate_all(
        """chevrons => chevrons.map(c => {
            const style = getComputedStyle(c), box = c.getBoundingClientRect();
            return {fill: style.fill, stroke: style.stroke, width: box.width,
                    right: Math.round(box.right)};
        })"""
    )
    assert len(drawn) >= 3, drawn
    assert all(c["fill"] == "none" and c["stroke"] != "none" for c in drawn), drawn
    assert {(c["width"], c["right"]) for c in drawn} == {(12, drawn[0]["right"])}, drawn


def test_the_leaf_s_menu_is_one_tab_stop_its_keys_walk(browser, serve):
    """Opened by a press, the leaf's menu is walked from the leaf by the arrows, Home and
    End, as one stop for Tab; Tab leaves it for the field, putting it away. On the leaf
    and on a count, as Escape leaves the user, the page's two-key Go-to still answers."""
    page = floating(browser, serve(LONG_PAGE, comments=1))
    leaf = page.locator(".lf-fp-leaf")
    leaf.click()
    rows = page.locator(".lf-fp-menu .lf-fp-item:not(:disabled)")
    page.keyboard.press("ArrowDown")
    expect(rows.first).to_be_focused()
    page.keyboard.press("End")
    expect(rows.last).to_be_focused()
    expect(rows.last).to_have_text(re.compile("Fold to the leaf"))
    page.keyboard.press("Home")
    expect(rows.first).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(rows.nth(1)).to_be_focused()
    expect(page.locator(".lf-fp-menu button[tabindex='0']")).to_have_count(1)
    page.keyboard.press("Tab")
    expect(page.locator(".lf-fp-menu")).to_be_hidden()
    expect(field(page)).to_be_focused()

    threads = page.locator(".lf-fp-view[data-view=threads]")
    for door in (leaf, page.locator(".lf-fp-on-user")):
        door.focus()
        page.keyboard.press("g")
        page.keyboard.press("Shift+T")
        expect(threads).to_be_visible()
        page.keyboard.press("Escape")
        expect(threads).to_have_count(0)


def test_the_leaf_s_menu_says_the_agent_s_state_once(browser, serve):
    """The menu's head says the agent's state in a word, over its one line, and under
    that only what the banner's disclosure adds to the line: while the agent works, the
    disclosure's sentence restates the line, so what waits on the user is all it adds."""
    url = serve(ASK_PAGE)
    working(serve.page_dir, "Drafting the rollout")
    page = floating(browser, url)
    line = re.compile(r"^Claude working\b.* — Drafting the rollout")
    page.locator(".lf-fp-leaf").click()
    head = page.locator(".lf-fp-state")
    expect(head.locator("b")).to_have_text("Working")
    expect(head.locator("span").first).to_have_text(line)
    expect(head.locator(".lf-fp-explain")).to_have_text(
        re.compile(r"^Waiting on me: 2 asks\. Waiting on Claude: 1 to-do")
    )


def test_news_under_the_open_menu_moves_nothing_in_it(browser, serve):
    """The leaf's menu stands on the leaf and grows upward, so while it stands it holds
    what it showed: a status that wraps to more lines, or fewer, re-wraps inside the
    lines its head first took, and a row a revision offers joins at the next opening, so
    neither the head's words nor the rows move. The shift watch holds the words; the
    boxes are read here."""
    page = floating(browser, serve(LONG_PAGE))
    leaf = page.locator(".lf-fp-leaf")
    leaf.click()
    head = page.locator(".lf-fp-state")
    expect(head.locator("b")).to_have_text("Away")
    settled(page)
    boxes = (
        "() => [...document.querySelectorAll('.lf-fp-menu > *')]"
        ".map(n => { const r = n.getBoundingClientRect(); return [r.top, r.height]; })"
    )
    before = page.evaluate(boxes)
    page.wait_for_timeout(600)  # Let Chrome's recent-input grace expire before news.
    for line in (
        "Drafting the rollout plan for the schema migration across every cluster",
        "Checking",
    ):
        working(serve.page_dir, line)
        expect(head.locator("span").first).to_contain_text(line)
        assert page.evaluate(boxes) == before

    source = (serve.page_dir / "index.html").read_text()
    stamp_page(serve.page_dir, source.replace("Filler.", "Filler!", 1), "revised")
    newer = re.compile("New page available → open v2")
    expect(page.locator(".lf-latest-chip")).to_have_text(newer)
    assert page.evaluate(boxes) == before
    page.keyboard.press("Escape")
    leaf.click()
    expect(page.locator(".lf-fp-menu .lf-fp-item", has_text=newer)).to_be_visible()


def test_each_view_s_list_is_one_tab_stop_its_keys_walk(browser, serve):
    """Threads and On are walked as the leaf's menu is: one stop for Tab, which the
    arrows, Home and End move, and from the view a pointer opened, ↓ enters its first
    row. Threads' rows leave out the state the selected filter already says, its
    counted tab says 0 rather than leave a gap where a count would go, and the marks
    that open both name themselves on hover."""
    url = serve(ASK_PAGE)
    for text in ("Is the window long enough?", "Who watches the weekend?"):
        panel_comment(serve.page_dir, text)
    page = floating(browser, url)
    on_mark, threads_mark = (
        page.locator(".lf-fp-on-user"),
        page.locator(".lf-fp-threads"),
    )
    expect(on_mark).to_have_attribute("title", "On me: 2")
    expect(threads_mark).to_have_attribute("title", "Threads, 2 open")

    threads_mark.click()
    view = page.locator(".lf-fp-view[data-view=threads]")
    expect(view).to_be_focused()
    rows = view.locator(".lf-fp-thread")
    expect(rows).to_have_count(2)
    expect(view.locator(".lf-fp-value", has_text="Open")).to_have_count(0)
    page.keyboard.press("ArrowDown")
    expect(rows.first).to_be_focused()
    page.keyboard.press("End")
    expect(rows.last).to_be_focused()
    page.keyboard.press("Home")
    expect(rows.first).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(rows.nth(1)).to_be_focused()
    expect(view.locator("[tabindex='0']")).to_have_count(1)
    expect(rows.nth(1)).to_have_attribute("tabindex", "0")
    unread = page.locator(".lf-fp-filters button", has_text="Unread")
    expect(unread.locator(".lf-fp-count[data-zero]")).to_have_text("0")

    on_mark.click()
    expect(page.get_by_role("button", name="On me 2", exact=True)).to_be_visible()
    cards = page.locator(".lf-fp-view[data-view=queue] .lf-fp-on-item")
    expect(cards).to_have_count(2)
    page.keyboard.press("ArrowDown")
    expect(cards.first).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(cards.nth(1)).to_be_focused()
    expect(cards.first).to_have_attribute("tabindex", "-1")


def test_skip_to_leaf_controls_lands_in_the_panel(browser, serve):
    """The page's first Tab stop, Skip to Leaf controls, lands in the panel that stands
    for Leaf's controls: in its field, or on the leaf where the field takes no words, as
    in a resolved thread, or while the panel is folded."""
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Is the window long enough?")
    page = floating(browser, url)
    skip = page.locator("body > .lf-skip")
    skip.focus()
    page.keyboard.press("Enter")
    expect(field(page)).to_be_focused()

    page.locator("body").focus()
    page.keyboard.press("t")
    settle = page.locator(".lf-fp-settle")
    with sending(page, "the resolve"):
        settle.click()
    expect(settle).to_have_text("Reopen", use_inner_text=True)
    skip.focus()
    page.keyboard.press("Enter")
    expect(page.locator(".lf-fp-leaf")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-fp-view")).to_have_count(0)

    page.locator("body").focus()
    page.keyboard.press(".")
    expect(page.locator(".lf-floating-panel")).to_have_attribute("data-rest", "mark")
    skip.focus()
    page.keyboard.press("Enter")
    expect(page.locator(".lf-fp-leaf")).to_be_focused()


def test_a_menu_row_that_puts_the_menu_away_leaves_the_user_on_the_leaf(browser, serve):
    """A row's press takes its row away with the menu, so the user stands on the leaf
    that opened it: a row in a view the menu opened returns there, and folding stands
    on the folded leaf."""
    page = floating(browser, serve(LONG_PAGE, comments=1))
    leaf = page.locator(".lf-fp-leaf")
    menu = page.locator(".lf-fp-menu")
    leaf.click()
    menu.locator(".lf-fp-item", has_text="Annotations").click()
    page.locator(".lf-fp-view[data-view=group] .lf-fp-item").last.click()
    expect(page.locator(".lf-fp-view")).to_have_count(0)
    expect(leaf).to_be_focused()

    leaf.click()
    menu.locator(".lf-fp-item", has_text="Fold to the leaf").click()
    expect(page.locator(".lf-floating-panel")).to_have_attribute("data-rest", "mark")
    expect(leaf).to_be_focused()


def test_a_layer_a_menu_row_opened_closes_back_to_the_leaf(browser, serve):
    """The command reference a menu row opens records the leaf as where it was opened
    from, since the row went with the menu, so Escape returns the user there."""
    page = floating(browser, serve(LONG_PAGE, comments=1))
    page.locator(".lf-fp-leaf").click()
    page.locator(".lf-fp-menu .lf-fp-item", has_text="Keyboard shortcuts").click()
    reference = page.locator(".lf-command-reference")
    expect(reference).to_be_visible()
    page.keyboard.press("Escape")
    expect(reference).to_be_hidden()
    expect(page.locator(".lf-fp-leaf")).to_be_focused()


def test_tab_from_the_field_reaches_dictate(browser, serve):
    """Dictate stands beside the field while the user writes in the panel and is gone at
    rest, so Tab from the field lands on it rather than hiding it as the field lets go.
    """
    page = floating(browser, serve(LONG_PAGE))
    dictate = page.locator(".lf-fp-box .lf-compose-dictate")
    expect(dictate).to_be_hidden()
    field(page).click()
    expect(dictate).to_be_visible()
    page.keyboard.press("Tab")
    # The field's letting go repaints the box a frame later; Dictate is still there.
    page.evaluate(
        "new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
    )
    expect(dictate).to_be_visible()
    expect(dictate).to_be_focused()


ROW_CENTRES = """() => {
  const centre = (selector) => {
    const node = document.querySelector(selector);
    if (!node || !node.getClientRects().length) return null;
    const box = node.getBoundingClientRect();
    return (box.top + box.bottom) / 2;
  };
  const text = document.querySelector('.lf-fp-field leaf-text').getBoundingClientRect();
  return {
    leaf: centre('.lf-fp-leaf .lf-dot'),
    line: text.bottom - 16,
    dictate: centre('.lf-fp-field .lf-compose-dictate svg'),
    send: centre('.lf-fp-field .lf-compose-submit svg'),
    count: centre('.lf-fp-on-user svg'),
    words: text.right,
    press: document.querySelector('.lf-fp-field .lf-compose-submit')
      .getBoundingClientRect().left,
  };
}"""


def test_the_row_s_marks_and_presses_share_the_words_line(browser, serve):
    """Everything in the row stands on the one line the words are written on: the
    leaf, Dictate beside the field, the counts, and Send where they stood while the user
    types, each centred on the field's last line of words, however many lines it holds.
    Send and Dictate stand beside the words rather than over their end."""
    page = floating(browser, serve(LONG_PAGE))
    field(page).click()
    settled(page)
    seats = page.evaluate(ROW_CENTRES)
    for mark in ("leaf", "dictate", "count"):
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
    assert seats["press"] >= seats["words"], seats


def test_a_finger_finds_the_keyboard_s_conveniences_under_navigate(browser, serve):
    """Where no keyboard is there to reach them, the conveniences the desk's menu leaves
    to their keys stand under Navigate, so a finger keeps a way to each."""
    context = browser.new_context(
        viewport={"width": 1280, "height": 800}, has_touch=True
    )
    context.add_init_script(FLOATING)
    page = open_page(browser, serve(LONG_PAGE, comments=1), context=context)
    assert page.evaluate("() => matchMedia('(pointer: coarse)').matches")
    page.locator(".lf-fp-leaf").click()
    page.locator(".lf-fp-menu .lf-fp-item", has_text="Navigate").click()
    listed = page.locator(".lf-fp-view[data-view=group] .lf-fp-label")
    expect(listed.filter(has_text="Search page")).to_have_count(1)
    expect(listed.filter(has_text="Align current item at top")).to_have_count(1)


def test_the_share_link_shows_where_it_can_be_selected_without_a_clipboard(
    browser, serve
):
    """A browser offers the clipboard only to a secure context, so a page read from
    another machine over plain http cannot copy. The menu's Copy link gives way to the
    link in About, in a field the user can select, with no copy control that could only
    fail, saying what the link grants."""
    no_clipboard = "Object.defineProperty(Navigator.prototype, 'clipboard', {get: () => undefined});"
    page = open_page(
        browser, serve(LONG_PAGE), init_script=f"{FLOATING}\n{no_clipboard}"
    )
    page.locator(".lf-fp-leaf").click()
    expect(page.locator(".lf-fp-menu")).not_to_contain_text("Copy link")
    page.locator(".lf-fp-menu .lf-fp-item", has_text="About this page").click()
    share = page.locator(".lf-fp-copy", has_text="Link")
    link = share.locator(".lf-fp-copy-text")
    expect(link).to_have_value(re.compile(r"^http://.*[?&]t="))
    expect(link).to_have_accessible_name("Link")
    expect(share.get_by_role("button", name=re.compile("Copy"))).to_have_count(0)
    expect(share).to_contain_text("Grants access")
    link.focus()
    selected = (
        "(e => e.value.slice(e.selectionStart, e.selectionEnd))(document.activeElement)"
    )
    assert page.evaluate(selected) == link.input_value()


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
