"""Which passage an unsent comment belongs to as the user selects, retargets, revisits
or moves to another location, and whose words a transfer carries."""

import re

import pytest
from playwright.sync_api import expect
from render_cases_navigation import compose, go_to_address, pending_text
from render_harness import (
    LONG_PAGE,
    draft_control,
    draft_key,
    hold_selection,
    leaf_page,
    open_page,
    scroll_settled,
    select_words,
    selection_field,
    sending,
    write,
)

from browser.drafts import (
    choose_comment_target,
)
from leaf import event_log as events_model
from leaf.render_checks import rendered, wait_until_ready
from leaf_dev.browser import slow_cpu

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
                '<p id="later">A later passage keeps native selection.</p>'
                '<p id="later-box" class="scroll" style="height:72px;overflow:auto">'
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
    assert (
        page.evaluate(
            """prefix => Object.keys(localStorage)
          .filter(key => key.startsWith(prefix)).length""",
            draft_key(page, "composer:"),
        )
        == 1
    )

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
    words = "Carry these unfinished words to the item I am at now."
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

    page.keyboard.press("c")
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", words)
    expect(field).to_have_attribute("aria-label", re.compile("Paragraph 41"))
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", words)
    expect(field).to_have_attribute("aria-label", re.compile("Paragraph 41"))
    expect(field).to_have_js_property("selectionStart", 1)
    with sending(page, "comment"):
        page.keyboard.press("Enter")
    sent = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [(event["text"], event["anchor"]) for event in sent] == [
        (words, {"section": "p41"})
    ]


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


@pytest.mark.parametrize("destination", ["passage", "reply"])
def test_a_transfer_keeps_its_persisted_source_when_the_destination_write_fails(
    browser, serve, destination
):
    """A failed larger destination write cannot be followed by a smaller tombstone."""
    page = open_page(browser, serve(LONG_PAGE, anchored=[("p41", "Paragraph 41.")]))
    words = "The only persisted copy must survive the transfer and reload."
    choose_comment_target(page, "#p3")
    write(page.locator(".lf-fab-input"), words)
    page.evaluate(
        """prefix => {
          const set = Storage.prototype.setItem;
          window.lfRefusedTransferWrites = 0;
          Storage.prototype.setItem = function (key, value) {
            if (key.startsWith(prefix) && !JSON.parse(value).settled) {
              window.lfRefusedTransferWrites++;
              throw new DOMException('full', 'QuotaExceededError');
            }
            return set.call(this, key, value);
          };
        }""",
        draft_key(page, ""),
    )
    if destination == "passage":
        page.keyboard.press("Escape")
        choose_comment_target(page, "#p9")
        field = page.locator(".lf-fab-input")
    else:
        page.keyboard.press("Shift+Tab")
        page.keyboard.press("t")
        page.keyboard.press("c")
        field = page.locator(".lf-margin-preview .lf-page-thread leaf-text")
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", words)
    assert page.evaluate("() => window.lfRefusedTransferWrites") > 0

    page.reload()
    wait_until_ready(page)
    page.keyboard.press("Escape")
    choose_comment_target(page, "#p3")
    expect(page.locator(".lf-fab-input")).to_have_js_property("value", words)


def test_an_explicit_target_does_not_overwrite_its_existing_draft(
    browser, serve, one_user
):
    """A deliberate retarget carries words only into an empty passage.

    Two passages may already hold independent work. Choosing the second from the first
    tab should therefore reopen the draft at the chosen destination and leave the source
    draft where it was, rather than tombstoning the source and replacing the destination.
    The target picker is the real explicit gesture whose carry path owns that choice.
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


def test_an_explicit_target_carries_into_an_emptied_draft(browser, serve):
    """A cleared destination record holds no work that should outrank a carried draft."""
    page = open_page(browser, serve(LONG_PAGE))
    field = page.locator(".lf-fab-input")

    choose_comment_target(page, "#p9")
    write(field, "Words the user removes.")
    write(field, "")
    page.keyboard.press("Escape")

    source = "Words to carry to the later paragraph."
    choose_comment_target(page, "#p3")
    write(field, source)
    page.keyboard.press("Escape")
    choose_comment_target(page, "#p9")
    expect(field).to_have_js_property("value", source)


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
      const {observeQueuedWork}=await window.__lfCheckApi();
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
import {LeafElement, html} from '/runtime/widget-api.js';
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
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "source": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$"},
                },
                "required": ["id"],
                "additionalProperties": False,
                "x-content": "empty",
                "x-data": {
                    "words": {
                        "contract": "text-document",
                        "source": "source",
                        "property": "value",
                    }
                },
                "x-upgrade": True,
                "x-example": '<lf-draft-subject id="example"></lf-draft-subject>',
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
