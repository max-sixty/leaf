"""Reading and replying inside a margin thread card: its transcript's scrolling, the
reply editor's growth, and what a sent or arriving turn leaves in view."""

import base64
from io import BytesIO

import pytest
from interact_support import append_carried_log_record
from PIL import Image
from playwright.sync_api import expect
from render_cases_interaction import (
    HOLD_MOTION,
    OBLIGATION_PAGE,
    PANEL_PAGE,
    panel_comment,
)
from render_cases_layout import ring_faults, rings_drawn
from render_harness import (
    example_media,
    holding,
    leaf_page,
    margins_laid_out,
    open_page,
    pane_scroll_behavior,
    resized,
    rgb_pixel,
    round_trip,
    scroll_settled,
    sending,
    told,
    write,
)

from browser.margin import (
    CARD_AND_REPLY,
    COMMENT_ON_OBLIGATION,
    DRAFTING_CARD,
    LONG_THREAD,
    LONG_THREAD_PAGE,
    LONG_THREAD_ROOT,
    MARGIN_EDITOR_ROOTS,
    PANE_PIN_PAGE,
    _comment_on,
    _focused_editor_caret,
    drafting_in_a_short_card,
    open_long_thread,
    send_anchored_comment,
)
from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.parametrize("long", [False, True], ids=["fitting", "overflowing"])
def test_floating_thread_chains_scrolling_to_its_page(browser, serve, long):
    """A floating thread scrolls its turns, then the document at either edge.

    A fitting transcript must not swallow the wheel just because it could scroll
    with more messages. This also protects overflowing threads at their boundaries.
    """
    source = leaf_page(
        "Scroll a contextual thread",
        '<div style="height: 80vh"></div>'
        '<p id="open">Review the open questions.</p>'
        '<div style="height: 180vh"></div>',
    )
    page = open_page(
        browser, serve(source, events=LONG_THREAD if long else [LONG_THREAD_ROOT])
    )
    resized(page, 1440, 900)
    page.locator("#open").scroll_into_view_if_needed()
    page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
    card = page.locator(".lf-margin-preview")
    expect(card).to_be_visible()
    transcript = card.locator(".lf-thread-transcript")
    room = transcript.evaluate("node => node.scrollHeight - node.clientHeight")
    assert (room > 0) == long

    if long:
        transcript.evaluate(
            "node => node.scrollTop = (node.scrollHeight - node.clientHeight) / 2"
        )
        before = transcript.evaluate("node => node.scrollTop")
        page_at = page.evaluate("scrollY")
        transcript.hover()
        page.mouse.wheel(0, -80)
        page.wait_for_function(
            "([node, before]) => node.scrollTop < before",
            arg=[transcript.element_handle(), before],
        )
        scroll_settled(page, ".lf-margin-preview .lf-thread-transcript")
        assert page.evaluate("scrollY") == page_at

    for direction in (-1, 1):
        transcript.evaluate(
            "(node, direction) => node.scrollTop = direction < 0 ? 0 : node.scrollHeight",
            direction,
        )
        transcript.hover()
        page_at = page.evaluate("scrollY")
        page.mouse.wheel(0, direction * 80)
        page.wait_for_function(
            "([before, direction]) => (scrollY - before) * direction > 20",
            arg=[page_at, direction],
        )
        scroll_settled(page)
        expect(card).to_be_visible()


@pytest.mark.parametrize("long", [False, True], ids=["fitting", "overflowing"])
def test_floating_thread_pages_on_to_its_page(browser, serve, long):
    """With a floating thread focused, d/u page its turns, then the document at
    either edge, as the wheel does, and go on paging it once the thread has
    scrolled out of view."""
    source = leaf_page(
        "Page through a contextual thread",
        '<div style="height: 80vh"></div>'
        '<p id="open">Review the open questions.</p>'
        '<div style="height: 400vh"></div>',
    )
    page = open_page(
        browser, serve(source, events=LONG_THREAD if long else [LONG_THREAD_ROOT])
    )
    page.emulate_media(reduced_motion="reduce")
    resized(page, 1440, 900)
    page.locator("#open").scroll_into_view_if_needed()
    page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
    card = page.locator(".lf-margin-preview")
    expect(card.locator(".lf-page-thread")).to_be_focused()
    transcript = card.locator(".lf-thread-transcript")
    assert (
        transcript.evaluate("box => box.scrollHeight - box.clientHeight") > 0
    ) == long

    for key, edge in (("u", "0"), ("d", "box.scrollHeight")):
        transcript.evaluate(f"box => box.scrollTop = {edge}")
        if long:
            transcript.evaluate(
                "box => box.scrollTop = (box.scrollHeight - box.clientHeight) / 2"
            )
            before = transcript.evaluate("box => box.scrollTop")
            page_at = page.evaluate("scrollY")
            page.keyboard.press(key)
            assert transcript.evaluate("box => box.scrollTop") != before
            assert page.evaluate("scrollY") == page_at
            transcript.evaluate(f"box => box.scrollTop = {edge}")
        page_at = page.evaluate("scrollY")
        page.keyboard.press(key)
        moved = page.evaluate("scrollY") - page_at
        assert moved > 20 if key == "d" else moved < -20
        expect(card).to_be_visible()

    transcript.evaluate("box => box.scrollTop = box.scrollHeight")
    for _ in range(8):
        if not card.evaluate("card => card.getBoundingClientRect().bottom > 0"):
            break
        page.keyboard.press("d")
    expect(card.locator(".lf-page-thread")).to_be_focused()
    assert not card.evaluate("card => card.getBoundingClientRect().bottom > 0")
    for key in ("d", "u"):
        page_at = page.evaluate("scrollY")
        page.keyboard.press(key)
        moved = page.evaluate("scrollY") - page_at
        assert moved > 20 if key == "d" else moved < -20


@pytest.mark.parametrize("height", [900, 250])
def test_the_margin_reply_outside_the_transcript_shows_its_whole_ring(
    browser, serve, height
):
    """Scrolling moves turns under the actions while both stay put, and the reply row
    stays outside the scrollport."""
    page, preview, transcript = open_long_thread(browser, serve, height)
    header = preview.locator(".lf-margin-thread-controls")
    row = preview.locator(".lf-thread-reply")
    original = [header.bounding_box(), row.bounding_box()]
    transcript.evaluate("list => list.scrollTop = 40")
    rendered(page)
    assert header.bounding_box() == pytest.approx(original[0], abs=0.5)
    assert row.bounding_box() == pytest.approx(original[1], abs=0.5)
    # The clip starts a ring's room above the heads' line, so a focus ring stays whole.
    ring_top = transcript.evaluate(
        "list => parseFloat(getComputedStyle(list).scrollPaddingTop)"
    )
    assert header.bounding_box()["y"] - transcript.bounding_box()["y"] >= ring_top - 0.5
    # The scrollport extends under the reply by its bottom padding so a rewrite's
    # outside focus ring stays visible; the scrolling turns stop above the row.
    ring_room = transcript.evaluate(
        "list => parseFloat(getComputedStyle(list).paddingBottom)"
    )
    assert row.bounding_box()["y"] >= (
        transcript.bounding_box()["y"]
        + transcript.bounding_box()["height"]
        - ring_room
        - 0.5
    )

    reply = preview.get_by_role("textbox", name="Reply", exact=True)
    page.keyboard.press("Tab")
    reply.focus()
    expect(reply).to_be_focused()
    [ring] = [
        ring
        for ring in rings_drawn(page)
        if ring["sample"] and ".lf-compose-field" in ring["rule"]
    ]
    assert ring["cuts"] == []


