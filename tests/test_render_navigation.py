"""Comment marks, addresses, and keyboard navigation tests."""

import re

import pytest
from leaf import event_log as events_model
from playwright.sync_api import expect
from render_support import (
    ADDRESS_PAGE,
    ADDRESSED_PAGE,
    BOARD_PAGE,
    CHIPS,
    CLIPPED_BY,
    CONTROL_LABEL_PAGE,
    CROWDED_PAGE,
    DECISIONS_PAGE,
    DISCLOSED_PAGE,
    FOOTED_PAGE,
    GLYPH_OFFSETS,
    INLINE_PAGE,
    INSIDE_ITS_OPTION,
    NOTED_PAGE,
    OVER_WORDS,
    PANEL_PAGE,
    RENDERED,
    ROOT,
    SPENT,
    STANDS_BACK,
    TARGETS_PAGE,
    WHERE_I_STAND_PAGE,
    _publish,
    card_body,
    composer_quote,
    hold_selection,
    key_line,
    leaf_page,
    live_url,
    mark_point,
    open_page,
    painted,
    panel_comment,
    panel_settled,
    pending_text,
    post_event,
    refuse,
    resized,
    round_trip,
    select,
    stamp_version_file,
    standing_mark,
    told,
    wait_for_revision,
    wait_hovered,
    wait_standing,
    watched,
)

pytestmark = pytest.mark.nightly


def test_an_inline_tab_keeps_its_panel_inside_one_visible_boundary(browser, serve):
    """The strip says which workstream is open, while one enclosing surface says how
    far that workstream runs. Without the shared frame and inset, an inline tab starts
    like a section heading and finishes like ordinary page flow, so the reader has no
    visible answer to which headings and paragraphs belong to it."""
    page, errors = open_page(
        browser,
        serve(
            leaf_page(
                "bounded tabs",
                """
<h1 id="heading">Parallel work</h1>
<p id="shared">This context belongs to every workstream.</p>
<lf-tabs id="workstreams">
  <lf-tab id="implementation" label="Implementation">
    <section id="implementation-section">
      <h2 id="implementation-heading">Build the narrow path</h2>
      <p id="implementation-end">This closing line still belongs to Implementation.</p>
    </section>
  </lf-tab>
  <lf-tab id="research" label="Research">
    <section id="research-section">
      <h2 id="research-heading">Test the broad premise</h2>
      <p id="research-end">This closing line still belongs to Research.</p>
    </section>
  </lf-tab>
</lf-tabs>
<section id="next-section"><h2 id="next-heading">Whole-page conclusion</h2></section>
""",
            )
        ),
    )
    boundary = page.evaluate(
        """() => {
          const tabs = document.querySelector('#workstreams');
          const strip = tabs.querySelector('.lf-tabstrip');
          const panel = tabs.querySelector('lf-tab:not([hidden])');
          const selected = strip.querySelector('[aria-selected="true"]');
          const inactive = strip.querySelector('[aria-selected="false"]');
          const opening = panel.querySelector('h2');
          const closing = panel.querySelector('p:last-child');
          const next = document.querySelector('#next-section');
          const box = element => {
            const rect = element.getBoundingClientRect();
            return {left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom};
          };
          const style = element => getComputedStyle(element);
          return {
            tabs: box(tabs), strip: box(strip), panel: box(panel),
            opening: box(opening), closing: box(closing), next: box(next),
            frame: {
              top: parseFloat(style(tabs).borderTopWidth),
              right: parseFloat(style(tabs).borderRightWidth),
              bottom: parseFloat(style(tabs).borderBottomWidth),
              left: parseFloat(style(tabs).borderLeftWidth),
              color: style(tabs).borderTopColor,
              ground: style(tabs).backgroundColor,
            },
            stripGround: style(strip).backgroundColor,
            selectedGround: style(selected).backgroundColor,
            inactiveGround: style(inactive).backgroundColor,
          };
        }"""
    )

    frame_edges = tuple(
        boundary["frame"][edge] for edge in ("top", "right", "bottom", "left")
    )
    assert min(frame_edges) > 0, (
        f"the tab surface has an open edge: {boundary['frame']}"
    )
    assert boundary["frame"]["color"] != "rgba(0, 0, 0, 0)", boundary
    assert boundary["selectedGround"] == boundary["frame"]["ground"], boundary
    assert boundary["selectedGround"] != boundary["stripGround"], boundary
    assert boundary["inactiveGround"] != boundary["selectedGround"], boundary
    assert boundary["opening"]["top"] - boundary["strip"]["bottom"] >= 16, boundary
    assert boundary["opening"]["left"] - boundary["tabs"]["left"] >= 16, boundary
    assert boundary["tabs"]["right"] - boundary["opening"]["right"] >= 16, boundary
    assert boundary["tabs"]["bottom"] - boundary["closing"]["bottom"] >= 16, boundary
    assert boundary["next"]["top"] > boundary["tabs"]["bottom"], boundary
    assert errors == []
    page.close()


def test_keys_answer_a_question_from_its_marks(browser, serve):
    """From a mark — where `d` lands — ↑/↓ walk the options clamping at the ends, a
    digit picks outright, and each option wears its digit only while a mark holds
    keyboard focus, so nothing appears on a page nobody is answering."""
    page, errors = open_page(browser, serve(DECISIONS_PAGE))
    nums = page.locator("#live-question .lf-address")
    expect(nums.first).to_be_hidden()

    page.keyboard.press("d")
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
    acts = [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "action"
    ]
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
    digit is level with its words, was checked by nothing.

    How far in it stands is the whole group's, and it is asked as the relation it is: the
    gutter reads status rule, digit, then prose, so the digit is measured against those two
    neighbours and against the other form's seat. Pinned as the number the gutter came to,
    the reading broke the day a status rule took the head of the column and the digit moved
    along behind it — a move the page wanted, reported as a failure of the digit."""
    page, errors = open_page(browser, serve(ADDRESS_PAGE))
    seats = {}
    for options, sitting in [
        (["c-heater", "c-cable", "c-hand"], "in the corner"),
        (["r-now", "r-later"], "centred"),
    ]:
        page.keyboard.press("d")
        for id_ in options:
            chip = page.locator(f"#{id_} > .lf-address")
            expect(chip).to_be_visible()
            cut = chip.evaluate(CLIPPED_BY)
            assert cut is None, f"{id_}'s digit is cut: {cut}"
            # Never on the hairline the outer corner would have shared with the cells
            # around it, and never in either neighbour's room: the option's gutter opens
            # with the status rule, and its words open at the column the option pads to.
            # Read the row form here as well as the cards above; both reserve status,
            # address, then prose in the same leading gutter.
            sits = chip.evaluate(INSIDE_ITS_OPTION)
            assert sits["afterStatus"] < sits["x"] < sits["ends"] < sits["opens"], (
                f"{id_}'s digit runs {sits['x']}…{sits['ends']} in a gutter whose status "
                f"rule ends at {sits['afterStatus']} and whose words open at "
                f"{sits['opens']}, so the gutter is holding one of the three in another's "
                "room"
            )
            seats.setdefault(round(sits["x"], 1), []).append(id_)
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
    # One column, in both forms: a card's cell and a row's are the two shapes whose room
    # differed, and a seat each would read as a straight rail down neither.
    assert len(seats) == 1, f"the digits stand at more than one column: {seats}"
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
            "revision": 1,
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
        data={"kind": "comment", "revision": 1, "text": "and another"},
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
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    first_id, second_id = (comment["id"] for comment in comments)
    page, errors = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
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


def test_the_page_marks_the_comment_the_reader_is_standing_in(browser, serve):
    """A reader sent from a comment to its passage lands among every other mark on the
    page, all of them painted alike, and the panel is the only surface saying which one
    they asked for. The page says it too: the thread holding the focus paints its own
    passage apart from the rest for as long as the reader remains in that thread.

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
            data={"kind": "comment", "revision": 1, "text": text, "anchor": anchor},
        )
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) >= 2")
    page.locator("#fig.lf-mark-el").wait_for()

    assert standing_mark(page) == {
        "text": "",
        "elements": [],
    }, "a page nobody has opened a comment on is already saying the reader is in one"

    page.keyboard.press("t")
    wait_standing(page, "bold text")

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

    page.keyboard.press("t")
    wait_standing(page, "neighbouring block")

    # A passage with no words to paint says the same thing with the outline it already
    # wears, so the two kinds of anchor answer one question and not two.
    page.keyboard.press("t")
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
    page.locator(".lf-threads-toggle").click()
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
        const rules = [...document.styleSheets].flatMap(s => {
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
        return events_model.append_event(
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
    page.keyboard.press("t")
    expect(page.locator(f'.lf-thread[data-id="{c2}"]')).to_be_focused()

    # Once the first thread resolves, the same control enters the next one.
    events_model.append_event(d, {"kind": "resolve", "author": "user", "parent": c1})
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
    c4 = [e for e in events_model.read_events(d) if e.get("kind") == "comment"][-1][
        "id"
    ]

    # A resolved thread takes its line with it: the pass owns what it wrote.
    events_model.append_event(d, {"kind": "resolve", "author": "user", "parent": c4})
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
    — it carries the whole address now, leader and letter and digit. Two addressable things
    can start within that width: markers
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
    # And the page was crowded, or a clean sweep says nothing. Five members start within a
    # chip's width of each other here — three footnote markers, the link that is the whole
    # of a summary, and the summary itself — so all five surviving would mean the chips had
    # stopped colliding rather than that this pass had taken the collisions down. Two is
    # the fewest a pair can be checked between. The window between those two numbers is
    # what a chip growing or shrinking moves, which is the change that empties this test.
    drawn = piles["drawn"]
    assert 2 <= len(drawn) < 5, (
        f"the crowded page drew {len(drawn)} of its five addresses ({drawn}): the pass "
        f"either dropped nothing or left too few to have checked a pair"
    )
    # And the ones that survived still say what they reach: pressing the first link's own
    # digit lands on that link and not on the neighbour whose chip it might have worn.
    first = piles["drawn"][0]
    _leader, letter, digit = first.split(" ")
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
        f"""async () => {{
             const line = () => document.querySelector('.lf-keyline').getBoundingClientRect();
             const hit = (a, b) => a.left < b.right && b.left < a.right
                                && a.top < b.bottom && b.top < a.bottom;
             const out = [];
             const room = document.scrollingElement.scrollHeight - document.scrollingElement.clientHeight;
             for (let i = 0; i <= 20; i++) {{
               document.scrollingElement.scrollTo(0, Math.round((room * i) / 20));
               await ({RENDERED})();
               const bar = line();
               for (const chip of document.querySelectorAll('.lf-addresses > .lf-address'))
                 if (hit(chip.getBoundingClientRect(), bar))
                   out.push(chip.textContent + ' at ' + Math.round(document.scrollingElement.scrollTop));
             }}
             return out;
           }}"""
    )
    assert fouled == [], (
        f"addresses are drawn over the key line that explains them: {fouled}"
    )
    assert errors == []
    page.close()


def test_the_g_chord_reaches_panels_and_document_lists(browser, serve):
    """A mnemonic completes one-off panel travel; a digit refines a document list.

    Threads and decisions already have repeatable category walks, so their g chords land in
    the panels that hold those categories. Hyperlinks and folds have no such walk;
    their mnemonic opens the numbered address stage instead."""
    url = serve(ADDRESSED_PAGE)
    d = serve.page_dir

    def comment(anchor, text):
        return events_model.append_event(
            d,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": text,
                "anchor": anchor,
            },
        )["id"]

    c1 = comment({"quote": "passage under discussion"}, "Sharpen this.")
    comment({"quote": "two separate remarks"}, "Second thought.")
    c3 = comment({"section": "p2"}, "The short one too.")
    page, errors = open_page(browser, url)
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 3")
    line = page.locator(".lf-keyline")

    # The page's own key is the letter alone: what it opens is a table, and a range on the
    # line here could only ever have counted one of the lists in it.
    expect(line).to_contain_text("go to")
    expect(line).not_to_contain_text("1–3")

    # Wide enough that the panel will stand beside the page rather than over it, which is
    # where a box in the fixed chrome and the page's flow part company: body is narrowed
    # as the layout shell, the panel is fixed and is not inside it, and a chip placed by
    # walking the page's clips came back with the whole reply box clipped away.
    resized(page, 1280, 800)

    # Armed, the line names the available panels and document lists. Only list members
    # wear numeric chips; a panel is one complete destination.
    page.keyboard.press("g")
    expect(line).to_contain_text("t")
    expect(line).to_contain_text("Threads panel")
    expect(line).to_contain_text("d")
    expect(line).to_contain_text("Decisions panel")
    expect(line).to_contain_text("h 1–2")
    expect(line).to_contain_text("hyperlinks")
    expect(line).to_contain_text("f 1")
    expect(line).to_contain_text("folds")
    expect(page.locator(CHIPS)).to_have_text(["g h 1", "g h 2", "g f 1"])
    # Whole, and saying how much of it is still to press: the leader is behind the reader
    # here, so it stands back on the chip's own paper and the two keys that finish the
    # motion are lit on a ground of their own. A chip set evenly would state an address and
    # leave the reader to work out for themselves which part of it they had already made —
    # and one that said it in type sizes would hold two of them in one box, and re-set every
    # chip on screen the moment the next press moved a key across.
    assert page.evaluate(SPENT, CHIPS) == ["g", "g", "g"]
    assert page.evaluate(STANDS_BACK, CHIPS) == {
        "quieter": True,
        "lit": True,
        "flat": True,
        "sized": True,
    }, (
        "the keys already pressed do not stand back from the ones still to come: "
        f"{page.evaluate(STANDS_BACK, CHIPS)}"
    )
    # The chips are the eye's copy of a mode; a reader who cannot see them is told the
    # window opened and what it holds, off the same rows the line just drew — the ranges
    # among them, where a row whose label counts the page used to be read out key by key
    # while an option group's, written as a string, was spelled "1–3".
    expect(page.locator(".lf-live")).to_contain_text("t Threads panel")

    # A panel mnemonic completes the chord and leaves the reader inside that panel, where
    # its own scoped keys are immediately available.
    expect(page.locator(".lf-panel")).not_to_be_visible()
    page.keyboard.press("t")
    expect(page.locator(".lf-panel")).to_be_visible()
    expect(page.locator(".lf-threads")).to_be_focused()
    expect(page.locator(CHIPS)).to_have_count(0)
    expect(page.locator(f'.lf-thread[data-id="{c1}"] textarea')).to_have_attribute(
        "placeholder", "Reply"
    )
    page.keyboard.press("Escape")
    expect(page.locator(".lf-panel")).not_to_be_visible()

    # The Decisions chord follows the same contract: show the panel and land on its first row.
    page.keyboard.press("g")
    page.keyboard.press("d")
    expect(page.locator(".lf-decisions-panel")).to_be_visible()
    expect(page.locator(".lf-decisions-row").first).to_be_focused()
    expect(page.locator(CHIPS)).to_have_count(0)
    page.keyboard.press("Escape")
    expect(page.locator(".lf-decisions-panel")).not_to_be_visible()

    # The hyperlinks, from the head of the page where both are on screen. A chip is hung on the
    # corner a member starts at, which for an inline that wraps is the corner of its first
    # line and not of its bounding box — those run the width of the column, so a digit
    # placed there sits a line above the words it addresses, over somebody else's sentence.
    page.evaluate("() => document.scrollingElement.scrollTo(0, 0)")
    page.keyboard.press("g")
    page.keyboard.press("h")
    expect(page.locator(CHIPS)).to_have_text(["g h 1", "g h 2"])
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
    # Two rungs down, because two presses built this window: the letter, then the
    # window itself. test_escape_gives_the_chord_back_one_press_at_a_time owns that.
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")

    # And from the foot of the page, where neither of them can be seen.
    # A list is the document's and not the window's, so an address means the same link at
    # every scroll position and holds where no chip can be drawn for it — counted what is
    # in the window, `g h 2` would name a different link each time the reader moved, and
    # the line would go stale about which digits are live every time the page scrolled.
    # The arrival is the focus, and the press that finishes the motion is the platform's:
    # named on the line, or the reader lands with nothing said.
    page.evaluate(
        "() => document.scrollingElement.scrollTo(0, document.scrollingElement.scrollHeight)"
    )
    page.keyboard.press("g")
    expect(line).to_contain_text("h 1–2")
    page.keyboard.press("h")
    expect(page.locator(CHIPS)).to_have_count(0)
    page.keyboard.press("2")
    expect(page.locator("#lk2")).to_be_focused()
    expect(line).to_contain_text("follow")

    # The panel folds its resolved comments into a <details> of its own, and that box is
    # the chrome's. A list is what the document holds, so it is not addressed: read of the
    # document at large, `f` would offer a digit for a fold the author never wrote
    # and the reader never sees on the page.
    events_model.append_event(d, {"kind": "resolve", "author": "user", "parent": c3})
    told(page)
    expect(page.locator("details.lf-details")).to_have_count(1)
    page.keyboard.press("g")
    expect(line).to_contain_text("f 1")
    expect(line).not_to_contain_text("f 1–2")
    page.keyboard.press("Escape")

    # The folds, and the one arrival that changes the page it arrives at. Every
    # other member is reached through a reveal that opens the collapsed boxes on the way;
    # here the box is the member, so that same reveal is the whole motion, and the reader
    # who wanted a section open has it open having asked once.
    page.evaluate("() => document.scrollingElement.scrollTo(0, 0)")
    page.keyboard.press("g")
    page.keyboard.press("f")
    expect(page.locator(CHIPS)).to_have_text(["g f 1"])
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

    # Standing there, the line says which way the next press goes and names every key that
    # goes that way: Space as well as Enter, where a link takes Enter alone and Space under
    # one is the page's own scroll, and the one arrow with somewhere to go. Both cells are
    # read where they are painted — a word fixed at declaration could say only one of the
    # two directions, and a binding set fixed there would name an arrow that does nothing.
    # What the arrows do is the test below this one; here they are what the line offers.
    opened, shut = r"⏎ / space / ←", r"⏎ / space / →"
    expect(line).to_contain_text(re.compile(opened + r"\s*close"))
    page.keyboard.press("Enter")
    expect(page.locator("#dsc")).not_to_have_attribute("open", "")
    # Read once rather than waited for. Opening a disclosure is the one change in what the
    # next press does that no writer in the runtime reports, so the word stood at "close"
    # until a poll came past — and an assertion that retries reads a stale line as an
    # eventually right one, going green on whichever poll happens to land inside its
    # budget. The attribute watch has answered by the time the press returns or nothing
    # has.
    said = key_line(page)
    assert re.search(shut + r"\s*open", said), said
    page.keyboard.press(" ")
    expect(page.locator("#dsc")).to_have_attribute("open", "")
    said = key_line(page)
    assert re.search(opened + r"\s*close", said), said

    # The two completions that take no digit: an edge of the page is one place, so the
    # second key is the whole address — G glides to the bottom, g to the top.
    foot = page.evaluate(
        "() => document.scrollingElement.scrollHeight - document.scrollingElement.clientHeight"
    )
    assert foot > 0, "the page must scroll for an edge to be a move at all"
    page.keyboard.press("g")
    expect(line).to_contain_text("top / bottom")
    # Shift spelled out: a bare press("G") synthesizes key "G" with no shift modifier,
    # which a real keyboard cannot do, and the dispatcher rightly reads it as g.
    page.keyboard.press("Shift+G")
    page.wait_for_function(
        "foot => Math.abs(document.scrollingElement.scrollTop - foot) < 1", arg=foot
    )
    page.keyboard.press("g")
    page.keyboard.press("g")
    page.wait_for_function("() => document.scrollingElement.scrollTop === 0")

    # A panel mnemonic completes the chord directly wherever the reader is on the page.
    page.keyboard.press("g")
    page.keyboard.press("t")
    expect(page.locator(".lf-threads")).to_be_focused()

    # Typing contexts are untouched: in a box, the whole chord is text.
    page.keyboard.press("t")
    page.keyboard.press("Enter")
    ta1 = page.locator(f'.lf-thread[data-id="{c1}"] textarea')
    expect(ta1).to_be_focused()
    page.keyboard.type("gc1")
    expect(ta1).to_have_value("gc1")
    expect(ta1).to_be_focused()
    assert errors == []
    page.close()


def test_the_g_chord_reaches_the_all_leaves_panel(browser, serve, live_leaf):
    """All leaves is the third panel destination and follows the same focus contract."""
    live_leaf("second", "A second leaf")
    page, errors = open_page(browser, serve(ADDRESSED_PAGE))

    page.keyboard.press("g")
    expect(page.locator(".lf-keyline")).to_contain_text("All leaves panel")
    page.keyboard.press("l")

    expect(page.locator(".lf-others-panel")).to_be_visible()
    expect(page.locator("a.lf-others-row").first).to_be_focused()
    expect(page.locator(CHIPS)).to_have_count(0)
    assert errors == []
    page.close()


def test_a_g_panel_destination_survives_an_empty_open_decisions_tray(browser, serve):
    """An open panel remains reachable after working its last row removes that row."""
    page, errors = open_page(
        browser,
        serve(
            leaf_page(
                "One decision",
                '<h1>One decision</h1><lf-decision id="only-decision"><h2>Pick one</h2>'
                '<lf-options id="only" choose>'
                '<lf-option id="first">First</lf-option>'
                '<lf-option id="second">Second</lf-option></lf-options></lf-decision>',
            )
        ),
    )

    page.keyboard.press("g")
    page.keyboard.press("d")
    expect(page.locator("button.lf-decisions-row")).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator("#only .lf-pick").first).to_be_focused()
    page.keyboard.press("1")
    round_trip(page)
    expect(page.locator("button.lf-decisions-row")).to_have_count(0)
    expect(page.locator(".lf-decisions-panel")).to_have_class(re.compile(r"\bopen\b"))

    page.keyboard.press("g")
    expect(page.locator(".lf-keyline")).to_contain_text("Decisions panel")
    page.keyboard.press("d")
    expect(page.locator(".lf-decisions-panel")).to_be_focused()
    expect(page.locator(".lf-keyline")).not_to_contain_text("walk the decisions")
    assert (
        page.locator(".lf-decisions-panel").get_attribute("aria-keyshortcuts") is None
    )
    assert errors == []
    page.close()


