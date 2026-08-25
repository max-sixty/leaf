"""Comment marks, addresses, and keyboard navigation tests."""

import re
from pathlib import Path

import pytest
from conftest import interact
from playwright.sync_api import expect
from render_support import (
    ADDRESS_PAGE,
    ADDRESSED_PAGE,
    ASKS_PAGE,
    BOARD_PAGE,
    CHIPS,
    CLIPPED_BY,
    CROWDED_PAGE,
    FOOTED_PAGE,
    INLINE_PAGE,
    INSIDE_ITS_OPTION,
    LONG_PAGE,
    NOTED_PAGE,
    OVER_WORDS,
    PANEL_PAGE,
    TARGETS_PAGE,
    WHERE_I_STAND_PAGE,
    _publish,
    card_body,
    composer_quote,
    hide_scroll_operation_promises,
    hold_arrival_scroll_ends,
    leaf_page,
    live_url,
    mark_point,
    open_page,
    painted,
    panel_comment,
    panel_settled,
    pending_text,
    post_event,
    resized,
    round_trip,
    select,
    standing_mark,
    told,
    wait_hovered,
    wait_standing,
)

pytestmark = pytest.mark.nightly


def test_keys_answer_a_question_from_its_marks(browser, serve):
    """From a mark — where `n` lands — ↑/↓ walk the options clamping at the ends, a
    digit picks outright, and each option wears its digit only while a mark holds
    keyboard focus, so nothing appears on a page nobody is answering."""
    page, errors = open_page(browser, serve(ASKS_PAGE))
    nums = page.locator("#live-question .lf-address")
    expect(nums.first).to_be_hidden()

    page.keyboard.press("n")
    marks = page.locator("#live-question .lf-pick")
    expect(marks.first).to_be_focused()
    expect(nums.first).to_be_visible()
    expect(nums.nth(1)).to_have_text("2")

    page.keyboard.press("ArrowDown")
    expect(marks.nth(1)).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(marks.nth(1)).to_be_focused()

    page.keyboard.press("1")
    expect(page.locator("#lq-keep")).to_have_attribute("chosen", "")
    round_trip(page)
    acts = [e for e in interact.read_events(serve.page_dir) if e["kind"] == "action"]
    assert acts[-1]["widget"] == "live-question"
    assert acts[-1]["detail"] == {"options": ["lq-keep"]}
    assert errors == []
    page.close()


def test_a_questions_digits_are_drawn_whole(browser, serve):
    """An address arrives into room its option is already holding, and lands on nothing.

    Every earlier placement borrowed that room instead, and each borrow showed. On the
    cell's outer corner the chip was half outside a group that clips itself, so no
    address the product drew had ever been whole — seven of its seventeen pixels gone,
    and in a bare-label group the first digit was a sliver.
    Out in the page margin beside the group it was whole and it was in the neighbouring
    card's prose, because a middle column's margin is another cell. Neither showed up
    as a failure: a clipped element still reports its whole box and still answers
    `to_be_visible`, and a chip drawn over words breaks no rule anybody had written.

    So the cell holds a column for it, and this asks the two questions that column
    answers — does any ancestor cut it, is it on anybody's words — in both forms,
    stepped through with the key that reaches them, since the room inside a cell is
    exactly what differed: cards padded clear of their corners, rows with none to
    spare.

    How far down the column it stands is each form's own answer, so each is asked for the
    fact it states rather than for one number covering both. A card's digit rides at the
    head of that column, beside the title rather than over it; a row's is centred on the
    row. Pinned as one 8px it was level with a 15px row, and the day the row went to the
    page's own 17px it was two pixels too high with the gate still green — because what
    the gate read was the number the theme stated, and the claim beside it, that a row's
    digit is level with its words, was checked by nothing."""
    page, errors = open_page(browser, serve(ADDRESS_PAGE))
    for options, sitting in [
        (["c-heater", "c-cable", "c-hand"], "in the corner"),
        (["r-now", "r-later"], "centred"),
    ]:
        page.keyboard.press("n")
        for id_ in options:
            chip = page.locator(f"#{id_} > .lf-address")
            expect(chip).to_be_visible()
            cut = chip.evaluate(CLIPPED_BY)
            assert cut is None, f"{id_}'s digit is cut: {cut}"
            # Never on the hairline the outer corner would have shared with the cells
            # around it: the column the option reserves starts 6px in, in both forms.
            sits = chip.evaluate(INSIDE_ITS_OPTION)
            assert round(sits["x"]) == 6, (
                f"{id_}'s digit sits {sits['x']} in from its option's left edge"
            )
            if sitting == "in the corner":
                assert round(sits["y"]) == 8, (
                    f"{id_}'s digit sits {sits['y']} down from its option's top, not in "
                    "the corner of the column its card reserves"
                )
            else:
                assert abs(sits["level"]) <= 0.5, (
                    f"{id_}'s digit is {sits['level']}px off the middle of its row's own "
                    "words"
                )
            assert sits["past"] <= 0, (
                f"{id_}'s digit hangs past its own option and onto the next"
            )
            # Asked of the words rather than of the numbers, because the numbers are
            # only right for as long as the column the theme reserves is.
            on = chip.evaluate(OVER_WORDS, id_)
            assert on is None, f"{id_}'s digit is drawn over the words “{on}”"
    assert errors == []
    page.close()


def test_composer_marks_the_passage_instead_of_quoting_it(browser, serve):
    """The passage stays visible while its comment is written. Focus moves into the
    composer the moment it opens, which drops the browser's own selection, so the
    runtime paints the anchor itself, and repaints it after every pass that redraws
    the posted threads' marks around it — otherwise a comment arriving mid-sentence
    would leave the reader's passage stranded across stale text nodes. It comes down
    with the box, and the whole time it never touches the document.

    And because the mark says which passage the box is on, the box doesn't say it too:
    the quote inside it stays out of sight while the page is marking the passage."""
    url = serve(INLINE_PAGE)
    page, errors = open_page(browser, url)

    page.locator("#p").click(
        click_count=3
    )  # a real selection, spanning the inline tags
    page.locator(".lf-fab").click()
    page.wait_for_function(
        "() => document.querySelector('.lf-composer').style.display === 'block'"
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
            "() => document.querySelector('.lf-composer textarea').getAttribute('aria-describedby')"
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
    # nodes the painted range is pinned to. The reader is mid-sentence; their passage
    # can neither blink out nor come back covering the wrong words.
    post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "comment",
            "version": 1,
            "text": "arriving mid-sentence",
            "anchor": {"section": "p", "quote": "bold text"},
        },
    )
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    assert pending_text(page) == passage, (
        "a poll landing while the composer is open disturbed the passage"
    )

    page.get_by_role("button", name="Cancel").click()
    assert pending_text(page) == "", "the highlight outlived its composer"

    # A passage with the runtime's own chrome inside it paints around the chrome, the way
    # the search reads around it — one range per segment, not one spanning the lot.
    # Across both options, so a Choose button falls in the middle of the passage rather
    # than after it — where a single range spanning the whole thing would swallow it.
    chrome = page.locator("#opts .lf-ui").first.text_content().strip()
    assert chrome, "this assertion needs the widget to have rendered chrome inside it"
    page.evaluate("""() => {
        const r = document.createRange();
        r.selectNodeContents(document.querySelector('#opts'));
        const s = getSelection(); s.removeAllRanges(); s.addRange(r);
        document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
    }""")
    page.locator(".lf-fab").click()
    page.wait_for_function("() => CSS.highlights.get('lf-pending')")
    assert chrome not in pending_text(page), (
        f"the highlight painted the widget's own {chrome!r} control along with the passage"
    )
    page.get_by_role("button", name="Cancel").click()

    # A diagram has no text to quote, so its anchor is the element and its mark is an
    # outline. That one the anchor pass really does take down, so it has to be redrawn.
    page.locator("#fig svg").click()
    page.locator(".lf-fab").click()
    page.locator("#fig.lf-mark-el.lf-pending").wait_for()
    assert not composer_quote(page)["shown"], (
        "the outline is on the figure and the composer names its section as well"
    )
    post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={"kind": "comment", "version": 1, "text": "and another"},
    )
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 2")
    assert page.locator("#fig.lf-mark-el.lf-pending").count() == 1, (
        "a poll landing while the composer is open dropped the outline"
    )

    # Both classes have to go, asserted apart: leaving .lf-mark-el behind repaints the
    # figure in the posted mark's own ink, pointer cursor and all, over no thread to open.
    page.get_by_role("button", name="Cancel").click()
    assert page.locator("#fig.lf-pending").count() == 0, (
        "the outline outlived its composer"
    )
    assert page.locator("#fig.lf-mark-el").count() == 0, (
        "the figure kept a thread's outline over no thread"
    )

    # A drag across the caption ends with the click's target inside the figure, but the
    # selection is what the reader picked: the one decider ranks the quote above the
    # element anchor, so the composer carries the caption's words rather than § fig.
    cap = page.locator("#fig figcaption").bounding_box()
    y = cap["y"] + cap["height"] / 2
    select(page, (cap["x"] + 2, y), (cap["x"] + cap["width"] - 2, y))
    page.locator(".lf-fab").click()
    page.wait_for_function("() => CSS.highlights.get('lf-pending')")
    assert "specimen" in pending_text(page), (
        "the click's visual find outranked the selection the drag made"
    )
    assert page.locator("#fig.lf-pending").count() == 0, (
        "the figure got the element outline over a live selection"
    )
    page.get_by_role("button", name="Cancel").click()
    assert errors == []
    page.close()


