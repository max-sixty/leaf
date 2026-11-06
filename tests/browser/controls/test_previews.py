"""Pointing reads; pressing acts: what a control, a mark or a value says before a press
acts on it, to a resting pointer, to the keyboard and to a held finger
(runtime/preview.js). The margin entry's preview, its label, is held in
`browser/margin/test_entries.py`."""

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, live_url, panel_comment
from render_cases_navigation import _publish
from render_harness import (
    leaf_page,
    long_press,
    margins_laid_out,
    open_page,
    post_event,
    told,
)

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
    repeated. A resting pointer and the keyboard's focus read it, and a press still
    follows the link. A finger held on the link reads it at the platform's long press,
    and letting go presses nothing: the card stands until a tap follows the link. By
    touch in Chromium, and in Firefox, which takes no held touch from a test, by the
    pointer events a finger sends. A link to another site previews nothing."""
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

    # A held finger reads the preview, letting go presses nothing, and a tap follows.
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

    def touch(start):
        if cdp:
            cdp.send(
                "Input.dispatchTouchEvent",
                {
                    "type": "touchStart" if start else "touchEnd",
                    "touchPoints": [point] if start else [],
                },
            )
        else:
            kind = "pointerdown" if start else "pointerup"
            phone.evaluate(finger, [kind, point["x"], point["y"]])

    touch(True)
    assert long_press(phone, point) is False, "the platform's menu opened"
    held = phone.locator(PREVIEW)
    expect(held.locator(".lf-preview-name")).to_have_text("Patch decision")
    touch(False)
    rendered(phone)
    assert phone.evaluate("location.hash") == "", "the held link was followed"
    expect(held).to_be_visible()
    if cdp:
        touch(True)
        touch(False)
    else:
        phone.locator("#to-decision").click()
    phone.wait_for_function("location.hash === '#decision'")
    expect(held).to_be_hidden()


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
<a id="to-kept" href="#kept">words after a kept newline</a>,
<a id="to-drawn" href="#drawn">words after a drawn title</a>,
<a id="to-slotted" href="#slotted">words after a slotted title</a> and
<a id="to-tallied" href="#tallied">words after a tally</a></p>
<details id="fold"><summary>Disclosure</summary><div><strong>Group</strong>
<span hidden>words</span><p id="folded">Folded words.</p></div></details>
<div style="white-space: pre-line"><strong>Kept</strong>
<span id="kept">Kept words.</span></div>
<p><strong><span id="drawn-title">Group</span></strong> runs on
<span id="drawn">Drawn words.</span></p>
<p><span id="slot-words"><strong>Slotted</strong> continues
<span id="slotted">Slotted words.</span></span></p>
<p><strong>Tallied</strong><lf-tally id="lead-tally" for="fold"></lf-tally> after
<span id="tallied">Tallied words.</span></p>
<p id="elsewhere">Words elsewhere.</p>
""",
)


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_bold_lead_in_runs_on_by_its_markup_whatever_draws_it(engine, request, serve):
    """Whether a bold title runs into its line, and so makes no part, is a fact about
    the markup, so the name a card gives what follows it stands while the page draws it
    differently: with the disclosure around it closed or open and after an edit
    elsewhere, a title followed by words the page hides runs into them; a newline the
    whitespace keeps is no break; a title whose words a widget's declared tree draws
    runs into the words after it, as one a declared tree's slot draws does; and a widget
    set among the words, whose tree holds Leaf's own apparatus, is no break either."""
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
          // A title and its words assigned to a slot inside a declared tree's span.
          registry['lf-slot-host'] = {'x-shadow': true};
          const held = document.getElementById('slot-words');
          const slotHost = document.createElement('lf-slot-host');
          held.replaceWith(slotHost);
          const line = document.createElement('span');
          line.append(document.createElement('slot'));
          shadowStage(slotHost, [line]);
          slotHost.append(...held.childNodes);
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
    named("#to-slotted", "Outer")
    named("#to-tallied", "Outer")


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
    preview, inside an authored scroller. The pointer comes from words beside the
    target, so its travel reads nothing either."""
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
# Two boxes at one edge can report a hair apart (Firefox reports layout's sixtieths of a
# pixel through float32), so an overlap thinner than half a layout unit is none.
COVERS = """(ids) => {
  const tip = document.getElementById('lf-preview').getBoundingClientRect();
  const over = (a, b) => b - a > 1 / 128;
  return ids.filter((id) => {
    const box = document.getElementById(id).getBoundingClientRect();
    return over(box.left, tip.right) && over(tip.left, box.right)
      && over(box.top, tip.bottom) && over(tip.top, box.bottom);
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
    preview ended (`PREVIEW_ENDED`). A widget placing focus as a move after a
    microtask shows it, since the cause is the placement's, and the user stepping
    back with the keyboard shows it again."""
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
    # A new point aimed at inside it is a new target, which shows again.
    page.evaluate(
        """async () => {
          const {previewChanged} = await window.__lfWidgetApi();
          window.lf.point = 3;
          previewChanged(document.getElementById('chart'), {aim: true});
        }"""
    )
    expect(tip).to_have_text("Point 3")
    page.keyboard.press("Escape")
    expect(tip).to_be_hidden()
    page.evaluate("() => { window.lf.point = 2; }")

    page.keyboard.press("Tab")
    expect(tip).to_have_text("Drag to move")
    page.evaluate("() => { window.lf.held = true; }")
    page.evaluate(changed, "grip")
    expect(tip).to_be_hidden()
    page.evaluate("() => { window.lf.held = false; }")
    page.evaluate(changed, "grip")
    page.wait_for_timeout(300)
    expect(tip).to_be_hidden()

    page.keyboard.press("Shift+Tab")
    expect(tip).to_have_text("Point 2")
    page.keyboard.press("Escape")
    expect(tip).to_be_hidden()
    page.evaluate(
        """async () => {
          const {focusDestination} = await import('/runtime/focus.js');
          document.getElementById('before').focus();
          queueMicrotask(() =>
            focusDestination(document.getElementById('chart'), 'move'));
        }"""
    )
    expect(tip).to_have_text("Point 2")
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
    than the room on either side once the window shrinks, held to the room it has with
    the lines that fit, the last ending in an ellipsis."""
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
        cut: Boolean(document.querySelector('#lf-preview [data-lf-cut]')),
        hidden: [...document.querySelectorAll('#lf-preview .lf-preview-detail')]
          .filter((line) => getComputedStyle(line).visibility === 'hidden').length};
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
    # The window's resize places it again, by the same gap, on whichever side then
    # holds it and covers no other target.
    assert resized["gap"] == shown["gap"], (resized, shown)
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
    # No preview scrolls: the lines that fit show, the last ending in an ellipsis.
    assert held["cut"] and held["hidden"] > 0, held


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


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_preview_stands_where_it_covers_no_small_target_and_fits_any_window(
    engine, request, serve
):
    """The side a preview takes is tested across the box the browser draws, every few
    pixels, so a control as small as WCAG's least target, 24 px, standing under the
    middle of the room below its target, sends it to a free side, and the box drawn
    covers none of them. In a window shorter than the preview, shorter than a few
    lines, it holds itself inside the window with the lines that fit."""
    rows = "".join(
        f'<button class="small" id="s{i}" aria-label="Small {i}" '
        f'style="position: absolute; left: {x}px; top: {y}px; width: 24px; height: 24px; '
        'padding: 0">·</button>'
        for i, (x, y) in enumerate(
            [(1100 + dx, 140 + dy) for dx in (40, 110, 180) for dy in (8, 40)]
        )
    )
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Small targets",
                '<p><button id="before">Before</button></p>'
                '<button id="aim" style="position: absolute; left: 1100px; top: 100px" '
                'aria-label="Aimed at, with a name that runs on for a while">⚙</button>'
                + rows,
            )
        ),
    )
    tip = page.locator(PREVIEW)
    aim = page.locator("#aim")
    page.mouse.move(2, 2)
    aim.hover()
    expect(tip.locator(".lf-preview-word")).to_contain_text("Aimed at")
    covered = page.evaluate(
        """() => {
          const tip = document.getElementById('lf-preview').getBoundingClientRect();
          return [...document.querySelectorAll('.small')].filter((el) => {
            const box = el.getBoundingClientRect();
            return box.left < tip.right && tip.left < box.right && box.top < tip.bottom
              && tip.top < box.bottom;
          }).map((el) => el.id);
        }"""
    )
    assert covered == [], covered

    page.mouse.move(2, 2)
    expect(tip).to_be_hidden()
    page.evaluate(
        """() => { document.getElementById('aim').lfPreview = () => ({name: 'Many',
          detail: Array.from({length: 12}, (_, i) => `Line ${i + 1} of its detail`)}); }"""
    )
    size = page.viewport_size
    page.set_viewport_size({"width": size["width"], "height": 150})
    page.evaluate(
        "() => document.getElementById('aim').scrollIntoView({block: 'center'})"
    )
    aim.hover()
    expect(tip.locator(".lf-preview-word")).to_have_text("Many")
    held = page.evaluate(
        """() => {
          const box = document.getElementById('lf-preview').getBoundingClientRect();
          return {top: box.top, bottom: box.bottom, window: innerHeight,
            cut: Boolean(document.querySelector('#lf-preview [data-lf-cut]'))};
        }"""
    )
    assert held["top"] >= 0 and held["bottom"] <= held["window"] and held["cut"], held


