"""Pointing reads; pressing acts: what a control, a mark or a value says before a press
acts on it, to a resting pointer, to the keyboard and to a held finger
(runtime/preview.js). The margin entry's preview, its label, is held in
`browser/margin/test_entries.py`."""

import re
from datetime import UTC, datetime, timedelta

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, panel_comment
from render_harness import leaf_page, open_page, preview_text

from browser.threads import open_panel_thread, thread_row
from leaf.render_checks import rendered

PREVIEW = "#lf-preview"
# Every box the thread draws, and the preview's own, where the page stands them.
BOXES = """() => [...document.querySelectorAll(
    '.lf-fp-view[data-lf-route=thread] *, .lf-fp-row *')]
  .filter((node) => node.checkVisibility())
  .map((node) => {
    const box = node.getBoundingClientRect();
    return [box.x, box.y, box.width, box.height].map(Math.round).join(',');
  })"""


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_control_previews_its_word_and_every_key_that_presses_it(
    engine, request, serve
):
    """A thread's Resolve shows its symbol, so its preview says its word and `r`, which
    presses it from anywhere in the thread, as a key chip: after a short rest of the
    pointer, at once under the keyboard's focus, and with no tooltip of the platform's
    beside it. The preview moves nothing and takes no pointer, and the next control the
    pointer reaches says its own at once. While it stands, Escape puts it away and does
    nothing else, so the thread it covers stays open; the next Escape leaves it."""
    url = serve(PANEL_PAGE)
    thread = panel_comment(serve.page_dir, "Could the mobile cohort wait a week?")
    page = open_page(request.getfixturevalue(engine), url)
    view = open_panel_thread(page, thread)
    resolve = page.locator(".lf-fp-thread-controls .lf-resolve")
    preview = page.locator(PREVIEW)
    expect(resolve).to_be_visible()
    # Off Leaf its word is the browser's tooltip; on Leaf the preview takes the title
    # once the pointer comes, so the browser shows no second one.
    title = resolve.get_attribute("title")
    assert title, "a symbol control carries its word as a title"
    rendered(page)
    before = page.evaluate(BOXES)

    resolve.hover()
    expect(preview).to_be_visible()
    expect(preview.locator(".lf-preview-word")).to_have_text("Resolve thread")
    expect(preview.locator("kbd.lf-key-badge")).to_have_text(["r"])
    assert resolve.get_attribute("title") is None, (
        "the browser's tooltip would show too"
    )
    # The chip's key is the one a screen reader hears it has.
    assert "r" in resolve.get_attribute("aria-keyshortcuts").split()
    rendered(page)
    assert page.evaluate(BOXES) == before, "showing the preview moved the thread"
    tip = preview.bounding_box()
    under = page.evaluate(
        "([x, y]) => document.elementFromPoint(x, y)?.id ?? null",
        [tip["x"] + tip["width"] / 2, tip["y"] + tip["height"] / 2],
    )
    assert under != "lf-preview", "the preview takes the pointer"

    close = page.locator(".lf-fp-head .lf-fp-close")
    close.hover()
    expect(preview.locator(".lf-preview-word")).to_have_text(
        close.get_attribute("aria-label")
    )
    page.mouse.move(0, 0)
    expect(preview).to_be_hidden()

    # The keyboard's focus reads it at once, and Escape hides it.
    resolve.focus()
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    expect(resolve).to_be_focused()
    expect(preview.locator("kbd.lf-key-badge")).to_have_text(["r"])
    page.keyboard.press("Escape")
    expect(preview).to_be_hidden()
    expect(resolve).to_be_focused()
    expect(view).to_be_visible()
    page.keyboard.press("Escape")
    expect(view).to_be_hidden()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_range_previews_beside_the_line_the_pointer_rests_on(engine, request, serve):
    """A range with no element of its own, as a passage mark is, previews through its
    owner's word of where the pointer rests: beside the line pointed at, carried with it
    through a scroll, and gone once the pointer leaves the range. An owner that makes the
    range again on every move points at the same range, so the dwell runs out once."""
    words = " ".join(["The passage runs across more than one line of the column."] * 6)
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page("Ranges", f'<p id="passage">{words}</p>' + "<p>More.</p>" * 40)
        ),
    )
    reading = page.evaluate(
        """async () => {
          const {pointRange} = await window.__lfCheckApi();
          const text = document.getElementById('passage').firstChild;
          const range = document.createRange();
          range.setStart(text, 0);
          range.setEnd(text, text.length);
          const lines = [...range.getClientRects()];
          const line = lines[1];
          const tip = document.getElementById('lf-preview');
          const started = performance.now();
          while (!tip.matches(':popover-open') && performance.now() - started < 2000) {
            pointRange(range.cloneRange(), () => ({name: 'Its thread'}),
              {x: line.left + 2, y: line.top + line.height / 2});
            await new Promise((done) => setTimeout(done, 20));
          }
          const box = tip.getBoundingClientRect();
          scrollBy(0, 30);
          await new Promise(requestAnimationFrame);
          await new Promise(requestAnimationFrame);
          const carried = tip.getBoundingClientRect().top - range.getClientRects()[1].bottom;
          pointRange(null);
          return {text: tip.innerText, gap: box.top - line.bottom, left: box.left - line.left,
            carried, open: tip.matches(':popover-open')};
        }"""
    )
    assert reading["text"] == "Its thread"
    assert reading["gap"] > 0 and reading["left"] == 0, reading
    assert abs(reading["carried"] - reading["gap"]) < 1, "the scroll left it behind"
    assert not reading["open"], "the preview stayed once the pointer left the range"