def test_the_pointer_over_a_page_mark_lights_its_comment_card(browser, serve):
    """The page and panel are reciprocal views of a thread. Resting on a card lights
    its passage; resting on that passage must identify the card too, or the common case
    where the passage is parked and the card is visible answers on the off-screen side.
    The signal follows the pointer from one thread to the next and leaves with it."""
    url = serve(
        INLINE_PAGE,
        anchored=[("p", "bold text"), ("p2", "neighbouring block")],
    )
    comments = [
        event
        for event in interact.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    first_id, second_id = (comment["id"] for comment in comments)
    page, errors = open_page(browser, url)
    page.locator(".lf-comments").click()
    panel_settled(page)
    first = page.locator(f'.lf-thread[data-id="{first_id}"]')
    second = page.locator(f'.lf-thread[data-id="{second_id}"]')
    resting = first.evaluate("element => getComputedStyle(element).backgroundColor")

    page.mouse.move(*mark_point(page, "lf-mark", 0))
    expect(first).to_have_class(re.compile(r"\blf-mark-hover\b"))
    expect(second).not_to_have_class(re.compile(r"\blf-mark-hover\b"))
    lit = first.evaluate("element => getComputedStyle(element).backgroundColor")
    assert lit != resting, (
        f"the page named the card in class but its paint stayed {resting!r}"
    )

    page.mouse.move(*mark_point(page, "lf-mark", 1))
    expect(first).not_to_have_class(re.compile(r"\blf-mark-hover\b"))
    expect(second).to_have_class(re.compile(r"\blf-mark-hover\b"))

    page.mouse.move(2, 2)
    expect(page.locator(".lf-thread.lf-mark-hover")).to_have_count(0)

    # A narrowing can put a different card under a hand that has not moved. The list
    # reconcile is therefore one of the hover's inputs, just like page geometry.
    page.mouse.move(*card_body(page, "About this bit."))
    wait_hovered(page, "bold text")
    page.fill(".lf-find-box", "neighbouring block")
    expect(page.locator(".lf-threads > .lf-thread")).to_have_count(1)
    expect(second).to_have_class(re.compile(r"\blf-mark-hover\b"))
    wait_hovered(page, "neighbouring block")
    assert errors == []
    page.close()


def test_pressing_a_page_mark_stands_in_the_thread_it_opens(browser, serve):
    """A page mark is one view of a thread, so pressing it leaves the reader in the
    card on the other surface rather than merely flashing that card and leaving focus
    behind on the prose. The focus is the standing fact: it paints the card and its
    passage through the same predicate, and gives the next key to the thread scope."""
    page, errors = open_page(browser, serve(INLINE_PAGE, anchored=[("p", "bold text")]))
    thread = page.locator(".lf-thread")

    page.mouse.click(*mark_point(page, "lf-mark"))
    panel_settled(page)

    expect(thread).to_be_focused()
    wait_standing(page, "bold text")
    assert errors == []
    page.close()


def test_the_scrollend_fallback_drains_a_one_pixel_preliminary_edge(browser, serve):
    """A one-pixel instant correction still has a scrollend of its own. Drain that edge
    before arming the glide's one-shot fallback, or it consumes the listener while the
    mark is still far from the destination and the real landing has no signal left."""
    page, errors = open_page(
        browser, serve(LONG_PAGE, anchored=[("p40", "Paragraph 40.")])
    )
    page.evaluate("""() => {
        const scrollTo = document.body.scrollTo.bind(document.body);
        document.body.scrollTo = options => { scrollTo(options); };
        const scrollIntoView = Element.prototype.scrollIntoView;
        Element.prototype.scrollIntoView = function(options) {
            if (this.closest('.lf-ui')) scrollIntoView.call(this, options);
            else document.body.scrollBy({top: 1, behavior: 'instant'});
        };
        window.__lfOnePixelArrival = null;
        document.addEventListener('animationstart', (event) => {
            if (!event.animationName.endsWith('-arrive')) return;
            const mark = [...CSS.highlights.get('lf-mark-here')][0]
                .getClientRects()[0];
            window.__lfOnePixelArrival = Math.abs(
                mark.top + mark.height / 2 - innerHeight / 2);
        }, true);
    }""")

    page.keyboard.press("j")
    page.wait_for_function("() => window.__lfOnePixelArrival !== null")
    assert page.evaluate("() => window.__lfOnePixelArrival") < 1
    assert errors == []
    page.close()


def test_superseding_a_fallback_travel_releases_its_listener(browser, serve):
    """A fallback operation can be superseded before it moves and emit no scrollend.
    Canceling the travel must both remove its listener and settle its promise, or every
    such navigation retains one more dead continuation indefinitely."""
    page, errors = open_page(
        browser,
        serve(
            LONG_PAGE,
            anchored=[("p40", "Paragraph 40."), ("p40", "Paragraph 40.")],
        ),
    )
    page.evaluate("""() => {
        const add = document.body.addEventListener.bind(document.body);
        const remove = document.body.removeEventListener.bind(document.body);
        window.__lfFallbackListeners = new Set();
        document.body.addEventListener = (type, listener, options) => {
            if (type === 'scrollend') window.__lfFallbackListeners.add(listener);
            return add(type, listener, options);
        };
        document.body.removeEventListener = (type, listener, options) => {
            if (type === 'scrollend') window.__lfFallbackListeners.delete(listener);
            return remove(type, listener, options);
        };
        const scrollTo = document.body.scrollTo.bind(document.body);
        document.body.scrollTo = options => {
            if (options?.behavior === 'smooth') {
                window.__lfDroppedSmooth = true;
                return;
            }
            scrollTo(options);
        };
        const scrollIntoView = Element.prototype.scrollIntoView;
        Element.prototype.scrollIntoView = function(options) {
            scrollIntoView.call(this, options);
        };
    }""")

    page.keyboard.press("j")
    page.wait_for_function(
        "() => window.__lfDroppedSmooth && window.__lfFallbackListeners.size === 1"
    )

    # Hold the replacement travel at its preliminary operation. Its own probe listener
    # is canceled as soon as the returned Promise is detected; no later scroll edge can
    # accidentally clean up the fallback the first travel left behind.
    page.evaluate("""() => {
        Element.prototype.scrollIntoView = () => new Promise(() => {});
    }""")
    page.keyboard.press("j")
    page.wait_for_function("() => window.__lfFallbackListeners.size === 0")
    assert errors == []
    page.close()


@pytest.mark.parametrize("anchor_kind", ["text", "element"])
def test_a_mark_changed_before_repaint_cannot_start_stale_travel(
    browser, serve, anchor_kind
):
    """Replacing main mutates a live Range or detaches an element before the next
    anchor pass can replace it. A preliminary edge settling in that interval must not
    centre the stale old record or mistake self-equality for target survival."""
    url = serve(LONG_PAGE)
    anchor = {"section": "p40"}
    if anchor_kind == "text":
        anchor["quote"] = "Paragraph 40."
    interact.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "version": 1,
            "text": "About this bit.",
            "anchor": anchor,
        },
    )
    page, errors = open_page(browser, live_url(url))
    hold_arrival_scroll_ends(page)
    page.evaluate(
        """kind => {
        const mark = kind === 'text'
            ? [...CSS.highlights.get('lf-mark')][0]
            : document.querySelector('#p40');
        window.__lfTravelMark = mark;
        window.__lfTravelBoundary = mark instanceof Range ? {
                startContainer: mark.startContainer,
                startOffset: mark.startOffset,
                endContainer: mark.endContainer,
                endOffset: mark.endOffset,
            } : null;
        }""",
        arg=anchor_kind,
    )
    page.keyboard.press("j")
    page.wait_for_function("() => window.__lfHeldScrollEnds.size === 1")

    held_highlighter = []
    page.evaluate("() => { document.startViewTransition = undefined; }")
    page.route(
        "**/vendor/highlight.esm.js", lambda route: held_highlighter.append(route)
    )
    v2 = LONG_PAGE.replace(
        "Paragraph 40.", '<span data-v2="true">Paragraph 40.</span>'
    ).replace(
        "</main>",
        '<pre><code class="language-rust">fn held() {}</code></pre></main>',
    )
    _publish(serve.page_dir, 2, v2, "kept the passage while replacing its markup")
    told(page)
    page.wait_for_selector('[data-v2="true"]')
    assert held_highlighter, "version activation reached anchor paint before the hold"
    mutation = page.evaluate("""() => {
        const mark = window.__lfTravelMark;
        const before = window.__lfTravelBoundary;
        return {
            stale: mark instanceof Range
                ? mark.startContainer !== before.startContainer
                    || mark.startOffset !== before.startOffset
                    || mark.endContainer !== before.endContainer
                    || mark.endOffset !== before.endOffset
                : !mark.isConnected,
        };
    }""")
    assert mutation == {"stale": True}, mutation

    page.evaluate("() => window.__lfReleaseScrollEnd()")
    page.evaluate("() => new Promise(requestAnimationFrame)")
    assert page.evaluate("() => window.__lfSmoothGoals") == []
    assert page.evaluate("() => window.__lfArrivalStarts") == 0

    held_highlighter.pop().continue_()
    expect(page.locator(".lf-version")).to_contain_text("v2")
    page.wait_for_function(
        """kind => {
        const mark = kind === 'text'
            ? [...CSS.highlights.get('lf-mark')][0]
            : document.querySelector('#p40');
        return mark !== window.__lfTravelMark
            && (mark instanceof Range ? mark.startContainer.isConnected : mark.isConnected);
    }""",
        arg=anchor_kind,
    )
    assert errors == []
    page.close()


def test_a_repaint_keeps_and_a_replacement_restarts_a_held_arrival(browser, serve):
    """A new Range object is a new target only when its boundaries changed. A live
    version replacement while the preliminary edge waits must restart against its new
    nodes; a routine repaint over those same nodes during the final edge must still
    announce the landing."""
    url = serve(LONG_PAGE, anchored=[("p40", "Paragraph 40.")])
    page, errors = open_page(browser, live_url(url))
    hold_arrival_scroll_ends(page)

    page.keyboard.press("j")
    page.wait_for_function("() => window.__lfHeldScrollEnds.size === 1")

    v2 = LONG_PAGE.replace("Paragraph 40.", '<span data-v2="true">Paragraph 40.</span>')
    _publish(serve.page_dir, 2, v2, "kept the passage while replacing its markup")
    told(page)
    expect(page.locator(".lf-version")).to_contain_text("v2")
    page.wait_for_selector('[data-v2="true"]')

    # Release the v1 preliminary edge. A fresh trip should stop at the v2 preliminary
    # boundary instead of starting a smooth scroll from the detached v1 Range.
    page.evaluate("() => window.__lfReleaseScrollEnd()")
    page.wait_for_function("() => window.__lfHeldScrollEnds.size === 1")
    assert page.evaluate("() => window.__lfSmoothGoals") == []

    page.evaluate("() => window.__lfReleaseScrollEnd()")
    page.wait_for_function("() => window.__lfSmoothGoals.length === 1")
    destination = page.evaluate("""() => {
        const mark = [...CSS.highlights.get('lf-mark')][0].getBoundingClientRect();
        return {
            goal: window.__lfSmoothGoals[0],
            expected: document.body.scrollTop + mark.top
                - (innerHeight - mark.height) / 2,
            connected: Boolean(mark.height),
        };
    }""")
    assert destination["connected"]
    assert abs(destination["goal"] - destination["expected"]) < 1, destination

    # Put the final operation at its goal while completion remains held. An unrelated
    # event now rebuilds every mark from the same authored nodes; that fresh Range is
    # the same target, not an interruption.
    page.evaluate("""() => {
        document.body.scrollTop = window.__lfSmoothGoals[0];
        window.__lfBeforeRepaint = [...CSS.highlights.get('lf-mark')][0];
    }""")
    post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={"kind": "comment", "version": 2, "text": "unrelated arrival"},
    )
    told(page)
    page.wait_for_function("""() =>
        [...CSS.highlights.get('lf-mark')][0] !== window.__lfBeforeRepaint
    """)
    repaint = page.evaluate("""() => {
        const before = window.__lfBeforeRepaint;
        const after = [...CSS.highlights.get('lf-mark')][0];
        return {
            fresh: after !== before,
            sameStart: after.startContainer === before.startContainer
                && after.startOffset === before.startOffset,
            sameEnd: after.endContainer === before.endContainer
                && after.endOffset === before.endOffset,
        };
    }""")
    assert repaint == {"fresh": True, "sameStart": True, "sameEnd": True}, repaint

    page.evaluate("() => window.__lfReleaseScrollEnd()")
    page.evaluate(
        "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
    )
    assert page.evaluate("() => window.__lfArrivalStarts") == 1, (
        "a routine repaint of the same passage canceled its completed arrival"
    )
    assert errors == []
    page.close()


def test_a_same_mark_moved_after_measurement_does_not_pulse_at_the_old_goal(
    browser, serve
):
    """Boundary identity alone is insufficient: layout above an unchanged Range can
    move its centred destination while the final edge waits. The obsolete operation
    must not announce a landing merely because it reached the goal it first measured."""
    page, errors = open_page(
        browser, serve(LONG_PAGE, anchored=[("p40", "Paragraph 40.")])
    )
    hold_arrival_scroll_ends(page)

    page.keyboard.press("j")
    page.wait_for_function("() => window.__lfHeldScrollEnds.size === 1")
    page.evaluate("() => window.__lfReleaseScrollEnd()")
    page.wait_for_function("() => window.__lfSmoothGoals.length === 1")
    page.evaluate("""() => {
        document.body.style.overflowAnchor = 'none';
        document.body.scrollTop = window.__lfSmoothGoals[0];
        const spacer = document.createElement('div');
        spacer.style.height = '200px';
        document.querySelector('#p40').before(spacer);
    }""")

    moved = page.evaluate("""() => {
        const mark = [...CSS.highlights.get('lf-mark')][0].getBoundingClientRect();
        const currentGoal = document.body.scrollTop + mark.top
            - (innerHeight - mark.height) / 2;
        return currentGoal - window.__lfSmoothGoals[0];
    }""")
    assert moved > 100, moved
    page.evaluate("() => window.__lfReleaseScrollEnd()")
    page.evaluate("() => new Promise(requestAnimationFrame)")
    assert page.evaluate("() => window.__lfArrivalStarts") == 0
    assert errors == []
    page.close()


@pytest.mark.parametrize(
    "operation_promises", [True, False], ids=["promise", "scrollend"]
)
@pytest.mark.parametrize(
    "direct_block", [False, True], ids=["paragraph", "direct-block"]
)
def test_a_comment_arrival_lifts_its_mark_after_the_page_travel(
    browser, serve, operation_promises, direct_block
):
    """The arrival belongs at the destination, not to the glide there. A long travel
    used almost half the mark's 1.2s decay before the passage entered the viewport.

    Record the animation's first frame because it is a transient state that cannot be
    polled honestly. At that frame the final scroll operation must have completed and
    the mark must be centred. A direct-text block proves the passage's parent carries
    the lift when there is no p/li/etc. text block. A scroll-end count also refuses a
    pulse at the request, before the browser has reported any completed movement."""
    source = LONG_PAGE
    if direct_block:
        paragraph = f"<p id='p40'>Paragraph 40. {'Filler. ' * 20}</p>"
        source = source.replace(
            paragraph,
            paragraph.replace("<p ", "<div ", 1).replace("</p>", "</div>"),
        )
    page, errors = open_page(
        browser, serve(source, anchored=[("p40", "Paragraph 40.")])
    )
    if not operation_promises:
        hide_scroll_operation_promises(page)
    page.evaluate("""() => {
        window.__lfArrival = {ends: 0, start: null};
        document.body.addEventListener('scrollend', () => window.__lfArrival.ends++);
        document.addEventListener('animationstart', (event) => {
            if (!event.animationName.endsWith('-arrive') || window.__lfArrival.start)
                return;
            const mark = [...CSS.highlights.get('lf-mark-here')][0]
                .getClientRects()[0];
            window.__lfArrival.start = {
                ends: window.__lfArrival.ends,
                distance: Math.abs(mark.top + mark.height / 2 - innerHeight / 2),
            };
        }, true);
    }""")

    page.keyboard.press("j")
    page.wait_for_function("() => window.__lfArrival.start !== null")
    started = page.evaluate("() => window.__lfArrival.start")

    assert started["ends"] >= 1, (
        f"the mark began its arrival before any page scroll ended: {started}"
    )
    assert started["distance"] < 1, (
        "the mark began spending its arrival before it reached the travel's destination: "
        f"{started}"
    )
    assert errors == []
    page.close()