def test_focus_a_command_places_in_a_surface_it_opens_shows_no_preview(browser, serve):
    """`m` walks to the question waiting on the user and opens its card with focus in
    it: the card placed that focus as it opened, so nothing previews until the user
    moves on, as Tab inside the card does. Every element the walk focuses previews
    here, so a preview the placement showed would show."""
    url = serve(PANEL_PAGE)
    panel_comment(
        serve.page_dir,
        "Which day suits the launch?",
        {"section": "lede"},
        author="agent",
        obligation=True,
    )
    page = open_page(browser, url)
    page.evaluate(
        """() => document.addEventListener('focusin', (event) => {
          const el = event.composedPath()[0];
          if (el instanceof Element && !el.lfPreview)
            el.lfPreview = () => ({name: 'Placed here'});
        }, true)"""
    )
    tip = page.locator(PREVIEW)
    page.locator("body").focus()
    page.keyboard.press("m")
    card = page.locator(".lf-margin-preview")
    expect(card).to_be_visible()
    page.wait_for_timeout(300)
    expect(tip).to_be_hidden()
    page.keyboard.press("Tab")
    expect(tip).to_have_text("Placed here")


def test_a_finger_s_hold_reads_and_its_release_presses_nothing(browser, serve):
    """A finger held on a target reads its preview at the platform's own long press,
    which its engine says (`contextmenu`), and the platform's menu stays shut; letting go
    presses nothing, the browser's own click after the release included: a held link
    stays where it is, and its preview stands until the next touch, which puts it away.
    An engine that says nothing as a press grows long, as WebKit's touch engines don't
    (`GestureEvent`), reads after `HOLD` instead. A press the platform never calls long
    is a tap, however slow, which shows nothing and follows the link."""
    url = serve(
        leaf_page(
            "Held link",
            '<p><a id="go" href="#far">a link</a> to read before following.</p>'
            + "<p>More.</p>" * 3
            + '<p id="far">Far.</p>',
        )
    )
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, url, context=context)
    page.evaluate(
        """() => { document.getElementById('go').lfPreview = () =>
          ({name: 'Where it goes'}); }"""
    )
    cdp = context.new_cdp_session(page)
    tip = page.locator(PREVIEW)
    word = tip.locator(".lf-preview-word")
    box = page.locator("#go").bounding_box()
    point = {"x": box["x"] + 10, "y": box["y"] + box["height"] / 2}
    elsewhere = page.locator("#far").bounding_box()

    def touch(kind, at=point):
        cdp.send(
            "Input.dispatchTouchEvent",
            {"type": kind, "touchPoints": [at] if kind != "touchEnd" else []},
        )

    def put_away():
        touch("touchStart", {"x": elsewhere["x"] + 10, "y": elsewhere["y"] + 4})
        touch("touchEnd")
        expect(tip).to_be_hidden()

    touch("touchStart")
    page.wait_for_timeout(600)
    expect(tip).to_be_hidden()
    assert long_press(page, point) is False, "the platform's menu opened"
    expect(tip).to_be_visible()
    expect(word).to_have_text("Where it goes")
    expect(tip).to_have_attribute("data-lf-route", "hold")
    touch("touchEnd")
    rendered(page)
    assert page.evaluate("location.hash") == "", "the held link was followed"
    expect(tip).to_be_visible()
    expect(page.locator("#go")).to_have_attribute("data-lf-held", "")
    put_away()

    page.evaluate("() => { window.GestureEvent = class extends UIEvent {}; }")
    touch("touchStart")
    expect(tip).to_be_visible()
    touch("touchEnd")
    rendered(page)
    assert page.evaluate("location.hash") == ""
    expect(tip).to_be_visible()
    put_away()
    page.evaluate("() => { delete window.GestureEvent; }")

    touch("touchStart")
    page.wait_for_timeout(700)
    touch("touchEnd")
    page.wait_for_function("location.hash === '#far'")
    expect(tip).to_be_hidden()


