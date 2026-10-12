"""The floating panel: Leaf's chrome as one box over the page's foot, where the user
chose it (`lf-chrome`, prepaint.js), in place of the banner and the bottom bar.

Each test is one journey a user takes through the panel, with the preference on:
writing a page comment and replying in the same field, settling the thread, finding
threads and taking in news, and folding the panel to the leaf and back."""

from interact_support import append_carried_log_record
from leaf import event_log as events_model
from playwright.sync_api import expect
from render_cases_interaction import panel_comment
from render_harness import LONG_PAGE, open_page, sending, told, write

FLOATING = "localStorage.setItem('lf-chrome', 'floating')"


def floating(browser, url):
    page = open_page(browser, url, init_script=FLOATING)
    expect(page.locator(".lf-floating-panel")).to_be_visible()
    return page


def settled(page):
    """Wait until the panel's motion has finished, so a box read is where it rests."""
    page.wait_for_function(
        "() => !document.querySelector('.lf-floating-panel')"
        ".getAnimations({subtree: true}).length"
    )


def field(page):
    """The editor standing in the panel's field now: the page's, or a thread's."""
    return page.locator(".lf-fp-field leaf-text")


def test_one_field_starts_a_thread_takes_its_reply_and_settles_it(browser, serve):
    """The field clicked at rest is the field written in. Sending a page comment opens
    its new thread above the row, the same field now replying there, and the thread is
    resolved and reopened from the line naming where the words go. The banner and the
    bottom bar are gone, and Escape steps back along the panel to rest."""
    page = floating(browser, serve(LONG_PAGE))
    expect(page.locator(".lf-banner")).to_be_hidden()
    expect(page.locator(".lf-shortcut-bar")).to_be_hidden()

    write(field(page), "Could the rollback cover the weekend?")
    expect(page.locator(".lf-fp-to")).to_contain_text("Comment on this page")
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
    expect(page.locator(".lf-fp-to")).to_contain_text("Reply in this thread")
    expect(field(page)).to_be_focused()

    write(field(page), "And the mobile cohort too.")
    with sending(page, "the reply"):
        page.keyboard.press("ControlOrMeta+Enter")
    reply = events_model.read_events(serve.page_dir)[-1]
    assert (reply["kind"], reply["parent"]) == ("reply", comment["id"])

    settle = page.locator(".lf-fp-settle")
    with sending(page, "the resolve"):
        settle.click()
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "resolve"
    expect(settle).to_have_text("Reopen")
    with sending(page, "the reopen"):
        settle.click()
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "unresolve"
    expect(settle).to_have_text("Resolve")

    field(page).focus()
    for _ in range(3):
        page.keyboard.press("Escape")
    expect(page.locator(".lf-fp-view")).to_have_count(0)


def test_threads_filter_in_place_and_hold_news_until_asked(browser, serve):
    """The count of threads with news opens Threads at Unread, and the inventory keeps
    its height whichever filter stands, so the filter just pressed stays under the
    pointer. A reply that arrives while its thread is open waits behind New reply."""
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
    page.locator(".lf-fp-news").click()
    inventory = page.locator(".lf-fp-view[data-view=threads]")
    expect(page.locator(".lf-fp-filters [aria-pressed=true]")).to_have_text("Unread")
    expect(inventory.locator(".lf-fp-thread")).to_have_count(1)
    settled(page)
    unread_box = inventory.bounding_box()
    all_filter = page.locator(".lf-fp-filters button", has_text="All")
    before = all_filter.bounding_box()
    all_filter.click()
    expect(inventory.locator(".lf-fp-thread")).to_have_count(4)
    settled(page)
    assert inventory.bounding_box() == unread_box
    assert all_filter.bounding_box() == before

    inventory.locator(".lf-fp-thread", has_text="Is the window long enough?").click()
    reader = page.locator(".lf-fp-view[data-view=thread]")
    expect(reader.locator(".lf-fp-message")).to_have_count(2)
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
    held = page.locator(".lf-fp-held")
    expect(held).to_have_text("New reply · Show")
    expect(reader.locator(".lf-fp-message")).to_have_count(2)
    held.click()
    expect(reader.locator(".lf-fp-message")).to_have_count(3)
    expect(held).to_be_hidden()


def test_the_panel_folds_to_the_leaf_and_stays_folded(browser, serve):
    """Folding to the leaf is a choice the panel keeps across a reload, until the leaf
    is pressed again; `c` still reaches the page's field, and Go-to's Threads door
    opens the panel's own Threads."""
    url = serve(LONG_PAGE, comments=1)
    page = floating(browser, url)
    page.locator(".lf-fp-leaf").click()
    page.locator(".lf-fp-item", has_text="Layout").click()
    page.locator(".lf-fp-item", has_text="Fold to the leaf").click()
    panel = page.locator(".lf-floating-panel")
    expect(panel).to_have_attribute("data-rest", "mark")
    expect(page.locator(".lf-fp-field")).to_be_hidden()

    page.reload()
    expect(panel).to_have_attribute("data-rest", "mark")
    page.locator(".lf-fp-leaf").click()
    expect(panel).to_have_attribute("data-rest", "row")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-fp-view")).to_have_count(0)

    page.locator("body").focus()
    page.keyboard.press("c")
    expect(field(page)).to_be_focused()
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("Shift+T")
    expect(page.locator(".lf-fp-view[data-view=threads]")).to_be_visible()
    expect(page.locator(".lf-thread-panel")).not_to_have_class("open")
