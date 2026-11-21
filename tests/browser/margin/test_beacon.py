"""Where the comment box the user's keys type into stands, once a scroll carries it
out of the window."""

import pytest
from playwright.sync_api import expect
from render_harness import leaf_page, open_page, resized, scroll_settled

from browser.margin import _comment_on

PAGE = leaf_page(
    "Beacon",
    """<h1 id="title">Beacon</h1>
<p id="early">The early paragraph, with a thread on it.</p>
<div style="height: 250vh"></div>
<p id="end">The end.</p>""",
)
BEACON = ".lf-writing-beacon"


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_comment_box_holding_the_caret_off_the_window_shows_a_beacon_toward_it(
    request, serve, engine
):
    """A press on a thread's margin entry opens its card with the caret in the reply,
    so a key types there wherever the card stands. Scrolled out of the window, the card
    leaves a beacon at the edge toward it, in its column; a press on the beacon brings
    the card back with the caret where it was. Stood on the thread instead, after
    Escape, a key lets go of what the user can't see, so the card leaves no beacon."""
    url = serve(PAGE, events=[_comment_on("early", "Why here?")])
    page = open_page(request.getfixturevalue(engine), url)
    resized(page, 1440, 800)
    page.locator('[data-lf-margin-for="early"] .lf-margin-marker').click()
    card = page.locator(".lf-margin-preview")
    reply = card.locator("leaf-text")
    expect(reply).to_be_focused()
    beacon = page.locator(BEACON)
    expect(beacon).to_be_hidden()

    page.mouse.move(700, 400)
    page.mouse.wheel(0, 1600)
    scroll_settled(page)
    expect(card).not_to_be_in_viewport()
    expect(beacon).to_be_visible()
    expect(beacon).to_have_attribute("data-lf-towards", "up")
    box, column = beacon.bounding_box(), card.bounding_box()
    assert 0 <= box["y"] <= 12, box
    assert column["x"] - 1 <= box["x"] <= column["x"] + 1, (box, column)

    beacon.click()
    scroll_settled(page)
    expect(card).to_be_in_viewport()
    expect(reply).to_be_focused()
    expect(beacon).to_be_hidden()

    page.keyboard.press("Escape")
    expect(card.locator(".lf-page-thread")).to_be_focused()
    page.mouse.wheel(0, 1600)
    scroll_settled(page)
    expect(card).not_to_be_in_viewport()
    expect(beacon).to_be_hidden()
