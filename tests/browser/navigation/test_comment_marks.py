"""Comment marks painted on the page, the cues that tie them to their thread cards, and
the notes that tell a screen reader of them."""

import re

import pytest
from interact_support import append_carried_log_record
from leaf import event_log as events_model
from leaf.render_checks import rendered
from playwright.sync_api import expect
from render_cases_interaction import HOLD_MOTION, live_url
from render_cases_layout import in_threads_scrollport, page_at_rest
from render_cases_navigation import (
    COMMENTED_LIST_PAGE,
    NOTED_PAGE,
    _publish,
    card_body,
    composer_quote,
    mark_point,
    painted,
    pending_text,
    standing_mark,
    wait_for_pending_mark,
    wait_hovered,
    wait_standing,
)
from render_harness import (
    INLINE_PAGE,
    accessible_details,
    comment_note,
    expect_comment_notes,
    open_page,
    panel_settled,
    post_event,
    resized,
    round_trip,
    select,
    shortcut_bar_text,
    stamp_page,
    told,
    wait_for_revision,
    write,
)

from browser.navigation import (
    color_cue_markup,
)

pytestmark = pytest.mark.shifts_unsurveyed


# Each surface once and each engine once.
@pytest.mark.parametrize(
    ("target", "engine"), [("banner", "browser"), ("tab", "firefox_browser")]
)
def test_color_cues_fade_to_the_live_surface(request, serve, engine, target):
    """Transient paint fades smoothly and returns to current hover or theme fill."""
    page = open_page(request.getfixturevalue(engine), serve(color_cue_markup()))
    page.emulate_media(reduced_motion="no-preference")
    page.evaluate("() => {" + HOLD_MOTION + "}")
    if target == "tab":
        page.keyboard.press("m")
        expect(page.locator("#ask-first")).to_be_focused()
        page.keyboard.press("m")
        expect(page.locator("#ask-second")).to_be_focused()
        cue_target = page.locator('#views [aria-controls="second"] .lf-tab-name')
    else:
        page.keyboard.press("c")
        box = page.locator(".lf-page-comment-card leaf-text")
        expect(box).to_be_focused()
        write(box, "Review both choices.")
        page.keyboard.press("Enter")
        card = page.locator(".lf-page-comment-card")
        expect(card).to_be_hidden()
        expect(page.locator(".lf-page-comment")).to_be_focused()
        cue_target = page.locator(".lf-threads-toggle")
    colours = cue_target.evaluate(
        """async node => {
          const cue = node.getAnimations()[0];
          if (!cue) throw new Error('the gesture has no color cue');
          cue.pause();
          const duration = cue.effect.getComputedTiming().endTime;
          const colours = [];
          for (const fraction of [0, .25, .5, .75, .99]) {
            cue.currentTime = duration * fraction;
            await new Promise(requestAnimationFrame);
            colours.push(getComputedStyle(node).backgroundColor);
          }
          return colours;
        }"""
    )
    assert len(set(colours)) >= 4, colours
    if target == "tab":
        page.emulate_media(color_scheme="dark")
    else:
        cue_target.hover()
    fills = cue_target.evaluate(
        """async node => {
          const cue = node.getAnimations()[0];
          cue.effect.updateTiming({fill: 'forwards'});
          cue.currentTime = cue.effect.getComputedTiming().endTime;
          await new Promise(requestAnimationFrame);
          const end = getComputedStyle(node).backgroundColor;
          cue.cancel();
          await new Promise(requestAnimationFrame);
          return {end, rest: getComputedStyle(node).backgroundColor};
        }"""
    )
    assert fills["end"] == fills["rest"], fills


def test_composer_marks_the_passage_instead_of_quoting_it(browser, serve):
    """The passage stays visible while its comment is written. Focus moves into the
    composer the moment it opens, which drops the browser's own selection, so the
    runtime paints the anchor itself, and repaints it after every pass that redraws
    the posted threads' marks around it — otherwise a comment arriving mid-sentence
    would leave the user's passage stranded across stale text nodes. It comes down
    with the box, and the whole time it never touches the document.

    And because the mark says which passage the box is on, the box doesn't say it too:
    the quote inside it stays out of sight while the page is marking the passage."""
    url = serve(INLINE_PAGE)
    page = open_page(browser, url)

    page.locator("#p").click(
        click_count=3
    )  # a real selection, spanning the inline tags
    page.keyboard.press("c")
    page.locator(".lf-fab-input").click()
    page.wait_for_function(
        "() => document.querySelector('.lf-composer').hasAttribute('data-lf-open')"
    )

    passage = " ".join(page.locator("#p").inner_text().split())
    quote = composer_quote(page)
    assert pending_text(page) == passage, (
        f"the page marks {pending_text(page)!r}, but the composer is anchored to {quote['text']!r}"
    )
    assert not quote["shown"], (
        f"the passage is marked on the page and the composer prints it as well: {quote['text']!r}"
    )
    # Out of sight, not gone: it is what the box's description resolves to, and a screen
    # reader hears nothing from a painted mark.
    assert quote["text"] == f"“{passage}”", (
        f"the composer's description of its passage says {quote['text']!r}"
    )
    assert (
        page.evaluate(
            "() => document.querySelector('.lf-composer leaf-text').getAttribute('aria-describedby')"
        )
        == "lf-composer-quote"
    ), "nothing announces what the box is anchored to"
    # Carrying that description costs the node an id, which is what makes it the one piece
    # of injected chrome that could answer "which section of the document is this in" with
    # itself. The reading position rides on that answer, so a reload would scroll to the
    # comment box instead of to the page.
    assert (
        page.evaluate(
            "() => document.getElementById('lf-composer-quote')"
            ".closest('[id]:not(.lf-ui)')?.id ?? null"
        )
        is None
    ), "the composer's own quote offers itself as a landmark in the document"

    # A comment landing from elsewhere re-runs the anchor pass, which splits the text
    # nodes the painted range is pinned to. The user is mid-sentence; their passage
    # can neither blink out nor come back covering the wrong words.
    post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "comment",
            "revision": 1,
            "text": "arriving mid-sentence",
            "anchor": {"section": "p", "quote": "bold text"},
        },
    )
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    assert pending_text(page) == passage, (
        "a poll landing while the composer is open disturbed the passage"
    )

    page.keyboard.press("Escape")
    assert pending_text(page) == "", "the highlight outlived its composer"

    # A selection across two options crosses their passage fence, so the composer
    # shows its detached quote. The widget's own control is not part of that quote.
    chrome = page.locator("#opts .lf-pick").first.text_content().strip()
    assert chrome, "this assertion needs the widget to have rendered chrome inside it"
    page.evaluate("""() => {
        const r = document.createRange();
        r.selectNodeContents(document.querySelector('#opts'));
        const s = getSelection(); s.removeAllRanges(); s.addRange(r);
        document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
    }""")
    page.get_by_role("button", name="Comment on selection", exact=True).click()
    page.locator(".lf-fab-input").click()
    quote = composer_quote(page)
    assert quote["shown"], "a selection across option cells cannot paint one passage"
    assert "Keep the store" in quote["text"]
    assert "Signed tokens" in quote["text"]
    assert chrome not in quote["text"], (
        f"the detached quote included the widget's own {chrome!r} control"
    )
    assert pending_text(page) == ""
    page.keyboard.press("Escape")

    # A diagram has no text to quote, so its anchor is the element and its mark is an
    # outline. That one the anchor pass really does take down, so it has to be redrawn.
    page.locator("#fig svg").click(modifiers=["Alt"])
    page.locator(".lf-fab-input").click()
    page.locator("#fig.lf-mark-el.lf-pending").wait_for()
    assert not composer_quote(page)["shown"], (
        "the outline is on the figure and the composer names its section as well"
    )
    post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={"kind": "comment", "revision": 1, "text": "and another"},
    )
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 2")
    assert page.locator("#fig.lf-mark-el.lf-pending").count() == 1, (
        "a poll landing while the composer is open dropped the outline"
    )

    # Both classes have to go, asserted apart: leaving .lf-mark-el behind repaints the
    # figure in the posted mark's own ink, pointer cursor and all, over no thread to open.
    page.keyboard.press("Escape")
    assert page.locator("#fig.lf-pending").count() == 0, (
        "the mark outlived its composer"
    )
    assert page.locator("#fig.lf-mark-el").count() == 0, (
        "the figure kept a thread's mark over no thread"
    )

    # A drag across the caption remains a native selection, so the composer carries the
    # caption's words rather than the enclosing figure's element anchor.
    cap = page.locator("#fig figcaption").bounding_box()
    y = cap["y"] + cap["height"] / 2
    select(page, (cap["x"] + 2, y), (cap["x"] + cap["width"] - 2, y))
    page.locator(".lf-fab-input").click()
    wait_for_pending_mark(page)
    assert "sample" in pending_text(page), (
        "the visual containing the drag replaced its selected passage"
    )
    assert page.locator("#fig.lf-pending").count() == 0, (
        "the figure got the element mark over a live selection"
    )
    page.keyboard.press("Escape")


