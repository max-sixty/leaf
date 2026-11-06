"""Pointing reads; pressing acts: what a control, a mark or a value says before a press
acts on it, to a resting pointer, to the keyboard and to a held finger
(runtime/preview.js). The margin entry's preview, its label, is held in
`browser/margin/test_entries.py`."""

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, live_url, panel_comment
from render_cases_navigation import _publish
from render_harness import leaf_page, margins_laid_out, open_page, post_event, told

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
    beside it. The preview moves nothing, the pointer can cross onto it and read it
    there, and the next control the pointer reaches says its own at once. While it stands, Escape puts it away and does
    nothing else, so the thread it covers stays open; the next Escape leaves it."""
    url = serve(PANEL_PAGE)
    thread = panel_comment(serve.page_dir, "Could the mobile cohort wait a week?")
    page = open_page(request.getfixturevalue(engine), url)
    view = open_panel_thread(page, thread)
    resolve = page.locator(".lf-fp-thread-controls .lf-resolve")
    preview = page.locator(PREVIEW)
    expect(resolve).to_be_visible()
    # Off Leaf its word is the browser's tooltip; on Leaf it writes no title, so the
    # browser shows none beside the preview.
    assert resolve.get_attribute("title") is None, (
        "the browser's tooltip would show too"
    )
    rendered(page)
    before = page.evaluate(BOXES)

    resolve.hover()
    expect(preview).to_be_visible()
    expect(preview.locator(".lf-preview-word")).to_have_text("Resolve thread")
    expect(preview.locator("kbd.lf-key-badge")).to_have_text(["r"])
    # The chip's key is the one a screen reader hears it has.
    assert "r" in resolve.get_attribute("aria-keyshortcuts").split()
    rendered(page)
    assert page.evaluate(BOXES) == before, "showing the preview moved the thread"
    tip = preview.bounding_box()
    # The pointer onto the preview keeps it, and reads it there (WCAG 1.4.13).
    page.mouse.move(tip["x"] + tip["width"] / 2, tip["y"] + tip["height"] / 2)
    page.wait_for_timeout(400)
    expect(preview.locator(".lf-preview-word")).to_have_text("Resolve thread")

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
    through a scroll, and gone a dwell after the pointer leaves the range. An owner that makes the
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
          const leaving = tip.matches(':popover-open');
          await new Promise((done) => setTimeout(done, 400));
          return {text: tip.innerText, gap: box.top - line.bottom, left: box.left - line.left,
            carried, leaving, open: tip.matches(':popover-open')};
        }"""
    )
    assert reading["text"] == "Its thread"
    assert reading["gap"] > 0 and reading["left"] == 0, reading
    assert abs(reading["carried"] - reading["gap"]) < 1, "the scroll left it behind"
    # It waits a dwell, as the pointer may be on its way onto the preview.
    assert reading["leaving"], "the preview went before the pointer could reach it"
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
    # The user steps onto the entry themselves: Tab and back.
    page.keyboard.press("Shift")
    entry.focus()
    page.keyboard.press("Tab")
    page.keyboard.press("Shift+Tab")
    expect(entry).to_be_focused()
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
at <a id="to-meeting" href="#meeting">the settled meeting point</a>, and support
has <a id="to-support" href="#support">its own heading</a>.</p>
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
<h2 id="support">Support</h2>
<p id="support-playbook">The playbook covers the spinner.</p>
<h2 id="first-sibling">First section</h2><p>First words.</p>
<h2 id="second-sibling">Second section</h2><p>Second words.</p>
<p><a id="to-first" href="#first-sibling">first</a>,
<a id="to-second" href="#second-sibling">second</a></p>
"""
    + "<p>More of the page.</p>" * 30,
)


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_link_into_the_page_previews_where_it_points(engine, request, serve):
    """A link into the page previews the place it names: its heading and first lines
    as the page reads them, a question's answer from the reading the page holds, the
    pick of a question authored settled, and the conversations about it or anything in
    it, with whose turn one is: for a heading, about the part of the page it heads. It holds only words, so no id or control of the place is
    repeated. A resting pointer and the keyboard's focus read it, a press still follows
    the link, and a finger held on the link reads it and follows it on release: by touch
    in Chromium, and in Firefox, which takes no held touch from a test, by the pointer
    events a finger sends. A link to another site previews nothing."""
    url = serve(LINKS_PAGE)
    question = panel_comment(
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
    panel_comment(
        serve.page_dir, "Does it cover queued edits?", {"section": "support-playbook"}
    )
    panel_comment(
        serve.page_dir, "Is this the right title?", {"section": "second-sibling"}
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
    # Answering the question turns its thread to the agent: the standing preview says
    # so with the thread reading that says it.
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": question,
            "revision": 1,
            "text": "Hold it until then.",
        },
    )
    told(page)
    expect(preview.locator(".lf-place-foot")).to_have_text("2 threads")

    page.locator("#to-decision").hover()
    expect(name).to_have_text("Patch decision")
    expect(preview.locator(".lf-place-state")).to_have_text(
        "Answered: Ship with the resend."
    )
    page.locator("#to-support").hover()
    expect(name).to_have_text("Support")
    expect(preview.locator(".lf-place-text").first).to_have_text(
        "The playbook covers the spinner."
    )
    expect(preview.locator(".lf-place-foot")).to_have_text("1 thread")
    # A conversation about a heading is its own part's, not the part before it.
    page.locator("#to-second").hover()
    expect(name).to_have_text("Second section")
    expect(preview.locator(".lf-place-foot")).to_have_text("1 thread")
    page.locator("#to-first").hover()
    expect(name).to_have_text("First section")
    expect(preview.locator(".lf-place-foot")).to_have_count(0)

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


DRAWN_PAGE = leaf_page(
    "What a place draws",
    """
