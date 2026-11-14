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
from render_cases_layout import NAMED, ring_faults, rings_drawn, solid_png
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
    CARD_AT_REST,
    CARD_OUTLINE,
    CARD_RELEASED,
    COMMENT_ON_OBLIGATION,
    DRAFTING_CARD,
    LONG_THREAD,
    LONG_THREAD_PAGE,
    LONG_THREAD_ROOT,
    LOW_PASSAGE_PAGE,
    MARGIN_EDITOR_ROOTS,
    PANE_PIN_PAGE,
    _comment_on,
    _focused_editor_caret,
    drafting_in_a_short_card,
    open_long_thread,
    send_anchored_comment,
)
from leaf import media as media_model
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
    expect(card.locator("leaf-text")).to_be_focused()
    # The click puts the caret in the reply (thread/focus.js, `openingPart`); Escape
    # stands the user on the thread.
    page.keyboard.press("Escape")
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
        # The card follows document scrolling during rendering. Read its delivered
        # position before deciding whether another press is needed.
        rendered(page)
    expect(card.locator(".lf-page-thread")).to_be_focused()
    assert not card.evaluate("card => card.getBoundingClientRect().bottom > 0"), {
        "scroll": page.evaluate("scrollY"),
        "card": card.evaluate("card => card.getBoundingClientRect().toJSON()"),
    }
    for key in ("d", "u"):
        page_at = page.evaluate("scrollY")
        page.keyboard.press(key)
        moved = page.evaluate("scrollY") - page_at
        assert moved > 20 if key == "d" else moved < -20, {
            "key": key,
            "before": page_at,
            "moved": moved,
            "geometry": card.evaluate("""card => ({
                scroll: scrollY,
                limit: document.scrollingElement.scrollHeight - innerHeight,
                card: card.getBoundingClientRect().toJSON(),
                transcript: card.querySelector('.lf-thread-transcript').scrollTop,
            })"""),
        }


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
    # The focused thread names the card as the box that shows its focus
    # (`--lf-focus-box`), so the card's ring is the one a control's focus marks.
    assert "[data-lf-control-focus-visible]" in worn[0][1], drawn
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
    """Next On Me lands on the agent's long question in its card, and the card wears
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
    message = page.locator(
        f'.lf-margin-preview .lf-msg[data-lf-event="{question["id"]}"]'
    )
    expect(message).to_be_focused()
    rendered(page)
    drawn = rings_drawn(page)
    worn = [seen["who"].split(" ")[0] for seen in drawn if seen["here"]]
    assert worn == ["div.lf-margin-preview-card"], drawn
    assert not (faults := ring_faults(drawn, "on the reply Next On Me reached")), (
        "\n".join(faults)
    )


def test_next_on_me_rings_the_options_a_card_message_asks_with_whole(browser, serve):
    """Next On Me lands on the options a reply in a card asks with, and their location
    ring stands whole inside the card's transcript. The ring stands a region's gap out,
    and the transcript kept only a control's room past its sides, so it cut the ring's
    whole inline end and the foot of its corners."""
    question = {
        "kind": "reply",
        "author": "agent",
        "agent": "Claude",
        "parent": LONG_THREAD_ROOT["id"],
        "responds": LONG_THREAD_ROOT["id"],
        "revision": 1,
        "text": "Shall I merge it?",
        "markup": '<lf-options id="merge" choose>'
        '<lf-option id="merge-go"><strong>Merge it once CI passes</strong></lf-option>'
        '<lf-option id="merge-read"><strong>I will read the diff first</strong>'
        "</lf-option></lf-options>",
        "id": "b" * 32,
    }
    page = open_page(
        browser, serve(LONG_THREAD_PAGE, events=[LONG_THREAD_ROOT, question])
    )
    page.emulate_media(reduced_motion="reduce")
    resized(page, 1440, 900)
    page.keyboard.press("m")
    options = page.locator(".lf-margin-preview lf-options#merge")
    expect(options).to_be_focused()
    expect(options).to_have_attribute("data-lf-projected-location", "")
    drawn = rings_drawn(page)
    assert any(seen["who"] == options.evaluate(NAMED) for seen in drawn), drawn
    assert not (faults := ring_faults(drawn, "on the options Next On Me reached")), (
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
    """The long thread's margin card with the user in its reply box, where the click
    that opened it put them. Scroll anchoring is off on the transcript, so every move
    read is the runtime's own."""
    page, preview, transcript = open_long_thread(browser, serve)
    transcript.evaluate("list => list.style.overflowAnchor = 'none'")
    editor = preview.locator("leaf-text")
    expect(editor).to_be_focused()
    rendered(page)
    return page, preview, editor, transcript


# Where a card's reply box stands: its top and its foot.
REPLY_BOX = """card => {
  const box = card.querySelector('.lf-thread-reply leaf-text').getBoundingClientRect();
  return [box.top, box.bottom];
}"""


def agent_says(page, page_dir, words):
    """The agent's reply to the long thread's opening comment, told to the page."""
    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": LONG_THREAD_ROOT["id"],
            "revision": 1,
            "text": words,
        },
    )
    told(page)


@pytest.mark.parametrize(
    ("size", "side"), [((1440, 900), "right"), ((1000, 600), "below")]
)
def test_news_at_a_card_s_end_shows_where_its_held_edge_keeps_the_reply_still(
    browser, serve, size, side
):
    """The caret a click's opening leaves in the empty box holds no line, so the card
    keeps its top and the answer the user waits for shows at once, growing the card
    down past the box. Once the user types there, a card beside its words holds its
    foot, so an answer shows at once and grows it up, the box staying where it stood; a
    card under its words keeps its top, so an answer waits behind the card's notice
    (thread-preview.js, `heldEdge`, `endNewsMoves`)."""
    page = open_page(browser, serve(LONG_THREAD_PAGE, events=[LONG_THREAD_ROOT]))
    resized(page, *size)
    page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_have_attribute("data-lf-thread-placement", side)
    box = preview.locator(".lf-thread-reply leaf-text")
    expect(box).to_be_focused()
    rendered(page)
    resting = preview.evaluate(REPLY_BOX)

    agent_says(
        page, serve.page_dir, "They are hard to follow because each closes elsewhere."
    )
    expect(preview.locator(".lf-msg", has_text="each closes elsewhere")).to_be_visible()
    expect(preview.locator(".lf-thread-news:visible")).to_have_count(0)
    rendered(page)
    shown = preview.evaluate(REPLY_BOX)
    assert shown[0] > resting[0] + 10, (resting, shown)

    page.keyboard.type("Which")
    rendered(page)
    typed = preview.evaluate(REPLY_BOX)
    agent_says(page, serve.page_dir, "One more thing about the second layer.")
    if side == "below":
        expect(preview.locator(".lf-thread-news")).to_have_text("1 new")
        expect(preview.locator(".lf-msg", has_text="One more thing")).to_have_count(0)
    else:
        expect(preview.locator(".lf-msg", has_text="One more thing")).to_be_visible()
        expect(preview.locator(".lf-thread-news:visible")).to_have_count(0)
    rendered(page)
    assert preview.evaluate(REPLY_BOX) == pytest.approx(typed, abs=0.5)


