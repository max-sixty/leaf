"""Moving to and between threads by keyboard and pointer: the walks that reach a
thread and the history they leave, and leaving or re-entering a reply."""

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import THREAD_DIFF_PAGE, live_url, panel_comment
from render_harness import (
    LONG_PAGE,
    leaf_page,
    open_page,
    put_preview_away,
    resized,
    scroll_settled,
)

from browser.threads import open_panel_thread
from leaf_dev.browser import PANEL_THREAD

pytestmark = pytest.mark.shifts_unsurveyed


def test_back_returns_from_a_thread_the_walk_travelled_to(browser, serve):
    """Each trip to a thread somewhere else adds a history entry where the user stood,
    so Back retraces the walk one thread at a time, back to where the user was reading,
    and Forward replays it."""
    filler = "".join(f"<p>Filler paragraph {n}.</p>" for n in range(60))
    url = serve(
        leaf_page(
            "Back from a thread",
            "<h1>Back from a thread</h1>"
            "<section id=near><p>The first question sits at the top.</p></section>"
            f"<section id=above>{filler}</section>"
            "<section id=also><p>A second question sits halfway down.</p></section>"
            f"<section id=below>{filler}</section>",
        )
    )
    for section in ("near", "also"):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "anchor": {"section": section},
                "text": f"A question about {section}.",
            },
        )
    page = open_page(browser, url)
    page.evaluate("document.scrollingElement.scrollTo({top: 1e6, behavior: 'instant'})")
    reading = page.evaluate("document.scrollingElement.scrollTop")
    assert reading > 2000
    entries = page.evaluate("history.length")

    page.keyboard.press("Shift+t")
    page.wait_for_function("() => document.activeElement?.closest('[data-lf-thread]')")
    # Focus reaches the card before its passage starts scrolling into view.
    expect(page.locator("#also p")).to_be_in_viewport()
    scroll_settled(page)
    landed = page.evaluate("document.scrollingElement.scrollTop")
    assert landed < reading - 1000
    assert page.evaluate("history.length") == entries + 1

    first = page.evaluate(
        "document.activeElement.closest('[data-lf-thread]').dataset.lfThread"
    )
    page.keyboard.press("Shift+t")
    page.wait_for_function(
        "first => document.activeElement?.closest('[data-lf-thread]')?.dataset.lfThread"
        " !== first",
        arg=first,
    )
    expect(page.locator("#near p")).to_be_in_viewport()
    scroll_settled(page)
    walked = page.evaluate("document.scrollingElement.scrollTop")
    assert walked < landed - 1000
    assert page.evaluate("history.length") == entries + 2

    for back, top in [
        (True, landed),
        (True, reading),
        (False, landed),
        (False, walked),
    ]:
        page.wait_for_function("navigation.transition === null")
        if back:
            page.go_back()
        else:
            page.go_forward()
        page.wait_for_function(
            "top => Math.abs(document.scrollingElement.scrollTop - top) <= 2", arg=top
        )


