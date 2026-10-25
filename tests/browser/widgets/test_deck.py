"""A deck of cards: an answer moves it on, Later keeps a card for the end of the pass,
Back and Review step through answered cards, and a new tab opens where a card waits."""

import pytest
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import leaf_page, open_page, round_trip

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

    forward(page, "Go through the 1 left")
    open_card(page, "beta-ask")
    page.locator("lf-deck .lf-deck-back").click()
    open_card(page, "store-ask")
    forward(page, "Next")
    open_card(page, "beta-ask")
    answer(page, "beta-yes")
    expect(page.locator("lf-deck > [data-lf-deck-open]")).to_have_count(0)

    forward(page, "Review from the start")
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