def test_the_pointer_over_a_page_mark_lights_its_comment_quote(browser, serve):
    """The page and panel are reciprocal views of a thread. Resting on a card lights
    its passage; resting on that passage must identify the bounded quote naming it too.
    Filling the card instead turns a long thread into a viewport-sized wash. The
    signal follows the pointer from one thread to the next and leaves with it."""
    url = serve(
        INLINE_PAGE,
        anchored=[("p", "bold text"), ("p2", "neighbouring block")],
    )
    comments = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    first_id, second_id = (comment["id"] for comment in comments)
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    first = page.locator(f'.lf-thread[data-id="{first_id}"]')
    second = page.locator(f'.lf-thread[data-id="{second_id}"]')
    first.locator(".lf-thread-summary").click()
    page.mouse.move(2, 2)
    expect(first).not_to_have_class(re.compile(r"\blf-mark-hover\b"))
    first_quote = first.locator(".lf-thread-head > .lf-quote")
    resting = first.evaluate("element => getComputedStyle(element).backgroundColor")
    quote_resting = first_quote.evaluate(
        "element => getComputedStyle(element).backgroundColor"
    )
    page.mouse.move(*mark_point(page, "lf-mark", 0))
    expect(first).to_have_class(re.compile(r"\blf-mark-hover\b"))
    expect(second).not_to_have_class(re.compile(r"\blf-mark-hover\b"))
    assert (
        first.evaluate("element => getComputedStyle(element).backgroundColor")
        == resting
    ), "pointing at a passage washed the whole thread card instead of its quote"
    quote_lit = first_quote.evaluate(
        "element => getComputedStyle(element).backgroundColor"
    )
    assert quote_lit != quote_resting, (
        f"the page named the quote in class but its paint stayed {quote_resting!r}"
    )
    assert first_quote.bounding_box()["height"] < first.bounding_box()["height"]

    page.mouse.move(*mark_point(page, "lf-mark", 1))
    expect(first).not_to_have_class(re.compile(r"\blf-mark-hover\b"))
    expect(second).to_have_class(re.compile(r"\blf-mark-hover\b"))

    page.mouse.move(2, 2)
    expect(page.locator(".lf-thread.lf-mark-hover")).to_have_count(0)

    # A narrowing can put a different card under a hand that has not moved. The list
    # reconcile is therefore one of the hover's inputs, just like page geometry.
    page.get_by_role("searchbox", name="Find in threads").fill("About")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(2)
    first.locator(".lf-thread-summary").click()
    first.locator(".lf-thread-summary").hover()
    wait_hovered(page, "bold text")
    page.get_by_role("searchbox", name="Find in threads").fill("neighbouring block")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(1)
    expect(second).to_have_class(re.compile(r"\blf-mark-hover\b"))
    wait_hovered(page, "neighbouring block")


@pytest.mark.parametrize("route", ["passage-press", "note-enter"])
def test_a_page_mark_flashes_its_panel_destination_without_page_travel(
    browser, serve, route
):
    """Opening a thread from its passage still cues the destination in an open panel."""
    page = open_page(browser, serve(INLINE_PAGE, anchored=[("p", "bold text")]))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.evaluate("""() => {
      window.__panelArrivalFlashed = false;
      const thread = document.querySelector('.lf-threads > .lf-thread');
      const observer = new MutationObserver(() => {
        if (!thread.classList.contains('flash')) return;
        window.__panelArrivalFlashed = true;
        observer.disconnect();
      });
      observer.observe(thread, {attributes: true, attributeFilter: ['class']});
    }""")
    if route == "passage-press":
        page.mouse.click(*mark_point(page, "lf-mark"))
        expect(page.locator(".lf-threads > .lf-thread leaf-text")).to_be_focused()
    else:
        comment_note(page, "#p").press("Enter")
        expect(page.locator(".lf-threads > .lf-thread > summary")).to_be_focused()
    assert page.evaluate("window.__panelArrivalFlashed"), "the destination lost its cue"