<p id="lede"><a id="to-closed" href="#closed">a closed disclosure</a>,
<a id="to-held" href="#held">a block holding one</a>,
<a id="to-spans" href="#spans">a paragraph with hidden words</a>,
<a id="to-titled" href="#titled">a section with a hidden word in its title</a>,
<a id="to-skipped" href="#skipped">a block skipping its rest</a>,
<a id="to-shown" href="#shown">words shown inside hidden ones</a>,
<a id="to-contents" href="#contents">a block that makes no box</a>,
<a id="to-untitled" href="#untitled">a section whose title is hidden</a>,
<a id="to-code" href="#code">code with hidden words and a control</a>,
<a id="to-broken" href="#broken">a line broken before hidden words</a>,
<a id="to-skipping" href="#skipping">a block skipping its own words</a>,
<a id="to-folded" href="#folded">a folded panel</a>,
<a id="to-far" href="#far">words out of view</a> and
<a id="to-joined" href="#joined">code joined over a hidden break</a>.</p>
<details id="closed"><summary>Method</summary>Secret text<p>Hidden paragraph.</p></details>
<div id="held">Intro <details><summary>More</summary><p>Hidden words.</p></details></div>
<p id="spans">Before <span style="display: none">Gone</span> <span hidden>Attr</span>
After<script type="application/json">{"secret": 1}</script></p>
<section id="titled"><h2>Public <span hidden>SECRET</span></h2><p>Body words.</p></section>
<div id="skipped"><p>Shown words.</p>
<div style="content-visibility: hidden"><p>Skipped words.</p></div></div>
<p id="shown">Plain <span style="visibility: hidden">masked
<b style="visibility: visible">Shown</b> masked</span> words.</p>
<div id="contents" style="display: contents"><p>Boxed <span style="display: none">Gone</span>
words.</p></div>
<section id="untitled"><h2 style="display: none">SECRET TITLE</h2><p>Visible body.</p>
</section>
<pre id="code">one <span style="display: none">HIDDEN</span>
two
three
four
five</pre>
<p id="broken">first<br><span hidden>HIDDEN</span>second</p>
<div id="skipping"><p>Shown words.</p><div style="content-visibility: hidden">SECRET
CV</div><div hidden="until-found">SECRET FOUND</div></div>
<section id="folded" hidden="until-found"><h3>Folded title</h3><p>Folded body.</p>
</section>
<pre id="joined"><code>con<br hidden>st value = 1;</code></pre>
"""
    + "<p>More of the page.</p>" * 40
    + """<div style="content-visibility: auto; contain-intrinsic-size: auto 40px">
<p id="far">Far <span style="visibility: hidden">SECRET VISIBILITY</span>
<span style="display: none">SECRET DISPLAY</span> words.</p></div>""",
)


LEAD_IN_PAGE = leaf_page(
    "Lead-ins",
    """
