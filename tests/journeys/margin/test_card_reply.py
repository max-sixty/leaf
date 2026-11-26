"""Tests scheduled by the measured cost of their boundary."""

import pytest
from browser.margin import LONG_THREAD_ROOT, open_long_thread
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_harness import scroll_settled, sending, told

from leaf.source.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_card_says_new_reply_for_an_answer_past_its_transcript_s_foot(browser, serve):
    """The answer the user waits for, arriving past the card's capped transcript's foot,
    says New reply there, by the floating panel's rule (thread-card.js, `#fitAnswer`). A
    reader who read back keeps their place. One at the transcript's end keeps their turn
    in sight above the answer, unless the two fit together, when the end shows both. A
    press, a key on the press, or scrolling to the answer's start takes it away, and so
    does their next turn; the press and the key show the answer's start, on the
    thread."""
    page, preview, transcript = open_long_thread(browser, serve)
    thread = preview.locator(".lf-page-thread")
    press = preview.locator(".lf-new-reply")
    box = preview.locator(".lf-thread-reply leaf-text")
    limit = "list => list.scrollHeight - list.clientHeight"
    long_answer = "Someone stays on call through Sunday, and Monday too. " * 40

    def turn(words):
        box.click()
        page.keyboard.insert_text(words)
        with sending(page, "the turn"):
            page.keyboard.press("ControlOrMeta+Enter")
        rendered(page)

    def read_back():
        transcript.hover()
        page.mouse.wheel(0, -500)
        page.wait_for_function(
            "list => list.scrollTop < list.scrollHeight - list.clientHeight - 200",
            arg=transcript.element_handle(),
        )
        scroll_settled(page, ".lf-margin-preview .lf-thread-transcript")

    def answer(words):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Claude",
                "parent": LONG_THREAD_ROOT["id"],
                "revision": 1,
                "text": words,
            },
        )
        told(page)
        message = transcript.locator(".lf-msg", has_text=words[:30]).last
        expect(message).to_be_attached()
        rendered(page)
        return message

    turn("And the short version?")
    answer("At the end, in a line.")
    expect(press).to_have_count(0)
    assert transcript.evaluate(limit) - transcript.evaluate("l => l.scrollTop") <= 2

    turn("And the mobile cohort?")
    stood = transcript.evaluate(
        """list => {
          window.lfScrolled = [];
          list.addEventListener('scroll', () => lfScrolled.push(list.scrollTop));
          return list.scrollTop;
        }"""
    )
    answer("At the end: " + long_answer)
    expect(press).to_have_text("New reply")
    # It never goes to its end on the way, which a frame could show.
    scrolled = transcript.evaluate("() => window.lfScrolled")
    assert max([stood, *scrolled]) - stood < 100, (stood, scrolled)
    asked = transcript.locator(".lf-msg", has_text="And the mobile cohort?")
    head = asked.locator(".lf-msg-head").bounding_box()
    words = asked.bounding_box()
    list_box = transcript.bounding_box()
    assert list_box["y"] <= head["y"], (list_box, head)
    assert words["y"] + words["height"] <= press.bounding_box()["y"], (words, press)
    assert transcript.evaluate(limit) - transcript.evaluate("l => l.scrollTop") > 100

    turn("And the weekend?")
    read_back()
    place = transcript.evaluate("l => l.scrollTop")
    shown = answer("By a press: " + long_answer)
    expect(press).to_have_text("New reply")
    assert transcript.evaluate("l => l.scrollTop") == place
    foot = transcript.bounding_box()
    at = press.bounding_box()
    assert foot["y"] < at["y"] and at["y"] + at["height"] <= foot["y"] + foot["height"]
    # A message head's height, as the thread's other actions are.
    assert at["height"] == 28
    press.click()
    expect(press).to_have_count(0)
    expect(thread).to_be_focused()
    expect(shown.locator(".lf-msg-head")).to_be_in_viewport()

    turn("And the holiday?")
    read_back()
    shown = answer("By a key: " + long_answer)
    expect(press).to_have_text("New reply")
    press.focus()
    page.keyboard.press("Enter")
    expect(press).to_have_count(0)
    expect(thread).to_be_focused()
    expect(shown.locator(".lf-msg-head")).to_be_in_viewport()

    turn("And the night shift?")
    read_back()
    shown = answer("By scrolling: " + long_answer)
    expect(press).to_have_text("New reply")
    transcript.hover()
    for _ in range(20):
        if not press.count():
            break
        page.mouse.wheel(0, 120)
        page.wait_for_timeout(30)
    expect(press).to_have_count(0)

    turn("And the next one?")
    read_back()
    answer("By a turn: " + long_answer)
    expect(press).to_have_text("New reply")
    turn("Thanks.")
    expect(press).to_have_count(0)