def test_news_under_a_card_s_words_waits_once_the_user_begins_in_the_box_a_send_left(
    browser, serve
):
    """Under its words a card keeps its top, so news at its end moves the reply box
    down. The box Send leaves the caret in lets the answer the user waits for show
    until they begin a reply there (thread-preview.js, `endNewsMoves`;
    thread/replies.js): by typing, even words they erase, or by coming back to it."""
    page = open_page(browser, serve(LONG_THREAD_PAGE, events=[LONG_THREAD_ROOT]))
    resized(page, 1000, 600)
    page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_have_attribute("data-lf-thread-placement", "below")
    box = preview.locator(".lf-thread-reply leaf-text")
    expect(box).to_be_focused()
    news = preview.locator(".lf-thread-news")

    def send(words):
        page.keyboard.type(words)
        with sending(page, "the turn"):
            page.keyboard.press("ControlOrMeta+Enter")
        rendered(page)
        expect(box).to_be_focused()

    send("First.")
    agent_says(page, serve.page_dir, "Shown beside the empty box.")
    expect(preview.locator(".lf-msg", has_text="Shown beside")).to_be_visible()
    page.keyboard.type("W")
    page.keyboard.press("Backspace")
    expect(box).to_have_js_property("value", "")
    agent_says(page, serve.page_dir, "Held once a word was typed.")
    expect(news).to_have_text("1 new")

    send("Second.")
    agent_says(page, serve.page_dir, "Shown again after the send.")
    expect(preview.locator(".lf-msg", has_text="Shown again")).to_be_visible()
    page.keyboard.press("Escape")
    expect(preview.locator(".lf-page-thread")).to_be_focused()
    page.keyboard.press("Enter")
    expect(box).to_be_focused()
    agent_says(page, serve.page_dir, "Held once they came back.")
    expect(news).to_have_text("1 new")


def test_replying_on_a_long_margin_card_keeps_the_turn_being_read(browser, serve):
    """Entering the visible reply box preserves the earlier transcript reading."""
    page, preview, transcript = open_long_thread(browser, serve)
    transcript.evaluate("list => list.style.overflowAnchor = 'none'")
    page.keyboard.press("Escape")
    expect(preview.locator(".lf-page-thread")).to_be_focused()
    rendered(page)
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


def test_a_card_send_grows_the_card_down_past_what_the_user_read(browser, serve):
    """A send from a margin card beside its words, with room below it, keeps the
    card's outline, its head row and the turn already there where they stood, from the
    send's first frame to rest: the sent turn joins under them and the reply box moves
    down, rather than the whole transcript moving up (thread-preview.js). Read at the
    first frame, held, and again at rest."""
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
    assert drawn[:3] == pytest.approx(stood, abs=1), (stood, drawn)
    assert rest[:3] == pytest.approx(stood, abs=1), (stood, rest)
    assert rest[3] > stood[2] + 10, (stood, rest)


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
            "responds": preview.locator(".lf-msg").last.get_attribute("data-lf-event"),
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
    write(editor, "A first line.\n")
    rendered(page)
    page.evaluate("() => {" + HOLD_MOTION + "}")
    # The line given up shrinks the card over the tween.
    page.keyboard.press("Backspace")
    page.wait_for_function("() => window.__lfHeld.some(m => m.playState !== 'idle')")
    close = preview.locator(".lf-margin-preview-close").bounding_box()
    page.mouse.click(close["x"] + close["width"] / 2, close["y"] + close["height"] / 2)
    expect(preview).to_be_hidden()


# The long thread's opening comment, the agent's two steps of progress on it and the
# user's turn after them, which fold the steps behind "Show 2 progress messages".
STEPPED_THREAD = [
    LONG_THREAD_ROOT,
    *(
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": LONG_THREAD_ROOT["id"],
            "revision": 1,
            "text": words,
            "ephemeral": True,
        }
        for words in ("Comparing the two layers.", "Checking where each one closes.")
    ),
    {
        "kind": "reply",
        "author": "user",
        "parent": LONG_THREAD_ROOT["id"],
        "revision": 1,
        "text": "And check the third?",
    },
]


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_press_that_changes_the_edge_holding_a_card_moves_it_from_where_it_stood(
    engine, request, serve
):
    """A card read beside its passage, whose foot stands within a line of where the
    window's foot holds a card, is held by that foot once a press shows its progress,
    and stands beside its passage again once a press hides it, which travels. The
    travel starts from where the card stood held: at the motion's first frame its
    outline and head row are drawn where they were, and at rest the card has moved
    down. Read by the edge holding the card after the press, its placement's move
    read as the page carrying it, which drew it part of a line lower for a frame before
    it travelled back (reported on 31 October 2026 in Firefox, for a line a key took
    from the reply, which beside its passage now holds the card's foot instead:
    thread-preview.js, `heldEdge`)."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(LOW_PASSAGE_PAGE, events=STEPPED_THREAD),
    )
    page.emulate_media(reduced_motion="no-preference")
    resized(page, 1440, 900)
    page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    page.keyboard.press("Escape")
    expect(preview.locator(".lf-page-thread")).to_be_focused()
    disclosure = preview.locator(".lf-summary-expand")
    expect(disclosure).to_have_text("Show 2 progress messages")

    def foot_after_scrolling(by):
        page.evaluate("by => document.scrollingElement.scrollBy(0, by)", by)
        scroll_settled(page)
        rendered(page)
        page.wait_for_function(CARD_AT_REST)
        box = preview.bounding_box()
        return box["y"] + box["height"]

    # The passage at the window's foot stands the card against it; scrolled well up,
    # the card stands beside its passage, and a scroll back stands its foot half a line
    # above where the window's holds it.
    page.locator("#open").evaluate("node => node.scrollIntoView({block: 'end'})")
    held = foot_after_scrolling(0)
    beside = foot_after_scrolling(400)
    assert beside < held - 100, (held, beside)
    assert foot_after_scrolling(-(held - 10 - beside)) == pytest.approx(
        held - 10, abs=1
    )
    page.evaluate("() => {" + HOLD_MOTION + "}")
    stood = preview.evaluate(CARD_DRAWN)
    disclosure.click()
    expect(disclosure).to_have_text("Hide 2 progress messages")
    rendered(page)
    page.wait_for_function(CARD_RELEASED)
    held_up = preview.evaluate(CARD_DRAWN)
    assert held_up[0] < stood[0] - 5, (
        f"the progress held the card nowhere: {stood} -> {held_up}"
    )
    disclosure.click()
    expect(disclosure).to_have_text("Show 2 progress messages")
    page.wait_for_function(
        "() => window.__lfHeld.some(motion => motion.playState !== 'idle')"
    )
    drawn = preview.evaluate(CARD_DRAWN)
    page.wait_for_function(CARD_RELEASED)
    rest = preview.evaluate(CARD_DRAWN)
    assert rest[0] > held_up[0] + 5, f"the progress went and the card stayed: {rest}"
    # The transcript changed size, so its turns show where they now stand (box-motion.js).
    assert drawn[:2] == pytest.approx(held_up[:2], abs=1), f"{held_up} -> {drawn}"


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_card_a_scroll_moves_onto_or_off_the_windows_foot_as_it_resizes_only_resizes(
    engine, request, serve
):
    """A card that a scroll moves in the frame it changes size starts its motion where
    its placement would have stood it at its old size, so no frame draws it past the
    window's foot or cuts its head row. Taken off the foot as it grew, the card was drawn
    with its foot already at rest and grew up to its head, half its head row hidden at
    first. Carried past the foot as it shrank, it was drawn below the window's foot for
    a frame and rose back to it, whether or not the foot held it before or after. The
    user reads on the thread, where the card holds its top (thread-preview.js,
    `heldEdge`)."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(LOW_PASSAGE_PAGE, events=[LONG_THREAD_ROOT]),
    )
    page.emulate_media(reduced_motion="no-preference")
    resized(page, 1440, 900)
    page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    page.keyboard.press("Escape")
    expect(preview.locator(".lf-page-thread")).to_be_focused()
    transcript = preview.locator(".lf-thread-transcript")

    def foot_after_scrolling(by):
        page.evaluate("by => document.scrollingElement.scrollBy(0, by)", by)
        scroll_settled(page)
        rendered(page)
        page.wait_for_function(CARD_AT_REST)
        return preview.evaluate(CARD_OUTLINE)[1]

    def scroll_resizing(by, padding):
        """Where the card's outline is drawn at the first frame of the motion a scroll
        and a change of its size in one frame start, and where it rests."""
        transcript.evaluate(
            """(node, [by, padding]) => new Promise(done => requestAnimationFrame(() => {
              document.scrollingElement.scrollBy(0, by);
              node.style.paddingBottom = padding;
              done();
            }))""",
            [by, padding],
        )
        page.wait_for_function(
            "() => window.__lfHeld.some(motion => motion.playState !== 'idle')"
        )
        drawn = preview.evaluate(CARD_OUTLINE)
        page.wait_for_function(CARD_RELEASED)
        return drawn, preview.evaluate(CARD_OUTLINE)

    def standing(passage, padding):
        """The card at rest, a `padding` taller, with its passage's top at `passage`."""
        transcript.evaluate(
            "(node, padding) => { node.style.paddingBottom = padding; }", padding
        )
        top = page.locator("#open").evaluate("node => node.getBoundingClientRect().top")
        page.evaluate("by => document.scrollingElement.scrollBy(0, by)", top - passage)
        scroll_settled(page)
        rendered(page)
        page.wait_for_function(CARD_RELEASED)
        return preview.evaluate(CARD_OUTLINE)

    # The passage at the window's foot stands the card against it. A scroll down, with
    # the card a little taller, stands it beside its passage by its head; a scroll back,
    # at its old size, against the foot again.
    page.locator("#open").evaluate("node => node.scrollIntoView({block: 'end'})")
    held = foot_after_scrolling(0)
    page.evaluate("() => {" + HOLD_MOTION + "}")
    drawn, rest = scroll_resizing(200, "20px")
    assert rest[1] < held - 20, f"still held at the foot: {rest}, {held}"
    assert drawn[0] == pytest.approx(rest[0], abs=1), f"{drawn} -> {rest}"
    assert drawn[1] < rest[1] - 5, f"its growth did not travel: {drawn} -> {rest}"
    drawn, rest = scroll_resizing(-200, "0px")
    assert rest[1] == pytest.approx(held, abs=1), f"held nowhere: {rest}, {held}"
    assert drawn[1] == pytest.approx(held, abs=1), f"{drawn} -> {rest}"
    # A card the foot holds for its height, and one standing beside its passage, each
    # carried down by a scroll up as it shrinks to fit beside its passage: at its old
    # size the foot would still hold it.
    for passage, padding, by in [(650, "141px", -50), (600, "121px", -60)]:
        stood = standing(passage, padding)
        drawn, rest = scroll_resizing(by, "0px")
        assert rest[1] < held - 20, f"still held at the foot: {stood} -> {rest}"
        assert drawn[1] <= held + 1, f"past the foot: {stood} -> {drawn} -> {rest}"


