"""Where an open margin thread card stands beside its target, and how it holds still
through news, presses, reflows and scrolls, panes included."""

import re
from datetime import datetime, timedelta

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import OBLIGATION_PAGE, PANEL_PAGE, panel_comment
from render_harness import (
    LONG_PAGE,
    expect_preview_words,
    holding,
    leaf_page,
    margins_laid_out,
    open_page,
    resized,
    scroll_settled,
    scroll_writes,
    select,
    sending,
    told,
)

from browser.margin import (
    ACTION_ON_OBLIGATION,
    COMMENT_ON_OBLIGATION,
    LONG_THREAD_ROOT,
    PARAGRAPH_ON_OBLIGATION,
    WORDS_RIGHT,
)
from browser.threads import append_agent_reply
from leaf.agents import thread as thread_model
from leaf.log import event_log
from leaf.source.render_checks import rendered
from leaf_dev.browser import text_field
from leaf_dev.example_data import named_source

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_thread_card_is_unseen_until_its_first_placement_lands(browser, serve):
    """An unplaced card is unseen; switching and closing retire its pending work."""
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    held = []
    context.route("**/vendor/floating-ui.esm.js", lambda route: held.append(route))
    page = open_page(
        browser,
        serve(
            OBLIGATION_PAGE,
            events=[
                COMMENT_ON_OBLIGATION,
                {
                    **COMMENT_ON_OBLIGATION,
                    "text": "Check the tools separately.",
                    "anchor": {"section": "tools"},
                },
            ],
        ),
        context=context,
        upgraded=False,
    )
    preview = page.locator(".lf-margin-preview")
    try:
        holding(page, held, 1, "the positioning module")
        first = page.locator('[data-lf-margin-for="bracket"] .lf-margin-marker')
        second = page.locator('[data-lf-margin-for="tools"] .lf-margin-marker')
        first.click()
        expect(preview).not_to_have_attribute("hidden", "")
        expect(preview).to_have_css("opacity", "0")
        expect(preview).to_have_css("pointer-events", "none")

        second.click()
        expect(preview).to_contain_text("Check the tools separately.")
        page.keyboard.press("Escape")
        expect(preview).to_be_hidden()
        page.locator(".lf-fp-leaf").focus()

        held.pop(0).continue_()
        rendered(page)
        expect(preview).to_be_hidden()
        expect(page.locator(".lf-fp-leaf")).to_be_focused()
        expect(preview).not_to_have_attribute("data-lf-thread-placement")

        first.click()
        expect(preview).to_have_attribute("data-lf-thread-placement", re.compile(r".+"))
        expect(preview).to_have_css("opacity", "1")
        expect(preview).to_have_css("pointer-events", "auto")
    finally:
        for route in held:
            route.continue_()
        context.unroute_all(behavior="wait")


@pytest.mark.parametrize("width", [1440, 2400])
def test_a_margin_card_clears_its_row_without_sacrificing_message_width(
    browser, serve, width
):
    """A card clears its margin row only where the row has room for the measure it
    may widen to, and otherwise stands beside the words. Either way a short message
    keeps it at the least width, or the window's room where that is narrower."""
    page = open_page(browser, serve(OBLIGATION_PAGE, events=[PARAGRAPH_ON_OBLIGATION]))
    resized(page, width, 900)
    page.locator('.lf-margin-marker[data-lf-kinds="comment"]').click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_have_attribute("data-lf-thread-placement", re.compile(r".+"))
    rendered(page)
    geometry = page.evaluate(
        """async () => {
          const {COMMENT_GAP, markRoom, subjectGap} = await window.__lfOverlayApi();
          const controls = document.querySelector('[data-lf-kinds="comment"]')
            .closest('[data-lf-margin-for]').getBoundingClientRect();
          const subject = document.getElementById('bracket');
          const room = markRoom(subject, subject.getBoundingClientRect(), COMMENT_GAP);
          const card = document.querySelector('.lf-margin-preview');
          const box = card.getBoundingClientRect();
          return {controlsRight: controls.right, cardLeft: box.left,
                  cardRight: box.right, viewport: innerWidth,
                  gap: subjectGap(room, 'right'),
                  preferred: parseFloat(getComputedStyle(card)
                    .getPropertyValue('--lf-thread-card')),
                  minimum: parseFloat(getComputedStyle(card)
                    .getPropertyValue('--lf-thread-card-min'))};
        }"""
    )
    past = (
        geometry["viewport"] - 8 - (geometry["controlsRight"] + geometry["gap"])
        >= geometry["preferred"]
    )
    assert past == (width == 2400), geometry
    assert geometry["cardLeft"] == pytest.approx(
        (geometry["controlsRight"] if past else page.evaluate(WORDS_RIGHT))
        + geometry["gap"],
        abs=0.5,
    ), geometry
    assert geometry["cardRight"] == pytest.approx(
        min(geometry["viewport"] - 8, geometry["cardLeft"] + geometry["minimum"]),
        abs=0.5,
    ), geometry


PICK_UNDER_A_CARD = leaf_page(
    "Pick under a card",
    """
<h1 id="title">Pick under a card</h1>
<lf-group id="ask" label="What should a phone's one-row banner hold?">
  <h3 id="ask-h">What should a phone's one-row banner hold?</h3>
  <lf-options id="choice">
    <lf-option id="row" label="Status in words"><strong>Status in words</strong> The status keeps its words
    on the row, cut short with an ellipsis where the sentence runs long.</lf-option>
    <lf-option id="two" label="Keep two rows"><strong>Keep two rows</strong> The status keeps its
    sentence.</lf-option>
  </lf-options>
</lf-group>
""",
)