# Where the preview stands against `id`'s box, and whether a press at that box's centre
# reaches it.
AGAINST = """(id) => {
  const tip = document.getElementById('lf-preview').getBoundingClientRect();
  const el = document.getElementById(id);
  const box = el.getBoundingClientRect();
  const x = box.left + box.width / 2;
  const y = box.top + box.height / 2;
  return {left: Math.round(tip.left), top: Math.round(tip.top),
    bottom: Math.round(tip.bottom), window: innerHeight,
    meets: box.left < tip.right && tip.left < box.right && box.top < tip.bottom
      && tip.top < box.bottom,
    reached: document.elementFromPoint(x, y) === el};
}"""


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_standing_preview_takes_its_place_again_as_what_holds_it_changes(
    engine, request, serve
):
    """Where a standing preview stands is decided again whenever what it was decided
    from changes, its own place the first tried: words that grow over a neighbour leave
    it where it stands, under the user's aim, held to the room that clears the
    neighbour, its last line ending in an ellipsis, so the neighbour shows whole and a
    press reaches it, and the pointer can still cross onto the preview; a declared point
    that moves inside its element takes the preview with it, a box the element changes
    in place as well as a new one; and a scroll that carries its target to where its
    side no longer holds it puts it on a side that does."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(leaf_page("Standing again", "<p>Words.</p>")),
    )
    page.set_viewport_size({"width": 1200, "height": 700})
    page.evaluate(
        """() => {
          const aim = document.createElement('button');
          aim.id = 'aim';
          aim.textContent = 'A';
          aim.style = 'position: fixed; left: 300px; top: 200px; width: 80px;'
            + ' height: 40px; padding: 0';
          aim.lfPreview = () => ({name: 'Preview words'});
          const next = document.createElement('button');
          next.id = 'next';
          next.textContent = 'Neighbour';
          next.style = 'position: fixed; left: 310px; top: 285px; width: 90px;'
            + ' height: 30px; padding: 0';
          window.pressed = 0;
          next.onclick = () => window.pressed++;
          document.body.append(aim, next);
        }"""
    )
    tip = page.locator(PREVIEW)
    page.mouse.move(2, 2)
    page.locator("#aim").hover()
    expect(tip.locator(".lf-preview-word")).to_have_text("Preview words")
    short = page.evaluate(AGAINST, "next")
    assert not short["meets"], short
    page.evaluate(
        """async () => {
          const {previewChanged} = await window.__lfWidgetApi();
          const aim = document.getElementById('aim');
          aim.lfPreview = () => ({name: 'Preview words', detail: [1, 2, 3, 4]
            .map((n) => `Additional detail on line ${n}`)});
          previewChanged(aim);
        }"""
    )
    expect(tip.locator(".lf-preview-detail")).to_have_count(4)
    rendered(page)
    grown = page.evaluate(AGAINST, "next")
    assert grown["top"] == short["top"], grown
    assert not grown["meets"] and grown["reached"], grown
    assert tip.locator("[data-lf-clamp], [data-lf-cut]").count() == 1
    held = tip.bounding_box()
    page.mouse.move(held["x"] + 20, held["y"] + 8, steps=4)
    page.wait_for_timeout(400)
    expect(tip).to_be_visible()
    box = page.locator("#next").bounding_box()
    page.mouse.click(box["x"] + 45, box["y"] + 15)
    assert page.evaluate("window.pressed") == 1

    page.mouse.move(2, 2)
    expect(tip).to_be_hidden()
    page.evaluate(
        """async () => {
          const {previewChanged} = await window.__lfWidgetApi();
          for (const id of ['aim', 'next']) document.getElementById(id).remove();
          const chart = document.createElement('div');
          chart.id = 'chart';
          chart.style = 'position: fixed; left: 300px; top: 150px; width: 600px;'
            + ' height: 300px';
          chart.tabIndex = 0;
          window.pointX = 320;
          // The chart keeps one box for its point and changes it in place.
          const at = {left: 320, right: 330, top: 250, bottom: 260};
          chart.lfPreview = () => ({name: 'Point value', at});
          // A key the chart takes redraws it with its point moved and the same words.
          chart.addEventListener('keydown', (event) => {
            if (event.key !== 'F10') return;
            window.pointX = 700;
            Object.assign(at, {left: 700, right: 710});
            previewChanged(chart);
          });
          const toChart = document.createElement('button');
          toChart.id = 'to-chart';
          toChart.textContent = 'To the chart';
          document.body.append(toChart, chart);
        }"""
    )
    page.locator("#to-chart").focus()
    page.keyboard.press("Tab")
    expect(tip.locator(".lf-preview-word")).to_have_text("Point value")
    assert abs(page.evaluate(AGAINST, "chart")["left"] - 320) <= 1
    page.keyboard.press("F10")
    page.wait_for_function("window.pointX === 700")
    rendered(page)
    assert abs(page.evaluate(AGAINST, "chart")["left"] - 700) <= 1, "it stayed behind"

    page.keyboard.press("Escape")
    expect(tip).to_be_hidden()
    page.set_viewport_size({"width": 900, "height": 400})
    page.evaluate(
        """() => {
          for (const id of ['chart', 'to-chart']) document.getElementById(id).remove();
          const aim = document.createElement('button');
          aim.id = 'held';
          aim.textContent = 'Held';
          const scroller = document.createElement('div');
          scroller.id = 'scroller';
          scroller.style = 'position: fixed; left: 200px; top: 0; width: 500px;'
            + ' height: 380px; overflow: auto';
          const inner = document.createElement('div');
          inner.style = 'padding-top: 250px; height: 800px';
          const before = document.createElement('button');
          before.id = 'before';
          before.textContent = 'Before';
          inner.append(before, aim);
          scroller.append(inner);
          document.body.append(scroller);
          aim.style = 'width: 80px; height: 40px; padding: 0';
          aim.lfPreview = () => ({name: 'Scrolled value',
            detail: Array.from({length: 7}, (_, n) => `Detail ${n}`)});
        }"""
    )
    page.locator("#before").focus()
    page.keyboard.press("Tab")
    expect(tip.locator(".lf-preview-word")).to_have_text("Scrolled value")
    # The user scrolls the box with the wheel, over none of its controls, the preview
    # or Leaf's own at the window's foot, so the preview's new side is the scroll's
    # doing, under their input.
    page.mouse.move(650, 60)
    page.mouse.wheel(0, 200)
    page.wait_for_function("document.getElementById('scroller').scrollTop >= 150")
    rendered(page)
    scrolled = page.evaluate(AGAINST, "held")
    assert scrolled["top"] >= 0 and scrolled["bottom"] <= scrolled["window"], scrolled


def test_a_pinch_zoomed_window_holds_its_preview_in_what_it_shows(browser, serve):
    """Zoomed in by a pinch, the window shows part of the page, and a preview stands
    whole inside that part. Chromium alone: Playwright pinches no other engine."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Pinched",
                '<p><button id="before">Before</button></p>'
                '<button id="aim" style="position: absolute; left: 500px; top: 200px"'
                ' aria-label="A control whose name runs on long enough to need room">'
                "⚙</button>",
            )
        ),
    )
    page.set_viewport_size({"width": 1440, "height": 900})
    cdp = page.context.new_cdp_session(page)
    cdp.send("Emulation.setPageScaleFactor", {"pageScaleFactor": 2})
    page.wait_for_function("visualViewport.scale === 2")
    tip = page.locator(PREVIEW)
    page.locator("#before").focus()
    page.keyboard.press("Tab")
    expect(tip.locator(".lf-preview-word")).to_contain_text("A control whose name")
    rendered(page)
    held = page.evaluate(
        """() => {
          const tip = document.getElementById('lf-preview').getBoundingClientRect();
          const v = visualViewport;
          return {left: tip.left - v.offsetLeft, right: v.offsetLeft + v.width - tip.right,
            top: tip.top - v.offsetTop, bottom: v.offsetTop + v.height - tip.bottom};
        }"""
    )
    assert min(held.values()) >= 0, held


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_name_longer_than_its_room_ends_in_an_ellipsis(engine, request, serve):
    """A name that wraps to more lines than the room holds shows the lines that fit,
    the last ending in an ellipsis, as a long title one span holds: none is cut through
    by the face's edge. The room alone decides it, so a window grown to hold the whole
    name shows it whole, standing or shown again."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Long name",
                '<p><button id="before">Before</button></p>'
                '<p><button id="aim">Aim</button></p>',
            )
        ),
    )
    page.evaluate(
        """() => { document.getElementById('aim').lfPreview = () => ({name:
          Array.from({length: 80}, (_, n) => `word${n}`).join(' ')}); }"""
    )
    page.set_viewport_size({"width": 900, "height": 180})
    tip = page.locator(PREVIEW)
    page.locator("#before").focus()
    page.keyboard.press("Tab")
    expect(tip.locator(".lf-preview-word")).to_contain_text("word0")
    rendered(page)
    held = page.evaluate(
        """() => {
          const face = document.querySelector('#lf-preview .lf-preview-face');
          const word = face.querySelector('.lf-preview-word');
          return {face: face.getBoundingClientRect().bottom,
            word: word.getBoundingClientRect().bottom,
            clamp: getComputedStyle(word).webkitLineClamp, window: innerHeight};
        }"""
    )
    assert held["word"] <= held["face"] + 0.5, held
    assert held["clamp"] not in ("none", ""), held
    page.set_viewport_size({"width": 900, "height": 800})
    rendered(page)
    clamped = "() => document.querySelectorAll('#lf-preview [data-lf-clamp]').length"
    assert page.evaluate(clamped) == 0, "the clamp stayed as the window grew"
    page.keyboard.press("Escape")
    expect(tip).to_be_hidden()
    page.locator("#before").focus()
    page.keyboard.press("Tab")
    expect(tip.locator(".lf-preview-word")).to_contain_text("word79")
    rendered(page)
    assert page.evaluate(clamped) == 0, "the clamp stayed as it showed again"


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_widget_s_new_aim_reads_again_whichever_child_holds_focus(
    engine, request, serve
):
    """A widget that declares its preview while a control inside it holds focus says
    the user aimed at something new (`previewChanged` with `aim`): the preview reads
    the widget again, and after Escape put it away the next aim shows it again."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Owner",
                '<div id="host"><button id="inner">Item one</button></div>',
            )
        ),
    )
    page.evaluate(
        """async () => {
          window.lfApi = await window.__lfWidgetApi();
          window.label = 'First item detail';
          document.getElementById('host').lfPreview = () => ({name: window.label});
        }"""
    )
    tip = page.locator(PREVIEW)
    aim = """(words) => {
      window.label = words;
      window.lfApi.previewChanged(document.getElementById('host'), {aim: true});
    }"""
    page.keyboard.press("Shift")
    page.evaluate(
        "() => window.lfApi.focusDestination(document.getElementById('inner'), 'move')"
    )
    expect(tip.locator(".lf-preview-word")).to_have_text("First item detail")
    page.evaluate(aim, "Second item detail")
    expect(tip.locator(".lf-preview-word")).to_have_text("Second item detail")
    page.keyboard.press("Escape")
    expect(tip).to_be_hidden()
    page.evaluate(aim, "Third item detail")
    expect(tip).to_be_visible()
    expect(tip.locator(".lf-preview-word")).to_have_text("Third item detail")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_focus_moved_into_a_dialog_already_open_previews(engine, request, serve):
    """A move into a dialog that already stands is the user's, as one beside it is, so
    the control it lands on previews; only a surface placing focus as it opens shows
    none, as one a widget opens through `openLayer` does."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Open dialog",
                '<button id="outside">Outside</button><div role="dialog" id="open"'
                ' aria-label="Standing"><button id="inside">I</button></div>'
                '<div role="dialog" id="opening" aria-label="Opening" hidden>'
                '<button id="first">F</button></div>',
            )
        ),
    )
    page.evaluate(
        """async () => {
          const api = await window.__lfWidgetApi();
          for (const id of ['outside', 'inside', 'first'])
            document.getElementById(id).lfPreview = () => ({name: `${id} detail`});
          // A key that moves the user to a place, as a command's walk does.
          const to = {F9: 'outside', F10: 'inside'};
          addEventListener('keydown', (event) => {
            if (event.key === 'F8') {
              // A widget opening its dialog, which places the user on its first control.
              event.preventDefault();
              const opening = document.getElementById('opening');
              api.openLayer(opening);
              opening.hidden = false;
              api.focusDestination(document.getElementById('first'), 'move');
              return;
            }
            if (!to[event.key]) return;
            event.preventDefault();
            api.focusDestination(document.getElementById(to[event.key]), 'move');
          }, true);
        }"""
    )
    tip = page.locator(PREVIEW)
    page.keyboard.press("F9")
    expect(tip.locator(".lf-preview-word")).to_have_text("outside detail")
    page.keyboard.press("F10")
    expect(tip.locator(".lf-preview-word")).to_have_text("inside detail")
    page.keyboard.press("Escape")
    expect(tip).to_be_hidden()
    page.keyboard.press("F8")
    expect(page.locator("#first")).to_be_focused()
    page.wait_for_timeout(300)
    expect(tip).to_be_hidden()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_an_aim_at_what_says_nothing_leaves_the_standing_preview(
    engine, request, serve
):
    """Only a new reading replaces a standing preview: an aim at an element that says
    nothing there leaves it standing, as plain text does. Keyboard focus reads one
    element while the pointer rests on another, which then says it changed and now says
    nothing, as a chart does as its point's ring comes off; then the pointer crosses
    that element where it says nothing, as empty space inside a chart."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Nothing to say",
                '<p><button id="before">Before</button></p>'
                '<p><span id="focused" tabindex="0">Focused</span></p>'
                '<div id="pointed" style="width: 320px; height: 120px">Pointed</div>',
            )
        ),
    )
    page.evaluate(
        """async () => {
          window.lfApi = await window.__lfWidgetApi();
          window.lfSays = true;
          document.getElementById('focused').lfPreview = () => ({name: 'Focus reads'});
          document.getElementById('pointed').lfPreview = () =>
            window.lfSays ? {name: 'Pointer reads'} : null;
        }"""
    )
    tip = page.locator(PREVIEW)
    word = tip.locator(".lf-preview-word")
    page.mouse.move(2, 2)
    page.locator("#pointed").hover()
    expect(word).to_have_text("Pointer reads")
    page.locator("#before").focus()
    page.keyboard.press("Tab")
    expect(word).to_have_text("Focus reads")
    page.evaluate(
        """() => {
          window.lfSays = false;
          window.lfApi.previewChanged(document.getElementById('pointed'));
        }"""
    )
    page.wait_for_timeout(400)
    expect(tip).to_be_visible()
    expect(word).to_have_text("Focus reads")
    box = page.locator("#pointed").bounding_box()
    page.mouse.move(box["x"] + 300, box["y"] + 100, steps=6)
    page.wait_for_timeout(400)
    expect(tip).to_be_visible()
    expect(word).to_have_text("Focus reads")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