def test_a_growing_margin_reply_keeps_its_whole_ring_from_the_first_frame(
    browser, serve
):
    """A line typed into a card's reply grows the field in the frame the key lands
    (box-motion.js, "Whose change it is"), its focus ring drawn whole at its new size
    in that frame. While the growth travelled, the field's own paper stood at its grown
    size over the ring's lower edge until the ring had nearly reached its rest."""
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
    before = field.bounding_box()
    ring = field.evaluate(
        "node => getComputedStyle(node).outlineColor.match(/\\d+/g).map(Number)"
    )
    page.evaluate("() => {" + HOLD_MOTION + "}")
    page.keyboard.press("Shift+Enter")
    page.wait_for_function(
        "height => document.querySelector('.lf-margin-preview .lf-thread-reply"
        " .lf-compose-field').getBoundingClientRect().height > height",
        arg=before["height"] + 10,
    )
    page.evaluate("() => new Promise(r => requestAnimationFrame(() => r()))")
    assert not page.evaluate("() => __lfHeld.some(m => m.playState !== 'idle')")
    stood = field.bounding_box()
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


def test_a_card_at_its_end_keeps_its_last_turn_as_the_window_shortens(browser, serve):
    """A transcript standing at its end keeps its last turn beside the reply box
    whatever takes its room, here the window shortening. The card read whether it
    stood at its end as it refitted, after the room had already gone, so the last
    turn slid under the reply box by the height the window lost."""
    page = open_page(browser, serve(LONG_THREAD_PAGE, events=LONG_THREAD))
    page.emulate_media(reduced_motion="reduce")
    resized(page, 1440, 900)
    page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
    transcript = page.locator(".lf-margin-preview .lf-thread-transcript")
    expect(transcript).to_be_visible()
    rendered(page)
    past_end = "list => list.scrollHeight - list.clientHeight - list.scrollTop"
    assert transcript.evaluate(past_end) <= 1
    room = transcript.evaluate("list => list.clientHeight")
    resized(page, 1440, 700)
    rendered(page)
    assert transcript.evaluate("list => list.clientHeight") < room - 100
    assert transcript.evaluate(past_end) <= 1


def test_a_card_at_its_end_follows_its_last_turn_as_it_grows(browser, serve):
    """A transcript standing at its end stays there as its last turn grows after it
    is drawn, here as the picture in an answer loads. The card followed only the growth
    a reading of the thread brought, so the picture pushed the turn's end below the
    transcript's foot, out of sight of the reader who stood there."""
    page = open_page(browser, serve(LONG_THREAD_PAGE, events=LONG_THREAD))
    page.emulate_media(reduced_motion="reduce")
    resized(page, 1440, 900)
    held = []
    page.route("**/media/051bee487bfb5d13.png", lambda route: held.append(route))
    page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
    transcript = page.locator(".lf-margin-preview .lf-thread-transcript")
    expect(transcript).to_be_visible()
    rendered(page)
    past_end = "list => list.scrollHeight - list.clientHeight - list.scrollTop"
    assert transcript.evaluate(past_end) <= 1
    agent_says(
        page,
        serve.page_dir,
        "The capture:\n\n![Release output](/media/051bee487bfb5d13.png)",
    )
    holding(page, held, 1, "the answer's picture")
    rendered(page)
    assert transcript.evaluate(past_end) <= 1
    picture = transcript.locator('img[src="/media/051bee487bfb5d13.png"]')
    before = picture.evaluate("image => image.getBoundingClientRect().height")
    pixels = (example_media() / "051bee487bfb5d13.png").read_bytes()
    held[0].fulfill(body=pixels, content_type="image/png")
    page.wait_for_function(
        "([image, before]) => image.complete && image.getBoundingClientRect().height > before + 40",
        arg=[picture.element_handle(), before],
    )
    rendered(page)
    assert transcript.evaluate(past_end) <= 1