# A passage a thread is about, the words its mark paints, and where they stand.
PASSAGE = (
    "Nothing is lost, and the edits stay queued, but the user sees a spinner until "
    "they background the app: one reconnect in about 40."
)
MARKED = "one reconnect in about 40"
MARK_LINE = """(words) => {
  const text = document.getElementById('passage').firstChild;
  const at = text.data.indexOf(words);
  const range = document.createRange();
  range.setStart(text, at);
  range.setEnd(text, at + words.length);
  return range.getClientRects()[0].toJSON();
}"""
CARD = ".lf-margin-preview:not([hidden])"
# The ids of what a screen reader hears describe a node.
DESCRIBED = "(node) => (node.ariaDescribedByElements ?? []).map((el) => el.id)"


def _thread_on_a_passage(serve, viewport=None):
    """A page whose passage holds a thread the agent answered three hours ago with a
    question back, and the page's URL."""
    url = serve(
        leaf_page(
            "Passages", f'<p id="passage">{PASSAGE}</p>' + "<p>More words.</p>" * 12
        )
    )
    then = (datetime.now(UTC) - timedelta(hours=3)).isoformat()
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "ts": then,
            "text": "Why ship with that?",
            "anchor": {"section": "passage", "quote": MARKED},
        },
    )["id"]
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "ts": then,
            "parent": root,
            "responds": root,
            "text": "No edits were lost in 8,412 sessions.\nWhich stall do I chase?",
            "obligation": True,
        },
    )
    return url


def _says_where_the_thread_stands(preview):
    """The thread's name, then who said its last message and when, that message's
    opening line, and where the thread stands, in the turn's colour."""
    expect(preview.locator(".lf-preview-word")).to_have_text("Why ship with that?")
    lines = preview.locator(".lf-preview-detail")
    expect(lines).to_have_text(
        [
            "Claude · 3h ago",
            "No edits were lost in 8,412 sessions.",
            "Your turn · 1 unread · 2 messages",
        ]
    )
    expect(lines.last.locator("[data-lf-turn]")).to_have_attribute(
        "data-lf-turn", "user"
    )


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_thread_previews_where_it_stands_from_its_words_and_its_entry(
    engine, request, serve
):
    """A thread's passage mark and its margin entry say the same thing when pointed at,
    from the reading every surface paints the thread from: the thread's name, who wrote
    its last message and when, that message's opening line, and the thread's word, what
    it holds unread and how many messages. A resting pointer reads it beside the line it
    rests on, the keyboard on the entry reads it at once, which a screen reader hears as
    the entry's description, and a press on the words still opens the card
    (thread/messages.js, `threadPreview`)."""
    page = open_page(request.getfixturevalue(engine), _thread_on_a_passage(serve))
    preview = page.locator(PREVIEW)
    line = page.evaluate(MARK_LINE, MARKED)
    rendered(page)

    page.mouse.move(line["left"] - 20, line["top"] - 20)
    page.mouse.move(line["left"] + 10, line["top"] + line["height"] / 2, steps=3)
    expect(preview).to_be_visible()
    _says_where_the_thread_stands(preview)
    tip = preview.bounding_box()
    assert tip["y"] >= line["bottom"] and tip["x"] == line["left"], (tip, line)
    said = preview.inner_text()

    entry = page.locator('[data-lf-margin-for="passage"] > .lf-margin-marker')
    entry.hover()
    expect(preview).to_be_visible()
    assert preview.inner_text() == said, "the entry and the words say different things"
    page.mouse.move(0, 0)
    expect(preview).to_be_hidden()

    page.keyboard.press("Shift")
    entry.focus()
    expect(preview).to_be_visible()
    assert preview.inner_text() == said
    assert "lf-preview" in entry.evaluate(DESCRIBED)
    page.keyboard.press("Escape")
    expect(preview).to_be_hidden()
    assert "lf-preview" not in entry.evaluate(DESCRIBED)

    page.mouse.click(line["left"] + 10, line["top"] + line["height"] / 2)
    expect(page.locator(CARD)).to_be_visible()
    # The thread the user is now in previews nothing from its words, as an entry
    # standing open previews nothing: the card says it all.
    page.mouse.move(line["left"] + 30, line["top"] + line["height"] / 2, steps=3)
    page.wait_for_timeout(500)
    expect(preview).to_be_hidden()