<h2>Outer</h2>
<p><a id="to-folded" href="#folded">folded words</a>,
<a id="to-kept" href="#kept">words after a kept newline</a> and
<a id="to-drawn" href="#drawn">words after a drawn title</a></p>
<details id="fold"><summary>Disclosure</summary><div><strong>Group</strong>
<span hidden>words</span><p id="folded">Folded words.</p></div></details>
<div style="white-space: pre-line"><strong>Kept</strong>
<span id="kept">Kept words.</span></div>
<p><strong><span id="drawn-title">Group</span></strong> runs on
<span id="drawn">Drawn words.</span></p>
<p id="elsewhere">Words elsewhere.</p>
""",
)


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_bold_lead_in_runs_on_by_its_markup_whatever_draws_it(engine, request, serve):
    """Whether a bold title runs into its line, and so makes no part, is a fact about
    the markup, so the name a card gives what follows it stands while the page draws it
    differently: with the disclosure around it closed or open and after an edit
    elsewhere, a title followed by words the page hides runs into them; a newline the
    whitespace keeps is no break; and a title whose words a widget's declared tree draws
    runs into the words after it."""
    page = open_page(request.getfixturevalue(engine), serve(LEAD_IN_PAGE))
    page.evaluate(
        """async () => {
          const {registry} = await import('/runtime/registry.js');
          const {shadowStage} = await import('/runtime/shadow-stage.js');
          registry['lf-staged-title'] = {'x-shadow': true};
          // The title's words move into a widget's declared tree, drawn where they stood.
          const words = document.getElementById('drawn-title');
          const host = document.createElement('lf-staged-title');
          words.replaceWith(host);
          shadowStage(host, [words]);
        }"""
    )
    preview = page.locator(PREVIEW)

    def named(link, name):
        page.mouse.move(0, 0)
        expect(preview).to_be_hidden()
        page.locator(link).hover()
        expect(preview.locator(".lf-preview-word")).to_have_text(name)

    named("#to-folded", "Disclosure")
    page.locator("#fold > summary").click()
    expect(page.locator("#folded")).to_be_visible()
    named("#to-folded", "Disclosure")
    page.evaluate(
        "() => { document.getElementById('elsewhere').firstChild.data = 'Other words.'; }"
    )
    named("#to-folded", "Disclosure")
    named("#to-kept", "Outer")
    named("#to-drawn", "Outer")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_link_s_preview_shows_only_what_the_page_draws(engine, request, serve):
    """A place's preview says what the page draws of it now, word by word as the
    browser computes it, in its name, its parts and its code alike: a closed disclosure
    its summary, words `display: none` or `hidden` and a script's text nothing, a title
    without its hidden word, a skipped subtree nothing, a word drawn inside a hidden
    one, a block with no box what it holds draws, a section whose title is hidden its
    body and not the title, code its lines without a hidden word or Leaf's control, a
    break before hidden words still a break, words a block's `content-visibility` skips
    nothing, a folded panel, which draws none of what it holds, all of it, and words a
    `content-visibility: auto` box skips out of view as they will draw: without what
    their own styles hide. Code cut short ends in an ellipsis, as cut prose does, and a
    hidden break joins the line it would have split."""
    page = open_page(request.getfixturevalue(engine), serve(DRAWN_PAGE))
    # Words Leaf writes into a block, as the paint pass writes a comment's count.
    page.evaluate(
        """() => {
          const words = document.createElement('span');
          words.className = 'lf-ui';
          words.textContent = 'COPY CONTROL';
          document.querySelector('#code > span').after(words);
        }"""
    )
    preview = page.locator(PREVIEW)
    parts = preview.locator(".lf-place")
    for link, name, said in (
        ("#to-closed", "Method", None),
        ("#to-held", None, "Intro More"),
        ("#to-spans", None, "Before After"),
        ("#to-titled", "Public", "Body words."),
        ("#to-skipped", None, "Shown words."),
        ("#to-shown", None, "Plain Shown words."),
        ("#to-contents", None, "Boxed words."),
        ("#to-untitled", None, "Visible body."),
        ("#to-code", None, "one two three four…"),
        ("#to-broken", None, "first second"),
        ("#to-skipping", None, "Shown words."),
        ("#to-folded", "Folded title", "Folded body."),
        ("#to-far", None, "Far words."),
        ("#to-joined", None, "const value = 1;"),
    ):
        page.mouse.move(0, 0)
        expect(preview).to_be_hidden()
        page.locator(link).hover()
        expect(preview).to_be_visible()
        if name:
            expect(preview.locator(".lf-preview-word")).to_have_text(name)
        if said:
            assert " ".join(parts.inner_text().split()) == said, link
        else:
            expect(parts).to_have_count(0)
        assert not {"SECRET", "HIDDEN", "CONTROL"} & set(preview.inner_text().split())


def test_a_message_s_parts_follow_its_accepted_edit(browser, serve):
    """A message's markup is outlined as the page is, and an edit the log accepts
    outlines it again: the paragraph after a heading the edit changed stands under the
    new heading."""
    url = serve(PANEL_PAGE)
    thread = panel_comment(
        serve.page_dir, "## Original heading\n\nWords after the heading."
    )
    page = open_page(browser, url)
    view = open_panel_thread(page, thread)
    part = """async () => {
      const {partOver} = await import('/runtime/thread/placement.js');
      const words = [...document.querySelectorAll('.lf-msg-body p')]
        .find((p) => p.textContent.includes('Words after the heading'));
      return partOver(words)?.textContent.trim() ?? null;
    }"""
    expect(view.locator("h2")).to_have_text("Original heading")
    assert page.evaluate(part) == "Original heading"
    view.locator(".lf-msg-text").dblclick()
    expect(view.locator(".lf-msg-editor leaf-text")).to_be_focused()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("### Changed heading")
    page.keyboard.press("Shift+Enter")
    page.keyboard.press("Shift+Enter")
    page.keyboard.type("Words after the heading.")
    page.keyboard.press("Enter")
    expect(view.locator(".lf-msg-editor")).to_have_count(0)
    expect(view.locator(".lf-edited")).to_have_text("edited")
    told(page)
    expect(view.locator("h3")).to_have_text("Changed heading")
    assert page.evaluate(part) == "Changed heading"


SECTION_PAGE = leaf_page(
    "A thread on a section",
    """
