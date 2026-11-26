"""Which passage an unsent comment belongs to as the user selects, retargets, revisits
or moves to another location, and where Threads lists it."""

import re

import pytest
from playwright.sync_api import expect
from render_cases_navigation import compose, go_to_address, pending_text
from render_harness import (
    LONG_PAGE,
    draft_control,
    expect_panel_says,
    hold_selection,
    leaf_page,
    open_page,
    open_threads,
    select_words,
    selection_field,
    sending,
    stored_drafts,
    write,
)

from browser.drafts import (
    choose_comment_target,
)
from leaf.log import event_log as events_model
from leaf.source.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


def test_completed_page_selection_opens_its_own_comment(browser, serve):
    """A real page selection opens Comment without focusing it or carrying earlier
    words, whether a mouse drag, a drag inside a bounded scroller, or the keyboard's
    select-all made it."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Selection gestures",
                '<p id="earlier">Earlier subject.</p>'
                # Room for the earlier subject's box, which stands under it at the
                # full measure, so each drag lands on words a reader can see.
                '<div style="height: 6rem"></div>'
                '<p id="later">A later passage keeps native selection.</p>'
                '<p id="later-box" class="lf-scroll" style="height:72px;overflow:auto">'
                "A later boxed passage keeps native selection.<br>"
                + "Another line of evidence.<br>" * 40
                + "</p>",
            )
        ),
    )
    field = page.locator(".lf-fab-input")
    for gesture, later in (
        ("mouse", "#later"),
        ("mouse-in-scroller", "#later-box"),
        ("keyboard", "#later"),
    ):
        page.locator("#earlier").click(modifiers=["Alt"])
        write(field, "Words about the earlier subject")
        if gesture.startswith("mouse"):
            line = page.locator(later).evaluate("""p => {
                const range = document.createRange();
                range.selectNodeContents(p);
                return range.getClientRects()[0].toJSON();
            }""")
            y = line["y"] + line["height"] / 2
            hold_selection(page, (line["x"] + 2, y), (line["x"] + line["width"] - 2, y))
            page.mouse.up()
            if gesture == "mouse-in-scroller":
                # A bounded reading region takes native focus as the drag begins.
                expect(page.locator(later)).to_be_focused()
        else:
            page.locator(later).click()
            page.keyboard.press("ControlOrMeta+a")
        rendered(page)
        assert page.evaluate("() => getSelection().toString()"), gesture
        expect(field).to_be_visible()
        expect(field).not_to_be_focused()
        expect(field).to_have_js_property("value", "")
        page.keyboard.press("c")
        expect(field).to_be_focused()
        page.keyboard.press("Escape")
        page.locator("#earlier").click(modifiers=["Alt"])
        expect(field).to_have_js_property("value", "Words about the earlier subject")
        page.keyboard.press("Escape")


@pytest.mark.parametrize(
    "touch, words",
    [(False, "An unfinished earlier comment"), (True, "")],
    ids=["browser-command-unfinished", "touch-handles-empty"],
)
def test_observed_selection_offers_comment_without_replacing_the_editor(
    browser, serve, touch, words
):
    """Browser-owned selection offers an explicit action while an existing editor stays.

    Chromium's native SelectAll command supplies desktop selection without a keyup.
    Touch emulation has no OS handles; Selection.extend exercises their endpoint
    notification without inventing a page pointer gesture.
    """
    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, has_touch=touch
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Observed selection",
                '<p id="earlier">Earlier subject.</p>'
                '<p id="later">A later passage keeps native selection.</p>',
            )
        ),
        context=context,
    )
    page.locator("#earlier").click(modifiers=["Alt"])
    field = page.locator(".lf-fab-input")
    write(field, words)
    field.evaluate("el => { window.heldSelectionEditor = el; }")
    action = selection_field(page)

    def select_in_browser():
        field.evaluate("el => el.blur()")
        if touch:
            page.locator("#later").evaluate("""async p => {
            const changed = new Promise(resolve => document.addEventListener(
              'selectionchange', resolve, {once: true}));
            getSelection().setBaseAndExtent(p.firstChild, 2, p.firstChild, 7);
            getSelection().extend(p.firstChild, 15);
            await changed;
        }""")
        else:
            context.new_cdp_session(page).send(
                "Input.dispatchKeyEvent", {"type": "keyDown", "commands": ["SelectAll"]}
            )
        expect(action).to_be_visible()

    select_in_browser()
    selected = page.evaluate("() => getSelection().toString()")
    assert selected
    # A modifier's release observes the passage; it does not select it for Comment.
    page.keyboard.press("Shift")
    rendered(page)
    assert field.evaluate("el => el === window.heldSelectionEditor")
    expect(field).to_be_visible()
    expect(field).to_have_js_property("value", words)
    assert page.evaluate("() => getSelection().toString()") == selected

    # Returning to this editor retires the browser-owned selection and its offer.
    if touch:
        field.tap()
    else:
        field.click()
    rendered(page)
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", words)
    assert page.evaluate("() => getSelection().toString()") == ""
    expect(action).to_be_hidden()
    select_in_browser()

    # A tap or a click on the panel's field comments on the captured passage.
    if touch:
        action.tap()
    else:
        action.click()
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", "")
    assert pending_text(page) == selected.replace("\n", "")
    assert page.evaluate("() => getSelection().toString()") == ""
    page.keyboard.press("Escape")
    page.locator("#earlier").click(modifiers=["Alt"])
    expect(field).to_have_js_property("value", words)


def test_a_passages_comment_box_undoes_only_its_own_draft(browser, serve):
    """The comment box moves from passage to passage, and its undo history belongs to
    the draft it stands on: words typed and deleted on one passage are not what ⌘Z
    brings into the next one's draft, even when both drafts read the same."""
    page = open_page(browser, serve(LONG_PAGE))
    field = page.locator(".lf-fab-input")
    compose(page, "#p0")
    page.keyboard.type("x")
    page.keyboard.press("ArrowLeft")  # a caret move ends the typing's undo step
    page.keyboard.press("End")
    page.keyboard.press("Backspace")
    expect(field).to_have_js_property("value", "")
    compose(page, "#p1")
    page.keyboard.press("ControlOrMeta+z")
    page.keyboard.type("y")
    expect(field).to_have_js_property("value", "y")