def test_a_card_on_a_widget_stands_its_gap_past_the_ring_round_its_decision(
    browser, serve
):
    """The options' own ring stands on their frame, and the ring round the decision
    they fill, which shows while the user stands in it, stands past the decision's
    padding: the card stands its gap past that ring rather than on it, whether or not
    the ring shows yet."""
    decision = leaf_page(
        "Decision ring",
        """
<h1 id="title">Decision ring</h1>
<lf-group id="ask" label="Which banner?" style="padding: 2px">
  <lf-options id="choice">
    <lf-option id="row" label="Status in words">Status in words.</lf-option>
    <lf-option id="two" label="Keep two rows">Keep two rows.</lf-option>
  </lf-options>
</lf-group>
""",
    )
    comment = {
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "text": "Does the banner wrap?",
        "anchor": {"section": "choice"},
    }
    page = open_page(browser, serve(decision, events=[comment]))
    resized(page, 1440, 900)
    page.locator('[data-lf-margin-for="choice"] .lf-margin-marker').click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_have_attribute("data-lf-thread-placement", re.compile(r".+"))
    rendered(page)
    clear = page.evaluate(
        """() => {
          const ask = document.getElementById('ask');
          const room = parseFloat(getComputedStyle(ask).getPropertyValue('--lf-band-room'));
          const box = ask.getBoundingClientRect();
          const card = document.querySelector('.lf-margin-preview').getBoundingClientRect();
          return Math.max(card.left - (box.right + room), (box.left - room) - card.right,
                          card.top - (box.bottom + room), (box.top - room) - card.bottom);
        }"""
    )
    assert clear == pytest.approx(8, abs=0.5)


def test_a_pick_under_an_open_card_leaves_the_card_where_it_stands(browser, serve):
    """The pick's receipt stands on the option group, whose top is level with the first
    option's, and it was seated above the option's thread row, pushing that row and the
    card standing on it down under the reader."""
    root = {**LONG_THREAD_ROOT, "anchor": {"section": "row"}}
    page = open_page(browser, serve(PICK_UNDER_A_CARD, events=[root]))
    page.emulate_media(reduced_motion="reduce")
    resized(page, 1400, 900)
    thread = page.locator('[data-lf-margin-for="row"]')
    thread.locator(".lf-margin-marker").click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    rendered(page)
    where = "node => node.getBoundingClientRect().toJSON()"
    card, row = preview.evaluate(where), thread.evaluate(where)
    with sending(page, "the pick"):
        page.locator("#row").click(position={"x": 20, "y": 10})
    expect(
        page.locator('[data-lf-margin-for="choice"] .lf-margin-marker')
    ).to_have_attribute("aria-label", re.compile(r"^Queued for Claude\b"))
    for _ in range(2):
        rendered(page)
        assert preview.evaluate(where) == card
        assert thread.evaluate(where) == row
        # A later pass, which any repaint of the margin brings, moves nothing either.
        margins_laid_out(page)


def test_a_row_arriving_takes_the_room_below_the_markers_already_seated(browser, serve):
    """A pick's receipt is news to the thread marker beside the options: it lands in the
    room below that marker rather than seating itself first, from the top, and pushing
    the marker out from beside the option the user may press next."""
    root = {**LONG_THREAD_ROOT, "anchor": {"section": "row"}}
    page = open_page(browser, serve(PICK_UNDER_A_CARD, events=[root]))
    resized(page, 1400, 900)
    rendered(page)
    thread = page.locator('[data-lf-margin-for="row"]')
    where = "node => node.getBoundingClientRect().toJSON()"
    row = thread.evaluate(where)
    with sending(page, "the pick"):
        page.locator("#two").click(position={"x": 20, "y": 10})
    receipt = page.locator('[data-lf-margin-for="choice"]')
    expect(receipt.locator(".lf-margin-marker")).to_have_attribute(
        "aria-label", re.compile(r"^Queued for Claude\b")
    )
    rendered(page)
    assert thread.evaluate(where) == row
    assert receipt.evaluate(where)["top"] >= row["bottom"]
    stands = receipt.evaluate(where)
    # A later pass, which any repaint of the margin brings, moves neither, and nor does
    # the receipt being held where it stands.
    receipt.locator(".lf-margin-marker").hover()
    margins_laid_out(page)
    rendered(page)
    assert thread.evaluate(where) == row
    assert receipt.evaluate(where) == stands


# Each visible message head's time, where it says one, against what could cut it: its
# own box, the metadata it stands in and the head, and each part it shows, which cuts
# its own words; and those parts, its day and its clock, where a time too narrow for
# both drops its clock below its one line.
TIMES_WHOLE = """card => [...card.querySelectorAll('.lf-msg-head')]
  .filter((head) => head.checkVisibility() && head.querySelector('time'))
  .map((head) => {
    const time = head.querySelector('time');
    const box = time.getBoundingClientRect();
    const shown = [...time.children]
      .filter((part) => part.getBoundingClientRect().top < box.bottom - 0.5);
    return {
      text: time.textContent,
      whole: time.scrollWidth <= time.clientWidth &&
        shown.every((part) => part.scrollWidth <= part.clientWidth) &&
        box.right <= time.parentElement.getBoundingClientRect().right + 0.5 &&
        box.right <= head.getBoundingClientRect().right + 0.5,
      shown: shown.map((part) => part.textContent),
    };
  })"""

