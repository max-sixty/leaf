"""Where a thread about a passage opens: beside its passage as a card, or in the floating
panel once the user chose the panel with a card's Open in panel, until the panel's Show
on page chooses cards again (records/thread/threads-in-panel.js; the rule is
records/thread/destination.js's)."""

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import SEAT, SEATED_OBLIGATION_PAGE, panel_comment
from render_harness import (
    leaf_page,
    open_page,
    open_threads,
    resized,
    round_trip,
    scroll_settled,
    sending,
    undo,
    word_point,
    write,
)

from browser.navigation.test_reading_place import ITEMS_LAYER, ITEMS_WIDGETS
from browser.threads import PANEL_REPLY, open_panel_thread
from leaf.source.render_checks import wait_until_ready
from leaf_dev.browser import PANEL, PANEL_THREAD, choose_threads_in_panel, panel_view

pytestmark = pytest.mark.shifts_unsurveyed

FILLER = "".join(f"<p>Filler paragraph {n}.</p>" for n in range(40))
SECTIONS = ("near", "mid", "far")


def threads_page(serve):
    """A page with a thread on the words of each of three sections far apart, and their
    ids."""
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
        name: panel_comment(
            serve.page_dir,
            f"About {name}?",
            {"section": name, "quote": f"question about the {name}"},
        )
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
    cards.get_by_role("button", name="Open in panel", exact=True).click()
    # The click lands on the thread, where `t` walks on.
    expect(view("near")).to_be_focused()
    expect(cards).to_be_hidden()

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
    point = word_point(page.locator("#far p"), "question")
    page.mouse.click(point["x"], point["y"])
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
    # The reload returns the user to the reply the row's press put them in (records/history.js),
    # which Escape leaves for its thread, where `t` walks on.
    expect(page.locator(PANEL_REPLY)).to_be_focused()
    page.keyboard.press("Escape")
    page.keyboard.press("t")
    expect(page.locator(PANEL_THREAD)).to_be_focused()
    expect(cards).to_be_hidden()

    shown = page.locator(PANEL_THREAD).get_attribute("data-lf-thread")
    page.locator(PANEL).get_by_role("button", name="Show on page", exact=True).click()
    expect(cards.locator(f'.lf-page-thread[data-lf-thread="{shown}"]')).to_be_visible()
    expect(page.locator(PANEL_THREAD)).to_have_count(0)
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
    page.locator(PANEL).get_by_role("button", name="Show on page", exact=True).click()
    expect(page.locator(PANEL_THREAD)).to_have_count(0)
    resized(page, 1440, 900)
    page.keyboard.press("t")
    card = cards.locator(f'.lf-page-thread[data-lf-thread="{roots["near"]}"]')
    expect(card).to_be_focused()

    cards.get_by_role("button", name="Open in panel", exact=True).click()
    expect(view("near")).to_be_visible()
    resized(page, 700, 900)
    page.locator(PANEL).get_by_role("button", name="Show on page", exact=True).click()
    expect(page.locator(PANEL_THREAD)).to_have_count(0)
    # Show on page left the user at the thread's place, so `t` arrives at it first.
    page.keyboard.press("t")
    expect(view("near")).to_be_focused()
    page.keyboard.press("t")
    expect(view("mid")).to_be_focused()
    resized(page, 1440, 900)
    expect(view("mid")).to_be_visible()
    expect(cards).to_be_hidden()


def test_resuming_a_reply_the_panel_holds_for_a_narrow_window_leaves_it_owed_back(
    browser, serve
):
    """Resume writing a reply in a thread the panel holds only because the window is
    too narrow for its card goes on in the panel, where the thread stands, and leaves
    the reason Leaf put it there: the window widening gives the thread back to its card,
    the reply with it."""
    url, roots = threads_page(serve)
    page = open_page(browser, url)
    resized(page, 700, 900)
    page.keyboard.press("t")
    view = page.locator(f'{PANEL_THREAD}[data-lf-thread="{roots["near"]}"]')
    expect(view).to_be_focused()
    reply = page.locator(PANEL_REPLY)
    write(reply, "Half a thought")
    page.keyboard.press("Escape")
    expect(reply).not_to_be_focused()
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(reply).to_be_focused()
    resized(page, 1440, 900)
    card = page.locator(
        f'.lf-margin-preview .lf-page-thread[data-lf-thread="{roots["near"]}"]'
    )
    expect(card.locator(".lf-thread-reply leaf-text")).to_have_js_property(
        "value", "Half a thought"
    )
    expect(page.locator(PANEL_THREAD)).to_have_count(0)