def test_an_unsent_comment_stays_with_its_passage_when_another_is_selected(
    browser, serve
):
    """Opening fields is automatic, so selecting a new passage is not re-anchoring.

    Each passage keeps its own durable draft: the newly selected passage starts empty,
    and returning to the original passage restores the words written about it."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Two passages",
                # Both selections have to reach words clear of the open comment card.
                '<h1>Noted</h1><p id="p1">The first passage under discussion.</p>'
                '<p id="p2" style="margin-top:180px">A second passage.</p>',
            )
        ),
    )
    field = page.locator(".lf-fab-input")
    original = "These words belong to the first passage."

    select_words(page, "#p1")
    expect(field).to_be_visible()
    expect(field).not_to_be_focused()
    write(field, original)

    select_words(page, "#p2")
    expect(field).to_have_js_property("value", "")
    expect(field).not_to_be_focused()
    composed = [
        context for context in stored_drafts(page) if context.startswith("composer:")
    ]
    assert len(composed) == 1

    select_words(page, "#p1")
    expect(field).to_have_js_property("value", original)
    expect(field).not_to_be_focused()


def _draft_attachment_boxes(field, passage):
    """Read both moving boxes in one layout instant during native smooth travel.

    Separate driver calls can straddle scroll frames and invent relative movement.
    """
    return field.evaluate(
        """(node, selector) => [
          node.getBoundingClientRect().toJSON(),
          document.querySelector(selector).getBoundingClientRect().toJSON(),
        ]""",
        passage,
    )


def test_comment_follows_a_new_current_location_instead_of_an_earlier_draft(
    browser, serve
):
    """The earlier draft keeps its subject while a later keyboard landing names
    the next comment. Resume recovers the editor that followed its earlier passage."""
    source = LONG_PAGE.replace(
        "<p id='p40'>", '<p id="p40"><a id="later-link" href="#p41">Later item</a> '
    )
    page = open_page(browser, serve(source))
    words = "Unfinished words that stay with the paragraph they are about."
    choose_comment_target(page, "#p3")
    write(page.locator(".lf-fab-input"), words)
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    rendered(page)
    earlier = page.locator(".lf-fab-input")
    earlier.evaluate("node => {window.earlierEditor = node;}")
    before_field, before_target = _draft_attachment_boxes(earlier, "#p3")
    page.keyboard.press("Shift+Tab")
    page.locator("#later-link").scroll_into_view_if_needed()
    go_to_address(page, "Link", "later-link")
    expect(page.locator("#p3")).not_to_be_in_viewport()
    expect(earlier).not_to_be_in_viewport()
    expect(earlier).to_have_js_property("value", words)
    expect(earlier).to_have_attribute("aria-label", re.compile("Paragraph 3"))
    after_field, after_target = _draft_attachment_boxes(earlier, "#p3")
    for axis in ("x", "y"):
        assert after_field[axis] - before_field[axis] == pytest.approx(
            after_target[axis] - before_target[axis], abs=2
        )

    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(earlier).to_be_focused()
    expect(earlier).to_be_in_viewport()
    expect(page.locator("#p3")).to_be_in_viewport()
    expect(earlier).to_have_js_property("value", words)
    expect(earlier).to_have_js_property("selectionStart", 1)
    expect(earlier).to_have_js_property("selectionEnd", 1)
    assert earlier.evaluate("node => node === window.earlierEditor")
    page.keyboard.press("Shift+Tab")
    page.locator("#later-link").scroll_into_view_if_needed()
    go_to_address(page, "Link", "later-link")
    expect(page.locator("#p41")).to_be_focused()
    expect(earlier).not_to_be_in_viewport()

    # Comment at the later item opens that item's own draft; the earlier words stay
    # with Paragraph 3, where Resume writing still leads.
    page.keyboard.press("c")
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", "")
    expect(field).to_have_attribute("aria-label", re.compile("Paragraph 41"))
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", words)
    expect(field).to_have_attribute("aria-label", re.compile("Paragraph 3"))
    expect(field).to_have_js_property("selectionStart", 1)
    with sending(page, "comment"):
        page.keyboard.press("Enter")
    sent = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [(event["text"], event["anchor"]) for event in sent] == [
        (words, {"section": "p3"})
    ]


def test_an_explicit_target_does_not_overwrite_its_existing_draft(
    browser, serve, one_user
):
    """A deliberate retarget opens the destination's own draft.

    Two passages may already hold independent work. Choosing the second from the first
    tab should therefore reopen the draft at the chosen destination and leave the source
    draft where it was, rather than tombstoning the source and replacing the destination.
    The target picker is the real explicit gesture.
    """
    url = serve(
        leaf_page(
            "Neighbouring comment targets",
            "<h1>Independent notes</h1>"
            + "".join(
                f'<p id="p{i}" style="margin:0;line-height:16px">Paragraph {i}.</p>'
                for i in range(12)
            ),
        )
    )
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)

    source = "This paragraph buries the point."
    destination = "This later paragraph already has its own note."
    choose_comment_target(first, "#p3")
    expect(first.locator(".lf-fab-input")).to_have_attribute(
        "aria-label", re.compile("Paragraph 3")
    )
    write(first.locator(".lf-fab-input"), source)
    choose_comment_target(second, "#p9")
    expect(second.locator(".lf-fab-input")).to_have_attribute(
        "aria-label", re.compile("Paragraph 9")
    )
    write(second.locator(".lf-fab-input"), destination)

    first.keyboard.press("Escape")
    expect(first.locator(".lf-composer")).to_be_hidden()
    choose_comment_target(first, "#p9")
    expect(first.locator(".lf-fab-input")).to_have_js_property("value", destination)

    first.keyboard.press("Escape")
    choose_comment_target(first, "#p3")
    expect(first.locator(".lf-fab-input")).to_have_js_property("value", source)


def test_a_draft_stays_with_its_subject_where_threads_lists_it(browser, serve):
    """Unsent words stay with what they are about. Comment on another target opens
    that target's own empty draft and says the earlier one is kept, and `c` into a
    thread opens the thread's reply. Threads lists every such draft under Drafts, in the
    page's order, each reading its words, what it is about and what Send makes of it,
    and a press on one resumes it in its own box with the caret after its words."""
    page = open_page(browser, serve(LONG_PAGE, anchored=[("p41", "Paragraph 41.")]))
    field = page.locator(".lf-fab-input")
    ninth = "About the ninth paragraph."
    choose_comment_target(page, "#p9")
    write(field, ninth)
    page.locator("#p3").scroll_into_view_if_needed()
    page.locator("#p3").click(modifiers=["Alt"])
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", "")
    expect(field).to_have_attribute("aria-label", re.compile("Paragraph 3"))
    expect_panel_says(page, "Draft kept")
    write(field, "About the third.")
    # On the anchored thread, which a press on its marker opens with the caret in its
    # reply, and Escape leaves the reply for.
    page.locator('[data-lf-margin-for="p41"] .lf-margin-marker').click()
    page.keyboard.press("Escape")
    page.keyboard.press("c")
    reply = page.locator(".lf-margin-preview .lf-page-thread leaf-text")
    expect(reply).to_be_focused()
    expect(reply).to_have_js_property("value", "")
    write(reply, "A reply to the anchored thread.")
    page.keyboard.press("Escape")

    open_threads(page)
    rows = page.locator(".lf-fp-draft")
    expect(rows).to_have_count(3)
    for row, (words, about, kind) in zip(
        rows.all(),
        [
            ("About the third.", "Paragraph 3", "Comment"),
            (ninth, "Paragraph 9", "Comment"),
            # A reply names its thread, which the fixture's comment names.
            ("A reply to the anchored thread.", "About this bit.", "Reply"),
        ],
        strict=True,
    ):
        expect(row.locator(".lf-row-main")).to_contain_text(words)
        expect(row.locator(".lf-fp-note")).to_contain_text(about)
        expect(row.locator(".lf-row-end")).to_have_text(kind)

    rows.nth(1).click()
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", ninth)
    expect(field).to_have_attribute("aria-label", re.compile("Paragraph 9"))
    expect(field).to_have_js_property("selectionStart", len(ninth))
    expect(page.locator(".lf-floating-panel")).not_to_have_attribute(
        "data-lf-open", "threads"
    )


def test_a_put_away_draft_dots_the_leaf_grey(browser, serve):
    """Where no thread has news, a draft the user put away dots the leaf grey, and a
    press on the leaf opens Threads, where Drafts lists it."""
    page = open_page(browser, serve(LONG_PAGE))
    field = page.locator(".lf-fab-input")
    mark = page.locator(".lf-fp-leaf")
    dot = mark.locator(".lf-fp-news-dot")
    expect(dot).to_be_hidden()
    choose_comment_target(page, "#p9")
    write(field, "About the ninth paragraph.")
    page.keyboard.press("Escape")
    expect_panel_says(page, "Draft kept")
    expect(dot).to_be_visible()
    expect(dot).to_have_attribute("data-lf-drafts", "")
    expect(mark).to_have_accessible_name(re.compile("1 draft unsent"))

    mark.click()
    expect(page.locator(".lf-floating-panel")).to_have_attribute(
        "data-lf-open", "threads"
    )
    expect(page.locator(".lf-fp-draft")).to_have_count(1)


def test_a_draft_stands_in_the_margin_where_it_is_about(browser, serve):
    """A comment draft stands as a margin entry at its passage, and a reply draft
    beside its thread's entry, each in an ink apart from a thread's; a press on one
    resumes it in its own box."""
    page = open_page(browser, serve(LONG_PAGE, anchored=[("p41", "Paragraph 41.")]))
    field = page.locator(".lf-fab-input")
    drafts = page.locator('.lf-margin-face[data-lf-kinds="draft"]')
    ninth = "About the ninth paragraph."
    choose_comment_target(page, "#p9")
    write(field, ninth)
    page.keyboard.press("Escape")
    expect(drafts).to_have_count(1)
    expect(drafts).to_have_accessible_name(re.compile("^Draft.*Paragraph 9"))
    page.locator('[data-lf-margin-for="p41"] .lf-margin-marker').click()
    reply = page.locator(".lf-margin-preview .lf-page-thread leaf-text")
    expect(reply).to_be_focused()
    write(reply, "A reply to the anchored thread.")
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(drafts).to_have_count(2)
    thread = page.locator('.lf-margin-face[data-lf-kinds~="comment"]')
    expect(thread).to_have_attribute("data-lf-kinds", "comment draft")
    ink = "n => getComputedStyle(n.querySelector('.lf-margin-entry-icon')).color"
    assert thread.evaluate(ink) not in drafts.evaluate_all(f"ns => ns.map({ink})")

    drafts.first.click()
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", ninth)


def test_page_map_reads_a_listed_draft_as_it_now_stands(browser, serve):
    """Words added to a draft already in the margin reach its Page Map row, though the
    drafts list publishes no keystroke."""
    page = open_page(browser, serve(LONG_PAGE))
    field = page.locator(".lf-fab-input")
    draft = page.locator('.lf-margin-face[data-lf-kinds="draft"]')
    choose_comment_target(page, "#p9")
    write(field, "About the ninth paragraph.")
    page.keyboard.press("Escape")
    draft.click()
    expect(field).to_be_focused()
    field.press("End")
    page.keyboard.type(" More words added later.")
    page.keyboard.press("Escape")
    page.evaluate("() => document.activeElement?.blur()")
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    expect(page.locator(".lf-page-map-list")).to_contain_text("More words added later")


def test_drafts_stand_by_their_own_passage_and_outlast_a_resolved_thread(
    browser, serve
):
    """Drafts about two passages of one paragraph stand apart, each by its passage,
    and a reply draft keeps its entry when its thread is resolved."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Two passages",
                '<p id="two">The first passage stands here and the second passage'
                " stands there.</p>",
            ),
            anchored=[("two", "The first passage")],
        ),
    )
    field = page.locator(".lf-fab-input")
    drafts = page.locator('.lf-margin-face[data-lf-kinds="draft"]')
    for words in ("first passage", "second passage"):
        page.evaluate(
            """words => {
              const text = document.getElementById('two').firstChild;
              const at = text.data.indexOf(words);
              const range = document.createRange();
              range.setStart(text, at);
              range.setEnd(text, at + words.length);
              getSelection().removeAllRanges();
              getSelection().addRange(range);
            }""",
            words,
        )
        page.keyboard.press("c")
        expect(field).to_be_focused()
        write(field, f"About the {words}.")
        page.keyboard.press("Escape")
    expect(drafts).to_have_count(2)
    tops = drafts.evaluate_all(
        "nodes => nodes.map(node => node.getBoundingClientRect().top)"
    )
    assert len(set(tops)) == 2

    page.evaluate("() => document.activeElement?.blur()")
    page.keyboard.press("t")
    page.keyboard.press("c")
    reply = page.locator(".lf-margin-preview .lf-page-thread leaf-text")
    expect(reply).to_be_focused()
    write(reply, "A reply left unsent.")
    page.locator(".lf-margin-preview .lf-resolve").click()
    expect(page.locator('.lf-margin-face[data-lf-kinds~="comment"]')).to_have_count(0)
    expect(drafts).to_have_count(3)