def test_a_page_mark_does_not_wash_a_long_thread_card(browser, serve):
    """The reciprocal cue stays at the quote when its thread is taller than the
    list. A short-card case proves selector routing but cannot reproduce the full-panel
    slab that made direct navigation visually ambiguous."""
    url = serve(INLINE_PAGE, anchored=[("p", "bold text")])
    root = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": root,
            "revision": 1,
            "text": "\n\n".join(
                f"Consideration {i}: this thread needs its full context."
                for i in range(24)
            ),
        },
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(f'.lf-thread[data-id="{root}"]')
    thread.locator(".lf-thread-summary").click()
    page.mouse.move(2, 2)
    expect(thread).not_to_have_class(re.compile(r"\blf-mark-hover\b"))
    quote = thread.locator(".lf-thread-head > .lf-quote")
    card_resting = thread.evaluate(
        "element => getComputedStyle(element).backgroundColor"
    )
    quote_resting = quote.evaluate(
        "element => getComputedStyle(element).backgroundColor"
    )
    assert (
        thread.bounding_box()["height"]
        > page.locator(".lf-threads").bounding_box()["height"]
    ), "the card fits in the list, so this does not reproduce the large wash"

    page.mouse.move(*mark_point(page, "lf-mark"))
    expect(thread).to_have_class(re.compile(r"\blf-mark-hover\b"))
    assert (
        thread.evaluate("element => getComputedStyle(element).backgroundColor")
        == card_resting
    )
    assert (
        quote.evaluate("element => getComputedStyle(element).backgroundColor")
        != quote_resting
    )
    assert (
        quote.bounding_box()["height"]
        < page.locator(".lf-threads").bounding_box()["height"]
    )


@pytest.mark.parametrize(
    "reply_paragraphs",
    # Either side of the card's fit, and a reply that does not fit at all.
    [0, 10, 18],
    ids=["short", "near-fit", "long"],
)
def test_pressing_a_page_mark_stands_in_the_thread_it_opens(
    browser, serve, reply_paragraphs
):
    """Pointer and keyboard arrival open one compact thread card. Enter or c
    enters its reply, and Escape returns through each layer. The Page Map fallback
    remains live at the same time: declaration order cannot move it ahead of the causal
    frame. The page mark follows both focus modes."""
    url = serve(
        INLINE_PAGE, anchored=[("p", "bold text"), ("p2", "neighbouring block")]
    )
    if reply_paragraphs:
        root = next(
            event["id"]
            for event in events_model.read_events(serve.page_dir)
            if event["kind"] == "comment"
        )
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "parent": root,
                "revision": 1,
                "text": "\n\n".join(
                    f"Consideration {i}: the response needs room for its explanation."
                    for i in range(reply_paragraphs)
                ),
            },
        )
    page = open_page(browser, url)
    page.emulate_media(reduced_motion="reduce")
    threads = page.locator(".lf-threads > .lf-thread:not([hidden])")
    first_id = threads.first.get_attribute("data-id")
    second_id = threads.nth(1).get_attribute("data-id")
    thread = page.locator(
        f'.lf-margin-preview .lf-page-thread[data-thread="{first_id}"]'
    )
    second = page.locator(
        f'.lf-margin-preview .lf-page-thread[data-thread="{second_id}"]'
    )
    reply = thread.locator("leaf-text")

    page.mouse.click(*mark_point(page, "lf-mark"))
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator(".lf-thread-panel")).not_to_have_class(re.compile(r"\bopen\b"))

    expect(thread).to_be_focused()
    expect(reply).to_be_visible()
    wait_standing(page, "bold text")
    assert "back to element" in shortcut_bar_text(page)
    page.keyboard.press("Enter")
    expect(reply).to_be_focused()
    expect(reply).to_be_visible()
    page.keyboard.type("t")
    expect(reply).to_have_js_property("value", "t")
    expect(reply).to_be_focused()
    page.keyboard.press("Escape")
    expect(thread).to_be_focused()
    page.keyboard.press("Escape")  # onto the element the thread is about
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    comment_note(page, "#p").press("Enter")
    expect(thread).to_be_focused()
    assert "reply" in shortcut_bar_text(page)
    # The note reopened this view without a trip, so the Page Map rung is the way out.
    # A sequence armed afterward is an inner interaction; Escape cancels it first.
    page.keyboard.press("g")
    assert "cancel" in shortcut_bar_text(page)
    page.keyboard.press("Escape")
    expect(thread).to_be_focused()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    page.keyboard.press("c")
    expect(reply).to_be_focused()
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("back to thread")
    page.keyboard.press("Escape")
    expect(thread).to_be_focused()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    page.keyboard.press("Escape")  # onto the element the thread is about
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    comment_note(page, "#p").press("Enter")
    expect(thread).to_be_focused()
    page.keyboard.press("t")
    expect(second).to_be_focused()
    wait_standing(page, "neighbouring block")
    page.keyboard.press("Enter")
    expect(second.locator("leaf-text")).to_be_focused()
    page.keyboard.press("Escape")
    expect(second).to_be_focused()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    page.keyboard.press("Escape")  # onto the element the thread is about
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    # Enter the known source before testing the directional walk. After Escape,
    # that walk starts from the visible passage rather than a saved card cursor.
    comment_note(page, "#p").press("Enter")
    expect(thread).to_be_focused()
    page.keyboard.press("t")
    expect(second).to_be_focused()
    page.keyboard.press("Shift+t")
    expect(thread).to_be_focused()
    page.keyboard.press("Enter")
    expect(reply).to_be_focused()
    expect(reply).to_be_visible()

    # With Threads already open, the same page mark takes the indexed route and keeps
    # the panel's long-thread landing guarantees.
    page.keyboard.press("Escape")
    expect(thread).to_be_focused()
    page.keyboard.press("Escape")  # onto the element the thread is about
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    panel_thread = threads.first
    panel_reply = panel_thread.locator(":scope > .lf-thread-reply leaf-text")
    page.mouse.click(*mark_point(page, "lf-mark"))
    expect(panel_reply).to_be_focused()
    in_threads_scrollport(
        page, ".lf-threads > .lf-thread:first-of-type .lf-thread-reply"
    )
    if reply_paragraphs:
        landing = page.evaluate(
            """() => {
              const list = document.querySelector('.lf-threads');
              const thread = list.querySelector('.lf-thread:first-of-type');
              const compose = thread.querySelector(':scope > .lf-thread-reply');
              const view = list.getBoundingClientRect();
              const target = compose.getBoundingClientRect();
              const clear = parseFloat(getComputedStyle(list).scrollPaddingTop) || 0;
              const start = view.top + clear;
              const contentStart = start +
                (parseFloat(getComputedStyle(compose).scrollMarginTop) || 0);
              // A turn's head is a block boundary as well as its paragraphs: a long
              // arrival starts the latest turn there.
              const blocks = [...thread.querySelectorAll(
                ':scope > *, :scope > .lf-thread-content > *, ' +
                '.lf-thread-transcript > :is(.lf-msg, .lf-thread-checkpoint), ' +
                '.lf-msg .lf-msg-body > *, .lf-msg .lf-msg-text > *'), compose]
                .map((block) => ({
                  name: block.className || block.tagName,
                  top: block.getBoundingClientRect().top,
                }));
              const lines = [];
              const walker = document.createTreeWalker(
                thread.querySelector('.lf-thread-content'), NodeFilter.SHOW_TEXT);
              for (let text; text = walker.nextNode();) {
                if (!text.data.trim()) continue;
                for (let i = 0; i < text.length; i++) {
                  const range = document.createRange();
                  range.setStart(text, i);
                  range.setEnd(text, Math.min(i + 1, text.length));
                  const line = range.getBoundingClientRect();
                  if (line.width && line.top < contentStart &&
                      line.bottom > contentStart)
                    lines.push(line.toJSON());
                }
              }
              return {target: target.toJSON(), listBottom: view.bottom,
                      start, contentStart, blocks,
                      crossedLines: lines, scroll: list.scrollTop,
                      maximumScroll: list.scrollHeight - list.clientHeight};
            }"""
        )
        assert landing["target"]["bottom"] <= landing["listBottom"]
        # A list scrolled to its limit has no travel left to align a content block.
        if landing["scroll"] and landing["scroll"] < landing["maximumScroll"] - 1:
            assert any(
                block["top"] == pytest.approx(landing["contentStart"], abs=2)
                for block in landing["blocks"]
            ), f"the long arrival cut through a content block: {landing}"
        elif landing["scroll"]:
            assert landing["target"]["top"] >= landing["start"] - 1
        else:
            assert landing["blocks"][0]["top"] >= landing["start"] - 1
        assert not landing["crossedLines"], (
            f"the pinned heading cut through a text line: {landing}"
        )


