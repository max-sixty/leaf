"""The floating panel: Leaf's one chrome, a box over the page's foot.

Each test is one journey a user takes through the panel: writing a page comment and replying in the same field, settling the thread, finding
threads and taking in news, answering obligations, travelling between versions, and
folding the panel to the leaf in the window's corner and back."""

import base64
import json
import re
from datetime import datetime, timedelta

import pytest
from click.testing import CliRunner
from interact_support import (
    append_carried_log_record,
    declare_idle,
    declare_work,
    working,
    write_record,
)
from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import interaction_log as interaction_model
from leaf import service as service_model
from leaf import state as cleanup_model
from leaf import thread as thread_model
from leaf.render_checks import one_frame, wait_until_ready
from model_folds import leaf_page
from playwright.sync_api import expect
from render_cases_interaction import LIVE_V1, LIVE_V2, live_url, panel_comment
from render_cases_layout import solid_png
from render_harness import (
    LONG_PAGE,
    consume_browser_errors,
    expect_panel_says,
    holding,
    http_error_console,
    open_page,
    resized,
    round_trip,
    select_words,
    sending,
    stamp_page,
    ticked,
    told,
    watched,
    write,
)
from render_harness import leaf_page as titled_page

SIGN_OFF = LONG_PAGE.replace(
    "<title>long</title>",
    '<title>long</title><meta name="lf-review" content="sign-off">',
)
OBLIGATION_PAGE = leaf_page(
    "obligation",
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


# Each field's closed shadow root, so a test can read inside it.
EDITOR_ROOTS = """
  window.editorRoots = new Map();
  const attach = Element.prototype.attachShadow;
  Element.prototype.attachShadow = function(options) {
    const root = attach.call(this, options);
    if (this.localName === 'leaf-text') window.editorRoots.set(this, root);
    return root;
  };
"""


def floating(browser, url):
    page = open_page(browser, url)
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
    its new thread above the row, the same field now replying there, and resolving the
    thread from its head moves the user on to Threads, where `z` stands them on its row. The focused field names where the
    words go, and once they hide that, nothing does: with no view open they go to the
    page, and over the thread its head names it. Escape, once the caret has left the field, puts the
    thread away."""
    page = floating(browser, serve(LONG_PAGE))
    write(field(page), "Could the rollback cover the weekend?")
    expect(page.locator(".lf-fp-context")).to_be_hidden()
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
    # Resolving moves the user on: with no other thread open, back to Threads.
    expect(page.locator(".lf-fp-view[data-view=threads]")).to_be_visible()
    with sending(page, "the undo"):
        page.keyboard.press("z")
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "undo"
    row = page.locator(".lf-fp-view[data-view=threads] .lf-fp-thread")
    expect(row).to_be_focused()
    page.keyboard.press("Enter")
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
    # Putting the view away returns the user to the page.
    assert page.evaluate(
        "() => !document.querySelector('.lf-floating-panel').contains(document.activeElement)"
    )

    page.locator(".lf-fp-threads").click()
    inventory = page.locator(".lf-fp-view[data-view=threads]")
    expect(inventory).to_be_visible()
    field(page).click()
    page.keyboard.press("Escape")
    expect(inventory).to_be_visible()
    expect(page.locator(".lf-fp-leaf")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-fp-view")).to_have_count(0)
    expect(page.locator(".lf-fp-leaf")).not_to_be_focused()


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
    the caret back in the reply with its words, `r` resolves the thread from the view, a
    message in it or its Resolve and moves the user on,
    here back to Threads with no other thread open, `z` takes the resolve back and
    stands on its row, Enter on a resolved thread reopens it, and `e` on a message opens the agent's
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
    threads = page.locator(".lf-fp-view[data-view=threads]")
    with sending(page, "the resolve"):
        page.keyboard.press("r")
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "resolve"
    expect(threads).to_be_visible()
    with sending(page, "the undo"):
        page.keyboard.press("z")
    row = threads.locator(".lf-fp-thread")
    expect(row).to_be_focused()
    page.keyboard.press("Enter")
    expect(thread).to_be_visible()
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
    expect(threads).to_be_visible()

    # A resolved thread opened from Threads' Resolved list reopens on Enter.
    page.locator(".lf-fp-filters button", has_text="Resolved").click()
    page.locator(".lf-fp-view[data-view=threads] .lf-fp-thread").first.click()
    expect(settle).to_have_text("Reopen", use_inner_text=True)
    thread.focus()
    with sending(page, "the reopen"):
        page.keyboard.press("Enter")
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "unresolve"
    expect(settle).to_have_text("Resolve", use_inner_text=True)


def test_a_reaction_in_the_view_stands_as_its_chip_alone(browser, serve):
    """A reaction to the agent's reply shows once in the thread's view, as the pressed
    chip on the reply, as a card in Threads draws it: before the server answers and
    after, the view draws no message of its own for it."""
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
    reply = thread.locator(".lf-msg.agent")
    reply.click()
    page.keyboard.press("e")
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("1")
    holding(page, held, 1, "the reaction")
    pressed = reply.locator(".lf-react[aria-pressed=true]")
    expect(pressed).to_have_count(1)
    expect(thread.locator(".lf-msg")).to_have_count(2)
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    assert events_model.read_events(serve.page_dir)[-1]["token"]
    expect(pressed).to_have_count(1)
    expect(thread.locator(".lf-msg")).to_have_count(2)


def test_resolving_a_thread_from_threads_moves_on_to_the_next(browser, serve):
    """Resolving the thread open from Threads moves the user on to the next open
    thread, standing on its view, while the field says the thread was resolved, so a
    second `r` resolves that one; taking a resolve back leaves the user where they moved on to;
    with none left, the user is back at Threads. Escape there puts
    the view away and returns the user to the page."""
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Is the window long enough?")
    panel_comment(serve.page_dir, "Should the mobile cohort wait?")
    page = floating(browser, url)
    page.locator(".lf-fp-threads").click()
    page.locator(".lf-fp-view[data-view=threads] .lf-fp-thread").first.click()
    # The thread standing open: moving on to the next thread fades the one it leaves.
    thread = page.locator(".lf-fp-view[data-view=thread]:not([data-leaving])")
    expect(thread).to_be_visible()
    first = page.locator(".lf-fp-head .lf-fp-title").inner_text()
    thread.focus()
    with sending(page, "the first resolve"):
        page.keyboard.press("r")
    expect(page.locator(".lf-fp-head .lf-fp-title")).not_to_have_text(first)
    expect(thread).to_be_visible()
    expect(thread).to_be_focused()
    expect(page.locator(".lf-fp-field leaf-text")).to_have_attribute(
        "data-says", "notice"
    )
    expect(page.locator(".lf-fp-row")).to_contain_text("Resolved the thread")
    second = page.locator(".lf-fp-head .lf-fp-title").inner_text()
    # Taking the first resolve back leaves the user on the thread they moved on to.
    with sending(page, "the undo"):
        page.keyboard.press("z")
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "undo"
    expect(page.locator(".lf-fp-head .lf-fp-title")).to_have_text(second)
    expect(thread).to_be_focused()
    with sending(page, "the second resolve"):
        page.keyboard.press("r")
    resolved = [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "resolve"
    ]
    assert len(resolved) == 2
    # The first thread, reopened, is the one open thread left, so the user moves to it.
    expect(page.locator(".lf-fp-head .lf-fp-title")).to_have_text(first)
    with sending(page, "the last resolve"):
        page.keyboard.press("r")
    expect(page.locator(".lf-fp-view[data-view=threads]")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-fp-view")).to_have_count(0)
    expect(page.locator(".lf-fp-leaf")).not_to_be_focused()


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
    expect(page.locator(".lf-fp-view[data-view=threads]")).to_be_visible()
    expect(field(page)).to_have_attribute("name", "comment")


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
            "text": "The window covers it. " * 300,
        },
    )
    news = view.locator(".lf-fp-new-reply")
    expect(news).to_be_visible()
    news.focus()
    expect(news).to_be_focused()
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


def test_on_shows_an_obligation_as_its_message_and_reply_comes_back(browser, serve):
    """A question the agent asked in a thread reads in the On view as its message, drawn
    whole as the thread draws it, so what it introduces after a colon is there with it.
    Reply opens its thread with On behind it, where the back link returns."""
    url = serve(LONG_PAGE)
    panel_comment(
        serve.page_dir,
        "Which build should ship? These are the candidates:\n\n- #4813 schedule\n"
        "- #4812 manual",
        author="agent",
        question="Which build should ship?",
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
    on: seat('.lf-fp-quiet'),
    settle: seat('.lf-fp-settle'),
    close: seat('.lf-fp-close'),
  };
}"""


def test_news_in_an_open_thread_moves_nothing_at_its_head(browser, serve):
    """A thread's head holds each control where it stood while the thread changes under
    it. Retitled long or short, the title gives or takes room at its own end, and Back,
    On the page, Resolve and Close stay put; detached by a revision, On the page leaves its seat empty; resolved by the
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
    assert page.evaluate(HEAD_SEATS) == seats


# What news arriving must leave where it stood: the open thread's message, read word
# by word, and how much of its title the head shows.
HELD_READING = """() => {
  const view = document.querySelector('.lf-fp-view[data-view=thread]');
  const box = (node) => {
    const r = node.getBoundingClientRect();
    return [r.left, r.top, r.right, r.bottom];
  };
  const title = document.querySelector('.lf-fp-head .lf-fp-title');
  return {
    message: [...view.querySelectorAll('.lf-msg-head > *, .lf-msg-body')].map(box),
    titleEnd: title.getBoundingClientRect().right,
  };
}"""


def test_held_news_reads_whole_on_the_thread_s_head_line(browser, serve):
    """News arriving while the user writes in an open thread waits behind a notice on the
    view's head line. It reads
    whole, the title shortening to give it room, and nothing else at the head or in the
    messages moves; no message head carries it. Pressing it shows what was held."""
    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir,
        "Which jobs should start first once the export and the reconciler have both "
        "landed on the new cluster?",
        author="agent",
    )
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(".lf-fp-view[data-view=thread]")
    expect(view.locator(".lf-msg")).to_have_count(1)
    write(field(page), "I think the export")
    settled(page)
    seats = page.evaluate(HEAD_SEATS)
    reading = page.evaluate(HELD_READING)

    for text in (
        "The export job first, since the reports read it.",
        "Then the reconciler, once the export has landed.",
    ):
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
    notice = page.locator(".lf-fp-head .lf-thread-news")
    expect(notice).to_have_text("2 new replies")
    expect(view.locator(".lf-msg")).to_have_count(1)
    settled(page)
    assert notice.evaluate("node => node.scrollWidth <= node.clientWidth")
    assert page.evaluate(HEAD_SEATS) == seats
    held = page.evaluate(HELD_READING)
    assert held["message"] == reading["message"]
    assert held["titleEnd"] < reading["titleEnd"], (reading, held)
    expect(view.locator(".lf-msg-head .lf-thread-news")).to_have_count(0)

    notice.click()
    expect(view.locator(".lf-msg")).to_have_count(3)
    expect(notice).to_be_hidden()
    expect(field(page)).to_have_js_property("value", "I think the export")


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


def test_the_leaf_version_is_one_press_in_the_leaf_s_menu(browser, serve):
    """The Leaf version is copied from a row of the leaf's menu itself, as the page's
    link is: one press puts the menu away, copies the version's diagnostics and says so
    in the field, and the row's hover name says which Leaf it is. With a clipboard there
    is no About view, which held only those rows."""
    page = floating(browser, serve(LONG_PAGE))
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.locator(".lf-fp-leaf").click()
    menu = page.locator(".lf-fp-menu")
    expect(menu.locator(".lf-fp-item", has_text="About this page")).to_have_count(0)
    row = menu.get_by_role("menuitem", name="Copy Leaf version")
    expect(row).to_have_attribute("title", re.compile("^Leaf "))
    row.click()
    expect(menu).to_be_hidden()
    expect(field(page)).to_have_attribute(
        "placeholder", re.compile("^Leaf version copied")
    )
    assert page.evaluate("navigator.clipboard.readText()").startswith("Leaf layer\n")


def test_copy_link_is_one_press_in_the_leaf_s_menu(browser, serve):
    """The page's link is copied from a row of the leaf's menu itself, in one press that
    puts the menu away and says in the field that the link was copied; its hover name
    says what the link grants."""
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


def test_a_refused_copy_leaves_the_link_to_select_in_about(browser, serve):
    """A clipboard that refuses the write leaves the user the link all the same: the
    press turns the menu to About on the link, in a field they can select, and the field
    says the link was not copied. The failure remains in Errors when the reader
    leaves About."""
    refuses = (
        "Clipboard.prototype.writeText = () => Promise.reject(new Error('refused'));"
    )
    page = open_page(browser, serve(LONG_PAGE), init_script=refuses)
    page.locator(".lf-fp-leaf").click()
    page.locator(".lf-fp-menu").get_by_role("menuitem", name="Copy link").click()
    about = page.locator(".lf-fp-menu[data-level=group]")
    link = about.get_by_label("Link", exact=True)
    expect(link).to_have_value(re.compile(r"^http://.*[?&]t="))
    expect(about.locator(".lf-fp-menu-back")).to_contain_text("About this page")
    expect(field(page)).to_have_attribute("placeholder", re.compile("^Link not copied"))
    about.locator(".lf-fp-menu-back").click()
    page.locator('.lf-fp-menu [data-row="errors"]').click()
    expect(page.locator(".lf-fp-menu .lf-fp-error")).to_contain_text(
        "Link not copied · select it to copy"
    )


def test_page_search_stands_with_its_controls_at_the_panel(browser, serve):
    """Page search's box stands just over the panel's row, where its ✕ stands, rather
    than at the window's head. The box walks its own matches: its up and down arrows
    move the count beside them and leave the query's field focused, so the next letter
    still edits it, and the panel's row keeps its counts. A press on the
    marked match selects it."""
    page = floating(browser, serve(LONG_PAGE))
    page.locator("body").focus()
    page.keyboard.press("/")
    search = page.locator(".lf-page-search")
    expect(search).to_be_visible()
    expect(page.locator('.lf-fp-exit[aria-label="Close search"]')).to_be_visible()
    box = search.bounding_box()
    row = page.locator(".lf-fp-row").bounding_box()
    gap = row["y"] - (box["y"] + box["height"])
    assert 0 <= gap < 24, f"the search box stands {gap:.0f}px over the panel's row"

    previous = search.get_by_role("button", name="Previous match")
    following = search.get_by_role("button", name="Next match")
    expect(following).to_have_attribute("aria-disabled", "true")
    page.keyboard.type("Paragraph 1")
    count = search.locator(".lf-page-search-status")
    expect(count).to_have_text("1 of 11")
    expect(page.locator(".lf-fp-threads")).to_be_visible()
    following.click()
    expect(count).to_have_text("2 of 11")
    previous.click()
    previous.click()
    expect(count).to_have_text("11 of 11")
    page.keyboard.type("0")
    expect(count).to_have_text("1 of 1")
    # A press on the marked match selects it, as Enter does, even once focus has left
    # the box; a control painted over the words keeps its own press.
    mark = page.locator(".lf-page-search-match").first.bounding_box()
    at = (mark["x"] + mark["width"] / 2, mark["y"] + mark["height"] / 2)
    page.evaluate(
        """([x, y]) => {
          const cover = Object.assign(document.createElement("button"), { id: "cover" });
          Object.assign(cover.style, {
            position: "fixed", left: `${x - 4}px`, top: `${y - 4}px`, width: "8px",
            height: "8px",
          });
          cover.addEventListener("click", () => cover.toggleAttribute("data-pressed"));
          document.body.append(cover);
        }""",
        at,
    )
    page.mouse.click(*at)
    expect(page.locator("#cover")).to_have_attribute("data-pressed", "")
    expect(search).to_be_visible()
    page.locator("#cover").evaluate("el => el.remove()")
    page.mouse.click(*at)
    expect(search).to_be_hidden()
    assert page.evaluate("getSelection().toString()") == "Paragraph 10"


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
    held = page.locator(".lf-fp-head .lf-thread-news:visible")
    expect(held).to_be_visible()
    expect(reader.locator(".lf-msg")).to_have_count(2)
    held.click()
    expect(reader.locator(".lf-msg")).to_have_count(3)


AGENDA_PAGE = titled_page(
    "agenda",
    """<h1 id="t">Workshop</h1>
<p id="agenda">The sample agenda has room for one more topic.</p>
<p id="lunch">The schedule leaves an hour at noon for lunch.</p>""",
)


def agenda_threads(page_dir):
    """Three threads in the log in the order they were started: one on the later
    passage, one on the page as a whole, then one on the earlier passage."""
    panel_comment(
        page_dir, "Is lunch provided?", {"section": "lunch", "quote": "schedule leaves"}
    )
    panel_comment(page_dir, "Who signs off?")
    panel_comment(
        page_dir, "Kickoff length", {"section": "agenda", "quote": "one more topic"}
    )


def threads_rows(page):
    page.locator(".lf-fp-threads").click()
    return page.locator(".lf-fp-view[data-view=threads] .lf-fp-thread")


def test_threads_read_in_the_page_s_order(browser, serve):
    """Threads lists its rows in the page's order, the one `t` walks, rather than the
    order they were started: the thread on the earlier passage, started last, leads, and
    a comment on the page as a whole stands under every thread on a passage."""
    url = serve(AGENDA_PAGE)
    agenda_threads(serve.page_dir)
    page = floating(browser, url)
    expect(threads_rows(page).locator(".lf-fp-label")).to_have_text(
        ["Kickoff length", "Is lunch provided?", "Who signs off?"]
    )


HOVER_LIT = "() => [...(CSS.highlights.get('lf-mark-hover') ?? [])].map(String)"
MARKED_ROW = re.compile(r"\blf-mark-hover\b")


def test_a_thread_s_row_and_its_passage_light_each_other(browser, serve):
    """In Threads, the pointer on a thread's row lights the words it is about, as the
    pointer on those words does, and the pointer on those words, or on their margin
    entry, marks the row. Neither moves anything or takes focus."""
    url = serve(AGENDA_PAGE)
    agenda_threads(serve.page_dir)
    page = floating(browser, url)
    rows = threads_rows(page)
    kickoff = rows.filter(has_text="Kickoff length")
    lunch = rows.filter(has_text="Is lunch provided?")
    expect(lunch).to_be_visible()
    settled(page)
    page.evaluate("() => { window.focusBefore = document.activeElement; }")
    boxes = "() => [...document.querySelectorAll('.lf-fp-thread, main p')].map(n => JSON.stringify(n.getBoundingClientRect()))"
    before = page.evaluate(boxes)

    kickoff.hover()
    page.wait_for_function(f"() => ({HOVER_LIT})().join() === 'one more topic'")
    expect(kickoff).to_have_class(MARKED_ROW)

    words = page.evaluate(
        """() => {
          const range = [...CSS.highlights.get('lf-mark')]
            .find((candidate) => String(candidate) === 'schedule leaves');
          const box = range.getClientRects()[0];
          return { x: box.left + box.width / 2, y: box.top + box.height / 2 };
        }"""
    )
    page.mouse.move(words["x"], words["y"])
    expect(lunch).to_have_class(MARKED_ROW)
    expect(kickoff).not_to_have_class(MARKED_ROW)
    page.wait_for_function(f"() => ({HOVER_LIT})().join() === 'schedule leaves'")

    entry = page.evaluate(
        """() => {
          const passage = document.getElementById('agenda').getBoundingClientRect();
          const entry = [...document.querySelectorAll('.lf-margin-entry')]
            .map((node) => node.getBoundingClientRect())
            .find((box) => box.width && box.top < passage.bottom && box.bottom > passage.top);
          return { x: entry.left + entry.width / 2, y: entry.top + entry.height / 2 };
        }"""
    )
    page.mouse.move(entry["x"], entry["y"])
    expect(kickoff).to_have_class(MARKED_ROW)
    expect(lunch).not_to_have_class(MARKED_ROW)

    page.mouse.move(2, 2)
    expect(rows.and_(page.locator(".lf-mark-hover"))).to_have_count(0)
    page.wait_for_function(f"() => !({HOVER_LIT})().length")
    assert page.evaluate(boxes) == before
    assert page.evaluate("() => document.activeElement === window.focusBefore")


def test_threads_search_finds_a_thread_by_the_words_it_quotes(browser, serve):
    """Searching Threads finds a thread by the words it is about as well as by its
    name and messages: words only the passage holds find the thread on it."""
    url = serve(AGENDA_PAGE)
    agenda_threads(serve.page_dir)
    page = floating(browser, url)
    rows = threads_rows(page)
    expect(rows).to_have_count(3)
    page.get_by_role("button", name="Find a thread or message").click()
    page.locator("input.lf-fp-search").fill("schedule leaves")
    expect(rows.locator(".lf-fp-label")).to_have_text(["Is lunch provided?"])


def test_keys_in_threads_act_on_threads(browser, serve):
    """In Threads, `/` opens Threads' own search, where it opened the page's search
    over the list, and d and u page the list rather than the page under it."""
    url = serve(AGENDA_PAGE)
    agenda_threads(serve.page_dir)
    for n in range(12):
        panel_comment(serve.page_dir, f"Question {n} about the room")
    page = floating(browser, url)
    resized(page, 1440, 500)
    rows = threads_rows(page)
    view = page.locator(".lf-fp-view[data-view=threads]")
    expect(view).to_be_focused()
    assert view.evaluate("box => box.scrollHeight > box.clientHeight")
    document = "() => document.scrollingElement.scrollTop"
    before = page.evaluate(document)
    page.keyboard.press("d")
    page.wait_for_function("box => box.scrollTop > 0", arg=view.element_handle())
    page.keyboard.press("u")
    page.wait_for_function("box => box.scrollTop === 0", arg=view.element_handle())
    assert page.evaluate(document) == before

    page.keyboard.press("/")
    expect(page.locator("input.lf-fp-search")).to_be_focused()
    expect(page.locator(".lf-page-search")).to_be_hidden()
    page.keyboard.type("schedule leaves")
    expect(rows.locator(".lf-fp-label")).to_have_text(["Is lunch provided?"])


def test_escape_from_threads_search_returns_to_threads(browser, serve):
    """Escape in Threads' search clears its words, then, with the box empty, closes the
    search and leaves the user in Threads, as a find box returns to its panel, where it
    put Threads away; the next Escape closes Threads."""
    url = serve(AGENDA_PAGE)
    agenda_threads(serve.page_dir)
    page = floating(browser, url)
    rows = threads_rows(page)
    view = page.locator(".lf-fp-view[data-view=threads]")
    search = page.locator("input.lf-fp-search")
    page.get_by_role("button", name="Find a thread or message").click()
    search.fill("schedule leaves")
    expect(rows).to_have_count(1)
    page.keyboard.press("Escape")
    expect(search).to_have_value("")
    expect(rows).to_have_count(3)
    page.keyboard.press("Escape")
    expect(search).to_have_count(0)
    expect(view).to_be_focused()
    page.keyboard.press("Escape")
    expect(view).to_have_count(0)


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


GROWTH = """() => {
  const view = document.querySelector('.lf-fp-view[data-view=thread]');
  const box = (node) => node.getBoundingClientRect();
  const msgs = [...view.querySelectorAll('.lf-msg')];
  const turn = msgs.findLast((msg) => msg.querySelector('.lf-msg-head')?.textContent.includes('Me'));
  const foot = view.querySelector('.lf-fp-foot');
  return {
    view: box(view).top,
    height: box(view).height,
    cap: parseFloat(getComputedStyle(view.parentElement).maxHeight),
    bottom: box(view).bottom,
    field: box(document.querySelector('.lf-fp-field')).top,
    turn: turn && [box(turn).top - box(view).top - parseFloat(getComputedStyle(view).paddingTop),
                   foot ? box(foot).top - box(turn).bottom : box(view).bottom - box(turn).bottom],
    foot: foot && box(foot).bottom,
  };
}"""


def risen(before, after, by):
    """Whether every seat of the head (`HEAD_SEATS`) stands where it stood, moved `by`
    down the window: the head rising with a view that grows at its top."""

    def lifted(seat):
        return [seat[0], seat[1] + by, seat[2], seat[3] + by]

    return all(
        (seat is None) == (after[name] is None)
        and (
            seat is None
            or (
                abs(after[name] - seat) < 0.5
                if isinstance(seat, float | int)
                else all(abs(a - b) < 0.5 for a, b in zip(after[name], lifted(seat)))
            )
        )
        for name, seat in before.items()
    )


def test_an_answer_the_user_waits_for_grows_the_view_up_to_its_cap(browser, serve):
    """The agent's answer to the user's own last turn grows the thread's view to hold
    it: the field stays where it is, and the head rises with the view's top, carrying
    each control by the same distance. Past the view's cap the answer goes on below the
    fold behind New reply, with the user's own turn wholly in sight above it, its head
    included, and nothing of the answer showing below the press; a press brings the
    answer's start into sight. A reply that follows the agent's own turn below that
    fold moves nothing the user sees, so it joins there at once, as on a card; one that
    would move what is in sight is held behind the thread's notice
    (`test_held_news_reads_whole_on_the_thread_s_head_line`)."""
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
    stood = page.evaluate(GROWTH)

    answer("Internal first. " + "The second wave waits for the alarms to hold. " * 3)
    expect(messages).to_have_count(2)
    settled(page)
    grown = page.evaluate(GROWTH)
    by = grown["view"] - stood["view"]
    assert by < -40, (stood, grown)
    assert grown["field"] == stood["field"]
    assert grown["bottom"] == stood["bottom"]
    assert risen(seats, page.evaluate(HEAD_SEATS), by), (seats, by)
    assert grown["turn"][0] >= 0 and grown["turn"][1] >= 0, grown
    expect(view.locator(".lf-fp-new-reply")).to_have_count(0)
    expect(page.locator(".lf-fp-head .lf-thread-news:visible")).to_have_count(0)

    write(field(page), "And the weekend?")
    with sending(page, "the reply"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect(messages).to_have_count(3)
    settled(page)

    answer("It would. " + "Someone stays on call through Sunday, and Monday too. " * 80)
    press = view.locator(".lf-fp-new-reply")
    expect(press).to_have_text("New reply")
    expect(messages).to_have_count(4)
    settled(page)
    capped = page.evaluate(GROWTH)
    assert abs(capped["height"] - capped["cap"]) < 1, capped
    assert capped["field"] == stood["field"]
    # The user's turn stands wholly between the view's head and New reply's ground,
    # which reaches the view's foot, so nothing scrolls by under the press.
    assert capped["turn"][0] >= 0 and capped["turn"][1] >= 0, capped
    assert abs(capped["foot"] - capped["bottom"]) < 0.5, capped

    press.click()
    expect(press).to_have_count(0)
    settled(page)
    shown, box = messages.last.bounding_box(), view.bounding_box()
    assert box["y"] <= shown["y"] < box["y"] + box["height"] - 40, (shown, box)

    seats = page.evaluate(HEAD_SEATS)
    read = page.evaluate(GROWTH)
    answer("One more thing: the alarms page the on-call too.")
    expect(messages).to_have_count(5)
    settled(page)
    expect(page.locator(".lf-fp-head .lf-thread-news:visible")).to_have_count(0)
    assert page.evaluate(HEAD_SEATS) == seats
    assert page.evaluate(GROWTH)["turn"] == read["turn"]


def test_new_reply_leads_to_the_reply_once_one_follows_the_work(browser, serve):
    """Work under way past the view's cap waits behind New message; the reply
    that follows it takes the press over, which then says New reply and brings the
    reply's start into sight, not the work before it."""
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
    say("Reading the jobs, the mounts and the frost dates. " * 80, ephemeral=True)
    expect(press).to_have_text("New message")
    say("The mounts come first. " + "They need the frost to lift. " * 120)
    expect(press).to_have_text("New reply")
    press.click()
    expect(press).to_have_count(0)
    settled(page)
    reply = view.locator(".lf-msg", has_text="The mounts come first.")
    shown, box = reply.bounding_box(), view.bounding_box()
    assert box["y"] <= shown["y"] < box["y"] + box["height"] - 40, (shown, box)


def test_a_streaming_answer_grows_the_view_until_it_outgrows_its_cap(
    browser, serve, request
):
    """An answer the user waits for that streams in grows the view at each step, the
    head rising with it and the field staying put, with the answer's end in sight; a
    step past the view's cap, such as the durable answer completing it with longer
    words, leaves New reply at the view's foot."""
    # The threads suite imports this one, so its stream helpers come in at run time.
    from browser.threads import claim_for_codex, stream_reply

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
    stood = page.evaluate(GROWTH)

    def streamed(text):
        stream_reply(serve.page_dir, root, text)
        told(page)
        expect(messages.last.locator(".lf-msg-text")).to_have_text(text)
        settled(page)
        grown = page.evaluate(GROWTH)
        assert (grown["field"], grown["bottom"]) == (stood["field"], stood["bottom"])
        assert risen(seats, page.evaluate(HEAD_SEATS), grown["view"] - stood["view"])
        shown, box = messages.last.bounding_box(), view.bounding_box()
        assert shown["y"] + shown["height"] <= box["y"] + box["height"] + 0.5
        return grown

    assert streamed("I'll")["view"] < stood["view"]
    streamed("I'll record it on the board now. " + "Then the totals. " * 12)
    expect(view.locator(".lf-fp-new-reply")).to_have_count(0)

    # The durable answer completes the streamed message with longer words.
    thread_model.post_reply(
        serve.page_dir,
        {"to": root, "for": root},
        "Recorded the release on the board. " + "Then I checked the totals. " * 200,
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
    capped = page.evaluate(GROWTH)
    assert abs(capped["height"] - capped["cap"]) < 1, capped
    assert capped["field"] == stood["field"]


def agent_said(page_dir, root, text, **fields):
    """One agent reply in `root`'s thread, written straight to the log."""
    return append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": root,
            "revision": 1,
            "text": text,
            **fields,
        },
    )["id"]