<h2>Link previews</h2>
<p><a id="to-stall" href="#stall">the reconnect stall</a></p>
<section id="stall"><h3>iOS reconnect stall</h3>
<p>One reconnect in about 40 stalls until the app is backgrounded.</p></section>
"""
    + "<p>More of the page.</p>" * 20,
)


def test_a_thread_on_a_whole_section_stands_where_the_section_stands(browser, serve):
    """A link to a section previews it by its own name, and On me groups a thread on
    the whole section under the part the section stands in: the preview says what a
    place is, On me where it is."""
    url = serve(SECTION_PAGE)
    panel_comment(
        serve.page_dir,
        "Should this wait for the vendor's release?",
        {"section": "stall"},
        author="agent",
        obligation=True,
    )
    page = open_page(browser, url)
    page.locator("#to-stall").hover()
    expect(page.locator(PREVIEW).locator(".lf-preview-name")).to_have_text(
        "iOS reconnect stall"
    )
    page.mouse.move(1, 1)
    page.evaluate("() => window.lfStorage.userStore.set('lf-on-me-grouping', 'place')")
    page.locator(".lf-fp-on-user").click()
    band = page.locator(".lf-rows-group").filter(
        has_text="Should this wait for the vendor's release?"
    )
    expect(band.locator(".lf-row-main")).to_have_text("Link previews")


def test_a_message_s_parts_follow_an_edit_the_card_held_as_news(browser, serve):
    """An edit arriving while a card holds the message back as news outlines the
    message once the card shows it, not before: the old words stand under their old
    heading while held, and the new under the new once shown, which names them."""
    url = serve(LINKS_PAGE)
    thread = panel_comment(
        serve.page_dir,
        "## Original heading\n\nOriginal paragraph.",
        {"section": "stall"},
    )
    page = open_page(browser, url)
    page.locator('[data-lf-margin-for="stall"] .lf-margin-marker').click()
    card = page.locator(".lf-margin-preview")
    expect(card.locator(".lf-msg-body")).to_contain_text("Original paragraph.")
    part = """async (words) => {
      const {partOver} = await import('/runtime/thread/placement.js');
      const said = [...document.querySelectorAll('.lf-margin-preview .lf-msg-body p')]
        .find((p) => p.textContent.includes(words));
      const over = partOver(said);
      return over?.isConnected ? over.textContent.trim() : null;
    }"""
    assert page.evaluate(part, "Original paragraph.") == "Original heading"
    post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "edit",
            "message": thread,
            "base": thread,
            "text": "### Changed heading\n\nChanged paragraph.",
        },
    )
    told(page)
    news = card.locator(".lf-thread-news")
    expect(news).to_be_visible()
    assert page.evaluate(part, "Original paragraph.") == "Original heading"
    news.click()
    expect(card.locator(".lf-msg-body")).to_contain_text("Changed paragraph.")
    assert page.evaluate(part, "Changed paragraph.") == "Changed heading"
    # A place in the message's text is named as the message reads: by its heading.
    named = page.evaluate(
        """async () => {
          const {placePreview} = await import('/runtime/place-preview.js');
          const said = [...document.querySelectorAll('.lf-margin-preview .lf-msg-body p')]
            .find((p) => p.textContent.includes('Changed paragraph.'));
          return placePreview(said)?.name ?? null;
        }"""
    )
    assert named == "Changed heading"


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_standing_preview_redraws_in_place_when_its_element_says_it_changed(
    engine, request, serve
):
    """An element whose aim moves inside it, as a chart's point does, says its preview
    changed (`previewChanged`): the preview standing for it reads the element again and
    draws the new words where it stands, still open, for a resting pointer and for the
    keyboard's focus."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Points",
                '<p><span id="value" tabindex="0">A value</span></p>'
                + "<p>More.</p>" * 5,
            )
        ),
    )
    page.evaluate(
        """() => {
          window.lfPoint = 1;
          document.getElementById('value').lfPreview = () =>
            ({name: `Point ${window.lfPoint}`});
        }"""
    )
    value = page.locator("#value")
    tip = page.locator(PREVIEW)
    moved = """async () => {
      const {previewChanged} = await window.__lfWidgetApi();
      window.lfPoint += 1;
      previewChanged(document.getElementById('value'));
    }"""

    page.mouse.move(2, 2)
    value.hover()
    expect(tip.locator(".lf-preview-word")).to_have_text("Point 1")
    page.evaluate(moved)
    expect(tip.locator(".lf-preview-word")).to_have_text("Point 2")
    rendered(page)
    expect(tip).to_be_visible()

    page.mouse.move(2, 2)
    expect(tip).to_be_hidden()
    page.keyboard.press("Shift")
    value.focus()
    page.keyboard.press("Tab")
    page.keyboard.press("Shift+Tab")
    expect(tip.locator(".lf-preview-word")).to_have_text("Point 2")
    page.evaluate(moved)
    expect(tip.locator(".lf-preview-word")).to_have_text("Point 3")
    rendered(page)
    expect(tip).to_be_visible()