def test_the_page_marks_the_comment_the_user_is_standing_in(browser, serve):
    """A user sent from a comment to its passage lands among every other mark on the
    page, all of them painted alike. The page says which one they asked for too: the
    thread holding the focus paints its own passage apart from the rest for as long as
    the user remains in that thread.

    Read off the focus rather than off the travel, so it answers where the user *is*.
    The walk moves it, a reply box keeps it — standing in a comment is standing in it
    while writing back — and leaving the thread takes it down, rather than leaving a
    page wearing "you are here" about a comment nobody is in."""
    url = serve(INLINE_PAGE)
    page = open_page(browser, url)
    api = url.rsplit("/versions/", 1)[0] + "/api/event"
    for anchor, text in (
        ({"section": "p", "quote": "bold text"}, "on the first"),
        ({"section": "p2", "quote": "neighbouring block"}, "on the second"),
        ({"section": "fig"}, "on the figure"),
    ):
        post_event(
            page,
            api,
            data={"kind": "comment", "revision": 1, "text": text, "anchor": anchor},
        )
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) >= 2")
    page.locator("#fig.lf-mark-el").wait_for()

    assert standing_mark(page) == {
        "text": "",
        "elements": [],
    }, "a page nobody has opened a comment on is already saying the user is in one"

    page.keyboard.press("t")
    wait_standing(page, "bold text")

    # The four readings of a marked passage have to stay in this order, or one of them
    # stops being visible where they overlap: the posted mark, the hover over it, the
    # standing comment's own ink, and above all three the draft the user is writing.
    # Asked with the pointer actually resting on the standing mark, because that is the
    # overlap the order exists for and because nothing registers the hover until a mouse
    # has been over a passage. A higher highlight supplies only the properties it states,
    # so this is what lets one mark say "clickable" and "you are here" at once.
    # Opening the inline card moves the document to the passage; settle it before
    # reading pointer geometry.
    page_at_rest(page)
    page.mouse.move(*mark_point(page, "lf-mark-here"))
    page.wait_for_function("() => (CSS.highlights.get('lf-mark-hover')?.size ?? 0) > 0")
    ranks = page.evaluate(
        """() => ['lf-mark', 'lf-mark-hover', 'lf-mark-here', 'lf-pending']
            .map(n => CSS.highlights.get(n)?.priority ?? null)"""
    )
    assert all(r is not None for r in ranks) and ranks == sorted(set(ranks)), (
        f"the marks' paint order is not strictly increasing: {ranks}"
    )
    assert standing_mark(page)["text"] == "bold text", (
        "the pointer resting on the standing mark took its own ink away"
    )

    page.keyboard.press("t")
    wait_standing(page, "neighbouring block")

    # A passage with no words to paint says the same thing with the outline it already
    # wears, so the two kinds of anchor answer one question and not two.
    page.keyboard.press("t")
    wait_standing(page, "", ["fig"])
    # Past the last comment the walk comes round to the first, and back again.
    first = page.locator(
        f'.lf-margin-preview .lf-page-thread[data-thread="{roots[0]}"]'
    )
    page.keyboard.press("t")
    expect(first).to_be_focused()
    wait_standing(page, "bold text")
    page.keyboard.press("Shift+t")
    expect(
        page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{roots[2]}"]')
    ).to_be_focused()
    wait_standing(page, "", ["fig"])
    page.keyboard.press("Shift+t")
    wait_standing(page, "neighbouring block")
    page.keyboard.press("Shift+t")
    expect(first).to_be_focused()
    wait_standing(page, "bold text")

    # Standing in a comment while writing back to it is still standing in it: the reply
    # box is inside the thread, and knowing which passage it is on is worth most there.
    first.locator("leaf-text").focus()
    wait_standing(page, "bold text")

    # And leaving the thread takes it down. A mark that outlived the user's attention
    # would be a page insisting on a comment nobody is in.
    page.evaluate("() => document.activeElement.blur()")
    wait_standing(page, "")
    assert painted(page, "lf-mark") != "", (
        "the posted marks went down with the standing one"
    )


