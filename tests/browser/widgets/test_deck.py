"""A deck of cards: an answer moves it on, Later keeps a card for the end of the pass,
Back and Review step through answered cards, and a new tab opens where a card waits."""

import re
from datetime import UTC, datetime, timedelta

import pytest
from playwright.sync_api import expect
from render_cases_interaction import HOLD_MOTION, live_url
from render_harness import (
    clocked,
    holding,
    leaf_page,
    open_page,
    round_trip,
    undo,
    wait_for_check_api,
)

from leaf.log import event_log as events_model

pytestmark = pytest.mark.shifts_unsurveyed


def card(name, question):
    return f"""<lf-group id="{name}-ask" label="{question}"><h3 id="{name}-ask-h">{question}</h3>
      <lf-options id="{name}-choice">
        <lf-option id="{name}-yes" label="Yes"><strong>Yes</strong></lf-option>
        <lf-option id="{name}-no" label="No"><strong>No</strong></lf-option>
      </lf-options></lf-group>"""


DECK_PAGE = leaf_page(
    "Deck",
    "<h1>Before the release</h1>"
    '<lf-deck id="deck">'
    + card("store", "Keep Redis?")
    + card("beta", "Ship the beta?")
    + card("notes", "Post the notes?")
    + "</lf-deck><p>After the deck.</p>",
)

OPEN = "() => document.querySelector('lf-deck > [data-lf-deck-open]')?.id ?? null"
# Whether no card is in flight, so the deck stands where its last change left it.
LANDED = "() => !document.querySelector('lf-deck[data-lf-deck-flying]')"


def open_card(page, name):
    page.wait_for_function(f"() => ({OPEN})() === {name!r}")


def answer(page, option):
    page.locator(f"#{option}").click()
    round_trip(page)


def forward(page, title):
    control = page.locator("lf-deck .lf-deck-forward")
    expect(control).to_have_attribute("aria-label", title)
    control.click()


def again(page, words):
    """The end frame's step back in, which stands where the cards stood."""
    page.locator("lf-deck .lf-deck-end").get_by_role("button", name=words).click()


def test_a_pass_moves_on_by_answers_keeps_later_and_reviews_every_card(browser, serve):
    """An answer moves the deck to the next card that waits; Later moves on and leaves
    its card waiting, which the end of the pass comes back to; Back returns to an
    answered card; and once nothing waits, Review steps through every card in order."""
    page = open_page(browser, serve(DECK_PAGE))
    open_card(page, "store-ask")

    answer(page, "store-yes")
    open_card(page, "beta-ask")
    forward(page, "Later")
    open_card(page, "notes-ask")
    answer(page, "notes-no")
    expect(page.locator("lf-deck > [data-lf-deck-open]")).to_have_count(0)

    again(page, "Go through the 1 left")
    open_card(page, "beta-ask")
    page.locator("lf-deck .lf-deck-back").click()
    open_card(page, "store-ask")
    forward(page, "Next")
    open_card(page, "beta-ask")
    answer(page, "beta-yes")
    expect(page.locator("lf-deck > [data-lf-deck-open]")).to_have_count(0)

    again(page, "Review from the start")
    open_card(page, "store-ask")
    forward(page, "Next")
    open_card(page, "beta-ask")
    forward(page, "Next")
    open_card(page, "notes-ask")


# A deck at the page's top with more page below it than the window shows, so a landing
# that put a card's options at the window's top would scroll the page.
DECK_ABOVE_MORE_PAGE = leaf_page(
    "Deck above more",
    "<h1>Before the release</h1>"
    '<lf-deck id="deck">'
    + card("store", "Keep Redis?")
    + card("beta", "Ship the beta?")
    + "</lf-deck>"
    + "".join(
        f"<p>Paragraph {i}. " + "Words to read. " * 30 + "</p>" for i in range(30)
    ),
)

# The page's offset and the top of the options of the card `arg` names.
PLACE = """(name) => [Math.round(scrollY),
  Math.round(document.getElementById(name).getBoundingClientRect().top)]"""