def test_a_finger_holding_a_thread_s_words_reads_it_above_them(browser, serve):
    """A finger held on a thread's words reads the preview a pointer would, above the
    line, which the finger doesn't cover, and its release opens the thread, as a tap
    on the words does (preview.js, `pointRange`)."""
    url = _thread_on_a_passage(serve)
    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, has_touch=True
    )
    page = open_page(browser, url, context=context)
    cdp = context.new_cdp_session(page)
    preview = page.locator(PREVIEW)
    line = page.evaluate(MARK_LINE, MARKED)
    rendered(page)
    point = {"x": line["left"] + 10, "y": line["top"] + line["height"] / 2}
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [point]})
    expect(preview).to_be_visible()
    _says_where_the_thread_stands(preview)
    tip = preview.bounding_box()
    assert tip["y"] + tip["height"] <= line["top"], (tip, line)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    expect(preview).to_be_hidden()
    expect(page.locator(CARD)).to_be_visible()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_an_age_previews_its_clock_time_in_the_reader_s_zone(engine, request, serve):
    """An age says how long ago, and its preview says when, in the reader's own zone:
    a message's age to a resting pointer, and the message the keyboard stands on,
    beside its age, which a screen reader hears as the message's description; the
    message's words say no time to a pointer. The panel's ages are times too. No title
    stands beside any of them."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    asked = append_carried_log_record(
        d,
        {
            "kind": "comment",
            "author": "agent",
            "agent": "Claude",
            "ts": "2026-08-15T21:02:00Z",
            "text": "Which stall do I chase first?",
            "obligation": True,
        },
    )["id"]
    settled = panel_comment(d, "Could the mobile cohort wait a week?")
    append_carried_log_record(
        d,
        {
            "kind": "resolve",
            "author": "user",
            "parent": settled,
            "ts": "2026-08-16T01:30:00Z",
        },
    )
    browser = request.getfixturevalue(engine)
    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, timezone_id="America/Los_Angeles"
    )
    page = open_page(browser, url, context=context)
    preview = page.locator(PREVIEW)

    page.keyboard.press("m")
    question = page.locator(f'.lf-msg[data-lf-event="{asked}"]')
    expect(question).to_be_focused()
    expect(preview).to_have_text("Sat 15 Aug 2026, 14:02 PT")
    assert "lf-preview" in question.evaluate(DESCRIBED)
    # It stands by the age, not under the whole message.
    tip = preview.bounding_box()
    time = question.locator(".lf-msg-head time").bounding_box()
    assert 0 <= tip["y"] - (time["y"] + time["height"]) <= 24, (tip, time)
    assert (
        tip["x"] <= time["x"] + time["width"] and tip["x"] + tip["width"] >= time["x"]
    )
    # A pointer on the words of the message the keyboard is on hears no time from them.
    body = question.locator(".lf-msg-body").bounding_box()
    page.mouse.move(body["x"] + 8, body["y"] + body["height"] / 2, steps=3)
    page.wait_for_timeout(500)
    expect(preview).not_to_have_text("Sat 15 Aug 2026, 14:02 PT")
    page.mouse.move(0, 0)
    page.keyboard.press("Escape")

    view = open_panel_thread(page, asked)
    age = view.locator(".lf-msg-head time").first
    expect(age).not_to_have_attribute("title", re.compile(".*"))
    box = age.bounding_box()
    page.mouse.move(box["x"] - 30, box["y"] - 30)
    age.hover()
    expect(preview).to_have_text("Sat 15 Aug 2026, 14:02 PT")
    page.mouse.move(0, 0)
    expect(preview).to_be_hidden()

    resolved = thread_row(page, settled).locator("time")
    expect(resolved).to_have_attribute("datetime", "2026-08-16T01:30:00Z")
    expect(resolved).not_to_have_attribute("title", re.compile(".*"))
    assert preview_text(resolved) == "Sat 15 Aug 2026, 18:30 PT"


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_preview_shown_on_focus_describes_what_focus_is_on(engine, request, serve):
    """A screen reader hears a preview the keyboard's focus shows as the focused
    element's description while it stands, whatever supplied it, and the element's own
    description is back once focus leaves: a margin entry's, which its label declares."""
    url = serve(PANEL_PAGE)
    panel_comment(serve.page_dir, "Which command?", {"section": "lede"})
    page = open_page(request.getfixturevalue(engine), url)
    entry = page.locator('[data-lf-margin-for="lede"] .lf-margin-marker')
    expect(entry).to_be_visible()
    rendered(page)
    described = "(node) => (node.ariaDescribedByElements ?? []).map((el) => el.id)"
    page.keyboard.press("Shift")
    entry.focus()
    expect(page.locator(PREVIEW)).to_have_attribute("data-lf-route", "focus")
    assert "lf-preview" in entry.evaluate(described)
    page.keyboard.press("Tab")
    expect(entry).not_to_be_focused()
    assert entry.get_attribute("aria-describedby") is None