# Whether a notice of news says its whole count: its words stand in a span of their
# own, which cuts them with an ellipsis, "2 …".
NOTICE_WHOLE = """notice => {
  const words = notice.querySelector(':scope > span');
  return words.scrollWidth <= words.clientWidth;
}"""


def test_a_card_s_head_line_cuts_its_title_beside_a_whole_notice(browser, serve):
    """A card at its least width, with Previous and Next for its target's two threads,
    holding news while the user writes: the notice reads whole on the head line, and
    the thread's title gives way before it, cut with an ellipsis."""
    url = serve(PANEL_PAGE)
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Make the banner quieter",
            "anchor": {"section": "h-how"},
        },
    )["id"]
    thread_model.post_reply(
        serve.page_dir,
        {"parent": root},
        "Quieter how?",
        title="The banner's weight against the status line and the logo",
    )
    panel_comment(serve.page_dir, "Keep the logo where it is", {"section": "h-how"})
    page = open_page(browser, url)
    resized(page, 1200, 900)
    page.locator(".lf-margin-marker").first.click()
    preview = page.locator(".lf-margin-preview")
    expect(preview.get_by_text("Make the banner quieter")).to_be_visible()
    text_field(preview, name="Reply", exact=True).click()
    page.keyboard.type("Also check the dark scheme")
    rendered(page)
    thread_model.post_reply(
        serve.page_dir,
        {"parent": root},
        "The status line can drop one weight.",
    )
    thread_model.post_reply(
        serve.page_dir, {"parent": root}, "And the title the muted ink."
    )
    told(page)
    notice = preview.locator(".lf-margin-thread-controls .lf-thread-news")
    expect(notice).to_have_text("2 new")
    rendered(page)
    assert notice.evaluate(NOTICE_WHOLE)
    title = preview.locator(".lf-margin-thread-title")
    expect(title).to_have_text(
        "The banner's weight against the status line and the logo"
    )
    assert title.evaluate("node => node.scrollWidth > node.clientWidth")
    assert title.evaluate("node => getComputedStyle(node).textOverflow") == "ellipsis"
    assert (
        title.bounding_box()["x"] + title.bounding_box()["width"]
        <= notice.bounding_box()["x"] + 0.5
    )


# Where a card's head line and what it holds stand: the line's box, the notice's
# start, the last press's end, and the first message's head's top; and on that head,
# its Edit's symbol and its time's end.
HEAD_LINE = """([line, notice]) => {
  const box = (node) => node.getBoundingClientRect();
  const presses = line.querySelector('.lf-thread-meta-actions');
  return {
    left: box(line).left,
    right: box(line).right,
    bottom: box(line).bottom,
    notice: box(notice).left,
    end: box(presses.lastElementChild).right,
    head: box(line.parentElement.querySelector('.lf-thread-transcript .lf-msg-head')).top,
    edit: box(line.parentElement.querySelector(
      '.lf-thread-transcript .lf-msg-head .lf-msg-controls > .lf-msg-edit svg')).left,
    time: box(line.parentElement.querySelector('.lf-thread-transcript .lf-msg-head time'))
      .right,
  };
}"""


@pytest.mark.parametrize("finger", [False, True])
def test_a_card_s_head_line_holds_a_whole_notice_and_its_presses(
    browser, serve, finger
):
    """A card at its least width holding news while the user writes, an agent's edit
    above the thread's end with a new reply, which waits wherever the card stands: the
    notice says one count, "2 new", whole, and it and the card's presses stand inside
    the head line, over the first message's head. On a desktop card, with Previous and
    Next for its target's two threads, and on one under a finger, whose presses and
    notice each take a finger's width; a touch screen as wide as 1408 stands that card
    beside its words. The user's message under them keeps "Me" whole and its time
    gives up its clock whole, keeping its day, where a cut read "25 Sep, …"; under a
    finger, where the controls always show, Edit stands clear of the time."""
    url = serve(PANEL_PAGE)
    # Written 51 days ago, so its time names its day, the widest a time reads.
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Keep the logo where it is",
            "anchor": {"section": "h-how"},
            "ts": (datetime.now().astimezone() - timedelta(days=51)).isoformat(),
        },
    )["id"]
    first = append_agent_reply(serve.page_dir, root, "The status line can drop one.")
    if finger:
        context = browser.new_context(
            viewport={"width": 1408, "height": 844}, has_touch=True, is_mobile=True
        )
        page = open_page(browser, url, context=context)
    else:
        panel_comment(serve.page_dir, "Make the banner quieter", {"section": "h-how"})
        page = open_page(browser, url)
        resized(page, 1200, 900)
    page.locator(".lf-margin-marker").first.click()
    preview = page.locator(".lf-margin-preview")
    expect(preview.get_by_text("Keep the logo where it is")).to_be_visible()
    text_field(preview, name="Reply", exact=True).click()
    page.keyboard.type("Also check the dark scheme")
    rendered(page)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "edit",
            "author": "agent",
            "agent": "Codex",
            "session": "pytest-summary",
            "message": first["id"],
            "text": "The status line can drop one weight.",
        },
    )
    append_agent_reply(serve.page_dir, root, "And the banner can keep its own.")
    told(page)
    line = preview.locator(".lf-margin-thread-controls")
    notice = line.locator(".lf-thread-news")
    expect_preview_words(notice, re.compile("1 new reply"))
    expect(notice).to_have_text("2 new")
    rendered(page)
    assert notice.evaluate(NOTICE_WHOLE)
    stands = page.evaluate(HEAD_LINE, [line.element_handle(), notice.element_handle()])
    assert stands["left"] <= stands["notice"], stands
    assert stands["end"] <= stands["right"] + 0.5, stands
    assert stands["bottom"] <= stands["head"] + 0.5, stands
    if finger:
        assert stands["time"] <= stands["edit"] + 0.5, stands
    card = preview.locator(f'.lf-page-thread[data-lf-thread="{root}"]')
    times = card.evaluate(TIMES_WHOLE)
    assert times and times[0]["whole"], times
    name = card.locator(".lf-msg-head").first.locator("b")
    expect(name).to_have_text("Me")
    assert name.evaluate("node => node.scrollWidth <= node.clientWidth")