def test_a_margin_card_is_one_frame_that_rings_for_its_thread(browser, serve):
    """The card is the thread's one frame. The thread the keyboard opens a card onto
    fills it with no tint and no ring of its own, and the card wears the ring, whole,
    at its own edge. The reply field keeps its box, standing at the card's padding.

    It used to ring and tint the thread inside the card's border, a frame in a frame
    with the reply field a third box inside that.
    """
    page = open_page(browser, serve(LONG_THREAD_PAGE, events=[LONG_THREAD_ROOT]))
    page.emulate_media(reduced_motion="reduce")
    resized(page, 1440, 900)
    marker = page.locator('[data-lf-margin-for="open"] .lf-margin-marker')
    page.keyboard.press("Tab")  # keyboard modality, so the thread's focus is visible
    marker.focus()
    page.keyboard.press("Enter")
    thread = page.locator(".lf-margin-preview .lf-page-thread")
    expect(thread).to_be_focused()
    assert thread.evaluate("node => node.matches(':focus-visible')")
    rendered(page)
    drawn = rings_drawn(page)
    worn = [(seen["who"].split(" ")[0], seen["rule"]) for seen in drawn if seen["here"]]
    assert [who for who, _rule in worn] == ["div.lf-margin-preview-card"], drawn
    assert ".lf-page-thread" in worn[0][1], drawn
    assert not (faults := ring_faults(drawn, "on a card the keyboard opened")), (
        "\n".join(faults)
    )
    frame = page.locator(".lf-margin-preview").evaluate(
        """(card) => {
        const thread = card.querySelector('.lf-page-thread');
        const words = thread.querySelector('.lf-msg-body');
        const field = thread.querySelector('.lf-thread-reply .lf-compose-field');
        const x = (node) => {
            const box = node.getBoundingClientRect();
            return [Math.round(box.left), Math.round(box.right)];
        };
        return {card: Math.round(card.getBoundingClientRect().left),
                ground: getComputedStyle(thread).backgroundColor,
                words: x(words), field: x(field),
                fieldBorder: getComputedStyle(field).borderTopStyle,
                inset: Math.round(words.getBoundingClientRect().left
                                  - card.getBoundingClientRect().left)};
    }"""
    )
    # The thread paints no ground, so the card's paper shows through it.
    assert frame["ground"] == "rgba(0, 0, 0, 0)", frame
    assert frame["fieldBorder"] == "solid", frame
    # The field's box stands at the card's padding; words share the conversation's
    # reading inset, rather than gaining a second frame.
    assert frame["field"][0] - frame["card"] == 13, frame
    assert frame["inset"] == frame["field"][0] - frame["card"] + 13, frame


def test_a_reply_next_on_me_lands_on_rings_its_card(browser, serve):
    """Next on me lands on the agent's long question in its card, and the card wears
    the ring, whole, as for the thread itself: the card is the thread's one frame. The
    message wore its own outline, a frame in the frame whose top its sticky head
    painted over."""
    question = {**LONG_THREAD[1], "obligation": True}
    page = open_page(
        browser, serve(LONG_THREAD_PAGE, events=[LONG_THREAD_ROOT, question])
    )
    page.emulate_media(reduced_motion="reduce")
    resized(page, 1440, 900)
    page.keyboard.press("m")
    message = page.locator(f'.lf-margin-preview .lf-msg[data-event="{question["id"]}"]')
    expect(message).to_be_focused()
    rendered(page)
    drawn = rings_drawn(page)
    worn = [seen["who"].split(" ")[0] for seen in drawn if seen["here"]]
    assert worn == ["div.lf-margin-preview-card"], drawn
    assert not (faults := ring_faults(drawn, "on the reply Next on me reached")), (
        "\n".join(faults)
    )


# Whether a message stands wholly between the transcript's top and the reply row pinned
# over its foot, which is the part of the transcript the user can read.
SHOWN_ABOVE_THE_REPLY = """message => {
  const list = message.closest('.lf-thread-transcript').getBoundingClientRect();
  const reply = message.closest('.lf-page-thread').querySelector(':scope > .lf-thread-reply')
    .getBoundingClientRect();
  const box = message.getBoundingClientRect();
  return {shown: box.top >= list.top - 0.5 && box.bottom <= reply.top + 0.5,
          message: [box.top, box.bottom], list: list.top, reply: reply.top};
}"""


def long_thread_in_reply(browser, serve):
    """The long thread's margin card with the user in its reply box, entered by
    Enter on the thread. Scroll anchoring is off on the transcript, so every move read
    is the runtime's own."""
    page, preview, transcript = open_long_thread(browser, serve)
    transcript.evaluate("list => list.style.overflowAnchor = 'none'")
    thread = preview.locator(".lf-page-thread").first
    expect(thread).to_be_focused()
    page.keyboard.press("Enter")
    editor = preview.locator("leaf-text")
    expect(editor).to_be_focused()
    rendered(page)
    return page, preview, editor, transcript


def test_replying_on_a_long_margin_card_keeps_the_turn_being_read(browser, serve):
    """Entering the visible reply box preserves the earlier transcript reading."""
    page, preview, transcript = open_long_thread(browser, serve)
    transcript.evaluate("list => list.style.overflowAnchor = 'none'")
    before = [page.evaluate("scrollY"), transcript.evaluate("list => list.scrollTop")]
    page.keyboard.press("Enter")
    expect(preview.locator("leaf-text")).to_be_focused()
    rendered(page)
    scroll_settled(page, ".lf-thread-transcript")
    assert [
        page.evaluate("scrollY"),
        transcript.evaluate("list => list.scrollTop"),
    ] == before


@pytest.mark.parametrize("place", ["end", "partway"])
def test_a_margin_reply_send_shows_the_sent_turn(browser, serve, place):
    page, preview, editor, transcript = long_thread_in_reply(browser, serve)
    write(editor, "My new reply words")
    transcript.evaluate(
        "(list, place) => list.scrollTop = place === 'end' ? list.scrollHeight : 40",
        place,
    )
    with sending(page, "the reply"):
        editor.press("Enter")
    sent = preview.locator(".lf-msg").last
    expect(sent).to_contain_text("My new reply words")
    rendered(page)
    reading = sent.evaluate(SHOWN_ABOVE_THE_REPLY)
    assert reading["shown"], reading


# Whether the margin card's motion has ended (box-motion.js).
CARD_AT_REST = (
    "() => !document.querySelector('.lf-margin-preview').getAnimations({subtree: true})"
    ".some(a => Number.isFinite(a.effect?.getComputedTiming().endTime))"
)

# Where the card's outline, its head row and each turn are drawn now: the outline as its
# surface's ring is cut (box-motion.js), the rest by their boxes.
CARD_DRAWN = """card => {
  const ring = card.querySelector('.lf-margin-preview-ground > .lf-box-ring');
  const ground = card.querySelector('.lf-margin-preview-ground');
  const cut = getComputedStyle(ring).clipPath.match(/inset\\(([-\\d.]+)px/);
  return [cut ? ground.getBoundingClientRect().top + Number(cut[1])
              : card.getBoundingClientRect().top,
          card.querySelector('.lf-margin-thread-controls').getBoundingClientRect().top,
          ...[...card.querySelectorAll('.lf-thread-transcript > .lf-msg')]
            .map(turn => turn.getBoundingClientRect().top)];
}"""


def test_a_card_send_moves_the_card_as_one_stream(browser, serve):
    """A send from a margin card slides the card up as one stream, as the floating
    panel's does: at the motion's first frame the card's outline, its head row and every
    turn already there stand one shared distance below where they come to rest, so the
    picture starts as it stood and nothing the reader reads overtakes anything else.
    The new turn starts that far below its rest too, coming up from the foot. Read at
    the first frame, held, and again at rest."""
    page = open_page(browser, serve(LONG_THREAD_PAGE, events=[LONG_THREAD_ROOT]))
    page.emulate_media(reduced_motion="no-preference")
    resized(page, 1440, 900)
    page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    editor = preview.get_by_role("textbox", name="Reply", exact=True)
    editor.click()
    write(editor, "And the mobile cohort too.")
    rendered(page)
    stood = preview.evaluate(CARD_DRAWN)
    page.evaluate("() => {" + HOLD_MOTION + "}")
    with sending(page, "the reply"):
        editor.press("Enter")
    expect(preview.locator(".lf-msg")).to_have_count(2)
    rendered(page)
    drawn = preview.evaluate(CARD_DRAWN)
    page.evaluate("() => window.__lfHeld.splice(0).forEach(motion => motion.finish())")
    page.wait_for_function(CARD_AT_REST)
    rest = preview.evaluate(CARD_DRAWN)
    offsets = [d - r for d, r in zip(drawn, rest, strict=True)]
    assert offsets[0] > 10, f"the card grew in place: {offsets}"
    assert max(offsets) - min(offsets) < 1, f"the stream came apart: {offsets}"
    assert drawn[:3] == pytest.approx(stood, abs=1), (stood, drawn)