def test_a_hovered_thread_rebinds_to_a_replaced_anchor(browser, serve):
    """A live revision replaces the authored nodes but keeps the thread and its anchor.
    With the pointer parked on that card, the semantic hover id does not change; its
    Range still must move from the detached v1 text node onto the connected v2 one."""
    url = serve(INLINE_PAGE, anchored=[("p", "bold text")])
    page = open_page(browser, live_url(url))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    point = card_body(page, "About this bit.")
    page.mouse.move(*point)
    wait_hovered(page, "bold text")
    page.evaluate(
        "() => { window.__lfOldHoverNode = "
        "[...CSS.highlights.get('lf-mark-hover')][0].startContainer; }"
    )
    v2 = INLINE_PAGE.replace(
        "<strong>bold text</strong>", '<span data-v2="true">bold text</span>'
    )
    _publish(serve.page_dir, 2, v2, "kept the passage while replacing its markup")
    told(page)
    expect(page.locator(".lf-version")).to_contain_text("v2")
    page.wait_for_selector('[data-v2="true"]')
    wait_hovered(page, "bold text")
    state = page.evaluate("""() => {
        const range = [...CSS.highlights.get('lf-mark-hover')][0];
        return {
            oldConnected: window.__lfOldHoverNode.isConnected,
            text: range?.toString() ?? null,
            rebound: Boolean(range && range.startContainer !== window.__lfOldHoverNode),
            connected: Boolean(range?.startContainer.isConnected),
            inV2: Boolean(document.querySelector('[data-v2="true"]')
              ?.contains(range?.startContainer)),
            card: document.querySelector('.lf-thread')?.classList.contains('lf-mark-hover'),
        };
    }""")
    assert state == {
        "oldConnected": False,
        "text": "bold text",
        "rebound": True,
        "connected": True,
        "inV2": True,
        "card": True,
    }, f"the parked hover did not move from the detached v1 anchor to v2: {state}"
    expect(page.locator(".lf-thread")).to_have_class(re.compile(r"\blf-mark-hover\b"))


def test_the_pointer_over_a_comment_lights_the_passage_it_is_about(browser, serve):
    """A user scanning a full panel asks the same thing of every card — which of these
    is about what — and pressing one to find out spends a travel they may not want. The
    pointer resting on the card answers it: a card is the thread's view in the list the
    way a mark is its view in the prose, so the same wash lights the same passage from
    either side. The standing mark answers the question for the comment the user chose;
    this answers it for the one under their hand.

    Read in the frame that already answers the page's own hover, because the pointer is
    in one place and the two readings are one answer: markAt refuses a point that lands
    in the chrome, so a card's reading and a mark's cannot both name a thread, and a
    second writer to this highlight would be overwritten by whichever frame ran last.

    The cursor stays behind on the page. It is the promise that pressing here opens
    something, and over a card the press on offer is the card's own."""
    url = serve(INLINE_PAGE)
    page = open_page(browser, url)
    api = url.rsplit("/versions/", 1)[0] + "/api/event"
    for anchor, text in (
        ({"section": "p", "quote": "bold text"}, "on the first"),
        ({"section": "p2", "quote": "neighbouring block"}, "on the second"),
        ({"section": "fig"}, "on the figure"),
    ):
        post_event(
            page,
            api,
            data={"kind": "comment", "revision": 1, "text": text, "anchor": anchor},
        )
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) >= 2")
    page.locator(".lf-threads-toggle").click()
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 3")

    assert painted(page, "lf-mark-hover") == "", (
        "a page whose pointer has touched nothing is already lighting a passage"
    )

    # Three things a mark can be — posted, indicated, stood in — are three steps of one
    # wash, and the middle one exists because this gesture puts the pointer over the panel
    # by construction: a hover sharing the standing wash left the two lit identically
    # whenever a hand rested where it had just clicked, with a 2px underline hue the only
    # thing between them.
    #
    # Measured as composited pixels rather than as declarations, because a rule full of
    # var() and color-mix reads back non-empty whatever it resolves to, and two alphas of
    # one hue is exactly the pair a string comparison calls different and the eye does
    # not. So the wash is painted over the page's own ground and the result compared in
    # Lab: ordering by distance from that ground, which holds in both colour schemes
    # because the wash is darker than the page in one and lighter in the other, and a
    # floor under each step, because ordering alone passes a middle set one alpha unit
    # from its neighbour. The floor is 4, against a just noticeable difference near 2.3
    # and the palette's own 6.4 and 6.5 in light, 7.4 and 7.2 in dark.
    ramp = page.evaluate("""() => {
        // The marks' rules are adopted, not linked (runtime/marks.css).
        const rules = [...document.styleSheets, ...document.adoptedStyleSheets].flatMap(s => {
            try { return [...s.cssRules] } catch { return [] }
        });
        const probe = document.createElement('div');
        document.body.append(probe);
        const declared = (name) => {
            const r = rules.find(r => (r.selectorText ?? '') === `::highlight(${name})`);
            if (!r?.style?.backgroundColor) return null;
            probe.style.backgroundColor = r.style.backgroundColor;
            return getComputedStyle(probe).backgroundColor;
        };
        const paper = getComputedStyle(document.body).backgroundColor;
        const canvas = document.createElement('canvas');
        canvas.width = canvas.height = 1;
        const ctx = canvas.getContext('2d', {willReadFrequently: true});
        const over = (css) => {
            ctx.fillStyle = paper; ctx.fillRect(0, 0, 1, 1);
            if (css !== null) { ctx.fillStyle = css; ctx.fillRect(0, 0, 1, 1); }
            return [...ctx.getImageData(0, 0, 1, 1).data].slice(0, 3);
        };
        const lab = (px) => {
            const [r, g, b] = px.map(v => {
                const c = v / 255;
                return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
            });
            const f = (t) => t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116;
            const x = f((r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047);
            const y = f(r * 0.2126 + g * 0.7152 + b * 0.0722);
            const z = f((r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883);
            return [116 * y - 16, 500 * (x - y), 200 * (y - z)];
        };
        const de = (a, b) => Math.hypot(...lab(a).map((v, i) => v - lab(b)[i]));
        const ground = over(null);
        const steps = {};
        for (const [step, name] of [['posted', 'lf-mark'], ['pointed', 'lf-mark-hover'],
                                    ['standing', 'lf-mark-here']]) {
            const css = declared(name);
            steps[step] = css === null ? null : over(css);
        }
        probe.remove();
        if (Object.values(steps).some(v => v === null)) return {missing: steps};
        return {
            fromGround: Object.fromEntries(
                Object.entries(steps).map(([k, v]) => [k, +de(v, ground).toFixed(2)])),
            apart: {
                'posted→pointed': +de(steps.posted, steps.pointed).toFixed(2),
                'pointed→standing': +de(steps.pointed, steps.standing).toFixed(2),
            },
        };
    }""")
    assert "missing" not in ramp, (
        f"a step of the mark ramp has no wash rule at all: {ramp['missing']}"
    )
    order = ramp["fromGround"]
    assert order["posted"] < order["pointed"] < order["standing"], (
        "the three things a mark can be are not three steps away from the page's own"
        f" ground, so the wash does not rank them: {order}"
    )
    assert min(ramp["apart"].values()) >= 4, (
        "two steps of the mark ramp are too close for a user to tell apart without one"
        f" of the other beside it: {ramp['apart']}"
    )

    page.mouse.move(*card_body(page, "on the first"))
    wait_hovered(page, "bold text")
    # The wash is the page's, and the cursor is not: body wears lf-over-mark only while
    # the pointer is on the page's own mark, or every card in the panel would promise a
    # press the page does not make — the quote inside the card makes its own.
    assert not page.evaluate(
        "() => document.body.classList.contains('lf-over-mark')"
    ), "resting on a card told the page the pointer was on a mark"

    # It follows the pointer along the list, so a sweep down the panel reads out what
    # each comment is about in turn.
    page.mouse.move(*card_body(page, "on the second"))
    wait_hovered(page, "neighbouring block")

    # An element anchor answers too, in the chrome projection above its descendants.
    # ::highlight paints glyphs and a box has none, so the contour gains weight for the
    # middle step. Without it the pointer over an element-anchored card did nothing at
    # all, which from the panel reads as a broken hover rather than as a passage with no
    # words.
    hovered_el = page.locator("#fig")
    hovered_el.scroll_into_view_if_needed()
    page.mouse.move(*card_body(page, "on the figure"))
    wait_hovered(page, "")
    expect(hovered_el).to_have_class(re.compile(r"\blf-mark-hover\b"))
    hovered_mark = page.locator('.lf-visual-mark[data-for="fig"]')
    expect(hovered_mark).to_have_class(re.compile(r"\blf-visual-mark-hover\b"))
    # The contour is the hover's alone: the figure's thread draws nothing at rest, so
    # moving the pointer on takes the figure's contour away.
    page.mouse.move(*card_body(page, "on the second"))
    wait_hovered(page, "neighbouring block")
    expect(hovered_mark).to_have_count(0)

    # Standing in one comment while pointing at another says both, because they answer
    # different questions and rank apart: the standing mark keeps its ink above the wash.
    page.locator(".lf-thread").filter(has_text="on the first").first.locator(
        ":scope > .lf-thread-summary"
    ).focus()
    wait_standing(page, "bold text")
    page.mouse.move(*card_body(page, "on the second"))
    wait_hovered(page, "neighbouring block")
    assert standing_mark(page)["text"] == "bold text", (
        "pointing at another comment's card took the standing comment's mark away"
    )

    # And the pointer leaving the panel puts it down, while what the page posted stays.
    page.mouse.move(2, 2)
    wait_hovered(page, "")
    assert painted(page, "lf-mark") != "", (
        "the posted marks went down with the pointer's"
    )