def test_a_card_wheeled_to_its_end_stays_where_the_browser_put_it(browser, serve):
    """A transcript the user scrolls to its end takes no scroll write from the card.
    Every scroll's end placed the card again, and the placement put a transcript at
    its end back at its end, though nothing had moved the end. The write stops the
    scroll the browser drives: in Firefox it flattened the rubber band a flick into the
    end had started, every 90ms, since the browser's end stood a fraction of a pixel
    past the whole-pixel one written."""
    page, _, transcript = open_long_thread(browser, serve)
    transcript.evaluate(
        """list => {
          list.lfWrites = [];
          for (const name of ["scrollTo", "scroll", "scrollBy"]) {
            const own = list[name].bind(list);
            list[name] = (...args) => (list.lfWrites.push(name), own(...args));
          }
        }"""
    )
    page.mouse.wheel(0, 2000)
    page.wait_for_function(
        "list => list.scrollHeight - list.clientHeight - list.scrollTop < 1",
        arg=transcript.element_handle(),
    )
    scroll_settled(page, ".lf-margin-preview .lf-thread-transcript")
    rendered(page)
    assert transcript.evaluate("list => list.lfWrites") == []


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
    if not comment_repeats:
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
    """The attachment keeps its own row above the editor in a bounded card, standing
    the shelf's gap clear of the ring the field wears."""
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
    rendered(page)
    clearance = image.evaluate(
        """image => {
          const field = image.closest('.lf-thread-reply').querySelector('.lf-compose-field');
          const ring = Math.max(...[field, field.querySelector('leaf-text')].map(box => {
            const style = getComputedStyle(box);
            return style.outlineStyle === 'none'
              ? 0 : parseFloat(style.outlineWidth) + parseFloat(style.outlineOffset);
          }));
          const shelf = getComputedStyle(image.closest('.lf-composer-media'));
          return {ring, gap: parseFloat(shelf.getPropertyValue('--lf-media-gap')),
                  clear: field.getBoundingClientRect().top - ring
                    - image.getBoundingClientRect().bottom};
        }"""
    )
    assert clearance["ring"] > 0, clearance
    assert clearance["clear"] >= clearance["gap"] - 0.5, clearance
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
    incoming = transcript.locator(f'[data-lf-event="{newest["id"]}"]')
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
    # Playwright reveals its target before hover and click. Measure after that
    # setup scroll, so the comparison isolates entering the field.
    reply.scroll_into_view_if_needed()
    rendered(page)
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
    assert reply.bounding_box() == pytest.approx(resting_box, abs=0.5)
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


# macOS draws the transcript's scrollbar as an overlay, which takes no room; a styled
# one takes room on every host, as Linux and Windows, or macOS with a mouse, draw it.
# Chromium styles a bar with `::-webkit-scrollbar` only once the standard properties
# are unset.
TRANSCRIPT_BAR_TAKES_ROOM = """(() => {
  const sheet = new CSSStyleSheet();
  sheet.replaceSync(`
    .lf-margin-thread .lf-thread-transcript {
      scrollbar-width: auto !important;
      scrollbar-color: auto !important;
    }
    .lf-margin-thread .lf-thread-transcript::-webkit-scrollbar { width: 11px; }`);
  document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet];
})()"""


# Where the transcript's words stand against its scrollbar, and how far it scrolls
# sideways.
CLEARANCE = """list => {
  const box = list.getBoundingClientRect();
  const inside = box.left + list.clientLeft + list.clientWidth;
  list.scrollLeft = list.scrollWidth;
  const sideways = list.scrollLeft;
  list.scrollLeft = 0;
  return {
    scrolls: list.scrollHeight > list.clientHeight,
    bar: list.offsetWidth - list.clientWidth,
    sideways,
    under: Math.max(...[...list.querySelectorAll('.lf-msg-body')].map(
      body => body.getBoundingClientRect().right - inside)),
  };
}"""


def opened_transcript(browser, serve, events):
    """The open card's transcript, on a page whose scrollbars take room."""
    page = open_page(
        browser,
        serve(LONG_THREAD_PAGE, events=events),
        init_script=TRANSCRIPT_BAR_TAKES_ROOM,
    )
    resized(page, 1440, 900)
    page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
    transcript = page.locator(".lf-margin-preview .lf-thread-transcript")
    expect(transcript).to_be_visible()
    page.evaluate(
        "() => new Promise(done => requestAnimationFrame(() => "
        "requestAnimationFrame(done)))"
    )
    return transcript


def test_a_card_that_fits_keeps_no_room_for_a_scrollbar(scrollbar_browser, serve):
    """A transcript that fits keeps no room for a scrollbar, so its words wrap as
    wide as the draft they were sent from."""
    transcript = opened_transcript(scrollbar_browser, serve, [LONG_THREAD_ROOT])
    reading = transcript.evaluate(CLEARANCE)
    assert not reading["scrolls"], reading
    assert reading["bar"] == 0, reading
    assert reading["sideways"] == 0, reading


def test_a_card_that_scrolls_gives_its_scrollbar_room(scrollbar_browser, serve):
    """A transcript that scrolls gives its bar room, so its words stand clear of the
    bar and it scrolls only down. A picture that room narrows is shorter, so a turn
    can overflow without the room and fit with it; the card keeps the room rather
    than dropping it and taking it back every frame."""
    transcript = opened_transcript(scrollbar_browser, serve, LONG_THREAD)
    reading = transcript.evaluate(CLEARANCE)
    assert reading["scrolls"], reading
    assert reading["bar"] > 0, reading
    assert reading["sideways"] == 0, reading
    assert reading["under"] <= 0, reading

    # The last turn holds only a picture, shaped to overflow by 6px at the width it
    # has without the gutter, so the gutter's narrowing makes it fit.
    reading = transcript.evaluate(
        """list => new Promise(done => {
          const sheet = new CSSStyleSheet();
          sheet.replaceSync(`
            .lf-thread-transcript > :not(:nth-last-child(1 of .lf-msg)),
            .lf-msg-body > :not(.picture) { display: none; }`);
          document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet];
          const picture = document.createElement('div');
          picture.className = 'picture';
          picture.style.cssText = 'width: 100%; aspect-ratio: 1 / 4';
          list.querySelector(':scope > :nth-last-child(1 of .lf-msg) .lf-msg-body')
            .append(picture);
          const gutter = list.offsetWidth - list.clientWidth;
          const width = picture.getBoundingClientRect().width;
          const rest = list.scrollHeight - picture.getBoundingClientRect().height;
          const ratio = (list.clientHeight + 6 - rest) / (width + gutter);
          let changes = 0;
          new MutationObserver((records) => (changes += records.length)).observe(
            list, {attributeFilter: ['data-lf-overflows']});
          picture.style.aspectRatio = `1 / ${ratio}`;
          let frames = 20;
          const step = () => {
            if (frames--) return requestAnimationFrame(step);
            list.scrollLeft = list.scrollWidth;
            done({
              changes,
              shrink: ratio * gutter,
              fits: list.scrollHeight <= list.clientHeight,
              sideways: list.scrollLeft,
            });
          };
          step();
        })"""
    )
    assert reading["shrink"] > 6, reading
    assert reading["fits"], reading
    assert reading["changes"] <= 1, reading
    assert reading["sideways"] == 0, reading


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
    expect(preview.locator("leaf-text")).to_be_focused()
    # The click puts the caret in the reply (thread/focus.js, `openingPart`); Escape
    # stands the user on the thread.
    page.keyboard.press("Escape")
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


