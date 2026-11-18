"""Tests scheduled by the measured cost of their boundary."""

import re

import pytest
from browser.margin import _comment_on
from playwright.sync_api import expect
from render_cases_widgets import RAIL_BAND_PAGE
from render_harness import (
    CHROME_ROOT,
    RELEASE_FOCUS,
    margins_laid_out,
    open_page,
    panel_field,
    resized,
)

from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


def test_o_hides_what_is_drawn_over_the_page_and_the_panel_says_so(browser, serve):
    """`o` hides the annotation layer: every pin, the controls one holds included, and
    the durable marks, while the rail and what stands in it stay, since the rail covers
    nothing. Nothing in the layer takes up room, so no box of the page moves. A press on
    a passage whose mark is hidden opens nothing, and the choice is the tab's, so a
    reload keeps it. An obligation walk reveals the pin it lands on for as long as the
    user stands there.

    Hidden annotations leave a commented page looking as if nobody commented, and the
    hidden layer comes back with a reload, after its notice has passed. So while it is
    hidden the panel's field says so, ahead of the status or after a stance's name,
    until `o` shows the layer again."""
    page = open_page(
        browser,
        serve(
            RAIL_BAND_PAGE,
            events=[_comment_on("gap", quote="Prose far enough below the changes")],
        ),
    )
    resized(page, 1440, 900)
    margins_laid_out(page)
    pin = page.locator('.lf-margin-cluster[data-lf-margin-for="sug-card"]')
    rail = page.locator('.lf-margin-cluster[data-lf-margin-for="sug-copy"]')
    expect(pin).to_have_attribute("data-lf-place", "pin")
    expect(rail).to_have_attribute("data-lf-place", "rail")
    boxes = """() => [...document.querySelectorAll('main, main *')].map(el => {
      const b = el.getBoundingClientRect();
      return [b.left, b.top, b.width, b.height].map(Math.round).join(',');
    })"""
    # The words the durable marks paint, which hiding the layer registers empty.
    marked = """() => [...(CSS.highlights.get('lf-mark') ?? [])]
      .map(range => range.toString()).join(' ')"""
    passage = "Prose far enough below the changes"
    page.wait_for_function(f"() => ({marked})() === {passage!r}")
    before = page.evaluate(boxes)

    page.evaluate(RELEASE_FOCUS)
    page.keyboard.press("o")
    expect(page.locator(CHROME_ROOT)).to_have_attribute(
        "data-lf-annotations-hidden", ""
    )
    expect(pin).to_be_hidden()
    expect(rail).to_be_visible()
    assert page.evaluate(marked) == ""
    margins_laid_out(page)
    assert page.evaluate(boxes) == before, "hiding the annotations moved the page"

    page.locator("#gap").click()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()

    page.reload()
    page.wait_for_selector("body[data-lf-presented]")
    margins_laid_out(page)
    expect(page.locator(CHROME_ROOT)).to_have_attribute(
        "data-lf-annotations-hidden", ""
    )
    expect(pin).to_be_hidden()
    assert page.evaluate(marked) == ""

    field = panel_field(page)
    expect(field).to_have_attribute("data-lf-says", "status")
    expect(field).to_have_attribute(
        "placeholder", re.compile(r"^Annotations hidden · \S")
    )
    page.evaluate(RELEASE_FOCUS)
    page.keyboard.press("w")
    expect(field).to_have_attribute("data-lf-says", "stance")
    expect(field).to_have_attribute(
        "placeholder", re.compile("^In Draw mode · Annotations hidden")
    )
    page.keyboard.press("Escape")
    expect(page.locator("html")).not_to_have_attribute("data-lf-draw-mode", "")

    # An explicit obligation walk reveals its pin until the user leaves that obligation.
    # The passage follows both obligations, so a step back lands on the last one.
    page.locator("#gap").click()
    page.keyboard.press("Shift+m")
    expect(page.locator("#sug-card")).to_be_focused()
    rendered(page)
    expect(pin).to_be_visible()
    page.evaluate(RELEASE_FOCUS)
    expect(pin).to_be_hidden()
    expect(page.locator(CHROME_ROOT)).to_have_attribute(
        "data-lf-annotations-hidden", ""
    )

    page.keyboard.press("o")
    expect(pin).to_be_visible()
    assert page.evaluate(marked) == passage
    expect(page.locator(CHROME_ROOT)).not_to_have_attribute(
        "data-lf-annotations-hidden", re.compile(".*")
    )
    # The notice saying the annotations are shown passes, and the status stands alone.
    expect(field).to_have_attribute("data-lf-says", "status")
    expect(field).not_to_have_attribute("placeholder", re.compile("Annotations"))