@pytest.mark.parametrize(
    "left",
    [
        "page thread's link",
        "passage thread's link",
        "card's link",
        "walk",
        "Show on page",
    ],
)
def test_back_reopens_the_thread_its_departure_put_away(browser, serve, left):
    """Leaving a thread for a place its view would stand over puts the view away, and
    Back reopens the thread in the reader the user had it in, where they had read it
    to, with the user on it and no other thread open: the panel for a thread they read
    there, about the whole page or a passage, and the margin card for one they read in
    the card. A `t` walk from the panel's thread to a card, and Show on page, read
    where the user was before the panel puts its view away. Forward lands on the place
    again and puts the view away again."""
    url = serve(LONG_PAGE)
    page_root = panel_comment(serve.page_dir, "Where does this end?")
    passage_root = panel_comment(
        serve.page_dir, "Why here?", {"section": "p1", "quote": "Paragraph 1."}
    )
    for root in (page_root, passage_root):
        # The link stands in the thread's first reply, above the replies the panel's
        # view opens at.
        for text in [
            "See [the last paragraph](#p59).",
            *(f"Reply {n}. " + "More of the explanation. " * 30 for n in range(6)),
        ]:
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
    page = open_page(browser, url)
    card = page.locator(
        f'.lf-margin-preview .lf-page-thread[data-lf-thread="{passage_root}"]'
    )
    if left == "card's link":
        page.keyboard.press("t")
        thread = card
    else:
        root = (
            passage_root
            if left in ("passage thread's link", "Show on page")
            else page_root
        )
        open_panel_thread(page, root)
        if left in ("walk", "Show on page"):
            # From the page's foot, so going to the passage at its top moves the page.
            # Opening the passage's thread in the panel brought its passage into view.
            page.evaluate("scrollTo({top: 1e6, behavior: 'instant'})")
            scroll_settled(page)
        thread = page.locator(f'{PANEL_THREAD}[data-lf-thread="{root}"]')
    if left == "walk":
        page.keyboard.press("Escape")
        expect(thread).to_be_focused()
        page.keyboard.press("t")
        destination = card
    elif left == "Show on page":
        page.locator(".lf-fp-head .lf-fp-on-page").click()
        # A press lands on the card's thread, its reply holding no words
        # (floating-panel.js, `movedPart`).
        destination = page.locator(
            f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]'
        )
    else:
        link = thread.get_by_role("link", name="the last paragraph")
        link.scroll_into_view_if_needed()
        read_to = thread.evaluate("view => view.scrollTop")
        link.click()
        destination = page.locator("#p59")
    expect(destination).to_be_focused()
    expect(thread).to_be_hidden()

    page.go_back()
    expect(thread).to_be_focused()
    if left in ("page thread's link", "passage thread's link"):
        assert abs(thread.evaluate("view => view.scrollTop") - read_to) <= 2
    expect(
        page.locator(PANEL_THREAD if left == "card's link" else ".lf-margin-preview")
    ).to_be_hidden()
    # Forward to a card's reply box returns to the thread's passage instead, with the
    # panel's view still open: a reply's editing continuity carries it across a
    # revision (version.js), and a return carries no reply.
    if left != "Show on page":
        page.go_forward()
        expect(destination).to_be_focused()
        expect(thread).to_be_hidden()


def test_escape_from_a_seated_reply_send_returns_to_its_thread(browser, serve):
    """Escape leaves a reply's whole composition row, its Send control included, onto
    the thread the reply belongs to. On a thread seated in the page's flow the page's
    let-go answered Send first, since it deferred only to a box that takes letters, so
    the press dropped the user onto the page with the draft left behind."""
    url = serve(THREAD_DIFF_PAGE)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Does the tray fit the north bracket?",
            "anchor": {"section": "cd-q"},
        },
    )
    page = open_page(browser, live_url(url))
    resized(page, 1200, 900)
    thread = page.locator("#cd-q .lf-page-thread")
    thread.focus()
    page.keyboard.press("c")
    box = thread.locator("leaf-text")
    expect(box).to_be_focused()
    page.keyboard.type("draft")
    page.keyboard.press("Tab")
    expect(thread.locator(".lf-thread-send")).to_be_focused()
    # The Tab showed Send's preview, Escape's first step (WCAG 1.4.13).
    put_preview_away(page)
    page.keyboard.press("Escape")
    expect(thread).to_be_focused()
    page.keyboard.press("Enter")
    expect(box).to_be_focused()
    expect(box).to_have_js_property("value", "draft")


def test_a_click_survives_an_element_whose_id_shadows_a_dom_method(browser, serve):
    """A click's composed path ends at the document and the window, and an element with
    `id="matches"` puts itself at `window.matches`, where a reader of that path expects
    Element's method. A handoff page with a "matches" section threw on every click."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "named access",
                '<h1 id="title">Pairs</h1><h2 id="matches">A pair that matches</h2>'
                "<p id='body'>Words to click.</p>",
            )
        ),
    )
    page.locator("#matches").click()
    page.locator("#body").click()
