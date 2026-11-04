"""Tests scheduled by the measured cost of their boundary."""

import pytest
from browser.threads import (
    long_diff_thread,
)
from browser.threads.test_composing import LEAD, long_seated_thread, send_reply
from playwright.sync_api import expect
from render_harness import (
    open_page,
    resized,
)

from leaf.render_checks import rendered


@pytest.mark.shifts_unsurveyed
@pytest.mark.watch_shifts
@pytest.mark.parametrize("engine", ["browser", "webkit_browser"])
@pytest.mark.parametrize(("seat", "lines"), [("widget", 1), ("diff", 1), ("diff", 4)])
def test_sends_from_a_page_threads_box_hold_its_foot_at_the_bands(
    engine, seat, lines, request, serve
):
    """Each send from a thread's box at the reading band's foot, where typing brings
    it, leaves the box's foot there, where Send and the caret stand, through the send
    that makes the thread taller than the band.

    The send landed the whole thread while it fitted and the reply row once it did
    not, and the thread, focused by the send, took its focus ring's room at its foot.
    So the first send lifted the box by that room and the thread's padding, and the
    send that made the thread too tall dropped it back by the same. Held by its top
    instead, a box emptied of several lines lifted its foot by the lines it lost."""
    browser = request.getfixturevalue(engine)
    url, root = (
        long_seated_thread(serve) if seat == "widget" else long_diff_thread(serve, LEAD)
    )
    page = open_page(browser, url)
    resized(page, 1200, 560)
    thread = page.locator(f'.lf-page-thread[data-lf-thread="{root}"]')
    expect(thread).to_be_visible()
    box = thread.locator("leaf-text")
    # The box's foot just past the landing band's, where the first keystroke lands it.
    box.evaluate(
        """box => scrollBy({top: box.getBoundingClientRect().bottom - innerHeight
          + parseFloat(getComputedStyle(document.documentElement).scrollPaddingBottom)
          - 12, behavior: 'instant'})"""
    )
    rendered(page)
    sends = []
    while not sends or not sends[-1][1]["tall"]:
        assert len(sends) < 8, sends
        words = "\n".join(f"Reply {len(sends)}, line {n}" for n in range(lines))
        sends.append(send_reply(page, thread, box, words))
    for before, after in sends:
        assert abs(after["foot"] - before["foot"]) < 1, sends