@pytest.mark.parametrize("width", ["auto", "50vw"])
def test_a_window_resize_decides_once_where_a_preview_stands(
    engine, width, request, serve
):
    """A resize of the window changes the window, the visible viewport and maybe the
    target's size at once, and the standing preview decides where it stands once for
    all of them, a target as wide as half the window included."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Resized",
                '<p><button id="before">Before</button></p>'
                f'<p><span id="aim" tabindex="0" style="display: inline-block;'
                f' width: {width}">A value</span></p>',
            )
        ),
    )
    page.evaluate(
        """() => {
          document.getElementById('aim').lfPreview = () => ({name: 'A value says'});
          // Each decision (preview.js, `stand`) measures the preview's width once; the
          // page's watches measure it too.
          const tip = document.getElementById('lf-preview');
          const measure = tip.getBoundingClientRect;
          window.lfDecisions = 0;
          tip.getBoundingClientRect = function () {
            const stack = new Error().stack ?? '';
            if (stack.includes('at stand (') || stack.includes('stand@'))
              window.lfDecisions += 1;
            return measure.call(this);
          };
        }"""
    )
    tip = page.locator(PREVIEW)
    page.locator("#before").focus()
    page.keyboard.press("Tab")
    expect(tip.locator(".lf-preview-word")).to_have_text("A value says")
    rendered(page)
    page.evaluate("() => { window.lfDecisions = 0; }")
    page.set_viewport_size({"width": 1000, "height": 640})
    rendered(page)
    page.wait_for_timeout(200)
    assert page.evaluate("window.lfDecisions") == 1


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_words_that_grow_keep_a_place_that_held_exactly_one_line(
    engine, request, serve
):
    """A preview standing in a room that holds exactly its one line, a neighbour just
    under it, keeps that place as its words grow, fitted to the line with an ellipsis,
    whatever fraction of a pixel the engine lays the line out at, rather than moving
    onto the neighbours."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(leaf_page("One line", "<p>Words.</p>")),
    )
    page.set_viewport_size({"width": 1200, "height": 700})
    page.evaluate(
        """() => {
          const aim = document.createElement('button');
          aim.id = 'aim';
          aim.textContent = 'A';
          aim.style = 'position: fixed; left: 300px; top: 200px; width: 80px;'
            + ' height: 40px; padding: 0';
          window.lfLong = false;
          aim.lfPreview = () => ({name: window.lfLong
            ? 'A growing label that runs on past one line, and past a second, before'
              + ' it says its only useful word, FAILURE' : 'Initial words'});
          document.body.append(aim);
        }"""
    )
    tip = page.locator(PREVIEW)
    page.mouse.move(2, 2)
    page.locator("#aim").hover()
    expect(tip.locator(".lf-preview-word")).to_have_text("Initial words")
    rendered(page)
    first = tip.bounding_box()
    page.mouse.move(2, 2)
    expect(tip).to_be_hidden()
    # A neighbour right under the one line the preview stood on.
    page.evaluate(
        """([left, top]) => {
          const next = document.createElement('button');
          next.id = 'next';
          next.textContent = 'Neighbour';
          next.style = `position: fixed; left: ${left}px; top: ${top}px; width: 600px;`
            + ' height: 30px; padding: 0';
          document.body.append(next);
        }""",
        [first["x"], first["y"] + first["height"]],
    )
    page.locator("#aim").hover()
    expect(tip).to_be_visible()
    rendered(page)
    before = tip.bounding_box()
    assert (before["x"], before["y"]) == (first["x"], first["y"]), (first, before)
    page.evaluate(
        """async () => {
          const {previewChanged} = await window.__lfWidgetApi();
          window.lfLong = true;
          previewChanged(document.getElementById('aim'));
        }"""
    )
    expect(tip.locator(".lf-preview-word")).to_contain_text("growing")
    rendered(page)
    after = tip.bounding_box()
    assert (after["x"], after["y"]) == (before["x"], before["y"]), (before, after)
    assert page.evaluate(COVERS, ["next"]) == []
    assert tip.locator("[data-lf-clamp]").count() == 1