def test_closing_the_panel_puts_down_the_card_it_was_lighting(browser, serve):
    """The panel going away is the card going out from under the pointer, and the wash it
    was lighting has to go with it. Escape closes the panel from its controls while
    the pointer stays on the card, so nothing else asks the hover question again —
    the page is left washing a passage with no card, no pointer on it, and nothing on the
    screen that says why."""
    url = serve(INLINE_PAGE)
    page = open_page(browser, url)
    post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "comment",
            "revision": 1,
            "text": "on the first",
            "anchor": {"section": "p", "quote": "bold text"},
        },
    )
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) >= 1")
    page.locator(".lf-threads-toggle").click()
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 1")

    page.mouse.move(*card_body(page, "on the first"))
    wait_hovered(page, "bold text")

    page.keyboard.press("Escape")
    page.wait_for_function(
        "() => !document.body.hasAttribute('data-lf-auxiliary-surface')"
    )
    wait_hovered(page, "")


def test_a_commented_block_says_so_to_a_screen_user(browser, serve):
    """A mark is painted, not wrapped, so it builds no accessibility node and a passage
    carrying a comment reads exactly like one that doesn't. So each commented block names
    a note as its details, ARIA's relation for an annotation: a button in the chrome
    saying how many comments the block carries, counting up per block, riding in on a
    sent comment's round trip, and leaving with its thread. The note is the runtime's, so
    it stays out of the document: out of a selection, out of the next quote, and out of
    the mutations a screen reader rebuilds its buffer on."""
    url = serve(NOTED_PAGE)
    d = serve.page_dir

    def comment(anchor, text):
        return append_carried_log_record(
            d,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": text,
                "anchor": anchor,
            },
        )["id"]

    c1 = comment({"quote": "first passage"}, "Sharpen this.")
    c2 = comment({"quote": "two separate remarks"}, "Second thought.")
    comment({"section": "fig"}, "The figure too.")
    page = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    # Two threads on one block count up, and leave one note rather than two.
    expect_comment_notes(page, "#p1", 1)
    # The block is named by its words, cut short as every chrome name is.
    named = "2 comments on § paragraph · The first passage under discussion, with words enough for…"
    assert accessible_details(page, "#p1") == [named], (
        "a screen reader reading the block is told nothing about the comments on it"
    )
    note = comment_note(page, "#p1")
    # Hidden means hidden from the eye, not the tree.
    assert note.evaluate(
        "el => { const r = el.getBoundingClientRect(); return r.width <= 1 && r.height <= 1; }"
    ), "the resting note is painting on screen"
    assert note.evaluate("el => getComputedStyle(el).opacity") == "0"
    assert note.evaluate("el => el.tabIndex") == -1, (
        "the note is a Tab stop in the chrome, after the whole page"
    )
    page.evaluate("""() => {
        window.__lfNote = document.getElementById('p1').ariaDetailsElements[0];
    }""")
    inline1 = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{c1}"]')
    inline2 = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{c2}"]')
    expect(note).to_have_role("button")
    # Focused with the keyboard's modality, as a screen reader moving to it focuses it,
    # the note shows and enters the first thread, and the walk goes on from there.
    page.keyboard.press("Tab")
    note.focus()
    expect(note).to_be_focused()
    assert note.evaluate("el => el.getBoundingClientRect().width > 1"), (
        "the comment path stayed invisible when a keyboard user reached it"
    )
    assert note.evaluate("el => getComputedStyle(el).opacity") == "1"
    note.press("Enter")
    expect(inline1).to_be_focused()
    expect(page.locator(".lf-thread-panel")).not_to_have_class(re.compile(r"\bopen\b"))
    page.keyboard.press("t")
    expect(inline2).to_be_focused()

    # Once the first thread resolves, the same control enters the next one.
    append_carried_log_record(d, {"kind": "resolve", "author": "user", "parent": c1})
    note.focus()
    told(page)
    expect(note).to_have_text("1 comment")
    expect(note).to_be_focused()
    assert page.evaluate("""() =>
        window.__lfNote === document.getElementById('p1').ariaDetailsElements[0]
    """), "a count change replaced the note"
    note.press("Enter")
    expect(inline2).to_be_focused()
    # An element anchor has no text to paint, and the element it names carries the note.
    assert any(
        detail.startswith("1 comment on § figure")
        for detail in accessible_details(page, "#fig")
    ), "the figure's comment note is missing from its accessible details"

    # A pass that finds nothing to change must change nothing: a screen reader rebuilds
    # its buffer on every mutation, and this pass runs on every poll. A comment on no
    # passage at all is what proves a pass ran without touching the block's count.
    page.evaluate("""() => {
        window.__churn = 0;
        new MutationObserver(rs => (window.__churn += rs.length))
            .observe(document.getElementById('p1'), {childList: true,
                     characterData: true, attributes: true, subtree: true});
    }""")
    comment({}, "On the page as a whole.")
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 4")
    assert page.evaluate("() => window.__churn") == 0, (
        "a poll that changed nothing still rewrote the block, so a screen reader re-reads it"
    )

    # The note belongs to the runtime, not the document: a user dragging across the
    # block neither copies it nor quotes it.
    page.locator("#p1").click(click_count=3)
    assert "comment" not in page.evaluate("() => getSelection().toString()"), (
        "the note came along in the user's own selection"
    )
    page.locator(".lf-fab-input").click()
    assert "comment" not in composer_quote(page)["text"], (
        "the note came along in the quote the comment would store"
    )
    page.keyboard.press("Escape")

    # The gesture's own comment reaches the note once the send's round trip lands.
    box = page.locator("#p2").bounding_box()
    y = box["y"] + box["height"] / 2
    select(page, (box["x"] + 2, y), (box["x"] + box["width"] - 2, y))
    page.locator(".lf-fab-input").click()
    page.wait_for_function(
        "() => document.querySelector('.lf-composer').hasAttribute('data-lf-open')"
    )
    write(page.locator(".lf-composer leaf-text"), "Too short.")
    page.keyboard.press("ControlOrMeta+Enter")
    expect_comment_notes(page, "#p2", 1)
    c4 = [e for e in events_model.read_events(d) if e.get("kind") == "comment"][-1][
        "id"
    ]

    # A resolved thread takes its note with it, and gives the block back its own
    # attributes: the pass owns what it wrote.
    append_carried_log_record(d, {"kind": "resolve", "author": "user", "parent": c4})
    told(page)
    expect_comment_notes(page, "#p2", 0)
    expect(page.locator("#p2")).not_to_have_attribute("aria-details", re.compile(".*"))
    assert accessible_details(page, "#p1")[0].startswith("1 comment on ")

    # A passage crossing two blocks says so in both: a user landing on either block
    # hears about the comment, the way the paint reaches both.
    comment({"quote": "to land in it. A short second"}, "Crosses the boundary.")
    told(page)
    expect_comment_notes(page, "#p2", 1)
    assert accessible_details(page, "#p1")[0].startswith("2 comments on ")
    assert accessible_details(page, "#p2")[0].startswith("1 comment on ")