@pytest.mark.parametrize(
    "operation_promises", [True, False], ids=["promise", "scrollend"]
)
def test_an_interrupted_comment_travel_cannot_arrive_later(
    browser, serve, operation_promises
):
    """An arrival belongs to the commanded travel, not merely to its old coordinate.

    Interrupt a long glide, then reach the abandoned destination with an unrelated
    instant scroll. Completion scoped to the original operation reports the abort, so
    that later movement has no arrival left to satisfy."""
    page, errors = open_page(
        browser, serve(LONG_PAGE, anchored=[("p40", "Paragraph 40.")])
    )
    if not operation_promises:
        hide_scroll_operation_promises(page)
    page.evaluate("""() => {
        document.documentElement.style.overflowAnchor = 'none';
        document.body.style.overflowAnchor = 'none';
        const mark = [...CSS.highlights.get('lf-mark')][0].getClientRects()[0];
        const goal = Math.max(0, Math.min(
            document.body.scrollHeight - document.body.clientHeight,
            document.body.scrollTop + mark.top - (innerHeight - mark.height) / 2));
        window.__lfInterruptedArrival = {goal, starts: 0};
        document.addEventListener('animationstart', (event) => {
            if (event.animationName.endsWith('-arrive'))
                window.__lfInterruptedArrival.starts++;
        }, true);
    }""")

    page.keyboard.press("j")
    page.wait_for_function(
        """() => { const s = window.__lfInterruptedArrival;
                   return document.body.scrollTop > 0
                       && document.body.scrollTop < s.goal - 50; }"""
    )
    page.evaluate(
        """async () => {
            const ended = new Promise(resolve =>
                document.body.addEventListener('scrollend', resolve, {once: true}));
            const completion = document.body.scrollTo({top: 0, behavior: 'instant'});
            if (typeof completion?.then === 'function') await completion;
            else await ended;
        }"""
    )
    page.evaluate(
        "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
    )
    assert page.evaluate(
        """() => Math.abs(document.body.scrollTop
                        - window.__lfInterruptedArrival.goal) > 50"""
    ), "the interrupt did not leave the commanded destination"
    assert page.evaluate("() => window.__lfInterruptedArrival.starts") == 0, (
        "the aborted glide announced a destination it never reached"
    )

    page.evaluate(
        """async () => {
            const ended = new Promise(resolve =>
                document.body.addEventListener('scrollend', resolve, {once: true}));
            const completion = document.body.scrollTo({
                top: window.__lfInterruptedArrival.goal, behavior: 'instant'
            });
            if (typeof completion?.then === 'function') await completion;
            else await ended;
        }"""
    )
    assert page.evaluate(
        """() => Math.abs(document.body.scrollTop
                        - window.__lfInterruptedArrival.goal) < 1"""
    )
    page.evaluate(
        "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
    )
    assert page.evaluate("() => window.__lfInterruptedArrival.starts") == 0, (
        "an unrelated later scroll satisfied the interrupted travel's old arrival"
    )
    assert errors == []
    page.close()


def test_the_page_marks_the_comment_the_reader_is_standing_in(browser, serve):
    """A reader sent from a comment to its passage lands among every other mark on the
    page, all of them painted alike, and the panel is the only surface saying which one
    they asked for. The page says it too: the thread holding the focus paints its own
    passage apart from the rest, and the arrival lifts that paint once so the landing is
    visible before the reader has to compare washes.

    Read off the focus rather than off the travel, so it answers where the reader *is*.
    The walk moves it, a reply box keeps it — standing in a comment is standing in it
    while writing back — and leaving the panel takes it down, rather than leaving a page
    wearing "you are here" about a comment nobody is in."""
    url = serve(INLINE_PAGE)
    page, errors = open_page(browser, url)
    api = url.rsplit("/versions/", 1)[0] + "/api/event"
    for anchor, text in (
        ({"section": "p", "quote": "bold text"}, "on the first"),
        ({"section": "p2", "quote": "neighbouring block"}, "on the second"),
        ({"section": "fig"}, "on the figure"),
    ):
        post_event(
            page,
            api,
            data={"kind": "comment", "version": 1, "text": text, "anchor": anchor},
        )
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) >= 2")
    page.locator("#fig.lf-mark-el").wait_for()

    # The wash has to resolve to a colour, and to a different one at each end of the
    # lift. Nothing else in this test would notice if it stopped: a mark whose wash
    # computes to nothing wears the posted mark's own paint, which leaves the right ranges
    # in the registry, nothing to see, and every assertion below still green. Asking the
    # rule for its text does not answer it either — the CSSOM keeps a declaration full of
    # var() exactly as written, so a wash naming a function no browser has still reads
    # back non-empty. So the expression is taken from the sheet and handed to the browser
    # to compute, rather than restated here where it could drift from the rule it stands
    # for.
    wash = page.evaluate("""() => {
        const rule = [...document.styleSheets].flatMap(s => {
            try { return [...s.cssRules] } catch { return [] }
        }).find(r => (r.selectorText ?? '').includes('lf-mark-here')
                  && r.style?.backgroundColor);
        if (!rule) return null;
        const probe = document.createElement('div');
        document.body.append(probe);
        const at = (lift) => {
            probe.style.setProperty('--lf-mark-lift', String(lift));
            probe.style.backgroundColor = rule.style.backgroundColor;
            return getComputedStyle(probe).backgroundColor;
        };
        const out = {rest: at(0), peak: at(1)};
        probe.remove();
        return out;
    }""")
    assert wash, "no rule paints the standing mark at all"
    assert "rgba(0, 0, 0, 0)" not in (wash["rest"], wash["peak"]), (
        f"the standing mark's wash does not resolve, so it paints as an ordinary mark: {wash}"
    )
    assert wash["rest"] != wash["peak"], (
        f"the arrival's lift changes nothing about the wash it drives: {wash}"
    )

    assert standing_mark(page) == {"text": "", "elements": []}, (
        "a page nobody has opened a comment on is already saying the reader is in one"
    )

    # The standing paint follows focus immediately; its arrival waits for the travel's
    # final operation to complete. Record that transient edge so the checks below inspect
    # the pulse that actually began rather than racing the glide or polling a 1.2s class.
    page.evaluate("""() => {
        window.__lfArrivalStarted = false;
        document.addEventListener('animationstart', (event) => {
            if (event.animationName.endsWith('-arrive'))
                window.__lfArrivalStarted = true;
        }, true);
    }""")
    page.keyboard.press("j")
    wait_standing(page, "bold text")
    page.wait_for_function("() => window.__lfArrivalStarted")
    # The lift hangs on the block the standing passage sits in, not on the document: an
    # inherited custom property invalidates the subtree of whatever animates it, so on
    # body it recomputes every element's style on every frame of the pulse. Asserted
    # here because nothing else would notice it moving back.
    assert page.evaluate(
        "() => [...document.querySelectorAll('.lf-arrived')].map(e => e.id)"
    ) == ["p"], "the arrival's lift is not hanging on the standing passage's own block"

    # The lift has to pass through the values between its ends, which is the whole
    # difference between an arrival and a blink: an unregistered custom property animates
    # discretely, swapping at the midpoint, and would never be found part way. Held at its
    # own midpoint rather than sampled, because a decay is a state the page passes through
    # — poll for it on a loaded machine and it is over before the first look.
    lift = page.evaluate("""() => {
        const carrier = document.querySelector('.lf-arrived');
        const a = carrier?.getAnimations()[0];
        if (!a) return null;
        a.pause();
        a.currentTime = a.effect.getTiming().duration / 2;
        return getComputedStyle(carrier).getPropertyValue('--lf-mark-lift');
    }""")
    assert lift is not None, "arriving at a comment's passage lifted nothing"
    assert 0 < float(lift) < 1, (
        f"the arrival's lift jumped rather than decayed: {lift!r} at its midpoint"
    )
    # And it ends where the standing state is, or the page keeps a mark shouting for as
    # long as it is open.
    page.evaluate("""() => {
        const carrier = document.querySelector('.lf-arrived');
        carrier.getAnimations().forEach(a => a.finish());
    }""")
    assert (
        page.evaluate(
            "() => getComputedStyle(document.querySelector('.lf-arrived'))"
            ".getPropertyValue('--lf-mark-lift')"
        ).strip()
        == "0"
    ), "the arrival's lift does not settle back to the standing state"

    # The four readings of a marked passage have to stay in this order, or one of them
    # stops being visible where they overlap: the posted mark, the hover over it, the
    # standing comment's own ink, and above all three the draft the reader is writing.
    # Asked with the pointer actually resting on the standing mark, because that is the
    # overlap the order exists for and because nothing registers the hover until a mouse
    # has been over a passage. A higher highlight supplies only the properties it states,
    # so this is what lets one mark say "clickable" and "you are here" at once.
    # Opening the panel moves the document; settle it before reading pointer geometry.
    panel_settled(page)
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

    page.keyboard.press("j")
    wait_standing(page, "neighbouring block")

    # A passage with no words to paint says the same thing with the outline it already
    # wears, so the two kinds of anchor answer one question and not two.
    page.keyboard.press("j")
    wait_standing(page, "", ["fig"])

    # Standing in a comment while writing back to it is still standing in it: the reply
    # box is inside the thread, and knowing which passage it is on is worth most there.
    page.locator(".lf-threads > .lf-thread").first.locator("textarea").focus()
    wait_standing(page, "bold text")

    # And leaving the panel takes it down. A mark that outlived the reader's attention
    # would be a page insisting on a comment nobody is in.
    page.evaluate("() => document.activeElement.blur()")
    wait_standing(page, "")
    assert painted(page, "lf-mark") != "", (
        "the posted marks went down with the standing one"
    )
    assert errors == []
    page.close()


def test_a_hovered_thread_rebinds_to_a_replaced_anchor(browser, serve):
    """A live version replaces the authored nodes but keeps the thread and its anchor.
    With the pointer parked on that card, the semantic hover id does not change; its
    Range still must move from the detached v1 text node onto the connected v2 one."""
    url = serve(INLINE_PAGE, anchored=[("p", "bold text")])
    page, errors = open_page(browser, live_url(url))
    page.locator(".lf-comments").click()
    panel_settled(page)
    point = card_body(page, "About this bit.")
    page.mouse.move(*point)
    wait_hovered(page, "bold text")
    page.evaluate(
        "() => { window.__lfOldHoverNode = "
        "[...CSS.highlights.get('lf-mark-hover')][0].startContainer; }"
    )
    # Keep the same live card under the pointer throughout the swap. This isolates the
    # anchor pass's record replacement from the view transition's temporary snapshots.
    page.evaluate("() => { document.startViewTransition = undefined; }")

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
            card: document.querySelector('.lf-thread')?.classList.contains('lf-mark-hover'),
        };
    }""")
    assert state == {
        "oldConnected": False,
        "text": "bold text",
        "rebound": True,
        "connected": True,
        "card": True,
    }, f"the parked hover did not move from the detached v1 anchor to v2: {state}"
    expect(page.locator(".lf-thread")).to_have_class(re.compile(r"\blf-mark-hover\b"))
    assert errors == []
    page.close()


def test_the_pointer_over_a_comment_lights_the_passage_it_is_about(browser, serve):
    """A reader scanning a full panel asks the same thing of every card — which of these
    is about what — and pressing one to find out spends a travel they may not want. The
    pointer resting on the card answers it: a card is the thread's view in the list the
    way a mark is its view in the prose, so the same wash lights the same passage from
    either side. The standing mark answers the question for the comment the reader chose;
    this answers it for the one under their hand.

    Read in the frame that already answers the page's own hover, because the pointer is
    in one place and the two readings are one answer: markAt refuses a point that lands
    in the chrome, so a card's reading and a mark's cannot both name a thread, and a
    second writer to this highlight would be overwritten by whichever frame ran last.

    The cursor stays behind on the page. It is the promise that pressing here opens
    something, and over a card the press on offer is the card's own."""
    url = serve(INLINE_PAGE)
    page, errors = open_page(browser, url)
    api = url.rsplit("/versions/", 1)[0] + "/api/event"
    for anchor, text in (
        ({"section": "p", "quote": "bold text"}, "on the first"),
        ({"section": "p2", "quote": "neighbouring block"}, "on the second"),
        ({"section": "fig"}, "on the figure"),
    ):
        post_event(
            page,
            api,
            data={"kind": "comment", "version": 1, "text": text, "anchor": anchor},
        )
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) >= 2")
    page.locator(".lf-comments").click()
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
        const rules = [...document.styleSheets].flatMap(s => {
            try { return [...s.cssRules] } catch { return [] }
        });
        const probe = document.createElement('div');
        probe.style.setProperty('--lf-mark-lift', '0');  // the standing wash at rest
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
        "two steps of the mark ramp are too close for a reader to tell apart without one"
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

    # An element anchor answers too, in the property it has. ::highlight paints glyphs and
    # a box has none, so the wash lands on nothing there and the middle step is said in
    # the outline instead — the same rank, one weight up from the posted hairline. Without
    # it the pointer over an element-anchored card did nothing at all, which from the
    # panel reads as a broken hover rather than as a passage with no words.
    page.mouse.move(*card_body(page, "on the figure"))
    wait_hovered(page, "")
    hovered_el = page.locator("#fig")
    expect(hovered_el).to_have_class(re.compile(r"\blf-mark-hover\b"))
    assert (
        page.evaluate(
            "() => getComputedStyle(document.querySelector('#fig')).outlineWidth"
        )
        == "2px"
    ), "the pointer on an element-anchored card left its box unchanged"

    # Standing in one comment while pointing at another says both, because they answer
    # different questions and rank apart: the standing mark keeps its ink above the wash.
    page.locator(".lf-thread").filter(has_text="on the first").first.focus()
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
    assert errors == []
    page.close()