def test_the_press_that_lights_a_key_moves_no_glyph(browser, serve):
    """A chip holds still while the chord advances through it — the box and every glyph in
    it.

    This is the whole claim of the split. A chip carries the address it does because the
    reader is meant to read it once and press it, and the old chip broke that by saying how
    far in they were with type size: the key crossing from the live half to the spent one
    shrank, so every chip on screen re-laid-out under the eye at the moment it was being
    read. The ground that replaced it is a fixed-width channel and was supposed to end that.

    It did not, quite, and the first version of this fix shipped the same fault one glyph
    smaller. The lit block took its padding as advance, so the crossing key stepped by that
    padding — 3px, against the 1.2px slide being fixed — while the chip's width, its left
    edge, the leader and the digit all held perfectly still. Every reading the suite had
    said the chip was fine, because every one of them was of the box.

    So the reading here is of the glyphs, through a Range: the spans are the thing that
    moves, and an element rect answers about a different element at each stage. The negative
    margin on .lf-lit is what this covers — remove it and the letter steps."""
    url = serve(ADDRESSED_PAGE)
    page, errors = open_page(browser, url)
    resized(page, 1280, 800)

    # The hyperlink list, whose letter narrows the offer without revealing anything, so the chip
    # under measurement is the same chip before and after and is drawn from the same box.
    # Its chip leads the layer, the table's order being the order they are painted in.
    page.keyboard.press("g")
    expect(page.locator(CHIPS)).to_have_text(["g h 1", "g h 2", "g f 1"])
    before = page.evaluate(GLYPH_OFFSETS, CHIPS)

    # The letter the chip itself names. What says the repaint has landed is the count and
    # not the text: this chip reads "g h 1" at both stages, so an assertion on what it says
    # is satisfied by the frame before the press as readily as the one after it, and the
    # measurement below then compares a reading with itself. It passed that way two runs in
    # three with the fix reverted. The narrowing is the fact the press actually writes —
    # every other list's chips go — and the paint is coalesced into one frame with it.
    page.keyboard.press("h")
    expect(page.locator(CHIPS)).to_have_text(["g h 1", "g h 2"])
    after = page.evaluate(GLYPH_OFFSETS, CHIPS)

    assert before and after, "the chord painted no chip to measure"
    # Half a pixel of tolerance, which is subpixel rounding rather than a step: the halves
    # are separate inline boxes, so a glyph's edge can land either side of a device pixel
    # depending on which of them carries it. The fault this covers was three pixels, and
    # paying the lit block's padding in advance is the smallest way to bring it back.
    assert before["glyphs"].keys() == after["glyphs"].keys(), (
        "the chip's keys changed with the press: "
        f"{sorted(before['glyphs'])} -> {sorted(after['glyphs'])}"
    )
    moved = {
        k: (v, after["glyphs"][k])
        for k, v in before["glyphs"].items()
        if abs(v - after["glyphs"][k]) > 0.5
    }
    assert not moved, "a key moved when the press lit it: " + ", ".join(
        f"{k!r} {a} -> {b}" for k, (a, b) in moved.items()
    )
    # And the box the glyphs sit in, which is the reading that passed while they moved.
    assert abs(before["width"] - after["width"]) <= 0.5, (
        f"the chip resized: {before['width']} -> {after['width']}"
    )
    assert abs(before["left"] - after["left"]) <= 0.5, (
        f"the chip slid: {before['left']} -> {after['left']}"
    )
    assert errors == []
    page.close()


def test_only_controls_and_boxes_with_something_out_of_sight_take_a_tab_stop(
    browser, serve
):
    """Anything a mouse can scroll a keyboard has to reach, and the reference is a list
    long enough to scroll — but its rows carry no control, so nothing put the reader in it
    and they could read the first screenful of the key reference and no more.

    The sweep that fixes that asks the box whether it may scroll, and the theme says every
    table may (`table { display: block; overflow-x: auto }`). So pointing it at the
    reference tagged all fourteen of its tables, none of which overflows: leaving the
    reference by Tab went from its native controls to fifteen extra stops, each wearing
    the browser's own ring rather than the layer's. A rule saying a box *could* scroll is
    not the same fact as a box that *has* something out of sight, and only the second is
    somewhere a reader needs to be able to stand.

    Asserted as the whole set rather than a count, because the count was right before and
    the members were wrong: every stop in the overlay has to be a control the reference
    offers or a box that really scrolls."""
    page, errors = open_page(browser, serve(CONTROL_LABEL_PAGE))
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.locator(".lf-help")).to_be_visible()

    stops = page.evaluate(
        """() => [...document.querySelector('.lf-help').querySelectorAll('*')]
                 .filter(e => e.tabIndex >= 0)
                 .map(e => ({
                    tag: e.tagName,
                    scrolls: e.scrollWidth > e.clientWidth
                          || e.scrollHeight > e.clientHeight,
                 }))"""
    )
    assert stops, "the reference offers no tab stop at all, not even its search box"
    controls = {"BUTTON", "INPUT"}
    dead = [s for s in stops if s["tag"] not in controls and not s["scrolls"]]
    assert dead == [], f"tab stops on boxes with nothing out of sight: {dead}"
    assert [s["tag"] for s in stops if s["tag"] in controls] == [
        "BUTTON",
        "INPUT",
        "BUTTON",
        "BUTTON",
    ]

    # And the box that does have something out of sight is one of those stops, which is
    # the whole point of the sweep. Its reachability is what is asserted here and not the
    # scroll itself: the headless shell does not move a focused div for an arrow or a
    # PageDown where Chrome does, so a motion assertion would be measuring the harness.
    # What this can say, and what the defect was, is that the box overflows and that a
    # reader can be put on it.
    results = page.locator(".lf-help-results")
    assert page.evaluate(
        "() => { const r = document.querySelector('.lf-help-results');"
        "        return r.scrollHeight > r.clientHeight; }"
    ), (
        "this reference fits its box, so it proves nothing about reaching one that does not"
    )
    results.focus()
    expect(results).to_be_focused()
    page.keyboard.press("Escape")
    assert errors == []
    page.close()


def test_the_reference_keeps_its_complete_keyboard_layer(browser, serve):
    """The reference has a visible close control and keeps Tab inside the surface.

    It claims the keyboard while open, so letting native Tab fall through to the page
    behind it makes the visible scope and the focus scope disagree. Forward and reverse
    Tab use the same registered walk, while Escape closes and restores the opener."""
    page, errors = open_page(browser, serve(CONTROL_LABEL_PAGE))
    opener = page.get_by_role("button", name="? more", exact=True)
    opener.click()
    opener = page.get_by_role("button", name="? all shortcuts", exact=True)
    opener.click()
    help_el = page.locator(".lf-help")
    close = page.get_by_role("button", name="Back to more shortcuts")
    expect(close).to_be_visible()

    seen = set()
    for _ in range(6):
        page.keyboard.press("Tab")
        active = page.evaluate(
            """() => {
              const e = document.activeElement;
              return {inside: document.querySelector('.lf-help').contains(e),
                      name: e.getAttribute('aria-label') || e.className || e.tagName};
            }"""
        )
        assert active["inside"], f"Tab left the keyboard reference for {active['name']}"
        seen.add(active["name"])
    assert "Back to more shortcuts" in seen, seen

    page.keyboard.press("Shift+Tab")
    assert page.evaluate(
        "() => document.querySelector('.lf-help').contains(document.activeElement)"
    )
    page.keyboard.press("Escape")
    expect(help_el).to_be_hidden()
    expect(opener).to_be_focused()

    # The native modal makes the page behind it inert. Its reachable light-dismiss gesture
    # is the backdrop, which closes the reference and returns to the door rather than
    # pretending a page control can be pressed through the modal layer.
    opener.click()
    page.mouse.click(2, 2)
    expect(help_el).to_be_hidden()
    expect(opener).to_be_focused()
    assert errors == []
    page.close()