def test_a_thread_s_view_folds_progress_as_its_card_does(browser, serve):
    """A thread's view draws its messages as the thread's card on the page does
    (thread/transcript.js): the progress the answer completed stands folded behind Show 2
    progress messages at the answer's head, and work still under way stands as one dim
    working message at the transcript's foot rather than as a reply."""
    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir, "Can you check that the workshop fits the afternoon?"
    )
    for step in ("the total practice time", "the break and closing discussion"):
        agent_said(serve.page_dir, root, f"Checking {step}.", ephemeral=True)
    agent_said(
        serve.page_dir,
        root,
        "The workshop fits, including a fifteen-minute break.",
        responds=root,
    )
    agent_said(
        serve.page_dir,
        root,
        "Checking whether the room stays free after five.",
        ephemeral=True,
    )
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(".lf-fp-view[data-view=thread]")
    shown = view.locator(".lf-msg:visible")
    expect(shown).to_have_count(2)
    expect(shown.last).to_contain_text("The workshop fits")
    toggle = shown.last.locator(".lf-progress-expand")
    expect(toggle).to_have_text("Show 2 progress messages")
    working = view.locator(".lf-thread-working")
    expect(working).to_be_visible()
    expect(working).to_contain_text("Checking whether the room stays free after five")

    toggle.click()
    expect(shown).to_have_count(4)
    expect(toggle).to_have_text("Hide 2 progress messages")


