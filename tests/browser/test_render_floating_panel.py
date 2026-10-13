"""The floating panel: Leaf's chrome as one box over the page's foot, where the user
chose it (`lf-chrome`, prepaint.js), in place of the banner and the bottom bar.

Each test is one journey a user takes through the panel, with the preference on:
writing a page comment and replying in the same field, settling the thread, finding
threads and taking in news, answering questions, travelling between versions, and
folding the panel to the leaf in the window's corner and back."""

import re

import pytest
from interact_support import append_carried_log_record
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
    resolved and reopened from the thread's head. The line above the field names where
    the words go. The banner and the bottom bar are gone, and Escape puts the thread
    away."""
    page = floating(browser, serve(LONG_PAGE))
    expect(page.locator(".lf-banner")).to_be_hidden()
    expect(page.locator(".lf-shortcut-bar")).to_be_hidden()

    write(field(page), "Could the rollback cover the weekend?")
    expect(page.locator(".lf-fp-context")).to_contain_text("New comment on the page")
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
    expect(page.locator(".lf-fp-context")).to_contain_text("Reply in")
    expect(field(page)).to_be_focused()

    write(field(page), "And the mobile cohort too.")
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
    expect(page.locator(".lf-fp-questions")).to_be_visible()

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


def test_questions_are_answered_where_they_are_read(browser, serve):
    """Questions lists what waits on the user, and each ask takes its answer there, by
    the widget's own choice: the event is the widget's action. The answered card keeps
    its place and height, so the next question does not move under the pointer, and
    Undo takes the answer back."""
    page = floating(browser, serve(ASK_PAGE))
    chip = page.locator(".lf-fp-questions")
    expect(chip).to_contain_text("2")
    chip.click()
    view = page.locator(".lf-fp-view[data-view=questions]")
    cards = view.locator(".lf-fp-question")
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
    expect(page.locator(".lf-fp-questions")).to_have_count(0)
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
    expect(page.locator(".lf-fp-questions")).to_be_hidden()
    settled(page)
    words = field(page).bounding_box()
    page.mouse.click(5, 5)
    expect(field(page)).not_to_be_focused()
    expect(send).to_be_hidden()
    expect(page.locator(".lf-fp-questions")).to_be_visible()
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