def test_a_standing_preview_reads_its_element_again_as_the_page_presents_news(
    browser, serve
):
    """A preview standing when the page presents a new state reads its element again,
    so it says what holds now without its declaration tracking what it reads, as a
    link's place or a thread's turn changes under it, and stays open where it stands."""
    url = serve(PANEL_PAGE)
    page = open_page(browser, url)
    page.evaluate(
        """() => {
          window.lfWords = 'Before the news';
          document.querySelector('#lede').lfPreview = () => ({name: window.lfWords});
        }"""
    )
    lede = page.locator("#lede")
    tip = page.locator(PREVIEW)
    page.mouse.move(2, 2)
    lede.hover()
    expect(tip.locator(".lf-preview-word")).to_have_text("Before the news")
    page.evaluate("() => { window.lfWords = 'After the news'; }")
    panel_comment(serve.page_dir, "News the page presents.")
    told(page)
    expect(tip.locator(".lf-preview-word")).to_have_text("After the news")
    expect(tip).to_be_visible()


def test_a_standing_range_preview_says_its_owners_latest_words(browser, serve):
    """A range's preview standing while what its owner says about it changes, as a
    thread turning to the user's under its passage, says the new words with no pointer
    input: on the page's next presentation, and when the owner declares the same range
    again with other words."""
    url = serve(PANEL_PAGE)
    page = open_page(browser, url)
    tip = page.locator(PREVIEW)
    page.evaluate(
        """async () => {
          const {pointRange} = await window.__lfCheckApi();
          const text = document.getElementById('lede').firstChild;
          const range = document.createRange();
          range.setStart(text, 0);
          range.setEnd(text, 8);
          const line = range.getClientRects()[0];
          window.lfWords = '2 messages';
          window.lfRange = range;
          window.lfAt = {x: line.left + 2, y: line.top + line.height / 2};
          pointRange(range, () => ({name: window.lfWords}), window.lfAt);
        }"""
    )
    expect(tip.locator(".lf-preview-word")).to_have_text("2 messages")

    page.evaluate("() => { window.lfWords = '3 messages · your turn'; }")
    panel_comment(serve.page_dir, "News the page presents.")
    told(page)
    expect(tip.locator(".lf-preview-word")).to_have_text("3 messages · your turn")

    page.evaluate(
        """async () => {
          const {pointRange} = await window.__lfCheckApi();
          pointRange(window.lfRange.cloneRange(), () => ({name: 'Resolved'}), window.lfAt);
        }"""
    )
    expect(tip.locator(".lf-preview-word")).to_have_text("Resolved")
    expect(tip).to_be_visible()