def test_closing_the_panel_puts_down_the_card_it_was_lighting(browser, serve):
    """The panel going away is the card going out from under the pointer, and the wash it
    was lighting has to go with it. Escape closes the panel from wherever the reader is
    standing, so the pointer never moves and nothing else asks the hover question again —
    the page is left washing a passage with no card, no pointer on it, and nothing on the
    screen that says why."""
    url = serve(INLINE_PAGE)
    page, errors = open_page(browser, url)
    post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "comment",
            "version": 1,
            "text": "on the first",
            "anchor": {"section": "p", "quote": "bold text"},
        },
    )
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) >= 1")
    page.locator(".lf-comments").click()
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 1")

    page.mouse.move(*card_body(page, "on the first"))
    wait_hovered(page, "bold text")

    page.keyboard.press("Escape")
    page.wait_for_function("() => !document.body.hasAttribute('data-lf-panel')")
    wait_hovered(page, "")
    assert errors == []
    page.close()


def test_a_commented_block_says_so_to_a_screen_reader(browser, serve):
    """A mark is painted, not wrapped, so it builds no accessibility node and a passage
    carrying a comment reads exactly like one that doesn't. No ARIA relation reaches a
    block that isn't focusable, so the pass says it in the one thing every screen reader
    announces — text — counting up per block, riding in on a sent comment's round trip,
    and leaving with its thread. Having put words on the page, it then has to keep them
    out of the document's own: out of a selection, out of the next quote, and out of the
    mutations a screen reader rebuilds its buffer on."""
    url = serve(NOTED_PAGE)
    d = serve.page_dir

    def comment(anchor, text):
        return interact.append_event(
            d,
            {
                "kind": "comment",
                "author": "user",
                "version": 1,
                "text": text,
                "anchor": anchor,
            },
        )["id"]

    c1 = comment({"quote": "first passage"}, "Sharpen this.")
    c2 = comment({"quote": "two separate remarks"}, "Second thought.")
    comment({"section": "fig"}, "The figure too.")
    page, errors = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    # Two threads on one block count up, and leave one line rather than two.
    assert "2 comments" in page.locator("#p1").aria_snapshot(), (
        "a screen reader reading the block hears nothing about the comments on it"
    )
    assert page.locator("#p1 .lf-mark-note").count() == 1, "one block, one line"
    # Hidden means hidden from the eye, not the tree: a line that paints is the runtime
    # writing visible prose into the author's paragraph.
    assert page.locator("#p1 .lf-mark-note").evaluate(
        "el => { const r = el.getBoundingClientRect(); return r.width <= 1 && r.height <= 1; }"
    ), "the hidden line is painting on screen"
    note = page.locator("#p1 .lf-mark-note")
    expect(note).to_have_role("button")
    note.focus()
    expect(note).to_be_focused()
    assert note.evaluate("el => el.getBoundingClientRect().width > 1"), (
        "the comment path stayed invisible when a keyboard reader reached it"
    )
    note.press("Enter")
    expect(page.locator(f'.lf-thread[data-id="{c1}"]')).to_be_focused()
    page.keyboard.press("j")
    expect(page.locator(f'.lf-thread[data-id="{c2}"]')).to_be_focused()

    # Once the first thread resolves, the same control enters the next one.
    interact.append_event(d, {"kind": "resolve", "author": "user", "parent": c1})
    told(page)
    expect(note).to_have_text("1 comment")
    note.press("Enter")
    expect(page.locator(f'.lf-thread[data-id="{c2}"]')).to_be_focused()
    # An element anchor has no text to paint, and the element it names holds the line.
    assert "1 comment" in page.locator("#fig").aria_snapshot()

    # A pass that finds nothing to change must change nothing: a screen reader rebuilds
    # its buffer on every mutation, and this pass runs on every poll. A comment on no
    # passage at all is what proves a pass ran without touching the block's count.
    page.evaluate("""() => {
        window.__churn = 0;
        new MutationObserver(rs => (window.__churn += rs.length))
            .observe(document.getElementById('p1'),
                     {childList: true, characterData: true, subtree: true});
    }""")
    comment({}, "On the page as a whole.")
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 4")
    assert page.evaluate("() => window.__churn") == 0, (
        "a poll that changed nothing still rewrote the block, so a screen reader re-reads it"
    )

    # The line belongs to the runtime, not the document: a user dragging across it
    # neither copies it nor quotes it.
    page.locator("#p1").click(click_count=3)
    assert "comment" not in page.evaluate("() => getSelection().toString()"), (
        "the hidden line came along in the user's own selection"
    )
    page.locator(".lf-fab").click()
    assert "comment" not in composer_quote(page)["text"], (
        "the hidden line came along in the quote the comment would store"
    )
    page.get_by_role("button", name="Cancel").click()

    # The gesture's own comment reaches the line once the send's round trip lands.
    box = page.locator("#p2").bounding_box()
    y = box["y"] + box["height"] / 2
    select(page, (box["x"] + 2, y), (box["x"] + box["width"] - 2, y))
    page.locator(".lf-fab").click()
    page.wait_for_function(
        "() => document.querySelector('.lf-composer').style.display === 'block'"
    )
    page.locator(".lf-composer textarea").fill("Too short.")
    page.get_by_role("button", name="Comment", exact=True).click()
    expect(page.locator("#p2 .lf-mark-note")).to_have_count(1)
    c4 = [e for e in interact.read_events(d) if e.get("kind") == "comment"][-1]["id"]

    # A resolved thread takes its line with it: the pass owns what it wrote.
    interact.append_event(d, {"kind": "resolve", "author": "user", "parent": c4})
    told(page)
    expect(page.locator("#p2 .lf-mark-note")).to_have_count(0)
    assert "1 comment" in page.locator("#p1").aria_snapshot()

    # A passage crossing two blocks says so in both: a reader landing on either block
    # hears about the comment, the way the paint reaches both.
    comment({"quote": "to land in it. A short second"}, "Crosses the boundary.")
    told(page)
    expect(page.locator("#p2 .lf-mark-note")).to_have_count(1)
    assert "2 comments" in page.locator("#p1").aria_snapshot()
    assert "1 comment" in page.locator("#p2").aria_snapshot()
    assert errors == []
    page.close()


def test_no_address_is_drawn_on_top_of_another(browser, serve):
    """An address the reader can read is one no other address is sitting on.

    Chips are centred on the corner their member starts at, and a chip is wider than it was
    — it carries a letter now. Two addressable things can start within that width: markers
    in a footnote run, or a link that is the whole of a summary, which is one corner in two
    lists at once and could not arise while a letter had to be pressed before anything was
    painted.

    Stacked, they do not read as two. The lower one shows an edge and the upper one's digit
    is the number the reader takes for the link underneath — so the promise is wrong rather
    than merely crowded, and the press goes somewhere else. The covered chip is taken down
    instead: its address still works, and the page has simply not said it, which is the
    answer already given for a member scrolled off screen.

    What is asserted is the property and not a count, because how many survive is the
    font's answer about how wide the keys are."""
    page, errors = open_page(browser, serve(CROWDED_PAGE))
    resized(page, 1280, 800)
    page.keyboard.press("g")
    # Something is on offer, or the rest of this proves nothing: four links and a
    # disclosure, of which the crowded ones are meant to lose their chips.
    expect(page.locator(CHIPS).first).to_be_visible()

    piles = page.evaluate(
        """() => {
             const boxes = [...document.querySelectorAll('.lf-addresses > .lf-address')]
               .map(chip => ({keys: chip.textContent, r: chip.getBoundingClientRect()}));
             const hit = (a, b) => a.left < b.right && b.left < a.right
                                && a.top < b.bottom && b.top < a.bottom;
             const found = [];
             for (let i = 0; i < boxes.length; i++)
               for (let j = i + 1; j < boxes.length; j++)
                 if (hit(boxes[i].r, boxes[j].r))
                   found.push(boxes[i].keys + ' under ' + boxes[j].keys);
             return {found, drawn: boxes.map(b => b.keys)};
           }"""
    )
    assert piles["found"] == [], (
        f"addresses are drawn on top of each other: {piles['found']} "
        f"(drawn: {piles['drawn']})"
    )
    # And the ones that survived still say what they reach: pressing the first link's own
    # digit lands on that link and not on the neighbour whose chip it might have worn.
    first = piles["drawn"][0]
    letter, digit = first.split(" ")
    page.keyboard.press(letter)
    page.keyboard.press(digit)
    assert page.evaluate("() => document.activeElement.id") in {
        "fn1",
        "fn2",
        "fn3",
        "lk-sum",
        "dsc-head",
    }, f"{first} did not reach an addressable member"
    assert errors == []
    page.close()


def test_an_address_is_never_drawn_on_the_key_line(browser, serve):
    """The chord's own legend is the one thing its chips must not cover.

    A chip is placed from its member's corner in a layer above everything, and the key line
    stands in the bottom-left corner of that same layer. A member whose first line begins
    there therefore wears its address on top of the line — which is the legend saying what
    the digits mean, on screen for exactly as long as the chips are. The banner at the top
    has always been dodged; the line at the foot was not, and the change that paints every
    list at once put four times as many chips in reach of it.

    Dropped rather than nudged clear: moved up, the chip would name a member it no longer
    sits on, and the address works whether or not the page draws it."""
    page, errors = open_page(browser, serve(FOOTED_PAGE))
    resized(page, 900, 700)
    page.keyboard.press("g")
    expect(page.locator(CHIPS).first).to_be_visible()

    # Swept rather than asked once. The line's height is reserved at the document's foot,
    # so the end of the page is exactly where this cannot happen; what puts a member in the
    # corner is an ordinary scroll position with a link resting on the bottom edge. Each
    # step waits for the runtime's own paint frame, since the chips follow a scroll on a
    # frame of their own and boxes read in the same turn are the positions it just left.
    fouled = page.evaluate(
        """async () => {
             const frame = () => new Promise(r => requestAnimationFrame(() => r()));
             const line = () => document.querySelector('.lf-keyline').getBoundingClientRect();
             const hit = (a, b) => a.left < b.right && b.left < a.right
                                && a.top < b.bottom && b.top < a.bottom;
             const out = [];
             const room = document.body.scrollHeight - document.body.clientHeight;
             for (let i = 0; i <= 20; i++) {
               document.body.scrollTo(0, Math.round((room * i) / 20));
               await frame(); await frame();
               const bar = line();
               for (const chip of document.querySelectorAll('.lf-addresses > .lf-address'))
                 if (hit(chip.getBoundingClientRect(), bar))
                   out.push(chip.textContent + ' at ' + Math.round(document.body.scrollTop));
             }
             return out;
           }"""
    )
    assert fouled == [], (
        f"addresses are drawn over the key line that explains them: {fouled}"
    )
    assert errors == []
    page.close()