def test_the_reference_runs_available_commands_and_explains_the_rest(browser, serve):
    """The reference is the command register made usable, not a second list of prose.

    Search narrows that register, arrows choose a result, and Enter runs it through the
    same scoped command route as its key. A command outside the reader's current scope
    stays selectable, but explains the scope it needs instead of closing and doing
    nothing. Stable command IDs are exposed on the results so words can change without
    breaking this route or tooling built on it."""
    page, errors = open_page(browser, serve(NOTED_PAGE, comments=2))
    help_el = page.locator(".lf-help")
    search = page.get_by_role("combobox", name="Search keyboard shortcuts")

    page.keyboard.press("?")
    page.keyboard.press("?")
    search.fill("resolve it")
    result = help_el.locator(
        '.lf-help-command[data-lf-command="thread.resolution.toggle"]'
    )
    expect(result).to_have_count(1)
    expect(result).to_have_attribute("data-lf-command", "thread.resolution.toggle")
    expect(search).to_have_attribute("aria-haspopup", "grid")
    page.keyboard.press("ArrowDown")
    expect(search).to_be_focused()
    expect(result).to_have_attribute("data-lf-selected", "true")
    expect(result.locator("xpath=ancestor::tr")).to_have_attribute(
        "aria-selected", "true"
    )
    page.keyboard.type("!")
    expect(search).to_have_value("resolve it!")
    expect(help_el.locator(".lf-help-empty")).to_be_visible()
    page.keyboard.press("Backspace")
    page.keyboard.press("ArrowDown")
    expect(result).to_have_attribute("data-lf-selected", "true")
    page.keyboard.press("Enter")
    expect(help_el).to_be_visible()
    expect(help_el.locator(".lf-help-meta")).to_have_text(
        "Available on a focused thread"
    )
    search.fill("put the reaction down")
    cancel_reaction = help_el.locator(
        '.lf-help-command[data-lf-command="reaction.cancel"]'
    )
    page.keyboard.press("ArrowDown")
    expect(search).to_be_focused()
    expect(cancel_reaction).to_have_attribute("data-lf-selected", "true")
    page.keyboard.press("Enter")
    expect(help_el.locator(".lf-help-meta")).to_have_text("Available with r armed")

    page.keyboard.press("Escape")
    page.keyboard.press("?")
    search.fill("previous open thread")
    previous = help_el.locator('.lf-help-command[data-lf-command="thread.previous"]')
    expect(previous).to_have_count(1)
    page.keyboard.press("ArrowDown")
    expect(search).to_be_focused()
    expect(previous).to_have_attribute("data-lf-selected", "true")
    page.keyboard.press("Enter")
    thread = page.locator(".lf-thread").last
    expect(thread).to_be_focused()
    page.keyboard.press("?")
    page.keyboard.press("?")
    search.fill("resolve it")
    page.keyboard.press("ArrowDown")
    expect(search).to_be_focused()
    expect(result).to_have_attribute("data-lf-selected", "true")
    page.keyboard.press("Enter")
    expect(help_el).to_be_hidden()
    expect(page.locator(".lf-details summary")).to_have_text("Resolved (1)")
    assert errors == []
    page.close()


def test_registered_shortcuts_are_exposed_to_assistive_technology(browser, serve):
    """The same declarations that paint help expose their active keys through ARIA."""
    page, errors = open_page(browser, serve(DECISIONS_PAGE))

    expect(page.get_by_role("button", name="? more", exact=True)).to_have_attribute(
        "aria-keyshortcuts", "?"
    )
    expect(page.locator(".lf-general textarea")).to_have_attribute(
        "aria-keyshortcuts", "Meta+Enter Control+Enter"
    )
    assert page.locator(".lf-version-menu").get_attribute("aria-keyshortcuts") is None

    page.keyboard.press("d")
    mark = page.locator("#live-question .lf-pick").first
    shortcuts = mark.get_attribute("aria-keyshortcuts").split()
    assert {"1", "2", "Enter", "ArrowUp", "ArrowDown", "Space"} <= set(shortcuts), (
        shortcuts
    )

    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(
        page.locator(
            ".lf-help tr", has_text="Next decision this page is waiting on you for"
        ).locator("kbd")
    ).to_have_text("d")
    expect(
        page.locator(
            ".lf-help tr", has_text="Previous decision this page is waiting on you for"
        ).locator("kbd")
    ).to_have_text("D")
    page.keyboard.press("Escape")

    assert page.locator(".lf-decisions").get_attribute("aria-keyshortcuts") is None
    page.locator(".lf-decisions").click()
    expect(page.locator(".lf-decisions-panel")).to_have_attribute(
        "aria-keyshortcuts", "ArrowUp ArrowDown"
    )
    expect(page.locator(".lf-decisions-row").first).to_have_attribute(
        "aria-keyshortcuts", "Enter Space"
    )
    page.keyboard.press("Escape")

    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.get_by_role("button", name="Back to more shortcuts")).to_have_attribute(
        "aria-keyshortcuts", "Escape"
    )
    page.keyboard.press("Escape")
    assert errors == []
    page.close()


def test_the_reference_reads_the_same_way_twice(browser, serve):
    """A widget registers its scope at upgrade, and the set the reference walks is
    insertion-ordered, so the sections came out in whatever order the modules happened to
    finish in. The same build read twice put "On a tab" above "On a card grip" once and
    below it the next time. A reference whose headings move between loads is one a reader
    cannot learn the shape of, and any assertion on it flakes rather than fails — which is
    how it was found, a reviewer taking a reordering for fallout from an unrelated change.

    So the widgets' sections read in the order the page holds them. Asserted twice over:
    the same page loaded twice gives the same list, and that list is the document's own
    order rather than any order at all — a stable-but-wrong order would pass the first
    check alone."""
    url = serve(CONTROL_LABEL_PAGE)
    seen = []
    for _ in range(2):
        page, errors = open_page(browser, url)
        page.keyboard.press("?")
        page.keyboard.press("?")
        expect(page.locator(".lf-help")).to_be_visible()
        seen.append(
            page.evaluate(
                "() => [...document.querySelectorAll('.lf-help h3')].map(h => h.textContent)"
            )
        )
        assert errors == []
        page.close()

    assert seen[0] == seen[1], f"the reference reordered between loads: {seen}"
    assert "On a tab" in seen[0], seen[0]


def test_a_widget_that_renames_its_role_keeps_the_press_offer_gave_it(browser, serve):
    """What makes a press is `offer`'s own answer, and nothing that can be overwritten on
    the way past. A tab is built by `offer("button", …)` and then wears `role="tab"`,
    because that is what its strip is; its own scope declares the arrows and Home/End and
    says nothing about Enter or Space, so the control scope is the only thing that gives a
    tab a press at all — and the only thing that consumes Space, which is the page's
    scroll.

    Read off the role, that scope stopped seeing tabs: Enter did nothing and Space threw
    the reader down the page from a control that looked like it had answered. Read off the
    tabindex, which is the reading before it, the same scope claimed every focus target
    `offer` builds, and led with "press it" over a conversation thread that answers
    nothing. So the marker is the one `offer` writes for this and a widget has no reason
    to touch.

    Asserted from the state where the press is the only way back: the tab strip is walked
    with arrows, so a focused tab is usually the selected one. Revealing the *other* panel
    leaves focus on a tab that is not selected, which is exactly when Enter has work to
    do."""
    page, errors = open_page(browser, serve(CONTROL_LABEL_PAGE))
    tabs = page.locator("#projects .lf-tab-btn")
    expect(tabs).to_have_count(2)

    tabs.first.focus()
    # Reveal the second panel without moving focus, so the focused tab is not the selected
    # one and Enter has something to do.
    page.evaluate(
        """() => document.querySelector('#tab-bath')
                 .dispatchEvent(new CustomEvent('lf-reveal',
                   {bubbles: true, detail: {target: document.querySelector('#tab-bath')}}))"""
    )
    expect(tabs.first).to_be_focused()
    expect(tabs.nth(1)).to_have_attribute("aria-selected", "true")

    # The line names the press, and the press re-selects the tab the reader is standing on.
    expect(page.locator(".lf-keyline")).to_contain_text("press it")
    page.keyboard.press("Enter")
    expect(tabs.first).to_have_attribute("aria-selected", "true")

    # And Space is consumed rather than scrolling the page out from under the press.
    page.evaluate("() => document.querySelector('#tab-bath').click()")
    tabs.first.focus()
    before = page.evaluate("() => document.scrollingElement.scrollTop")
    page.keyboard.press(" ")
    expect(tabs.first).to_have_attribute("aria-selected", "true")
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before, (
        "Space scrolled the page instead of working the control it was promised on"
    )
    assert errors == []
    page.close()


def test_an_address_reaches_every_member_of_a_long_list(browser, serve):
    """A list keeps every member addressable after its count passes nine.

    A digit that is both a complete address and the start of a longer one leaves the
    choice open: Enter takes the exact address, another digit takes the longer one, and
    Escape removes one entered digit. The page's chips and key line make that temporary
    ambiguity visible, so the extra reach does not turn short addresses into a timeout or
    an implicit guess."""
    # One row per member keeps this test about decimal addressing. The crowded-address
    # test above deliberately leaves collision survival to the platform's font metrics.
    links = "".join(
        f'<li><a id="link-{n}" href="#link-{n}">link {n}</a></li>' for n in range(1, 13)
    )
    lead = "".join(f"<p>Context before the links, line {n}.</p>" for n in range(16))
    tail = "".join(f"<p>Context after the links, line {n}.</p>" for n in range(16))
    page, errors = open_page(
        browser, serve(leaf_page("Twelve links", f"{lead}<ol>{links}</ol>{tail}"))
    )
    page.emulate_media(reduced_motion="reduce")
    line = page.locator(".lf-keyline")
    page.locator("#link-1").scroll_into_view_if_needed()
    page.evaluate(
        """() => {
          const link = document.querySelector('#link-1').getBoundingClientRect();
          const banner = document.querySelector('.lf-banner').getBoundingClientRect();
          document.scrollingElement.scrollBy(0, link.top - banner.bottom - 96);
        }"""
    )

    page.keyboard.press("g")
    expect(line).to_contain_text("h 1–12")
    page.keyboard.press("h")
    expect(page.locator(CHIPS).first).to_have_text("g h 1 ⏎")
    before = page.evaluate(GLYPH_OFFSETS, CHIPS)
    page.keyboard.press("1")
    expect(line).to_contain_text("0–2 / ⏎")
    expect(line).to_contain_text("continue / choose 1")
    expect(page.locator(CHIPS)).to_have_text(["g h 1 ⏎", "g h 10", "g h 11", "g h 12"])
    after = page.evaluate(GLYPH_OFFSETS, CHIPS)
    assert before["glyphs"].keys() == after["glyphs"].keys()
    moved = {
        key: (left, after["glyphs"][key])
        for key, left in before["glyphs"].items()
        if abs(left - after["glyphs"][key]) > 0.5
    }
    assert not moved, f"a key moved while the numeric prefix advanced: {moved}"
    assert abs(before["width"] - after["width"]) <= 0.5
    assert abs(before["left"] - after["left"]) <= 0.5

    # One Escape gives back the digit and keeps the chosen list standing.
    page.keyboard.press("Escape")
    expect(line).to_contain_text("1–12")
    page.keyboard.press("1")
    visible = page.evaluate(
        """() => {
          const link = document.querySelector('#link-1').getBoundingClientRect();
          const banner = document.querySelector('.lf-banner').getBoundingClientRect();
          return {scroll: document.scrollingElement.scrollTop, top: link.top, bottom: link.bottom,
                  banner: banner.bottom, height: innerHeight};
        }"""
    )
    assert visible["top"] > visible["banner"] + 48
    assert visible["bottom"] < visible["height"] - 48
    page.keyboard.press("Enter")
    expect(page.locator("#link-1")).to_be_focused()
    stayed = page.evaluate(
        """() => ({
          scroll: document.scrollingElement.scrollTop,
          top: document.querySelector('#link-1').getBoundingClientRect().top,
        })"""
    )
    assert stayed["scroll"] == pytest.approx(visible["scroll"], abs=0.5)
    assert stayed["top"] == pytest.approx(visible["top"], abs=0.5)

    page.evaluate("() => document.scrollingElement.scrollTo(0, 0)")
    page.keyboard.press("g")
    page.keyboard.press("h")
    page.keyboard.press("1")
    page.keyboard.press("2")
    expect(page.locator("#link-12")).to_be_focused()
    revealed = page.locator("#link-12").bounding_box()
    assert revealed is not None
    assert revealed["y"] + revealed["height"] > page.viewport_size["height"] * 0.75
    assert revealed["y"] + revealed["height"] <= page.viewport_size["height"]
    assert errors == []
    page.close()


def test_escape_gives_the_chord_back_one_press_at_a_time(browser, serve):
    """The keyboard is a stack and the address chord is two presses of it: `g` opens
    the window over every list the page has, and the letter names one of them. The
    armed chip says as much, reading `g` and then `g h`, and the chips on the page
    narrow with it. So Esc gives the letter back and the next Esc closes the window.

    It spent both on one press, which put a reader who had narrowed to the wrong list
    back on the page — pressing `g` again to reach a window that had been standing the
    whole time. The chips are what make the two stages visible, so they are what the
    unwind is read off: every list's again, then none. Direct panel destinations complete
    on their mnemonic and therefore add no intermediate Escape rung."""
    page, errors = open_page(browser, serve(ADDRESSED_PAGE))
    line = page.locator(".lf-keyline")

    page.keyboard.press("g")
    expect(page.locator(CHIPS)).to_have_text(["g h 1", "g h 2", "g f 1"])
    expect(line).to_contain_text("cancel")

    # The letter narrows the window to its own list, which is the second layer.
    page.keyboard.press("h")
    expect(page.locator(CHIPS)).to_have_text(["g h 1", "g h 2"])
    expect(line).to_contain_text("back to the lists")

    # One press gives that back and no more: the window still stands, over every list.
    page.keyboard.press("Escape")
    expect(page.locator(CHIPS)).to_have_text(["g h 1", "g h 2", "g f 1"])
    expect(line).to_contain_text("cancel")
    # And a letter still names one, so what came back is the window and not its ghost.
    page.keyboard.press("h")
    expect(page.locator(CHIPS)).to_have_text(["g h 1", "g h 2"])

    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(page.locator(CHIPS)).to_have_count(0)
    expect(line).not_to_contain_text("cancel")
    assert errors == []
    page.close()