def test_a_standing_preview_says_what_a_new_revision_changed(browser, serve):
    """A preview standing over a link while a new revision changes the place it points
    at says the place's new words, with no pointer input: a revision ends in a
    presentation, which reads every standing preview again."""

    def page_with(words):
        return leaf_page(
            "Revisions",
            '<p><span id="go" tabindex="0">The table below</span></p>'
            f'<p id="dest">{words}</p>' + "<p>More.</p>" * 4,
        )

    url = serve(page_with("The first words"))
    page = open_page(browser, live_url(url))
    page.evaluate(
        """() => {
          document.getElementById('go').lfPreview = () =>
            ({name: document.getElementById('dest').textContent});
        }"""
    )
    tip = page.locator(PREVIEW)
    page.mouse.move(2, 2)
    page.locator("#go").hover()
    expect(tip.locator(".lf-preview-word")).to_have_text("The first words")
    _publish(serve.page_dir, 2, page_with("The revised words"), "two")
    told(page)
    expect(page.locator("#dest")).to_have_text("The revised words")
    expect(tip.locator(".lf-preview-word")).to_have_text("The revised words")
    expect(tip).to_be_visible()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_the_innermost_target_previews_on_every_route(engine, request, serve):
    """A link inside a passage a range's owner previews, as a link in a commented
    paragraph, previews as the link: to a resting pointer, though the passage's owner
    reports its range under the pointer after the link's boundary, as to the keyboard
    and a finger. The passage's words around the link still preview as the passage."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Innermost",
                '<p id="passage">The words a thread is about, with '
                '<a id="go" href="#more">a link</a> among them, and more words after '
                "the link so the passage runs on.</p>"
                + '<p id="more">More.</p>'
                + "<p>More words.</p>" * 3,
            )
        ),
    )
    page.evaluate(
        """async () => {
          const {pointRange} = await window.__lfCheckApi();
          const passage = document.getElementById('passage');
          document.getElementById('go').lfPreview = () => ({name: 'The link'});
          const range = document.createRange();
          range.selectNodeContents(passage);
          passage.addEventListener('pointermove', (event) =>
            pointRange(range.cloneRange(), () => ({name: 'The thread'}),
              {x: event.clientX, y: event.clientY}));
          passage.addEventListener('pointerleave', () => pointRange(null));
        }"""
    )
    tip = page.locator(PREVIEW)
    word = tip.locator(".lf-preview-word")
    page.mouse.move(2, 2)
    box = page.locator("#passage").bounding_box()
    page.mouse.move(box["x"] + 20, box["y"] + 8, steps=4)
    expect(word).to_have_text("The thread")
    page.mouse.move(2, 2)
    expect(tip).to_be_hidden()
    link = page.locator("#go").bounding_box()
    page.mouse.move(link["x"] + 4, link["y"] + link["height"] / 2, steps=4)
    page.mouse.move(link["x"] + 8, link["y"] + link["height"] / 2, steps=2)
    expect(word).to_have_text("The link")


# How many times the margin lays out (`lf-margin-layout`) and which of the page's boxes
# are written from now until `window.lfHeard()` is awaited, two frames on: a style or
# class written on a page box is what brings a pass (margin-layout.js, `heardPage`). The
# preview's own boxes are not the page's.
HEARD = """() => {
  const stage = document.getElementById('lf-preview').parentElement;
  const heard = {marginPasses: 0, written: new Set()};
  const passed = () => { heard.marginPasses += 1; };
  document.addEventListener('lf-margin-layout', passed);
  const watch = new MutationObserver((records) => {
    for (const record of records)
      if (!stage.contains(record.target))
        heard.written.add(record.target.id || record.target.localName);
  });
  watch.observe(document.documentElement,
    {subtree: true, attributes: true, attributeFilter: ['style', 'class']});
  window.lfHeard = async () => {
    await new Promise(requestAnimationFrame);
    await new Promise(requestAnimationFrame);
    watch.disconnect();
    document.removeEventListener('lf-margin-layout', passed);
    return {marginPasses: heard.marginPasses, written: [...heard.written]};
  };
}"""


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_preview_writes_nothing_on_the_page(engine, request, serve):
    """A preview shows with its target as its source and the browser places it, so it
    writes nothing on the page's boxes, its root or a box that scrolls its target,
    which the margin would hear as a change and lay out again: the session's first
    preview, a range's on a paragraph, and the first inside an authored scroller. The
    pointer comes from words beside each target, so its travel reads nothing either."""
    url = serve(
        leaf_page(
            "Quiet previews",
            '<p id="lede">A paragraph a thread is about.</p>'
            '<div id="box" style="height: 80px; overflow: auto">'
            '<p><span id="calm">Calm words</span> '
            '<button id="inner" aria-label="A control in a scroller">⚙</button></p>'
            '<p style="height: 200px">More.</p></div>',
        )
    )
    panel_comment(serve.page_dir, "About the lede.", {"section": "lede"})
    page = open_page(request.getfixturevalue(engine), url)
    expect(
        page.locator('[data-lf-margin-for="lede"] .lf-margin-marker')
    ).to_be_visible()
    tip = page.locator(PREVIEW)
    margins_laid_out(page)
    rendered(page)
    page.evaluate(HEARD)
    page.evaluate(
        """async () => {
          const {pointRange} = await window.__lfCheckApi();
          const range = document.createRange();
          range.selectNodeContents(document.getElementById('lede'));
          const line = range.getClientRects()[0];
          pointRange(range, () => ({name: 'Its thread'}),
            {x: line.left + 2, y: line.top + 4});
        }"""
    )
    expect(tip.locator(".lf-preview-word")).to_have_text("Its thread")
    assert page.evaluate("window.lfHeard()") == {"marginPasses": 0, "written": []}
    page.evaluate("async () => (await window.__lfCheckApi()).pointRange(null)")
    expect(tip).to_be_hidden()

    page.locator("#calm").hover()
    margins_laid_out(page)
    rendered(page)
    page.evaluate(HEARD)
    page.locator("#inner").hover()
    expect(tip.locator(".lf-preview-word")).to_have_text("A control in a scroller")
    assert page.evaluate("window.lfHeard()") == {"marginPasses": 0, "written": []}


GRID = """<div id="grid" style="display: grid; grid-template-columns: repeat(2, max-content);
  gap: 4px"><button id="g-a" aria-label="Alpha control">A</button><button id="g-b"
  aria-label="Bravo control">B</button><button id="g-c" aria-label="Charlie control">C
  </button><button id="g-d" aria-label="Delta control">D</button></div>