def test_undo_brings_back_the_card_an_answer_moved_on_from_where_it_stood(
    browser, serve
):
    """Taking back the answer that moved the deck on opens its card again where it
    stood, with the user on its question, and the page doesn't scroll."""
    page = open_page(browser, serve(DECK_ABOVE_MORE_PAGE))
    open_card(page, "store-ask")
    before = page.evaluate(PLACE, "store-choice")
    answer(page, "store-yes")
    open_card(page, "beta-ask")
    page.wait_for_function(LANDED)
    undo(page)
    open_card(page, "store-ask")
    expect(page.locator("#store-choice")).to_be_focused()
    assert page.evaluate(PLACE, "store-choice") == before


def test_the_end_of_the_pass_lists_each_answer_and_a_row_opens_its_card(browser, serve):
    """Once the pass is over, the cards are put away but the end frame lists each one's
    question beside the answer given, or that it still waits. A pass by keyboard ends
    on the step back in, the rows follow it in Tab order, and a row opens its card, by
    Enter as by pointer."""
    page = open_page(browser, serve(DECK_PAGE))
    page.keyboard.press("m")
    expect(page.locator("#store-ask")).to_be_focused()
    page.keyboard.press("1")
    round_trip(page)
    open_card(page, "beta-ask")
    expect(page.locator("#beta-ask")).to_be_focused()
    page.keyboard.press("ArrowRight")
    open_card(page, "notes-ask")
    page.keyboard.press("2")
    round_trip(page)
    end = page.locator("lf-deck .lf-deck-end")
    expect(end.get_by_role("button", name="Go through the 1 left")).to_be_focused()

    recap = end.locator(".lf-deck-recap > li")
    expect(recap.locator("a")).to_have_text(
        ["Keep Redis?", "Ship the beta?", "Post the notes?"]
    )
    expect(recap.locator("span")).to_have_text(["Yes", "Still waiting", "No"])

    page.keyboard.press("Tab")
    page.keyboard.press("Tab")
    expect(recap.get_by_role("link", name="Ship the beta?")).to_be_focused()
    page.keyboard.press("Enter")
    open_card(page, "beta-ask")
    forward(page, "Later")
    expect(page.locator("lf-deck > [data-lf-deck-open]")).to_have_count(0)
    recap.get_by_role("link", name="Keep Redis?").click()
    open_card(page, "store-ask")


PLAIN_CARD_PAGE = leaf_page(
    "Deck with a card of no id",
    '<h1>Before the release</h1><lf-deck id="deck">'
    + card("store", "Keep Redis?")
    + "<section>"
    + card("docs", "Ship the docs?")
    + "</section></lf-deck>",
)


def test_a_recap_row_opens_a_card_with_no_id_of_its_own(browser, serve):
    """A card can be a plain wrapper around the question it holds; its row in the
    end frame still links to where the user answers it, and opens it."""
    page = open_page(browser, serve(PLAIN_CARD_PAGE))
    open_card(page, "store-ask")
    answer(page, "store-yes")
    expect(page.locator("#docs-ask")).to_be_visible()
    answer(page, "docs-no")
    expect(page.locator("lf-deck > [data-lf-deck-open]")).to_have_count(0)

    page.locator("lf-deck .lf-deck-recap").get_by_role(
        "link", name="Ship the docs?"
    ).click()
    expect(page.locator("#docs-ask")).to_be_visible()


SUGGESTION_DECK_PAGE = leaf_page(
    "Deck with a suggestion",
    '<h1>Before the release</h1><lf-deck id="deck">'
    '<section id="note-card"><h3>Tighten the upgrade note?</h3>'
    '<lf-suggestion id="note-suggestion">'
    "<lf-old><p>Users may need to clear their cache in some cases.</p></lf-old>"
    "<lf-new><p>Clear the cache once after installing.</p></lf-new>"
    "</lf-suggestion></section>" + card("store", "Keep Redis?") + "</lf-deck>",
)


def test_a_recap_row_names_a_question_with_no_words_as_on_me_does(browser, serve):
    """A suggestion is set among words, in no group, so its question has no words of
    its own; its row in the end frame names it as On Me does, by the words it suggests."""
    page = open_page(browser, serve(SUGGESTION_DECK_PAGE))
    open_card(page, "note-card")
    page.get_by_role(
        "button", name=re.compile(r"^Accept the suggested change")
    ).first.click()
    round_trip(page)
    open_card(page, "store-ask")
    answer(page, "store-yes")
    expect(page.locator("lf-deck > [data-lf-deck-open]")).to_have_count(0)
    expect(page.locator("lf-deck .lf-deck-recap > li > a")).to_have_text(
        ["Clear the cache once after installing.", "Keep Redis?"]
    )