# Where a card's outline, its head row, each turn and each turn's name are drawn now.
FULL_CARD_DRAWN = """card => {
  const ring = card.querySelector('.lf-margin-preview-ground > .lf-box-ring');
  const ground = card.querySelector('.lf-margin-preview-ground');
  const cut = getComputedStyle(ring).clipPath.match(/inset\\(([-\\d.]+)px/);
  const tops = (selector) => [...card.querySelectorAll(selector)]
    .map(node => node.getBoundingClientRect().top);
  return {
    outline: ground.getBoundingClientRect().top + Number(cut?.[1] ?? 0),
    controls: tops('.lf-margin-thread-controls')[0],
    turns: tops('.lf-thread-transcript > .lf-msg'),
    names: tops('.lf-thread-transcript .lf-msg-head'),
  };
}"""


def sending_from_a_full_card(browser, serve):
    """A card at its height cap, its transcript scrolled, with a two-line reply sent from
    it and every motion the send starts held at its first frame. Returns the page, the
    card, its transcript and where the card's parts stood before the send."""
    page = open_page(browser, serve(LONG_THREAD_PAGE, events=LONG_THREAD))
    page.emulate_media(reduced_motion="no-preference")
    resized(page, 1440, 900)
    page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    transcript = preview.locator(".lf-thread-transcript")
    editor = preview.get_by_role("textbox", name="Reply", exact=True)
    editor.click()
    write(editor, "And the mobile cohort too.\nAnd the weekend shift.")
    rendered(page)
    page.wait_for_function(CARD_AT_REST)
    assert transcript.evaluate("list => list.scrollTop > 100"), "nothing scrolled away"
    stood = preview.evaluate(FULL_CARD_DRAWN)
    page.evaluate("() => {" + HOLD_MOTION + "}")
    with sending(page, "the reply"):
        editor.press("Enter")
    expect(preview.locator(".lf-msg")).to_have_count(4)
    rendered(page)
    return page, preview, transcript, stood


def test_a_send_from_a_full_card_rides_its_turns_and_names_up(browser, serve):
    """A send from a card at its cap scrolls its transcript to the new turn, which the
    card presents as the turns riding up together. At the first frame every turn and
    every name, the one stuck at the top included, stands where it stood, and the
    outline and head row stay put; at rest the turns have all moved up one shared
    distance and the transcript stands at its end."""
    page, preview, transcript, stood = sending_from_a_full_card(browser, serve)
    drawn = preview.evaluate(FULL_CARD_DRAWN)
    page.evaluate("() => window.__lfHeld.splice(0).forEach(motion => motion.finish())")
    page.wait_for_function(CARD_AT_REST)
    rest = preview.evaluate(FULL_CARD_DRAWN)
    for part in ("outline", "controls"):
        assert drawn[part] == pytest.approx(stood[part], abs=1), (part, stood, drawn)
    for part in ("turns", "names"):
        assert drawn[part][:3] == pytest.approx(stood[part], abs=1), (
            part,
            stood,
            drawn,
        )
    rode = [d - r for d, r in zip(drawn["turns"], rest["turns"], strict=True)]
    assert min(rode) > 10, f"the turns did not ride: {rode}"
    assert max(rode) - min(rode) < 1, f"the turns came apart: {rode}"
    assert transcript.evaluate(
        "list => list.scrollHeight - list.clientHeight - list.scrollTop < 2"
    )


def test_news_during_a_card_s_ride_lands_at_its_end(browser, serve):
    """An answer arriving while a send's turns still ride lands the transcript at its
    new end, as it would at rest: the end the ride holds is the layout's, with the
    answer in it."""
    page, preview, transcript, _stood = sending_from_a_full_card(browser, serve)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "parent": LONG_THREAD_ROOT["id"],
            "responds": preview.locator(".lf-msg").last.get_attribute("data-event"),
            "text": "Noted, the weekend shift as well.",
        },
    )
    told(page)
    expect(preview.locator(".lf-msg")).to_have_count(5)
    rendered(page)
    page.evaluate("() => window.__lfHeld.splice(0).forEach(motion => motion.finish())")
    page.wait_for_function(CARD_AT_REST)
    rendered(page)
    assert transcript.evaluate(
        "list => list.scrollHeight - list.clientHeight - list.scrollTop < 2"
    ), transcript.evaluate(
        "list => [list.scrollHeight, list.clientHeight, list.scrollTop]"
    )


def test_a_press_on_a_moving_card_reaches_what_it_aims_at(browser, serve):
    """While a card moves after a change of its size, a press on one of its controls
    reaches that control: the grip along the card's edge takes presses only in its
    band, mid-motion as at rest. Its own clip opens its middle, and a motion cutting
    the grip replaced that clip, so the press started a drag instead."""
    page = open_page(browser, serve(LONG_THREAD_PAGE, events=[LONG_THREAD_ROOT]))
    page.emulate_media(reduced_motion="no-preference")
    resized(page, 1440, 900)
    page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    editor = preview.get_by_role("textbox", name="Reply", exact=True)
    editor.click()
    write(editor, "A first line.")
    rendered(page)
    page.evaluate("() => {" + HOLD_MOTION + "}")
    page.keyboard.press("Shift+Enter")
    page.keyboard.type("A second line grows the card.")
    page.wait_for_function("() => window.__lfHeld.some(m => m.playState !== 'idle')")
    close = preview.locator(".lf-margin-preview-close").bounding_box()
    page.mouse.click(close["x"] + close["width"] / 2, close["y"] + close["height"] / 2)
    expect(preview).to_be_hidden()


def test_a_growing_margin_reply_keeps_its_whole_ring_from_the_first_frame(
    browser, serve
):
    """While the card grows with its reply field, the field's focus ring is drawn
    whole where the field stood, from the motion's first frame. The field's own paper
    already stood at its grown size, over the ring's lower edge, until the ring had
    nearly reached its rest."""
    page = open_page(browser, serve(LONG_THREAD_PAGE, events=[LONG_THREAD_ROOT]))
    page.emulate_media(reduced_motion="no-preference")
    resized(page, 1440, 900)
    page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    editor = preview.get_by_role("textbox", name="Reply", exact=True)
    editor.click()
    write(editor, "A first line.")
    rendered(page)
    page.wait_for_function(CARD_AT_REST)
    field = preview.locator(".lf-thread-reply .lf-compose-field")
    stood = field.bounding_box()
    ring = field.evaluate(
        "node => getComputedStyle(node).outlineColor.match(/\\d+/g).map(Number)"
    )
    page.evaluate("() => {" + HOLD_MOTION + "}")
    page.keyboard.press("Shift+Enter")
    page.wait_for_function("() => window.__lfHeld.some(m => m.playState !== 'idle')")
    assert field.bounding_box()["height"] > stood["height"] + 10, "the field never grew"
    pixels = Image.open(
        BytesIO(
            page.screenshot(
                clip={
                    "x": stood["x"] - 4,
                    "y": stood["y"] - 4,
                    "width": stood["width"] + 8,
                    "height": stood["height"] + 8,
                }
            )
        )
    ).convert("RGB")
    scale = pixels.width / (stood["width"] + 8)

    def ringed(y):
        """The share of the field's width along row `y`, in the clip's CSS pixels,
        drawn in the ring's colour."""
        row = [
            rgb_pixel(pixels, (round(x * scale), round(y * scale)))
            for x in range(24, round(stood["width"]) - 16)
        ]
        return sum(
            sum(abs(a - b) for a, b in zip(seen, ring, strict=True)) < 90
            for seen in row
        ) / len(row)

    # The ring stands two pixels outside the field's box: its top band ends at the
    # field's top, 4 px into the clip, and its bottom band starts at the field's foot.
    edges = {"top": ringed(3), "bottom": ringed(stood["height"] + 5)}
    page.evaluate("() => window.__lfHeld.splice(0).forEach(motion => motion.finish())")
    assert min(edges.values()) > 0.8, edges


def test_typing_in_a_margin_reply_leaves_the_transcript_where_the_reader_put_it(
    browser, serve
):
    """The growth reveal aimed at the pinned row crept the transcript by its scroll
    padding on every keystroke, pulling a reader partway up down to the end."""
    page, _preview, editor, transcript = long_thread_in_reply(browser, serve)
    transcript.evaluate("list => list.scrollTop = 100")
    rendered(page)
    editor.type("twenty characters!!!")
    rendered(page)
    assert transcript.evaluate("list => list.scrollTop") == 100