def test_a_delayed_draft_close_yields_to_a_newer_page_selection(browser, serve):
    """Returning editor focus cannot overwrite a real gesture made before that handoff."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Close focus",
                '<p id="reading">Another passage for the reader to select.</p>'
                '<lf-draft id="local"><pre>Editable source.</pre></lf-draft>',
            )
        ),
        init_script="""(() => {
          const frame=requestAnimationFrame.bind(window);
          window.heldFrames=[];window.holdFrames=false;
          window.requestAnimationFrame=callback=>frame(now=>{
            if(window.holdFrames)heldFrames.push(callback);else callback(now);
          });
          window.releaseFrames=()=>{
            window.holdFrames=false;
            const callbacks=heldFrames.splice(0);
            frame(now=>callbacks.forEach(callback=>callback(now)));
          };
        })();""",
    )
    draft_control(page, "edit", "local").click()
    expect(page.locator("#local leaf-text")).to_be_focused()
    rendered(page)
    page.evaluate("""async()=>{
      const {observeQueuedWork}=await window.__lfLibImport('queued-work.js');
      window.closeJobs=new Set();window.captureClose=true;
      window.stopCloseObserver=observeQueuedWork((phase,job)=>{
        if(phase==='enqueue'&&captureClose)closeJobs.add(job);
        if(phase==='finish'||phase==='cancel')closeJobs.delete(job);
      });
      window.holdFrames=true;
    }""")
    page.keyboard.press("Escape")
    page.evaluate("window.captureClose=false")
    expect(page.locator("#local leaf-text")).to_have_count(0)
    page.wait_for_function("heldFrames.length>0", polling=20)
    assert page.evaluate("closeJobs.size") > 0
    start, end = page.locator("#reading").evaluate("""p=>[2,24].map(at=>{
      const range=new Range();range.setStart(p.firstChild,at);range.setEnd(p.firstChild,at+1);
      const box=range.getBoundingClientRect();return [box.left+0.01,box.top+box.height/2];
    })""")
    page.mouse.move(*start)
    page.mouse.down()
    page.mouse.move(*end, steps=5)
    page.mouse.up()
    selected = page.evaluate("getSelection().toString()")
    assert selected
    assert page.evaluate("document.activeElement===document.body")
    page.evaluate("releaseFrames()")
    page.wait_for_function("closeJobs.size===0", polling=20)
    rendered(page)
    assert page.evaluate("document.activeElement===document.body")
    # The shared selection owner may expand partial words; the newer passage remains.
    assert selected in page.evaluate("getSelection().toString()")
    page.evaluate("stopCloseObserver()")


@pytest.mark.parametrize("edited", [False, True], ids=["seed", "edited"])
def test_commenting_on_the_same_selection_preserves_the_existing_suggestion(
    browser, serve, edited
):
    """Activating an already captured passage focuses its existing draft and mode."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Selection mode",
                '<h1>Selection mode</h1><p id="words">The same selected passage.</p>',
            )
        ),
    )
    select_words(page, "#words")
    page.keyboard.press("c")
    editor = page.locator(".lf-fab-input")
    expect(editor).to_be_focused()
    page.keyboard.press("Tab")
    page.locator(".lf-fab-suggest").click()
    expect(editor).to_have_attribute("placeholder", re.compile(r"^Replacement text"))
    words = "My replacement" if edited else "The same selected passage."
    if edited:
        write(editor, words)
    select_words(page, "#words")
    rendered(page)
    page.keyboard.press("c")
    expect(editor).to_be_focused()
    expect(editor).to_have_js_property("value", words)
    expect(editor).to_have_attribute("placeholder", re.compile(r"^Replacement text"))