def test_the_arrows_say_which_way_the_section_under_the_reader_goes(browser, serve):
    """⏎ and space toggle a disclosure; → opens it and ← closes it. A direction and not a
    second toggle, which is the whole of what they add: → over a section already open
    leaves it open, where a toggle would have shut it. Only the direction with somewhere
    to go is bound, so the line names ← over an open section and → over a shut one and
    every key it names is a key that works — and each press that must change nothing
    follows one that changed something, since a box nobody has touched passes that
    assertion however dead the scope is.

    Both spellings of a folded section, because a reader standing on one cannot see which
    it is: the platform's <details>, and a settled option group, which is a span the
    widget wrote `aria-expanded` onto. One scope answers for both, and the press goes
    through the element's own click either way, so the keyboard leaves the page in the
    state the pointer would have left it in.

    The word follows either spelling within the press, not within the poll. Neither
    reports itself — an aria-expanded write fires no event at all — so what the line says
    about the key under the reader's finger rests on the attribute watch rather than on
    the two-second poll behind it. Both readings of it are taken once, through
    `key_line`: an assertion that retries cannot tell the watch from a poll that lands
    inside its budget, and the first version of this test went green with the watch
    broken.

    Shift+← is the last thing this holds to: a summary's words are the page's, and
    extending a selection through them must not shut the section they are in."""
    page, errors = open_page(browser, serve(DISCLOSED_PAGE))
    line = page.locator(".lf-keyline")
    opened, shut = r"⏎ / space / ←", r"⏎ / space / →"

    dsc = page.locator("#dsc")
    head = page.locator("#dsc-head")
    head.focus()
    expect(dsc).not_to_have_attribute("open", "")
    expect(line).to_contain_text(re.compile(shut + r"\s*open"))

    page.keyboard.press("ArrowRight")
    expect(dsc).to_have_attribute("open", "")
    # The press does not move the reader off what they pressed it on, so the next one
    # lands on the same section.
    expect(head).to_be_focused()
    said = key_line(page)
    assert re.search(opened + r"\s*close", said), said

    # A direction and not a toggle, which is the one thing ⏎ cannot say: this press
    # follows one that is proven live, so a scope answering nothing at all could not pass
    # it, and a toggle bound to the arrows would have shut the section here.
    page.keyboard.press("ArrowRight")
    expect(dsc).to_have_attribute("open", "")
    # Shift+← is a reader extending a selection through the summary's own words. A named
    # key asks for its modifiers exactly, so it is not this row's binding.
    page.keyboard.press("Shift+ArrowLeft")
    expect(dsc).to_have_attribute("open", "")

    page.keyboard.press("ArrowLeft")
    expect(dsc).not_to_have_attribute("open", "")
    page.keyboard.press("ArrowLeft")
    expect(dsc).not_to_have_attribute("open", "")

    # And the platform's own pair still toggles, once each: the row owns its whole binding
    # set, so the runtime makes the press the browser was going to make.
    page.keyboard.press("Enter")
    expect(dsc).to_have_attribute("open", "")
    page.keyboard.press(" ")
    expect(dsc).not_to_have_attribute("open", "")

    # The other spelling, which keeps its state in ARIA's own attribute rather than in
    # `open`, and whose press is the widget's own handler rather than the platform's.
    row = page.locator("#settled .lf-settled")
    row.focus()
    expect(row).to_have_attribute("aria-expanded", "false")
    expect(line).to_contain_text(re.compile(shut + r"\s*open"))
    page.keyboard.press("ArrowRight")
    expect(row).to_have_attribute("aria-expanded", "true")
    expect(page.locator("#st-keep")).to_be_visible()
    # Nothing reports this one at all — an aria-expanded write fires no event anywhere —
    # so read once: the word is the attribute watch's answer by the time the press
    # returns, or it is the poll's two seconds later, and only an assertion that refuses
    # to retry can tell those apart.
    said = key_line(page)
    assert re.search(opened + r"\s*close", said), said
    page.keyboard.press("ArrowRight")
    expect(row).to_have_attribute("aria-expanded", "true")
    page.keyboard.press("ArrowLeft")
    expect(row).to_have_attribute("aria-expanded", "false")
    expect(page.locator("#st-keep")).to_be_hidden()

    # A disclosure in a message, where the disclosure scope does not reach: thread markup
    # is a second document beside the version, and the arrows are the page's. A diff,
    # because what is being asked is what a widget's own row names — a widget re-wording
    # this press reads its bindings from DISCLOSE, which answers for where the element
    # stands as well as which way it is standing, so the row cannot offer a key that
    # nothing there runs. The platform's pair still works it, so what differs is the
    # offer rather than the capability.
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c-diff",
            "author": "claude",
            "revision": 1,
            "text": "The patch, for the record.",
            "markup": '<lf-diff id="msg-diff"><pre>'
            "diff --git a/gateway/limits.py b/gateway/limits.py\n"
            "--- a/gateway/limits.py\n"
            "+++ b/gateway/limits.py\n"
            "@@ -38,2 +38,2 @@ class Limiter:\n"
            "     def bucket_key(self, request):\n"
            "-        return request.remote_addr\n"
            "+        return request.token.id\n"
            "</pre></lf-diff>",
        },
    )
    told(page)
    # Opened, because standing somewhere is where focus is and a shut panel has nowhere to
    # stand: without this the summary took no focus, the reader was still on the page's own
    # row, and the line went on describing that one — an assertion that would have passed
    # for the wrong reason had the two been in the same state.
    page.get_by_role("button", name=re.compile("Threads")).click()
    staged = page.locator("#msg-diff summary").first
    expect(staged).to_be_visible()
    staged.focus()
    expect(staged).to_be_focused()
    # Every live row rather than the two hints that fit: the panel's own rows win the line
    # where the reader is standing in it, and what is asked here is what the register
    # answers, not which two chips got the room.
    key_line(page)  # the repaint's own frame, as everywhere else here
    chips = page.evaluate(
        "() => [...document.querySelectorAll('.lf-keyline .lf-key')]"
        ".map(c => c.textContent)"
    )
    assert any("⏎ / space" in c for c in chips), chips
    assert not any("←" in c or "→" in c for c in chips), chips
    # And the press, which is the half that would matter if no surface said anything: the
    # arrow is the page's here and moves nothing, where the platform's pair still folds it.
    opened_now = staged.evaluate("el => el.parentElement.open")
    page.keyboard.press("ArrowLeft")
    assert staged.evaluate("el => el.parentElement.open") is opened_now
    page.keyboard.press("Enter")
    assert staged.evaluate("el => el.parentElement.open") is not opened_now
    assert errors == []
    page.close()


def test_the_key_line_says_what_a_press_will_do(browser, serve):
    """The key line renders the same scene() escapeKey() runs, so what Esc promises
    is what Esc then does, rung by rung: general box → the list → the panel closed.
    And the armed chord is on screen with the panel closed — where the old corner
    badges, display:none inside it, said nothing at all."""
    url = serve(NOTED_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "One thread.",
            "anchor": {"quote": "first passage"},
        },
    )
    page, errors = open_page(browser, url)
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 1")
    line = page.locator(".lf-keyline")

    # Page scope: the standing verbs, thread rows only over threads, and no esc
    # chip — there is nothing to back out of.
    expect(line).to_contain_text("threads")
    expect(line).to_contain_text("more")
    expect(line).not_to_contain_text("esc")

    # Armed with the panel closed: the direct panel destination and its way out are visible.
    page.keyboard.press("g")
    expect(line).to_contain_text("Threads panel")
    expect(line).to_contain_text("cancel")
    page.keyboard.press("Escape")
    expect(line).not_to_contain_text("Threads panel")
    # Asked of the armed chip: "threads" is the page's own c word now (the key goes to
    # the panel), so it stands on the resting line and cannot say whether g is pending.
    expect(page.locator(".lf-keyline kbd.armed")).to_have_count(0)

    # c stands the reader on the list and c again opens the general box: there the line
    # says send, and where Esc goes.
    page.keyboard.press("c")
    expect(page.locator(".lf-threads")).to_be_focused()
    page.keyboard.press("c")
    expect(line).to_contain_text("send")
    expect(line).to_contain_text("back to list")
    # A send key on an empty box is answered, not swallowed — silence reads as a
    # send that happened.
    page.keyboard.press("ControlOrMeta+Enter")
    expect(page.locator(".lf-toast")).to_contain_text("Nothing to send")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-threads")).to_be_focused()
    expect(line).to_contain_text("close threads")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-panel")).to_be_hidden()
    expect(line).not_to_contain_text("close threads")
    # Focus doesn't fall to body: it lands on the control that reopens the panel.
    expect(page.locator(".lf-threads-toggle")).to_be_focused()

    # The fast rung: t reopens onto a thread, and Esc from it is one press out.
    # Every rung earns a press here because Esc is the only keyboard collapse.
    page.keyboard.press("t")
    expect(page.locator(".lf-thread")).to_be_focused()
    expect(line).to_contain_text("close threads")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-panel")).to_be_hidden()
    assert errors == []
    page.close()


def test_a_comments_quoted_passage_is_in_the_keyboard_journey(browser, serve):
    """The pointer's return-to-passage action is a focusable, named control too."""
    lead = "".join(f"<p>Earlier reading context, line {n}.</p>" for n in range(14))
    tail = "".join(f"<p>Later reading context, line {n}.</p>" for n in range(14))
    noted_page = NOTED_PAGE.replace('<p id="p1">', f'{lead}<p id="p1">').replace(
        '<figure id="fig">', f'{tail}<figure id="fig">'
    )
    url = serve(noted_page)
    d = serve.page_dir
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Check this wording.",
            "anchor": {"section": "p1", "quote": "first passage"},
        },
    )
    page, errors = open_page(browser, live_url(url))
    page.emulate_media(reduced_motion="reduce")
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 1")

    page.keyboard.press("c")
    expect(page.locator(".lf-threads")).to_be_focused()
    page.keyboard.press("t")
    expect(page.locator(".lf-thread")).to_be_focused()
    page.keyboard.press("Tab")
    quote = page.locator(".lf-thread .lf-quote")
    expect(quote).to_be_focused()
    expect(quote).to_have_attribute("role", "button")
    expect(quote).to_have_attribute("aria-keyshortcuts", "Enter Space")
    expect(page.locator(".lf-keyline")).to_contain_text("return to the passage")

    quote.evaluate(
        """node => node.addEventListener('click', () => {
          node.dataset.keyboardActivations =
            String(Number(node.dataset.keyboardActivations || 0) + 1);
        })"""
    )
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
    expect(quote).to_have_attribute("data-keyboard-activations", "2")
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
    page.keyboard.press("Enter")
    returned = page.evaluate(
        """() => ({
          scroll: document.scrollingElement.scrollTop,
          top: document.querySelector('#p1').getBoundingClientRect().top,
          banner: document.querySelector('.lf-banner').getBoundingClientRect().bottom,
        })"""
    )
    assert returned["scroll"] != pytest.approx(sliver["scroll"], abs=0.5)
    assert returned["top"] > returned["banner"]

    # A resolved thread keeps its page placement even though its folded quote has no live
    # mark. On a covering phone panel, that retained destination remains an enabled
    # keyboard action, spends the sheet, and returns to the passage.
    page.get_by_role("button", name="Resolve").click()
    round_trip(page)
    resized(page, 390, 800)
    details = page.locator(".lf-details")
    details.evaluate("el => { el.open = true; }")
    resolved_quote = details.locator(".lf-quote")
    expect(resolved_quote).not_to_have_class(re.compile(r"\bdetached\b"))
    expect(resolved_quote).to_have_attribute("aria-disabled", "false")
    page.evaluate(
        "() => document.scrollingElement.scrollTo(0, document.scrollingElement.scrollHeight)"
    )
    placed_before = page.evaluate("() => document.scrollingElement.scrollTop")
    resolved_quote.focus()
    expect(page.locator(".lf-keyline")).to_contain_text("return to the passage")
    page.keyboard.press("Enter")
    expect(page.locator(".lf-panel")).to_be_hidden()
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

    # When a later version removes the passage altogether, the same folded quote is an
    # informative disabled stop. A pointer press has no destination to spend the sheet on,
    # so the covering panel and the page behind it both stay where the reader left them.
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    without_passage = re.sub(r'<p id="p1">.*?</p>', "", noted_page, flags=re.DOTALL)
    (d / "versions" / "v2.html").write_text(without_passage)
    stamp_version_file(d, 2, "remove the quoted passage")
    wait_for_revision(page, 2)
    details.evaluate("el => { el.open = true; }")
    resolved_quote = details.locator(".lf-quote")
    expect(resolved_quote).to_have_class(re.compile(r"\bdetached\b"))
    expect(resolved_quote).to_have_attribute("aria-disabled", "true")
    assert resolved_quote.get_attribute("aria-keyshortcuts") is None
    expect(page.locator(".lf-panel")).to_be_visible()
    stranded_before = page.evaluate("() => document.scrollingElement.scrollTop")
    quote_box = resolved_quote.bounding_box()
    assert quote_box is not None
    page.mouse.click(
        quote_box["x"] + quote_box["width"] / 2,
        quote_box["y"] + quote_box["height"] / 2,
    )
    expect(page.locator(".lf-panel")).to_be_visible()
    assert page.evaluate("() => document.scrollingElement.scrollTop") == stranded_before
    resolved_quote.focus()
    expect(page.locator(".lf-keyline")).not_to_contain_text("return to the passage")
    assert errors == []
    page.close()


def test_a_text_box_keeps_its_keys_from_the_widget_around_it(browser, serve):
    """A widget scope may contain a text box, but its bare keys still type there.

    The focused element's own rows remain nearer so a draft can keep its specific Escape
    and a wired composer can send with Mod+Enter. The text-entry scope then claims the
    characters and editing keys before an ancestor widget can see them."""
    page, errors = open_page(browser, serve(NOTED_PAGE))
    page.evaluate(
        """async () => {
          const { keys } = await import('/runtime/widget-api.js');
          const host = document.createElement('section');
          host.id = 'key-owning-widget';
          const box = document.createElement('textarea');
          host.append(box);
          document.querySelector('main').append(host);
          keys(host, 'Around a text box', [
            {id: 'test.widget',
             keys: ['a', 'Enter', 'Shift+ArrowLeft', 'Mod+z', 'Escape'],
             does: 'Work the widget', line: 'work widget',
             run: (binding) => host.dataset.fired = binding},
          ]);
          box.focus();
        }"""
    )

    page.keyboard.press("a")
    page.keyboard.press("Enter")
    expect(page.locator("#key-owning-widget textarea")).to_have_value("a\n")
    assert page.locator("#key-owning-widget").get_attribute("data-fired") is None
    page.keyboard.press("Shift+ArrowLeft")
    page.keyboard.press("Control+z")
    assert page.locator("#key-owning-widget").get_attribute("data-fired") is None

    # An unrelated core layer may stand at the same time. The widget ancestor remains
    # nearer for keys the text-entry shield does not claim; only editing stays native.
    page.locator(".lf-version").click()
    expect(page.locator(".lf-version-menu")).to_be_visible()
    page.locator("#key-owning-widget textarea").focus()
    page.keyboard.press("Escape")
    expect(page.locator("#key-owning-widget")).to_have_attribute("data-fired", "Escape")
    expect(page.locator(".lf-version-menu")).to_be_visible()
    assert errors == []
    page.close()