def test_a_thread_s_view_marks_unread_replies_and_goes_to_the_next(browser, serve):
    """A reply the user has not read wears the unread rail in the thread's view, as on
    its card, and Next unread at the view's head goes to the thread's first one, above
    the end the view opens at, past the long reply after it. Shown whole there, it
    counts as read, as on a card, and so does the long reply, whose whole extent the
    view has now shown, so Next unread is no longer offered, though its seat stays."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Which job comes first?")
    agent_said(serve.page_dir, root, "The mounts come first.", responds=root)
    agent_said(
        serve.page_dir, root, "Then the beds. " + "The frost dates hold them. " * 150
    )
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(".lf-fp-view[data-view=thread]")
    reply = view.locator(".lf-msg", has_text="The mounts come first.")
    unread = re.compile(r"(^|\s)lf-unread(\s|$)")
    expect(reply).to_have_class(unread)
    assert reply.evaluate("(node) => getComputedStyle(node).borderImageSource") != (
        "none"
    )
    expect(reply).not_to_be_in_viewport()
    press = page.locator(".lf-fp-head .lf-fp-next-unread")
    expect(press).to_have_text("Next unread")

    with sending(page, "the reply read"):
        press.click()
    expect(reply).to_be_focused()
    expect(reply).to_be_in_viewport()
    expect(reply).not_to_have_class(unread)
    expect(view.locator(".lf-msg", has_text="Then the beds.")).not_to_have_class(unread)
    expect(press).to_be_hidden()
    expect(press).to_be_disabled()


# Where a press and the view's head stand once the frame after it has drawn, so the
# view's own reading of what the press grew has run.
PRESS_AND_HEAD = """(toggle) => new Promise((done) =>
  requestAnimationFrame(() => requestAnimationFrame(() => done({
    toggle: document.querySelector(toggle).getBoundingClientRect().top,
    head: document.querySelector('.lf-fp-head').getBoundingClientRect().top,
    page: scrollY,
  })))
)"""


def test_a_fold_pressed_in_a_thread_s_view_stays_under_the_press(browser, serve):
    """A press keeps what it pressed under the pointer. Show 2 progress messages opens
    above itself, so the view grows up the window to show both messages, the press
    standing where it was. Show 2 earlier messages opens below itself, where the view
    growing would carry the press and the head up, so the view holds its height and
    what opened goes on inside it, the press and the head standing where they were."""
    from browser.threads import summarize_thread

    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir, "Can you check that the workshop fits the afternoon?"
    )
    for step in ("the total practice time", "the break and closing discussion"):
        agent_said(serve.page_dir, root, f"Checking {step}. " * 3, ephemeral=True)
    agent_said(
        serve.page_dir,
        root,
        "The workshop fits, including a fifteen-minute break.",
        responds=root,
    )
    asked = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": root,
            "revision": 1,
            "text": "And the room after five?",
        },
    )["id"]
    said = agent_said(
        serve.page_dir, root, "The room stays free until seven. " * 4, responds=asked
    )
    summarize_thread(serve.page_dir, asked, said, "The room is free until seven.")
    agent_said(serve.page_dir, root, "Booked it for the afternoon.")
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(".lf-fp-view[data-view=thread]")
    expect(view.locator(".lf-progress-expand")).to_be_visible()
    settled(page)
    toggle = ".lf-fp-view .lf-progress-expand"
    stood = page.evaluate(PRESS_AND_HEAD, toggle)
    page.locator(toggle).click()
    expect(page.locator(toggle)).to_have_attribute("aria-expanded", "true")
    settled(page)
    after = page.evaluate(PRESS_AND_HEAD, toggle)
    assert after["toggle"] == stood["toggle"], (stood, after)
    for step in view.locator(".lf-msg", has_text="Checking").all():
        expect(step).to_be_in_viewport(ratio=1)

    toggle = ".lf-fp-view .lf-summary-checkpoint .lf-summary-expand"
    stood = page.evaluate(PRESS_AND_HEAD, toggle)
    page.locator(toggle).click()
    expect(page.locator(toggle)).to_have_attribute("aria-expanded", "true")
    settled(page)
    assert page.evaluate(PRESS_AND_HEAD, toggle) == stood
    expect(view.locator(".lf-msg:visible")).to_have_count(7)


def test_an_answer_the_user_waits_for_grows_the_view_after_a_press_on_its_words(
    browser, serve
):
    """A press that grows nothing holds nothing: the user clicking a message's words
    while waiting for the agent's answer still sees the answer grow the view, as it
    would without the click."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Which job comes first?")
    agent_said(serve.page_dir, root, "The mounts come first.", responds=root)
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(".lf-fp-view[data-view=thread]")
    messages = view.locator(".lf-msg")
    expect(messages).to_have_count(2)
    write(field(page), "And then?")
    with sending(page, "the reply"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect(messages).to_have_count(3)
    settled(page)
    messages.first.locator(".lf-msg-text").click()
    page.wait_for_timeout(200)
    settled(page)
    stood = view.bounding_box()["height"]
    agent_said(
        serve.page_dir, root, "Then the beds. " + "The frost dates hold them. " * 4
    )
    told(page)
    expect(messages).to_have_count(4)
    settled(page)
    assert view.bounding_box()["height"] > stood + 40, stood


def long_progress_thread(page_dir, after=None):
    """A thread whose answer folds two long progress steps, with `after` below it."""
    root = panel_comment(page_dir, "Can you check that the workshop fits?")
    for step in ("the total practice time", "the break and closing discussion"):
        agent_said(
            page_dir,
            root,
            f"Checking {step} against the booking. " * 22,
            ephemeral=True,
        )
    agent_said(page_dir, root, "The workshop fits.", responds=root)
    if after:
        agent_said(page_dir, root, after)
    return root


PROGRESS_TOGGLE = ".lf-fp-view .lf-progress-expand"


def test_progress_taller_than_the_view_can_grow_opens_under_the_press(browser, serve):
    """Progress opens above the answer whose head holds its disclosure. Where it is
    taller than the room the view can still grow into, the view grows to its cap and
    scrolls by the rest, so Show 2 progress messages stays under the pointer."""
    url = serve(LONG_PAGE)
    long_progress_thread(serve.page_dir)
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    expect(page.locator(PROGRESS_TOGGLE)).to_be_visible()
    settled(page)
    stood = page.evaluate(PRESS_AND_HEAD, PROGRESS_TOGGLE)
    page.locator(PROGRESS_TOGGLE).click()
    expect(page.locator(PROGRESS_TOGGLE)).to_have_attribute("aria-expanded", "true")
    settled(page)
    after = page.evaluate(PRESS_AND_HEAD, PROGRESS_TOGGLE)
    assert after["toggle"] == pytest.approx(stood["toggle"], abs=0.5), (stood, after)
    assert after["page"] == stood["page"], (stood, after)
    expect(page.locator(PROGRESS_TOGGLE)).to_be_in_viewport(ratio=1)


def test_progress_opening_in_a_capped_view_at_its_top_stays_under_the_press(
    browser, serve
):
    """A view at its cap, scrolled to its top, cannot grow, and scroll anchoring holds
    nothing there: the progress opening above the press scrolls the view by all of
    it, so the press stays where it stood."""
    url = serve(LONG_PAGE)
    long_progress_thread(
        serve.page_dir, after="The room notes. " + "The projector is booked. " * 90
    )
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(".lf-fp-view[data-view=thread]")
    expect(page.locator(PROGRESS_TOGGLE)).to_be_attached()
    settled(page)
    view.evaluate("view => view.scrollTop = 0")
    expect(page.locator(PROGRESS_TOGGLE)).to_be_in_viewport(ratio=1)
    stood = page.evaluate(PRESS_AND_HEAD, PROGRESS_TOGGLE)
    page.locator(PROGRESS_TOGGLE).click()
    expect(page.locator(PROGRESS_TOGGLE)).to_have_attribute("aria-expanded", "true")
    settled(page)
    assert page.evaluate(PRESS_AND_HEAD, PROGRESS_TOGGLE) == pytest.approx(
        stood, abs=0.5
    )


def test_closing_a_fold_keeps_its_press_and_the_head_in_place(browser, serve):
    """Closing a fold shrinks what the view holds below its press. After the user's turn
    has let go of the height opening it held, the view holds its height again for the
    close, so Collapse and the head stay where they were rather than dropping as the
    view shrinks from its head."""
    from browser.threads import summarize_thread

    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Which jobs come first?")
    first = agent_said(
        serve.page_dir, root, "The mounts come first. " * 6, responds=root
    )
    then = agent_said(serve.page_dir, root, "Then the beds, once the frost lifts. " * 6)
    summarize_thread(serve.page_dir, first, then, "Mounts, then beds.")
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(".lf-fp-view[data-view=thread]")
    toggle = ".lf-fp-view .lf-summary-checkpoint .lf-summary-expand"
    page.locator(toggle).click()
    expect(page.locator(toggle)).to_have_attribute("aria-expanded", "true")
    write(field(page), "And the paths?")
    with sending(page, "the reply"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect(view.locator(".lf-msg", has_text="And the paths?")).to_be_visible()
    settled(page)
    view.evaluate("view => view.scrollTop = 0")
    stood = page.evaluate(PRESS_AND_HEAD, toggle)
    page.locator(toggle).click()
    expect(page.locator(toggle)).to_have_attribute("aria-expanded", "false")
    settled(page)
    assert page.evaluate(PRESS_AND_HEAD, toggle) == pytest.approx(stood, abs=0.5)


def test_next_unread_into_a_closed_summary_stays_under_the_press(browser, serve):
    """Next unread reaching a reply a closed summary holds opens the summary in the
    view, which holds its height so the press and the head stay where they were, and
    lands on the reply inside it."""
    from browser.threads import summarize_thread

    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Which jobs come first?")
    first = agent_said(serve.page_dir, root, "The mounts come first.", responds=root)
    then = agent_said(serve.page_dir, root, "Then the beds, once the frost lifts.")
    summarize_thread(serve.page_dir, first, then, "Mounts, then beds.")
    agent_said(serve.page_dir, root, "That is the order.")
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    press = page.locator(".lf-fp-head .lf-fp-next-unread")
    expect(press).to_be_visible()
    settled(page)
    stood = page.evaluate(PRESS_AND_HEAD, ".lf-fp-head .lf-fp-next-unread")
    press.click()
    reply = page.locator(".lf-fp-view .lf-msg", has_text="The mounts come first.")
    expect(reply).to_be_focused()
    settled(page)
    assert page.evaluate(PRESS_AND_HEAD, ".lf-fp-head .lf-fp-next-unread") == stood


def test_next_unread_never_shows_for_a_reply_the_opening_reads(browser, serve):
    """Opening a thread whose one unread reply is short reads it as the view lands, so
    Next unread never shows at the view's head, not even for the moment before the
    reply is read."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Which job comes first?")
    agent_said(serve.page_dir, root, "The mounts come first.", responds=root)
    page = floating(browser, url)
    page.evaluate("""() => {
      window.nextUnreadShown = false;
      new MutationObserver(() => {
        window.nextUnreadShown ||= Boolean(
          document.querySelector('.lf-fp-next-unread:not([data-unoffered])'));
      }).observe(document, {subtree: true, childList: true, attributes: true});
    }""")
    reply = page.locator(".lf-fp-view .lf-msg", has_text="The mounts come first.")
    with sending(page, "the reply read"):
        page.locator("body").focus()
        page.keyboard.press("t")
        expect(reply).to_be_visible()
    expect(reply).not_to_have_class(re.compile(r"(^|\s)lf-unread(\s|$)"))
    round_trip(page)
    assert not page.evaluate("() => window.nextUnreadShown")
    expect(page.locator(".lf-fp-next-unread")).to_have_count(0)


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


def test_a_package_s_transcript_takes_its_notice_where_every_part_does(browser, serve):
    """A package that draws a thread's head itself may name its transcript alone
    (`parts.transcript`, as the panel's view does) without naming where the thread's
    notice goes: Leaf draws the transcript, and news that would move it waits behind
    the notice at the head of its first message, where every part takes it by
    default."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Is the window long enough?")
    page = floating(browser, url)
    page.evaluate(
        """async () => {
          const api = await window.__lfWidgetApi();
          const host = document.createElement('div');
          host.id = 'reader';
          // Over the page, so drawing it moves none of the page's words.
          host.style = 'position: fixed; inset: 0 0 auto auto; width: 320px';
          document.querySelector('main').append(host);
          window.reader = api.registerThreadPresentation(host, {
            render: (collection, parts) => {
              for (const thread of collection.threads) {
                const outlet = document.createElement('div');
                host.replaceChildren(outlet);
                parts.transcript(thread.key, outlet);
              }
            },
            reveal: () => {},
          });
          await window.reader.update();
        }"""
    )
    reader = page.locator("#reader")
    expect(reader.locator(".lf-msg")).to_contain_text("Is the window long enough?")
    agent_said(serve.page_dir, root, "Forty-eight hours covers the first cohort.")
    told(page)
    expect(reader.locator(".lf-msg-head .lf-thread-news")).to_have_text("1 new reply")
    expect(reader.locator(".lf-msg")).to_have_count(1)
    assert page.evaluate("() => window.reader.primary")


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
          box.style.cssText = 'position: fixed; top: 8px; left: 8px';
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


@pytest.mark.parametrize("hidden_by", ["draft", "fold"])
def test_floating_status_records_feedback_only_when_its_words_show(
    browser, serve, request, hidden_by
):
    """Authored status words retain their exact source through the native placeholder
    slot and folded peek. A draft, focus, or folded panel cannot claim them visible.
    """
    from browser.threads import claim_for_codex

    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Can we simplify the logging?")
    claim_for_codex(serve.page_dir, request)
    page = floating(browser, url)
    if hidden_by == "draft":
        write(field(page), "Keep my unfinished question")
    else:
        page.locator(".lf-fp-leaf").click()
        page.locator(".lf-fp-item", has_text="Fold to the leaf").click()
        page.mouse.move(5, 5)
    progress = thread_model.post_reply(
        serve.page_dir,
        {"to": root, "for": root},
        "Reading the diagnostic transport.",
        ephemeral=True,
        identity={"agent": "Codex", "session": "codex-thread"},
    )
    told(page)

    def batch_has(response, kind):
        return (
            response.url.endswith("/api/interaction")
            and response.ok
            and any(
                entry["type"] == kind
                for entry in response.request.post_data_json["entries"]
            )
        )

    def visible():
        return [
            row
            for row in interaction_model.read_interactions(serve.page_dir)
            if row["type"] == "reply_visible" and row.get("reply_id") == progress["id"]
        ]

    # A later acknowledged gesture flushes all observations of the hidden words.
    with page.expect_response(lambda response: batch_has(response, "click")):
        page.locator("h1").first.click()
    assert visible() == []
    if hidden_by == "draft":
        field(page).click()
        page.keyboard.press("ControlOrMeta+a")
        with page.expect_response(lambda response: batch_has(response, "keydown")):
            page.keyboard.press("Backspace")
        expect(field(page)).to_have_attribute("placeholder", re.compile("^Comment"))
        expect(field(page).locator(".lf-key-badge")).to_contain_text("⏎")
        assert visible() == []
    with page.expect_response(lambda response: batch_has(response, "reply_visible")):
        if hidden_by == "draft":
            page.locator("h1").first.click()
        else:
            page.locator(".lf-fp-leaf").hover()
            expect(page.locator(".lf-fp-peek")).to_contain_text(
                "Reading the diagnostic transport"
            )
    rows = visible()
    assert len(rows) == 1
    assert rows[0]["input_id"] == root
    assert rows[0]["presentation_kind"] == "status_words"
    assert rows[0]["surface"] == "panel"
    assert "text" not in rows[0]


def test_a_folded_status_keeps_its_reading_until_the_next_exposure(
    browser, serve, request
):
    """A clock tick cannot move tooltip words; the leaf stays live and reopening
    reads current status. A notice answering a gesture still shows immediately."""
    from browser.threads import claim_for_codex

    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Can we simplify the logging?")
    claim_for_codex(serve.page_dir, request)
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press(".")
    progress = thread_model.post_reply(
        serve.page_dir,
        {"to": root, "for": root},
        "Reading the diagnostic transport.",
        ephemeral=True,
        identity={"agent": "Codex", "session": "codex-thread"},
    )
    told(page)
    peek = page.locator(".lf-fp-peek")
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
    expect(leaf).to_have_attribute("aria-label", re.compile("1m ago"))
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
        {"to": root, "for": root},
        "Tracing the reply acknowledgements.",
        ephemeral=True,
        identity={"agent": "Codex", "session": "codex-thread"},
    )
    with page.expect_request("**/api/news"):
        page.evaluate("""() => {
          window.__lfTestVisibility = 'visible';
          document.dispatchEvent(new Event('visibilitychange'));
        }""")
    told(page)
    expect(peek).to_contain_text("Tracing the reply acknowledgements.")
    ticked(page)
    words = peek.inner_text()
    now += timedelta(minutes=1)
    page.clock.set_fixed_time(now)
    expect(leaf).to_have_attribute("aria-label", re.compile("2m ago"))
    assert peek.inner_text() == words
    page.evaluate(
        "async () => (await window.__lfWidgetApi()).notice('Saved for later')"
    )
    expect(peek).to_have_text("Saved for later")


def test_pointing_at_the_row_s_leaf_or_field_says_the_status_in_full(browser, serve):
    """In the row, pointing at the leaf or at the empty field shows the leaf's peek, the
    box the folded leaf shows, at once and over the row, with the status the field cuts
    short in full; the field keeps no browser tooltip of its own. The peek stands down
    while the leaf's menu, which says the status itself, stands, and over a field the
    user writes in or whose words hide the status."""
    page = floating(browser, serve(LONG_PAGE))
    peek = page.locator(".lf-fp-peek")
    leaf = page.locator(".lf-fp-leaf")
    seat = page.locator(".lf-fp-field")
    shown = "peek => peek.hasAttribute('data-shown')"
    expect(field(page)).to_have_attribute("placeholder", re.compile(r" away\b"))
    assert seat.get_attribute("title") is None
    row = page.locator(".lf-fp-row").bounding_box()
    for asker in (leaf, seat):
        page.mouse.move(5, 5)
        expect(peek).to_be_hidden()
        asker.hover()
        assert peek.evaluate(shown)
        expect(peek).to_have_text(re.compile(r"isn't watching right now\."))
        box = peek.bounding_box()
        assert box["y"] + box["height"] <= row["y"], (box, row)

    leaf.click()
    expect(page.locator(".lf-fp-menu")).to_be_visible()
    expect(peek).to_be_hidden()
    field(page).click()
    expect(page.locator(".lf-fp-menu")).to_be_hidden()
    expect(peek).to_be_hidden()
    write(field(page), "Could the rollback cover the weekend?")
    page.mouse.click(5, 5)
    seat.hover()
    expect(peek).to_be_hidden()


def test_the_peek_says_what_its_asker_says_now(browser, serve):
    """The leaf's peek keeps the status it opened with through one exposure, but a
    different thing to say is said at once: the leaf holding keyboard focus shows the
    status, and the pointer then on a field saying an error shows the error, and a newer
    error under the still pointer replaces it."""
    page = floating(browser, serve(LONG_PAGE))
    peek = page.locator(".lf-fp-peek")
    say = "async (text) => (await window.__lfWidgetApi()).raiseError(text)"
    page.evaluate(say, "Couldn't save the draft")
    expect(field(page)).to_have_attribute("data-says", "error")
    leaf = page.locator(".lf-fp-leaf")
    leaf.focus()
    expect(leaf).to_be_focused()
    expect(peek).to_have_text(re.compile(r"isn't watching right now\."))
    page.locator(".lf-fp-field").hover()
    expect(peek).to_have_text("Couldn't save the draft")
    page.evaluate(say, "Couldn't load v1")
    expect(peek).to_have_text("Couldn't load v1")


def test_floating_menu_tracks_stalled_detail_hidden_by_a_draft(browser, serve, request):
    """The stalled summary carries no authored detail; its menu's Last said words do.
    A draft keeps the row's placeholder hidden, so that menu is their first exposure.
    """
    from browser.threads import claim_for_codex

    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Can we simplify the logging?")
    claim_for_codex(serve.page_dir, request)
    page = floating(browser, url)
    write(field(page), "Keep my unfinished question")
    progress = declare_work(
        serve.page_dir,
        "Reading the diagnostic transport.",
        item=root,
        ts="2020-01-01T00:00:00+00:00",
        agent="Codex",
        session="codex-thread",
    )
    told(page)

    def traced(response, kind):
        return (
            response.url.endswith("/api/interaction")
            and response.ok
            and any(
                entry["type"] == kind
                for entry in response.request.post_data_json["entries"]
            )
        )

    def feedback():
        return [
            row
            for row in interaction_model.read_interactions(serve.page_dir)
            if row["type"] == "reply_visible" and row.get("reply_id") == progress["id"]
        ]

    with page.expect_response(lambda response: traced(response, "click")):
        page.locator("h1").first.click()
    assert feedback() == []
    with page.expect_response(lambda response: traced(response, "reply_visible")):
        page.locator(".lf-fp-leaf").click()
        expect(page.locator(".lf-fp-explain")).to_contain_text(
            "Last said: Reading the diagnostic transport"
        )
    rows = feedback()
    assert len(rows) == 1
    assert rows[0]["input_id"] == root
    assert rows[0]["presentation_kind"] == "status_words"
    assert rows[0]["surface"] == "panel"
    assert "text" not in rows[0]


def test_the_empty_field_says_the_agent_s_status_until_the_caret_is_in(browser, serve):
    """At rest the empty field says what the agent is doing, in the status's words and
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
    page = open_page(browser, url, init_script=EDITOR_ROOTS)
    status = re.compile(rf"^{agent} working\b.* — Drafting the rollout")
    expect(field(page)).to_have_attribute("placeholder", status)
    # The sheen runs on the field's placeholder part, inside the field's closed tree,
    # where no animation list reaches: a moving mask dims the words, and the field reads
    # differently from one moment to the next.
    words = page.locator(".lf-fp-field .lf-compose-placeholder > span")
    ink = """node => getComputedStyle(node).color"""

    def sheen(running):
        page.wait_for_function(
            """running => {
              const host = document.querySelector('.lf-fp-field leaf-text');
              const part = window.editorRoots.get(host)
                .querySelector('[part~="placeholder"]');
              return (getComputedStyle(part).maskImage !== 'none') === running;
            }""",
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
    assert alpha < 0.7, f"the resting status reads at {alpha:.0%} of ink"
    page.emulate_media(reduced_motion="no-preference")
    sheen(True)
    # Forced colours drop the mask but keep the animation, so the words stay whole.
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
    expect(line).to_be_hidden()
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


def test_a_refused_key_is_an_error_the_field_says(browser, serve):
    """A status that only reports reads in the dim face, with the status in full in the
    leaf's peek on pointing at the field. Once the server refuses this tab's key, which
    asks the user to act, that stands as an error: the field says it in the danger's
    ink, and the peek over the still pointer says it in full in the status's place. The
    caret going in leaves it in the field until the user writes."""
    url = serve(LONG_PAGE)
    working(serve.page_dir, "Drafting the rollout")
    page = floating(browser, url)
    words = page.locator(".lf-fp-field .lf-compose-placeholder > span")
    peek = page.locator(".lf-fp-peek")

    def alpha():
        color = words.evaluate("node => getComputedStyle(node).color")
        found = re.search(r"/\s*([\d.]+)\)$", color)
        return float(found.group(1)) if found else 1.0

    expect(field(page)).to_have_attribute("placeholder", re.compile("^Claude working"))
    page.locator(".lf-fp-field").hover()
    expect(peek).to_have_text(re.compile("^Claude is working — Drafting the rollout"))

    page.route("**/api/state*", lambda route: route.fulfill(status=401, body="{}"))
    declare_idle(serve.page_dir)
    expect(field(page)).to_have_attribute("data-says", "error")
    expect(field(page)).to_have_attribute("placeholder", re.compile("^Key refused"))
    assert alpha() > 0.6, "the refused key reads as dim as a report"
    expect(peek).to_have_text(re.compile("^Key refused — open Leaf's link"))
    field(page).click()
    expect(field(page)).to_have_attribute("data-says", "error")
    expect(peek).to_be_hidden()
    # The refused reads recur on the page's clock until it closes.
    page.close()
    consume_browser_errors(page, http_error_console(401))


def test_nothing_passing_interrupts_the_user_writing(browser, serve):
    """A passing notice is said in the empty field's place, and on the line above the
    field once words hide that with the caret elsewhere. While the caret is in the
    field, whose placeholder then says where the words go, nothing passing is said:
    news goes unsaid but for the live region, there and over an open view, where the
    leaf's peek stays down. On a folded panel the peek says any notice."""
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Is the window long enough?")
    page = floating(browser, url)
    say = "async (text) => (await window.__lfWidgetApi()).notice(text)"
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
    expect(line).to_be_hidden()
    write(field(page), "Could the rollback cover the weekend?")
    page.evaluate(say, "Saved for later")
    expect(line).to_be_hidden()
    page.mouse.click(5, 5)
    expect(line).to_have_text("Saved for later")

    page.locator("body").focus()
    page.keyboard.press("t")
    expect(page.locator(".lf-fp-view[data-view=thread]")).to_be_visible()
    write(field(page), "And the weekend?")
    page.evaluate(say, "2 agent messages in 2 threads")
    expect(peek).to_be_hidden()
    expect(line).to_be_hidden()
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")

    # Folded to the leaf, the panel has no field, and the leaf's peek says it.
    page.locator("body").focus()
    page.keyboard.press(".")
    expect(page.locator(".lf-floating-panel")).to_have_attribute("data-rest", "mark")
    page.evaluate(say, "Reconnected")
    expect(peek).to_be_visible()
    expect(peek).to_have_text("Reconnected")


def test_an_error_stands_in_the_field_until_edited_then_waits_in_the_menu(
    browser, serve
):
    """An error the page raises stands in the field's status place while the field can
    say it: about its editor, or about nothing while the editor is empty. The user's
    first edit passes every error the field says to Errors in the leaf's menu, where a
    dot on the leaf marks them until the list is opened and each can be dismissed. Over
    words its editor holds, an error covers them until the first key there: an edit
    or a caret move lands in those words, and Enter only uncovers them, so nothing
    sends them unseen.
    An error the field cannot say, such as one about nothing while the user has words
    there, goes straight to the list."""
    url = serve(LONG_PAGE)
    page = floating(browser, url)
    raise_error = """async ([text, onField]) => {
      const subject = onField ? document.querySelector('.lf-fp-field leaf-text') : null;
      (await window.__lfWidgetApi()).raiseError(text, { subject });
    }"""
    panel = page.locator(".lf-floating-panel")
    cover = page.locator(".lf-fp-field .lf-compose-error")
    dot = page.locator(".lf-fp-error-dot")
    value = "node => node.value"
    page.evaluate(raise_error, ["Couldn't load v1", False])
    page.evaluate(raise_error, ["That reaction target is no longer available", False])
    expect(field(page)).to_have_attribute("data-says", "error")
    expect(field(page)).to_have_attribute(
        "placeholder", re.compile(r"^That reaction target is no longer available")
    )
    # Clicking in is no edit: the errors stay until the user writes, and the first
    # key passes both of them.
    field(page).click()
    expect(field(page)).to_have_attribute("data-says", "error")
    expect(dot).to_be_hidden()
    page.keyboard.type("Could")
    expect(field(page)).to_have_attribute("data-says", "destination")
    expect(dot).to_be_visible()

    # Over words its editor holds, an error covers them, and Enter only uncovers
    # them, sending nothing, with the caret at their end for the next key.
    page.evaluate(raise_error, ["Could not add image — disk full", True])
    expect(cover).to_have_text("Could not add image — disk full")
    assert field(page).evaluate(value) == "Could"
    sent = len(events_model.read_events(serve.page_dir))
    page.keyboard.press("Enter")
    expect(cover).to_be_hidden()
    assert field(page).evaluate(value) == "Could"
    page.keyboard.type(" it")
    assert field(page).evaluate(value) == "Could it"
    # A caret key uncovers them too, moving the caret as it would.
    page.evaluate(raise_error, ["Could not add image — disk full", True])
    expect(cover).to_be_visible()
    page.keyboard.press("ArrowLeft")
    expect(cover).to_be_hidden()
    assert field(page).evaluate("node => node.selectionStart") == len("Could i")
    assert len(events_model.read_events(serve.page_dir)) == sent
    # One about nothing while the user has words goes straight to the list.
    page.evaluate(raise_error, ["Draw on or beside something on the page.", False])
    expect(cover).to_be_hidden()
    expect(field(page)).to_have_attribute("data-says", "destination")

    page.locator(".lf-fp-leaf").click()
    errors = page.locator('.lf-fp-menu [data-row="errors"]')
    expect(errors).to_contain_text("5")
    errors.click()
    listed = page.locator(".lf-fp-menu .lf-fp-error")
    expect(listed).to_have_count(5)
    expect(listed.first).to_contain_text("Draw on or beside something")
    expect(dot).to_be_hidden()
    listed.first.get_by_role("menuitem").click()
    expect(listed).to_have_count(4)
    expect(listed.first.get_by_role("menuitem")).to_be_focused()
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")

    # Folded, the panel says no error; the leaf's dot marks one raised there.
    page.locator("body").focus()
    page.keyboard.press(".")
    expect(panel).to_have_attribute("data-rest", "mark")
    page.evaluate(raise_error, ["That selected passage is unavailable", False])
    expect(dot).to_be_visible()


def test_question_mark_opens_the_command_reference_at_once(browser, serve):
    """The first `?` opens the command reference."""
    page = floating(browser, serve(LONG_PAGE))
    page.locator("body").focus()
    page.keyboard.press("?")
    expect(page.locator(".lf-command-reference")).to_be_visible()


def test_a_walk_says_its_position_in_the_panel(browser, serve):
    """A walk's position is said where the panel says whatever passes, not against the
    window: in the empty field's place, as a notice is. The room the page shows (geometry.js, `shownWindow`) runs from the window's
    head to the panel's row whether or not a walk is under way. The position lasts
    while the obligation it reached is the block being read, which lasts while the user
    writes a comment, so it goes unsaid once the caret is in the field: on the line
    over the field, and in the leaf's peek, which would lie on the thread's last words
    all that time, once the comment's thread opens over the row."""
    heading = "<h3>How should the schema migrate?</h3>"
    tall = "<p>The old schema has three tables, each a year of records.</p>" * 30
    page = floating(browser, serve(OBLIGATION_PAGE.replace(heading, heading + tall)))
    room = """async () => {
      const shown = (await window.__lfWidgetApi()).shownWindow();
      return {top: shown.top, bottom: shown.bottom};
    }"""
    foot = page.locator(".lf-fp-row").bounding_box()["y"]
    before = page.evaluate(room)
    assert before["bottom"] == pytest.approx(foot, abs=1)

    page.locator("body").focus()
    page.keyboard.press("m")
    expect(field(page)).to_have_attribute("data-says", "notice")
    expect(field(page)).to_have_attribute(
        "placeholder", re.compile("1 of 2 waiting on me")
    )
    assert page.evaluate(room) == before

    # Once the landing's scroll has stopped, the obligation is the block being read.
    page.wait_for_function(
        """() => new Promise((done) => {
          const y = scrollY;
          requestAnimationFrame(() => requestAnimationFrame(() => done(scrollY === y)));
        })"""
    )
    field(page).click()
    expect(page.locator(".lf-fp-context")).to_be_hidden()
    write(field(page), "Is this the one?")
    page.keyboard.press("Enter")
    expect(page.locator(".lf-fp-view[data-view=thread]")).to_be_visible()
    expect(field(page)).to_have_attribute(
        "placeholder", re.compile("^Reply in this thread")
    )
    expect(page.locator(".lf-fp-peek")).to_be_hidden()


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
    page's field, and Go-to's Threads door opens the panel's own Threads. Folded, the
    leaf stands as far from the window's right edge as from its foot."""
    url = serve(LONG_PAGE, comments=1)
    page = floating(browser, url)
    page.locator(".lf-fp-leaf").click()
    page.locator(".lf-fp-item", has_text="Fold to the leaf").click()
    panel = page.locator(".lf-floating-panel")
    expect(panel).to_have_attribute("data-rest", "mark")
    expect(page.locator(".lf-fp-field")).to_be_hidden()
    expect(page.locator(".lf-fp-quick")).to_be_hidden()
    leaf = page.locator(".lf-fp-leaf").bounding_box()
    window = page.viewport_size
    right = window["width"] - (leaf["x"] + leaf["width"])
    foot = window["height"] - (leaf["y"] + leaf["height"])
    assert right == pytest.approx(foot, abs=0.5), (right, foot)

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


def test_a_new_line_past_the_field_s_height_scrolls_into_view(browser, serve):
    """Shift+Enter at the field's height limit scrolls the new, empty line into view,
    as typing a character does, rather than leaving the caret below the field."""
    page = floating(browser, serve(LONG_PAGE))
    box = field(page)
    box.click()
    page.keyboard.type("line")
    for _ in range(20):
        page.keyboard.press("Shift+Enter")
    page.wait_for_function(
        # Within a line of the end: the reveal keeps the field's scroll padding.
        """box => box.scrollHeight > box.clientHeight
            && box.scrollTop + box.clientHeight >= box.scrollHeight - 10""",
        arg=box.element_handle(),
    )


def test_a_pointer_folds_the_panel_from_its_corner(browser, serve):
    """A round button on the box's top-right corner folds the panel, shown only while
    the pointer is near that corner, so the resting row, and the row under a pointer
    passing over the field, is the row alone; it takes no Tab stop, since the menu's
    row and `.` fold from the keyboard."""
    page = floating(browser, serve(LONG_PAGE, comments=1))
    minimize = page.locator(".lf-fp-minimize")
    page.mouse.move(5, 5)
    expect(minimize).to_be_hidden()
    expect(minimize).to_have_attribute("tabindex", "-1")
    card = page.locator(".lf-fp-card").bounding_box()
    page.mouse.move(card["x"] + 40, card["y"] + card["height"] / 2)
    expect(minimize).to_be_hidden()
    page.mouse.move(card["x"] + card["width"] - 20, card["y"] + 6)
    expect(page.get_by_role("button", name="Fold to the leaf")).to_be_visible()
    button = minimize.bounding_box()
    # It rides the corner: its centre sits on the box's top-right edge.
    assert abs(button["x"] + button["width"] / 2 - (card["x"] + card["width"])) <= 2
    assert abs(button["y"] + button["height"] / 2 - card["y"]) <= 2
    # A view opening carries the corner up, away from the still pointer, and the
    # button with it goes; putting the view away brings the corner back to it.
    page.locator("body").focus()
    for keys in ("g", "Shift+t"):
        page.keyboard.press(keys)
    expect(page.locator(".lf-fp-view")).to_have_attribute("data-view", "threads")
    expect(minimize).to_be_hidden()
    for keys in ("g", "Shift+t"):
        page.keyboard.press(keys)
    expect(page.locator(".lf-fp-view")).to_have_count(0)
    expect(minimize).to_be_visible()
    # It presses the fold command, as the menu's row does, so the press is announced
    # and logged like any other.
    page.evaluate(
        """() => document.addEventListener('lf-command-invoked',
            ({detail}) => { window.invoked = detail.id }, {once: true})"""
    )
    minimize.click()
    expect(page.locator(".lf-floating-panel")).to_have_attribute("data-rest", "mark")
    expect(minimize).to_be_hidden()
    assert page.evaluate("window.invoked") == "panel.floating.fold"


def test_obligations_are_answered_where_they_are_read_on_me(browser, serve):
    """On me lists what waits on the user, and each obligation takes its answer there, by the
    widget's own choice: the event is the widget's action. The answered card keeps its
    place and height, so the next obligation does not move under the pointer, and
    Undo takes the answer back."""
    page = floating(browser, serve(OBLIGATION_PAGE))
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


def test_the_plan_has_its_own_tab_and_an_item_says_its_place_in_it(browser, serve):
    """While the agent has a plan, the On view adds a Plan tab beside the two lists,
    drawing the goal with its steps in order, and a step waiting on the user is a way
    to On me. On me keeps every item it lists, and one the plan names says its goal
    and step after its kind, over its question, counted as the goal counts, without
    dropped steps, and still says it once answered."""
    url = serve(OBLIGATION_PAGE)
    steps = [
        {"depth": 0, "title": "Ship the migration", "state": "working"},
        {"depth": 1, "title": "Read the old schema", "state": "done"},
        {"depth": 1, "title": "Ask the DBA", "state": "dropped"},
        {"depth": 1, "item": "widget:schema"},
        {"depth": 1, "title": "Write the note", "state": "open"},
    ]
    written = CliRunner().invoke(
        cli_model.cli, ["task", "plan", str(serve.page_dir)], input=json.dumps(steps)
    )
    assert written.exit_code == 0, written.output
    page = floating(browser, url)
    page.locator(".lf-fp-on-user").click()
    cards = page.locator(".lf-fp-view[data-view=queue] .lf-fp-on-item")
    expect(cards).to_have_count(2)
    expect(cards.first.locator(".lf-fp-on-kind")).to_have_text(
        "Options · Ship the migration · step 2 of 3"
    )
    expect(cards.nth(1).locator(".lf-fp-on-kind")).to_have_text("Options")
    settled(page)
    answers = cards.first.locator(".lf-fp-answers").bounding_box()
    with sending(page, "the answer"):
        cards.first.locator(".lf-fp-answer", has_text="Shim").click()
    expect(cards.first.locator(".lf-fp-said")).to_have_text(re.compile("^Answered"))
    expect(cards.first.locator(".lf-fp-on-kind")).to_have_text(
        "Options · Ship the migration · step 2 of 3"
    )
    assert cards.first.locator(".lf-fp-answers").bounding_box()["y"] == answers["y"]
    with sending(page, "the undo"):
        cards.first.get_by_role("button", name="Undo").click()

    tabs = page.locator(".lf-fp-filters button")
    expect(tabs).to_have_text(["On me 2", "On Claude 0", "Plan"])
    tabs.nth(2).click()
    expect(page.locator(".lf-fp-title")).to_have_text("Plan")
    expect(page.locator(".lf-fp-plan-goal")).to_have_text(
        re.compile(r"Ship the migration\s*1 of 3")
    )
    plan_steps = page.locator(".lf-fp-plan > .lf-fp-plan-steps > .lf-fp-plan-step")
    expect(plan_steps).to_have_count(4)
    expect(plan_steps.nth(0).get_by_role("img")).to_have_accessible_name("Done")
    # The step waiting on the user turns the view to On me, and focus with it.
    plan_steps.nth(2).locator(".lf-fp-plan-tag").click()
    expect(page.locator(".lf-fp-title")).to_have_text("On me")
    expect(tabs.nth(0)).to_be_focused()


def test_versions_travel_and_approval_open_in_the_panel(browser, serve):
    """Version travel turns the leaf's menu to Versions, whatever route asks for the
    versions menu: the menu's row, which names the key as keys, apart from its value,
    and that key, which stands the user on the first version. It lists each version
    with its note, marks the one shown, travels to another, and holds the page's
    approval, which records the sign-off."""
    url = serve(SIGN_OFF)
    stamp_page(
        serve.page_dir, SIGN_OFF.replace("Paragraph 0.", "Paragraph zero."), "two"
    )
    page = floating(browser, url)
    view = page.locator(".lf-fp-menu[data-level=versions]")
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
    expect(view.locator(".lf-fp-version")).to_have_count(2)
    expect(view.locator(".lf-fp-version[data-current]")).to_contain_text("Showing")
    # Each version says the note its stamp gave it after its name, whole on hover.
    expect(view.locator(".lf-fp-note")).to_have_text(["two", "t"])
    expect(view.locator(".lf-fp-version .lf-fp-item").first).to_have_attribute(
        "title", "two"
    )
    # The list is one stop for Tab, which the arrows walk from its way back through
    # each version and its Compare to the approval.
    stops = view.locator("button:not(:disabled)")
    expect(stops.nth(1)).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(stops.nth(2)).to_be_focused()
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


def test_versions_rests_the_page_s_keys_and_takes_a_version_s_number(browser, serve):
    """While Versions holds focus the page's keys rest, where d and j scrolled the page
    under it and c left it for the field. A version's number shows that version, not
    the row in that place, and `?` lists the numbers among the panel's keys."""
    url = serve(SIGN_OFF)
    for words, note in (("Paragraph zero.", "two"), ("Paragraph nought.", "three")):
        stamp_page(serve.page_dir, SIGN_OFF.replace("Paragraph 0.", words), note)
    page = floating(browser, url)
    view = page.locator(".lf-fp-menu[data-level=versions]")

    def open_versions():
        page.locator("body").focus()
        page.keyboard.press("g")
        page.keyboard.press("Shift+V")
        expect(view.locator(".lf-fp-version")).to_have_count(3)

    open_versions()
    document = "() => document.scrollingElement.scrollTop"
    before = page.evaluate(document)
    for key in "djc":
        page.keyboard.press(key)
    one_frame(page)
    assert page.evaluate(document) == before
    expect(view.locator(".lf-fp-version .lf-fp-item").first).to_be_focused()

    page.keyboard.press("?")
    reference = page.locator(".lf-command-reference")
    expect(
        reference.locator('tr[data-lf-command="panel.floating.versions.pick"] kbd')
    ).to_have_text(["1–3"])
    page.keyboard.press("Escape")
    expect(reference).to_be_hidden()

    open_versions()
    # v1 is the last row: the number names the version.
    page.keyboard.press("1")
    expect(page).to_have_url(re.compile(r"/versions/v1\b"))


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


def test_the_row_says_the_version_shown_is_approved(browser, serve):
    """Once the user approves the version shown, the row says so, quietly and with no
    press, until Undo takes the approval back."""
    page = floating(browser, serve(SIGN_OFF))
    notice = page.locator(".lf-fp-row-notice")
    expect(notice).to_be_hidden()
    page.locator(".lf-fp-leaf").click()
    page.locator(".lf-fp-menu .lf-fp-item", has_text="Versions").click()
    view = page.locator(".lf-fp-menu[data-level=versions]")
    with sending(page, "the approval"):
        view.locator(".lf-fp-item", has_text="Approve version").click()
    expect(notice).to_have_text(re.compile(r"^\s*✓ v1 approved\s*$"))
    expect(notice.locator("button, a")).to_have_count(0)
    expect(notice.locator(".lf-fp-row-notice-face")).to_have_attribute(
        "data-tone", "ok"
    )
    page.keyboard.press("Escape")
    page.locator("body").focus()
    with sending(page, "the undo"):
        page.keyboard.press("z")
    expect(notice).to_be_hidden()


def test_a_failed_save_is_an_error_until_the_next_valid_one(browser, serve):
    """When the agent's latest save fails its check, the page keeps the last one that
    passed, and that stands as an error: the field says it and Errors in the leaf's
    menu lists it, and Versions says what the check found. It leaves both with the next
    valid save."""
    page = open_page(browser, live_url(serve(LIVE_V1)))
    (serve.page_dir / "index.html").write_text(LIVE_V2.replace("</main>", ""))
    told(page)
    expect(field(page)).to_have_attribute("data-says", "error")
    expect(field(page)).to_have_attribute(
        "placeholder", re.compile(r"^Latest edit not shown")
    )
    page.locator(".lf-fp-leaf").click()
    expect(page.locator('.lf-fp-menu [data-row="errors"]')).to_contain_text("1")
    page.locator(".lf-fp-menu .lf-fp-item", has_text="Versions").click()
    failed = page.locator(".lf-fp-menu[data-level=versions] .lf-fp-failed")
    expect(failed).to_contain_text("Latest edit couldn't be shown")
    expect(failed.locator(".lf-fp-failed-error")).not_to_be_empty()
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    (serve.page_dir / "index.html").write_text(LIVE_V2)
    told(page)
    expect(field(page)).not_to_have_attribute("data-says", "error")
    page.locator(".lf-fp-leaf").click()
    expect(page.locator('.lf-fp-menu [data-row="errors"]')).to_have_count(0)


def test_a_website_copy_says_who_revises_it_and_where_leaf_comes_from(browser, serve):
    """On Leaf's website the field says who revises the visitor's copy, the row's notice
    says where Leaf comes from, and the leaf's menu keeps the introduction with its
    links."""
    page = floating(
        browser,
        serve(
            leaf_page("Website example", "<h1>Website example</h1>"),
            website_publication={
                "kind": "example",
                "agent": "Leaf guide",
                "install_url": "/#install",
            },
        ),
    )
    expect(field(page)).to_have_attribute(
        "placeholder", re.compile("^Leaf guide revises your private copy")
    )
    notice = page.locator(".lf-fp-row-notice a")
    expect(notice).to_have_text(re.compile(r"^\s*Example\s*·\s*Install Leaf\s*$"))
    expect(notice).to_have_attribute("href", "/#install")
    page.locator(".lf-fp-leaf").click()
    links = page.locator(".lf-fp-menu .lf-fp-state a")
    expect(links).to_have_count(2)
    assert links.evaluate_all("as => as.map(a => a.getAttribute('href'))") == [
        "/examples/",
        "/#install",
    ]


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
    expect_panel_says(page, "Approval")

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
          go.onclick = () => api.obligationActions.open(
            api.readObligations().all.find((item) => item.source.kind === 'approval').id);
          go.style.cssText = 'position: fixed; top: 0; left: 0';
          document.body.append(go);
        }"""
    )
    page.locator("#to-approval").click()
    card = page.locator(".lf-fp-view[data-view=queue] [data-approval]")
    expect(card.get_by_role("button", name="Undo")).to_be_focused()


def test_the_approval_is_arrived_at_in_sight_below_many_obligations(browser, serve):
    """With more obligations than On me shows at once, arriving at the approval
    scrolls its card into the view, so the Approve the user stands on is in sight."""
    items = "".join(
        f'<lf-ask id="ask-{n}"><h3>Question {n}?</h3><lf-options id="o-{n}" choose>'
        f'<lf-option id="y-{n}">Yes</lf-option><lf-option id="n-{n}">No</lf-option>'
        "</lf-options></lf-ask>"
        for n in range(12)
    )
    source = leaf_page("many", f"<h1>Many</h1>{items}").replace(
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
          go.onclick = () => api.obligationActions.open(
            api.readObligations().all.find((item) => item.source.kind === 'approval').id);
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
    """Annotations, a row of the leaf's menu, opens a list whose Draw mode stands its ✕ at
    the row's end, beside the counts, and names the mode in the field; the ✕ leaves the
    mode. Picking an element is left to the page, where selecting words or pressing `s`
    starts it, so Annotations doesn't list it."""
    page = floating(browser, serve(LONG_PAGE, comments=1))
    page.locator(".lf-fp-leaf").click()
    page.locator(".lf-fp-menu .lf-fp-item", has_text="Annotations").click()
    expect(page.locator(".lf-fp-item", has_text="Capture area")).to_be_visible()
    expect(page.locator(".lf-fp-item", has_text="Select element")).to_have_count(0)
    page.locator(".lf-fp-item", has_text="Draw mode").click()
    exit_step = page.locator('.lf-fp-exit[aria-label="Exit Draw mode"]')
    expect(exit_step).to_be_visible()
    expect(page.locator(".lf-fp-on-user")).to_be_visible()
    # The field names the mode in the status's place.
    expect(field(page)).to_have_attribute("data-says", "stance")
    expect(field(page)).to_have_attribute("placeholder", re.compile("^In Draw mode"))
    exit_step.click()
    expect(exit_step).to_have_count(0)
    expect(field(page)).to_have_attribute("data-says", "status")
    expect(page.locator(".lf-fp-on-user")).to_be_visible()