def datum_draft_url(serve, *, identified=False):
    """Serve a projected subject whose rendering can change independently of its identity."""
    module = """
import { html } from '/vendor/lit.js';
import { LeafElement } from '/runtime/lib/leaf-element.js';
customElements.define('lf-draft-subject', class extends LeafElement {
  static properties = {words: {attribute: false}, key: {attribute: false}};
  constructor() {
    super();
    this.words = 'Original datum words.';
    this.key = 'datum';
  }
  show(words, key = 'datum') {
    this.words = words;
    this.key = key;
  }
  render() {
    return html`<p data-lf-datum=${this.key} IDENTITY data-lf-datum-label="Datum"
      >${this.words}</p><p>Other words in the same widget.</p>`;
  }
  updated(changed) {
    super.updated(changed);
    this.dispatchEvent(new CustomEvent('drawn', {detail: {value: this.words}}));
  }
});
"""
    module = module.replace(
        "IDENTITY", 'data-lf-identity="subject"' if identified else ""
    )
    return serve(
        leaf_page("Datum draft", '<lf-draft-subject id="subject"></lf-draft-subject>'),
        layer_registry={
            "lf-draft-subject": {
                "description": "A datum whose words can change.",
                "attributes": {
                    "properties": {
                        "source": {"type": "string"},
                    },
                    "required": ["id"],
                },
                "content": "empty",
                "inputs": {
                    "words": {
                        "contract": "text-document",
                        "source": "source",
                        "property": "value",
                    }
                },
                "example": '<lf-draft-subject id="example"></lf-draft-subject>',
            }
        },
        layer_widgets={"lf-draft-subject.js": module},
    )