def test_a_walk_into_the_panel_draws_the_widget_part_its_thread_is_on(browser, serve):
    """With the panel chosen, a walk to a thread about a part of a widget that the
    widget isn't drawing asks the widget to draw it (`lfRevealDatum`), as a walk to the
    thread's card does, rather than bringing the widget into view with the part still
    undrawn."""
    url = serve(
        leaf_page(
            "Items",
            "<h1>Items</h1><div style='height:1200px'></div>"
            "<lf-items id='items'></lf-items><div style='height:1600px'></div>",
        ),
        layer_registry=ITEMS_LAYER,
        layer_widgets=ITEMS_WIDGETS,
    )
    root = panel_comment(
        serve.page_dir, "About item b?", {"section": "items", "datum": "b/2"}
    )
    page = open_page(browser, url)
    resized(page, 1440, 900)
    choose_threads_in_panel(page)
    page.keyboard.press("t")
    expect(page.locator(f'{PANEL_THREAD}[data-lf-thread="{root}"]')).to_be_focused()
    expect(page.locator('#items [data-item="b"][data-part="2"]')).to_have_count(1)


def test_undo_returns_a_seated_thread_where_the_user_chose(browser, serve):
    """With the panel chosen, taking back a Resolve made in the panel's view of a thread
    a widget also seats on the page opens the thread in the panel again, where the user
    reads threads, though its seat shows it too, rather than leaving the panel on the
    thread the Resolve moved on to."""
    filler = "".join(f"<p>Filler {n}. " + "Words. " * 30 + "</p>" for n in range(12))
    url = serve(SEATED_OBLIGATION_PAGE.replace("</main>", filler + "</main>"))
    seated = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "These jobs can share one visit.",
        },
    )["id"]
    panel_comment(serve.page_dir, "Is the plan ready?")
    page = open_page(browser, url)
    resized(page, 1920, 900)
    view = open_panel_thread(page, seated)
    expect(page.locator(f"#jobs > {SEAT} .lf-page-thread")).to_be_visible()
    page.keyboard.press("Escape")
    expect(view).to_be_focused()
    with sending(page, "the resolve"):
        page.keyboard.press("r")
    expect(view).to_have_count(0)
    undo(page)
    round_trip(page)
    expect(view).to_be_focused()


def test_a_click_on_either_switch_offers_its_way_back(browser, serve):
    """A click on Open in panel or Show on page lands on the thread, where the panel's
    field shows the notice saying the choice lasts, with the press that switches back.
    That press moves the thread the notice was raised for, though pressing it takes the
    user out of the thread, and makes the choice either way."""
    url, roots = threads_page(serve)
    page = open_page(browser, url)
    resized(page, 1440, 900)
    cards = page.locator(".lf-margin-preview")
    card = cards.locator(f'.lf-page-thread[data-lf-thread="{roots["near"]}"]')
    view = page.locator(f'{PANEL_THREAD}[data-lf-thread="{roots["near"]}"]')
    back = page.locator(".lf-fp-field .lf-compose-press")

    page.keyboard.press("t")
    expect(card).to_be_focused()
    cards.get_by_role("button", name="Open in panel", exact=True).click()
    expect(view).to_be_focused()
    expect(back).to_contain_text("Show on page")

    page.locator(PANEL).get_by_role("button", name="Show on page", exact=True).click()
    expect(card).to_be_focused()
    expect(back).to_contain_text("Open in panel")
    back.click()
    expect(view).to_be_focused()
    expect(cards).to_be_hidden()
    page.keyboard.press("t")
    expect(
        page.locator(f'{PANEL_THREAD}[data-lf-thread="{roots["mid"]}"]')
    ).to_be_focused()