def test_a_scope_cannot_give_one_live_key_two_meanings(browser, serve):
    """An ambiguous row set is refused at the register boundary.

    Reusing a key in mutually exclusive states remains valid; a card grip relies on that
    to make Enter and Space mean grab before the move and drop during it."""
    page, errors = open_page(browser, serve(NOTED_PAGE))
    answers = page.evaluate(
        """async () => {
          const { keys } = await import('/runtime/widget-api.js');
          const { activeRows, answers: bindingAnswers, canonicalBinding } =
            await import('/runtime/keyboard/bindings.js');
          const { paintKeys } = await import('/runtime/keyboard/scopes.js');
          const declare = (id, rows) => {
            const button = document.createElement('button');
            button.id = id;
            document.querySelector('main').append(button);
            try {
              keys(button, id, rows);
              return 'declared';
            } catch (error) {
              return error.message;
            } finally {
              button.remove();
            }
          };
          const conflicts = (rows) => {
            try {
              activeRows(rows, 'Alias meanings');
              return 'accepted';
            } catch (error) {
              return error.message;
            }
          };
          const keptInvalid = (id, when) => {
            const button = document.createElement('button');
            button.id = id;
            document.querySelector('main').append(button);
            let declaration = 'declared';
            try {
              keys(button, id, [
                {id: 'test.kept-first', keys: ['F4'], does: 'First kept meaning', line: 'first', run: () => {}},
                {id: 'test.kept-second', keys: ['F4'], does: 'Second kept meaning', line: 'second', run: () => {}},
              ], when);
            } catch (error) {
              declaration = error.message;
            }
            const paints = [];
            for (let i = 0; i < 2; i++) {
              try {
                paintKeys();
                paints.push('painted');
              } catch (error) {
                paints.push(error.message);
              }
            }
            return {declaration, paints};
          };
          return {
            ambiguous: declare('ambiguous', [
              {id: 'test.first', keys: ['F2'], does: 'First meaning', line: 'first', run: () => {}},
              {id: 'test.second', keys: ['F2'], does: 'Second meaning', line: 'second', run: () => {}},
            ]),
            exclusive: declare('exclusive', [
              {id: 'test.first-state', keys: ['F2'], does: 'First state', line: 'first',
               when: () => true, run: () => {}},
              {id: 'test.second-state', keys: ['F2'], does: 'Second state', line: 'second',
               when: () => false, run: () => {}},
            ]),
            missingIdentity: declare('missing-identity', [
              {keys: ['F5'], does: 'Anonymous command', line: 'anonymous', run: () => {}},
            ]),
            malformedIdentity: declare('malformed-identity', [
              {id: 'Sentence shaped identity', keys: ['F5'], does: 'Named badly',
               line: 'bad identity', run: () => {}},
            ]),
            duplicateIdentity: declare('duplicate-identity', [
              {id: 'test.same', keys: ['F5'], does: 'First route', line: 'first', run: () => {}},
              {id: 'test.same', keys: ['F6'], does: 'Second route', line: 'second', run: () => {}},
            ]),
            modifierAlias: conflicts([
              {keys: ['Mod+Shift+x'], does: 'First alias'},
              {keys: ['Shift+Mod+x'], does: 'Second alias'},
            ]),
            caseAlias: conflicts([
              {keys: ['a'], does: 'Lowercase alias'},
              {keys: ['A'], does: 'Uppercase alias'},
            ]),
            punctuationAlias: conflicts([
              {keys: ['?'], does: 'Layout-owned punctuation'},
              {keys: ['Shift+?'], does: 'Shifted alias'},
            ]),
            spacePair: conflicts([
              {keys: [' '], does: 'Read down'},
              {keys: ['Shift+ '], does: 'Read up'},
            ]),
            spaceIdentity: [canonicalBinding(' '), canonicalBinding('Shift+ ')],
            spaceAnswers: {
              down: bindingAnswers(' ', {
                key: ' ', metaKey: false, ctrlKey: false, altKey: false, shiftKey: false,
              }),
              downFromShift: bindingAnswers(' ', {
                key: ' ', metaKey: false, ctrlKey: false, altKey: false, shiftKey: true,
              }),
              up: bindingAnswers('Shift+ ', {
                key: ' ', metaKey: false, ctrlKey: false, altKey: false, shiftKey: true,
              }),
              upWithoutShift: bindingAnswers('Shift+ ', {
                key: ' ', metaKey: false, ctrlKey: false, altKey: false, shiftKey: false,
              }),
            },
            noncanonical: declare('noncanonical', [
              {id: 'test.noncanonical', keys: ['Shift+Mod+x'], does: 'Noncanonical binding',
               line: 'work', run: () => {}},
            ]),
            immediateTransaction: keptInvalid('kept-immediate'),
            gatedTransaction: keptInvalid('kept-gated', () => true),
          };
        }"""
    )
    assert "two live meanings for F2" in answers["ambiguous"], answers
    assert answers["exclusive"] == "declared", answers
    assert "has no stable command id" in answers["missingIdentity"], answers
    assert "is not a stable command id" in answers["malformedIdentity"], answers
    assert "declares test.same twice" in answers["duplicateIdentity"], answers
    assert "two live meanings for Shift+Mod+x" in answers["modifierAlias"], answers
    assert "two live meanings for A" in answers["caseAlias"], answers
    assert "two live meanings for Shift+?" in answers["punctuationAlias"], answers
    assert answers["spacePair"] == "accepted", answers
    assert answers["spaceIdentity"] == [" ", "Shift+ "], answers
    assert answers["spaceAnswers"] == {
        "down": True,
        "downFromShift": False,
        "up": True,
        "upWithoutShift": False,
    }, answers
    assert "write the canonical Mod+Shift+x" in answers["noncanonical"], answers
    assert "two live meanings for F4" in answers["immediateTransaction"]["declaration"]
    assert answers["immediateTransaction"]["paints"] == ["painted", "painted"]
    assert answers["gatedTransaction"]["declaration"] == "declared"
    assert "two live meanings for F4" in answers["gatedTransaction"]["paints"][0]
    assert answers["gatedTransaction"]["paints"][1] == "painted"

    # Help merges instances with the same title for presentation. Repeated keys there
    # belong to separate focus locations, so they are not a conflict in either scope.
    page.evaluate(
        """async () => {
          const { keys } = await import('/runtime/widget-api.js');
          let first;
          for (const label of ['First', 'Second']) {
            const button = document.createElement('button');
            button.textContent = label;
            document.querySelector('main').append(button);
            if (!first) first = button;
            keys(button, 'Repeated controls', [
              {id: 'test.repeated', keys: ['F3'], does: () => `Work ${label}`,
               line: 'work', run: () => button.dataset.fired = '1'},
              ...(label === 'Second' ? [{
                id: 'test.second-only', keys: ['F6'], does: 'Work only the second',
                line: 'second only', reach: 'on the second control',
                run: () => button.dataset.secondFired = '1',
              }] : []),
            ]);
          }
          first.focus();
        }"""
    )
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.get_by_role("dialog", name="Keyboard reference")).to_be_visible()
    search = page.get_by_role("combobox", name="Search keyboard shortcuts")
    search.fill("work only the second")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    expect(page.locator(".lf-help-meta")).to_have_text(
        "Available on the second control"
    )
    search.fill("work first")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    expect(page.get_by_role("button", name="First", exact=True)).to_have_attribute(
        "data-fired", "1"
    )
    expect(page.get_by_role("button", name="Second", exact=True)).not_to_have_attribute(
        "data-fired", "1"
    )
    assert errors == []
    page.close()


def test_the_signoff_key_approves_the_version(browser, serve):
    """The page-level decision has a direct, intentional key from its visible label."""
    html = NOTED_PAGE.replace(
        '<script type="module" src="/leaf.js"></script>',
        '<meta name="lf-review" content="sign-off">\n'
        '<script type="module" src="/leaf.js"></script>',
    )
    page, errors = open_page(browser, serve(html))
    approve = page.locator(".lf-signoff")
    expect(approve).to_have_attribute("aria-keyshortcuts", "Shift+l")

    page.keyboard.press("Shift+l")
    round_trip(page)
    expect(approve).to_have_text("✓ Version approved")
    expect(approve).not_to_have_attribute("aria-keyshortcuts", "Shift+l")
    assert "(L)" not in approve.get_attribute("title")
    done = [e for e in events_model.read_events(serve.page_dir) if e["kind"] == "done"]
    assert len(done) == 1, done
    assert done[0]["text"] == "Looks good"
    assert errors == []
    page.close()


def test_character_shortcuts_can_be_turned_off_without_losing_the_keyboard(
    browser, serve
):
    """Speech-input and error-prone readers can disable every character command.

    The visible More button remains a native keyboard route back to the preference;
    Enter, Escape, and other non-character controls keep their ordinary meanings."""
    url = serve(DECISIONS_PAGE)
    events_model.append_event(
        serve.page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "A note."},
    )
    page, errors = open_page(browser, url)
    more = page.locator(".lf-key-more")
    expect(more).to_have_attribute("aria-label", "? more")
    version = page.locator(".lf-version")
    expect(version).to_have_attribute("aria-keyshortcuts", "v")
    expect(version).to_have_attribute("title", re.compile(r"\(v\)$"))
    expect(page.locator(".lf-general textarea")).to_have_attribute(
        "placeholder", re.compile(r" · c$")
    )
    page.keyboard.press("c")
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 1")
    reply = page.locator(".lf-thread textarea")
    expect(reply).to_have_attribute("placeholder", "Reply")
    page.keyboard.press("Escape")

    page.keyboard.press("?")
    page.keyboard.press("?")
    toggle = page.get_by_role("button", name="Character shortcuts")
    expect(toggle).to_have_attribute("aria-pressed", "true")
    toggle.click()
    expect(toggle).to_have_attribute("aria-pressed", "false")
    expect(page.locator(".lf-help")).not_to_contain_text("Go to the Threads panel")

    page.keyboard.press("Escape")
    expect(version).not_to_have_attribute("aria-keyshortcuts", "v")
    expect(version).not_to_have_attribute("title", re.compile(r"\(v\)$"))
    expect(page.locator(".lf-latest-chip")).not_to_have_attribute(
        "title", re.compile(r"\(v v\)$")
    )
    expect(page.locator(".lf-general textarea")).not_to_have_attribute(
        "placeholder", re.compile(r" · c$")
    )
    expect(reply).to_have_attribute("placeholder", "Reply")
    # Space is control activation, not a character shortcut. Offered buttons retain
    # both native-button keys and advertise both from the same register while letters,
    # digits, and punctuation are off.
    mark = page.locator("#live-question .lf-pick").first
    mark.focus()
    shortcuts = mark.get_attribute("aria-keyshortcuts").split()
    assert {"Enter", "Space"} <= set(shortcuts), shortcuts
    page.keyboard.press("Space")
    expect(page.locator("#lq-keep")).to_have_attribute("chosen", "")

    expect(more).to_have_attribute("aria-label", "More keyboard shortcuts")
    assert more.get_attribute("aria-keyshortcuts") is None
    page.keyboard.press("c")
    expect(page.locator(".lf-panel")).to_be_hidden()
    page.keyboard.press("?")
    expect(page.locator(".lf-help")).to_be_hidden()

    # The preference survives a visit, and the non-character Enter path can reverse it.
    page.reload()
    page.wait_for_function("() => document.body.hasAttribute('data-lf-presented')")
    more = page.locator(".lf-key-more")
    expect(more).to_have_attribute("aria-label", "More keyboard shortcuts")
    more.focus()
    page.keyboard.press("Enter")
    expect(page.locator(".lf-help")).to_be_visible()
    toggle = page.get_by_role("button", name="Character shortcuts")
    expect(toggle).to_have_attribute("aria-pressed", "false")
    toggle.focus()
    page.keyboard.press("Enter")
    expect(toggle).to_have_attribute("aria-pressed", "true")
    create = page.locator('.lf-help-command[data-lf-command="comment.create"]')
    expect(create).to_have_attribute("data-lf-available", "true")
    create.click()
    expect(page.locator(".lf-help")).to_be_hidden()
    expect(version).to_have_attribute("aria-keyshortcuts", "v")
    expect(page.locator(".lf-general textarea")).to_have_attribute(
        "placeholder", re.compile(r" · c$")
    )
    expect(page.locator(".lf-panel")).to_be_visible()
    assert errors == []
    page.close()