def test_crossing_to_the_small_screen_moves_the_card_s_thread_to_the_panel(
    browser, serve
):
    """The rail falling takes the card's room, not its thread: the marker becomes a pin,
    and the thread goes on in the floating panel, the reply being written in the card
    with it, the same editor with its words and caret. The rail returning gives the
    thread back to a card the same way."""
    page = open_page(
        browser,
        serve(OBLIGATION_PAGE, events=[ACTION_ON_OBLIGATION, COMMENT_ON_OBLIGATION]),
    )
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    marker.click()
    card = page.locator(".lf-margin-preview")
    expect(card).to_be_visible()
    reply = text_field(card, name="Reply", exact=True)
    reply.click()
    page.keyboard.type("Keep the reaper")
    page.keyboard.press("ArrowLeft")
    reply.evaluate("el => { window.lfTypedIn = el; }")

    resized(page, 390, 760)
    margins_laid_out(page)
    row = marker.locator("xpath=ancestor::*[@data-lf-margin-for][1]")
    expect(row).to_have_attribute("data-lf-place", "pin")
    expect(marker).to_be_visible()
    expect(card).to_be_hidden()
    field = page.locator(".lf-fp-field leaf-text")
    expect(field).to_be_focused()
    assert field.evaluate("el => el === window.lfTypedIn")
    expect(field).to_have_js_property("value", "Keep the reaper")
    assert field.evaluate("el => el.selectionStart") == len("Keep the reape")

    resized(page, 1440, 900)
    expect(card).to_be_visible()
    expect(page.locator(".lf-fp-view")).to_have_count(0)
    typed = card.locator("leaf-text")
    expect(typed).to_be_focused()
    assert typed.evaluate("el => el === window.lfTypedIn")
    expect(typed).to_have_js_property("value", "Keep the reaper")


def test_widening_from_a_thread_in_the_panel_lands_in_its_card(browser, serve):
    """A user reading a thread in the floating panel as the rail returns goes on in its
    card: focus lands on the card's thread, never on the panel's view the card
    replaces, which left them on the page's body once that view went."""
    page = open_page(
        browser,
        serve(OBLIGATION_PAGE, events=[ACTION_ON_OBLIGATION, COMMENT_ON_OBLIGATION]),
    )
    resized(page, 390, 760)
    margins_laid_out(page)
    page.locator('.lf-margin-marker[data-lf-kinds~="comment"]').click()
    # The click puts the caret in the reply (records/thread/focus.js, `openingPart`); Escape
    # stands the user on the thread.
    page.keyboard.press("Escape")
    expect(page.locator(".lf-fp-view")).to_be_focused()

    resized(page, 1440, 900)
    card = page.locator(".lf-margin-preview")
    expect(card).to_be_visible()
    expect(card.locator(".lf-page-thread")).to_be_focused()