def test_open_reply_keeps_its_foot_after_card_moves_to_right_rail(browser, serve):
    """A draft opened below its target keeps its reply's foot once the rail widens and
    the card stands beside it: a new line grows the card up from the line typed."""
    sidebar_page = OBLIGATION_PAGE.replace(
        '<main class="layout-column">',
        '<main class="layout-sidebar"><aside><div class="layout-track">Page reference</div></aside>'
        '<div class="layout-column">',
        1,
    ).replace("</main>", "</div></main>", 1)
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
    assert after["editorTop"] < before["editorTop"] - 10, (before, after)
    for edge in ("cardBottom", "editorBottom"):
        assert after[edge] == pytest.approx(before[edge], abs=0.5), (
            edge,
            before,
            after,
        )


def test_a_growing_draft_under_its_words_holds_the_editor_s_top(browser, serve):
    """Each new line keeps a card under its words on its side and the reply's first
    line where it was, until the card's foot meets the window's; further lines scroll
    inside the editor. No keystroke carries its first line along the boundary."""
    page, _preview, editor = drafting_in_a_short_card(browser, serve, 1000, 600)
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
        assert now["placement"] == held["placement"] == "below", (held, now)
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


def test_a_growing_draft_over_its_words_holds_the_reply_s_foot(browser, serve):
    """Over its words, a card being written in keeps its foot and the reply's, so each
    new line rises over the transcript and the words the thread is about stay in view
    below it; the card climbs to the window's head, then the transcript gives way,
    then further lines scroll inside the editor (the user's decision, 2026-10-31).
    Kept at its top, the draft grew down over those words."""
    page, _preview, editor = drafting_in_a_short_card(browser, serve, 1000, 520)
    held = page.evaluate(CARD_AND_REPLY)
    readings = [held]
    for _ in range(30):
        editor.press("Shift+Enter")
        rendered(page)
        readings.append(page.evaluate(CARD_AND_REPLY))
    for now in readings:
        assert now["placement"] == held["placement"] == "above", (held, now)
        assert now["cardTop"] >= now["head"] - 0.5, now
        for edge in ("cardBottom", "editorBottom"):
            assert now[edge] == pytest.approx(held[edge], abs=0.5), (edge, held, now)
    first = readings[1]
    assert first["editorTop"] < held["editorTop"] - 10, (held, first)
    last = readings[-1]
    assert last["cardTop"] == pytest.approx(last["head"], abs=0.5), last
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


def test_a_turn_arriving_leaves_a_card_under_its_words_where_it_stands(browser, serve):
    """A card under its words holds its top as a turn arrives: one longer than the room
    below scrolls in inside the card, since rising would cover the words. Beside its
    words a card rises instead (`test_an_answer_arriving_lifts_a_card_beside_its_words`)."""
    page = open_page(browser, serve(LONG_THREAD_PAGE, events=[LONG_THREAD_ROOT]))
    page.emulate_media(reduced_motion="reduce")
    resized(page, 1000, 600)
    page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_have_attribute("data-lf-thread-placement", "below")
    rendered(page)
    top = preview.evaluate("card => card.getBoundingClientRect().top")
    reply = append_carried_log_record(
        serve.page_dir,
        {k: v for k, v in LONG_THREAD[1].items() if k not in ("id", "ts")},
    )
    told(page)
    expect(preview.locator(f'[data-lf-event="{reply["id"]}"]')).to_be_attached()
    rendered(page)
    assert preview.evaluate(
        "card => card.getBoundingClientRect().top"
    ) == pytest.approx(top, abs=0.5)
    assert preview.locator(".lf-thread-transcript").evaluate(
        "list => list.scrollHeight > list.clientHeight"
    )


@pytest.mark.parametrize("repeats", [2, 12])
def test_an_answer_arriving_lifts_a_card_beside_its_words(browser, serve, repeats):
    """A card being read beside its words near the window's foot, the user standing on
    its thread rather than in its reply, rises as an answer arrives, the window's foot
    lifting it, so the question stays in view above the answer. An answer the window
    can't hold fills the window and scrolls inside the card. Held at its top, the card
    scrolled the answer in under the question and hid it (the user's decision,
    2026-10-31)."""
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
    # The click's opening leaves the caret in the reply box, which holds the card's
    # foot; Escape stands the user on the thread to read it.
    expect(preview.locator(".lf-thread-reply leaf-text")).to_be_focused()
    page.keyboard.press("Escape")
    expect(preview.locator(".lf-page-thread")).to_be_focused()
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
    expect(transcript.locator(f'[data-lf-event="{answer["id"]}"]')).to_be_attached()
    rendered(page)
    risen = preview.bounding_box()
    room = preview.evaluate(
        """async card => {
          const {left, right} = card.getBoundingClientRect();
          const {top, bottom} = (await window.__lfWidgetApi())
            .shownWindow({gap: 8, across: {left, right}});
          return {top, bottom};
        }"""
    )
    assert risen["y"] < top - 20, (top, risen)
    assert risen["y"] + risen["height"] == pytest.approx(room["bottom"], abs=1)
    if repeats == 2:
        assert transcript.evaluate("node => node.scrollHeight <= node.clientHeight + 1")
    else:
        assert risen["y"] == pytest.approx(room["top"], abs=1), (risen, room)
        assert transcript.evaluate("node => node.scrollHeight > node.clientHeight")


def test_an_agent_reply_leaves_the_reply_being_typed_where_it_stands(browser, serve):
    """An agent answer shows at once while the user writes in a card over its words,
    which holds its reply's foot while the user is in the box, so the answer grows
    the card up and the line being typed stays where it stands."""
    # The short card, where an arrival has the least room to take.
    size = (1000, 520)
    page, preview, editor = drafting_in_a_short_card(browser, serve, *size)
    before = preview.evaluate(DRAFTING_CARD)
    assert before["side"] == "above", before
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
    expect(preview).to_contain_text("An agent answer arriving while the user types.")
    expect(preview.locator(".lf-thread-news")).to_have_count(0)
    rendered(page)
    expect(editor).to_be_focused()
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


