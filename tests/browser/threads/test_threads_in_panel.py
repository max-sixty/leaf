"""Where a thread about a passage opens: beside its passage as a card, or in the floating
panel once the user chose the panel with a card's Open in panel, until the panel's Show
on page chooses cards again (thread/threads-in-panel.js; the rule is
thread/destination.js's)."""

import pytest
from playwright.sync_api import expect
from render_cases_interaction import panel_comment
from render_harness import leaf_page, open_page, open_threads, resized, scroll_settled

from leaf.render_checks import wait_until_ready
from leaf_dev.browser import PANEL, PANEL_THREAD, panel_view

pytestmark = pytest.mark.shifts_unsurveyed

FILLER = "".join(f"<p>Filler paragraph {n}.</p>" for n in range(40))
SECTIONS = ("near", "mid", "far")


def threads_page(serve):
    """A page with a thread on each of three sections far apart, and their ids."""
    url = serve(
        leaf_page(
            "Where threads open",
            "<h1>Where threads open</h1>"
            + FILLER.join(
                f"<section id={name}><p>The question about the {name} section.</p>"
                "</section>"
                for name in SECTIONS
            )
            + FILLER,
        )
    )
    roots = {
        name: panel_comment(serve.page_dir, f"About {name}?", {"section": name})
        for name in SECTIONS
    }
    return url, roots


def test_open_in_panel_and_show_on_page_choose_where_threads_open(browser, serve):
    """A card's Open in panel chooses the panel for the threads the user opens after it,
    by `t`, a press on their words or a row of Threads, until the panel's Show on page
    chooses cards again, and `p` presses whichever of the two the thread shows. A walk
    into the panel brings the thread's passage into view above the panel's view, and a
    press on words the user sees leaves the page where it stands. The choice lasts for
    the tab, across a reload."""
    url, roots = threads_page(serve)
    page = open_page(browser, url)
    resized(page, 1440, 900)
    cards = page.locator(".lf-margin-preview")

    def card(name):
        return cards.locator(f'.lf-page-thread[data-lf-thread="{roots[name]}"]')

    def view(name):
        return page.locator(f'{PANEL_THREAD}[data-lf-thread="{roots[name]}"]')

    page.keyboard.press("t")
    expect(card("near")).to_be_focused()
    cards.get_by_role("button", name="Open in panel").click()
    expect(view("near")).to_be_visible()
    expect(cards).to_be_hidden()

    # The caret leaves the reply for the view, where `t` walks.
    page.keyboard.press("Escape")
    page.keyboard.press("t")
    expect(view("mid")).to_be_focused()
    expect(cards).to_be_hidden()
    scroll_settled(page)
    words = page.locator("#mid p")
    expect(words).to_be_in_viewport()
    assert (
        words.bounding_box()["y"] + words.bounding_box()["height"]
        <= (view("mid").bounding_box()["y"])
    ), "the passage stands clear of the panel's view"

    page.locator("#far").scroll_into_view_if_needed()
    scroll_settled(page)
    before = page.evaluate("scrollY")
    page.locator("#far p").get_by_text("The question about the far section.").click()
    expect(view("far")).to_be_visible()
    expect(cards).to_be_hidden()
    scroll_settled(page)
    assert page.evaluate("scrollY") == before

    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    open_threads(page)
    page.locator(
        f'{panel_view("threads")} .lf-fp-thread[data-lf-key="{roots["near"]}"]'
    ).click()
    expect(view("near")).to_be_visible()
    expect(cards).to_be_hidden()

    page.reload()
    wait_until_ready(page)
    page.keyboard.press("t")
    expect(page.locator(PANEL_THREAD)).to_be_focused()
    expect(cards).to_be_hidden()

    shown = page.locator(PANEL_THREAD).get_attribute("data-lf-thread")
    page.locator(PANEL).get_by_role("button", name="Show on page").click()
    expect(cards.locator(f'.lf-page-thread[data-lf-thread="{shown}"]')).to_be_visible()
    expect(page.locator(PANEL_THREAD)).to_have_count(0)
    page.keyboard.press("Escape")
    page.keyboard.press("t")
    expect(cards.locator(".lf-page-thread")).to_be_focused()
    walked = cards.locator(".lf-page-thread").get_attribute("data-lf-thread")
    assert walked != shown

    page.keyboard.press("p")
    expect(page.locator(f'{PANEL_THREAD}[data-lf-thread="{walked}"]')).to_be_focused()
    expect(cards).to_be_hidden()
    page.keyboard.press("p")
    expect(cards.locator(f'.lf-page-thread[data-lf-thread="{walked}"]')).to_be_focused()
    expect(page.locator(PANEL_THREAD)).to_have_count(0)


def test_a_narrow_window_puts_threads_in_the_panel_and_keeps_the_choice(browser, serve):
    """On a window too narrow for cards every thread opens in the panel, whatever the
    user chose, and Show on page there goes to the passage and chooses nothing. A window
    widening gives a thread back to its card under the cards choice, and leaves it in
    the panel under the panel's."""
    url, roots = threads_page(serve)
    page = open_page(browser, url)
    cards = page.locator(".lf-margin-preview")

    def view(name):
        return page.locator(f'{PANEL_THREAD}[data-lf-thread="{roots[name]}"]')

    resized(page, 700, 900)
    page.keyboard.press("t")
    expect(view("near")).to_be_focused()
    page.locator(PANEL).get_by_role("button", name="Show on page").click()
    expect(page.locator(PANEL_THREAD)).to_have_count(0)
    resized(page, 1440, 900)
    page.keyboard.press("t")
    card = cards.locator(f'.lf-page-thread[data-lf-thread="{roots["near"]}"]')
    expect(card).to_be_focused()

    cards.get_by_role("button", name="Open in panel").click()
    expect(view("near")).to_be_visible()
    resized(page, 700, 900)
    page.locator(PANEL).get_by_role("button", name="Show on page").click()
    expect(page.locator(PANEL_THREAD)).to_have_count(0)
    # Show on page left the user at the thread's place, so `t` arrives at it first.
    page.keyboard.press("t")
    expect(view("near")).to_be_focused()
    page.keyboard.press("t")
    expect(view("mid")).to_be_focused()
    resized(page, 1440, 900)
    expect(view("mid")).to_be_visible()
    expect(cards).to_be_hidden()
