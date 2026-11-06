"""Pointing reads; pressing acts: what a control, a mark or a value says before a press
acts on it, to a resting pointer, to the keyboard and to a held finger
(runtime/preview.js). The margin entry's preview, its label, is held in
`browser/margin/test_entries.py`."""

import pytest
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, panel_comment
from render_harness import leaf_page, open_page

from browser.threads import open_panel_thread
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


LINKS_PAGE = leaf_page(
    "Links into the page",
    """
<p id="lede">The patch decision is <a id="to-decision" href="#decision">below</a>,
after <a id="to-stall" href="#stall">the reconnect stall</a>; the vendor's notes are
<a id="to-site" href="https://example.com/notes">on their site</a>; the group meets
at <a id="to-meeting" href="#meeting">the settled meeting point</a>.</p>
<section id="stall"><p class="eyebrow">offline editing</p><h2>iOS reconnect stall</h2>
<p id="stall-detail">One reconnect in about 40 stalls until the app is backgrounded.</p>
</section>
<lf-ask id="decision"><h3>Patch decision</h3>
<lf-options id="decision-options" choose>
  <lf-option id="decision-ship" chosen>Ship with the resend.</lf-option>
  <lf-option id="decision-hold">Hold the patch.</lf-option>
</lf-options></lf-ask>
<lf-ask id="meeting"><h3>Where should the group meet?</h3>
<lf-options id="meeting-options" choose settled>
  <lf-option id="meeting-door">At the door</lf-option>
  <lf-option id="meeting-desk" chosen>At reception</lf-option>
</lf-options></lf-ask>
"""
    + "<p>More of the page.</p>" * 30,
)


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_link_into_the_page_previews_where_it_points(engine, request, serve):
    """A link into the page previews the place it names: its heading and first lines
    as the page reads them, a question's answer from the reading the page holds, the
    pick of a question authored settled, and the conversations about it or anything in
    it, with whose turn one is. It holds only words, so no id or control of the place is
    repeated. A resting pointer and the keyboard's focus read it, a press still follows
    the link, and a finger held on the link reads it and follows it on release: by touch
    in Chromium, and in Firefox, which takes no held touch from a test, by the pointer
    events a finger sends. A link to another site previews nothing."""
    url = serve(LINKS_PAGE)
    panel_comment(
        serve.page_dir,
        "Should this wait for the vendor's release?",
        {"section": "stall"},
        author="agent",
        obligation=True,
    )
    panel_comment(
        serve.page_dir,
        "Does backgrounding always clear it?",
        {"section": "stall-detail"},
    )
    browser = request.getfixturevalue(engine)
    page = open_page(browser, url)
    preview = page.locator(PREVIEW)
    name = preview.locator(".lf-preview-name")

    page.locator("#to-stall").hover()
    expect(name).to_have_text("iOS reconnect stall")
    expect(preview).to_have_attribute("data-lf-face", "excerpt")
    expect(preview.locator(".lf-place-text")).to_have_text(
        "One reconnect in about 40 stalls until the app is backgrounded."
    )
    expect(preview).not_to_contain_text("offline editing")
    expect(preview.locator(".lf-place-foot")).to_have_text("2 threadsYour turn")
    assert (
        preview.locator("[id], a, button, input, [tabindex], lf-options").count() == 0
    )

    page.locator("#to-decision").hover()
    expect(name).to_have_text("Patch decision")
    expect(preview.locator(".lf-place-state")).to_have_text(
        "Answered: Ship with the resend."
    )
    page.locator("#to-meeting").hover()
    expect(name).to_have_text("Where should the group meet?")
    expect(preview.locator(".lf-place-item[data-lf-chosen]")).to_have_text(
        "At reception"
    )
    expect(preview.locator(".lf-place-item:not([data-lf-chosen])")).to_have_text(
        "At the door"
    )
    page.locator("#to-site").hover()
    expect(preview).to_be_hidden()

    # The keyboard's focus reads it at once, and Enter follows the link.
    page.locator("#to-site").focus()
    page.keyboard.press("Shift+Tab")
    expect(page.locator("#to-stall")).to_be_focused()
    expect(name).to_have_text("iOS reconnect stall")
    page.keyboard.press("Enter")
    expect(preview).to_be_hidden()
    page.wait_for_function("location.hash === '#stall'")

    # A held finger reads the preview, and letting go follows the link.
    chromium = engine == "browser"
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=chromium
    )
    phone = open_page(browser, url, context=context)
    box = phone.locator("#to-decision").bounding_box()
    point = {"x": box["x"] + box["width"] / 2, "y": box["y"] + box["height"] / 2}
    cdp = context.new_cdp_session(phone) if chromium else None
    finger = """([type, x, y]) => document.elementFromPoint(x, y).dispatchEvent(
      new PointerEvent(type, {pointerId: 7, pointerType: 'touch', isPrimary: true,
        bubbles: true, cancelable: true, composed: true, button: 0,
        buttons: type === 'pointerup' ? 0 : 1, clientX: x, clientY: y}))"""
    if cdp:
        cdp.send(
            "Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [point]}
        )
    else:
        phone.evaluate(finger, ["pointerdown", point["x"], point["y"]])
    held = phone.locator(PREVIEW)
    expect(held.locator(".lf-preview-name")).to_have_text("Patch decision")
    if cdp:
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    else:
        phone.evaluate(finger, ["pointerup", point["x"], point["y"]])
    expect(held).to_be_hidden()
    phone.wait_for_function("location.hash === '#decision'")
