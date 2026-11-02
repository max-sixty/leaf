"""Tests scheduled by the measured cost of their boundary."""

import re

import pytest
from browser.drafts import (
    choose_comment_target,
)
from browser.drafts.test_comment_targets import _draft_attachment_boxes
from playwright.sync_api import expect
from render_harness import (
    LONG_PAGE,
    open_page,
    scroll_settled,
    sending,
    write,
)

from leaf import event_log as events_model
from leaf.render_checks import rendered
from leaf_dev.browser import slow_cpu


@pytest.mark.shifts_unsurveyed
@pytest.mark.parametrize(
    ("existing_reply", "resume_before_scroll"),
    [("", True), ("", False), ("This thread already holds a reply.", False)],
)
def test_comment_follows_a_thread_current_location_instead_of_an_earlier_draft(
    browser, serve, existing_reply, resume_before_scroll
):
    """A chrome thread is a destination; an earlier draft follows its own passage.

    Resume returns its words and caret before Comment answers the current thread.
    """
    page = open_page(browser, serve(LONG_PAGE, anchored=[("p41", "Paragraph 41.")]))
    if not resume_before_scroll:
        # Slow the browser to expose Resume interrupting native smooth travel.
        slow_cpu(page, 6)
    thread = page.locator(".lf-margin-preview .lf-page-thread")
    if existing_reply:
        page.keyboard.press("t")
        page.keyboard.press("c")
        write(thread.locator("leaf-text"), existing_reply)
        page.keyboard.press("Escape")
    words = "These words belong to my earlier unfinished comment."
    choose_comment_target(page, "#p3")
    expect(page.locator(".lf-fab-input")).to_have_attribute(
        "aria-label", re.compile("Paragraph 3")
    )
    write(page.locator(".lf-fab-input"), words)
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    rendered(page)
    earlier = page.locator(".lf-fab-input")
    earlier.evaluate("node => {window.earlierEditor = node;}")
    before_field, before_target = _draft_attachment_boxes(earlier, "#p3")
    page.keyboard.press("Shift+Tab")
    if resume_before_scroll:
        # Hold the ordering at the native smooth-scroll call: Resume runs before
        # its first frame, while both destinations still look readable. The real
        # browser animation runs, so a Resume that does not cancel it loses them.
        page.evaluate("""async () => {
          const {executeCommand} = await window.__lfCheckApi();
          const scrollTo = Element.prototype.scrollTo;
          Element.prototype.scrollTo = function(options) {
            const result = scrollTo.call(this, options);
            if (this === document.scrollingElement && options.behavior === 'smooth') {
              Element.prototype.scrollTo = scrollTo;
              window.earlyResumeBoxes = ['#p3', '.lf-fab-input'].map(selector =>
                document.querySelector(selector).getBoundingClientRect().toJSON());
              queueMicrotask(() => executeCommand('writing.resume'));
            }
            return result;
          };
        }""")
    page.keyboard.press("t")
    if resume_before_scroll:
        page.wait_for_function("window.earlyResumeBoxes !== undefined")
        boxes = page.evaluate("earlyResumeBoxes")
        height = page.viewport_size["height"]
        assert all(0 <= box["top"] < box["bottom"] <= height for box in boxes)
    else:
        expect(thread).to_be_focused()
        expect(page.locator("#p3")).not_to_be_in_viewport()
        expect(earlier).not_to_be_in_viewport()
    expect(earlier).to_have_js_property("value", words)
    expect(earlier).to_have_attribute("aria-label", re.compile("Paragraph 3"))
    if not resume_before_scroll:
        after_field, after_target = _draft_attachment_boxes(earlier, "#p3")
        for axis in ("x", "y"):
            assert after_field[axis] - before_field[axis] == pytest.approx(
                after_target[axis] - before_target[axis], abs=2
            )
        page.keyboard.press("g")
        page.keyboard.press("i")
    expect(earlier).to_be_focused()
    scroll_settled(page)
    expect(earlier).to_be_in_viewport()
    expect(page.locator("#p3")).to_be_in_viewport()
    expect(earlier).to_have_js_property("value", words)
    expect(earlier).to_have_js_property("selectionStart", 1)
    expect(earlier).to_have_js_property("selectionEnd", 1)
    assert earlier.evaluate("node => node === window.earlierEditor")
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("t")
    expect(thread).to_be_focused()
    expect(page.locator("#p3")).not_to_be_in_viewport()
    expect(earlier).not_to_be_in_viewport()
    page.keyboard.press("c")
    reply = thread.locator("leaf-text")
    expect(reply).to_be_focused()
    expect(reply).to_have_js_property("value", existing_reply or words)
    if existing_reply:
        page.keyboard.press("Escape")
        page.keyboard.press("g")
        page.keyboard.press("i")
        expect(page.locator(".lf-fab-input")).to_be_focused()
        expect(page.locator(".lf-fab-input")).to_have_js_property("value", words)
    else:
        page.keyboard.press("Escape")
        page.keyboard.press("g")
        page.keyboard.press("i")
        reply = page.locator("leaf-text[name=reply]:focus")
        expect(reply).to_be_focused()
        expect(reply).to_have_js_property("value", words)
        expect(reply).to_have_js_property("selectionStart", 1)
        with sending(page, "carried reply"):
            page.keyboard.press("Enter")
        replies = [
            event
            for event in events_model.read_events(serve.page_dir)
            if event["kind"] == "reply"
        ]
        assert [event["text"] for event in replies] == [words]