# Controls fencing a target, rows above and below it and controls beside it, each as
# tall as WCAG's least target, so no side holds a long preview whole and clear: the one
# below holds two lines, above one.
FENCED = """<div style="height: 700px"></div>
<button id="over" style="position: fixed; left: 0; right: 0; top: 226px; height: 24px">
  Over</button>
<button id="under" style="position: fixed; left: 0; right: 0; top: 400px; height: 24px">
  Under</button>
<button id="left" style="position: fixed; left: 0; width: 290px; top: 300px;
  height: 40px">Left</button>
<button id="right" style="position: fixed; left: 390px; right: 0; top: 300px;
  height: 40px">Right</button>
<button id="fenced" style="position: fixed; left: 300px; top: 300px; width: 80px;
  height: 40px; padding: 0">F</button>"""


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_preview_no_side_holds_whole_takes_the_side_that_holds_most_lines_clear(
    engine, request, serve
):
    """Where no side holds a preview whole and clear of every other control, it stands
    on the side whose clear room holds the most whole lines, fitted there with an
    ellipsis, covering nothing, so it takes the pointer as any preview does."""
    page = open_page(
        request.getfixturevalue(engine), serve(leaf_page("Fenced", FENCED))
    )
    page.set_viewport_size({"width": 1200, "height": 700})
    page.evaluate(
        """() => { document.getElementById('fenced').lfPreview = () => ({name:
          'Fenced in', detail: Array.from({length: 6}, (_, n) => `Detail line ${n}`)}); }"""
    )
    tip = page.locator(PREVIEW)
    page.mouse.move(2, 2)
    page.locator("#fenced").hover()
    expect(tip.locator(".lf-preview-word")).to_have_text("Fenced in")
    rendered(page)
    assert tip.get_attribute("data-lf-y") == "below"
    assert tip.get_attribute("data-lf-covers") is None
    assert page.evaluate(COVERS, ["over", "under", "left", "right"]) == []
    assert tip.locator("[data-lf-clamp], [data-lf-cut]").count() == 1


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_target_filling_a_short_window_previews_a_whole_line(engine, request, serve):
    """A target that leaves no side room for even one line of its preview has it stand
    over it, showing at least a whole line, rather than a sliver of clipped text."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Filling",
                '<button id="before" style="position: fixed; left: 0; top: 0;'
                ' width: 10px; height: 10px; padding: 0">B</button>'
                '<button id="filling" style="position: fixed; left: 20px; top: 20px;'
                ' width: 350px; height: 140px">Filling</button>',
            )
        ),
    )
    page.set_viewport_size({"width": 390, "height": 180})
    page.evaluate(
        """() => { document.getElementById('filling').lfPreview = () => ({name:
          'What the target does', detail: ['A second line', 'A third line']}); }"""
    )
    tip = page.locator(PREVIEW)
    page.locator("#before").focus()
    page.keyboard.press("Tab")
    expect(tip).to_be_visible()
    rendered(page)
    held = page.evaluate(
        """() => {
          const face = document.querySelector('#lf-preview .lf-preview-face');
          const word = face.querySelector('.lf-preview-word').getBoundingClientRect();
          const box = face.getBoundingClientRect();
          return {face: box.height, wordBottom: word.bottom, faceBottom: box.bottom,
            line: parseFloat(getComputedStyle(face.querySelector('.lf-preview-word'))
              .lineHeight)};
        }"""
    )
    assert held["face"] >= held["line"], held
    assert held["wordBottom"] <= held["faceBottom"] + 0.5, held


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_count_on_a_control_s_face_names_nothing(engine, request, serve):
    """A control whose face shows a mark and a count, as the folded On me does, says
    nothing of what it is by that count, so it previews its name to the keyboard and to
    a held finger, whose release then presses nothing."""
    url = serve(
        leaf_page(
            "Counted",
            '<p><button id="before">Before</button></p>'
            '<p><button id="count" aria-label="1 question waiting on you">'
            '<span aria-hidden="true">●</span>1</button></p>',
        )
    )
    browser = request.getfixturevalue(engine)
    page = open_page(browser, url)
    page.evaluate(
        "() => { window.lfPressed = 0; document.getElementById('count')"
        ".addEventListener('click', () => { window.lfPressed += 1; }); }"
    )
    tip = page.locator(PREVIEW)
    page.locator("#before").focus()
    page.keyboard.press("Tab")
    expect(tip.locator(".lf-preview-word")).to_have_text("1 question waiting on you")
    if engine != "browser":
        return
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    phone = open_page(browser, url, context=context)
    phone.evaluate(
        "() => { window.lfPressed = 0; document.getElementById('count')"
        ".addEventListener('click', () => { window.lfPressed += 1; }); }"
    )
    box = phone.locator("#count").bounding_box()
    point = {"x": box["x"] + box["width"] / 2, "y": box["y"] + box["height"] / 2}
    cdp = context.new_cdp_session(phone)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [point]})
    long_press(phone, point)
    held = phone.locator(PREVIEW)
    expect(held).to_be_visible()
    expect(held.locator(".lf-preview-word")).to_have_text("1 question waiting on you")
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    rendered(phone)
    assert phone.evaluate("window.lfPressed") == 0


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_preview_leaves_a_field_beside_it_reachable(engine, request, serve):
    """A field is a control the user works, though it previews nothing, so a preview
    stands clear of one beside its target, and a press on the field focuses it."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Field",
                '<p style="margin-top: 200px"><button id="explain">Explain the'
                ' calculation</button><br><input id="field" aria-label="Amount"'
                ' style="width: 260px"></p>',
            )
        ),
    )
    page.set_viewport_size({"width": 1200, "height": 700})
    page.evaluate(
        """() => { document.getElementById('explain').lfPreview = () => ({name:
          'How the total is worked out', detail: ['Each line is the price times the'
          + ' quantity', 'The total adds every line']}); }"""
    )
    tip = page.locator(PREVIEW)
    page.mouse.move(2, 2)
    page.locator("#explain").hover()
    expect(tip.locator(".lf-preview-word")).to_have_text("How the total is worked out")
    rendered(page)
    assert page.evaluate(COVERS, ["field"]) == []
    page.locator("#field").click()
    expect(page.locator("#field")).to_be_focused()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_standing_preview_redrawn_over_a_control_that_arrived_moves_clear(
    engine, request, serve
):
    """A control that arrives under a standing preview is found again as the preview
    redraws, whatever it found clear before, so the preview leaves it whole and a press
    on it reaches it."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(leaf_page("Arrived", "<p>Words.</p>")),
    )
    page.set_viewport_size({"width": 1200, "height": 700})
    page.evaluate(
        """() => {
          const aim = document.createElement('button');
          aim.id = 'aim';
          aim.textContent = 'A';
          aim.style = 'position: fixed; left: 300px; top: 200px; width: 80px;'
            + ' height: 40px; padding: 0';
          aim.lfPreview = () => ({name: 'Preview words',
            detail: ['A second line', 'A third line']});
          window.pressed = 0;
          document.body.append(aim);
        }"""
    )
    tip = page.locator(PREVIEW)
    page.mouse.move(2, 2)
    page.locator("#aim").hover()
    expect(tip.locator(".lf-preview-word")).to_have_text("Preview words")
    rendered(page)
    box = tip.bounding_box()
    page.evaluate(
        """async ([left, top]) => {
          const next = document.createElement('button');
          next.id = 'next';
          next.textContent = 'Arrived';
          next.style = `position: fixed; left: ${left}px; top: ${top}px; width: 100px;`
            + ' height: 30px; padding: 0';
          next.onclick = () => { window.pressed += 1; };
          document.body.append(next);
          const {previewChanged} = await window.__lfWidgetApi();
          previewChanged(document.getElementById('aim'));
        }""",
        [box["x"] + 10, box["y"] + box["height"] / 2],
    )
    rendered(page)
    assert page.evaluate(COVERS, ["next"]) == []
    arrived = page.locator("#next").bounding_box()
    page.mouse.click(arrived["x"] + 50, arrived["y"] + 15)
    assert page.evaluate("window.pressed") == 1


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_focus_preview_out_of_view_stands_once_its_target_comes_into_view(
    engine, request, serve
):
    """Focus the user moved onto a target out of view reads its preview as soon as the
    target comes into view, as a scroll that lands it brings it, though no place
    could hold the preview as focus arrived."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Out of view",
                '<div style="height: 300px"></div>'
                '<p><button id="late">Late</button></p><div style="height: 2400px"></div>',
            )
        ),
    )
    page.evaluate(
        """async () => {
          window.lfApi = await window.__lfWidgetApi();
          document.getElementById('late').lfPreview = () => ({name: 'Late says'});
          // The target stands above the window as focus reaches it.
          scrollTo(0, 1200);
        }"""
    )
    tip = page.locator(PREVIEW)
    page.keyboard.press("Shift")
    page.evaluate(
        "() => window.lfApi.focusDestination(document.getElementById('late'), 'move')"
    )
    expect(page.locator("#late")).to_be_focused()
    page.evaluate(
        "() => document.getElementById('late').scrollIntoView({block: 'center'})"
    )
    expect(tip).to_be_visible()
    expect(tip.locator(".lf-preview-word")).to_have_text("Late says")


