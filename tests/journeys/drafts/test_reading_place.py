"""Tests scheduled by the measured cost of their boundary."""

import pytest
from browser.drafts.test_reading_place import (
    GROW_ABOVE_AND_SCROLL,
    READ_HEADING,
    reading_section_page,
)
from render_harness import open_page, resized, scroll_settled

from leaf.render_checks import one_frame

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_page_that_never_settles_lets_the_held_place_go_after_a_while(browser, serve):
    """A chart whose box breathes forever keeps the page's rendering from ever reading
    settled. A width change restores the reader's place and holds it while the layout
    settles, but no longer than a moment: well after, a script that scrolls as content
    grows above the reader moved the page, and the next width change starts from
    there rather than putting the held place back."""
    source = reading_section_page(
        "A page that never settles",
        "<style>@keyframes breathe { from { width: 60%; } to { width: 100%; } }"
        " .breathe #breathing { animation: breathe 3s linear infinite alternate; }"
        "</style>"
        '<div id="breathing"><lf-chart id="spin" data-height="120"><pre>\n'
        '{ ariaLabel: "Two teams", marks: [Plot.barY([{team: "a", n: 12},'
        ' {team: "b", n: 19}], {x: "team", y: "n"})] }\n</pre></lf-chart></div>',
    )
    page = open_page(browser, serve(source))
    page.evaluate("document.documentElement.classList.add('breathe')")

    def settle():
        # The page never reads settled, so wait out its scrolls and a few frames.
        scroll_settled(page)
        page.wait_for_timeout(300)
        one_frame(page)

    resized(page, 390, 800)
    settle()
    page.evaluate("location.hash = 'read'")
    settle()
    box = page.locator("#read p").first.bounding_box()
    page.mouse.move(box["x"] + 20, box["y"] + 5)
    page.mouse.wheel(0, 8)
    settle()
    resized(page, 1200, 800)
    settle()
    held = page.evaluate(READ_HEADING)
    page.wait_for_timeout(1500)
    page.evaluate(GROW_ABOVE_AND_SCROLL)
    settle()
    assert page.evaluate(READ_HEADING) < held - 300, "the script's scroll was undone"
    resized(page, 390, 800)
    settle()
    assert page.evaluate(READ_HEADING) < held - 300, "the held place came back"