<dialog id="dialog"><p>In the dialog.</p>
  <button id="in-dialog" aria-label="A control in the dialog">⚙</button></dialog>"""
# Where the preview stands, and which of `ids` it covers.
COVERS = """(ids) => {
  const tip = document.getElementById('lf-preview').getBoundingClientRect();
  return ids.filter((id) => {
    const box = document.getElementById(id).getBoundingClientRect();
    return box.left < tip.right && tip.left < box.right && box.top < tip.bottom
      && tip.top < box.bottom;
  });
}"""


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_preview_covers_no_neighbour_and_takes_the_pointer_in_a_modal(
    engine, request, serve
):
    """In a grid of controls a preview stands where it covers none of the neighbours,
    so the pointer reaches the one below and reads that one's preview, and inside a
    modal dialog the preview stands in the dialog, so the pointer can cross onto it and
    read it there, where outside it the dialog would make it inert."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(leaf_page("Neighbours", "<p>Words above the grid.</p>" * 6 + GRID)),
    )
    tip = page.locator(PREVIEW)
    word = tip.locator(".lf-preview-word")
    page.mouse.move(2, 2)
    page.locator("#g-a").hover()
    expect(word).to_have_text("Alpha control")
    assert page.evaluate(COVERS, ["g-b", "g-c", "g-d"]) == []
    below = page.locator("#g-c").bounding_box()
    page.mouse.move(
        below["x"] + below["width"] / 2, below["y"] + below["height"] / 2, steps=6
    )
    expect(word).to_have_text("Charlie control")

    page.mouse.move(2, 2)
    page.evaluate("() => document.getElementById('dialog').showModal()")
    page.locator("#in-dialog").hover()
    expect(word).to_have_text("A control in the dialog")
    box = tip.bounding_box()
    middle = [box["x"] + box["width"] / 2, box["y"] + box["height"] / 2]
    page.mouse.move(*middle, steps=4)
    page.wait_for_timeout(400)
    expect(word).to_have_text("A control in the dialog")
    assert page.evaluate(
        "([x, y]) => Boolean(document.elementFromPoint(x, y)?.closest('#lf-preview'))",
        middle,
    ), "the dialog left the preview inert"


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_preview_put_away_stays_away_until_the_user_aims_again(
    engine, request, serve
):
    """Escape puts a focus preview away, and an element declaring its preview again,
    as a chart redrawing with the same point does, brings nothing back; nor does a
    grip whose words come back once its card is put down. The element hears that its
    preview ended (`PREVIEW_ENDED`). Focus a script moves while a key is down shows
    nothing, and the user stepping back with the keyboard shows it again."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Put away",
                '<p><button id="before">Before</button> '
                '<span id="chart" tabindex="0">A chart</span> '
                '<span id="grip" tabindex="0">A grip</span></p>',
            )
        ),
    )
    page.evaluate(
        """() => {
          window.lf = {point: 1, held: false, ended: 0};
          const chart = document.getElementById('chart');
          chart.lfPreview = () => ({name: `Point ${window.lf.point}`});
          chart.addEventListener('lf-preview-ended', () => { window.lf.ended += 1; });
          document.getElementById('grip').lfPreview = () =>
            !window.lf.held && {name: 'Drag to move'};
        }"""
    )
    changed = """async (id) => {
      const {previewChanged} = await window.__lfWidgetApi();
      previewChanged(document.getElementById(id));
    }"""
    tip = page.locator(PREVIEW)
    page.locator("#before").focus()
    page.keyboard.press("Tab")
    expect(tip).to_have_text("Point 1")
    page.keyboard.press("Escape")
    expect(tip).to_be_hidden()
    assert page.evaluate("window.lf.ended") == 1
    page.evaluate("() => { window.lf.point = 2; }")
    page.evaluate(changed, "chart")
    page.wait_for_timeout(300)
    expect(tip).to_be_hidden()

    page.keyboard.press("Tab")
    expect(tip).to_have_text("Drag to move")
    page.evaluate("() => { window.lf.held = true; }")
    page.evaluate(changed, "grip")
    expect(tip).to_be_hidden()
    page.evaluate("() => { window.lf.held = false; }")
    page.evaluate(changed, "grip")
    page.wait_for_timeout(300)
    expect(tip).to_be_hidden()

    page.keyboard.down("Shift")
    page.evaluate("() => document.getElementById('chart').focus()")
    page.keyboard.up("Shift")
    page.wait_for_timeout(300)
    expect(tip).to_be_hidden()
    page.keyboard.press("Tab")
    page.keyboard.press("Shift+Tab")
    expect(tip).to_have_text("Point 2")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_title_stays_its_writers(engine, request, serve):
    """A title is its writer's: a pointer over it reads the browser's tooltip and no
    preview, focus reads its words in the preview, and nothing takes the attribute
    off, so a title removed leaves no words behind and a control it names keeps its
    name."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Titles",
                '<p><button id="before">Before</button> '
                '<span id="titled" tabindex="0" title="The author\'s words">Words</span> '
                '<button id="named" title="Named by its title">'
                '<span aria-hidden="true">⚙</span></button></p>',
            )
        ),
    )
    tip = page.locator(PREVIEW)
    titled = page.locator("#titled")
    page.mouse.move(2, 2)
    titled.hover()
    page.wait_for_timeout(500)
    expect(tip).to_be_hidden()
    expect(titled).to_have_attribute("title", "The author's words")
    page.mouse.move(2, 2)
    page.locator("#before").focus()
    page.keyboard.press("Tab")
    expect(tip).to_have_text("The author's words")
    page.keyboard.press("Tab")
    expect(page.get_by_role("button", name="Named by its title")).to_be_focused()
    expect(tip).to_have_text("Named by its title")

    page.evaluate("() => document.activeElement.blur()")
    expect(tip).to_be_hidden()
    page.evaluate("() => document.getElementById('titled').removeAttribute('title')")
    titled.hover()
    page.wait_for_timeout(500)
    expect(tip).to_be_hidden()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_preview_stands_by_its_target_as_the_page_moves(engine, request, serve):
    """The browser stands a preview by its target: through a scroll inside the page
    and a resize of the window, from a right-to-left target's right edge, and, taller
    than the room on either side once the window shrinks, held to the room below with
    its face scrolling."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Standing",
                '<p><button id="before">Before</button></p>'
                '<div id="box" tabindex="-1" style="height: 120px; width: 320px; overflow: auto">'
                '<p style="padding-top: 40px"><span id="inner" tabindex="0">Inner</span>'
                '</p><p style="height: 400px">More.</p></div>'
                '<p dir="rtl" style="margin-inline-start: 200px">מילים עם '
                '<span id="rtl" tabindex="0">קישור</span> ועוד מילים</p>',
            )
        ),
    )
    page.evaluate(
        """() => {
          document.getElementById('inner').lfPreview = () => ({name: 'Inner value'});
          document.getElementById('rtl').lfPreview = () => ({name: 'A name in full'});
        }"""
    )
    tip = page.locator(PREVIEW)
    beside = """(id) => {
      const tip = document.getElementById('lf-preview').getBoundingClientRect();
      const at = document.getElementById(id).getBoundingClientRect();
      return {start: Math.round(tip.left - at.left), end: Math.round(at.right - tip.right),
        gap: Math.round(tip.top - at.bottom), top: Math.round(tip.top),
        bottom: Math.round(tip.bottom), window: innerHeight,
        scrolls: document.getElementById('lf-preview').scrollHeight
          > document.getElementById('lf-preview').clientHeight + 1};
    }"""
    page.locator("#before").focus()
    page.keyboard.press("Tab")
    expect(tip).to_have_text("Inner value")
    shown = page.evaluate(beside, "inner")
    page.evaluate("() => { document.getElementById('box').scrollTop = 25; }")
    page.wait_for_timeout(200)
    assert page.evaluate(beside, "inner")["gap"] == shown["gap"], "the scroll left it"
    size = page.viewport_size
    page.set_viewport_size({"width": size["width"] - 200, "height": size["height"]})
    page.wait_for_timeout(300)
    resized = page.evaluate(beside, "inner")
    assert (resized["start"], resized["gap"]) == (shown["start"], shown["gap"])
    page.set_viewport_size(size)

    rtl = page.locator("#rtl")
    rtl.focus()
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    expect(tip).to_have_text("A name in full")
    assert page.evaluate(beside, "rtl")["end"] == 0, "it starts at the left edge"

    page.evaluate(
        """() => { document.getElementById('inner').lfPreview = () => ({name: 'Many',
          detail: Array.from({length: 30}, (_, i) => `Line ${i + 1} of its detail`)}); }"""
    )
    page.evaluate("() => document.getElementById('box').scrollTop = 0")
    page.locator("#before").focus()
    page.keyboard.press("Tab")
    expect(tip.locator(".lf-preview-word")).to_have_text("Many")
    page.set_viewport_size({"width": size["width"], "height": 260})
    page.wait_for_timeout(400)
    held = page.evaluate(beside, "inner")
    assert held["top"] >= 0 and held["bottom"] <= held["window"], held
    assert held["scrolls"], held


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_list_preview_shows_what_its_room_holds_and_counts_the_rest(
    engine, request, serve
):
    """A preview's list longer than the room its face is held to shows the items that
    fit and, under them, its declaration's words for how many more there are, the
    rest hidden from sight and from a screen reader; the window growing shows them
    all again, with no count."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Lists",
                '<p><button id="before">Before</button> '
                '<span id="place" tabindex="0">Threads here</span></p>',
            )
        ),
    )
    page.evaluate(
        """() => { document.getElementById('place').lfPreview = () => ({
          name: '30 threads',
          list: {items: Array.from({length: 30}, (_, i) => `Thread ${i + 1}`),
            more: (count) => `and ${count} more threads`}}); }"""
    )
    tip = page.locator(PREVIEW)
    read = """() => {
      const tip = document.getElementById('lf-preview');
      const more = tip.querySelector('.lf-preview-more');
      const items = [...tip.querySelectorAll('.lf-preview-item')];
      const box = tip.getBoundingClientRect();
      const counted = getComputedStyle(more).visibility === 'visible';
      const end = counted ? more.getBoundingClientRect().top : box.bottom;
      return {seen: items.filter((item) => getComputedStyle(item).visibility === 'visible'
          && item.getBoundingClientRect().bottom <= end + 1).length,
        hidden: items.filter((item) => getComputedStyle(item).visibility === 'hidden')
          .length,
        more: counted ? more.textContent : null, inside: box.bottom <= innerHeight};
    }"""
    size = page.viewport_size
    page.set_viewport_size({"width": size["width"], "height": 260})
    page.locator("#before").focus()
    page.keyboard.press("Tab")
    expect(tip.locator(".lf-preview-word")).to_have_text("30 threads")
    short = page.evaluate(read)
    assert 0 < short["seen"] < 30 and short["seen"] + short["hidden"] == 30, short
    assert short["more"] == f"and {short['hidden']} more threads", short
    assert short["inside"], short
    page.set_viewport_size({"width": size["width"], "height": 1400})
    page.wait_for_timeout(400)
    tall = page.evaluate(read)
    assert tall["hidden"] == 0 and tall["more"] is None, tall