@pytest.mark.parametrize(
    ("size", "how"), [((1200, 900), "key"), ((1000, 520), "press")]
)
def test_a_send_keeps_the_edge_its_card_holds(browser, serve, size, how):
    """Over its words a card keeps its foot, and so its reply's, through the send, its
    admission, an answer, and the next draft typed in the box Send leaves the caret
    in. Under its words it keeps its top, so the sent turn and the answer move the
    reply row down: the answer shows at once, since the caret only rests in the empty
    box (thread-preview.js, `endNewsMoves`). Clearing several lines may lower the
    editor's top, but cannot move the card's column or the page, even for one
    frame."""
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
    expect(editor).to_be_focused()
    page.wait_for_function("replyMotion.frames.some(frame => frame.pending)")
    below = before["side"] == "below"
    pending = finish(before, "top" if below else "editorFoot")
    assert pending["editorTop"] > before["editorTop"] + 20, (before, pending)

    # Admission names the same turn; its later sizing passes keep the same edge.
    begin()
    held.pop().continue_()
    round_trip(page)
    expect(preview.locator(".lf-msg").last).not_to_have_attribute("aria-busy", "true")
    page.wait_for_function("replyMotion.frames.some(frame => !frame.pending)")
    accepted = finish(pending, "top", "foot", "editorTop", "editorFoot")
    page.unroute_all(behavior="wait")

    # A later answer shows at once, growing the card at the edge it doesn't hold: up
    # over the words, the reply staying where it stands, and down past the reply under
    # them.
    begin()
    answer = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "parent": LONG_THREAD_ROOT["id"],
            "responds": preview.locator(".lf-msg").last.get_attribute("data-lf-event"),
            "text": "Noted.",
        },
    )
    told(page)
    expect(preview.locator(f'[data-lf-event="{answer["id"]}"]')).to_be_attached()
    expect(preview.locator(".lf-thread-news")).to_have_count(0)
    answered = finish(accepted, *(["top"] if below else ["foot", "editorFoot"]))
    if below:
        assert answered["editorFoot"] > accepted["editorFoot"] + 10, (
            accepted,
            answered,
        )

    # A fresh draft in the box Send left the caret in grows away from the words, down
    # from its first line under them and up from the reply's foot over them, the
    # transcript giving way where the card fills the room above them; then it scrolls
    # within the card.
    editor.click()
    rendered(page)
    drafting = observe()
    begin()
    page.keyboard.insert_text("The next point.\nAnother line.")
    if accepted["side"] == "above":
        grown = finish(drafting, "top", "foot", "editorFoot")
        assert grown["editorTop"] < drafting["editorTop"] - 10, (drafting, grown)
    else:
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
            "viewport": {"width": 1024, "height": 768},
            "is_mobile": True,
            "has_touch": True,
        },
    ],
    ids=["desktop", "tablet"],
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
    # nothing the document hears. Chromium pans it by the wheel's delta, unscaled; a
    # longer pan than this one moves the card, whose placement then makes its room by
    # scrolling the document (comment-placement.js, `makeRoom`).
    page.mouse.move(4, 150)
    page.mouse.wheel(0, 75)
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
def test_sending_during_a_stream_keeps_later_tokens_from_moving_the_reply(
    scrollbar_browser, serve, request, pending
):
    """An ongoing answer keeps its identity across the user's interjection. Its tokens
    stay live while the user writes, growing the card up from its reply row, which
    stays where it stands. Send empties the box, so the card keeps its top through the
    send and the tokens after it, accepted or pending, grow it down from the reading.
    They need no news press."""
    from browser.threads import claim_for_codex, stream_reply

    url = serve(LONG_THREAD_PAGE, events=[LONG_THREAD_ROOT])
    root = LONG_THREAD_ROOT["id"]
    claim_for_codex(serve.page_dir, request)
    stream_reply(serve.page_dir, root, "The answer has started.")
    # Exercise bars that take room on every host: their gutter can rewrap the answer
    # while Send fits the card against the window's top.
    page = open_page(scrollbar_browser, url, init_script=TRANSCRIPT_BAR_TAKES_ROOM)
    resized(page, 1440, 900)
    page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
    card = page.locator(".lf-margin-preview")
    streamed = card.locator(".lf-msg[data-lf-author=agent] .lf-msg-text")
    expect(streamed).to_have_text("The answer has started.")

    read_positions = """card => ({
          card: card.getBoundingClientRect().top,
          transcript: (() => {
            const list = card.querySelector('.lf-thread-transcript');
            return {
              scroll: list.scrollTop,
              height: list.clientHeight,
              content: list.scrollHeight,
              gutter: list.offsetWidth - list.clientWidth,
            };
          })(),
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
    rendered(page)
    writing = positions()
    waiting = "The answer has started. " + (
        "Additional words that wrap the ongoing answer. " * 2
    )
    stream_reply(serve.page_dir, root, waiting)
    told(page)
    expect(streamed).to_have_text(waiting.strip())
    expect(card.locator(".lf-thread-news")).to_have_count(0)
    expect(card.locator("leaf-text")).to_be_focused()
    rendered(page)
    before_send = positions()
    assert before_send["reply"] == pytest.approx(writing["reply"], abs=0.5)
    held = []

    def hold_reply(route):
        if route.request.post_data_json.get("kind") == "reply":
            held.append(route)
        else:
            route.continue_()

    page.route("**/api/event", hold_reply)
    card.locator(".lf-thread-reply .lf-compose-submit").click()
    holding(page, held, 1, "the reply")
    sent = card.locator(".lf-msg[data-lf-author=user]").filter(
        has_text="Also include the date."
    )
    expect(sent).to_be_visible()
    expect(sent).to_have_attribute("aria-busy", "true")
    expect(streamed).to_have_text(waiting.strip())
    expect(card.locator(".lf-thread-news")).to_have_count(0)
    rendered(page)
    assert positions()["card"] == pytest.approx(before_send["card"], abs=0.5)
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
        expect(card.locator(".lf-thread-news")).to_have_count(0)

    def append_tokens(repetitions):
        before = positions()
        stream_tokens(repetitions)
        after = positions()
        assert after["card"] == pytest.approx(before["card"], abs=0.5)
        assert after["messages"] == pytest.approx(before["messages"], abs=0.5), (
            before,
            after,
        )
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
          const words = card.querySelector('.lf-msg[data-lf-author=agent] .lf-msg-text');
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


def test_a_press_on_a_cards_news_leaves_the_caret_in_its_reply(browser, serve):
    """A card holding news while the user writes its reply shows it on a press of its
    notice, and the caret stays in the reply with the words before it. The press took
    focus from the box and landed it on the thread, as a key on the notice does."""
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "Where should this explanation go?", {"section": "how-store"}
    )
    page = open_page(browser, url)
    page.locator('[data-lf-margin-for="how-store"] .lf-margin-marker').click()
    preview = page.locator(".lf-margin-preview")
    reply = preview.get_by_role("textbox", name="Reply", exact=True)
    write(reply, "Drafting while the answer arrives")
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "parent": root,
            "responds": root,
            "text": "Under the queue's heading.",
        },
    )
    told(page)
    notice = preview.locator(".lf-thread-news")
    expect(notice).to_be_visible()
    notice.click()
    expect(preview.get_by_text("Under the queue's heading.")).to_be_visible()
    expect(reply).to_be_focused()
    expect(reply).to_have_js_property("value", "Drafting while the answer arrives")


def test_a_card_offers_next_unread_for_a_reply_its_opening_left_unread(browser, serve):
    """A card that opens on a reply too long to show whole leaves it unread, so Next
    unread stands on its head line, drawn by the thread as in the floating panel's view
    (thread-card.js, `settled`). A press on it, or a key, lands on that reply; once
    every reply reads a card draws nothing for it, since nothing on its line moves for
    the press."""
    short_reply = {
        **LONG_THREAD[1],
        "text": "Landed: the first two now close to the page.",
        "id": "d" * 32,
        "ts": "2026-09-18T19:34:26-07:00",
    }
    page = open_page(
        browser,
        serve(LONG_THREAD_PAGE, events=[LONG_THREAD_ROOT, LONG_THREAD[1], short_reply]),
    )
    resized(page, 1440, 700)
    page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
    preview = page.locator(".lf-margin-preview")
    transcript = preview.locator(".lf-thread-transcript")
    press = preview.locator(".lf-margin-thread-controls .lf-next-unread")
    expect(press).to_have_text("Next unread")
    reply = transcript.locator(".lf-msg").nth(1)

    press.click()
    expect(reply).to_be_focused()
    expect(reply).to_be_in_viewport()

    preview.locator(".lf-thread-reply leaf-text").click()
    press.focus()
    page.keyboard.press("Enter")
    expect(reply).to_be_focused()

    transcript.hover()
    for _ in range(40):
        if transcript.evaluate(
            "list => list.scrollTop + list.clientHeight >= list.scrollHeight - 1"
        ):
            break
        page.mouse.wheel(0, 120)
        page.wait_for_timeout(20)
    expect(transcript.locator(".lf-msg-new")).to_have_count(0)
    expect(press).to_be_hidden()
    expect(press).to_be_disabled()
    assert press.evaluate("press => getComputedStyle(press).display") == "none"


@pytest.mark.parametrize("pointer", ["mouse", "finger"])
def test_next_unread_beside_previous_and_next_leaves_a_head_its_words(
    browser, serve, pointer
):
    """Beside Previous and Next, Next unread stands on its symbol, its words its name, so
    the first head keeps its author and time, which its words cut to "Me ju". Under a
    finger, where each press is a finger wide, a card draws none there (annotation-chrome.css)."""
    second = {**LONG_THREAD_ROOT, "text": "A second question.", "id": "e" * 32}
    url = serve(LONG_THREAD_PAGE, events=[LONG_THREAD_ROOT, LONG_THREAD[1], second])
    context = browser.new_context(
        viewport={"width": 1440, "height": 700}, has_touch=pointer == "finger"
    )
    page = open_page(browser, url, context=context)
    marker = page.locator('[data-lf-margin-for="open"] .lf-margin-marker')
    marker.tap() if pointer == "finger" else marker.click()
    preview = page.locator(".lf-margin-preview")
    expect(preview.locator(".lf-margin-preview-position")).to_have_text("1/2")
    press = preview.locator(".lf-next-unread")
    expect(press).to_be_attached()
    rendered(page)
    if pointer == "finger":
        expect(press).to_be_hidden()
        return
    expect(
        preview.get_by_role("button", name="Next unread", exact=True)
    ).to_be_visible()
    assert press.bounding_box()["width"] == 24
    head = preview.locator(".lf-msg-head").first
    for part in (head.locator(":scope > b"), head.locator(".lf-msg-meta > time")):
        assert part.evaluate("part => part.scrollWidth <= part.clientWidth")


def test_next_unread_never_shows_in_a_card_whose_opening_reads_its_reply(
    browser, serve
):
    """A short reply reads as the card lands, so Next unread never shows, not even for
    the moment before the reply is read."""
    short_reply = {**LONG_THREAD[1], "text": "Landed: the first two close."}
    page = open_page(
        browser, serve(LONG_THREAD_PAGE, events=[LONG_THREAD_ROOT, short_reply])
    )
    resized(page, 1440, 900)
    page.evaluate("""() => {
      window.nextUnreadShown = false;
      new MutationObserver(() => {
        window.nextUnreadShown ||= Boolean(
          document.querySelector('.lf-next-unread:not([data-lf-unoffered])'));
      }).observe(document, {subtree: true, childList: true, attributes: true});
    }""")
    preview = page.locator(".lf-margin-preview")
    with sending(page, "the reply read"):
        page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
        expect(preview.locator(".lf-msg", has_text="Landed")).to_be_visible()
    expect(preview.locator(".lf-msg-new")).to_have_count(0)
    round_trip(page)
    assert not page.evaluate("() => window.nextUnreadShown")
    expect(preview.locator(".lf-next-unread")).to_have_count(0)


def test_a_card_says_new_reply_for_an_answer_past_its_transcript_s_foot(browser, serve):
    """The answer the user waits for, arriving past the card's capped transcript's foot,
    says New reply there, by the floating panel's rule (thread-card.js, `#fitAnswer`). A
    reader who read back keeps their place. One at the transcript's end keeps their turn
    in sight above the answer, unless the two fit together, when the end shows both. A
    press, a key on the press, or scrolling to the answer's start takes it away, and so
    does their next turn; the press and the key show the answer's start, on the
    thread."""
    page, preview, transcript = open_long_thread(browser, serve)
    thread = preview.locator(".lf-page-thread")
    press = preview.locator(".lf-new-reply")
    box = preview.locator(".lf-thread-reply leaf-text")
    limit = "list => list.scrollHeight - list.clientHeight"
    long_answer = "Someone stays on call through Sunday, and Monday too. " * 40

    def turn(words):
        box.click()
        page.keyboard.insert_text(words)
        with sending(page, "the turn"):
            page.keyboard.press("ControlOrMeta+Enter")
        rendered(page)

    def read_back():
        transcript.hover()
        page.mouse.wheel(0, -500)
        page.wait_for_function(
            "list => list.scrollTop < list.scrollHeight - list.clientHeight - 200",
            arg=transcript.element_handle(),
        )
        scroll_settled(page, ".lf-margin-preview .lf-thread-transcript")

    def answer(words):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Claude",
                "parent": LONG_THREAD_ROOT["id"],
                "revision": 1,
                "text": words,
            },
        )
        told(page)
        message = transcript.locator(".lf-msg", has_text=words[:30]).last
        expect(message).to_be_attached()
        rendered(page)
        return message

    turn("And the short version?")
    answer("At the end, in a line.")
    expect(press).to_have_count(0)
    assert transcript.evaluate(limit) - transcript.evaluate("l => l.scrollTop") <= 2

    turn("And the mobile cohort?")
    stood = transcript.evaluate(
        """list => {
          window.lfScrolled = [];
          list.addEventListener('scroll', () => lfScrolled.push(list.scrollTop));
          return list.scrollTop;
        }"""
    )
    answer("At the end: " + long_answer)
    expect(press).to_have_text("New reply")
    # It never goes to its end on the way, which a frame could show.
    scrolled = transcript.evaluate("() => window.lfScrolled")
    assert max([stood, *scrolled]) - stood < 100, (stood, scrolled)
    asked = transcript.locator(".lf-msg", has_text="And the mobile cohort?")
    head = asked.locator(".lf-msg-head").bounding_box()
    words = asked.bounding_box()
    list_box = transcript.bounding_box()
    assert list_box["y"] <= head["y"], (list_box, head)
    assert words["y"] + words["height"] <= press.bounding_box()["y"], (words, press)
    assert transcript.evaluate(limit) - transcript.evaluate("l => l.scrollTop") > 100

    turn("And the weekend?")
    read_back()
    place = transcript.evaluate("l => l.scrollTop")
    shown = answer("By a press: " + long_answer)
    expect(press).to_have_text("New reply")
    assert transcript.evaluate("l => l.scrollTop") == place
    foot = transcript.bounding_box()
    at = press.bounding_box()
    assert foot["y"] < at["y"] and at["y"] + at["height"] <= foot["y"] + foot["height"]
    # A message head's height, as the thread's other actions are.
    assert at["height"] == 28
    press.click()
    expect(press).to_have_count(0)
    expect(thread).to_be_focused()
    expect(shown.locator(".lf-msg-head")).to_be_in_viewport()

    turn("And the holiday?")
    read_back()
    shown = answer("By a key: " + long_answer)
    expect(press).to_have_text("New reply")
    press.focus()
    page.keyboard.press("Enter")
    expect(press).to_have_count(0)
    expect(thread).to_be_focused()
    expect(shown.locator(".lf-msg-head")).to_be_in_viewport()

    turn("And the night shift?")
    read_back()
    shown = answer("By scrolling: " + long_answer)
    expect(press).to_have_text("New reply")
    transcript.hover()
    for _ in range(20):
        if not press.count():
            break
        page.mouse.wheel(0, 120)
        page.wait_for_timeout(30)
    expect(press).to_have_count(0)

    turn("And the next one?")
    read_back()
    answer("By a turn: " + long_answer)
    expect(press).to_have_text("New reply")
    turn("Thanks.")
    expect(press).to_have_count(0)


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_wheel_up_a_card_as_its_answer_arrives_goes_where_it_takes_the_reader(
    engine, request, serve
):
    """A reader at the card's end who wheels up its transcript as the answer to their
    turn arrives goes where the wheel takes them, New reply standing for the answer
    (thread-card.js, `#fitAnswer`). Firefox applies the wheel's scroll a frame or more
    after the wheel, and the answer's placement, reading the reader at the end in
    between, moved their turn into sight and cancelled the wheel."""
    page, preview, transcript = open_long_thread(request.getfixturevalue(engine), serve)
    press = preview.locator(".lf-new-reply")
    preview.locator(".lf-thread-reply leaf-text").click()
    page.keyboard.insert_text("And over the weekend?")
    with sending(page, "the turn"):
        page.keyboard.press("ControlOrMeta+Enter")
    rendered(page)
    stood = transcript.evaluate("list => list.scrollTop")
    assert transcript.evaluate("l => l.scrollHeight - l.clientHeight") - stood <= 2
    held = []
    page.route("**/api/state*", lambda route: held.append(route))
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": LONG_THREAD_ROOT["id"],
            "revision": 1,
            "text": "It would. " + "Someone stays on call through Sunday. " * 60,
        },
    )
    holding(page, held, 1, "the answer")
    transcript.hover()
    page.mouse.wheel(0, -300)
    page.unroute("**/api/state*")
    for route in held:
        route.continue_()
    expect(press).to_have_text("New reply")
    scroll_settled(page, ".lf-margin-preview .lf-thread-transcript")
    assert transcript.evaluate("list => list.scrollTop") < stood - 200


@pytest.mark.parametrize("progress", [False, True])
def test_an_answer_a_card_followed_says_new_reply_once_its_picture_outgrows_it(
    browser, serve, progress
):
    """An answer the card's end followed into sight, since it fit with the user's turn
    as it was drawn, is placed by the same rule once it grows, here as a tall picture in
    it loads: following the end would carry the user's turn away, so the turn stays in
    sight and New reply stands for the rest of the answer. So is one that replaced
    taller progress, which moved nothing as it shrank the transcript."""
    page, preview, transcript = open_long_thread(browser, serve, height=600)
    press = preview.locator(".lf-new-reply")
    held = []
    picture = media_model.store_uploaded_media(
        serve.page_dir, solid_png(400, 1600, (64, 64, 64)), "image/png"
    )
    page.route(f"**{picture}", lambda route: held.append(route))
    preview.locator(".lf-thread-reply leaf-text").click()
    page.keyboard.insert_text("And the capture?")
    with sending(page, "the turn"):
        page.keyboard.press("ControlOrMeta+Enter")
    rendered(page)
    if progress:
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Claude",
                "parent": LONG_THREAD_ROOT["id"],
                "revision": 1,
                "text": "Checking the release capture. " * 20,
                "ephemeral": True,
            },
        )
        told(page)
        rendered(page)
    agent_says(
        page,
        serve.page_dir,
        "The capture shows the release output as it stood after the deploy. " * 3
        + f"\n\n![Capture]({picture})",
    )
    holding(page, held, 1, "the answer's picture")
    rendered(page)
    past_end = "list => list.scrollHeight - list.clientHeight - list.scrollTop"
    assert transcript.evaluate(past_end) <= 2
    expect(press).to_have_count(0)
    held[0].continue_()
    expect(press).to_have_text("New reply")
    rendered(page)
    asked = transcript.locator(".lf-msg", has_text="And the capture?")
    head = asked.locator(".lf-msg-head").bounding_box()
    words = asked.bounding_box()
    assert transcript.bounding_box()["y"] <= head["y"], head
    assert words["y"] + words["height"] <= press.bounding_box()["y"], words


def test_an_edit_landing_as_a_card_s_last_turn_grows_shows_at_its_end(browser, serve):
    """A reader at a card's transcript end sees the agent's edit to the last turn at
    once, though it lands in the task where the turn grew, here as its picture loaded,
    before the end keeper read that growth (thread-card.js, `newsMoves`). The card asked
    the transcript's offset whether its reader followed the end, and the offset, short
    of the end by the picture, said no: the edit waited behind the card's notice while
    the keeper took the reader to the end."""
    page = open_page(browser, serve(LONG_THREAD_PAGE, events=LONG_THREAD))
    page.emulate_media(reduced_motion="reduce")
    resized(page, 1440, 900)
    held = []
    picture = "/media/051bee487bfb5d13.png"
    page.route(f"**{picture}", lambda route: held.append(route))
    page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
    preview = page.locator(".lf-margin-preview")
    transcript = preview.locator(".lf-thread-transcript")
    expect(transcript).to_be_visible()
    words = f"The capture:\n\n![Capture]({picture})"
    answer = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": LONG_THREAD_ROOT["id"],
            "revision": 1,
            "text": words,
        },
    )
    told(page)
    holding(page, held, 1, "the answer's picture")
    rendered(page)
    past_end = "list => list.scrollHeight - list.clientHeight - list.scrollTop"
    assert transcript.evaluate(past_end) <= 1
    # The page's next reading waits for the picture and is taken in the task where it
    # loads.
    page.evaluate(
        """picture => {
          const image = document.querySelector(`.lf-margin-preview img[src="${picture}"]`);
          const loaded = new Promise(resolve =>
            image.addEventListener('load', resolve, {once: true}));
          const own = Response.prototype.text;
          Response.prototype.text = async function () {
            const body = await own.call(this);
            if (!this.url.includes('/api/state')) return body;
            Response.prototype.text = own;
            window.lfReadingHeld = true;
            await loaded;
            return body;
          };
        }""",
        picture,
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "edit",
            "author": "agent",
            "agent": "Claude",
            "message": answer["id"],
            "text": f"{words}\n\nOne more thing about the second layer.",
        },
    )
    page.wait_for_function("() => window.lfReadingHeld === true")
    pixels = (example_media() / "051bee487bfb5d13.png").read_bytes()
    held[0].fulfill(body=pixels, content_type="image/png")
    told(page)
    rendered(page)
    assert preview.locator(".lf-msg", has_text="One more thing").is_visible()
    assert preview.locator(".lf-thread-news:visible").count() == 0
    assert transcript.evaluate(past_end) <= 1