def test_a_block_pasted_into_a_margin_reply_keeps_the_last_turn_above_it(
    browser, serve
):
    """A full card shares its bounded body with the growing reply. Paste preserves
    the outer frame and latest answered turn, then scrolls inside the editor."""
    page, preview, editor, transcript = long_thread_in_reply(browser, serve)
    transcript.evaluate("list => list.scrollTop = list.scrollHeight")
    editor.type("first")
    rendered(page)
    before = page.evaluate(CARD_AND_REPLY)
    page.keyboard.insert_text("\n" + "\n".join(f"pasted {n}" for n in range(30)))
    rendered(page)
    after = page.evaluate(CARD_AND_REPLY)
    for edge in ("cardTop", "cardBottom"):
        assert after[edge] == pytest.approx(before[edge], abs=0.5), (before, after)
    before_height = before["editorBottom"] - before["editorTop"]
    after_height = after["editorBottom"] - after["editorTop"]
    assert after_height > before_height, (before, after)
    assert editor.evaluate("box => box.scrollTop > 0")
    caret = _focused_editor_caret(page)
    assert caret["selection"] == caret["length"], caret
    assert caret["caretTop"] >= caret["boxTop"], caret
    assert caret["caretBottom"] <= caret["boxBottom"], caret
    reading = preview.locator(".lf-msg").last.evaluate(SHOWN_ABOVE_THE_REPLY)
    assert reading["shown"], reading


def test_a_growing_margin_reply_keeps_the_previous_turn_visible(browser, serve):
    page = open_page(browser, serve(LONG_THREAD_PAGE, events=LONG_THREAD))
    resized(page, 1440, 250)
    page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    transcript = preview.locator(".lf-thread-transcript")
    preview.get_by_role("textbox", name="Reply", exact=True).click()
    editor = preview.locator("leaf-text")
    transcript.evaluate("list => list.scrollTop = list.scrollHeight")
    write(editor, "A reply that grows.\n" * 30)
    latest = transcript.locator(".lf-msg").last
    visible = latest.evaluate(
        """message => {
          const list = message.closest('.lf-thread-transcript');
          const band = list.getBoundingClientRect();
          const editor = list.closest('.lf-page-thread').querySelector('leaf-text').getBoundingClientRect();
          return {
            tail: message.getBoundingClientRect().bottom,
            top: band.top,
            editor: editor.top,
          };
        }"""
    )
    assert visible["tail"] >= visible["top"] + 20, visible
    assert visible["tail"] <= visible["editor"], visible
    assert editor.evaluate("input => input.scrollTop > 0")


@pytest.mark.parametrize("comment_repeats", [0, 17])
def test_a_margin_reply_grows_before_it_scrolls(browser, serve, comment_repeats):
    """Visible and already clipped transcripts both yield writing space."""
    root = LONG_THREAD_ROOT | (
        {
            "text": "The export must keep each tenant's credits separate. "
            * comment_repeats
        }
        if comment_repeats
        else {}
    )
    page = open_page(browser, serve(LONG_THREAD_PAGE, events=[root]))
    resized(page, 1440, 600 if comment_repeats else 900)
    page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
    preview = page.locator(".lf-margin-preview")
    preview.get_by_role("textbox", name="Reply", exact=True).click()
    editor = preview.locator("leaf-text")
    rendered(page)
    transcript = preview.locator(".lf-thread-transcript")
    if comment_repeats == 6:
        assert transcript.evaluate("list => list.scrollHeight <= list.clientHeight + 1")
    write(editor, "\n".join("A reply with several lines." for _ in range(5)))
    assert editor.evaluate(
        "input => input.getBoundingClientRect().height"
        " >= 5 * parseFloat(getComputedStyle(input).lineHeight)"
    )
    assert editor.evaluate("input => input.scrollHeight <= input.clientHeight + 1")


def test_a_margin_reply_with_a_pasted_image_keeps_its_editor_and_attachment_visible(
    browser, serve
):
    """The attachment keeps its own row above the editor in a bounded card."""
    page, preview, editor, transcript = long_thread_in_reply(browser, serve)
    pixels = (example_media() / "051bee487bfb5d13.png").read_bytes()
    editor.evaluate(
        """(box, encoded) => {
          const bytes = Uint8Array.from(atob(encoded), char => char.charCodeAt(0));
          const transfer = new DataTransfer();
          transfer.items.add(new File([bytes], 'pasted.png', {type: 'image/png'}));
          box.dispatchEvent(new ClipboardEvent('paste', {
            bubbles: true, cancelable: true, clipboardData: transfer,
          }));
        }""",
        base64.b64encode(pixels).decode(),
    )
    image = preview.locator(".lf-composer-media img")
    expect(image).to_have_count(1)
    write(
        editor, "\n".join(f"A reply with several lines, line {n}." for n in range(30))
    )
    rendered(page)
    bounds = image.evaluate(
        """image => {
          const card = image.closest('.lf-margin-preview').getBoundingClientRect();
          const input = image.closest('.lf-thread-reply').querySelector('leaf-text')
            .getBoundingClientRect();
          const media = image.getBoundingClientRect();
          return {cardTop: card.top, cardBottom: card.bottom,
                  imageTop: media.top, imageBottom: media.bottom, imageHeight: media.height,
                  inputTop: input.top, inputBottom: input.bottom};
        }"""
    )
    assert bounds["imageHeight"] >= 50, bounds
    assert bounds["imageTop"] >= bounds["cardTop"], bounds
    assert bounds["imageBottom"] <= bounds["inputTop"], bounds
    assert bounds["inputBottom"] <= bounds["cardBottom"], bounds
    assert editor.evaluate("input => input.scrollTop > 0")
    editor.press("ControlOrMeta+End")
    rendered(page)
    caret = _focused_editor_caret(page)
    assert caret["caretTop"] >= caret["boxTop"], caret
    assert caret["caretBottom"] <= caret["boxBottom"], caret
    assert transcript.evaluate("list => list.clientHeight") >= 20


def test_an_incoming_margin_reply_follows_only_at_the_tail(browser, serve):
    page = open_page(browser, serve(LONG_THREAD_PAGE, events=LONG_THREAD))
    resized(page, 1440, 900)
    page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
    transcript = page.locator(".lf-margin-preview .lf-thread-transcript")
    transcript.evaluate("list => list.scrollTop = list.scrollHeight")
    before = transcript.evaluate("list => list.scrollTop")
    newest = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": LONG_THREAD_ROOT["id"],
            "text": "A new answer at the end of this thread. " * 8,
        },
    )
    told(page)
    incoming = transcript.locator(f'[data-event="{newest["id"]}"]')
    expect(incoming).to_be_visible()
    page.wait_for_function(
        "before => document.querySelector('.lf-margin-preview .lf-thread-transcript').scrollTop > before",
        arg=before,
    )
    scroll_settled(page, ".lf-margin-preview .lf-thread-transcript")
    assert incoming.evaluate(
        """message => {
          const list = message.closest('.lf-thread-transcript');
          return message.getBoundingClientRect().bottom <=
            list.getBoundingClientRect().bottom;
        }"""
    )
    at_tail = transcript.evaluate("list => list.scrollTop")
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "edit",
            "author": "agent",
            "agent": "Codex",
            "message": newest["id"],
            "text": "The answer now has more detail. " * 25,
        },
    )
    told(page)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "edit",
            "author": "agent",
            "agent": "Codex",
            "message": newest["id"],
            "text": "The answer now has even more detail. " * 30,
        },
    )
    told(page)
    page.wait_for_function(
        "before => document.querySelector('.lf-margin-preview .lf-thread-transcript').scrollTop > before",
        arg=at_tail,
    )
    scroll_settled(page, ".lf-margin-preview .lf-thread-transcript")
    assert (
        transcript.evaluate(
            "list => list.scrollHeight - list.clientHeight - list.scrollTop"
        )
        <= 2
    )
    assert incoming.evaluate(
        "message => message.getBoundingClientRect().bottom <= message.closest('.lf-page-thread').querySelector('.lf-thread-reply').getBoundingClientRect().top"
    )

    transcript.evaluate("list => list.scrollTop -= 10")
    earlier = transcript.evaluate("list => list.scrollTop")
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": LONG_THREAD_ROOT["id"],
            "text": "A later answer should not interrupt earlier reading.",
        },
    )
    told(page)
    assert transcript.evaluate("list => list.scrollTop") == pytest.approx(
        earlier, abs=2
    )