def test_the_g_chord_addresses_every_list_the_page_has(browser, serve):
    """g names a list and then a place in it. The letter is what made the chord general:
    it was one list deep — g then a digit, and the digit meant a reply box — so the one
    list that asked first held the whole of a leader, and the line advertised a range that
    only ever counted threads.

    So each list states itself, and every surface reads the table: the letters on the line
    are the lists the page has, the digits are the members the named one holds, each member
    on screen wears its own two-key address as a chip from the moment the chord is armed,
    and a reply box's placeholder speaks the whole address it answers to. What is asserted
    here is that the lists behave as one mechanism — a comment, an ask, a link and a
    disclosure reached the same way — rather than that any of them works, which is each
    list's own business elsewhere."""
    url = serve(ADDRESSED_PAGE)
    d = serve.page_dir

    def comment(anchor, text):
        return interact.append_event(
            d,
            {
                "kind": "comment",
                "author": "user",
                "version": 1,
                "text": text,
                "anchor": anchor,
            },
        )["id"]

    # The addresses are the panel's order, which is the page's: p1's two passages in the
    # order they are written, then p2. Each quote occurs once — a repeated one resolves to
    # nowhere by design, and a thread with nowhere to be is addressed after the ones that
    # have somewhere, which would make these three numbers a fact about that instead.
    c1 = comment({"quote": "passage under discussion"}, "Sharpen this.")
    c2 = comment({"quote": "two separate remarks"}, "Second thought.")
    c3 = comment({"section": "p2"}, "The short one too.")  # the third address
    page, errors = open_page(browser, url)
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 3")
    line = page.locator(".lf-keyline")

    # The page's own key is the letter alone: what it opens is a table, and a range on the
    # line here could only ever have counted one of the lists in it.
    expect(line).to_contain_text("go to")
    expect(line).not_to_contain_text("1–3")

    # Wide enough that the panel will stand beside the page rather than over it, which is
    # where a box in the chrome and the page's own scroller part company: body is narrowed
    # to the column, the panel is fixed and is not inside it, and a chip placed by walking
    # the page's clips came back with the whole reply box clipped away.
    resized(page, 1280, 800)

    # Armed, the line is the lists the page has — one chip each, counting what each holds.
    page.keyboard.press("g")
    expect(line).to_contain_text("c 1–3")
    expect(line).to_contain_text("comments")
    expect(line).to_contain_text("a 1")
    expect(line).to_contain_text("asks")
    expect(line).to_contain_text("l 1–2")
    expect(line).to_contain_text("links")
    expect(line).to_contain_text("d 1")
    expect(line).to_contain_text("disclosures")
    # And the page wears the offer: everything addressable on screen carries its whole
    # address, so the press that opened the window states what the next one reaches. The
    # comments are the one list absent, its panel being shut — a chip is drawn from a
    # member's own visible box, and a shut panel gives none.
    expect(page.locator(CHIPS)).to_have_text(["a 1", "l 1", "l 2", "d 1"])
    # The chips are the eye's copy of a mode; a reader who cannot see them is told the
    # window opened and what it holds, off the same rows the line just drew — the ranges
    # among them, where a row whose label counts the page used to be read out key by key
    # while an option group's, written as a string, was spelled "1–3".
    expect(page.locator(".lf-live")).to_contain_text("c 1–3 comments")

    # A letter names one, and naming it shows it: the comments live in a panel that draws
    # nothing while it is shut, so the letter opens it and the members then wear their
    # addresses — on the box the digit lands in, which for a comment is its reply box
    # rather than the thread's own corner. Opened on the digit instead, the letter painted
    # nothing at all and the addresses arrived after the choice they were for.
    expect(page.locator(".lf-panel")).not_to_be_visible()
    page.keyboard.press("c")
    expect(page.locator(".lf-panel")).to_be_visible()
    # Waited for rather than read, the strip the panel holds being the layout's answer to
    # the open and not the open itself.
    page.wait_for_function(
        "() => document.querySelector('.lf-thread > .lf-compose')"
        ".getBoundingClientRect().left > document.body.clientWidth"
    )
    # The offer narrows to the named list: the links and the disclosure drop their chips,
    # and the three that arrive say the same two keys their boxes answer to whether or not
    # anything is armed — the reply box's placeholder reads them out below.
    expect(page.locator(CHIPS)).to_have_text(["c 1", "c 2", "c 3"])
    assert page.evaluate(
        """() => {
             const chips = [...document.querySelectorAll('.lf-addresses > .lf-address')];
             const boxes = [...document.querySelectorAll('.lf-thread > .lf-compose')];
             return chips.map((chip, i) => {
               const c = chip.getBoundingClientRect(), b = boxes[i].getBoundingClientRect();
               return Math.abs(c.left + c.width / 2 - b.left) < 2
                 && Math.abs(c.top + c.height / 2 - b.top) < 2;
             });
           }"""
    ) == [True, True, True], "the chips are not the addresses of the boxes under them"
    # The chord's own chip says which stage the reader is at, and the digits are now the
    # whole of what the letter's row promises — spoken as well as drawn.
    expect(line).to_contain_text("1–3")
    expect(line).to_contain_text("cancel")
    expect(page.locator(".lf-live")).to_contain_text("1–3 comments")

    # And the digit arrives, however long the reader took over it: the mode stands until
    # something ends it, where a clock used to end it at a second and a half — and a letter
    # arriving after that clock was not a no-op but the page's own key, so a slow reader
    # pressing `l` got the leaves tray rather than the links.
    page.wait_for_timeout(2000)
    expect(line).to_contain_text("1–3")
    page.keyboard.press("2")
    ta2 = page.locator(f'.lf-thread[data-id="{c2}"] textarea')
    expect(ta2).to_be_focused()
    expect(page.locator(CHIPS)).to_have_count(0)
    # The focused box claims the send keys; an unfocused one speaks its own address, whole
    # — the chip is the aimed moment's copy of a fact the placeholder states always.
    expect(ta2).to_have_attribute("placeholder", re.compile(r"Reply · (⌘⏎|Ctrl\+⏎)$"))
    expect(page.locator(f'.lf-thread[data-id="{c1}"] textarea')).to_have_attribute(
        "placeholder", "Reply · g c 1"
    )

    # A digit outside the window is nothing: Esc backs out to the thread, and 3 stays put
    # rather than reaching the third address the window had just been offering.
    page.keyboard.press("Escape")
    expect(page.locator(f'.lf-thread[data-id="{c2}"]')).to_be_focused()
    page.keyboard.press("3")
    expect(page.locator(f'.lf-thread[data-id="{c2}"]')).to_be_focused()

    # The same motion into a different list. An ask is reached by the control that decides
    # it, wearing the ring that says where the reader is standing.
    #
    # Scrolled first so the banner has taken the ask's own corner. The bar stands over the
    # page and clips none of it, so the reading that says where a member is (shownRect) is
    # right to ignore it and the chip is the one thing that cannot: placed on that corner it
    # is a digit floating over the status line, addressing nothing the reader can see there.
    page.evaluate(
        """() => { const ask = document.getElementById('opts');
                   document.body.scrollTo(
                     0, ask.getBoundingClientRect().top + document.body.scrollTop - 8); }"""
    )
    page.keyboard.press("g")
    page.keyboard.press("a")
    expect(page.locator(CHIPS)).to_have_text(["a 1"])
    assert page.evaluate(
        """() => document.querySelector('.lf-addresses > .lf-address')
                   .getBoundingClientRect().top
                 >= document.querySelector('.lf-banner').getBoundingClientRect().bottom"""
    ), "the ask's address chip is drawn over the banner"
    page.keyboard.press("1")
    expect(page.locator("#opts .lf-pick").first).to_be_focused()
    expect(page.locator("#opts[data-lf-ask]")).to_have_count(1)

    # The links, from the head of the page where both are on screen. A chip is hung on the
    # corner a member starts at, which for an inline that wraps is the corner of its first
    # line and not of its bounding box — those run the width of the column, so a digit
    # placed there sits a line above the words it addresses, over somebody else's sentence.
    page.evaluate("() => document.body.scrollTo(0, 0)")
    page.keyboard.press("g")
    page.keyboard.press("l")
    expect(page.locator(CHIPS)).to_have_text(["l 1", "l 2"])
    assert page.evaluate(
        """() => {
             const links = [...document.querySelectorAll('#refs a[href]')];
             const chips = [...document.querySelectorAll('.lf-addresses > .lf-address')];
             return {wrapped: links[0].getClientRects().length > 1,
                     on: chips.map((chip, i) => {
                       const c = chip.getBoundingClientRect();
                       const first = links[i].getClientRects()[0];
                       return Math.abs(c.left + c.width / 2 - first.left) < 2
                           && Math.abs(c.top + c.height / 2 - first.top) < 2;
                     })};
           }"""
    ) == {
        "wrapped": True,
        "on": [True, True],
    }, "a chip is not on the corner its link starts at"
    page.keyboard.press("Escape")

    # And from the foot of the page, where neither of them can be seen.
    # A list is the document's and not the window's, so an address means the same link at
    # every scroll position and holds where no chip can be drawn for it — counted what is
    # in the window, `g l 2` would name a different link each time the reader moved, and
    # the line would go stale about which digits are live every time the page scrolled.
    # The arrival is the focus, and the press that finishes the motion is the platform's:
    # named on the line, or the reader lands with nothing said.
    page.evaluate("() => document.body.scrollTo(0, document.body.scrollHeight)")
    page.keyboard.press("g")
    expect(line).to_contain_text("l 1–2")
    page.keyboard.press("l")
    expect(page.locator(CHIPS)).to_have_count(0)
    page.keyboard.press("2")
    expect(page.locator("#lk2")).to_be_focused()
    expect(line).to_contain_text("follow")

    # The panel folds its resolved comments into a <details> of its own, and that box is
    # the chrome's. A list is what the document holds, so it is not addressed: read of the
    # document at large, `d` would offer a digit for a disclosure the author never wrote
    # and the reader never sees on the page.
    interact.append_event(d, {"kind": "resolve", "author": "user", "parent": c3})
    told(page)
    expect(page.locator("details.lf-details")).to_have_count(1)
    page.keyboard.press("g")
    expect(line).to_contain_text("d 1")
    expect(line).not_to_contain_text("d 1–2")
    page.keyboard.press("Escape")

    # The disclosures, and the one arrival that changes the page it arrives at. Every
    # other member is reached through a reveal that opens the collapsed boxes on the way;
    # here the box is the member, so that same reveal is the whole motion, and the reader
    # who wanted a section open has it open having asked once.
    page.evaluate("() => document.body.scrollTo(0, 0)")
    page.keyboard.press("g")
    page.keyboard.press("d")
    expect(page.locator(CHIPS)).to_have_text(["d 1"])
    assert page.evaluate(
        """() => {
             const c = document.querySelector('.lf-addresses > .lf-address')
                        .getBoundingClientRect();
             const first = document.getElementById('dsc-head').getClientRects()[0];
             return Math.abs(c.left + c.width / 2 - first.left) < 2
                 && Math.abs(c.top + c.height / 2 - first.top) < 2;
           }"""
    ), "the chip is not on the corner the summary starts at"
    expect(page.locator("#dsc")).not_to_have_attribute("open", "")
    page.keyboard.press("1")
    expect(page.locator("#dsc-head")).to_be_focused()
    expect(page.locator("#dsc")).to_have_attribute("open", "")

    # Standing there, the line says which way the next press goes — the platform's press,
    # which the runtime names rather than binds, and which is Space as well as Enter here
    # where a link takes Enter alone, Space under one being the page's own scroll. A word
    # fixed at declaration could say only one of the two directions.
    expect(line).to_contain_text(re.compile(r"⏎ / space\s*close"))
    page.keyboard.press("Enter")
    expect(page.locator("#dsc")).not_to_have_attribute("open", "")
    # Timed out short, because the poll would otherwise answer for the toggle. Opening a
    # disclosure is the one change in what the next press does that no writer in the
    # runtime reports, so the word stood at "close" for the three seconds until a poll
    # came past — and every assertion that waits reads a stale line as an eventually
    # right one.
    expect(line).to_contain_text(re.compile(r"⏎ / space\s*open"), timeout=1500)
    page.keyboard.press(" ")
    expect(page.locator("#dsc")).to_have_attribute("open", "")
    expect(line).to_contain_text(re.compile(r"⏎ / space\s*close"), timeout=1500)

    # The two completions that take no digit: an edge of the page is one place, so the
    # second key is the whole address — G glides to the bottom, g to the top.
    foot = page.evaluate(
        "() => document.body.scrollHeight - document.body.clientHeight"
    )
    assert foot > 0, "the page must scroll for an edge to be a move at all"
    page.keyboard.press("g")
    expect(line).to_contain_text("top / bottom")
    # Shift spelled out: a bare press("G") synthesizes key "G" with no shift modifier,
    # which a real keyboard cannot do, and the dispatcher rightly reads it as g.
    page.keyboard.press("Shift+G")
    page.wait_for_function(
        "foot => Math.abs(document.body.scrollTop - foot) < 1", arg=foot
    )
    page.keyboard.press("g")
    page.keyboard.press("g")
    page.wait_for_function("() => document.body.scrollTop === 0")

    # A key naming no list disarms the chord and keeps its ordinary meaning: g j is a
    # thread step, so a mistyped g costs nothing.
    page.keyboard.press("g")
    page.keyboard.press("j")
    expect(page.locator(f'.lf-thread[data-id="{c1}"]')).to_be_focused()

    # Typing contexts are untouched: in a box, the whole chord is text.
    page.keyboard.press("Enter")
    ta1 = page.locator(f'.lf-thread[data-id="{c1}"] textarea')
    expect(ta1).to_be_focused()
    page.keyboard.type("gc1")
    expect(ta1).to_have_value("gc1")
    expect(ta1).to_be_focused()
    assert errors == []
    page.close()


def test_the_key_line_says_what_a_press_will_do(browser, serve):
    """The key line renders the same scene() escapeKey() runs, so what Esc promises
    is what Esc then does, rung by rung: general box → the list → the panel closed.
    And the armed chord is on screen with the panel closed — where the old corner
    badges, display:none inside it, said nothing at all."""
    url = serve(NOTED_PAGE)
    interact.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "version": 1,
            "text": "One thread.",
            "anchor": {"quote": "first passage"},
        },
    )
    page, errors = open_page(browser, url)
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 1")
    line = page.locator(".lf-keyline")

    # Page scope: the standing verbs, thread rows only over threads, and no esc
    # chip — there is nothing to back out of.
    expect(line).to_contain_text("comment")
    expect(line).to_contain_text("threads")
    expect(line).to_contain_text("more")
    expect(line).not_to_contain_text("esc")

    # Armed with the panel closed: the pending chord and its way out are on screen, and
    # the letter's chip counts the one thread there is rather than promising nine.
    page.keyboard.press("g")
    expect(line).to_contain_text("comments")
    expect(line).to_contain_text("c 1")
    expect(line).not_to_contain_text("1–9")
    expect(line).to_contain_text("cancel")
    page.keyboard.press("Escape")
    expect(line).not_to_contain_text("comments")

    # c opens the panel into the general box: the line says send, and where Esc goes.
    page.keyboard.press("c")
    expect(line).to_contain_text("send")
    expect(line).to_contain_text("back to list")
    # A send key on an empty box is answered, not swallowed — silence reads as a
    # send that happened.
    page.keyboard.press("ControlOrMeta+Enter")
    expect(page.locator(".lf-toast")).to_contain_text("Nothing to send")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-threads")).to_be_focused()
    expect(line).to_contain_text("close comments")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-panel")).to_be_hidden()
    expect(line).not_to_contain_text("close comments")
    # Focus doesn't fall to body: it lands on the control that reopens the panel.
    expect(page.locator(".lf-comments")).to_be_focused()

    # The fast rung: j reopens onto a thread, and Esc from it is one press out.
    # Every rung earns a press here because Esc is the only keyboard collapse.
    page.keyboard.press("j")
    expect(page.locator(".lf-thread")).to_be_focused()
    expect(line).to_contain_text("close comments")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-panel")).to_be_hidden()
    assert errors == []
    page.close()