def test_a_revision_keeps_a_block_naming_its_comment_note(browser, serve):
    """A revision that keeps a commented block and changes its own `aria-details` writes
    the new source's value over the block's name for its note. The next pass names the
    note again after the source's own details, and the note's release keeps the source's
    value rather than the one the block had when the comment arrived."""
    url = serve(NOTED_PAGE, anchored=[("p1", "first passage")])
    page = open_page(browser, live_url(url))
    expect_comment_notes(page, "#p1", 1)
    source = (serve.page_dir / "index.html").read_text(encoding="utf-8")
    stamp_page(
        serve.page_dir,
        source.replace('<p id="p1">', '<p id="p1" aria-details="p2">'),
        "Point the first passage at the second",
    )
    told(page)
    expect(page.locator("#p2")).to_be_attached()
    page.wait_for_function(
        """() => document.getElementById('p1').ariaDetailsElements
            ?.map((el) => el.id || el.textContent).join('|') === 'p2|1 comment'"""
    )


def test_a_comment_leaves_its_block_as_the_page_wrote_it(browser, serve):
    """Nothing Leaf draws moves the page's content (assets/AGENTS.md, "Space and
    scrolling"), and the page's own rules read a block's structure: here the last item
    of a list takes a wide bottom margin. A comment on the list adds no child to it, so
    the rule keeps matching and the paragraph after the list stays where it stood."""
    url = serve(COMMENTED_LIST_PAGE)
    page = open_page(browser, url)
    read = """() => ({
        children: [...document.getElementById('list').children].map(el => el.id),
        after: document.getElementById('after').getBoundingClientRect().top,
    })"""
    before = page.evaluate(read)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Is this list complete?",
            "anchor": {"section": "list"},
        },
    )
    told(page)
    expect_comment_notes(page, "#list", 1)
    assert page.evaluate(read) == before