def test_a_new_tab_opens_on_the_first_card_that_waits(browser, serve):
    """A tab that never showed the deck opens on the first card still waiting, not on
    the answered card the markup puts first; the tab that answered keeps its place."""
    url = live_url(serve(DECK_PAGE))
    first = open_page(browser, url)
    answer(first, "store-no")
    open_card(first, "beta-ask")

    second = open_page(browser, url)
    open_card(second, "beta-ask")


def test_an_answer_from_another_window_moves_the_card_on_here_too(browser, serve):
    """A card answered in another window moves on in this one too, as it would had
    this window answered it."""
    url = live_url(serve(DECK_PAGE))
    watching = open_page(browser, url)
    open_card(watching, "store-ask")

    answering = open_page(browser, url)
    answer(answering, "store-no")
    open_card(watching, "beta-ask")


def test_an_answer_read_back_late_moves_the_card_and_not_the_page(browser, serve):
    """An answer moves its card on when the server's reading of it comes back,
    wherever the user is by then, as a slow first answer on a hosted page can come
    after they scrolled away and turned to another window. The page stays where they
    went, since the answer is no longer their latest gesture."""
    page = open_page(browser, serve(TALL_DECK_PAGE))
    open_card(page, "store-ask")
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.locator("#store-yes").click()
    holding(page, held, 1, "the answer whose reading is held")
    page.mouse.wheel(0, -2000)
    page.wait_for_function("() => scrollY === 0")
    page.evaluate("() => { Document.prototype.hasFocus = () => false; }")
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    open_card(page, "tall-ask")
    page.wait_for_function(LANDED)
    assert page.evaluate("() => scrollY") == 0


def test_a_scroll_as_the_card_moves_on_keeps_the_page(browser, serve):
    """An answer by key brings up the next card, and a wheel the user turns while it
    comes up leaves the page where the wheel took it: neither the card's landing nor
    the focus that follows the answer pulls it back. The card's motion and the page's
    timers are held until the page has read the wheel, so the wheel lands while the
    card comes up however long the machine takes to deliver it."""
    page = open_page(clocked(browser), serve(TALL_DECK_PAGE))
    page.emulate_media(reduced_motion="no-preference")
    page.keyboard.press("m")
    expect(page.locator("#store-ask")).to_be_focused()
    page.evaluate("() => {" + HOLD_MOTION + "}")
    page.evaluate(
        "() => { window.__wheeled = new Promise((read) =>"
        " addEventListener('wheel', read, { once: true, passive: true })); }"
    )
    page.clock.pause_at(datetime.now(UTC) + timedelta(seconds=1))
    page.keyboard.press("1")
    page.mouse.wheel(0, -3000)
    page.evaluate("() => window.__wheeled.then(() => {})")
    page.evaluate(
        "() => __lfHeld.filter(a => a.playState !== 'idle').forEach(a => a.finish())"
    )
    page.clock.resume()
    open_card(page, "tall-ask")
    page.wait_for_function(LANDED)
    # The arrival an answer by key makes waits as long as the card that came up takes
    # no press, and was timed just after it: once that card takes presses again, a
    # timer posted then runs behind the arrival.
    page.wait_for_function(
        "() => !document.querySelector('lf-deck [data-lf-deck-settling]')"
    )
    page.evaluate("() => new Promise((then) => setTimeout(then))")
    assert page.evaluate("() => scrollY") == 0
    expect(page.locator("#tall-ask")).not_to_be_focused()


DRAFT_DECK_PAGE = leaf_page(
    "Deck with a draft",
    '<h1>Before the release</h1><lf-deck id="deck">'
    '<lf-group id="reply-ask" label="Send this reply?"><h3 id="reply-ask-h">Send this reply?</h3>'
    '<lf-draft id="reply-draft"><pre>\nThanks for the report.</pre></lf-draft>'
    '<lf-options id="reply-choice">'
    '<lf-option id="reply-send" label="Send it"><strong>Send it</strong></lf-option>'
    '<lf-option id="reply-hold" label="Hold it"><strong>Hold it</strong></lf-option>'
    "</lf-options></lf-group>" + card("notes", "Post the notes?") + "</lf-deck>",
)