def test_a_key_the_runtime_binds_is_a_key_some_surface_names(browser, serve):
    """One declaration per runtime binding, and every surface is a projection of it.

    Browser-owned paging is absent from those surfaces; declared Leaf commands still
    require the words the key line and reference need.

    It is refused now, where a scope is declared, so the next binding written without a
    word fails on the page that introduces it rather than going quiet on every page after
    it. A row that presses nothing needs none — F7 is the browser's caret browsing, real
    and worth knowing and not what the next press does."""
    page, errors = open_page(browser, serve(NOTED_PAGE))
    line = page.locator(".lf-keyline")
    expect(line).not_to_contain_text("page down")
    expect(line).not_to_contain_text("page up")
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.locator(".lf-help")).not_to_contain_text("Move 60% of a page")
    expect(page.locator(".lf-help")).to_contain_text("Caret browsing")
    page.keyboard.press("Escape")
    expect(line).not_to_contain_text("F7")

    refused = page.evaluate(
        """async () => {
          const { keys } = await import('/runtime/widget-api.js');
          try {
            keys(document.body, 'A project scope', [
              { id: 'test.no-line', keys: ['F2'],
                does: 'a press with nothing to say for itself',
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
          const { keys } = await import('/runtime/widget-api.js');
          try {
            keys(document.body, 'A project scope', [
              { id: 'test.bad-modifier', keys: ['Ctrl+k'],
                does: 'a modifier the matcher never asks about',
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

    # A registered result may deliberately precede the platform's own half of a press.
    # It still enters through the same register — and therefore the same surfaces and
    # scoping — but the dispatcher must not cancel that native result. The versions menu
    # uses this for the Tab that closes it before the browser moves focus past its door.
    native = page.evaluate(
        """async () => {
          const { keys } = await import('/runtime/widget-api.js');
          const owner = document.createElement('div');
          owner.tabIndex = -1;
          document.body.append(owner);
          owner.focus();
          let ran = 0;
          keys(owner, 'A native companion', [
            { id: 'test.native-companion', keys: ['F2'],
              does: 'Run before the browser', line: 'run first',
              native: true, run: () => ran++ },
          ]);
          const event = new KeyboardEvent(
            'keydown', {key: 'F2', bubbles: true, cancelable: true}
          );
          owner.dispatchEvent(event);
          owner.remove();
          return {ran, prevented: event.defaultPrevented};
        }"""
    )
    assert native == {"ran": 1, "prevented": False}, native
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
    layer = ROOT / "skills/leaf"
    sources = [
        layer / "assets/leaf.js",
        *sorted((layer / "assets/runtime").rglob("*.js")),
        *sorted((layer / "packages/default/widgets").glob("*.js")),
        *sorted((ROOT / "examples/packages").glob("*/widgets/*.js")),
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


def test_native_controls_need_no_generic_space_binding(browser, serve):
    """The reference has no synthetic generic-control command. Specialized controls
    such as a board grip still declare the Space meaning that belongs to their widget."""
    page, errors = open_page(browser, serve(BOARD_PAGE))
    page.keyboard.press("?")
    page.keyboard.press("?")
    help_el = page.locator(".lf-help")
    expect(help_el).not_to_contain_text("On a control")
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
    """A held key repeats keydown where a real button fires once. A walk wants that — t
    down threads, d down decisions, arrows down the tray — and a press that toggles or navigates
    does not: a held `]` was a page navigation per repeat, and a held pick a `choose` per
    repeat, each of them one decision the reader made once. So a row says whether it
    repeats and the default is no, where before only `offer`'s own listener had thought
    about it and the global table had not.

    No gesture Playwright makes carries the repeat flag, so the press is dispatched with
    it set. That is the event a held key sends and the handler under test is the one the
    page installed; the tap below it, dispatched the same way and answered, is what says
    so rather than leaving the held press to pass for want of reaching anything."""
    live_leaf("second", "A second leaf")
    page, errors = open_page(browser, serve(DECISIONS_PAGE, comments=3))
    press = """([key, repeat]) => document.dispatchEvent(
        new KeyboardEvent('keydown', {key, repeat, bubbles: true, cancelable: true}))"""

    page.keyboard.press("t")
    expect(page.locator(".lf-thread").first).to_be_focused()
    page.evaluate(press, ["t", True])  # a walk repeats
    expect(page.locator(".lf-thread").nth(1)).to_be_focused()

    page.keyboard.press("d")
    expect(page.locator("#live-question-decision[data-lf-decision]")).to_have_count(1)
    page.evaluate(press, ["d", True])  # the same grammar repeats for decisions
    expect(page.locator("#sug-refill[data-lf-decision]")).to_have_count(1)

    tray = page.locator(".lf-others-panel")
    page.keyboard.press("g")
    page.evaluate(press, ["l", True])  # a panel destination does not repeat
    expect(tray).to_be_hidden()
    page.evaluate(press, ["l", False])  # the same event, answered
    expect(tray).to_be_visible()
    assert errors == []
    page.close()


def test_the_key_line_keeps_two_local_hints_and_progressively_reveals_the_rest(
    browser, serve
):
    """The short line is a glance, not the keyboard reference. It keeps two bindings:
    first the innermost live action, then the way out when the current scene has one. One
    `? more` unfolds a bounded shelf of current commands; `? all shortcuts` then opens
    the complete searchable register.

    The panel's general box is the causal contrast for the cap. A full page row crosses
    into the panel and paints over the box; two hints end before it. The overlap is tested
    before opening the reference so a searchable popup cannot make the symptom disappear
    merely by covering both surfaces."""
    page, errors = open_page(browser, serve(NOTED_PAGE, comments=2))
    page.set_viewport_size({"width": 1200, "height": 800})
    page.get_by_role("button", name=re.compile("^Threads")).click()

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
    #
    # Two presses, because the panel was opened by its button in the banner and that is
    # where the reader is standing: focus in the chrome is not a place in the page, so
    # the first `c` is the page's and goes to the list, and the second is the panel's
    # and goes to the box. The line in between is the contrast — the list's own keys are
    # what a reader gets for pressing once, which is the whole point of the two presses.
    page.keyboard.press("c")
    expect(page.locator(".lf-threads")).to_be_focused()
    expect(visible_hints.nth(0)).not_to_contain_text("send")
    page.keyboard.press("c")
    expect(visible_hints.nth(0)).to_contain_text("send")
    expect(visible_hints.nth(1)).to_contain_text("back to list")

    more = page.get_by_role("button", name="? more", exact=True)
    expect(more).to_have_attribute("aria-expanded", "false")
    more.click()
    help_el = page.locator(".lf-help")
    search = page.get_by_role("combobox", name="Search keyboard shortcuts")
    expect(help_el).to_be_hidden()
    expect(line).to_have_attribute("data-lf-expanded", "true")
    expect(page.locator(".lf-live")).to_contain_text(
        "More keyboard shortcuts shown. Press question mark again for all shortcuts"
    )
    assert visible_hints.count() > 2
    expect(line).to_contain_text("less")
    for width in (1200, 420):
        page.set_viewport_size({"width": width, "height": 800})
        page.evaluate(RENDERED)
        geometry = line.evaluate(
            """node => {
              const visible = [...node.children].filter(el => el.checkVisibility());
              const boxes = visible.map(el => el.getBoundingClientRect());
              const tolerance = Math.min(...visible.map(el => el.offsetHeight)) / 2;
              const rows = [];
              for (const el of visible)
                if (rows.every(top => Math.abs(top - el.offsetTop) > tolerance))
                  rows.push(el.offsetTop);
              return {
                rows: rows.length,
                clientWidth: node.clientWidth,
                scrollWidth: node.scrollWidth,
                clientHeight: node.clientHeight,
                scrollHeight: node.scrollHeight,
                bandHeight: Math.max(...boxes.map(box => box.bottom))
                          - Math.min(...boxes.map(box => box.top)),
                maxItemHeight: Math.max(...boxes.map(box => box.height)),
              };
            }"""
        )
        assert geometry["rows"] <= 2, geometry
        assert geometry["scrollWidth"] <= geometry["clientWidth"], geometry
        assert geometry["scrollHeight"] <= geometry["clientHeight"], geometry
        assert geometry["bandHeight"] <= geometry["maxItemHeight"] * 2 + 8, geometry
    more = page.get_by_role("button", name="? all shortcuts", exact=True)
    expect(more).to_have_attribute("aria-expanded", "true")
    more.click()
    expect(help_el).to_be_visible()
    expect(search).to_be_focused()
    expect(page.get_by_role("button", name="Back to more shortcuts")).to_be_visible()
    expect(help_el).not_to_contain_text("With more keyboard shortcuts")

    search.fill("Cancel item selection")
    expect(help_el.locator("tr:not([hidden])")).to_have_count(1)
    expect(help_el.locator("tr:not([hidden])").first).to_contain_text(
        "Cancel item selection"
    )

    search.fill("thread panel")
    expect(
        help_el.get_by_role("heading", name="In the thread panel", exact=True)
    ).to_be_visible()
    expect(help_el.locator("tr:not([hidden])")).not_to_have_count(0)

    search.fill("no such shortcut")
    expect(help_el.locator(".lf-help-empty")).to_be_visible()
    expect(help_el.locator("tr:not([hidden])")).to_have_count(0)
    page.keyboard.press("Escape")
    expect(help_el).to_be_hidden()
    expect(line).to_have_attribute("data-lf-expanded", "true")
    expect(
        page.get_by_role("button", name="? all shortcuts", exact=True)
    ).to_be_focused()
    page.keyboard.press("Escape")
    expect(line).to_have_attribute("data-lf-expanded", "false")
    expect(page.locator(".lf-live")).to_contain_text("Fewer keyboard shortcuts shown")
    expect(page.get_by_role("button", name="? more", exact=True)).to_have_attribute(
        "aria-expanded", "false"
    )
    expect(visible_hints).to_have_count(2)
    assert errors == []
    page.close()


def test_the_expanded_key_line_stands_down_for_a_page_press_and_another_command(
    browser, serve
):
    """The shelf is transient help, so either kind of onward motion folds it. The
    page-click owner handles presses outside the line, while the dispatcher folds it
    before a registered command runs."""
    page, errors = open_page(browser, serve(NOTED_PAGE))
    line = page.locator(".lf-keyline")

    page.keyboard.press("?")
    expect(line).to_have_attribute("data-lf-expanded", "true")
    page.locator("#t").click()
    expect(line).to_have_attribute("data-lf-expanded", "false")

    page.keyboard.press("?")
    expect(line).to_have_attribute("data-lf-expanded", "true")
    page.keyboard.press("g")
    expect(line).to_have_attribute("data-lf-expanded", "false")
    expect(line.locator("kbd.armed")).to_have_text("g")
    assert errors == []
    page.close()


def test_the_walk_reaches_more_and_goes_on_after_the_line_has_repainted(browser, serve):
    """A frame passes between one Tab and the next for every reader, and none for a test.

    `renderLine` runs under `paintHere`'s frame, so it repaints the key line just after
    focus lands somewhere — including on More, the line's own button. Clearing the line
    with `textContent = ""` took More out of the document, and removing a focused element
    blurs it; it came straight back as the same node, connected, with the reader dropped
    to `body`. The button was never gone to look at and never gone from the DOM to assert
    on, so nothing but standing on it one frame later could see it.

    That is why the frame is the whole of this test. Pressed back to back the walk is
    whole, because the repaint has not run yet between the presses — the failure hid
    behind the one habit every browser test has. So each press waits two frames, and the
    contrast is against the same walk pressed fast: they have to agree.

    Reaching More is the claim, and going on past it is the other half — a walk that
    loses focus to `body` does not stop, it silently restarts, and a reader tabbing
    through their own page never gets past the banner."""
    page, errors = open_page(browser, serve(NOTED_PAGE, comments=2))
    who = """() => {
      let e = document.activeElement;
      while (e?.shadowRoot?.activeElement) e = e.shadowRoot.activeElement;
      return e === document.body ? 'body' : (e?.className || e?.tagName || 'null');
    }"""

    walks = {}
    for settled in (False, True):
        # Start each walk from the page rather than from the last control in the
        # previous walk. Blurring preserves that control as the sequential focus
        # starting point, which only happened to wrap before the page gained a visual
        # reaction proxy as its first Tab stop.
        page.evaluate("() => document.body.focus()")
        trail = []
        for _ in range(24):
            page.keyboard.press("Tab")
            if settled:
                page.evaluate(RENDERED)
            trail.append(page.evaluate(who))
        walks["frame" if settled else "fast"] = trail

    # The two walks have to be the same walk. A count of lost stops would need a
    # threshold, and there is no honest one: this page's order is three controls and a
    # wrap, so a `body` every fourth press is the walk working. What says focus was lost
    # is that waiting changed where the presses went.
    assert walks["fast"] == walks["frame"], (
        "a frame between presses changed the tab order:\n"
        f"  fast  {walks['fast']}\n  frame {walks['frame']}"
    )
    for how, trail in walks.items():
        assert any("lf-key-more" in at for at in trail), (
            f"tabbing {how}, the walk never stood on More in 24 presses: {trail}"
        )

    # Standing on More, the repaint must leave the reader on it.
    page.evaluate("() => document.activeElement?.blur()")
    for _ in range(24):
        page.keyboard.press("Tab")
        if page.evaluate(
            "() => document.activeElement?.classList?.contains('lf-key-more')"
        ):
            break
    expect(page.locator(".lf-key-more")).to_be_focused()
    page.evaluate(RENDERED)
    expect(page.locator(".lf-key-more")).to_be_focused()

    assert errors == []
    page.close()


def test_a_page_at_rest_repaints_the_key_line_only_when_the_state_moves(browser, serve):
    """A repaint that schedules the next one is a loop no surface reports.

    `paintCoreControls` runs inside `paintHere` and writes what the More control
    currently says, `aria-expanded` among it. The runtime watches `open` and
    `aria-expanded` over the whole document, because those two attributes are how both
    spellings of a disclosure keep which way they stand, and it repaints the line for
    either. So the paint delivered its own write back to itself and asked for another
    frame, and the page went on repainting for as long as it was open — every browser
    test on every page paying for it, which is where it showed: the nightly suite ran
    half again as long and the run went over its bound with a fifth of the tests unread.

    Nothing on screen says so, which is why the reading is the page's own frames against
    its own state applications. Every application repaints the line and says so through
    `lf-actions`, the heartbeat's re-application of state the page already holds
    included, so a line that repaints more often than the state moves is repainting for
    a reason the page has not got."""
    page, errors = open_page(browser, serve(NOTED_PAGE, comments=2))
    page.evaluate(
        """() => {
          const probe = { frames: 0, paints: 0, applied: 0 };
          window.__lfProbe = probe;
          document.addEventListener("lf-actions", () => { probe.applied += 1; });
          new MutationObserver(() => { probe.paints += 1; }).observe(
            document.querySelector(".lf-keyline"),
            { attributes: true, childList: true, subtree: true },
          );
          const tick = () => { probe.frames += 1; requestAnimationFrame(tick); };
          requestAnimationFrame(tick);
        }"""
    )
    # The window is the page's own frames rather than a duration: a loop of this shape
    # repaints once per frame whatever the machine's speed, so counting frames is what
    # makes the contrast the same size on a loaded runner as on a desk.
    page.wait_for_function("() => window.__lfProbe.frames >= 90")
    probe = page.evaluate("() => window.__lfProbe")

    assert probe["paints"] <= probe["applied"] + 1, (
        "the key line repainted without the state moving over "
        f"{probe['frames']} frames: {probe}"
    )
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
        page.get_by_role("button", name=re.compile("^Threads")).click()
        expect(page.locator(".lf-panel")).to_be_visible()
        page.locator(control).focus()
        expect(page.locator(".lf-keyline")).to_contain_text("let go")
        page.keyboard.press("Escape")
        assert page.evaluate("() => document.activeElement === document.body")
        expect(page.locator(".lf-keyline")).to_contain_text("close threads")
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
    expect(line).not_to_contain_text("page down")
    expect(line).not_to_contain_text("page up")
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
    expect(line).not_to_contain_text("page down")
    expect(line).not_to_contain_text("page up")
    page.keyboard.press("c")
    expect(page.locator("#note")).to_have_value("c")
    expect(page.locator(".lf-help")).to_be_hidden()
    page.keyboard.press("?")
    expect(page.locator("#note")).to_have_value("c?")
    expect(page.locator(".lf-help")).to_be_hidden()
    assert errors == []
    page.close()


def test_a_label_press_keeps_the_controls_keyboard_standing(browser, serve):
    """Leaf treats a label's native activation as one keyboard standing.

    Chromium moves focus through body between mousedown and native label activation.
    That intermediate state must not repaint focus-derived surfaces. The native click
    and text selection must still work."""
    html = leaf_page(
        "label focus",
        """
<h1 id="frames">Choose a frame</h1>
<lf-decision id="first-question-decision"><h2>Which first frame?</h2>
<lf-options id="first-question" choose>
  <lf-option id="first-frame"><strong>First</strong>
    <label><input id="first" type="radio" name="first-frame">
      <span>first state</span></label>
  </lf-option>
  <lf-option id="neither-first-frame"><strong>Neither</strong></lf-option>
</lf-options></lf-decision>
<lf-decision id="frame-question-decision"><h2>Which next frame?</h2>
<lf-options id="frame-question" choose>
  <lf-option id="after-frame"><strong>After</strong>
    <label id="frame-label"><input id="frame" type="radio" name="frame">
      <span>after state</span></label>
  </lf-option>
  <lf-option id="before-frame"><strong>Before</strong></lf-option>
</lf-options></lf-decision>
""",
    )
    page, errors = open_page(
        browser, serve(html, anchored=[("frames", "Choose a frame")])
    )
    first = page.locator("#first")
    control = page.locator("#frame")
    words = page.locator("#frame-label span")
    first.focus()
    standing = key_line(page)
    assert "let go" in standing
    expect(page.locator("#first-question-decision[data-lf-decision]")).to_have_count(1)

    # A secondary contact does not drive native label activation, so it must not
    # start the logical transaction either.
    page.evaluate(
        """() => {
          const init = {bubbles: true, composed: true, pointerId: 98,
                        pointerType: 'touch', isPrimary: false, button: 0};
          document.querySelector('#frame-label').dispatchEvent(
            new PointerEvent('pointerdown', init)
          );
          document.activeElement.blur();
        }"""
    )
    assert "let go" not in key_line(page)
    page.evaluate(
        """() => dispatchEvent(new PointerEvent('pointerup', {
          bubbles: true, composed: true, pointerId: 98,
          pointerType: 'touch', isPrimary: false, button: 0
        }))"""
    )
    first.focus()
    assert key_line(page) == standing

    bounds = words.bounding_box()
    assert bounds is not None
    middle = (bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] / 2)
    page.mouse.move(*middle)
    page.mouse.down()
    page.evaluate(
        """() => {
          const init = {bubbles: true, composed: true, pointerId: 99,
                        pointerType: 'touch', isPrimary: true, button: 0};
          document.body.dispatchEvent(new PointerEvent('pointerdown', init));
          dispatchEvent(new PointerEvent('pointerup', init));
        }"""
    )
    assert key_line(page) == standing
    held_decision = page.locator("#first-question-decision[data-lf-decision]")
    expect(held_decision).to_have_count(1)
    expect(held_decision).to_have_css("--lf-here-ring", "decision")
    page.mouse.up()
    expect(control).to_be_checked()
    expect(control).to_be_focused()
    expect(page.locator("#frame-question-decision[data-lf-decision]")).to_have_count(1)

    hold_selection(
        page,
        (bounds["x"] + 2, middle[1]),
        (bounds["x"] + bounds["width"] - 2, middle[1]),
        steps=10,
    )
    assert "after state" in page.evaluate("() => getSelection().toString()")
    assert "unselect" in key_line(page)
    page.mouse.up()
    assert "let go" not in key_line(page)

    # A focused thread has a runtime-owned scope outside the generic control register.
    # It reads the same logical focus while the press moves toward the label's control.
    page.evaluate("() => getSelection().removeAllRanges()")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(".lf-threads > .lf-thread")
    thread.focus()
    thread_standing = key_line(page)
    assert "reply" in thread_standing
    bounds = words.bounding_box()
    assert bounds is not None
    page.mouse.move(
        bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] / 2
    )
    page.mouse.down()
    assert key_line(page) == thread_standing
    expect(thread).to_have_css("--lf-here-ring", "thread")
    page.mouse.up()
    assert "reply" not in key_line(page)
    assert errors == []
    page.close()


def test_a_label_press_keeps_the_shortcut_hint_on_the_focused_box(browser, serve):
    """Immediate focus readers share the label transaction with the painted ones."""
    page, errors = open_page(browser, serve(INLINE_PAGE))
    page.locator("#p").click(click_count=3)
    page.locator(".lf-fab").click()
    box = page.locator(".lf-composer textarea")
    label = page.locator(".lf-composer .lf-suggest-row")
    expect(box).to_be_focused()
    expect(label).to_be_visible()
    expect(box).to_have_attribute("placeholder", re.compile(r"(⌘⏎|Ctrl\+⏎)$"))
    hint = box.get_attribute("placeholder")
    assert hint is not None

    bounds = label.bounding_box()
    assert bounds is not None
    page.mouse.move(
        bounds["x"] + bounds["width"] - 2, bounds["y"] + bounds["height"] / 2
    )
    page.mouse.down()
    page.evaluate(RENDERED)
    assert box.get_attribute("placeholder") == hint
    page.keyboard.type("x")
    expect(box).to_have_value("x")
    page.mouse.up()
    expect(label.locator("input")).to_be_checked()
    expect(box).to_have_attribute("placeholder", "Replacement text")

    box.focus()
    expect(box).to_have_attribute("placeholder", re.compile(r"(⌘⏎|Ctrl\+⏎)$"))
    replacement_hint = box.get_attribute("placeholder")
    assert replacement_hint is not None
    text_bounds = label.evaluate(
        """label => {
          const node = [...label.childNodes].find(node => node.nodeType === Node.TEXT_NODE);
          const range = document.createRange();
          range.selectNodeContents(node);
          const box = range.getBoundingClientRect();
          return {x: box.x, y: box.y, width: box.width, height: box.height};
        }"""
    )
    hold_selection(
        page,
        (text_bounds["x"] + 2, text_bounds["y"] + text_bounds["height"] / 2),
        (
            text_bounds["x"] + text_bounds["width"] - 2,
            text_bounds["y"] + text_bounds["height"] / 2,
        ),
        steps=10,
    )
    assert "Suggest replacement text" in page.evaluate(
        "() => getSelection().toString()"
    )
    page.evaluate(RENDERED)
    assert box.get_attribute("placeholder") == replacement_hint
    page.mouse.up()
    expect(box).to_have_attribute("placeholder", "Replacement text")
    assert errors == []
    page.close()


def test_focus_paint_releases_every_text_box_crossed_before_a_frame(browser, serve):
    """A synchronous input sync cannot hide an intermediate focus from repaint."""
    page, errors = open_page(browser, serve(INLINE_PAGE, comments=2))
    page.locator(".lf-threads-toggle").click()
    general = page.locator(".lf-general textarea")
    replies = page.locator(".lf-thread textarea")
    general.focus()
    key_line(page)
    assert re.search(r"(⌘⏎|Ctrl\+⏎)$", general.get_attribute("placeholder"))

    # Cross A -> B (and sync B) -> C in one turn, before the coalesced focus paint.
    replies.evaluate_all(
        """boxes => {
          boxes[0].focus();
          boxes[0].dispatchEvent(new Event('input', {bubbles: true}));
          boxes[1].focus();
        }"""
    )
    key_line(page)
    assert general.get_attribute("placeholder") == "Comment on the page · c"
    assert replies.nth(0).get_attribute("placeholder") == "Reply"
    assert re.search(r"(⌘⏎|Ctrl\+⏎)$", replies.nth(1).get_attribute("placeholder"))
    assert errors == []
    page.close()


def test_the_key_line_names_what_this_press_will_comment_on(browser, serve, other_leaf):
    """A key's word is the meaning it has now, not one wide enough to cover every
    meaning it could have. c opens a box on the selection, on the item a click raised the
    💬 on, or on whatever the reader is standing in — and with none of those in hand goes
    to the threads — yet every one of them read "comment": true of the key and silent
    about the press, so a reader with a paragraph selected and one with nothing selected
    were told the same thing about two different destinations. Both surfaces read the row
    where they paint it, so both say where this press goes; o is the same defect and says
    show or hide rather than both.

    Three of the four here, this page holding nothing to stand on;
    test_c_comments_on_what_the_reader_is_standing_in owns the fourth."""
    page, errors = open_page(browser, serve(TARGETS_PAGE))
    line = page.locator(".lf-keyline")
    help_el = page.locator(".lf-help")

    # Nothing in hand: there is no box to name, so the word is the room c goes to.
    expect(line).to_contain_text("threads")
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(help_el).to_contain_text("Go to the threads")
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
    answer — the edges always among them, every page having a top. Its rows carry the
    complete chord, so no heading has to supply a key the row itself omits."""
    url = serve(NOTED_PAGE)
    d = serve.page_dir
    page, errors = open_page(browser, live_url(url))
    help_el = page.locator(".lf-help")

    # No open threads, one version: the reference names only what a press would do.
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(help_el).to_be_visible()
    # Nothing is selected and the reader is standing nowhere, so c's own row says where
    # the press goes — the word is the press's, not the key's (see the row's neighbour
    # test below). Not "Comment on the page", which is the panel's own c saying what its
    # row does, in its own section: naming that sentence here is answered by the wrong
    # row and says nothing about the page's.
    expect(help_el).to_contain_text("Go to the threads")
    # The chord's section stands on every page — the edges need no list — but holds
    # no row for a list this page hasn't got. Each row says the whole press from the
    # standing page rather than asking its heading to supply the first g.
    expect(help_el.get_by_role("heading", name="Go to", exact=True)).to_be_visible()
    expect(
        help_el.locator("tr", has_text="top of the page").locator("kbd")
    ).to_have_text("g g")
    expect(
        help_el.locator("tr", has_text="bottom of the page").locator("kbd")
    ).to_have_text("g G")
    expect(help_el).not_to_contain_text("open comment's reply box")
    # And no link scope: this page holds none, while the machine's own tray is full of
    # them — a scope asked about the document at large was had by every page there is.
    expect(help_el).not_to_contain_text("On a link")
    expect(help_el).not_to_contain_text("Next open thread")
    expect(help_el).not_to_contain_text("Previous open thread")
    expect(help_el).not_to_contain_text("On a focused thread")
    expect(help_el).not_to_contain_text("waiting on you for")
    # A first version has a useful chooser but no neighbouring version to walk. Escape is
    # the popover's native dismissal and therefore is not a Leaf shortcut row.
    expect(help_el).to_contain_text("The versions, and what each one changed")
    expect(help_el).not_to_contain_text("Close the versions menu")
    expect(help_el).not_to_contain_text("Previous version")
    expect(help_el).not_to_contain_text("Next version")
    page.keyboard.press("Escape")
    expect(help_el).to_be_hidden()

    # The dispatcher asks the same declaration: neither half of the pair runs while
    # there is no thread to walk.
    page.keyboard.press("t")
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-panel")).to_be_hidden()
    line = page.locator(".lf-keyline")
    expect(line).not_to_contain_text("t / T")

    # Threads arrive, making both the category walk and the Threads panel useful.
    for text in ["A thread.", "Another."]:
        events_model.append_event(
            d, {"kind": "comment", "author": "user", "revision": 1, "text": text}
        )
    told(page)
    expect(page.locator(".lf-thread")).to_have_count(2)
    # The key line repaints on the same render that made them live — no focus
    # change to lean on, so the repaint is the thread render's own.
    expect(line).to_contain_text("threads")
    page.keyboard.press("?")
    expect(
        help_el.locator("tr", has_text="Go to the Threads panel").locator("kbd")
    ).to_have_text("g t")
    expect(help_el).not_to_contain_text("link on screen")
    expect(help_el).not_to_contain_text("waiting on you for")
    expect(help_el).to_contain_text("Next open thread")
    expect(help_el).to_contain_text("Previous open thread")
    expect(
        help_el.locator("tr", has_text="Next open thread").locator("kbd")
    ).to_have_text("t")
    expect(
        help_el.locator("tr", has_text="Previous open thread").locator("kbd")
    ).to_have_text("T")
    expect(help_el).to_contain_text("On a focused thread")
    # Still one version, so there is no version walk to advertise.
    expect(help_el).not_to_contain_text("Close the versions menu")
    expect(help_el).not_to_contain_text("Previous version")
    expect(help_el).not_to_contain_text("Next version")
    page.keyboard.press("Escape")

    # A v2 lands and the live page follows it; on v2 the menu's own keys are
    # live, having a list to walk and a base to walk onto.
    (d / "versions" / "v2.html").write_text(NOTED_PAGE)
    stamp_version_file(d, 2, "two")
    wait_for_revision(page, 2)
    expect(page.locator('.lf-version-diff[data-lf-version="1"]')).to_have_count(1)
    expect(page.locator(".lf-version-menu")).to_have_attribute(
        "aria-keyshortcuts", "ArrowUp ArrowDown Enter Space v"
    )
    page.keyboard.press("?")
    expect(help_el).to_contain_text("In the versions menu")
    expect(help_el).to_contain_text("Previous version")
    expect(help_el).to_contain_text("Next version")
    page.keyboard.press("Escape")

    # A resolved thread stays focusable after the last open one is gone, and the
    # scene branch that restates the t/T row over it asks the same liveness.
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
    expect(line).to_contain_text("close threads")
    expect(line).not_to_contain_text("t / T")

    # And no disclosure scope, with the panel's own <details> standing open beside the
    # reader. A capability is what they can reach from where the scope holds, and this box
    # is the chrome's — it declares the keys it answers itself. Asked of the document at
    # large, the scope arrives on every page that has ever had a comment resolved.
    expect(page.locator(".lf-details[open]")).to_have_count(1)
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(help_el).to_be_visible()
    expect(help_el).not_to_contain_text("On a disclosure")
    page.keyboard.press("Escape")
    assert errors == []
    page.close()


def test_the_resolve_key_changes_the_focused_threads_resolution(browser, serve):
    """x changes the resolution of the thread the reader is standing on.

    It resolves the thread t/T landed on through the button's own press, so
    focus lands where the button already sends it — on the thread that takes the
    resolved one's place. On a resolved thread the same state key reopens it, while
    Enter performs that thread's available primary action: reply when open and reopen
    when resolved."""
    url = serve(NOTED_PAGE)
    d = serve.page_dir

    def comment(text):
        return events_model.append_event(
            d, {"kind": "comment", "author": "user", "revision": 1, "text": text}
        )["id"]

    c1 = comment("First thought.")
    c2 = comment("Second thought.")
    page, errors = open_page(browser, url)
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 2")
    line = page.locator(".lf-keyline")

    def tab_to(target, limit=40):
        for _ in range(limit):
            page.keyboard.press("Tab")
            if target.evaluate("node => node === document.activeElement"):
                return
        raise AssertionError("Tab did not reach the expected control")

    # At page scope nothing promises x — its target is the focused thread, and
    # none is — while the overlay teaches the capability, scope in its words.
    expect(line).not_to_contain_text("resolve")
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.locator(".lf-help")).to_contain_text("On a focused thread")
    expect(page.locator(".lf-help")).to_contain_text("Resolve it")
    focused_section = page.locator(".lf-help-section").filter(
        has=page.get_by_role("heading", name="On a focused thread", exact=True)
    )
    expect(focused_section.get_by_text("Resolve it", exact=True)).to_have_count(1)
    page.keyboard.press("Escape")

    # t lands on the first thread and the line offers resolve; x takes it, and
    # focus lands on the thread now holding the resolved one's place, so t/T
    # and a second x walk on from there.
    page.keyboard.press("t")
    expect(page.locator(f'.lf-thread[data-id="{c1}"]')).to_be_focused()
    expect(line).to_contain_text("resolve")
    page.keyboard.press("x")
    expect(page.locator(".lf-details summary")).to_have_text("Resolved (1)")
    expect(page.locator(f'.lf-thread[data-id="{c2}"]')).to_be_focused()
    expect(line).to_contain_text("resolve")

    # The native disclosure and Reopen control put a resolved thread in the ordinary Tab
    # journey. Enter is the primary route and the same x state key is available there.
    expect(page.locator(f'.lf-details .lf-thread[data-id="{c1}"]')).to_have_count(1)
    summary = page.locator(".lf-details summary")
    tab_to(summary)
    page.keyboard.press("Enter")
    resolved = page.locator(f'.lf-details .lf-thread[data-id="{c1}"]')
    reopen_control = resolved.get_by_role("button", name="Reopen")
    tab_to(reopen_control)
    expect(reopen_control).to_be_focused()
    expect(line).to_contain_text("reopen")
    page.keyboard.press("Enter")
    round_trip(page)
    reopened = page.locator(f'.lf-threads > .lf-thread[data-id="{c1}"]')
    expect(reopened).to_be_focused()
    expect(line).to_contain_text("reply")

    # The state key is reversible from either visible state control too: Tab to Resolve,
    # resolve with x, then Tab to Reopen and use the same x to reverse it.
    resolve_control = reopened.get_by_role("button", name="Resolve")
    tab_to(resolve_control)
    expect(resolve_control).to_be_focused()
    expect(line).to_contain_text("resolve")
    resolve_control.evaluate("button => button.disabled = true")
    page.evaluate(
        "async () => (await import('/runtime/keyboard/scopes.js')).paintKeys()"
    )
    assert resolve_control.get_attribute("aria-keyshortcuts") is None
    expect(line).not_to_contain_text("resolve")
    resolve_control.evaluate("button => button.disabled = false")
    page.evaluate(
        "async () => (await import('/runtime/keyboard/scopes.js')).paintKeys()"
    )
    resolve_control.focus()
    page.keyboard.press("x")
    round_trip(page)
    expect(page.locator(".lf-details summary")).to_have_text("Resolved (1)")
    resolved = page.locator(f'.lf-details .lf-thread[data-id="{c1}"]')
    reopen_control = resolved.get_by_role("button", name="Reopen")
    tab_to(reopen_control)
    expect(reopen_control).to_be_focused()
    page.keyboard.press("x")
    round_trip(page)
    expect(page.locator(f'.lf-threads > .lf-thread[data-id="{c1}"]')).to_be_focused()
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
    events_model.append_event(
        serve.page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "A thread."},
    )
    page, errors = open_page(browser, url)
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 1")
    page.keyboard.press("c")  # panel open, so the old second action would show
    expect(page.locator(".lf-panel")).to_be_visible()

    page.locator(".lf-draft-controls .lf-draft-pencil").click()
    ta = page.locator("lf-draft textarea")
    expect(ta).to_be_focused()
    ta.fill("Ship it — but louder.")
    page.keyboard.press("Escape")
    expect(ta).to_have_count(0)  # the editor closed…
    expect(page.locator(".lf-panel")).to_be_visible()  # …and only the editor
    # The edit was set aside, not discarded: reopening resumes it.
    page.locator(".lf-draft-controls .lf-draft-pencil").click()
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
    # Asked of the armed chip, which is the chord itself saying it is waiting for the
    # second key. The word "comments" used to stand for that, being one of the addresses
    # an armed chord lists — but the page's own c says it too now (it goes to the panel
    # rather than into its box), so the word is on the resting line either way and the
    # proxy would pass over an armed chord.
    expect(page.locator(".lf-keyline kbd.armed")).to_have_count(0)
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

    Where they are standing is the unanswered decision first, because that is what the page
    has already told them: markHere rings the whole ask when d/D lands on its control.
    Below a decision it is the innermost
    item, which is the aim's own reading — so the link the walk stands on speaks for
    the paragraph holding it, no id of its own being what an anchor needs.

    One box either way: `openOnItem` writes `{section: item.id}`, which is the anchor a
    widget's own conversation seat collects, so a remark made here lands in that seat's
    conversation rather than beside it. Reaching for the seat directly instead was five
    questions — escaping an author's id, whether the box can take focus, which box when
    the seat holds several, what design mode files, where the reader already stood — for
    a focus landing.

    The control is the same press from the same page with the reader standing nowhere in
    it, where `c` opens no box at all and goes to the comments. Without it a green here
    would follow just as well from a composer that opened on everything.

    Focus is dropped between the phases rather than backed out of, because each press
    lands the reader in a box: the typing scope owns the letter there, and the `g`
    opening the next address would be a character in the last one's draft."""
    page, errors = open_page(browser, serve(WHERE_I_STAND_PAGE))
    line = page.locator(".lf-keyline")

    def drop():
        page.evaluate("() => document.activeElement?.blur()")

    # Standing nowhere in the page: no box is named, so the press is the room the boxes
    # are in. Read against every phase below, which is what makes those mean anything.
    expect(line).not_to_contain_text("comment on the")
    page.keyboard.press("c")
    expect(page.locator(".lf-threads")).to_be_focused()
    drop()

    # A decision: the composer opens on the question rather than on the option the
    # walk happens to stand the reader on, and rather than on the page.
    page.keyboard.press("d")
    expect(page.locator("#shape-decision")).to_have_attribute("data-lf-decision", "1")
    expect(line).to_contain_text("comment on the decision")
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-composer")).to_contain_text("decision")
    drop()

    # A settled group: not a decision at all, and the conversation seat it still holds is
    # inside `hidden="until-found"`, so a press that reached into the seat focused a box
    # that cannot take focus and did nothing at all. Named by its own words rather than by
    # "options", which the composer standing open from the phase above already says — an
    # assertion true before the press is no assertion about the press.
    page.locator("#settled .lf-settled").focus()
    expect(line).to_contain_text("comment on the options")
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_contain_text("Decided last week")
    drop()

    # A decision with no seat: the composer, anchored on the decision rather than on the page.
    page.keyboard.press("d")
    expect(page.locator("#sug-window")).to_have_attribute("data-lf-decision", "1")
    expect(line).to_contain_text("comment on the rewrite")
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-composer")).to_contain_text("rewrite")
    drop()

    # A link inside a question, open and settled: the same markup, and the same answer.
    # Standing in a decision is not working one — a reader who addressed a link has named
    # something more particular than the question around it, and answering the question
    # there both overrode what they named and made the reply turn on whether that question
    # happened to be open. The settled one is the contrast that shows it was the openness
    # doing it: it always said "option", and the open one used to say "options".
    for expected_id, keys in (("sh-steel", "gh2"), ("st-keep", "gh3")):
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
    for key in "gh1":
        page.keyboard.press(key)
    expect(page.locator("#p1 a")).to_be_focused()
    expect(line).to_contain_text("comment on the paragraph")
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_contain_text("paragraph")

    assert errors == []
    page.close()