def test_a_key_the_runtime_binds_is_a_key_some_surface_names(browser, serve):
    """One declaration per binding, and every surface is a projection of it — so a key
    cannot be bound and go unnamed. `d` and `u` are the case that named this. They have
    stepped half a page for as long as the runtime has had them and the reference has
    always carried them, while the always-visible line never did: the line's word was an
    optional field, and its absence read exactly like a decision not to show the key.

    It is refused now, where a scope is declared, so the next binding written without a
    word fails on the page that introduces it rather than going quiet on every page after
    it. A row that presses nothing needs none — F7 is the browser's caret browsing, real
    and worth knowing and not what the next press does."""
    page, errors = open_page(browser, serve(NOTED_PAGE))
    line = page.locator(".lf-keyline")
    expect(line).to_contain_text("d / u")
    expect(line).to_contain_text("half a page")
    page.keyboard.press("?")
    expect(page.locator(".lf-help")).to_contain_text("Half a page down / up")
    expect(page.locator(".lf-help")).to_contain_text("Caret browsing")
    page.keyboard.press("Escape")
    expect(line).not_to_contain_text("F7")

    refused = page.evaluate(
        """async () => {
          const { keys } = await import('/leaf.js');
          try {
            keys(document.body, 'A project scope', [
              { keys: ['F2'], does: 'a press with nothing to say for itself',
                run: () => {} },
            ]);
            return 'declared';
          } catch (e) {
            return e.message;
          }
        }"""
    )
    assert "no word for the key line" in refused, refused

    # The other half of what this gate is for, and the quieter failure. `answers` asks
    # after Mod, Alt and Shift by name and reads every other prefix as absent, so a
    # binding written `Ctrl+k` is not a key that never fires — it is `k`, which fires on
    # a bare press while both surfaces spell the chip "Ctrl+k" and the press the chip
    # names does nothing. A declaration that means a different key than it says is the
    # one thing no surface can project, so it is refused where declarations enter.
    modified = page.evaluate(
        """async () => {
          const { keys } = await import('/leaf.js');
          try {
            keys(document.body, 'A project scope', [
              { keys: ['Ctrl+k'], does: 'a modifier the matcher never asks about',
                line: 'a key that is really just k', run: () => {} },
            ]);
            return 'declared';
          } catch (e) {
            return e.message;
          }
        }"""
    )
    assert "Ctrl is no modifier" in modified, modified
    assert "Mod, Alt, Shift" in modified, modified
    assert errors == []
    page.close()


def test_the_register_is_the_only_way_a_key_enters_the_runtime():
    """Every surface that names a key is a projection of the register, which holds only if
    nothing binds a key behind its back. That is not a property a rendered page can be
    asked about — a listener nobody declared looks exactly like no listener at all until
    the press it eats goes missing — so it is pinned in the source, the way the
    document-level class surface is.

    Two are allowed and both are named here. The dispatcher is the register's own. The aim
    latch is not a binding at all: holding ⌥ arms nothing and answers no press, it paints
    what a click would take, and its keyup half has no place in a table of presses. A third
    is how every drift this register replaced began — a `keydown` beside a display list,
    the two of them free to disagree about which keys the widget answers."""
    layer = Path(__file__).resolve().parent.parent / "plugins/leaf/skills/leaf"
    sources = [
        layer / "assets/leaf.js",
        *sorted((layer / "bundled/widgets").glob("*.js")),
    ]
    listeners = [
        f"{src.name}:{n}"
        for src in sources
        for n, line in enumerate(src.read_text().splitlines(), 1)
        if 'addEventListener("keydown"' in line
    ]
    assert len(listeners) == 2, (
        f"the runtime's keydown listeners changed: {listeners}. A key belongs in the "
        "register (keys(el, title, rows)), which is what lets a surface promise it."
    )


def test_the_reference_names_the_space_that_works_a_control(browser, serve):
    """`offer` builds every press as a span wearing role="button", so the keys the
    platform would have given a real button are the runtime's to supply — and it supplied
    them through a listener no surface could see. Space activated nine classes of control
    across core and five widgets, and exactly one of them said so anywhere.

    The activation is a scope now, so the reference names it once for all of them, and a
    widget whose press means more than "work this control" says so in its own words and
    binds the same two keys. The grip is where that was wrong twice over: its handler
    answered Space in both its states while both its declarations said Enter."""
    page, errors = open_page(browser, serve(BOARD_PAGE))
    page.keyboard.press("?")
    help_el = page.locator(".lf-help")
    expect(help_el).to_contain_text("On a control")
    expect(help_el.locator("tr", has_text="Work the focused control")).to_contain_text(
        "space"
    )
    expect(help_el.locator("tr", has_text="Grab the card")).to_contain_text("space")
    page.keyboard.press("Escape")

    # And the key does what the reference says it does.
    grip = page.locator("lf-board .lf-grip").first
    grip.focus()
    page.keyboard.press(" ")
    expect(page.locator(".lf-lift")).to_have_count(1)
    expect(page.locator(".lf-keyline")).to_contain_text("drop")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-lift")).to_have_count(0)
    assert errors == []
    page.close()


def test_holding_a_key_repeats_only_where_the_press_is_a_walk(
    browser, serve, live_leaf
):
    """A held key repeats keydown where a real button fires once. A walk wants that — j
    down a list of threads, arrows down the tray — and a press that toggles or navigates
    does not: a held `]` was a page navigation per repeat, and a held pick a `choose` per
    repeat, each of them one decision the reader made once. So a row says whether it
    repeats and the default is no, where before only `offer`'s own listener had thought
    about it and the global table had not.

    No gesture Playwright makes carries the repeat flag, so the press is dispatched with
    it set. That is the event a held key sends and the handler under test is the one the
    page installed; the tap below it, dispatched the same way and answered, is what says
    so rather than leaving the held press to pass for want of reaching anything."""
    live_leaf("second", "A second leaf")
    page, errors = open_page(browser, serve(LONG_PAGE, comments=3))
    press = """([key, repeat]) => document.dispatchEvent(
        new KeyboardEvent('keydown', {key, repeat, bubbles: true, cancelable: true}))"""

    page.keyboard.press("j")
    expect(page.locator(".lf-thread").first).to_be_focused()
    page.evaluate(press, ["j", True])  # a walk repeats
    expect(page.locator(".lf-thread").nth(1)).to_be_focused()

    tray = page.locator(".lf-others-panel")
    page.keyboard.press("l")
    expect(tray).to_be_visible()
    page.evaluate(press, ["l", True])  # a toggle does not
    expect(tray).to_be_visible()
    page.evaluate(press, ["l", False])  # the same event, answered
    expect(tray).to_be_hidden()
    assert errors == []
    page.close()


def test_the_key_line_keeps_two_local_hints_and_searches_the_rest(browser, serve):
    """The short line is a glance, not the keyboard reference. It keeps two bindings:
    first the innermost live action, then the way out when the current scene has one. The
    complete register remains one `? more` away and can be searched by key, action, or
    scope.

    The panel's general box is the causal contrast for the cap. A full page row crosses
    into the panel and paints over the box; two hints end before it. The overlap is tested
    before opening the reference so a searchable popup cannot make the symptom disappear
    merely by covering both surfaces."""
    page, errors = open_page(browser, serve(NOTED_PAGE, comments=2))
    page.set_viewport_size({"width": 1200, "height": 800})
    page.get_by_role("button", name=re.compile("^Comments")).click()

    line = page.locator(".lf-keyline")
    visible_hints = line.locator(".lf-key:not([hidden])")
    assert visible_hints.count() == 2, page.evaluate(
        """() => { const line = document.querySelector('.lf-keyline'); return {
          client: line.clientWidth, scroll: line.scrollWidth,
          max: getComputedStyle(line).maxWidth,
          hints: [...line.querySelectorAll('.lf-key')].map(el => ({
            text: el.textContent, hidden: el.hidden
          }))
        }; }"""
    )
    assert not page.evaluate(
        """() => {
          const a = document.querySelector('.lf-keyline').getBoundingClientRect();
          const b = document.querySelector('.lf-general').getBoundingClientRect();
          return a.left < b.right && a.right > b.left &&
                 a.top < b.bottom && a.bottom > b.top;
        }"""
    ), "the key line covers the general comment box"

    # Moving into the box changes the two most useful hints without introducing a
    # second shortlist: the same scope order the dispatcher uses supplies them.
    page.keyboard.press("c")
    expect(visible_hints.nth(0)).to_contain_text("send")
    expect(visible_hints.nth(1)).to_contain_text("back to list")

    more = page.get_by_role("button", name="? more", exact=True)
    more.click()
    help_el = page.locator(".lf-help")
    search = page.get_by_role("searchbox", name="Search keyboard shortcuts")
    expect(help_el).to_be_visible()
    expect(search).to_be_focused()

    search.fill("d / u")
    expect(help_el.locator("tr:not([hidden])")).to_have_count(1)
    expect(help_el.locator("tr:not([hidden])")).to_contain_text("Half a page down / up")

    search.fill("comment panel")
    expect(
        help_el.get_by_role("heading", name="In the comment panel", exact=True)
    ).to_be_visible()
    expect(help_el.locator("tr:not([hidden])")).not_to_have_count(0)

    search.fill("no such shortcut")
    expect(help_el.locator(".lf-help-empty")).to_be_visible()
    expect(help_el.locator("tr:not([hidden])")).to_have_count(0)
    page.keyboard.press("Escape")
    expect(help_el).to_be_hidden()
    assert errors == []
    page.close()


def test_c_reaches_the_general_box_while_the_panel_stands_open(browser, serve):
    """c goes to the general box from any state. It doubled as the panel's
    collapse once, which left the box with no shortcut exactly while the panel
    stood open: the press that promised "comment" answered "close".
    Collapse is the ladder's — Esc from the list closes the panel, the rung the
    key-line test walks — so both stay reachable without one key meaning two
    things."""
    page, errors = open_page(browser, serve(NOTED_PAGE))
    page.keyboard.press("c")  # closed: opens the panel into the box
    expect(page.locator(".lf-general textarea")).to_be_focused()
    page.keyboard.press("Escape")  # back out to the list, focus outside any box
    expect(page.locator(".lf-threads")).to_be_focused()
    page.keyboard.press("c")  # open: still the box, never the collapse
    expect(page.locator(".lf-general textarea")).to_be_focused()
    expect(page.locator(".lf-panel")).to_have_class(re.compile("open"))
    assert errors == []
    page.close()


def test_escape_backs_out_from_a_control_nothing_is_typed_into(browser, serve):
    """A scope takes the keys it uses, so a control that has no Escape of its own
    leaves the rung standing behind it. The banner's version chooser swallowed it,
    so the panel could not be closed by key right after the user worked it; the
    fix's first attempt was a two-item denylist, which an authored slider walked
    straight past. The chooser is a button now, so what holds the rule is the
    page's own controls — which is where it always mattered, a page being free to
    author any of them.

    A slider and a select answer here for the two sides of the claim. The slider
    types nothing, so the typing scope never stands over it at all; the select's
    letters jump its options, so it stands and takes them — and takes only them,
    which is what leaves this press to the page. Reaching the rung used to be a
    branch inside the typing scope's own row, restating another scope's word.

    Which rung the press reaches is the ladder's own business, and it unwinds from
    where the reader is: standing out on the page, the first thing they are in is
    the control they are standing on, and the panel behind them is a layer they are
    not in. So the press takes two — and the panel closing on the second is the
    whole of what this test is about, the control having had every chance to
    swallow the first."""
    html = NOTED_PAGE.replace(
        "</main>",
        '<input id="zoom" type="range">'
        '<select id="pick"><option>one</option><option>two</option></select></main>',
    )
    page, errors = open_page(browser, serve(html))
    # The mouse opens between rounds because c is the select's own letter, and the
    # press has to be made the same way on both to be comparing anything.
    for control in ("#zoom", "#pick"):
        page.get_by_role("button", name=re.compile("^Comments")).click()
        expect(page.locator(".lf-panel")).to_be_visible()
        page.locator(control).focus()
        expect(page.locator(".lf-keyline")).to_contain_text("let go")
        page.keyboard.press("Escape")
        assert page.evaluate("() => document.activeElement === document.body")
        expect(page.locator(".lf-keyline")).to_contain_text("close comments")
        page.keyboard.press("Escape")
        expect(page.locator(".lf-panel")).to_be_hidden()
    assert errors == []
    page.close()