def test_a_comments_quoted_passage_is_in_the_keyboard_journey(browser, serve):
    """The pointer's return-to-passage action is a focusable, named control too."""
    lead = "".join(f"<p>Earlier reading context, line {n}.</p>" for n in range(14))
    tail = "".join(f"<p>Later reading context, line {n}.</p>" for n in range(14))
    noted_page = NOTED_PAGE.replace('<p id="p1">', f'{lead}<p id="p1">').replace(
        '<figure id="fig">', f'{tail}<figure id="fig">'
    )
    url = serve(noted_page)
    d = serve.page_dir
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Check this wording.",
            "anchor": {"section": "p1", "quote": "first passage"},
        },
    )
    page = open_page(browser, live_url(url))
    page.emulate_media(reduced_motion="reduce")
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 1")

    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-thread-summary")).to_be_focused()
    page.keyboard.press("Tab")
    quote = page.locator(".lf-thread .lf-quote")
    expect(quote).to_be_focused()
    expect(quote).to_have_attribute("role", "button")
    expect(quote).to_have_attribute("aria-keyshortcuts", "Enter Space")
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("return to the passage")

    passage = page.locator("#p1")
    passage.scroll_into_view_if_needed()
    page.evaluate(
        """() => {
          const passage = document.querySelector('#p1').getBoundingClientRect();
          const banner = document.querySelector('.lf-banner').getBoundingClientRect();
          document.scrollingElement.scrollBy(0, passage.top - banner.bottom - 96);
        }"""
    )
    before = page.evaluate(
        """() => {
          const passage = document.querySelector('#p1').getBoundingClientRect();
          const banner = document.querySelector('.lf-banner').getBoundingClientRect();
          return {scroll: document.scrollingElement.scrollTop, top: passage.top,
                  bottom: passage.bottom, banner: banner.bottom, height: innerHeight};
        }"""
    )
    assert before["top"] > before["banner"] + 48
    assert before["bottom"] < before["height"] - 48
    page.keyboard.press("Enter")
    page.keyboard.press("Space")
    after = page.evaluate(
        """() => ({
          scroll: document.scrollingElement.scrollTop,
          top: document.querySelector('#p1').getBoundingClientRect().top,
        })"""
    )
    assert after["scroll"] == pytest.approx(before["scroll"], abs=0.5)
    assert after["top"] == pytest.approx(before["top"], abs=0.5)

    # One painted pixel is not a readable arrival. Carry the passage almost entirely
    # behind the fixed banner, then the same quote must bring it back into view.
    for key in ("Enter", "Space"):
        page.evaluate(
            """() => {
              const passage = document.querySelector('#p1').getBoundingClientRect();
              const banner = document.querySelector('.lf-banner').getBoundingClientRect();
              document.scrollingElement.scrollBy(0, passage.bottom - banner.bottom - 1);
            }"""
        )
        sliver = page.evaluate(
            """() => {
              const passage = document.querySelector('#p1').getBoundingClientRect();
              const banner = document.querySelector('.lf-banner').getBoundingClientRect();
              return {scroll: document.scrollingElement.scrollTop, top: passage.top,
                      bottom: passage.bottom, banner: banner.bottom};
            }"""
        )
        assert sliver["top"] < sliver["banner"] < sliver["bottom"]
        page.keyboard.press(key)
        returned = page.evaluate(
            """() => ({
              scroll: document.scrollingElement.scrollTop,
              top: document.querySelector('#p1').getBoundingClientRect().top,
              banner: document.querySelector('.lf-banner').getBoundingClientRect().bottom,
            })"""
        )
        assert returned["scroll"] != pytest.approx(sliver["scroll"], abs=0.5)
        assert returned["top"] > returned["banner"]

    # A resolved thread keeps its page placement even though its quote has no live
    # mark. On a covering phone panel, that retained destination remains an enabled
    # keyboard action, spends the sheet, and returns to the passage.
    page.get_by_role("button", name="Resolve thread", exact=True).click()
    round_trip(page)
    resized(page, 390, 800)
    page.locator(".lf-thread-filter-toggle").click()
    page.locator('[data-filter-value="resolved"]').click()
    # The user read this card open, and narrowing to Resolved keeps the disclosure they
    # left rather than folding the card away under them, so the card comes back open and
    # a press on its summary here would shut it.
    expect(page.locator(".lf-thread:not([hidden])")).to_have_attribute("open", "")
    rendered(page)
    resolved_quote = page.locator(".lf-thread:not([hidden]) .lf-quote")
    expect(resolved_quote).not_to_have_class(re.compile(r"\bdetached\b"))
    expect(resolved_quote).to_have_attribute("role", "button")
    expect(resolved_quote).to_have_attribute("tabindex", "0")
    page.evaluate(
        "() => document.scrollingElement.scrollTo(0, document.scrollingElement.scrollHeight)"
    )
    placed_before = page.evaluate("() => document.scrollingElement.scrollTop")
    resolved_quote.focus()
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("return to the passage")
    page.keyboard.press("Enter")
    expect(page.locator(".lf-thread-panel")).to_be_hidden()
    placed_after = page.evaluate(
        """() => {
          const passage = document.querySelector('#p1').getBoundingClientRect();
          const banner = document.querySelector('.lf-banner').getBoundingClientRect();
          return {scroll: document.scrollingElement.scrollTop, top: passage.top,
                  bottom: passage.bottom, banner: banner.bottom, height: innerHeight};
        }"""
    )
    assert placed_after["scroll"] != placed_before
    assert placed_after["top"] > placed_after["banner"]
    assert placed_after["bottom"] < placed_after["height"]

    # When a later version removes the passage altogether, the same resolved quote is an
    # informative blockquote. A pointer press has no destination to spend the sheet on,
    # so the covering panel and the page behind it both stay where the user left them.
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    without_passage = re.sub(r'<p id="p1">.*?</p>', "", noted_page, flags=re.DOTALL)
    stamp_page(d, without_passage, "remove the quoted passage")
    wait_for_revision(page, 2)
    # Narrowing is interaction-local heap state, and nothing executable changed, so the
    # user keeps this document and the Resolved narrowing they chose stands in it.
    # The status narrowing is a group of toggles, so the active member wears its own
    # pressed state.
    expect(page.locator('[data-filter-value="resolved"]')).to_have_attribute(
        "aria-pressed", "true"
    )
    resolved_quote = page.locator(".lf-thread:not([hidden]) .lf-quote")
    expect(resolved_quote).to_have_class(re.compile(r"\bdetached\b"))
    expect(resolved_quote).not_to_have_attribute("role", "button")
    expect(resolved_quote).not_to_have_attribute("tabindex", "0")
    assert resolved_quote.get_attribute("aria-keyshortcuts") is None
    expect(page.locator(".lf-thread-panel")).to_be_visible()
    stranded_before = page.evaluate("() => document.scrollingElement.scrollTop")
    quote_box = resolved_quote.bounding_box()
    assert quote_box is not None
    page.mouse.click(
        quote_box["x"] + quote_box["width"] / 2,
        quote_box["y"] + quote_box["height"] / 2,
    )
    expect(page.locator(".lf-thread-panel")).to_be_visible()
    assert page.evaluate("() => document.scrollingElement.scrollTop") == stranded_before
    resolved_quote.focus()
    expect(page.locator(".lf-shortcut-bar")).not_to_contain_text(
        "return to the passage"
    )