def test_the_ring_holds_on_a_seat_the_agent_has_still_to_answer(browser, serve):
    """Where the reader is standing and what the reader still owes are two facts, and a
    widget mid-conversation with the agent is where they part. Its seat holds the words
    the reader just wrote, its pick is unmade and its controls are live, and it has left
    the banner and the tray because the next word there is the agent's — but the reader
    is standing in it all the same, and it is still the question they are working.

    Read off the reader's list, both the ring and `c` went with the count: the moment the
    remark was sent the ring left from under the reader, and `c` slid from the seat they
    were writing in down to whichever option their focus rested on. That is a different
    conversation, not a shorter way into the same one — `{section: "shape"}` is the seat's
    own anchor and `{section: "sh-steel"}` is not — so the next line of a remark landed
    somewhere the first line was not. The agent's reply moved both back. Nothing the
    reader did moved either, which is the whole of the complaint; the reply phase here is
    what says the ring has stopped tracking the count rather than merely tracking it late.

    A picked group is the control on the other side. It is answered, so it is off both
    readings and must stay off: the switch is about a seat the reader is mid-sentence in,
    not about reopening what a pick has closed."""
    url = serve(
        leaf_page(
            "mid-sentence",
            """
<h1 id="t">Mid-sentence</h1>
<lf-decision id="shape-decision"><h2>Which material?</h2>
<lf-options id="shape" choose>
  <lf-option id="sh-steel"><strong>Steel</strong> Galvanised, drop-in.</lf-option>
  <lf-option id="sh-cedar"><strong>Cedar</strong> Cheap; needs sealing.</lf-option>
</lf-options></lf-decision>
<lf-decision id="picked-decision"><h2>Should we keep it?</h2>
<lf-options id="picked" choose>
  <lf-option id="pk-keep" chosen><strong>Keep it</strong> Settled by a pick.</lf-option>
  <lf-option id="pk-drop"><strong>Drop it</strong> The alternative.</lf-option>
</lf-options></lf-decision>
<p id="p2">A passage carrying
<lf-suggestion id="sug-window">
  <lf-old>Refill every feeder each morning.</lf-old>
  <lf-new>Refill when the camera shows it half-empty.</lf-new>
</lf-suggestion></p>
""",
        )
    )
    d = serve.page_dir
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Steel, unless the sealing is quick?",
            "anchor": {"section": "shape"},
        },
    )

    page, errors = open_page(browser, url)
    line = page.locator(".lf-keyline")
    decisions = page.locator(".lf-decisions")

    # The premise, from the reader's list itself: the group has left it, the picked group
    # was never on it, and the suggestion is what remains to be counted.
    expect(decisions).to_have_text("Decisions (1)")
    decisions.click()
    expect(page.locator("button.lf-decisions-row")).to_have_count(1)
    # Which row, not just how many: one row is also what a build listing the picked group
    # and dropping the suggestion would show.
    expect(page.locator('.lf-decisions-row[data-lf-at="sug-window"]')).to_have_count(1)

    # The reader is standing in it all the same — and first with the tray still open, the
    # one state where the ring has a second surface to reach for and this decision has no row
    # on it. `markHere` looks its row up by id and paints the row too; there is none, and
    # the scroll that brings a row into view is the tray's own reading. So the decision wears
    # the ring alone, and the tray goes on listing what the reader owes rather than
    # gaining a row for where they happen to be standing.
    page.locator("#shape .lf-pick").first.focus()
    expect(page.locator("#shape-decision")).to_have_attribute("data-lf-decision", "1")
    expect(page.locator("button.lf-decisions-row")).to_have_count(1)
    assert page.locator(".lf-decisions-row[data-lf-decision]").count() == 0, (
        "the tray drew a here-ring on a row for a decision it does not list"
    )
    page.evaluate("() => document.activeElement?.blur()")
    decisions.click()

    # And with it shut, which is every other reading below.
    page.locator("#shape .lf-pick").first.focus()
    expect(page.locator("#shape-decision")).to_have_attribute("data-lf-decision", "1")
    expect(line).to_contain_text("comment on the decision")

    # Answering hands the question back, and the count moves while the ring does not.
    # Focus is not touched again from here, so the ring read below is the one painted
    # above: blurring and coming back would re-derive it and repeat the phase instead of
    # measuring that it stayed through the news.
    #
    # The source is the reader's again once the conversation in its answer control has
    # been answered.
    for root in [
        e["id"] for e in events_model.read_events(d) if e.get("kind") == "comment"
    ]:
        events_model.append_event(
            d,
            {
                "kind": "reply",
                "author": "claude",
                "revision": 1,
                "parent": root,
                "text": "Sealing is an afternoon.",
            },
        )
    told(page)
    expect(decisions).to_have_text("Decisions (2)")
    expect(page.locator("#shape .lf-pick").first).to_be_focused()
    expect(page.locator("#shape-decision")).to_have_attribute("data-lf-decision", "1")
    expect(line).to_contain_text("comment on the decision")
    page.evaluate("() => document.activeElement?.blur()")

    # The picked group is the control on the other side: answered, so off both readings,
    # and the switch leaves it there. Read through the key line, because `markHere` paints
    # inside `paintHere`'s frame — an absence read in the same round trip as the focus is
    # the frame before the paint, and stays green while a ring lands here a frame later.
    # The word is the other half of the same fact: with `standingIn` null the reading falls
    # through to the innermost item, which from a pick is the option and not the question.
    page.locator("#picked .lf-pick").first.focus()
    expect(line).to_contain_text(re.compile(r"comment on the option(?!s)"))
    assert page.locator("[data-lf-decision]").count() == 0, (
        "an answered group wears the ring the switch was not about"
    )

    assert errors == []
    page.close()