def test_an_answer_saves_the_open_draft_before_the_card_moves_on(browser, serve):
    """An answer pressed on a card whose draft editor is still open saves the edit, as
    any press away from the editor does, and the deck moves on with nothing lost."""
    page = open_page(browser, serve(DRAFT_DECK_PAGE))
    open_card(page, "reply-ask")
    page.locator("#reply-draft .lf-draft-body").click()
    editor = page.locator("#reply-draft leaf-text")
    expect(editor).to_be_focused()
    page.keyboard.press("End")
    page.keyboard.type(" Sorry for the wait.")
    answer(page, "reply-send")
    open_card(page, "notes-ask")
    edits = [
        event["detail"]["value"]
        for event in events_model.read_events(serve.page_dir)
        if event.get("action") == "edit"
    ]
    assert edits == ["Thanks for the report. Sorry for the wait."], edits


SENTENCE = "Each platform adds a day of smoke testing before the beta ships. "
TALL_CARD = (
    '<lf-group id="tall-ask" label="Ship the beta on every platform?">'
    "<h3>Ship the beta on every platform?</h3>"
    + "".join(f"<p>{SENTENCE * 3}</p>" for _ in range(4))
    + '<lf-options id="tall-choice">'
    '<lf-option id="tall-yes" label="Yes"><strong>Yes</strong></lf-option>'
    '<lf-option id="tall-no" label="No"><strong>No</strong></lf-option>'
    "</lf-options></lf-group>"
)
TALL_DECK_PAGE = leaf_page(
    "Deck below an opening",
    "<h1>Before the release</h1>"
    + "".join(f"<p>{SENTENCE * 3}</p>" for _ in range(4))
    + '<lf-deck id="deck">'
    + card("store", "Keep Redis?")
    + TALL_CARD
    + "</lf-deck><p>After the deck.</p>",
)

# Whether the open card, landed, stands whole in the room above the panel's top, with
# the deck's bar in the window above it. A scroll that brings it there only moves it up,
# so once this holds it holds where the scroll ends.
WHOLE_ABOVE = """(panelTop) => {
  const deck = document.querySelector('lf-deck');
  const card = deck.querySelector(':scope > [data-lf-deck-open]');
  if (!card || deck.matches('[data-lf-deck-flying]')) return false;
  const bar = deck.querySelector('.lf-deck-bar').getBoundingClientRect();
  return bar.top >= 0 && card.getBoundingClientRect().bottom <= panelTop;
}"""


def test_a_card_brought_back_below_the_opening_stands_whole_above_the_panel(
    browser, serve
):
    """Go through brings back a card left for later where the pass began, below the
    page's opening. A card taller than the room there scrolls up until the whole card
    clears the panel, with the bar still above it, so the press that brought it leaves
    it answerable."""
    page = open_page(browser, serve(TALL_DECK_PAGE))
    open_card(page, "store-ask")
    answer(page, "store-yes")
    open_card(page, "tall-ask")
    forward(page, "Later")
    expect(page.locator("lf-deck > [data-lf-deck-open]")).to_have_count(0)

    again(page, "Go through the 1 left")
    open_card(page, "tall-ask")
    panel_top = page.locator(".lf-fp-row").bounding_box()["y"]
    page.wait_for_function(WHOLE_ABOVE, arg=panel_top)


def test_by_keyboard_an_answer_lands_on_the_next_question_once(browser, serve):
    """A digit that answers a card brings the user to the next card's question once it
    has settled, so its digits answer it. Once the pass is over, the end frame says what
    is left and takes the user back in."""
    page = open_page(browser, serve(DECK_PAGE))
    page.keyboard.press("m")
    expect(page.locator("#store-ask")).to_be_focused()
    page.keyboard.press("1")
    round_trip(page)
    open_card(page, "beta-ask")
    expect(page.locator("#beta-ask")).to_be_focused()
    page.keyboard.press("ArrowRight")
    open_card(page, "notes-ask")
    page.keyboard.press("2")
    round_trip(page)
    end = page.locator("lf-deck .lf-deck-end")
    expect(end).to_contain_text("One still waits on you.")
    again = end.get_by_role("button", name="Go through the 1 left")
    expect(again).to_be_focused()
    page.keyboard.press("Enter")
    open_card(page, "beta-ask")


