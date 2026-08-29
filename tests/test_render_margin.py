"""The document's shared, semantic margin map."""

import re

import pytest
from axe_playwright_python.sync_playwright import Axe
from leaf import event_log as events_model
from playwright.sync_api import expect
from render_support import (
    ASK_PAGE,
    _publish,
    compare_with,
    live_url,
    open_page,
    resized,
    told,
)

pytestmark = pytest.mark.nightly

COMMENT_ON_ASK = {
    "kind": "comment",
    "author": "user",
    "revision": 1,
    "text": "Check whether these jobs can share one visit.",
    "anchor": {"section": "bracket"},
}
DECISION_ON_ASK = {
    "kind": "action",
    "author": "user",
    "revision": 1,
    "widget": "bracket",
    "action": "choose",
    "detail": {"options": ["br-steel"]},
}


def test_the_margin_groups_meanings_at_one_destination_without_moving_the_page(
    browser, serve
):
    """One location is one marker, even when several kinds of work meet there.

    Hover and keyboard inspection are readings, not travel. They may preview and
    outline the destination, but must preserve the user's place in the document.
    """
    page, errors = open_page(
        browser, serve(ASK_PAGE, events=[DECISION_ON_ASK, COMMENT_ON_ASK])
    )
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment decision"]')
    expect(marker).to_have_count(1)
    expect(marker.locator(".lf-margin-count")).to_have_text("2")
    expect(marker).to_have_attribute(
        "aria-label", re.compile(r"Comment, Decision, \d+ of")
    )

    before = page.evaluate("() => document.body.scrollTop")
    marker.hover()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator("#bracket")).to_have_class(re.compile(r"lf-margin-target"))
    assert page.evaluate("() => document.body.scrollTop") == before

    marker.click()
    expect(marker).to_have_attribute("aria-pressed", "true")
    expect(page.locator(".lf-margin-preview-action")).to_have_count(2)
    page.locator(".lf-margin-preview-close").click()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(marker).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator(".lf-margin-preview-action").first).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(marker).to_be_focused()
    held = marker.get_attribute("aria-label")
    page.keyboard.press("ArrowDown")
    assert page.evaluate("() => document.body.scrollTop") == before
    assert page.evaluate("() => document.activeElement.matches('.lf-margin-marker')")
    assert page.locator(":focus").get_attribute("aria-label") != held

    assert errors == []
    page.close()


def test_the_margin_keeps_its_page_coordinate_while_the_reader_scrolls(browser, serve):
    """Runtime chrome and authored content share one document-space coordinate."""
    page, errors = open_page(
        browser, serve(ASK_PAGE, events=[DECISION_ON_ASK, COMMENT_ON_ASK])
    )
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment decision"]')
    target = page.locator("#bracket")

    def offset():
        return marker.bounding_box()["y"] - target.bounding_box()["y"]

    before = offset()
    page.evaluate("() => document.body.scrollBy({top: 320, behavior: 'instant'})")
    page.evaluate(
        "() => import('/runtime/widget-api.js').then(({layoutMarginRows}) => layoutMarginRows())"
    )
    assert offset() == pytest.approx(before, abs=1)

    assert errors == []
    page.close()


def test_the_small_screen_map_is_a_complete_accessible_sheet(browser, serve):
    """The rail becomes a touch-sized index when the margin no longer exists."""
    page, errors = open_page(
        browser, serve(ASK_PAGE, events=[DECISION_ON_ASK, COMMENT_ON_ASK])
    )
    resized(page, 390, 760)
    expect(page.locator(".lf-living-margin")).to_be_hidden()
    toggle = page.locator(".lf-page-map-toggle")
    expect(toggle).to_be_visible()
    expect(toggle).to_have_text(re.compile(r"Map \(\d+\)"))
    assert toggle.evaluate(
        "button => button.previousElementSibling.matches('.lf-signoff, .lf-comments')"
    ), "the small-screen map is not beside the primary feedback controls"

    before = page.evaluate("() => document.body.scrollTop")
    toggle.click()
    sheet = page.locator(".lf-page-map-sheet")
    expect(sheet).to_be_visible()
    expect(sheet.locator(".lf-page-map-action").first).to_have_css("min-height", "44px")
    assert page.evaluate("() => document.body.scrollTop") == before

    result = Axe().run(
        page,
        options={
            "runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag21a"]},
            "resultTypes": ["violations"],
        },
    )
    assert [
        violation["id"]
        for violation in result.response["violations"]
        if violation["impact"] in {"serious", "critical"}
    ] == []

    page.keyboard.press("Escape")
    expect(sheet).to_be_hidden()
    expect(toggle).to_be_focused()
    assert page.evaluate("() => document.body.scrollTop") == before
    assert errors == []
    page.close()


def test_crossing_to_the_small_screen_retires_the_desktop_preview(browser, serve):
    """A responsive posture exposes one map surface, never both at once."""
    page, errors = open_page(
        browser, serve(ASK_PAGE, events=[DECISION_ON_ASK, COMMENT_ON_ASK])
    )
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment decision"]')
    marker.click()
    expect(page.locator(".lf-margin-preview")).to_be_visible()

    resized(page, 390, 760)
    expect(page.locator(".lf-living-margin")).to_be_hidden()
    expect(page.locator(".lf-page-map-toggle")).to_be_visible()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()

    assert errors == []
    page.close()