def test_a_reflow_that_moves_a_marker_carries_its_open_card(browser, serve):
    """The card beside a cluster's words follows it when the page moves under it.

    The margin geometry owner places a row at its target before the paint of a
    reflow — a diagram finishing, an image arriving, a disclosure opening above
    the marker. The card is placed by the layout pass that the column's change of size
    runs, a frame behind. The reflow here is a section growing, which is what every one
    of those cases is to the margin.
    """
    width = 1440
    page = open_page(browser, serve(OBLIGATION_PAGE, events=[COMMENT_ON_OBLIGATION]))
    resized(page, width, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment"]')
    marker.evaluate(
        "node => node.scrollIntoView({block: 'center', behavior: 'instant'})"
    )
    marker.click()
    card = page.locator(".lf-margin-preview")
    expect(card).to_be_visible()
    placement = """words => {
      const marker = document.querySelector('.lf-margin-marker[data-lf-kinds="comment"]');
      const controls = marker.closest('[data-lf-margin-for]');
      const card = document.querySelector('.lf-margin-preview');
      const m = controls.getBoundingClientRect();
      const c = card.getBoundingClientRect();
      return {marker: m.top, clear: c.left >= words + 7.5, words,
              cardLeft: c.left, cardTop: c.top};
    }"""
    before = page.evaluate(placement, page.evaluate(WORDS_RIGHT))
    assert before["clear"], before

    page.evaluate(
        "() => { document.getElementById('sec-mounts').style.paddingBottom = '48px'; }"
    )
    page.wait_for_function(
        """was => document.querySelector('.lf-margin-marker[data-lf-kinds="comment"]')
                 .getBoundingClientRect().top > was + 40""",
        arg=before["marker"],
    )
    margins_laid_out(page)
    after = page.evaluate(placement, page.evaluate(WORDS_RIGHT))
    assert after["marker"] > before["marker"] + 40, (before, after)
    assert after["clear"], after
    assert after["cardTop"] - before["cardTop"] == pytest.approx(
        after["marker"] - before["marker"], abs=0.5
    ), (before, after)


@pytest.mark.parametrize("transform", ["translate(30px, 40px)", "scale(0.25)"])
def test_a_card_under_a_containing_block_stands_beside_its_cluster(
    browser, serve, transform
):
    """The card's rule is worked out in client coordinates, and Floating UI carries it
    into the card's positioning space. A transformed ancestor is a containing block for
    the fixed card, so a spot or a length written as a client one would be moved or
    scaled by the transform; carried across, the card stays where and as wide as the
    rule put it."""
    page = open_page(browser, serve(OBLIGATION_PAGE, events=[PARAGRAPH_ON_OBLIGATION]))
    resized(page, 1920, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment"]')
    marker.evaluate(
        "node => node.scrollIntoView({block: 'center', behavior: 'instant'})"
    )
    marker.click()
    card = page.locator(".lf-margin-preview")
    expect(card).to_have_attribute("data-lf-thread-placement", "right")
    offset = """() => {
      const card = document.querySelector('.lf-margin-preview').getBoundingClientRect();
      const controls = document.querySelector('.lf-margin-marker[data-lf-kinds="comment"]')
        .closest('[data-lf-margin-for]').getBoundingClientRect();
      return {left: card.left - controls.left, top: card.top - controls.top,
              width: card.width};
    }"""
    before = page.evaluate(offset)
    page.evaluate(
        """transform => {
          const card = document.querySelector('.lf-margin-preview');
          // A block the size of the window, as a transformed body would be.
          const block = document.createElement('div');
          block.style.cssText = 'position: fixed; inset: 0; pointer-events: none';
          block.style.transform = transform;
          card.before(block);
          block.append(card);
        }""",
        transform,
    )
    page.evaluate("() => dispatchEvent(new Event('resize'))")
    rendered(page)
    after = page.evaluate(offset)
    if transform == "scale(0.25)":
        # The card's lengths are its own, so its least width shrinks with the
        # transform while it stands where it did.
        minimum = page.evaluate(
            "() => parseFloat(getComputedStyle(document.documentElement)"
            ".getPropertyValue('--lf-thread-card-min'))"
        )
        before = {**before, "width": minimum * 0.25}
    assert after == pytest.approx(before, abs=0.5), (before, after)


QUOTED_ON_OBLIGATION = {
    **COMMENT_ON_OBLIGATION,
    "anchor": {"section": "sec-mounts", "quote": "one came down in January"},
}


def test_a_focused_thread_covers_the_pages_choice_hints(browser, serve):
    """A fallback chip for a covered option stays behind the focused discussion. At
    1100x900 the window has room for the rail but the card none beside its ask, and it
    stands over the ask's options, below its marker: at 1000x838, Linux CI's wider
    DejaVu left the card no room below, and it stood above the options. How far over
    the chip the card's top edge reaches varies with the faces, from its whole box in
    DejaVu to its lower half in macOS 26's Charter, so the hit test reads the paint
    where the two overlap."""
    page = open_page(browser, serve(named_source("thread-choice-hints")))
    resized(page, 1100, 900)
    page.locator(".lf-margin-marker").first.focus()
    page.keyboard.press("Enter")
    card = page.locator(".lf-margin-preview .lf-page-thread")
    expect(card).to_be_focused()
    chip = page.locator(".lf-command-binding-badge").filter(has_text=re.compile("^2$"))
    expect(chip).to_have_count(1)
    rendered(page)
    paint = chip.evaluate(
        """chip => {
          const card = document.querySelector('.lf-margin-preview');
          const box = chip.getBoundingClientRect();
          const frame = card.getBoundingClientRect();
          const left = Math.max(box.left, frame.left);
          const right = Math.min(box.right, frame.right);
          const top = Math.max(box.top, frame.top);
          const bottom = Math.min(box.bottom, frame.bottom);
          if (right - left < 2 || bottom - top < 2) return {overlaps: false};
          // The hint is normally pointer-transparent. Include it in the browser's
          // hit test to read its paint order against the thread without moving it.
          chip.style.pointerEvents = 'auto';
          const hit = document.elementFromPoint((left + right) / 2, (top + bottom) / 2);
          chip.style.removeProperty('pointer-events');
          return {overlaps: true, covered: card.contains(hit)};
        }"""
    )
    assert paint == {"overlaps": True, "covered": True}, paint
    # Reading the thread keeps the reply's own hint and keyboard route usable.
    expect(card.locator(".lf-compose-placeholder > .lf-key-badge")).to_have_text("c")
    page.keyboard.press("c")
    expect(card.locator("leaf-text")).to_be_focused()


def test_a_scroll_that_carries_the_card_only_updates_the_rail_tab_stop(browser, serve):
    """The card, trace, marks and binding badges ride with their cluster without
    writes. The rail may move its one Tab stop to the highest visible entry, but
    scrolling must not rewrite the paint that already stands in the page's plane."""
    page = open_page(
        browser,
        serve(OBLIGATION_PAGE, events=[COMMENT_ON_OBLIGATION, QUOTED_ON_OBLIGATION]),
    )
    resized(page, 1440, 600)
    marker = page.locator('[data-lf-margin-for="bracket"] .lf-margin-marker')
    marker.evaluate(
        "node => node.scrollIntoView({block: 'center', behavior: 'instant'})"
    )
    marker.click()
    card = page.locator(".lf-margin-preview")
    expect(card).to_have_attribute("data-lf-plane", "page")
    offset = """() =>
      document.querySelector('.lf-margin-preview').getBoundingClientRect().top -
      document.querySelector('[data-lf-margin-for="bracket"]').getBoundingClientRect().top"""
    before = page.evaluate(offset)
    writes = scroll_writes(page, (-20, -20, 20, 20, 20))
    assert all(
        change["type"] == "attributes"
        and change["attribute"] == "tabindex"
        and all(".lf-margin-marker." in target for target in change["target"])
        for change in writes
    ), writes
    assert page.evaluate(offset) == pytest.approx(before, abs=0.5)


def test_news_while_a_card_s_row_is_scrolled_away_leaves_the_card_open(browser, serve):
    """A row its log has scrolled out of view is withheld from the margin, not gone
    from it, so news that repaints the margin meanwhile leaves its card open, and the
    card comes back with the row. The repaint read the withheld row as a thread gone
    from the margin and closed the card, so whether a card survived a scroll turned on
    whether anything arrived while its row was away."""
    rows = "".join(
        f'<p id="row-{n}">The export wrote tenant {n} to its archive.</p>'
        for n in range(30)
    )
    url = serve(
        leaf_page(
            "Scrolled away",
            "<p>The export copies each tenant into its own archive.</p>" * 3
            + f'<div id="log" data-bound="start" style="--lf-bound: 10rem">{rows}</div>',
        ),
        events=[
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": "Why did tenant 2 retry?",
                "anchor": {"section": "row-2"},
            }
        ],
    )
    page = open_page(browser, url)
    resized(page, 1440, 900)
    root = next(
        event
        for event in event_log.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )["id"]
    page.locator('[data-lf-margin-for="row-2"] .lf-margin-marker').click()
    card = page.locator(".lf-margin-preview")
    expect(card).to_be_visible()
    rendered(page)
    log = page.locator("#log").bounding_box()
    page.mouse.move(log["x"] + 40, log["y"] + log["height"] / 2)
    page.mouse.wheel(0, 400)
    scroll_settled(page, "#log")
    rendered(page)
    expect(page.locator('[data-lf-margin-for="row-2"]')).to_have_class(
        re.compile(r"\blf-withheld\b")
    )
    append_agent_reply(serve.page_dir, root, "Its first copy missed rows taken late.")
    told(page)
    rendered(page)
    page.mouse.wheel(0, -400)
    scroll_settled(page, "#log")
    rendered(page)
    expect(card).to_be_visible()
    expect(card).to_contain_text("missed rows taken late")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_tab_reaching_a_card_the_page_carried_away_brings_it_back(
    request, serve, engine
):
    """Past the page's last stop, Tab reaches the chrome, whose first stop can stand in a
    card the user scrolled away from. Firefox can't reveal a control in a box fixed over
    the page, so the card comes back with the control. Left away, the next Tab would let
    go of a control the user can't see and land where Tab reaches the same one again."""
    url = serve(
        LONG_PAGE,
        events=[
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": "Does this paragraph need a source?",
                "anchor": {"section": "p2"},
            }
        ],
    )
    page = open_page(request.getfixturevalue(engine), url)
    resized(page, 1440, 900)
    page.locator('.lf-margin-marker[data-lf-kinds="comment"]').click()
    card = page.locator(".lf-margin-preview")
    expect(card.locator("leaf-text")).to_be_focused()
    page.keyboard.press("Escape")
    expect(card.locator(".lf-page-thread")).to_be_focused()
    page.mouse.move(700, 450)
    for _ in range(4):
        page.mouse.wheel(0, 800)
    page.wait_for_function("() => scrollY > 2000")
    scroll_settled(page)
    rendered(page)
    expect(card).not_to_be_in_viewport()

    def control_in_card():
        return page.evaluate(
            """() => {
              let at = document.activeElement;
              while (at?.shadowRoot?.activeElement) at = at.shadowRoot.activeElement;
              return at?.closest('.lf-margin-preview') ? at.outerHTML : null;
            }"""
        )

    page.keyboard.press("Tab")
    expect(card).to_be_in_viewport()
    scroll_settled(page)
    rendered(page)
    reached = control_in_card()
    assert reached
    page.keyboard.press("Tab")
    rendered(page)
    assert control_in_card() not in (None, reached)