def test_the_leaf_s_menu_marks_what_opens_a_list_and_leaves_key_conveniences_out(
    browser, serve
):
    """The row holds the leaf, the field and the two counts, and the leaf's menu holds
    the rest. A menu row that opens a list of its own ends in a chevron. Navigate lists
    where a reader goes from a menu; the keyboard's conveniences for where they stand
    (Page Map beside the margin's rail, Resume writing, Restore selection, Align current
    item at top) keep their keys, and the menu leaves them out."""
    page = floating(browser, serve(LONG_PAGE, comments=1))
    expect(page.locator(".lf-fp-quick button")).to_have_count(2)
    page.locator(".lf-fp-leaf").click()
    menu = page.locator(".lf-fp-menu")
    for opens in ("Navigate", "Annotations"):
        expect(menu.locator(".lf-fp-item[data-opens]", has_text=opens)).to_have_count(1)
    expect(
        menu.locator(".lf-fp-item[data-opens]", has_text="Keyboard shortcuts")
    ).to_have_count(0)
    menu.locator(".lf-fp-item", has_text="Navigate").click()
    listed = page.locator(
        ".lf-fp-menu[data-level=group] .lf-fp-item:not(.lf-fp-menu-back) .lf-fp-label"
    )
    expect(listed.filter(has_text="Search page")).to_have_count(1)
    assert set(listed.all_inner_texts()) <= {"All pages", "Search page"}