# A region a preview's target stands just above, each of which the user must keep
# reaching: code Leaf lends a tab stop to as it overflows, a tab panel that takes focus,
# and a frame with a field in it.
REACHED = {
    "code": (
        '<pre id="region" class="scroll" style="width: 400px; height: 120px;'
        ' overflow: auto; margin: 4px 0 0"><code>'
        + "total = sum(item.price * item.quantity for item in all_items_with_a_long"
        "_collection_name_that_runs_past_the_box)\n" * 8 + "</code></pre>"
    ),
    "panel": (
        '<div id="region" role="tabpanel" tabindex="0" style="width: 400px;'
        ' height: 120px; margin-top: 4px; border: 1px solid">A tab panel'
        " the user can step into.</div>"
    ),
    "frame": (
        '<iframe id="region" style="width: 400px; height: 120px; margin-top: 4px"'
        ' srcdoc="<input id=inner aria-label=Inside>"></iframe>'
    ),
}


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
@pytest.mark.parametrize("region", sorted(REACHED))
def test_a_preview_leaves_a_region_the_user_works_in_reachable(
    engine, region, request, serve
):
    """A preview stands clear of a region the user must keep reaching, though nothing
    in it previews and the gestures Leaf routes leave it alone: code that scrolls, a
    tab panel that takes focus, a frame. A press there reaches it."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Reached",
                '<p style="margin-top: 200px"><button id="explain" style="width:'
                ' 160px">Explain calculation</button></p>' + REACHED[region],
            )
        ),
    )
    page.set_viewport_size({"width": 1200, "height": 700})
    page.evaluate(
        """() => { document.getElementById('explain').lfPreview = () => ({name:
          'Explain calculation', detail: ['Each line is price times quantity',
          'The total adds every line']}); }"""
    )
    tip = page.locator(PREVIEW)
    page.mouse.move(2, 2)
    page.locator("#explain").hover()
    expect(tip.locator(".lf-preview-word")).to_have_text("Explain calculation")
    rendered(page)
    assert page.evaluate(COVERS, ["region"]) == []
    box = page.locator("#region").bounding_box()
    page.mouse.click(box["x"] + 40, box["y"] + 20)
    if region == "frame":
        expect(page.frame_locator("#region").locator("#inner")).to_be_focused()
    else:
        expect(page.locator("#region")).to_be_focused()