def test_by_keyboard_back_from_the_end_of_the_pass_keeps_stepping_back(browser, serve):
    """Back pressed on the end frame's step back in brings the last card up with the
    user on it, so the next Back steps further rather than falling to the page."""
    page = open_page(browser, serve(DECK_PAGE))
    page.keyboard.press("m")
    for name in ["store", "beta", "notes"]:
        expect(page.locator(f"#{name}-ask")).to_be_focused()
        page.keyboard.press("1")
        round_trip(page)
    end = page.locator("lf-deck .lf-deck-end")
    expect(end.get_by_role("button", name="Review from the start")).to_be_focused()
    page.keyboard.press("ArrowLeft")
    open_card(page, "notes-ask")
    expect(page.locator("#notes-ask")).to_be_focused()
    page.keyboard.press("ArrowLeft")
    open_card(page, "beta-ask")


def test_by_keyboard_the_forward_control_hands_over_to_the_step_back_in(browser, serve):
    """Later pressed from the bar on the last card ends the pass and hides the bar's
    forward control; the user lands on the end frame's step back in, which stands for
    it, rather than on the page."""
    page = open_page(browser, serve(DECK_PAGE))
    page.keyboard.press("m")
    for name in ["store", "beta"]:
        expect(page.locator(f"#{name}-ask")).to_be_focused()
        page.keyboard.press("1")
        round_trip(page)
    expect(page.locator("#notes-ask")).to_be_focused()
    page.keyboard.press("Shift+Tab")
    forward_control = page.locator("lf-deck .lf-deck-forward")
    expect(forward_control).to_be_focused()
    page.keyboard.press("Enter")
    end = page.locator("lf-deck .lf-deck-end")
    expect(end.get_by_role("button", name="Go through the 1 left")).to_be_focused()


def test_a_card_still_flying_off_takes_no_focus(browser, serve):
    """The card an answer sends off stands before the one that came up until its motion
    ends, so Shift+Tab from the new card goes to the bar's Later rather than into the
    card leaving. The motion is held at its first frame through the focus check, so
    neither a slow runner nor a fast one decides whether the card is still leaving."""
    page = open_page(browser, serve(DECK_PAGE))
    page.emulate_media(reduced_motion="no-preference")
    page.keyboard.press("m")
    expect(page.locator("#store-ask")).to_be_focused()
    page.evaluate("() => {" + HOLD_MOTION + "}")
    page.keyboard.press("1")
    expect(page.locator("#beta-ask")).to_be_focused()
    leaving = page.locator("#store-ask")
    expect(leaving).to_have_attribute("data-lf-deck-leaving", "right")
    assert page.evaluate("() => __lfHeld.some(a => a.playState === 'paused')")
    page.keyboard.press("Shift+Tab")
    expect(page.locator("lf-deck .lf-deck-forward")).to_be_focused()
    expect(leaving).to_have_attribute("data-lf-deck-leaving", "right")
    page.evaluate(
        "() => __lfHeld.filter(a => a.playState !== 'idle').forEach(a => a.finish())"
    )
    expect(leaving).not_to_have_attribute("data-lf-deck-leaving", "right")
    expect(leaving).not_to_have_attribute("inert", "")