@pytest.mark.parametrize("target", ["sec-mounts", "bracket"])
def test_a_card_beside_an_element_scrolled_past_its_top_waits_at_the_windows_top(
    browser, serve, target
):
    """Beside an element, a card stays level with some line of it. A scroll that takes
    the element's top past the window's, with the rest still showing, leaves the card
    held at the window's top, in the window's plane, so the scroll writes nothing.
    Stood level with the element's clipped top instead, the card sat at the window's
    top in the page's plane: the browser carried it with each scroll
    frame and the next placement pulled it back, and Shift+a up to an obligation with a
    thread shook its card. Once the element's foot passes the window's top, the card
    leaves with it. On an obligation's options, the binding badge held at the window's top
    stands in the window's plane too, for the same reason."""
    comment = {**COMMENT_ON_OBLIGATION, "anchor": {"section": target}}
    # Give the last obligation room to pass above the viewport before scroll reaches the
    # document's end; the fixture otherwise stops with #bracket still visible.
    source = OBLIGATION_PAGE.replace(
        "</main>", '<div style="height: 800px" aria-hidden="true"></div></main>'
    )
    page = open_page(browser, serve(source, events=[comment]))
    resized(page, 1440, 600)
    marker = page.locator(f'[data-lf-margin-for="{target}"] .lf-margin-marker')
    marker.evaluate(
        "node => node.scrollIntoView({block: 'center', behavior: 'instant'})"
    )
    marker.click()
    card = page.locator(".lf-margin-preview")
    expect(card).to_have_attribute("data-lf-thread-placement", "right")
    reading = """async id => {
      const geometry = await window.__lfWidgetApi();
      const target = document.getElementById(id).getBoundingClientRect();
      return {
        card: document.querySelector('.lf-margin-preview').getBoundingClientRect().top,
        top: target.top, bottom: target.bottom,
        window: geometry.shownWindow({gap: 8}).top,
      };
    }"""

    def scroll_by(by):
        page.mouse.wheel(0, by)
        scroll_settled(page)
        rendered(page)
        return page.evaluate(reading, target)

    at = page.evaluate(reading, target)
    assert at["bottom"] - at["top"] > 60, at
    at = scroll_by(at["top"] - at["window"] + 20)
    expect(card).to_have_attribute("data-lf-plane", "window")
    assert at["card"] == pytest.approx(at["window"], abs=0.5), at
    writes = scroll_writes(page, (5, 5, -5, 5))
    assert writes == [], writes
    at = page.evaluate(reading, target)
    assert at["card"] == pytest.approx(at["window"], abs=0.5), at
    at = scroll_by(at["bottom"] - at["window"] + 20)
    assert at["bottom"] < at["window"], at
    expect(card).to_have_attribute("data-lf-plane", "page")
    assert at["card"] == pytest.approx(at["bottom"], abs=0.5), at