def test_a_press_on_words_the_panel_opens_over_brings_them_clear(browser, serve):
    """With the panel chosen, a press on a passage's words low in the window, where the
    panel's view of its thread opens, scrolls the page just far enough to show the
    words above the view."""
    url, roots = threads_page(serve)
    page = open_page(browser, url)
    resized(page, 1440, 900)
    choose_threads_in_panel(page)
    words = page.locator("#mid p")
    words.evaluate(
        "p => scrollBy({top: p.getBoundingClientRect().top - innerHeight + 90,"
        " behavior: 'instant'})"
    )
    scroll_settled(page)
    point = word_point(words, "question")
    page.mouse.click(point["x"], point["y"])
    view = page.locator(f'{PANEL_THREAD}[data-lf-thread="{roots["mid"]}"]')
    expect(view).to_be_visible()
    scroll_settled(page)
    box = words.bounding_box()
    assert box["y"] + box["height"] <= view.bounding_box()["y"] + 1, (
        "the words stand under the panel's view"
    )


def test_p_moves_a_thread_whose_reply_holds_words_the_user_left(browser, serve):
    """`p` lands on the thread it moves, even where its reply holds words the user
    stopped writing, so a second `p` moves it back rather than typing a letter into
    them."""
    url, roots = threads_page(serve)
    page = open_page(browser, url)
    resized(page, 1440, 900)
    cards = page.locator(".lf-margin-preview")
    card = cards.locator(f'.lf-page-thread[data-lf-thread="{roots["near"]}"]')
    view = page.locator(f'{PANEL_THREAD}[data-lf-thread="{roots["near"]}"]')
    page.keyboard.press("t")
    expect(card).to_be_focused()
    reply = card.locator(".lf-thread-reply leaf-text")
    reply.click()
    page.keyboard.type("Halfway through a reply")
    page.keyboard.press("Escape")
    expect(card).to_be_focused()

    page.keyboard.press("p")
    expect(view).to_be_focused()
    page.keyboard.press("p")
    expect(card).to_be_focused()
    expect(reply).to_have_js_property("value", "Halfway through a reply")


def test_a_move_while_writing_keeps_the_caret_in_the_reply(browser, serve):
    """A click on Open in panel while the user writes in the card's reply carries the
    reply to the panel with its words and selection, and the caret stays in it, so
    they go on writing."""
    url, roots = threads_page(serve)
    page = open_page(browser, url)
    resized(page, 1440, 900)
    cards = page.locator(".lf-margin-preview")
    card = cards.locator(f'.lf-page-thread[data-lf-thread="{roots["near"]}"]')
    page.keyboard.press("t")
    expect(card).to_be_focused()
    card.locator(".lf-thread-reply leaf-text").click()
    page.keyboard.type("Halfway through a reply")
    for _ in range(3):
        page.keyboard.press("Shift+ArrowLeft")
    cards.get_by_role("button", name="Open in panel", exact=True).click()
    field = page.locator('.lf-fp-field leaf-text[name="reply"]')
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", "Halfway through a reply")
    assert field.evaluate("f => [f.selectionStart, f.selectionEnd]") == [20, 23]


def test_reopening_a_thread_on_the_element_read_moves_nothing(browser, serve):
    """With the panel chosen, reopening from Threads the thread on an element taller
    than the window, while reading inside it, moves nothing, since the landing of its
    passage finds it already shown. The press is one Back step, as every Threads row's
    is, since it lands the user in a thread they weren't in."""
    paragraphs = "".join(
        f"<p>Tall paragraph {n}. " + "Words. " * 40 + "</p>" for n in range(30)
    )
    url = serve(
        leaf_page(
            "Tall section",
            f"<h1>Tall section</h1>{FILLER}<section id='tall'>{paragraphs}</section>{FILLER}",
        )
    )
    root = panel_comment(serve.page_dir, "About the tall section?", {"section": "tall"})
    page = open_page(browser, url)
    resized(page, 1440, 900)
    choose_threads_in_panel(page)
    page.locator("#tall p").nth(15).evaluate(
        "p => p.scrollIntoView({block: 'start', behavior: 'instant'})"
    )
    scroll_settled(page)
    top, entries = page.evaluate("[scrollY, history.length]")
    open_threads(page)
    page.locator(f'{panel_view("threads")} .lf-fp-thread[data-lf-key="{root}"]').click()
    expect(page.locator(f'{PANEL_THREAD}[data-lf-thread="{root}"]')).to_be_visible()
    scroll_settled(page)
    page.wait_for_function("navigation.transition === null")
    assert page.evaluate("[scrollY, history.length]") == [top, entries + 1]