def test_the_margin_reply_keeps_its_shape_when_the_user_enters_it(browser, serve):
    """The compact reply keeps its box and face when the user enters it."""
    # The reply's box and face are geometry, the same in either scheme.
    color_scheme = "light"
    page = open_page(
        browser,
        serve(OBLIGATION_PAGE, events=[COMMENT_ON_OBLIGATION]),
        color_scheme=color_scheme,
    )
    resized(page, 1440, 900)
    page.locator('.lf-margin-marker[data-lf-kinds~="comment"]').click()

    preview = page.locator(".lf-margin-preview")
    reply = preview.get_by_role("textbox", name="Reply", exact=True)
    expect(reply).to_be_visible()
    resting_box = reply.bounding_box()
    field = preview.locator(".lf-thread-reply .lf-compose-field")
    resting_field_box = field.bounding_box()
    message_left = preview.locator(".lf-msg").first.bounding_box()["x"]

    def text_left(control):
        return control.evaluate(
            """node => node.getBoundingClientRect().left + node.clientLeft
              + parseFloat(getComputedStyle(node).paddingInlineStart)"""
        )

    resting_text_left = text_left(reply)
    # The field owns the border. Its words share the message column.
    assert resting_text_left == pytest.approx(message_left, abs=0.5)
    expect(field).to_have_css("border-top-style", "solid")
    resting_face = field.evaluate(
        """node => {
          const style = getComputedStyle(node);
          return [style.backgroundColor, style.borderRadius];
        }"""
    )

    reply.hover()
    expect(field).to_have_css("background-color", resting_face[0])
    reply.click()
    expect(reply).to_be_focused()
    assert reply.bounding_box() == pytest.approx(resting_box, abs=0.5)
    assert field.bounding_box() == pytest.approx(resting_field_box, abs=0.5)
    assert text_left(reply) == pytest.approx(resting_text_left, abs=0.5)
    assert preview.locator(".lf-thread-transcript").evaluate(
        "list => list.scrollWidth === list.clientWidth"
    )
    assert (
        field.evaluate(
            """node => {
          const style = getComputedStyle(node);
          return [style.backgroundColor, style.borderRadius];
        }"""
        )
        == resting_face
    )


def test_the_thread_card_s_transcript_is_its_scroller_when_it_opens(browser, serve):
    """The selected thread registers the message scrollport before input reaches it."""
    url = serve(PANEL_PAGE)
    panel_comment(
        serve.page_dir,
        "A long comment about capacity. " + "Review the capacity limit. " * 250,
        {"section": "how-cap"},
    )
    page = open_page(browser, url)
    resized(page, 1440, 700)
    scroller = """async () => {
      const regions = await window.__lfCheckApi();
      const list = document.querySelector('.lf-margin-preview .lf-thread-transcript');
      const box = regions.effectiveScroller('lf-margin-preview');
      return list && box === list ? 'transcript'
        : box === document.scrollingElement ? 'page' : box?.className;
    }"""
    assert page.evaluate(scroller) == "page"
    page.evaluate("""async () => {
      const regions = await window.__lfWidgetApi();
      window.__previewShifts = [];
      regions.watchReadingRegionTransitions(({phase, shifted}) => {
        if (phase === 'shift')
          window.__previewShifts.push(...shifted.map(({region}) => region.id));
      });
    }""")

    page.locator('.lf-margin-marker[data-lf-kinds~="comment"]').click()
    transcript = page.locator(".lf-margin-preview .lf-thread-transcript")
    expect(transcript).to_be_visible()
    # A shift is announced from the resize observer's delivery, after the layout that
    # opened the card; two frames later it has been heard if it is coming.
    page.evaluate(
        "() => new Promise(done => requestAnimationFrame(() => "
        "requestAnimationFrame(done)))"
    )
    assert page.evaluate("() => window.__previewShifts") == []
    assert page.evaluate(scroller) == "transcript"

    before = page.evaluate("() => document.scrollingElement.scrollTop")
    box = transcript.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.wheel(0, 400)
    page.wait_for_function(
        "() => document.querySelector('.lf-margin-preview .lf-thread-transcript').scrollTop > 0"
    )
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before


def test_anchored_thread_reading_keys_and_page_return(browser, serve):
    """The focused thread pages its own transcript; g p returns to the page
    without dismissing the card, and the next d pages the document."""
    url = serve(PANEL_PAGE)
    panel_comment(
        serve.page_dir,
        "A long comment about capacity. " + "Review the capacity limit. " * 250,
        {"section": "how-cap"},
    )
    context = browser.new_context(
        viewport={"width": 1440, "height": 700}, reduced_motion="reduce"
    )
    page = open_page(browser, url, context=context)
    marker = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    marker.click()
    preview = page.locator(".lf-margin-preview")
    expect(preview.locator(".lf-page-thread")).to_be_focused()
    transcript = preview.locator(".lf-thread-transcript")
    assert transcript.evaluate("box => box.scrollHeight > box.clientHeight")
    before = page.evaluate("() => document.scrollingElement.scrollTop")

    page.keyboard.press("d")
    assert transcript.evaluate("box => box.scrollTop") > 0
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before

    page.keyboard.press("g")
    page.keyboard.press("p")
    expect(preview).to_be_visible()
    assert page.evaluate("() => document.activeElement === document.body")

    preview.get_by_role("button", name="Dismiss thread view").focus()
    page.keyboard.press("g")
    page.keyboard.press("p")
    expect(preview).to_be_visible()
    assert page.evaluate("() => document.activeElement === document.body")
    page.keyboard.press("d")
    assert page.evaluate("() => document.scrollingElement.scrollTop") > before

    marker.focus()
    marker_page = page.evaluate("() => document.scrollingElement.scrollTop")
    page.keyboard.press("d")
    assert page.evaluate("() => document.scrollingElement.scrollTop") > marker_page


@pytest.mark.parametrize(
    ("text", "zoom"),
    [
        ("better; is there a way of shortening? or maybe we just remove it??", 1.1),
        ("Check the January failure mode before accepting this design. " * 3, 1),
    ],
    ids=["short-zoomed", "long"],
)
def test_a_sent_comment_keeps_its_text_viewport(browser, serve, text, zoom):
    """Sharing the editor's measure, the card holds the sent words inside its scrollport."""
    page = open_page(browser, serve(OBLIGATION_PAGE), init_script=MARGIN_EDITOR_ROOTS)
    resized(page, 1200, 900)
    page.evaluate("zoom => document.documentElement.style.zoom = zoom", zoom)
    send_anchored_comment(page, text.rstrip())
    reading = page.locator(".lf-margin-preview")
    overflow = reading.evaluate("""card => [...card.querySelectorAll('*')]
        .filter(node => node.clientWidth && /auto|scroll/.test(getComputedStyle(node).overflow))
        .filter(node => node.scrollWidth > node.clientWidth || node.scrollHeight > node.clientHeight)
        .map(node => ({class: node.className, width: node.clientWidth,
            scrollWidth: node.scrollWidth, height: node.clientHeight, scrollHeight: node.scrollHeight}))""")
    assert not overflow, overflow


def test_open_reply_keeps_its_top_after_card_moves_to_right_rail(browser, serve):
    """A draft opened below its target keeps its card's top once the rail widens."""
    sidebar_page = OBLIGATION_PAGE.replace(
        '<main class="layout-column">',
        '<main class="layout-column"><aside class="sidebar">Page reference</aside>',
        1,
    )
    page = open_page(browser, serve(sidebar_page, events=[COMMENT_ON_OBLIGATION]))
    resized(page, 1200, 900)
    page.locator('.lf-margin-marker[data-lf-kinds="comment"]').click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).not_to_have_attribute("data-lf-thread-placement", "right")
    preview.get_by_role("textbox", name="Reply", exact=True).click()
    editor = preview.locator("leaf-text")
    write(editor, "First line")

    # Tall enough that the card, beside its cluster, has room under it.
    resized(page, 1920, 1400)
    expect(preview).to_have_attribute("data-lf-thread-placement", "right")
    rendered(page)
    before = page.evaluate(CARD_AND_REPLY)
    assert before["cardBottom"] < before["foot"] - 40, before
    editor.press("End")
    editor.press("Shift+Enter")
    expect(editor).to_have_js_property("value", "First line\n")
    rendered(page)
    after = page.evaluate(CARD_AND_REPLY)
    assert after["editorBottom"] > before["editorBottom"] + 10, (before, after)
    for edge in ("cardTop", "turn", "editorTop"):
        assert after[edge] == pytest.approx(before[edge], abs=0.5), (
            edge,
            before,
            after,
        )