def test_a_list_the_menu_leads_to_takes_its_place_and_goes_back(browser, serve):
    """A menu row that opens a list turns the menu to that list in the same box, under a
    head naming it, with no view rising from the field; the head, ← and Escape go back
    to the menu, standing a keyboard user on the row that led there, and → on that row
    goes in again, onto the list's first row."""
    page = floating(browser, serve(LONG_PAGE, comments=1))
    menu = page.locator(".lf-fp-menu")
    back = menu.locator(".lf-fp-menu-back")
    annotations = menu.locator(".lf-fp-item[data-row='group:annotate']")
    page.locator(".lf-fp-leaf").click()
    annotations.click()
    expect(back).to_have_text("Annotations")
    expect(menu.locator(".lf-fp-item", has_text="Draw mode")).to_be_visible()
    expect(page.locator(".lf-fp-view")).to_have_count(0)
    back.click()
    expect(back).to_have_count(0)
    expect(annotations).to_be_visible()

    annotations.focus()
    page.keyboard.press("ArrowRight")
    expect(back).to_have_text("Annotations")
    expect(menu.locator(".lf-fp-item", has_text="Draw mode")).to_be_focused()
    page.keyboard.press("ArrowLeft")
    expect(annotations).to_be_focused()
    page.keyboard.press("Enter")
    expect(back).to_be_visible()
    page.keyboard.press("Escape")
    expect(annotations).to_be_focused()
    page.keyboard.press("Escape")
    expect(menu).to_be_hidden()