PANE_FILLER = "".join(
    f"<p>Filler paragraph {i} about the release.</p>" for i in range(12)
)


PANE_PAGE = leaf_page(
    "Release pane",
    f"""<div><h1>Release</h1>
<lf-pane id="evidence" label="Evidence"><div id="pane-body">
{PANE_FILLER}
<section id="pane-sec"><h2>Rollout</h2><p>One.</p><p>Two.</p><p>Three.</p><p>Four.</p>
</section>
{PANE_FILLER}
</div></lf-pane>
{PANE_FILLER}</div>""",
    head="<style>#pane-body { height: 420px; overflow: auto; }</style>",
    layout="sidebar",
)
# The same pane inside a box that contains its paint and stops short of the pane's foot,
# so the box's foot cuts the pane off there without the box scrolling anything.
PAINT_CLIPPED_PANE_PAGE = leaf_page(
    "Release pane",
    f"""<div><h1>Release</h1>
<div id="paint-clip">
<lf-pane id="evidence" label="Evidence"><div id="pane-body">
{PANE_FILLER}
<section id="pane-sec"><h2>Rollout</h2><p>One.</p><p>Two.</p><p>Three.</p><p>Four.</p>
</section>
{PANE_FILLER}
</div></lf-pane>
</div>
{PANE_FILLER}</div>""",
    head="""<style>#pane-body { height: 420px; overflow: auto; }
#paint-clip { contain: paint; height: 400px; }</style>""",
    layout="sidebar",
)


@pytest.mark.parametrize(
    "source,foot", [(PANE_PAGE, "pane-body"), (PAINT_CLIPPED_PANE_PAGE, "paint-clip")]
)
def test_a_card_a_panes_edge_holds_stays_put_as_the_pane_scrolls(
    browser, serve, source, foot
):
    """A card under an element in a scrolling pane, held in by the pane's foot, stands
    in the pane's plane: it is anchored to the pane, which the pane's own scroll does not
    move, so that scroll writes nothing to the card. Read as the page's plane, the card
    was anchored to the element, carried up with each scroll frame, and placed back. A
    scroll of the page carries the pane and the card together, and keeps the card's
    side, which the pane's size holds rather than where the page shows it. Where a box
    that contains its paint cuts the pane off above the pane's foot, the box's foot
    holds the card in, so the card stands in that box's plane."""
    comment = {**COMMENT_ON_OBLIGATION, "anchor": {"section": "pane-sec"}}
    page = open_page(browser, serve(source, events=[comment]))
    resized(page, 1440, 900)
    page.evaluate("() => document.getElementById('pane-sec').scrollIntoView()")
    page.locator('[data-lf-margin-for="pane-sec"] .lf-margin-marker').click()
    card = page.locator(".lf-margin-preview")
    expect(card).to_have_attribute("data-lf-thread-placement", "below")
    reading = """foot => ({
      card: document.querySelector('.lf-margin-preview').getBoundingClientRect().top,
      bottom: document.getElementById('pane-sec').getBoundingClientRect().bottom,
      foot: document.getElementById(foot).getBoundingClientRect().bottom,
    })"""
    at = page.evaluate(reading, foot)
    page.evaluate(
        "by => document.getElementById('pane-body').scrollBy(0, by)",
        at["bottom"] - at["foot"] + 60,
    )
    rendered(page)
    expect(card).to_have_attribute("data-lf-plane", "region")
    before = page.evaluate(reading, foot)
    writes = scroll_writes(
        page, (5, 5, -5, 5), scroller="document.getElementById('pane-body')"
    )
    assert not [
        w for w in writes if any("lf-margin-preview" in step for step in w["target"])
    ], writes
    assert page.evaluate(reading, foot)["card"] == pytest.approx(
        before["card"], abs=0.5
    )
    before = page.evaluate(reading, foot)
    writes = scroll_writes(page, (5, 5, -5, 5))
    assert not [
        w for w in writes if any("lf-margin-preview" in step for step in w["target"])
    ], writes
    expect(card).to_have_attribute("data-lf-thread-placement", "below")
    after = page.evaluate(reading, foot)
    assert after["card"] - after["foot"] == pytest.approx(
        before["card"] - before["foot"], abs=0.5
    )