def test_c_in_a_thread_reaches_that_threads_own_box(browser, serve):
    """The panel's open list is the one part of the chrome that holds a conversation of
    its own, so a press meaning "say something about this" belongs to that box rather
    than to the page the panel stands over. `conversationBox` states the same rule from
    the other side when it declines to seat a widget standing inside a thread, and the
    asks and the `d`/`D` walk include the ones an agent sent — without this the same
    question answered one way on the page and another in the panel.

    A resolved thread is the case that has to be asked separately, and the reason this
    test exists at all: it is built by the same `threadNode` and wears the same class,
    under the Resolved disclosure, where it keeps a tab stop and a Reopen button. Reading
    the class alone put the reader in a thread whose reply box is not there, and the press
    died on the null with the panel's own `c` never reached. Whether there is a box is what
    tells them apart — `standingConversation` asks for one rather than for the class — so
    the resolved thread falls through to the general box, which is the honest answer for a
    thread with no box of its own to offer."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    live = panel_comment(d, "Six weeks reads long.", {"section": "lede"})
    gone = panel_comment(d, "Settled already.", {"section": "how-cap"})
    events_model.append_event(d, {"kind": "resolve", "author": "user", "parent": gone})

    page, errors = open_page(browser, url)
    line = page.locator(".lf-keyline")

    # The control: standing nowhere, the press names no box and goes to the list.
    expect(line).not_to_contain_text("comment on the")
    page.keyboard.press("c")
    expect(page.locator(".lf-threads")).to_be_focused()

    # Standing in the open thread, it means that thread's reply box. `t` walks on from
    # where the press above left the reader, no backing out of a box first.
    page.keyboard.press("t")
    expect(page.locator(f'.lf-thread[data-id="{live}"]')).to_be_focused()
    expect(line).to_contain_text("comment on the thread")
    page.keyboard.press("c")
    expect(
        page.locator(f'.lf-thread[data-id="{live}"] > .lf-compose textarea')
    ).to_be_focused()

    # And Esc gives that press back: the thread, then the panel. In the panel the old
    # class-only reading and the new climb agree, so this is the consistency half rather
    # than the gate — test_c_in_a_seated_conversation_reaches_the_thread_it_is_in is what
    # actually goes red if the climb regresses, the page being where they diverge.
    expect(line).to_contain_text("back to thread")
    page.keyboard.press("Escape")
    expect(page.locator(f'.lf-thread[data-id="{live}"]')).to_be_focused()
    expect(line).to_contain_text("close threads")
    page.evaluate("() => document.activeElement?.blur()")

    # A resolved thread has no box, so the press falls through to the general box rather
    # than reaching for one that is not there. The panel's own row answers it, saying so in
    # the panel's words; what matters is that the thread is not named, which is the phase
    # above's answer and would be the wrong one here.
    page.locator(".lf-details > summary").click()
    page.locator(f'.lf-details .lf-thread[data-id="{gone}"]').focus()
    expect(line).not_to_contain_text("comment on the thread")
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
    conversation.

    The agent has answered both remarks, so each thread here is a whole exchange. Nothing
    in this test turns on that: `standingIn` reads the unanswered decisions rather than the
    reader's list, so the group is what the reader is standing in whichever way the seat's
    conversations are facing, and this control says the same thing before a reply and
    after one. test_the_ring_holds_on_a_seat_the_agent_has_still_to_answer is what holds
    that, and it is why the replies are the exchange's shape and not a premise."""
    url = serve(
        leaf_page(
            "seated",
            """
<h1 id="t">Seated</h1>
<lf-decision id="shape-decision"><h2>Which material?</h2>
<lf-options id="shape" choose>
  <lf-option id="sh-steel"><strong>Steel</strong> Galvanised, drop-in.</lf-option>
  <lf-option id="sh-cedar"><strong>Cedar</strong> Cheap; needs sealing.</lf-option>
</lf-options></lf-decision>
""",
        )
    )
    d = serve.page_dir
    said = []
    for text in ("First remark.", "Second remark."):
        events_model.append_event(
            d,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": text,
                "anchor": {"section": "shape"},
            },
        )
        said.append(events_model.read_events(d)[-1]["id"])
        events_model.append_event(
            d,
            {
                "kind": "reply",
                "author": "claude",
                "revision": 1,
                "parent": said[-1],
                "text": "Noted.",
            },
        )

    page, errors = open_page(browser, url)
    line = page.locator(".lf-keyline")
    threads = page.locator(".lf-conversation-thread")
    expect(threads).to_have_count(2)

    # The control: standing on the widget, not in either thread.
    page.locator("#shape .lf-pick").first.focus()
    expect(line).to_contain_text("comment on the decision")
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

    # And Esc hands back the press that got them there, which is the keyboard-is-a-stack
    # rule read on the page rather than in the panel. The box asked for `.lf-thread` and
    # the panel alone, so out here the rung fell through to the page's own "let go": one
    # press in from the thread, one press out to body, with the thread they had been
    # standing in two feet away and no key back to it. Both ends read one climb now, so
    # the word going in ("comment on the thread") and the word coming out are about the
    # same element.
    expect(line).to_contain_text("back to thread")
    page.keyboard.press("Escape")
    expect(second).to_be_focused()
    # One rung, not two: the page's own way out is the press after this one.
    expect(line).to_contain_text("let go")
    page.keyboard.press("Escape")
    assert page.evaluate("() => document.activeElement === document.body")

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


def test_c_reaches_the_panel_and_c_again_the_box(browser, serve):
    """c goes inward and never back out. It doubled as the panel's collapse once,
    which left the box with no shortcut exactly while the panel stood open: the press
    that promised "comment" answered "close". Collapse is the ladder's — Esc from the
    list closes the panel, the rung the key-line test walks — so both stay reachable
    without one key meaning two things.

    Where the first press lands is the list rather than the box, because the box is the
    one place in the panel where the panel's own keys are all shadowed: the typing scope
    claims a letter before the panel's scope can see it, so a reader who pressed c to
    reach the comments had to press Escape before w or / would answer. The same letter
    twice is the same intent one scope further in, and the third press below is what says
    the second one is about the scope the reader is standing in rather than about the
    panel being shut."""
    page, errors = open_page(browser, serve(NOTED_PAGE))
    page.keyboard.press("c")  # closed: opens the panel and stands on its list
    expect(page.locator(".lf-threads")).to_be_focused()
    page.keyboard.press("c")  # standing in the panel: into the box
    expect(page.locator(".lf-general textarea")).to_be_focused()
    page.keyboard.press("Escape")  # back out to the list, focus outside any box
    expect(page.locator(".lf-threads")).to_be_focused()
    page.keyboard.press("c")  # open, and still the box — never the collapse
    expect(page.locator(".lf-general textarea")).to_be_focused()
    expect(page.locator(".lf-panel")).to_have_class(re.compile("open"))
    assert errors == []
    page.close()


def test_the_panels_own_c_answers_a_page_whose_log_has_not_arrived(browser, serve):
    """A page whose first poll cannot reach the server is a page the reader still writes
    on: the general box stands, its placeholder names the key that reaches it, and the
    banner says only that a comment will not send yet. What it has not got is a thread
    list, so the panel's other two keys — narrow and find — are dead, and the scope used
    to say that for all three at once.

    Both presses, because one of them is the whole defect: `c` takes the reader to the
    list, and with the panel's own row out of the stack the second `c` was the page's
    again, which lands focus where it already is. The key line went on offering the box
    while no press could reach it, and there is no third key to try.

    Offline rather than mid-load, because it is the state that stays: a loading page
    answers a moment later, and a page whose server has stopped is where a reader sits."""
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    errors = watched(page)
    page.route("**/api/state*", refuse)
    try:
        page.goto(serve(NOTED_PAGE), wait_until="load")
        page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
        expect(page.locator(".lf-status-text")).to_have_text(
            "Server offline — reconnecting. Keep this page open so pending changes can send."
        )

        page.keyboard.press("c")
        expect(page.locator(".lf-threads")).to_be_focused()
        page.keyboard.press("c")
        expect(page.locator(".lf-general textarea")).to_be_focused()

        # The two the missing list really does take away, so the scope is not simply
        # live for everything: a green above has to be about `c` and not about the
        # guard having been dropped altogether.
        page.keyboard.press("Escape")
        expect(page.locator(".lf-threads")).to_be_focused()
        line = page.locator(".lf-keyline")
        expect(line).not_to_contain_text("waiting on you")
        expect(line).not_to_contain_text("find")

        assert errors == []
    finally:
        page.close()