def test_a_control_that_types_nothing_keeps_the_pages_keyboard(browser, serve):
    """A scope claims the keys it uses and leaves the rest standing. This one used to
    claim the lot: the typing scope stood wherever focus was in a form control, on the
    reading that a letter is a keystroke there — true of a text box, false of a radio, a
    checkbox and a slider, none of which the platform ever hands a letter. So a reader
    standing on a screenshot's before/after switch lost c, the walks, the version keys and
    the reference itself, and the line went blank rather than wrong, which is how it
    reaches its author as "the keyboard stopped working".

    One key had already been rescued from that swallow by hand, in a branch inside the
    typing scope's own row. Every other key it took stayed taken, and that is what says the
    swallow was the wrong shape rather than one key short.

    The claim has to hold in both directions or it has bought nothing, so the control's
    own key is asserted beside the page's: a page whose keyboard stands over a radio must
    not be taking Space off it."""
    html = NOTED_PAGE.replace(
        "</main>",
        '<label><input id="flip" type="radio" name="frame"> after</label>'
        '<input id="note" type="text"></main>',
    )
    page, errors = open_page(browser, serve(html))
    line = page.locator(".lf-keyline")

    page.locator("#flip").focus()
    expect(line).to_contain_text("half a page")
    page.keyboard.press("Space")
    expect(page.locator("#flip")).to_be_checked()
    # The letter reaches the page, which is the whole claim; where it then goes is the
    # standing's business — a reader on the radio is standing on it, so the box that
    # opens is about it rather than about the page. Named in full, because "comment on
    # the" matches every destination this key has and would assert nothing about which.
    expect(line).to_contain_text("comment on the control")
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-composer")).to_contain_text("flip")
    page.keyboard.press("Escape")

    # The box beside it, where every one of those letters is the reader's. The line
    # names none of them, which is the same register saying so.
    page.locator("#note").focus()
    expect(line).not_to_contain_text("half a page")
    page.keyboard.press("c")
    expect(page.locator("#note")).to_have_value("c")
    expect(page.locator(".lf-help")).to_be_hidden()
    page.keyboard.press("?")
    expect(page.locator("#note")).to_have_value("c?")
    expect(page.locator(".lf-help")).to_be_hidden()
    assert errors == []
    page.close()


def test_the_key_line_names_what_this_press_will_comment_on(browser, serve, other_leaf):
    """A key's word is the meaning it has now, not one wide enough to cover every
    meaning it could have. c opens a box on the selection, on the item a click raised the
    💬 on, on whatever the reader is standing in, or on the page, and every one of them
    read "comment" — true of the key and silent about the press, so a reader with a
    paragraph selected and one with nothing selected were told the same thing about two
    different boxes. Both surfaces read the row where they paint it, so both say which box
    this press opens; o is the same defect and says show or hide rather than both.

    Three of the four here, this page holding nothing to stand on;
    test_c_comments_on_what_the_reader_is_standing_in owns the fourth."""
    page, errors = open_page(browser, serve(TARGETS_PAGE))
    line = page.locator(".lf-keyline")
    help_el = page.locator(".lf-help")

    # Nothing in hand: the box c opens is the page's.
    expect(line).to_contain_text("comment on the page")
    page.keyboard.press("?")
    expect(help_el).to_contain_text("Comment on the page")
    page.keyboard.press("Escape")

    # A selection under the hand moves the word, on the gesture that raises the button
    # — the anchor the line names and the one the press takes are the same one. Dragged
    # rather than select_text()'d, which sets the selection through the injected script
    # and fires neither mouseup nor keyup: the button would never rise, and the press
    # under test would be answered by a state no gesture produced.
    box = page.locator("#prose").bounding_box()
    select(
        page,
        (box["x"] + 1, box["y"] + 4),
        (box["x"] + box["width"] - 1, box["y"] + box["height"] - 4),
        steps=12,
    )
    expect(page.locator(".lf-fab")).to_be_visible()
    expect(line).to_contain_text("comment on the selection")
    page.keyboard.press("?")
    expect(help_el).to_contain_text("Comment on the selection")
    page.keyboard.press("Escape")
    # And the press does what the word said: a composer carrying that passage, which
    # is what makes the suggestion row (a replacement for quoted words) offered at all.
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-composer .lf-suggest-row")).to_be_visible()
    page.keyboard.press("Escape")

    # A visual has no words to quote, so the press lands on the element — and the word
    # is the item's own, the way the panel names one.
    page.locator("#fig svg").click()
    expect(line).to_contain_text("comment on the figure")
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-composer .lf-suggest-row")).to_be_hidden()
    page.keyboard.press("Escape")

    # l names the direction of its own toggle. Opened from the banner, because opening
    # it by key lands focus inside the tray, and the line is then the tray's own scope
    # rather than the page's — the l row is only on screen while the page's is.
    expect(line).to_contain_text("show leaves")
    page.get_by_role("button", name=re.compile("^All leaves")).click()
    expect(page.locator(".lf-others-panel")).to_have_class(re.compile("open"))
    expect(line).to_contain_text("hide leaves")
    page.keyboard.press("l")
    expect(page.locator(".lf-others-panel")).not_to_have_class(re.compile("open"))
    expect(line).to_contain_text("show leaves")
    assert errors == []
    page.close()


def test_a_key_on_screen_is_a_key_that_works(browser, serve):
    """Every surface naming a key promises the press does something now. One table
    kept the words from drifting and not the surfaces: the key line asked `when`,
    the ? overlay didn't, and a shortcut could hold its liveness where no surface
    could ask — inside its own run — so the overlay offered g 1–9 with no thread to
    reply to, and named a walk through a list of one. Liveness is one declaration,
    and the dispatcher, the line, and the overlay all ask it. The chord's lists are
    where that division earns its keep twice over: a list the page hasn't got is a
    row the reference must not name, and the section holds only what this page can
    answer — the edges always among them, every page having a top."""
    url = serve(NOTED_PAGE)
    d = serve.page_dir
    page, errors = open_page(browser, url)
    help_el = page.locator(".lf-help")

    # No open threads, one version: the reference names only what a press would do.
    page.keyboard.press("?")
    expect(help_el).to_be_visible()
    # Nothing is selected, so c's own row says the box it would open — the word is the
    # press's, not the key's (see the row's neighbour test below).
    expect(help_el).to_contain_text("Comment on the page")
    # The chord's section stands on every page — the edges need no list — but holds
    # no row for a list this page hasn't got.
    expect(help_el).to_contain_text("With g armed")
    expect(help_el).to_contain_text("top / bottom")
    expect(help_el).not_to_contain_text("open comment's reply box")
    # And no link scope: this page holds none, while the machine's own tray is full of
    # them — a scope asked about the document at large was had by every page there is.
    expect(help_el).not_to_contain_text("On a link")
    expect(help_el).not_to_contain_text("Next / previous open thread")
    expect(help_el).not_to_contain_text("On a focused thread")
    expect(help_el).not_to_contain_text("waiting on you for")
    # The chooser is the one version key a first version has: its menu holds this
    # version and what it changed, where the menu's own keys have nothing to walk.
    expect(help_el).to_contain_text("The versions, and what each one changed")
    expect(help_el).not_to_contain_text("In the versions menu")
    page.keyboard.press("Escape")
    expect(help_el).to_be_hidden()

    # The dispatcher asks the same declaration: k used to open an empty panel
    # while j, when-gated, did nothing.
    page.keyboard.press("j")
    page.keyboard.press("k")
    expect(page.locator(".lf-panel")).to_be_hidden()
    line = page.locator(".lf-keyline")
    expect(line).not_to_contain_text("threads")

    # Threads arrive, and the next open holds the rows they make live — the chord's
    # comments row counting the two there are, not the nine there could be, and no
    # row for the lists this page hasn't got.
    for text in ["A thread.", "Another."]:
        interact.append_event(
            d, {"kind": "comment", "author": "user", "version": 1, "text": text}
        )
    told(page)
    expect(page.locator(".lf-thread")).to_have_count(2)
    # The key line repaints on the same render that made them live — no focus
    # change to lean on, so the repaint is the thread render's own.
    expect(line).to_contain_text("threads")
    page.keyboard.press("?")
    expect(help_el).to_contain_text("With g armed")
    expect(help_el).to_contain_text("c 1–2")
    expect(help_el).not_to_contain_text("link on screen")
    expect(help_el).not_to_contain_text("waiting on you for")
    expect(help_el).to_contain_text("Next / previous open thread")
    expect(help_el).to_contain_text("On a focused thread")
    expect(help_el).not_to_contain_text("In the versions menu")
    page.keyboard.press("Escape")

    # A v2 lands and the unpinned page follows it; on v2 the menu's own keys are
    # live, having a list to walk and a base to walk onto.
    (d / "versions" / "v2.html").write_text(NOTED_PAGE)
    interact.append_event(
        d, {"kind": "note", "author": "claude", "version": 2, "text": "two"}
    )
    page.wait_for_url("**/versions/v2.html*")
    expect(page.locator('.lf-version-diff[data-lf-version="1"]')).to_have_count(1)
    page.keyboard.press("?")
    expect(help_el).to_contain_text("In the versions menu")
    expect(help_el).to_contain_text("Walk the versions")
    expect(help_el).to_contain_text("c 1–2")
    page.keyboard.press("Escape")

    # A resolved thread stays focusable after the last open one is gone, and the
    # scene branch that restates the j/k row over it asks the same liveness.
    page.keyboard.press("c")
    for n in [1, 2]:
        page.locator(".lf-threads > .lf-thread").first.get_by_role(
            "button", name="Resolve"
        ).click()
        expect(page.locator(".lf-details summary")).to_have_text(f"Resolved ({n})")
    # The summary counts the log before the disclosure finishes folding its list.
    expect(page.locator(".lf-details .lf-thread")).to_have_count(2)
    page.locator(".lf-details summary").click()
    resolved = page.locator(".lf-details .lf-thread").first
    resolved.click()
    expect(resolved).to_be_focused()
    expect(line).to_contain_text("close comments")
    expect(line).not_to_contain_text("threads")

    # And no disclosure scope, with the panel's own <details> standing open beside the
    # reader. A capability is what they can reach from where the scope holds, and this box
    # is the chrome's — it declares the keys it answers itself. Asked of the document at
    # large, the scope arrives on every page that has ever had a comment resolved.
    expect(page.locator(".lf-details[open]")).to_have_count(1)
    page.keyboard.press("?")
    expect(help_el).to_be_visible()
    expect(help_el).not_to_contain_text("On a disclosure")
    page.keyboard.press("Escape")
    assert errors == []
    page.close()


def test_the_resolve_key_resolves_the_focused_thread(browser, serve):
    """r resolves the thread j/k landed on, through the button's own press, so
    focus lands where the button already sends it — on the thread that takes the
    resolved one's place. The promise is scoped the way it is worded: the key
    line offers resolve only over an open focused thread, the overlay row
    carries the scope in its words, and on a focused resolved thread the press
    acts on nothing — a run that reached for "the first open thread" instead of
    the focused one would resolve a thread the user never aimed at."""
    url = serve(NOTED_PAGE)
    d = serve.page_dir

    def comment(text):
        return interact.append_event(
            d, {"kind": "comment", "author": "user", "version": 1, "text": text}
        )["id"]

    c1 = comment("First thought.")
    c2 = comment("Second thought.")
    page, errors = open_page(browser, url)
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 2")
    line = page.locator(".lf-keyline")

    # At page scope nothing promises r — its target is the focused thread, and
    # none is — while the overlay teaches the capability, scope in its words.
    expect(line).not_to_contain_text("resolve")
    page.keyboard.press("?")
    expect(page.locator(".lf-help")).to_contain_text("On a focused thread")
    expect(page.locator(".lf-help")).to_contain_text("Resolve it")
    page.keyboard.press("Escape")

    # j lands on the first thread and the line offers resolve; r takes it, and
    # focus lands on the thread now holding the resolved one's place, so j/k
    # and a second r walk on from there.
    page.keyboard.press("j")
    expect(page.locator(f'.lf-thread[data-id="{c1}"]')).to_be_focused()
    expect(line).to_contain_text("resolve")
    page.keyboard.press("r")
    expect(page.locator(".lf-details summary")).to_have_text("Resolved (1)")
    expect(page.locator(f'.lf-thread[data-id="{c2}"]')).to_be_focused()
    expect(line).to_contain_text("resolve")

    # A focused resolved thread promises nothing, and the press acts on nothing.
    expect(page.locator(f'.lf-details .lf-thread[data-id="{c1}"]')).to_have_count(1)
    page.locator(".lf-details summary").click()
    resolved = page.locator(f'.lf-details .lf-thread[data-id="{c1}"]')
    resolved.click()
    expect(resolved).to_be_focused()
    expect(line).not_to_contain_text("resolve")
    page.keyboard.press("r")
    # The absence is read after a poll the test forces, so a resolve the press
    # had wrongly posted would have landed by now.
    comment("Third thought.")
    told(page)
    expect(page.locator(".lf-details summary")).to_have_text("Resolved (1)")
    expect(page.locator(f'.lf-threads > .lf-thread[data-id="{c2}"]')).to_have_count(1)
    assert errors == []
    page.close()