NESTED_PANE_PAGE = leaf_page(
    "Nested panes",
    f"""<div><h1>Release</h1>
<lf-pane id="evidence" label="Evidence"><div id="pane-body">
{PANE_FILLER}
<div id="inner" data-bound="start" style="height: 700px">
{PANE_FILLER}
<section id="pane-sec"><h2>Rollout</h2><p>One.</p><p>Two.</p><p>Three.</p><p>Four.</p>
</section>
{PANE_FILLER}{PANE_FILLER}
</div>
{PANE_FILLER}
</div></lf-pane></div>""",
    head="<style>#pane-body { height: 300px; overflow: auto; }</style>",
    layout="sidebar",
)


def test_a_card_an_outer_panes_edge_holds_stands_in_that_panes_plane(browser, serve):
    """Inside a bounded block that itself scrolls inside a pane, the edge holding the
    card in can be the outer pane's, which clips the inner block. The card is anchored
    to the box whose edge holds it, so the outer pane's scroll writes nothing to it."""
    comment = {**COMMENT_ON_OBLIGATION, "anchor": {"section": "pane-sec"}}
    page = open_page(browser, serve(NESTED_PANE_PAGE, events=[comment]))
    resized(page, 1440, 900)
    page.evaluate(
        """() => {
          const pane = document.getElementById('pane-body');
          const inner = document.getElementById('inner');
          const box = (node) => node.getBoundingClientRect();
          pane.scrollTop += box(inner).top - box(pane).top - 10;
          const sec = document.getElementById('pane-sec');
          inner.scrollTop += box(sec).top - box(inner).top - 20;
        }"""
    )
    rendered(page)
    page.locator('[data-lf-margin-for="pane-sec"] .lf-margin-marker').click()
    card = page.locator(".lf-margin-preview")
    expect(card).to_have_attribute("data-lf-thread-placement", "below")
    reading = """() => ({
      card: document.querySelector('.lf-margin-preview').getBoundingClientRect().top,
      bottom: document.getElementById('pane-sec').getBoundingClientRect().bottom,
      foot: document.getElementById('pane-body').getBoundingClientRect().bottom,
    })"""
    at = page.evaluate(reading)
    page.evaluate(
        "by => document.getElementById('inner').scrollBy(0, by)",
        at["bottom"] - at["foot"] + 60,
    )
    rendered(page)
    expect(card).to_have_attribute("data-lf-plane", "region")
    before = page.evaluate(reading)
    writes = scroll_writes(
        page, (5, 5, -5, 5), scroller="document.getElementById('pane-body')"
    )
    assert not [
        w for w in writes if any("lf-margin-preview" in step for step in w["target"])
    ], writes
    assert page.evaluate(reading)["card"] == pytest.approx(before["card"], abs=0.5)


def test_the_marks_on_a_target_in_panes_ride_each_panes_scroll(browser, serve):
    """The card's thread marks an element inside nested scrolling panes while the user
    is located in it, and the trace while they stand on its marker. The element draws
    each as its own outline (surfaces.css), so a scroll of either pane carries it, and
    writes nothing to the element: drawn in the document's plane from the element's box
    as the panes cut it, the marks were rewritten on every scroll step, a frame behind
    the words."""
    comment = {**COMMENT_ON_OBLIGATION, "anchor": {"section": "pane-sec"}}
    page = open_page(browser, serve(NESTED_PANE_PAGE, events=[comment]))
    resized(page, 1440, 900)
    page.evaluate(
        """() => {
          const pane = document.getElementById('pane-body');
          const inner = document.getElementById('inner');
          const box = (node) => node.getBoundingClientRect();
          pane.scrollTop += box(inner).top - box(pane).top - 10;
          const sec = document.getElementById('pane-sec');
          inner.scrollTop += box(sec).top - box(inner).top - 20;
        }"""
    )
    rendered(page)
    marker = page.locator('[data-lf-margin-for="pane-sec"] .lf-margin-marker')
    marker.click()
    target = page.locator("#pane-sec")
    for mark, stand in (
        (("data-lf-mark", re.compile(r"\bhere\b")), lambda: None),
        (("data-lf-traced", ""), marker.focus),
    ):
        stand()
        expect(target).to_have_attribute(*mark)
        for scroller in ("inner", "pane-body"):
            writes = scroll_writes(
                page,
                (5, 5, -5, 5),
                scroller=f"document.getElementById('{scroller}')",
            )
            marked = [
                w for w in writes if any("#pane-sec" in step for step in w["target"])
            ]
            assert marked == [], (mark, scroller, marked)
            expect(target).to_have_attribute(*mark)


def test_a_scroll_that_carries_the_response_bar_writes_nothing(browser, serve):
    """The response bar a selection raises rides a scroll with its passage in the same
    plane, writing nothing, as the card does."""
    page = open_page(browser, serve(OBLIGATION_PAGE, events=[QUOTED_ON_OBLIGATION]))
    resized(page, 1440, 600)
    words = page.locator("#heater-p")
    words.evaluate(
        "node => node.scrollIntoView({block: 'center', behavior: 'instant'})"
    )
    box = words.bounding_box()
    y = box["y"] + 10
    select(page, (box["x"] + 2, y), (box["x"] + 120, y))
    bar = page.locator(".lf-fab-bar")
    expect(bar).to_be_visible()
    expect(bar).to_have_attribute("data-lf-plane", "page")
    offset = """() => document.querySelector('.lf-fab-bar').getBoundingClientRect().top -
      document.querySelector('#heater-p').getBoundingClientRect().top"""
    before = page.evaluate(offset)
    writes = scroll_writes(page, (-20, -20, 20, 20, 20))
    assert writes == [], writes
    assert page.evaluate(offset) == pytest.approx(before, abs=0.5)
