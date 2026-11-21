"End-to-end journey and durable draft tests."

import pytest
from playwright.sync_api import expect
from render_cases_interaction import (
    live_url,
)
from render_harness import (
    open_page,
    panel_field,
    scroll_settled,
    write,
)

from browser.drafts import (
    editing_revision_source,
    replace_editing_document,
)
from browser.threads import open_panel_thread, seed_panel_threads
from leaf_dev.browser import PANEL_THREAD

pytestmark = pytest.mark.shifts_unsurveyed


def test_executable_revision_keeps_a_reader_who_scrolled_away_from_their_reply(
    browser, serve
):
    """A replaced reply box takes focus back without pulling the reader back to it.

    The reader wrote the reply to a long thread open in the panel, then scrolled its
    view back up the thread with no other input, so the box keeps focus while the
    reader reads elsewhere. A revision that replaces the document returns focus and
    words to the new box and leaves the view where they read."""
    url = live_url(serve(editing_revision_source("before")))
    [root] = seed_panel_threads(serve.page_dir, 1, long_index=0, messages=24)
    page = open_page(browser, url)
    view = open_panel_thread(page, root)
    scroller = f'{PANEL_THREAD}[data-lf-thread="{root}"]'
    reply = panel_field(page)
    words = "Words the reader left to read on."
    write(reply, words)
    view.evaluate("list => { list.scrollTop = 0; }")
    scroll_settled(page, scroller)
    expect(reply).to_be_focused()
    held = view.evaluate("list => list.scrollTop")
    assert view.evaluate("list => list.scrollHeight > list.clientHeight + 100")
    replace_editing_document(page, serve)
    expect(reply).to_be_focused()
    expect(reply).to_have_js_property("value", words)
    scroll_settled(page, scroller)
    assert view.evaluate("list => list.scrollTop") == pytest.approx(held, abs=2)