def test_changed_datum_words_keep_the_draft_on_that_datum(browser, serve):
    """The resolver's canonical datum fallback owns placement after its quote changes."""
    page = open_page(browser, datum_draft_url(serve))
    select_words(page, "#subject p:first-child")
    page.keyboard.press("c")
    field = page.locator(".lf-fab-input")
    write(field, "Keep this datum's original quotation.")
    page.locator("#subject").evaluate("el => el.show('Changed datum words.')")
    rendered(page)
    expect(field).to_be_focused()
    attachment = page.locator(".lf-fab-bar").evaluate("""bar => {
      let frame = bar;
      while (getComputedStyle(frame).positionAnchor === 'auto') frame=frame.parentElement;
      return {name: getComputedStyle(frame).positionAnchor,
        datum: getComputedStyle(document.querySelector('#subject p')).anchorName};
    }""")
    assert attachment["name"] in attachment["datum"].split(", "), attachment


def test_a_mirrored_datum_retarget_does_not_reopen_a_dismissed_response(
    browser, serve, one_user
):
    url = datum_draft_url(serve, identified=True)
    first = open_page(browser, url, context=one_user)
    first.locator("#subject p:first-child").click(modifiers=["Alt"])
    write(first.locator(".lf-fab-input"), "A shared identified subject.")
    first.keyboard.press("Escape")
    first.mouse.click(5, 600)
    expect(first.locator(".lf-fab-bar")).not_to_be_visible()
    second = open_page(browser, url, context=one_user)
    second.keyboard.press("Escape")
    second.locator("#subject").evaluate(
        "el => el.show('Original datum words.', 'next')"
    )
    rendered(second)
    second.locator("#subject p:first-child").click(modifiers=["Alt"])
    words = "This rendering is now the shared draft's subject."
    write(second.locator(".lf-fab-input"), words)
    expect(first.locator(".lf-fab-input")).to_have_js_property("value", words)
    expect(first.locator(".lf-fab-bar")).not_to_be_visible()