@pytest.mark.parametrize("size", [(800, 520), (1000, 600)])
def test_a_growing_draft_holds_its_card_s_side_and_the_editor_s_top(
    browser, serve, size
):
    """Each new line keeps the card on its side and the reply's first line where it was,
    until the card's foot meets the window's; further lines scroll inside the editor.
    No keystroke flips the card over its cluster (800x520 stands over it) or carries
    its first line along the boundary (1000x600 stands under it)."""
    page, _preview, editor = drafting_in_a_short_card(browser, serve, *size)
    held = page.evaluate(CARD_AND_REPLY)
    readings = [held]
    for _ in range(30):
        editor.press("Shift+Enter")
        rendered(page)
        readings.append(page.evaluate(CARD_AND_REPLY))
    cap = next(
        (
            i
            for i, now in enumerate(readings)
            if now["cardBottom"] >= now["foot"] - 0.01
        ),
        None,
    )
    assert cap is not None and cap > 0, readings
    for i, now in enumerate(readings):
        assert now["placement"] == held["placement"], (held, now)
        assert now["cardBottom"] <= now["foot"] + 0.5, now
        assert now["cardTop"] == pytest.approx(held["cardTop"], abs=0.5), (held, now)
        # At the first cap, the inner grid's fractional track can round by 1px.
        # Before and after that transition, the turn and editor stay still.
        reference = readings[cap] if i > cap else held
        tolerance = 1.5 if i == cap else 0.5
        for edge in ("turn", "editorTop"):
            assert now[edge] == pytest.approx(reference[edge], abs=tolerance), (
                reference,
                now,
            )
    last = readings[-1]
    assert last["cardBottom"] == pytest.approx(last["foot"], abs=0.5), last
    assert editor.evaluate("box => box.scrollHeight > box.clientHeight"), (
        "thirty lines never outgrew the editor's room"
    )


def test_scrolling_a_drafting_card_leaves_its_editor_s_height_alone(browser, serve):
    """The editor's height follows its words and the room the card has, never the
    scroll: a scroll carries the card whole, so a draft that fits keeps its lines."""
    page, _preview, editor = drafting_in_a_short_card(browser, serve, 1000, 600)
    write(editor, "First line\nSecond line")
    rendered(page)
    height = editor.evaluate("box => box.getBoundingClientRect().height")
    assert not editor.evaluate("box => box.scrollHeight > box.clientHeight")
    for step in range(3):
        page.evaluate("() => document.scrollingElement.scrollBy(0, 40)")
        rendered(page)
        assert editor.evaluate(
            "box => box.getBoundingClientRect().height"
        ) == pytest.approx(height, abs=0.5), step


def test_a_turn_arriving_leaves_the_card_being_read_where_it_stands(browser, serve):
    """A card being read holds its top: a turn longer than the room below it scrolls in
    inside the card rather than lifting the card's top over the words being read."""
    page = open_page(browser, serve(LONG_THREAD_PAGE, events=[LONG_THREAD_ROOT]))
    page.emulate_media(reduced_motion="reduce")
    resized(page, 1000, 600)
    page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    rendered(page)
    top = preview.evaluate("card => card.getBoundingClientRect().top")
    reply = append_carried_log_record(
        serve.page_dir,
        {k: v for k, v in LONG_THREAD[1].items() if k not in ("id", "ts")},
    )
    told(page)
    expect(preview.locator(f'[data-event="{reply["id"]}"]')).to_be_attached()
    rendered(page)
    assert preview.evaluate(
        "card => card.getBoundingClientRect().top"
    ) == pytest.approx(top, abs=0.5)
    assert preview.locator(".lf-thread-transcript").evaluate(
        "list => list.scrollHeight > list.clientHeight"
    )


@pytest.mark.parametrize("repeats", [2, 12])
def test_a_thread_uses_room_the_page_gives_it(browser, serve, repeats):
    """A scroll into room expands clipped turns, whether or not the whole thread fits."""
    source = leaf_page(
        "Room for a conversation",
        '<h1>Room for a conversation</h1><div style="height: 100vh"></div>'
        '<section id="open"><h2>The question</h2><p>What should this cost?</p></section>'
        '<div style="height: 200vh"></div>',
    )
    page = open_page(browser, serve(source, events=[LONG_THREAD_ROOT]))
    page.emulate_media(reduced_motion="reduce")
    resized(page, 1440, 864)
    marker = page.locator('[data-lf-margin-for="open"] .lf-margin-marker')
    marker.evaluate("node => scrollBy(0, node.getBoundingClientRect().top - 620)")
    rendered(page)
    marker.click()
    preview = page.locator(".lf-margin-preview")
    transcript = preview.locator(".lf-thread-transcript")
    rendered(page)
    top = preview.bounding_box()["y"]
    expect(preview).to_have_attribute("data-lf-thread-placement", "right")
    answer = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": LONG_THREAD_ROOT["id"],
            "text": "One shared geometry reading can simplify the render gate while "
            "individual tests keep their assertions. The experiment checks that "
            "taking those readings together still detects known faults. " * repeats,
        },
    )
    told(page)
    expect(transcript.locator(f'[data-event="{answer["id"]}"]')).to_be_attached()
    rendered(page)
    assert preview.bounding_box()["y"] == pytest.approx(top, abs=0.5)
    assert transcript.evaluate("node => node.scrollHeight > node.clientHeight")
    cramped = transcript.evaluate("node => node.clientHeight")
    page.evaluate("scrollBy(0, 400)")
    rendered(page)
    assert transcript.evaluate("node => node.clientHeight") > cramped + (
        150 if repeats == 2 else 300
    )
    if repeats == 2:
        assert transcript.evaluate("node => node.scrollHeight <= node.clientHeight + 1")
    assert preview.bounding_box()["y"] == pytest.approx(top - 400, abs=0.5)


def test_an_agent_reply_leaves_the_reply_being_typed_where_it_stands(browser, serve):
    """An agent answer waits behind a notice while the user writes in the card."""
    # The short card, where an arrival has the least room to take.
    size = (800, 520)
    page, preview, editor = drafting_in_a_short_card(browser, serve, *size)
    before = preview.evaluate(DRAFTING_CARD)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "parent": LONG_THREAD_ROOT["id"],
            "responds": LONG_THREAD_ROOT["id"],
            "text": "An agent answer arriving while the user types. " * 6,
        },
    )
    told(page)
    expect(preview.locator(".lf-thread-notice-news")).to_have_text("1 new reply")
    expect(preview).not_to_contain_text(
        "An agent answer arriving while the user types."
    )
    rendered(page)
    expect(editor).to_be_focused()
    assert preview.evaluate(DRAFTING_CARD) == before
    preview.locator(".lf-thread-notice-news").click()
    expect(preview).to_contain_text("An agent answer arriving while the user types.")
    rendered(page)
    assert preview.evaluate(DRAFTING_CARD) == before
    expect(editor).to_have_js_property("value", "words")


def test_an_agent_reply_into_an_open_card_cues_only_its_own_words(browser, serve):
    """A turn arriving in a card the user has open wears the cue a sent turn wears,
    once and on its own words; opening the card cues nothing it already held."""
    page = open_page(browser, serve(LONG_THREAD_PAGE, events=[LONG_THREAD_ROOT]))
    page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    rendered(page)
    cued = """preview => [...preview.querySelectorAll('.lf-msg')].filter(message =>
      message.getAnimations().some(animation =>
        animation.effect.getKeyframes().some(frame => frame['--lf-msg-arrival'])))
      .map(message => message.textContent.includes('arriving') ? 'reply' : 'root')"""
    assert preview.evaluate(cued) == []
    # Pause the cue at its first frame, before driver latency can let it finish.
    preview.evaluate(
        """preview => {
          window.__arrival = null;
          const observer = new MutationObserver(() => {
            const message = [...preview.querySelectorAll('.lf-msg')].find(node =>
              node.textContent.includes('arriving'));
            if (!message) return;
            const cue = message.getAnimations().find(animation =>
              animation.effect.getKeyframes().some(frame => frame['--lf-msg-arrival']));
            if (cue) { cue.pause(); cue.currentTime = 0; }
            window.__arrival = Boolean(cue);
            observer.disconnect();
          });
          observer.observe(preview, {subtree: true, childList: true, attributes: true});
        }"""
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "parent": LONG_THREAD_ROOT["id"],
            "responds": LONG_THREAD_ROOT["id"],
            "text": "An agent answer arriving while the card is open.",
        },
    )
    told(page)
    page.wait_for_function("() => window.__arrival !== null")
    assert page.evaluate("() => window.__arrival")
    assert preview.evaluate(cued) == ["reply"]