def test_crossing_to_the_wide_screen_retires_the_small_screen_sheet(browser, serve):
    """The restored desktop rail replaces, rather than layers under, the mobile map."""
    page, errors = open_page(
        browser, serve(ASK_PAGE, events=[DECISION_ON_ASK, COMMENT_ON_ASK])
    )
    resized(page, 390, 760)
    page.locator(".lf-page-map-toggle").click()
    sheet = page.locator(".lf-page-map-sheet")
    expect(sheet).to_be_visible()

    resized(page, 1200, 900)
    expect(page.locator(".lf-living-margin")).to_be_visible()
    expect(page.locator(".lf-page-map-toggle")).to_be_hidden()
    expect(sheet).to_be_hidden()

    assert errors == []
    page.close()


def test_an_open_small_screen_map_reconciles_arriving_meanings(browser, serve):
    """The open sheet is a live projection, not a snapshot from its opening press."""
    page, errors = open_page(
        browser, serve(ASK_PAGE, events=[DECISION_ON_ASK, COMMENT_ON_ASK])
    )
    resized(page, 390, 760)
    page.locator(".lf-page-map-toggle").click()
    sheet = page.locator(".lf-page-map-sheet")
    actions = sheet.locator(".lf-page-map-action")
    expect(actions).to_have_count(4)
    page.keyboard.press("Tab")
    expect(actions.first).to_be_focused()

    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "claude",
            "agent": "Claude",
            "revision": 1,
            "text": "A second reading arrived while the map was open.",
            "anchor": {"section": "bracket"},
        },
    )
    told(page)
    expect(
        page.locator('.lf-margin-marker[data-lf-kinds="comment decision"]').locator(
            ".lf-margin-count"
        )
    ).to_have_text("3")
    expect(actions).to_have_count(5)
    expect(actions.first).to_be_focused()

    assert errors == []
    page.close()


def test_an_open_desktop_preview_reconciles_arriving_meanings(browser, serve):
    """A pinned marker card stays current while its semantic location is retained."""
    page, errors = open_page(
        browser, serve(ASK_PAGE, events=[DECISION_ON_ASK, COMMENT_ON_ASK])
    )
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment decision"]')
    marker.click()
    actions = page.locator(".lf-margin-preview-action")
    expect(actions).to_have_count(2)

    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "claude",
            "agent": "Claude",
            "revision": 1,
            "text": "A second reading arrived while the preview was pinned.",
            "anchor": {"section": "bracket"},
        },
    )
    told(page)
    expect(marker.locator(".lf-margin-count")).to_have_text("3")
    expect(actions).to_have_count(3)

    assert errors == []
    page.close()


def test_a_live_version_keeps_the_reader_on_the_same_margin_location(browser, serve):
    """Replacing authored main must not discard focus held by retained map chrome."""
    version_url = serve(ASK_PAGE, events=[DECISION_ON_ASK, COMMENT_ON_ASK])
    page, errors = open_page(browser, live_url(version_url))
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment decision"]')
    marker.focus()
    expect(marker).to_be_focused()

    (serve.page_dir / "index.html").write_text(
        ASK_PAGE.replace("Three jobs", "Four jobs")
    )
    told(page)
    expect(page.get_by_role("heading", name="Four jobs")).to_be_visible()
    expect(marker).to_be_focused()

    assert errors == []
    page.close()


def test_a_live_version_retargets_an_open_margin_preview(browser, serve):
    """A retained preview must outline the new document's matching destination."""
    version_url = serve(ASK_PAGE, events=[DECISION_ON_ASK, COMMENT_ON_ASK])
    page, errors = open_page(browser, live_url(version_url))
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment decision"]')
    marker.focus()
    page.keyboard.press("Enter")
    action = page.locator(".lf-margin-preview-action").first
    expect(action).to_be_focused()
    expect(page.locator("#bracket")).to_have_class(re.compile(r"lf-margin-target"))

    (serve.page_dir / "index.html").write_text(
        ASK_PAGE.replace("Three jobs", "Four jobs")
    )
    told(page)
    expect(page.get_by_role("heading", name="Four jobs")).to_be_visible()
    expect(action).to_be_focused()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator("#bracket")).to_have_class(re.compile(r"lf-margin-target"))

    assert errors == []
    page.close()


def test_a_version_comparison_joins_the_same_map_and_leaves_with_it(browser, serve):
    """Comparison marks are another projection, not DOM scraped by the map."""
    url = serve(ASK_PAGE)
    _publish(
        serve.page_dir,
        2,
        ASK_PAGE.replace("Three jobs", "Four jobs"),
        "The heading now names four jobs.",
    )
    page, errors = open_page(browser, url.replace("v1.html", "v2.html"))

    compare_with(page, 1)
    expect(
        page.locator('.lf-margin-marker[data-lf-kinds~="change"]')
    ).not_to_have_count(0)
    page.locator(".lf-version").click()
    page.locator('.lf-version-diff[data-lf-version="1"]').click()
    expect(page.locator('.lf-margin-marker[data-lf-kinds~="change"]')).to_have_count(0)

    assert errors == []
    page.close()