def test_all_pages_in_the_menu_counts_the_pages_it_lists(
    browser, serve, other_leaf, live_leaf
):
    """The menu's All pages row says how many pages its view lists, this page
    included, and follows the page list while it stands open: a neighbour that closes leaves the count."""
    _, closing_dir = live_leaf("closing", "The closing leaf")
    page = floating(browser, serve(LONG_PAGE))
    page.locator(".lf-fp-leaf").click()
    page.locator(".lf-fp-menu .lf-fp-item", has_text="Navigate").click()
    row = page.locator(
        ".lf-fp-menu[data-level=group] .lf-fp-item", has_text="All pages"
    )
    expect(row.locator(".lf-fp-value")).to_have_text("3")
    write_record(
        closing_dir / "status.json",
        {"state": "idle", "detail": "", "ts": cleanup_model.now_iso()},
    )
    told(page)
    expect(row.locator(".lf-fp-value")).to_have_text("2")


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
    """The menu's head says the agent's state in its one line, in the state's ink, and
    under that only what the status's disclosure adds to the line: while the agent
    works, the disclosure's sentence restates the line, so what waits on the user is all
    it adds. The line names the state itself, so no word for it stands above."""
    url = serve(OBLIGATION_PAGE)
    working(serve.page_dir, "Drafting the rollout")
    page = floating(browser, url)
    line = re.compile(r"^Claude working\b.* — Drafting the rollout")
    page.locator(".lf-fp-leaf").click()
    head = page.locator(".lf-fp-state")
    expect(head.locator("> *")).to_have_count(2)
    summary = head.locator("> .lf-fp-summary")
    expect(summary).to_have_text(line)
    assert summary.evaluate(
        """line => {
          const ink = document.createElement('span');
          ink.hidden = true;
          ink.style.color = 'var(--accent)';
          line.append(ink);
          const worn = getComputedStyle(ink).color === getComputedStyle(line).color;
          ink.remove();
          return worn;
        }"""
    )
    expect(head.locator("> .lf-fp-explain")).to_have_text(
        re.compile(r"^Waiting on me: 2 to answer\. Waiting on Claude: 1 to-do")
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
    expect(head.locator(".lf-fp-summary")).to_have_text(re.compile(r" away$"))
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
    told(page)
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
    url = serve(OBLIGATION_PAGE)
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
    # Open counts what the thread mark counts, so the mark's number is found here.
    open_tab = page.locator(".lf-fp-filters button", has_text="Open")
    expect(open_tab.locator(".lf-fp-count")).to_have_text("2")

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
    in a resolved thread, or while the panel is folded. A resolved thread's field says
    no error either, so the leaf's dot marks one raised there."""
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
    page.locator(".lf-fp-filters button", has_text="Resolved").click()
    page.locator(".lf-fp-view[data-view=threads] .lf-fp-thread").first.click()
    expect(settle).to_have_text("Reopen", use_inner_text=True)
    page.evaluate(
        "async () => (await window.__lfWidgetApi()).raiseError('Couldn\\'t load v1')"
    )
    expect(page.locator(".lf-fp-error-dot")).to_be_visible()
    expect(field(page)).not_to_have_attribute("data-says", "error")
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
    that opened it: a row in a list the menu turned to does too, and folding stands on
    the folded leaf."""
    page = floating(browser, serve(LONG_PAGE, comments=1))
    leaf = page.locator(".lf-fp-leaf")
    menu = page.locator(".lf-fp-menu")
    leaf.click()
    menu.locator(".lf-fp-item", has_text="Annotations").click()
    menu.locator(".lf-fp-item").last.click()
    expect(menu).to_be_hidden()
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
    field: text.right,
    press: document.querySelector('.lf-fp-field .lf-compose-submit')
      ?.getBoundingClientRect().toJSON(),
  };
}"""
# The right end of each line of words in the field, top to bottom.
WORD_LINES = """host => {
  const rows = [];
  for (const line of window.editorRoots.get(host).querySelectorAll('.cm-line')) {
    const range = document.createRange();
    range.selectNodeContents(line);
    for (const r of range.getClientRects()) {
      if (r.width < 0.5) continue;
      const row = rows.find(o => Math.abs(o.top - r.top) < 4);
      if (row) row.right = Math.max(row.right, r.right);
      else rows.push({top: r.top, right: r.right});
    }
  }
  return rows.sort((a, b) => a.top - b.top).map((row) => row.right);
}"""


def test_the_row_s_marks_and_presses_share_the_words_line(browser, serve):
    """Everything in the row stands on the one line the words are written on: the
    leaf, Dictate, the counts, and Send while the user types, each centred on the
    field's last line of words, however many lines it holds. Send floats in the field's
    end corner, as an anchored comment box's does: the words above its line run past
    it, and the last line keeps room for it."""
    page = open_page(browser, serve(LONG_PAGE), init_script=EDITOR_ROOTS)
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
    assert seats["press"]["right"] == pytest.approx(seats["field"], abs=1), seats
    # The lines above Send's own may run past its left edge (where words end depends
    # on how they wrap); the last line's words stop short of it.
    first_line = field(page).evaluate(
        "host => window.editorRoots.get(host).querySelector('.cm-line')"
        ".getBoundingClientRect().right"
    )
    assert first_line > seats["press"]["left"], (first_line, seats)
    lines = field(page).evaluate(WORD_LINES)
    assert lines[-1] <= seats["press"]["left"], (lines, seats)


def test_a_long_draft_offers_more_room_at_a_press(browser, serve):
    """Past three lines the field offers more room, by a press rather than on its own:
    a mark stands over the leaf, beside the field's first line, taking no room of its
    own, or in an open view's head. Pressing it widens the panel and keeps the caret in
    the words; emptying the field folds it back."""
    page = floating(browser, serve(LONG_PAGE))
    panel = page.locator(".lf-floating-panel")
    expand = page.locator(".lf-fp-expand")
    field(page).click()
    page.keyboard.type("A line of words long enough to wrap in the panel's field, " * 2)
    expect(expand).to_be_hidden()
    narrow = panel.bounding_box()["width"]
    page.keyboard.type("A line of words long enough to wrap in the panel's field, " * 2)
    expect(expand).to_be_visible()
    expect(page.locator(".lf-fp-context")).to_be_hidden()
    words = page.locator(".lf-fp-field").bounding_box()
    leaf = page.locator(".lf-fp-leaf").bounding_box()
    mark = expand.bounding_box()
    assert mark["x"] + mark["width"] <= words["x"] + 0.5, (words, mark)
    assert words["y"] <= mark["y"] + 0.5, (words, mark)
    assert mark["y"] + mark["height"] <= leaf["y"] + 0.5, (leaf, mark)
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("Shift+T")
    expect(page.locator(".lf-fp-head .lf-fp-expand")).to_be_visible()
    expect(page.locator(".lf-fp-field .lf-fp-expand")).to_have_count(0)
    page.keyboard.press("Escape")
    field(page).click()
    expect(page.locator(".lf-fp-row > .lf-fp-expand")).to_be_visible()
    expect(expand).to_have_attribute("aria-pressed", "false")
    expand.click()
    expect(expand).to_have_attribute("aria-pressed", "true")
    expect(field(page)).to_be_focused()
    settled(page)
    assert panel.bounding_box()["width"] > narrow + 100
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


def test_a_long_draft_leaves_an_open_view_its_head(browser, serve):
    """A long draft and an open view share the window: the view takes what the field
    leaves and scrolls inside it, so its head, where Close stands, stays in the window.
    The two once stacked at their own full heights, the view's head above the window's
    top."""
    url = serve(LONG_PAGE)
    for n in range(30):
        panel_comment(serve.page_dir, f"Page comment {n}")
    page = floating(browser, url)
    page.set_viewport_size({"width": 1440, "height": 900})
    page.keyboard.press("g")
    page.keyboard.press("Shift+T")
    view = page.locator(".lf-fp-view[data-view=threads]")
    expect(view).to_be_visible()
    field(page).click()
    page.keyboard.insert_text("".join(f"Line {n} of a long draft\n" for n in range(40)))
    page.locator(".lf-fp-head .lf-fp-expand").click()
    settled(page)
    head = page.locator(".lf-fp-head").bounding_box()
    shown = view.bounding_box()
    words = page.locator(".lf-fp-field").bounding_box()
    assert head["y"] >= 0, head
    assert shown["y"] + shown["height"] <= words["y"] + 0.5, (shown, words)
    assert view.evaluate("v => v.scrollHeight > v.clientHeight")


@pytest.mark.parametrize("touch", [False, True])
def test_the_page_end_stops_as_far_above_the_row_as_the_row_stands_up(
    browser, serve, touch
):
    """The theme reserves the panel's row at the window's foot, with the gap it stands
    above the window's edge again above it, so the page's last line scrolls clear of the
    row and no further. The reserve was a number of its own, 4px taller than the row
    under a mouse and under a finger alike."""
    context = browser.new_context(
        viewport={"width": 1280, "height": 800}, has_touch=touch
    )
    page = open_page(browser, serve(LONG_PAGE), context=context)
    assert page.evaluate("() => matchMedia('(pointer: coarse)').matches") == touch
    at = page.evaluate("""() => {
      const room = document.createElement('div');
      room.style.height = 'var(--lf-foot-room)';
      document.body.append(room);
      const foot = room.getBoundingClientRect().height;
      room.remove();
      const row = document.querySelector('.lf-fp-row').getBoundingClientRect();
      return {foot, row: row.height, below: innerHeight - row.bottom};
    }""")
    assert at["foot"] == pytest.approx(at["row"] + 2 * at["below"], abs=0.5), at


@pytest.mark.parametrize("touch", [False, True])
def test_a_press_arriving_in_a_line_of_answers_moves_nothing(browser, serve, touch):
    """A line of answers holding only words is already a press tall, so the Undo a
    reading brings later moves nothing beside it. Under a finger the panel's presses
    are the row's 34px line, and the line kept the mouse's 28px, so a press arriving
    grew it by 6px."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Should the rollout wait?")
    thread_model.post_reply(
        serve.page_dir,
        {"to": root, "for": root},
        "Which week suits?",
        '<lf-ask id="week"><h3>Which week?</h3><lf-options id="week-choice" choose>'
        '<lf-option id="this">This week</lf-option>'
        '<lf-option id="next">Next week</lf-option></lf-options></lf-ask>',
    )
    context = browser.new_context(
        viewport={"width": 1280, "height": 800}, has_touch=touch
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-fp-on-user").click()
    answers = page.locator(".lf-fp-view[data-view=queue] .lf-fp-answers").first
    expect(answers).to_be_visible()
    heights = answers.evaluate("""line => {
      line.replaceChildren('Answered.');
      const words = line.getBoundingClientRect().height;
      const press = document.createElement('button');
      press.type = 'button';
      press.className = 'lf-fp-answer';
      press.textContent = 'Undo';
      line.append(press);
      return [words, line.getBoundingClientRect().height];
    }""")
    assert heights[1] == pytest.approx(heights[0], abs=0.5), heights


def test_a_count_arriving_moves_no_mark_under_a_finger(browser, serve):
    """Each mark keeps its count's room whether or not it has a number, under a finger
    as under a mouse, so a question arriving in a reply puts On me's count in that room
    and moves nothing beside it. The finger's larger aim floor once stood in place of
    that room, so the mark widened by the digit as the count came."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Should the rollout wait?")
    context = browser.new_context(
        viewport={"width": 1280, "height": 800}, has_touch=True
    )
    page = open_page(browser, url, context=context)
    assert page.evaluate("() => matchMedia('(pointer: coarse)').matches")
    marks = page.locator(".lf-fp-quick")
    on_me = page.locator(".lf-fp-on-user")
    expect(on_me.locator(".lf-fp-num")).to_have_text("")
    before = [box.bounding_box() for box in (marks, on_me)]
    thread_model.post_reply(
        serve.page_dir,
        {"to": root, "for": root},
        "Which week suits?",
        '<lf-ask id="week"><h3>Which week?</h3><lf-options id="week-choice" choose>'
        '<lf-option id="this">This week</lf-option>'
        '<lf-option id="next">Next week</lf-option></lf-options></lf-ask>',
    )
    told(page)
    expect(on_me.locator(".lf-fp-num")).to_have_text("1")
    assert [box.bounding_box() for box in (marks, on_me)] == before


