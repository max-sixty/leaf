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
    expect(control).to_have_attribute("title", title)
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
        "title", "Next"
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
