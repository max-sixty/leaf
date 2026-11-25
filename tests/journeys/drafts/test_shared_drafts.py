"""Tests scheduled by the measured cost of their boundary."""

import pytest
from browser.drafts.test_shared_drafts import (
    _land,
    _reload_while_writing,
    _send_cut_short,
    _type_on_arrival,
)
from playwright.sync_api import expect
from render_harness import (
    LONG_PAGE,
    drafts_on_server,
    holding,
    open_page,
    refuse,
    restarting,
    stored_draft_text,
)

pytestmark = pytest.mark.shifts_unsurveyed


def test_words_typed_on_a_reload_stand_over_the_send_it_cut_short(
    firefox_browser, serve
):
    """A reload that cuts short a send still out starts from the drafts it was served,
    since only the log can say whether those words were sent, and the page it replaced
    resends them as it goes. Each reload after counts that resend as its own write
    until the server takes one of its own, so the words typed after a second reload
    stand over the resend landing after them. Firefox's routes hold the resend, which
    Chromium's don't see."""
    page = open_page(firefox_browser, serve(LONG_PAGE))
    sends = []
    _, says, reads = _reload_while_writing(
        page, before_reload=lambda: sends.extend(_send_cut_short(page))
    )
    holding(page, says["resent Kept"], 1, "the resend")
    refuse(sends[0])
    with restarting(page):
        page.reload()
    # The send took the user out of the box; `c` puts them back in it.
    page.keyboard.press("c")
    field = _type_on_arrival(page, " words")
    holding(page, says["K words"], 1, "the second reload's write")

    refuse(says["Ke"][0])
    for resend in says["resent Kept"]:
        _land(resend)
    assert drafts_on_server(page)["general"]["text"] == "Kept"
    page.unroute("**/api/draft")
    page.unroute("**/api/drafts")
    _land(says["K words"][0])
    for route in reads:
        route.continue_()
    assert stored_draft_text(page, "general") == "K words"
    expect(field).to_have_js_property("value", "K words")