def test_a_finger_finds_the_keyboard_s_conveniences_under_navigate(browser, serve):
    """Where no keyboard is there to reach them, the conveniences the desk's menu leaves
    to their keys stand under Navigate, so a finger keeps a way to each."""
    context = browser.new_context(
        viewport={"width": 1280, "height": 800}, has_touch=True
    )
    page = open_page(browser, serve(LONG_PAGE, comments=1), context=context)
    assert page.evaluate("() => matchMedia('(pointer: coarse)').matches")
    page.locator(".lf-fp-leaf").click()
    page.locator(".lf-fp-menu .lf-fp-item", has_text="Navigate").click()
    listed = page.locator(
        ".lf-fp-menu[data-level=group] .lf-fp-item:not(.lf-fp-menu-back) .lf-fp-label"
    )
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
    page = open_page(browser, serve(LONG_PAGE), init_script=no_clipboard)
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


PAGE_ANNOTATED = LONG_PAGE.replace("<body>", '<body data-annotations="page">', 1)


def test_a_thread_the_page_draws_nowhere_opens_in_the_panel(browser, serve):
    """On a page that draws no margin (`data-annotations="page"`), a thread about a
    passage has nowhere on the page to open, so the panel is its home: `m` arrives at
    the agent's question there, as `t` does at a thread, drawn by Leaf's reader in the
    panel's thread view (#91)."""
    url = serve(PAGE_ANNOTATED)
    panel_comment(
        serve.page_dir,
        "Should the rollout pause on Fridays?",
        anchor={"section": "p3", "quote": "Paragraph 3."},
        author="agent",
        question="Pause on Fridays?",
    )
    page = floating(browser, url)
    reader = page.locator(".lf-fp-view[data-view=thread]")
    page.locator("body").focus()
    page.keyboard.press("m")
    expect(reader.locator(".lf-msg")).to_contain_text("Should the rollout pause")
    page.keyboard.press("Escape")
    expect(reader).to_have_count(0)
    page.locator("body").focus()
    page.keyboard.press("t")
    expect(reader.locator(".lf-msg")).to_contain_text("Should the rollout pause")


def test_a_reply_its_card_cannot_draw_opens_in_the_panel(browser, serve):
    """A route to one message needs the reader that draws a message whole, which is
    Leaf's in the panel: a reply carrying a widget, which a thread's card beside its
    passage offers to open, opens in the panel's thread view, widget and all."""
    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir,
        "Which job should come first?",
        {"section": "p3", "quote": "Paragraph 3."},
    )
    thread_model.post_reply(
        serve.page_dir,
        {"to": root, "for": root},
        "Choose the first job.",
        '<lf-ask id="first-job-decision"><h3>Which job first?</h3>'
        '<lf-options id="first-job" choose>'
        '<lf-option id="mounts">Put the mounts back</lf-option>'
        '<lf-option id="camera">Install the camera</lf-option>'
        "</lf-options></lf-ask>",
    )
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    page.locator(".lf-page-thread-open").click()
    reader = page.locator(".lf-fp-view[data-view=thread]")
    expect(reader.locator("#first-job")).to_be_visible()


def test_a_page_comment_sent_before_the_first_reading_stands_in_the_panel(
    browser, serve
):
    """A page comment sent while the page still waits for its saved state is the thread
    the user opened: its view draws it at once, Threads lists it above the line saying
    the saved threads are still loading, and `t` walks to it once the view is put away.
    The panel once read threads only from a settled reading, so its view said the
    thread was not on the page, Threads listed nothing, and `t` was dropped."""
    held = []
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    page.route("**/api/state*", lambda route: held.append(route))
    page.route("**/api/event", lambda route: held.append(route))
    page.goto(serve(LONG_PAGE), wait_until="load")
    holding(page, held, 1, "the first state read")
    wait_until_ready(page, through="upgraded")
    words = "Sent before the page heard back."
    write(field(page), words)
    page.keyboard.press("Enter")
    view = page.locator(".lf-fp-view[data-view=thread]:not([data-leaving])")
    expect(view).to_contain_text(words)

    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-fp-view")).to_have_count(0)
    page.locator(".lf-fp-threads").click()
    threads = page.locator(".lf-fp-view[data-view=threads]")
    expect(threads.locator(".lf-fp-thread")).to_have_text([re.compile(words)])
    expect(threads.locator(".lf-fp-empty")).to_have_text("Loading current threads…")

    page.locator(".lf-fp-close").click()
    expect(page.locator(".lf-fp-view")).to_have_count(0)
    page.locator("body").focus()
    page.keyboard.press("t")
    expect(view).to_contain_text(words)
    expect(view).to_be_focused()


def test_a_refused_page_comment_hands_its_words_back_to_the_field(browser, serve):
    """A page comment the server refuses takes back the thread its send opened in the
    panel, which the server never held, so the field stands for the page again with
    the words in it and the caret in them, ready to send again."""
    page = floating(browser, serve(LONG_PAGE))

    def refuse(route):
        attempt = route.request.post_data_json["attempt"]
        route.fulfill(
            status=400,
            json={"ok": False, "attempt": attempt, "error": "refused", "final": True},
        )

    page.route("**/api/event", refuse)
    write(field(page), "Is the window long enough?")
    page.keyboard.press("Enter")
    expect(page.locator(".lf-fp-view")).to_have_count(0)
    expect(field(page)).to_have_js_property("value", "Is the window long enough?")
    expect(field(page)).to_be_focused()
    consume_browser_errors(page, http_error_console(400))