@pytest.mark.parametrize(("size", "how"), [((1200, 900), "key"), ((800, 520), "press")])
def test_a_sent_reply_leaves_the_reply_row_where_it_stands(browser, serve, size, how):
    """Sending keeps the reply's foot through admission, then releases it for news
    and the next draft. Clearing several lines may lower the editor's top, but cannot
    move its foot, the card's column, or the page, even for one frame."""
    page, preview, editor = drafting_in_a_short_card(browser, serve, *size)
    write(editor, "First point.\nSecond point.\nThird point.")
    rendered(page)
    preview.evaluate("""card => {
      const read = () => {
        const box = card.getBoundingClientRect();
        const reply = card.querySelector('leaf-text').getBoundingClientRect();
        const latest = card.querySelector('.lf-msg:last-child');
        return {side: card.dataset.lfThreadPlacement,
          left: box.left, width: box.width, top: box.top, foot: box.bottom,
          editorTop: reply.top, editorFoot: reply.bottom, pageScroll: scrollY,
          pending: latest?.getAttribute('aria-busy') === 'true'};
      };
      const sample = () => {
        window.replyMotion.frames.push(read());
        window.replyMotion.frame = requestAnimationFrame(sample);
      };
      window.replyMotion = {read, frames: [],
        start() {
          this.frames = [];
          this.frame = requestAnimationFrame(sample);
        },
        stop() {
          cancelAnimationFrame(this.frame);
          return {frames: this.frames, settled: read()};
        }};
    }""")

    def observe():
        return page.evaluate("replyMotion.read()")

    def begin():
        page.evaluate("replyMotion.start()")

    def finish(before, *fixed):
        rendered(page)
        page.wait_for_function("replyMotion.frames.length > 0")
        reading = page.evaluate("replyMotion.stop()")
        for after in [*reading["frames"], reading["settled"]]:
            assert after["side"] == before["side"], reading
            for edge in ("left", "width", "pageScroll", *fixed):
                assert after[edge] == pytest.approx(before[edge], abs=0.5), (
                    edge,
                    before,
                    reading,
                )
        return reading["settled"]

    before = observe()
    send = preview.locator(".lf-thread-reply .lf-compose-submit")
    held = []

    def hold_reply(route):
        if route.request.post_data_json["kind"] == "reply":
            held.append(route)
        else:
            route.continue_()

    page.route("**/api/event", hold_reply)
    begin()
    if how == "key":
        editor.press("Enter")
    else:
        send.click()
    holding(page, held, 1, "the reply")
    expect(preview.locator(".lf-msg").last).to_contain_text("Third point.")
    expect(preview.locator(".lf-msg").last).to_have_attribute("aria-busy", "true")
    rendered(page)
    expect(preview.locator(".lf-page-thread")).to_be_focused()
    page.wait_for_function("replyMotion.frames.some(frame => frame.pending)")
    pending = finish(before, "editorFoot")
    assert pending["editorTop"] > before["editorTop"] + 20, (before, pending)

    # Admission names the same turn; its later sizing passes still hold the pressed row.
    begin()
    held.pop().continue_()
    round_trip(page)
    expect(preview.locator(".lf-msg").last).not_to_have_attribute("aria-busy", "true")
    page.wait_for_function("replyMotion.frames.some(frame => !frame.pending)")
    accepted = finish(pending, "top", "foot", "editorTop", "editorFoot")
    page.unroute_all(behavior="wait")

    # A later answer uses the card's reading edge, rather than the sent reply's foot.
    begin()
    answer = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "parent": LONG_THREAD_ROOT["id"],
            "responds": preview.locator(".lf-msg").last.get_attribute("data-event"),
            "text": "Noted.",
        },
    )
    told(page)
    if accepted["side"] == "above":
        notice = preview.locator(".lf-thread-notice-news")
        expect(notice).to_have_text("1 new reply")
        finish(accepted, "top", "foot", "editorTop", "editorFoot")
        begin()
        notice.click()
    expect(preview.locator(f'[data-event="{answer["id"]}"]')).to_be_attached()
    reading_edge = "foot" if accepted["side"] == "above" else "top"
    answered = finish(accepted, reading_edge)
    if reading_edge == "top":
        assert answered["editorFoot"] > accepted["editorFoot"] + 10, (
            accepted,
            answered,
        )

    # A fresh draft grows down from its first line, then scrolls within the card.
    editor.click()
    rendered(page)
    drafting = observe()
    begin()
    page.keyboard.insert_text("The next point.\nAnother line.")
    grown = finish(drafting, "top", "editorTop")
    assert grown["editorFoot"] > drafting["editorFoot"] + 10, (drafting, grown)
    write(editor, "\n".join(f"More detail {line}." for line in range(60)))
    rendered(page)
    bounded = observe()
    assert bounded["side"] == grown["side"]
    for edge in ("left", "width", "pageScroll"):
        assert bounded[edge] == pytest.approx(grown[edge], abs=0.5), (grown, bounded)
    assert editor.evaluate("box => box.scrollHeight > box.clientHeight")
    assert (
        bounded["top"]
        <= bounded["editorTop"]
        < bounded["editorFoot"]
        <= bounded["foot"]
    )
    assert 0 <= bounded["top"] < bounded["foot"] <= size[1]
    expect(editor).to_be_focused()


@pytest.mark.parametrize(
    "window",
    [
        {"viewport": {"width": 1280, "height": 800}},
        {
            "viewport": {"width": 390, "height": 844},
            "is_mobile": True,
            "has_touch": True,
        },
    ],
    ids=["desktop", "phone"],
)
def test_a_thread_card_reply_stays_in_the_visible_viewport(browser, serve, window):
    """Zooming in, like a phone's software keyboard, shrinks the visible viewport without
    resizing the window, and a card whose reply the user is writing stands inside what
    is left, clear of the floating panel. The zoom stands in for the keyboard, which no
    emulation raises; the card starts low in the window, where the shrunk viewport no
    longer reaches."""
    filler = "".join(f"<p>Filler paragraph {i}.</p>" for i in range(14))
    after = "".join(f"<p>After {i}.</p>" for i in range(30))
    source = leaf_page(
        "card in a shrunk viewport",
        f'<h1 id="t">Card</h1>{filler}<p id="low">The paragraph a thread is on.</p>'
        f"{after}",
    )
    context = browser.new_context(**window)
    page = open_page(
        browser, serve(source, events=[_comment_on("low")]), context=context
    )
    margins_laid_out(page)
    page.locator("#low").evaluate(
        "p => scrollBy(0, p.getBoundingClientRect().top - innerHeight * 0.55)"
    )
    rendered(page)
    page.locator('[data-lf-margin-for="low"] .lf-margin-marker').click()
    card = page.locator(".lf-margin-preview")
    expect(card).to_be_visible()
    card.get_by_role("textbox", name="Reply", exact=True).click()
    expect(card.locator("leaf-text")).to_be_focused()

    def stands_in_the_visible_viewport():
        rendered(page)
        room = page.evaluate("""() => {
          const panel = document.querySelector('.lf-floating-panel').getBoundingClientRect();
          const v = visualViewport;
          const card = document.querySelector('.lf-margin-preview').getBoundingClientRect();
          const across = panel.left < card.right && card.left < panel.right;
          return {
            card: card.toJSON(),
            top: v.offsetTop,
            bottom: Math.min(v.offsetTop + v.height, across ? panel.top : Infinity),
            left: v.offsetLeft,
            right: v.offsetLeft + v.width,
            scrolled: [scrollY, v.offsetTop],
          };
        }""")
        shown = room["card"]
        assert shown["top"] >= room["top"], room
        assert shown["bottom"] <= room["bottom"], room
        assert shown["left"] >= room["left"], room
        assert shown["right"] <= room["right"], room
        return room

    context.new_cdp_session(page).send(
        "Emulation.setPageScaleFactor", {"pageScaleFactor": 1.6}
    )
    page.wait_for_function("Math.abs(visualViewport.scale - 1.6) < 0.01")
    before = stands_in_the_visible_viewport()
    # A wheel over the page moves the visible viewport inside the window, which scrolls
    # nothing the document hears.
    page.mouse.move(4, 150)
    page.mouse.wheel(0, 120)
    page.wait_for_function("visualViewport.offsetTop > 0")
    after = stands_in_the_visible_viewport()
    assert after["scrolled"][0] == before["scrolled"][0], (before, after)


