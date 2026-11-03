"""Moving to and between threads by keyboard and pointer: the walks that reach a
thread and the history they leave, and leaving or re-entering a reply."""

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import THREAD_DIFF_PAGE, live_url
from render_harness import (
    leaf_page,
    open_page,
    resized,
    scroll_settled,
)

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
    page.wait_for_function("() => document.activeElement?.closest('[data-thread]')")
    # Focus reaches the card before its passage starts scrolling into view.
    expect(page.locator("#also p")).to_be_in_viewport()
    scroll_settled(page)
    landed = page.evaluate("document.scrollingElement.scrollTop")
    assert landed < reading - 1000
    assert page.evaluate("history.length") == entries + 1

    first = page.evaluate(
        "document.activeElement.closest('[data-thread]').dataset.thread"
    )
    page.keyboard.press("Shift+t")
    page.wait_for_function(
        "first => document.activeElement?.closest('[data-thread]')?.dataset.thread"
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