def test_a_thread_whose_words_are_gone_keeps_its_quotation_in_the_panel(browser, serve):
    """A thread about words the page no longer holds opens in the panel, where the
    quotation it kept stands over its messages, marked as no longer on the page, in
    three lines; Full quote shows the rest, as a card's head does."""
    url = serve(LONG_PAGE)
    words = "The earlier plan required a manual review before every rollout. " * 6
    panel_comment(
        serve.page_dir,
        "Does this still apply?",
        {"section": "gone", "quote": words + "FINAL WORDS"},
    )
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(".lf-fp-view[data-view=thread]")
    expect(view.locator(".lf-msg")).to_contain_text("Does this still apply?")
    quote = view.locator(".lf-quote")
    expect(quote).to_contain_text("FINAL WORDS")
    expect(quote).to_have_class(re.compile(r"\bdetached\b"))
    assert quote.evaluate("el => el.scrollHeight > el.clientHeight")
    disclosure = view.get_by_role("button", name="Full quote", exact=True)
    expect(disclosure).to_be_visible()
    disclosure.click()
    expect(disclosure).to_have_attribute("aria-expanded", "true")
    assert quote.evaluate("el => el.scrollHeight <= el.clientHeight + 1")


def test_a_thread_s_words_start_on_its_head_s_edge(browser, serve):
    """In a thread's view the head's words, the quote's and each message's start on one
    edge, the quote's rule standing left of it. A rewrite's frame reaches back only as
    far as that rule, so its words keep the message's and its frame stays clear of the
    panel's edge."""
    url = serve(PAGE_ANNOTATED)
    panel_comment(
        serve.page_dir,
        "Is the window long enough?",
        anchor={"section": "p3", "quote": "Paragraph 3."},
    )
    page = floating(browser, url)
    page.locator("body").focus()
    page.keyboard.press("t")
    view = page.locator(".lf-fp-view[data-view=thread]")
    expect(view.locator(".lf-msg")).to_contain_text("Is the window long enough?")
    settled(page)
    starts = """() => {
      const edge = document.querySelector('.lf-fp-card').getBoundingClientRect().left;
      const words = (node) => {
        const text = document.createTreeWalker(node, NodeFilter.SHOW_TEXT, {
          acceptNode: (t) => (t.textContent.trim() ? 1 : 3),
        }).nextNode();
        const range = document.createRange();
        range.selectNodeContents(text);
        return range.getClientRects()[0].left - edge;
      };
      const view = document.querySelector('.lf-fp-view[data-view=thread]');
      const quote = view.querySelector('.lf-fp-quote');
      const frame = view.querySelector('.lf-msg-editor .lf-compose-field');
      const text = frame?.querySelector('leaf-text');
      return {
        head: words(document.querySelector('.lf-fp-head')),
        quote: words(quote),
        message: words(view.querySelector('.lf-msg')),
        rule: quote.getBoundingClientRect().left - edge,
        frame: frame && frame.getBoundingClientRect().left - edge,
        rewrite: text && text.getBoundingClientRect().left - edge
          + parseFloat(getComputedStyle(text).paddingLeft),
      };
    }"""
    at = page.evaluate(starts)
    assert at["head"] == pytest.approx(at["quote"], abs=0.5), at
    assert at["message"] == pytest.approx(at["head"], abs=0.5), at
    assert 0 < at["rule"] < at["head"] - 4, at

    view.locator(".lf-msg-body").dblclick()
    expect(view.locator(".lf-msg-editor leaf-text")).to_be_focused()
    at = page.evaluate(starts)
    assert at["rewrite"] == pytest.approx(at["message"], abs=0.5), at
    assert at["frame"] == pytest.approx(at["rule"], abs=0.5), at


def test_the_go_to_doors_open_the_panel_s_views(browser, serve):
    """`g T` and `g M` open Threads and On me in the panel, and the same keys put them
    away again."""
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Is the window long enough?")
    page = floating(browser, url)
    view = page.locator(".lf-fp-view:not([data-leaving])")
    page.locator("body").focus()
    for keys, shown in (("Shift+t", "threads"), ("Shift+m", "queue")):
        page.keyboard.press("g")
        page.keyboard.press(keys)
        expect(view).to_have_attribute("data-view", shown)
        page.keyboard.press("g")
        page.keyboard.press(keys)
        expect(view).to_have_count(0)


def test_all_pages_is_a_view_of_the_panel(browser, serve, other_leaf):
    """All pages, from the leaf's menu under Navigate or by `g L`, opens a view above
    the row listing the pages live on this machine, this one first and marked as this
    page, each other one a link that opens it in a tab of its own. `g L` puts it away
    again."""
    page = floating(browser, serve(LONG_PAGE))
    pages = page.locator(".lf-fp-view[data-view=leaves]")
    page.locator(".lf-fp-leaf").click()
    page.locator(".lf-fp-menu .lf-fp-item", has_text="Navigate").click()
    page.locator(".lf-fp-menu .lf-fp-item", has_text="All pages").click()
    expect(page.locator(".lf-fp-title")).to_have_text("All pages")
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


def test_a_comment_on_words_where_the_page_draws_no_margin_is_written_in_the_row(
    browser, serve
):
    """On a page that draws its own annotations and gives the comment box no seat, the
    box for a comment on selected words stands in the field's place in the panel's row
    while it is open, holding the caret. Its
    comment sent, the panel opens the thread it started, which the page draws
    nowhere, and the field is back in the row."""
    page = floating(browser, serve(PAGE_ANNOTATED))
    response = page.locator(".lf-fp-response")
    select_words(page, "#p3")
    page.keyboard.press("c")
    box = response.locator("leaf-text")
    expect(box).to_be_visible()
    expect(box).to_be_focused()
    expect(page.locator(".lf-fp-field")).to_be_hidden()
    page.keyboard.type("Is this paragraph needed?")
    # Send stands in the field's end corner, as in every comment box, not on a line
    # of its own under the field.
    send = response.locator(".lf-compose-submit").bounding_box()
    words = box.bounding_box()
    assert words["y"] <= send["y"] and send["y"] + send["height"] <= (
        words["y"] + words["height"]
    ), (send, words)
    assert words["x"] + words["width"] / 2 < send["x"], (send, words)
    assert send["x"] + send["width"] <= words["x"] + words["width"], (send, words)
    # An image it is given hangs over the panel as the field's does, so the box and
    # its words stay where they are.
    card = page.locator(".lf-fp-card")
    before = (card.bounding_box(), box.bounding_box())
    box.evaluate(
        """(box, encoded) => {
          const bytes = Uint8Array.from(atob(encoded), char => char.charCodeAt(0));
          const transfer = new DataTransfer();
          transfer.items.add(new File([bytes], 'pasted.png', {type: 'image/png'}));
          box.dispatchEvent(new ClipboardEvent('paste', {
            bubbles: true, cancelable: true, clipboardData: transfer,
          }));
        }""",
        base64.b64encode(solid_png(40, 30, (255, 128, 64))).decode(),
    )
    picture = response.locator(".lf-composer-media-open")
    expect(picture).to_have_count(1)
    expect(box).not_to_have_attribute("aria-busy", "true")
    assert (card.bounding_box(), box.bounding_box()) == before
    tile = picture.bounding_box()
    assert tile["y"] + tile["height"] <= before[0]["y"], (tile, before)
    page.keyboard.press("Enter")
    reader = page.locator(".lf-fp-view[data-view=thread]")
    expect(reader.locator(".lf-msg")).to_contain_text("Is this paragraph needed?")
    expect(response).to_be_hidden()


def test_a_sample_shows_its_threads_in_its_panel(browser, serve):
    """A live sample's host asking for the panel (`surface: "panel"`) shows the thread
    it names in the child's panel, or its Threads with none named."""
    url = serve(
        titled_page(
            "A sample's threads",
            """
<style>#sample { height: 400px; }</style><h1>Containing page</h1>
<button id="show-thread" type="button">Show the thread</button>
<button id="show-threads" type="button">Show Threads</button>
<script id="history" type="application/json">
[{"id":"question","kind":"comment","author":"user","text":"Can we schedule lunch?"}]
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
    reader = child.locator(".lf-fp-view[data-view=thread]")
    expect(reader.locator(".lf-msg")).to_contain_text("Can we schedule lunch?")
    child.locator(".lf-fp-close").click()
    expect(reader).to_have_count(0)
    page.locator("#show-threads").click()
    expect(child.locator(".lf-fp-view[data-view=threads]")).to_be_visible()


def test_an_image_pasted_in_the_page_s_field_hangs_above_the_panel(browser, serve):
    """An image pasted into the page's field hangs just over the panel's top edge,
    outside its box, so attaching grows the panel by nothing and leaves the field its
    width; its thumbnail is the paste's result, so no notice says it was added."""
    page = floating(browser, serve(LONG_PAGE))
    field(page).click()
    card = page.locator(".lf-fp-card")
    before = card.bounding_box()
    field(page).evaluate(
        """(box, encoded) => {
          const bytes = Uint8Array.from(atob(encoded), char => char.charCodeAt(0));
          const transfer = new DataTransfer();
          transfer.items.add(new File([bytes], 'pasted.png', {type: 'image/png'}));
          box.dispatchEvent(new ClipboardEvent('paste', {
            bubbles: true, cancelable: true, clipboardData: transfer,
          }));
        }""",
        base64.b64encode(solid_png(40, 30, (255, 128, 64))).decode(),
    )
    shelf = page.locator(".lf-fp-box .lf-composer-media-item")
    expect(shelf).to_have_count(1)
    expect(field(page)).not_to_have_attribute("aria-busy", "true")
    assert card.bounding_box() == before
    assert field(page).bounding_box()["width"] > 300
    tile = shelf.bounding_box()
    assert tile["y"] + tile["height"] <= before["y"], (tile, before)
    assert tile["x"] >= field(page).bounding_box()["x"] - 1, tile
    expect(field(page)).not_to_have_attribute("placeholder", re.compile("Image added"))


def test_a_long_draft_fades_where_words_run_past_the_field(browser, serve):
    """A draft taller than the field shows no scrollbar, whose overlay flashed with each
    line; its words fade at whichever edge they run past, read from the field's scroll
    rather than a scroll timeline, which Firefox lacks."""
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


def test_a_draft_draws_a_bullet_list_as_the_message_will(browser, serve):
    """A draft's bullet item shows a bullet in place of its dash, with the item's
    wrapped line hanging under its words, as the sent message draws the list; the dash
    shows again, in the same room, while the caret touches it."""
    page = open_page(
        browser,
        serve(LONG_PAGE),
        init_script=EDITOR_ROOTS,
    )
    field(page).click()
    page.keyboard.type("- " + "an item long enough to wrap in the field " * 3)
    page.keyboard.press("Shift+Enter")
    page.keyboard.type("two")

    def reading():
        return field(page).evaluate(
            """host => {
              const root = window.editorRoots.get(host);
              const marks = [...root.querySelectorAll('.lf-md-bullet')];
              const words = document.createRange();
              words.selectNodeContents(root.querySelector('.cm-line'));
              const rows = [...words.getClientRects()];
              return {
                marks: marks.map((mark) => ({
                  left: mark.getBoundingClientRect().left,
                  drawn: getComputedStyle(mark, '::before').content,
                  ink: getComputedStyle(mark).color,
                })),
                wrapped: rows.at(-1).left - rows[0].left,
                markWidth: marks[0].getBoundingClientRect().width,
              };
            }"""
        )

    away = reading()
    assert [mark["drawn"] for mark in away["marks"]] == ['"•"', '"•"'], away
    assert away["marks"][0]["ink"] == "rgba(0, 0, 0, 0)", away
    assert away["wrapped"] == pytest.approx(away["markWidth"], abs=1), away
    page.keyboard.press("ControlOrMeta+Home")
    near = reading()
    assert near["marks"][0]["drawn"] == "none", near
    assert near["marks"][0]["left"] == away["marks"][0]["left"]
    # A nested item keeps its indentation and is drawn as a bullet too.
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.insert_text("- parent\n    - child")
    nested = reading()
    assert [mark["drawn"] for mark in nested["marks"]] == ['"•"', '"•"'], nested


def test_send_stands_in_the_counts_place_while_the_user_types(browser, serve):
    """Typing puts Send where the counts stood, wearing every composer's accent arrow
    rather than the panel's own press face, and a press that takes the caret away
    brings the counts back while the words stay where they were."""
    page = floating(browser, serve(LONG_PAGE))
    field(page).click()
    page.keyboard.type("Could the rollback cover the weekend?")
    send = page.locator(".lf-fp-send")
    expect(send).to_be_visible()
    accent = page.evaluate(
        "() => { const probe = document.createElement('span'); probe.style.color = 'var(--accent)';"
        " document.body.append(probe); const seen = getComputedStyle(probe).color;"
        " probe.remove(); return seen; }"
    )
    expect(send).to_have_css("color", accent)
    expect(page.locator(".lf-fp-on-user")).to_be_hidden()
    settled(page)
    words = field(page).bounding_box()
    page.mouse.click(5, 5)
    expect(field(page)).not_to_be_focused()
    expect(send).to_be_hidden()
    expect(page.locator(".lf-fp-on-user")).to_be_visible()
    settled(page)
    after = field(page).bounding_box()
    assert (after["x"], after["y"]) == (words["x"], words["y"])


def test_writing_reaches_the_field_however_the_panel_stands(browser, serve):
    """Asking to write reaches the panel's field from any state it stands in: `c`
    unfolds a panel folded to the leaf and rings the field as an anchored comment box is
    ringed, so the move shows, and Resume writing comes back to a reply left unsent in a
    thread the user has since closed, in the same field."""
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
    ring = page.locator(".lf-fp-field .lf-compose-field").evaluate(
        "box => [getComputedStyle(box).outlineStyle, getComputedStyle(box).outlineWidth]"
    )
    assert ring == ["solid", "2px"], f"the field holding the caret wears {ring}"
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