def test_a_swipe_stays_held_until_the_fingers_lift(browser, serve):
    """A swipe of the open card says the user holds it (`lf-hold`) from its first
    sideways move until the finger lifts. A second finger that lands on the card
    mid-swipe leaves the swipe to the first, so once both lift the hold has ended and
    the card stands where it was."""
    context = browser.new_context(
        has_touch=True, viewport={"width": 900, "height": 800}
    )
    page = open_page(browser, serve(DECK_PAGE), context=context)
    open_card(page, "store-ask")
    cdp = context.new_cdp_session(page)

    def touch(kind, *points):
        cdp.send(
            "Input.dispatchTouchEvent",
            {
                "type": kind,
                "touchPoints": [{"x": x, "y": y, "id": i} for i, x, y in points],
            },
        )

    box = page.locator("#store-ask-h").bounding_box()
    x, y = box["x"] + 20, box["y"] + box["height"] / 2

    def swipe():
        touch("touchStart", (0, x, y))
        touch("touchMove", (0, x + 15, y))
        touch("touchMove", (0, x + 30, y))
        wait_for_check_api(page, "(api) => api.dragHeld()")

    swipe()
    touch("touchEnd")
    wait_for_check_api(page, "(api) => !api.dragHeld()")

    swipe()
    touch("touchStart", (0, x + 30, y), (1, x + 80, y + 2))
    touch("touchEnd")
    wait_for_check_api(page, "(api) => !api.dragHeld()")
    assert page.evaluate(OPEN) == "store-ask"
    assert (
        page.evaluate("() => document.querySelector('#store-ask').style.translate")
        == ""
    )


# The height each motion of the deck's own box ends at, recorded as it starts.
RECORD_RESIZES = """() => {
  window.lfDeckResizes = [];
  const animate = Element.prototype.animate;
  Element.prototype.animate = function (frames, options) {
    if (this.localName === 'lf-deck' && Array.isArray(frames) && frames.at(-1)?.height)
      window.lfDeckResizes.push(parseFloat(frames.at(-1).height));
    return animate.call(this, frames, options);
  };
}"""


def test_the_deck_grows_to_the_end_frame_it_lands_on(browser, serve):
    """The last answer brings up the end frame with its record of the pass, and the
    deck's height glides to the frame's whole height, where the frame is taller than the
    card it follows, rather than to an empty frame's and then jumps."""
    page = open_page(browser, serve(DECK_PAGE))
    page.emulate_media(reduced_motion="no-preference")
    page.evaluate(RECORD_RESIZES)
    height = (
        "() => parseFloat(getComputedStyle(document.querySelector('lf-deck')).height)"
    )
    held = None
    for name, option in [
        ("store", "store-yes"),
        ("beta", "beta-no"),
        ("notes", "notes-no"),
    ]:
        open_card(page, f"{name}-ask")
        page.wait_for_function(LANDED)
        held = page.evaluate(height)
        page.evaluate("() => { window.lfDeckResizes.length = 0; }")
        answer(page, option)
    expect(page.locator("lf-deck .lf-deck-recap > li")).to_have_count(3)
    page.wait_for_function(LANDED)
    landed = page.evaluate(height)
    resizes = page.evaluate("() => window.lfDeckResizes")
    assert abs((resizes[-1] if resizes else held) - landed) <= 1, (resizes, landed)
    frame = page.locator("lf-deck .lf-deck-end").bounding_box()
    deck = page.locator("lf-deck").bounding_box()
    assert frame["y"] + frame["height"] <= deck["y"] + deck["height"] + 1


def test_as_a_workspace_body_a_tall_card_scrolls_under_the_bar(browser, serve):
    """As a workspace's body the deck is the box that scrolls, and a card taller than
    the room scrolls under the bar: read down to its options, the bar still stands at
    the deck's top, and the options take a press."""
    context = browser.new_context(viewport={"width": 1100, "height": 560})
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Deck as a workspace",
                "<header><h1>Before the release</h1></header>"
                + '<lf-deck id="deck">'
                + TALL_CARD
                + card("store", "Keep Redis?")
                + "</lf-deck>",
                layout="workspace",
            )
        ),
        context=context,
    )
    open_card(page, "tall-ask")
    page.wait_for_function(LANDED)
    bar = page.locator("lf-deck .lf-deck-bar")
    before = bar.bounding_box()["y"]
    box = page.locator("#tall-ask").bounding_box()
    page.mouse.move(box["x"] + 40, box["y"] + 80)
    page.mouse.wheel(0, 2000)
    page.wait_for_function(
        "() => { const d = document.querySelector('lf-deck');"
        " return d.scrollTop > 0 && d.scrollTop >= d.scrollHeight - d.clientHeight - 1; }"
    )
    expect(page.locator("#tall-no")).to_be_in_viewport()
    assert bar.bounding_box()["y"] == before
    answer(page, "tall-no")
    open_card(page, "store-ask")
