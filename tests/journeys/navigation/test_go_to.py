"""Tests scheduled by the measured cost of their boundary."""

import re

import pytest
from browser.threads import open_panel_thread
from playwright.sync_api import expect
from render_cases_interaction import OBLIGATIONS_PAGE, serve_obligations
from render_cases_navigation import _publish
from render_harness import PANEL, all_pages_offered, open_page, panel_view, resized

from leaf.log import event_log as events_model

pytestmark = pytest.mark.shifts_unsurveyed


def test_global_destinations_switch_from_a_covering_workspace(
    browser, serve, live_leaf
):
    """An open view keeps the global Go-to addresses that can replace it."""
    live_leaf("second", "A second leaf")
    url = serve_obligations(serve, comments=1)
    _publish(serve.page_dir, 2, OBLIGATIONS_PAGE, "two")
    page = open_page(browser, url)
    resized(page, 420, 800)
    all_pages_offered(page)

    def view(name):
        return page.locator(panel_view(name))

    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    expect(view("leaves")).to_be_visible()

    for key, opened, closed in (
        ("Shift+m", "queue", "leaves"),
        ("Shift+t", "threads", "queue"),
    ):
        page.keyboard.press("g")
        expect(page.locator("body")).to_have_attribute("data-lf-go-to-active", "")
        page.keyboard.press(key)
        expect(view(opened)).to_be_visible()
        expect(view(closed)).to_have_count(0)

    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    page_map = page.locator(".lf-page-map-dialog")
    expect(page_map).to_be_visible()
    expect(page_map.get_by_role("searchbox")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page_map).to_be_hidden()

    # From a thread open in the panel, Versions opens over the leaf's menu in the
    # thread's place, as every view does; Escape steps back to the menu, then puts the
    # view away.
    thread_id = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    open_panel_thread(page, thread_id).focus()
    page.keyboard.press("g")
    page.keyboard.press("Shift+v")
    versions = view("versions")
    expect(versions).to_be_visible()
    assert versions.evaluate("view => view.contains(document.activeElement)")
    expect(versions.locator(".lf-fp-version")).to_have_count(2)
    expect(page.locator(".lf-fp-head .lf-fp-back")).to_have_accessible_name(
        "Back to Menu"
    )
    page.keyboard.press("Escape")
    expect(versions).to_have_count(0)
    expect(page.locator(PANEL)).to_have_attribute("data-lf-open", "menu")
    page.keyboard.press("Escape")
    expect(page.locator(PANEL)).not_to_have_attribute("data-lf-open", re.compile("."))