def test_escape_on_a_declaring_control_does_exactly_what_it_says(browser, serve):
    """One press is one action: the rung is the innermost scope in reach that binds
    Escape, and the dispatcher runs that one and no other. The draft editor's Esc used
    to be two — the edit cancelled and the runtime's ladder closed the panel behind it
    — and the cancel discarded the user's words against the never-lose-text norm. Each
    control kept that by hand once and the stack keeps it now, so this is the test that
    says the structure holds. The editor closes keeping the edit, the panel stands, and
    a grabbed card's Esc cancels the move and nothing else."""
    html = BOARD_PAGE.replace(
        "</main>", '<lf-draft id="plan"><pre>Ship it.</pre></lf-draft></main>'
    )
    url = serve(html)
    interact.append_event(
        serve.page_dir,
        {"kind": "comment", "author": "user", "version": 1, "text": "A thread."},
    )
    page, errors = open_page(browser, url)
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 1")
    page.keyboard.press("c")  # panel open, so the old second action would show
    expect(page.locator(".lf-panel")).to_be_visible()

    page.locator("lf-draft .lf-draft-pencil").click()
    ta = page.locator("lf-draft textarea")
    expect(ta).to_be_focused()
    ta.fill("Ship it — but louder.")
    page.keyboard.press("Escape")
    expect(ta).to_have_count(0)  # the editor closed…
    expect(page.locator(".lf-panel")).to_be_visible()  # …and only the editor
    # The edit was set aside, not discarded: reopening resumes it.
    page.locator("lf-draft .lf-draft-pencil").click()
    expect(page.locator("lf-draft textarea")).to_have_value("Ship it — but louder.")
    page.keyboard.press("Escape")

    # A grabbed card: Esc cancels the move, and the panel it would have closed stands.
    grip = page.locator("#card-heater .lf-grip")
    grip.focus()
    page.keyboard.press("Enter")
    expect(page.locator(".lf-keyline")).to_contain_text("cancel the move")
    # The contract's flip side: the chord refuses to arm over a control that has
    # claimed Escape, or one press would have two owners — the grip consuming it,
    # the chord promising its cancel.
    page.keyboard.press("g")
    expect(page.locator(".lf-keyline")).not_to_contain_text("comments")
    expect(page.locator(".lf-keyline")).to_contain_text("cancel the move")
    page.keyboard.press("Escape")
    # The grab is over (an uncancelled one would also leave the card in Todo),
    # the line is back to the resting grip, and the panel the ladder would have
    # closed stands.
    expect(page.locator(".lf-lift")).to_have_count(0)
    expect(page.locator(".lf-keyline")).to_contain_text("grab the card")
    expect(page.locator("#col-todo #card-heater")).to_have_count(1)
    expect(page.locator(".lf-panel")).to_be_visible()
    assert errors == []
    page.close()


def test_c_comments_on_what_the_reader_is_standing_in(browser, serve):
    """The keyboard reaches an element anchor. `c` read the 💬 alone, which only a
    selection or a click on a visual ever raises, so a reader working from the keys
    had two destinations where the pointer had three: a quote, or the whole page. An
    address put them on an option and the box that opened still said "Comment on the
    page" — the ⌥ aim's "the item under the pointer" with no twin for the cursor.

    Where they are standing is the open ask first, because that is what the page has
    already told them: markHere rings the whole ask, and `g a 1` addressed the
    question rather than the first of its options. Below an ask it is the innermost
    item, which is the aim's own reading — so the link the walk stands on speaks for
    the paragraph holding it, no id of its own being what an anchor needs.

    One box either way: `openOnItem` writes `{section: item.id}`, which is the anchor a
    widget's own conversation seat collects, so a remark made here lands in that seat's
    conversation rather than beside it. Reaching for the seat directly instead was five
    questions — escaping an author's id, whether the box can take focus, which box when
    the seat holds several, what design mode files, where the reader already stood — for
    a focus landing.

    The control is the same press from the same page with the reader standing nowhere
    in it: `c` still means the page. Without it a green here would follow just as well
    from a composer that opened on everything.

    Focus is dropped between the phases rather than backed out of, because each press
    lands the reader in a box: the typing scope owns the letter there, and the `g`
    opening the next address would be a character in the last one's draft."""
    page, errors = open_page(browser, serve(WHERE_I_STAND_PAGE))
    line = page.locator(".lf-keyline")
    drop = lambda: page.evaluate("() => document.activeElement?.blur()")

    # Standing nowhere in the page: the press means the page, as it always did.
    expect(line).to_contain_text("comment on the page")
    page.keyboard.press("c")
    expect(page.locator(".lf-general textarea")).to_be_focused()
    drop()

    # An ask, addressed: the composer opens on the question rather than on the option the
    # walk happens to stand the reader on, and rather than on the page.
    for key in "ga1":
        page.keyboard.press(key)
    expect(page.locator("#shape")).to_have_attribute("data-lf-ask", "1")
    expect(line).to_contain_text("comment on the options")
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-composer")).to_contain_text("options")
    drop()

    # A settled group: not an ask at all, and the conversation seat it still holds is
    # inside `hidden="until-found"`, so a press that reached into the seat focused a box
    # that cannot take focus and did nothing at all. Named by its own words rather than by
    # "options", which the composer standing open from the phase above already says — an
    # assertion true before the press is no assertion about the press.
    page.locator("#settled .lf-settled").focus()
    expect(line).to_contain_text("comment on the options")
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_contain_text("Decided last week")
    drop()

    # An ask with no seat: the composer, anchored on the ask rather than on the page.
    for key in "ga2":
        page.keyboard.press(key)
    expect(page.locator("#sug-window")).to_have_attribute("data-lf-ask", "1")
    expect(line).to_contain_text("comment on the rewrite")
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-composer")).to_contain_text("rewrite")
    drop()

    # A link inside a question, open and settled: the same markup, and the same answer.
    # Standing in an ask is not working one — a reader who addressed a link has named
    # something more particular than the question around it, and answering the question
    # there both overrode what they named and made the reply turn on whether that question
    # happened to be open. The settled one is the contrast that shows it was the openness
    # doing it: it always said "option", and the open one used to say "options".
    for expected_id, keys in (("sh-steel", "gl2"), ("st-keep", "gl3")):
        drop()
        for key in keys:
            page.keyboard.press(key)
        expect(line).to_contain_text("comment on the option")
        page.keyboard.press("c")
        expect(page.locator(".lf-composer")).to_be_visible()
        assert page.evaluate(
            "() => document.querySelector('.lf-composer blockquote')?.textContent ?? ''"
        ).startswith("§ option · "), "the box named the question, not the option"
        drop()

    # Below any ask, the innermost item: the paragraph the addressed link sits in.
    for key in "gl1":
        page.keyboard.press(key)
    expect(page.locator("#p1 a")).to_be_focused()
    expect(line).to_contain_text("comment on the paragraph")
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_contain_text("paragraph")

    assert errors == []
    page.close()


def test_c_in_a_thread_reaches_that_threads_own_box(browser, serve):
    """The panel's open list is the one part of the chrome that holds a conversation of
    its own, so a press meaning "say something about this" belongs to that box rather
    than to the page the panel stands over. `conversationBox` states the same rule from
    the other side when it declines to seat a widget standing inside a thread, and the
    asks a `g a` digit walks include the ones an agent sent — without this the same
    address answered one way on the page and another in the panel.

    A resolved thread is the case that has to be asked separately, and the reason this
    test exists at all: it is built by the same `threadNode` and wears the same class,
    under the Resolved disclosure, where it keeps a tab stop and a Reopen button. Reading
    the class alone put the reader in a thread whose reply box is not there, and the press
    died on the null with the page's own `c` never reached. Whether there is a box is what
    tells them apart — `standingConversation` asks for one rather than for the class — so
    the resolved thread falls through to the page, which is the honest answer for a thread
    with no box to offer."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    live = panel_comment(d, "Six weeks reads long.", {"section": "lede"})
    gone = panel_comment(d, "Settled already.", {"section": "how-cap"})
    interact.append_event(d, {"kind": "resolve", "author": "user", "parent": gone})

    page, errors = open_page(browser, url)
    line = page.locator(".lf-keyline")

    # The control: standing nowhere, the press still means the page.
    expect(line).to_contain_text("comment on the page")
    page.keyboard.press("c")
    expect(page.locator(".lf-general textarea")).to_be_focused()

    # Standing in the open thread, it means that thread's reply box.
    page.keyboard.press("Escape")
    page.keyboard.press("j")
    expect(page.locator(f'.lf-thread[data-id="{live}"]')).to_be_focused()
    expect(line).to_contain_text("comment on the thread")
    page.keyboard.press("c")
    expect(
        page.locator(f'.lf-thread[data-id="{live}"] > .lf-compose textarea')
    ).to_be_focused()
    page.evaluate("() => document.activeElement?.blur()")

    # A resolved thread has no box, so the press falls through to the page rather than
    # reaching for one that is not there.
    page.locator(".lf-details > summary").click()
    page.locator(f'.lf-details .lf-thread[data-id="{gone}"]').focus()
    expect(line).to_contain_text("comment on the page")
    page.keyboard.press("c")
    expect(page.locator(".lf-general textarea")).to_be_focused()

    assert errors == []
    page.close()


def test_c_in_a_seated_conversation_reaches_the_thread_it_is_in(browser, serve):
    """The page side of the same question. A widget that seats its own conversation
    (`x-conversation`) holds one thread per exchange, each with its own box, and the
    reader can stand in any of them — so "say something about this" means the box of the
    thread they are in, exactly as it does in the panel. One reading answers both, because
    a rule for the panel and a different one for the page is two answers to one question:
    read off the panel's class alone, the page side sent every thread on a seat to the
    oldest one's box.

    Two threads, and the reader in the second: with one there is no wrong answer to give,
    so the pair is what makes the assertion mean anything. The first phase is the control
    — standing on the widget rather than in a thread still opens the composer on the
    widget, so a green here is the standing being read and not every press landing in a
    conversation."""
    url = serve(
        leaf_page(
            "seated",
            """
<h1 id="t">Seated</h1>
<lf-options id="shape" choose>
  <lf-option id="sh-steel"><strong>Steel</strong> Galvanised, drop-in.</lf-option>
  <lf-option id="sh-cedar"><strong>Cedar</strong> Cheap; needs sealing.</lf-option>
</lf-options>
""",
        )
    )
    d = serve.page_dir
    said = []
    for text in ("First remark.", "Second remark."):
        interact.append_event(
            d,
            {
                "kind": "comment",
                "author": "user",
                "version": 1,
                "text": text,
                "anchor": {"section": "shape"},
            },
        )
        said.append(interact.read_events(d)[-1]["id"])

    page, errors = open_page(browser, url)
    line = page.locator(".lf-keyline")
    threads = page.locator(".lf-conversation-thread")
    expect(threads).to_have_count(2)

    # The control: standing on the widget, not in either thread.
    page.locator("#shape .lf-pick").first.focus()
    expect(line).to_contain_text("comment on the options")
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    page.keyboard.press("Escape")
    page.evaluate("() => document.activeElement?.blur()")

    # Standing in the second thread, the press means that thread's box.
    second = page.locator(f'.lf-conversation-thread[data-thread="{said[1]}"]')
    second.focus()
    expect(line).to_contain_text("comment on the thread")
    page.keyboard.press("c")
    expect(second.locator("> .lf-say textarea")).to_be_focused()

    assert errors == []
    page.close()


def test_c_travels_to_an_item_its_own_scroller_has_taken_away(browser, serve):
    """What the press asks is whether the item is in front of the reader, and only the
    page shows that. An item's own box is the box it would have — unclipped — so a card
    carried out of a board's sideways scroller still reports one inside the window, and a
    gate reading that called it visible and opened the box on something entirely off
    screen. `shownRect` is the reading the ⌥ aim's own paint takes, and this press is its
    keyboard twin: the two decide "in front of the reader" alike or they are not twins.

    The control is the same board with the scroller left alone, where the card is really
    in front of the reader and nothing moves — the pointer's answer on the same card. A
    test with only the scrolled case would pass just as well on a press that always
    travelled, which is the behaviour this replaced."""
    url = serve(
        leaf_page(
            "carried",
            """
<h1 id="t">Carried</h1>
<lf-board id="b">
"""
            + "\n".join(
                f'<lf-column id="col{i}" label="Column {i}">'
                f'<lf-card id="card{i}">Card {i} with a '
                f'<a href="https://example.invalid/{i}">link {i}</a> inside it.</lf-card>'
                "</lf-column>"
                for i in range(8)
            )
            + """
</lf-board>
""",
        )
    )
    seen = """() => {
      const r = document.querySelector('#card0').getBoundingClientRect();
      return {left: Math.round(r.left), onScreen: r.right > 0 && r.left < innerWidth};
    }"""

    # The control: nothing scrolled, so the card is in front of the reader and stays put.
    page, errors = open_page(browser, url)
    page.locator("#card0 a").focus()
    was = page.evaluate(seen)
    assert was["onScreen"], "the control needs the card visible to begin with"
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    assert page.evaluate(seen)["left"] == was["left"], (
        "the page moved under a reader who could already see the card"
    )
    page.close()

    # Carried out of its own scroller after the reader stood on it — focus first, because
    # focusing a card is itself a scroll and would undo the carrying it is meant to survive.
    page, errors = open_page(browser, url)
    page.locator("#card0 a").focus()
    page.evaluate(
        "() => { const b = document.querySelector('#b'); b.scrollLeft = b.scrollWidth; }"
    )
    assert not page.evaluate(seen)["onScreen"], (
        "the board did not carry the card off screen, so this proves nothing"
    )
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    assert page.evaluate(seen)["onScreen"], (
        "the box opened on a card the board had carried out of sight"
    )
    assert errors == []
    page.close()
