"Where the reader's view stays when a revision, news or a repaint changes the page:\nlines, landmarks, active regions, panes and bounded scrollports."

import re

import pytest
from interact_support import append_carried_log_record, declare_work
from playwright.sync_api import expect
from render_cases_interaction import (
    SEATED_OBLIGATION_PAGE,
    live_url,
)
from render_harness import (
    open_page,
    panel_field,
    resized,
    told,
    write,
)

from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.watch_shifts
def test_live_news_keeps_the_reading_draft_in_the_thread_being_written_in(
    browser, serve
):
    """Live news keeps the user's simultaneous reading and editing places.

    At a phone's width, where the tall reply grows the most, the following passage and
    editor are visible below the reply's insertion point. The user writes in the
    thread, so its news draws at once, as in a chat: the agent's working state, then a
    tall reply, each standing above the editor, which holds still with its words and
    selection while what stands above it, Resolve included, scrolls up by the growth.
    An unrelated source revision then arrives while retaining the editor and the
    page's reading position.
    """
    source = SEATED_OBLIGATION_PAGE.replace(
        "</main>",
        '<p id="reading">The next passage remains where I am reading.</p>'
        + "<p>Further context. "
        + "Context. " * 300
        + "</p></main>",
    )
    url = serve(source)
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "Which job comes first?",
        },
    )
    page = open_page(browser, live_url(url))
    resized(page, 390, 900)
    thread = page.locator("#jobs .lf-page-thread")
    editor = thread.locator("leaf-text")
    words = "  Keep the middle of this unsent thought.  "
    write(editor, words)
    editor.evaluate("box => box.setSelectionRange(7, 17, 'backward')")
    # Read past the page's start: a page still at zero deliberately stays at its
    # start across revisions, showing any new context inserted before its title.
    page.evaluate("scrollTo({top: 20, behavior: 'instant'})")
    resolve = thread.get_by_role("button", name="Resolve thread", exact=True)
    reading = page.locator("#reading")
    expect(reading).to_be_in_viewport()
    rendered(page)
    # Keep Chrome's native clock and deliver news after its 500 ms input grace period.
    page.wait_for_timeout(600)
    place = reading.bounding_box()
    box = editor.bounding_box()
    assert place and box

    def kept():
        expect(editor).to_be_focused()
        assert editor.evaluate(
            "box => [box.value, box.selectionStart, box.selectionEnd, box.selectionDirection]"
        ) == [words, 7, 17, "backward"]
        assert reading.bounding_box() == pytest.approx(place, abs=0.5)
        assert editor.bounding_box() == pytest.approx(box, abs=0.5)

    def above_the_editor():
        target = resolve.bounding_box()
        assert target
        return target["y"]

    declare_work(serve.page_dir, "Checking the order of these jobs", item=root["id"])
    told(page)
    expect(panel_field(page)).to_have_attribute(
        "placeholder", re.compile("Checking the order")
    )
    expect(thread.locator(".lf-thread-working")).to_have_count(1)
    expect(thread.locator(".lf-thread-news")).to_have_count(0)
    rendered(page)
    kept()
    working = above_the_editor()

    reply = "\n\n".join(["The first job needs a careful explanation."] * 12)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": root["id"],
            "revision": 1,
            "text": reply,
        },
    )
    told(page)
    expect(thread.locator(".lf-msg")).to_have_count(2)
    expect(thread.locator(".lf-msg").last).to_contain_text(
        "The first job needs a careful explanation."
    )
    expect(thread.locator(".lf-thread-news")).to_have_count(0)
    rendered(page)
    kept()
    answered = above_the_editor()
    assert answered < working - 100, (working, answered)

    (serve.page_dir / "index.html").write_text(
        source.replace(
            "<title>seated question</title>", "<title>Jobs updated</title>"
        ).replace('<h1 id="h">', '<p id="new-context">New context.</p><h1 id="h">')
    )
    told(page)
    expect(page).to_have_title("Jobs updated")
    expect(page.locator("#new-context")).to_have_count(1)
    rendered(page)
    kept()
    assert above_the_editor() == pytest.approx(answered, abs=0.5)