def test_resizing_a_focused_editor_keeps_the_pane_the_reader_scrolled_away(
    browser, serve
):
    """External room changes reveal within the editor, without treating retained
    focus as permission to bring the surrounding reading pane back."""
    page = open_page(browser, serve(PANE_PIN_PAGE))
    resized(page, 1440, 600)
    pane_scroll_behavior(page, page.locator("#pin-pane"), "bounded")
    page.evaluate("""() => {
      const body = document.querySelector('#pin-pane > div');
      body.style.overflowAnchor = 'none';
      const input = document.createElement('leaf-text');
      input.id = 'resized-editor';
      input.className = 'lf-ui';
      input.style.cssText = 'height:100px;max-height:100px;overflow:auto';
      body.prepend(input);
      input.value = 'Words\\n'.repeat(40);
      input.focus();
    }""")
    rendered(page)
    pane = page.locator("#pin-pane > div")
    pane.evaluate("body => body.scrollTop = 400")
    rendered(page)
    before = pane.evaluate("body => body.scrollTop")
    assert before == 400
    editor = page.locator("#resized-editor")
    expect(editor).to_be_focused()
    editor.evaluate("input => input.style.height = '80px'")
    rendered(page)
    assert editor.bounding_box()["height"] == pytest.approx(80)
    assert pane.evaluate("body => body.scrollTop") == before


@pytest.mark.parametrize("pending", [False, True], ids=["accepted", "pending"])
def test_sending_during_a_stream_keeps_later_tokens_from_moving_the_reading(
    browser, serve, request, pending
):
    """An ongoing answer keeps its identity across the user's interjection. Its later
    tokens stay live, growing down from the reading whether Send has been accepted or
    is still pending. They need no news press and may move the empty reply row down."""
    from browser.threads import claim_for_codex, stream_reply

    url = serve(LONG_THREAD_PAGE, events=[LONG_THREAD_ROOT])
    root = LONG_THREAD_ROOT["id"]
    claim_for_codex(serve.page_dir, request)
    stream_reply(serve.page_dir, root, "The answer has started.")
    page = open_page(browser, url)
    resized(page, 1440, 900)
    page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
    card = page.locator(".lf-margin-preview")
    streamed = card.locator(".lf-msg.agent .lf-msg-text")
    expect(streamed).to_have_text("The answer has started.")

    read_positions = """card => ({
          card: card.getBoundingClientRect().top,
          messages: [...card.querySelectorAll('.lf-msg')]
            .map(node => node.getBoundingClientRect().top),
          reply: card.querySelector('.lf-thread-reply').getBoundingClientRect().bottom
        })"""

    def positions():
        return card.evaluate(read_positions)

    write(
        card.get_by_role("textbox", name="Reply", exact=True), "Also include the date."
    )
    expect(card.locator("leaf-text")).to_be_focused()
    waiting = "The answer has started. " + (
        "Additional words that wrap the ongoing answer. " * 2
    )
    stream_reply(serve.page_dir, root, waiting)
    told(page)
    expect(card.locator(".lf-thread-notice-news")).to_have_text("1 new reply")
    expect(streamed).to_have_text("The answer has started.")
    expect(card.locator("leaf-text")).to_be_focused()
    rendered(page)
    before_send = positions()
    held = []

    def hold_reply(route):
        if route.request.post_data_json.get("kind") == "reply":
            held.append(route)
        else:
            route.continue_()

    page.route("**/api/event", hold_reply)
    card.locator(".lf-thread-reply .lf-compose-submit").click()
    holding(page, held, 1, "the reply")
    sent = card.locator(".lf-msg.user").filter(has_text="Also include the date.")
    expect(sent).to_be_visible()
    expect(sent).to_have_attribute("aria-busy", "true")
    expect(streamed).to_have_text(waiting.strip())
    expect(card.locator(".lf-thread-notice-news")).to_have_count(0)
    rendered(page)
    assert positions()["reply"] == pytest.approx(before_send["reply"], abs=0.5)
    if not pending:
        held.pop().continue_()
        round_trip(page)
        expect(sent).not_to_have_attribute("aria-busy", "true")
    rendered(page)
    # The send's own motion ends before the tokens the reading is measured against.
    page.wait_for_function(CARD_AT_REST)

    def stream_tokens(repetitions):
        text = "The answer has started. " + (
            "Additional words that wrap the ongoing answer. " * repetitions
        )
        stream_reply(serve.page_dir, root, text)
        told(page)
        expect(streamed).to_have_text(text.strip())
        rendered(page)
        expect(card.locator(".lf-thread-notice-news")).to_have_count(0)

    def append_tokens(repetitions):
        before = positions()
        stream_tokens(repetitions)
        after = positions()
        assert after["card"] == pytest.approx(before["card"], abs=0.5)
        assert after["messages"] == pytest.approx(before["messages"], abs=0.5)
        assert after["reply"] > before["reply"] + 10, (before, after)

    before_stream = positions()
    page.evaluate(
        """() => {
          const read = """
        + read_positions
        + """;
          window.streamMotion = {active: true, frames: []};
          const sample = () => {
            if (!streamMotion.active) return;
            streamMotion.frames.push(read(document.querySelector('.lf-margin-preview')));
            requestAnimationFrame(sample);
          };
          requestAnimationFrame(sample);
        }"""
    )
    append_tokens(8)
    frames = page.evaluate("""() => {
      streamMotion.active = false;
      return streamMotion.frames;
    }""")
    assert frames
    for frame in frames:
        assert frame["card"] == pytest.approx(before_stream["card"], abs=0.5)
        assert frame["messages"] == pytest.approx(before_stream["messages"], abs=0.5)
    if pending:
        expect(sent).to_have_attribute("aria-busy", "true")
        held.pop().continue_()
        round_trip(page)
        expect(sent).not_to_have_attribute("aria-busy", "true")
        rendered(page)
    page.unroute_all(behavior="wait")
    append_tokens(12)

    # Once the transcript fills the card, reading back wins over following its end.
    stream_tokens(80)
    transcript = card.locator(".lf-thread-transcript")
    assert transcript.evaluate("node => node.scrollHeight > node.clientHeight")
    transcript.hover()
    page.mouse.wheel(0, 300)
    page.wait_for_function(
        "document.querySelector('.lf-margin-preview .lf-thread-transcript').scrollTop > 200"
    )
    scroll_settled(page, ".lf-margin-preview .lf-thread-transcript")
    down = transcript.evaluate("node => node.scrollTop")
    page.mouse.wheel(0, -120)
    page.wait_for_function(
        "before => document.querySelector('.lf-margin-preview .lf-thread-transcript').scrollTop < before",
        arg=down,
    )
    scroll_settled(page, ".lf-margin-preview .lf-thread-transcript")

    def reading():
        return card.evaluate("""card => {
          const transcript = card.querySelector('.lf-thread-transcript');
          const bounds = transcript.getBoundingClientRect();
          const words = card.querySelector('.lf-msg.agent .lf-msg-text');
          const walker = document.createTreeWalker(words, NodeFilter.SHOW_TEXT);
          const range = document.createRange();
          let text, offset = 0;
          while ((text = walker.nextNode())) {
            range.selectNodeContents(text);
            const lines = [...range.getClientRects()];
            const index = lines.findIndex(line =>
              line.top >= bounds.top && line.bottom <= bounds.bottom);
            if (index >= 0) return {
              card: card.getBoundingClientRect().top,
              scroll: transcript.scrollTop,
              offset, line: index, top: lines[index].top
            };
            offset += text.length;
          }
        }""")

    before = reading()
    assert before is not None
    stream_tokens(100)
    assert reading() == pytest.approx(before, abs=0.5)
