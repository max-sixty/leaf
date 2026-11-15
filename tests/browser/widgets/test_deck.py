"""A deck of cards: an answer moves it on, Later keeps a card for the end of the pass,
Back and Review step through answered cards, and a new tab opens where a card waits."""

import pytest
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import leaf_page, open_page, round_trip

from leaf import event_log as events_model

pytestmark = pytest.mark.shifts_unsurveyed


def card(name, question):
    return f"""<lf-ask id="{name}-ask"><h3>{question}</h3>
      <lf-options id="{name}-choice" choose>
        <lf-option id="{name}-yes"><strong>Yes</strong></lf-option>
        <lf-option id="{name}-no"><strong>No</strong></lf-option>
      </lf-options></lf-ask>"""


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


def test_the_end_of_the_pass_lists_each_answer_and_a_row_opens_its_card(browser, serve):
    """Once the pass is over, the cards are put away but the end frame lists each one's
    question beside the answer given, or that it still waits; a row opens its card, by
    Enter as by pointer."""
    page = open_page(browser, serve(DECK_PAGE))
    open_card(page, "store-ask")
    answer(page, "store-yes")
    open_card(page, "beta-ask")
    forward(page, "Later")
    open_card(page, "notes-ask")
    answer(page, "notes-no")
    expect(page.locator("lf-deck > [data-lf-deck-open]")).to_have_count(0)

    recap = page.locator("lf-deck .lf-deck-end .lf-deck-recap > li")
    expect(recap.locator("a")).to_have_text(
        ["Keep Redis?", "Ship the beta?", "Post the notes?"]
    )
    expect(recap.locator("span")).to_have_text(["Yes", "Still waiting", "No"])

    page.locator("lf-deck .lf-deck-end").get_by_role("button").focus()
    page.keyboard.press("Tab")
    page.keyboard.press("Tab")
    expect(recap.get_by_role("link", name="Ship the beta?")).to_be_focused()
    page.keyboard.press("Enter")
    open_card(page, "beta-ask")
    forward(page, "Later")
    expect(page.locator("lf-deck > [data-lf-deck-open]")).to_have_count(0)
    recap.get_by_role("link", name="Keep Redis?").click()
    open_card(page, "store-ask")


def test_a_new_tab_opens_on_the_first_card_that_waits(browser, serve):
    """A tab that never showed the deck opens on the first card still waiting, not on
    the answered card the markup puts first; the tab that answered keeps its place."""
    url = live_url(serve(DECK_PAGE))
    first = open_page(browser, url)
    answer(first, "store-no")
    open_card(first, "beta-ask")

    second = open_page(browser, url)
    open_card(second, "beta-ask")


def test_an_answer_from_another_window_leaves_the_card_in_place(browser, serve):
    """A card the user pressed in stays put when its answer comes from a window other
    than this one, which is news; Next then moves on."""
    url = live_url(serve(DECK_PAGE))
    watching = open_page(browser, url)
    watching.locator("#store-ask h3").click()
    watching.evaluate("() => { Document.prototype.hasFocus = () => false; }")

    answering = open_page(browser, url)
    answer(answering, "store-yes")
    expect(watching.locator("lf-deck .lf-deck-forward")).to_have_attribute(
        "aria-label", "Next"
    )
    open_card(watching, "store-ask")


DRAFT_DECK_PAGE = leaf_page(
    "Deck with a draft",
    '<h1>Before the release</h1><lf-deck id="deck">'
    '<lf-ask id="reply-ask"><h3>Send this reply?</h3>'
    '<lf-draft id="reply-draft"><pre>\nThanks for the report.</pre></lf-draft>'
    '<lf-options id="reply-choice" choose>'
    '<lf-option id="reply-send"><strong>Send it</strong></lf-option>'
    '<lf-option id="reply-hold"><strong>Hold it</strong></lf-option>'
    "</lf-options></lf-ask>" + card("notes", "Post the notes?") + "</lf-deck>",
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
TALL_DECK_PAGE = leaf_page(
    "Deck below an opening",
    "<h1>Before the release</h1>"
    + "".join(f"<p>{SENTENCE * 3}</p>" for _ in range(4))
    + '<lf-deck id="deck">'
    + card("store", "Keep Redis?")
    + '<lf-ask id="tall-ask"><h3>Ship the beta on every platform?</h3>'
    + "".join(f"<p>{SENTENCE * 3}</p>" for _ in range(7))
    + '<lf-options id="tall-choice" choose>'
    '<lf-option id="tall-yes"><strong>Yes</strong></lf-option>'
    '<lf-option id="tall-no"><strong>No</strong></lf-option>'
    "</lf-options></lf-ask></lf-deck><p>After the deck.</p>",
)

# Whether the open card's last option stands clear of the panel, which covers the
# window's foot, with the deck's bar in the window above it.
ANSWERABLE = """() => {
  const deck = document.querySelector('lf-deck');
  const last = deck.querySelector(':scope > [data-lf-deck-open] lf-option:last-of-type');
  if (!last || deck.matches('[data-lf-deck-flying]')) return false;
  const box = last.getBoundingClientRect();
  const hit = document.elementFromPoint(box.left + box.width / 2, box.bottom - 4);
  return last.contains(hit) && deck.querySelector('.lf-deck-bar').getBoundingClientRect().top >= 0;
}"""


def test_a_card_brought_back_below_the_opening_stands_whole_above_the_panel(
    browser, serve
):
    """Go through brings back a card left for later where the pass began, below the
    page's opening. A card taller than the room there scrolls up until its options
    clear the panel, with the bar still above it, so the press that brought it leaves
    it answerable."""
    page = open_page(browser, serve(TALL_DECK_PAGE))
    open_card(page, "store-ask")
    answer(page, "store-yes")
    open_card(page, "tall-ask")
    forward(page, "Later")
    expect(page.locator("lf-deck > [data-lf-deck-open]")).to_have_count(0)

    again(page, "Go through the 1 left")
    open_card(page, "tall-ask")
    page.wait_for_function(ANSWERABLE)


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
