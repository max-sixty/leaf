"""Tests scheduled by the measured cost of their boundary."""

from browser.controls.test_press_away import centre, drag, tap
from browser.test_render_reactions import select_paragraph
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE
from render_harness import (
    open_page,
)


def test_a_press_away_puts_the_response_bar_away(browser, serve):
    page = open_page(browser, serve(PANEL_PAGE))
    bar = page.locator(".lf-fab-bar")
    outside = centre(page.locator("h1"))
    select_paragraph(page, "#how-store")
    expect(bar).to_be_visible()
    # Selecting the words typed in its field past its edge leaves it standing.
    drag(page, centre(bar.locator(".lf-fab-input")), outside)
    expect(bar).to_be_visible()
    tap(page, outside)
    expect(bar).to_be_hidden()
    select_paragraph(page, "#how-store")
    expect(bar).to_be_visible()
    page.mouse.click(*outside)
    expect(bar).to_be_hidden()
    select_paragraph(page, "#how-store")
    expect(bar).to_be_visible()
    page.keyboard.press("Escape")
    expect(bar).to_be_hidden()
