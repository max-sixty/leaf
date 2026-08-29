"""The document's shared, semantic margin map."""

import re

import pytest
from axe_playwright_python.sync_playwright import Axe
from leaf import event_log as events_model
from playwright.sync_api import expect
from render_support import (
    DECISION_PAGE,
    _publish,
    compare_with,
    live_url,
    open_page,
    panel_settled,
    resized,
    round_trip,
    ticked,
    told,
)

pytestmark = pytest.mark.nightly

COMMENT_ON_DECISION = {
    "kind": "comment",
    "author": "user",
    "revision": 1,
    "text": "Check whether these jobs can share one visit.",
    "anchor": {"section": "bracket"},
}
OUTCOME_ON_DECISION = {
    "kind": "action",
    "author": "user",
    "revision": 1,
    "widget": "bracket",
    "action": "choose",
    "detail": {"options": ["br-steel"]},
}


def test_the_preview_stands_in_the_room_the_page_has_beside_the_panel(browser, serve):
    """An open panel takes its strip out of the page, so the margin's preview keeps to
    what is left. Placed against the window instead, a card the reader left open stands
    over the panel — and the box it covers first is the narrowing box at the top of it,
    whose ring then reads as a control the reader can see only half of."""
    page, errors = open_page(
        browser, serve(DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION])
    )
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment outcome"]')
    marker.hover()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    page.wait_for_function(
        "() => Boolean(document.querySelector('.lf-margin-preview').style.left)"
    )
    preview_box = preview.bounding_box()
    panel_box = page.locator(".lf-panel").bounding_box()
    room_right = page.evaluate("() => document.body.getBoundingClientRect().right")
    assert panel_box["x"] < page.evaluate("innerWidth"), (
        f"the panel is not standing beside the page, so this reads nothing: {panel_box}"
    )
    assert preview_box["x"] + preview_box["width"] <= panel_box["x"] + 0.5, (
        f"the preview stands in the panel: {preview_box} against {panel_box}"
    )
    assert preview_box["x"] + preview_box["width"] <= room_right + 0.5, (
        f"the preview stands outside the page's room: {preview_box} of {room_right}"
    )
    assert preview_box["x"] >= 0, (
        f"the preview is off the left of the window: {preview_box}"
    )

    assert errors == []
    page.close()


def test_the_margin_groups_meanings_at_one_destination_without_moving_the_page(
    browser, serve
):
    """One location is one marker, even when several kinds of work meet there.

    Hover and keyboard inspection are readings, not travel. They may preview and
    outline the destination, but must preserve the user's place in the document.
    """
    page, errors = open_page(
        browser, serve(DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION])
    )
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment outcome"]')
    expect(marker).to_have_count(1)
    expect(marker.locator(".lf-margin-count")).to_have_text("2")
    expect(marker).to_have_attribute(
        "aria-label", re.compile(r"Comment, Outcome, \d+ of")
    )

    before = page.evaluate("() => document.body.scrollTop")
    marker.hover()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    expect(page.locator("#bracket")).to_have_class(re.compile(r"lf-margin-target"))
    page.wait_for_function(
        "() => Boolean(document.querySelector('.lf-margin-preview').style.left)"
    )
    main_box = page.locator("main").bounding_box()
    preview_box = preview.bounding_box()
    assert preview_box["x"] >= main_box["x"] + main_box["width"]
    assert preview_box["x"] + preview_box["width"] <= page.evaluate("innerWidth")
    assert page.evaluate("() => document.body.scrollTop") == before

    marker.click()
    expect(marker).to_have_attribute("aria-pressed", "true")
    expect(page.locator(".lf-margin-thread")).to_have_count(1)
    expect(page.locator(".lf-margin-preview-action")).to_have_count(1)
    page.locator(".lf-margin-preview-close").click()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(marker).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator(".lf-margin-thread textarea")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-thread .lf-conversation-thread")).to_be_focused()
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


def test_a_thread_can_be_answered_in_the_margin_without_opening_threads(browser, serve):
    """The anchored thread is the margin's primary interaction surface."""
    page, errors = open_page(
        browser, serve(DECISION_PAGE, events=[COMMENT_ON_DECISION])
    )
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment"]')
    marker.click()
    thread = page.locator(".lf-margin-thread")
    reply = thread.locator("textarea")

    expect(thread.locator(".lf-conversation-body")).to_have_text(
        COMMENT_ON_DECISION["text"]
    )
    reply.fill("Yes. One visit can cover both jobs.")
    ticked(page)
    expect(reply).to_have_value("Yes. One visit can cover both jobs.")
    expect(reply).to_be_focused()
    thread.get_by_role("button", name="Send").click()
    round_trip(page)

    expect(thread.locator(".lf-conversation-thread")).to_contain_text(
        "Yes. One visit can cover both jobs."
    )
    expect(page.locator(".lf-panel")).not_to_have_class(re.compile(r"\bopen\b"))
    root_id = thread.locator(".lf-conversation-thread").get_attribute("data-thread")
    replies = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("kind") == "reply" and event.get("parent") == root_id
    ]
    assert [event["text"] for event in replies] == [
        "Yes. One visit can cover both jobs."
    ]

    assert errors == []
    page.close()


def test_only_a_page_with_threads_reserves_the_conversation_margin(browser, serve):
    """Other map meanings keep their narrow rail until a thread needs the card."""
    page, errors = open_page(
        browser, serve(DECISION_PAGE, events=[OUTCOME_ON_DECISION])
    )

    def padding_right():
        return page.locator("body").evaluate(
            "body => getComputedStyle(body).paddingRight"
        )

    assert padding_right() == "54px"

    events_model.append_event(serve.page_dir, COMMENT_ON_DECISION)
    told(page)
    assert padding_right() == "384px"

    assert errors == []
    page.close()


def test_the_margin_keeps_its_page_coordinate_while_the_reader_scrolls(browser, serve):
    """Runtime chrome and authored content share one document-space coordinate."""
    page, errors = open_page(
        browser, serve(DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION])
    )
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment outcome"]')
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
        browser, serve(DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION])
    )
    resized(page, 390, 760)
    expect(page.locator(".lf-living-margin")).to_be_hidden()
    toggle = page.locator(".lf-page-map-toggle")
    expect(toggle).to_be_visible()
    expect(toggle).to_have_text(re.compile(r"Map \(\d+\)"))
    assert toggle.evaluate(
        "button => button.previousElementSibling.matches('.lf-signoff, .lf-threads-toggle')"
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
        browser, serve(DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION])
    )
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment outcome"]')
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
        browser, serve(DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION])
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
        browser, serve(DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION])
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
        page.locator('.lf-margin-marker[data-lf-kinds="comment outcome"]').locator(
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
        browser, serve(DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION])
    )
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment outcome"]')
    marker.click()
    actions = page.locator(".lf-margin-preview-action")
    expect(actions).to_have_count(1)
    expect(page.locator(".lf-margin-thread")).to_have_count(1)

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
    expect(actions).to_have_count(1)
    expect(page.locator(".lf-margin-thread")).to_have_count(2)
    expect(page.locator(".lf-margin-thread").last).to_contain_text(
        "A second reading arrived while the preview was pinned."
    )

    assert errors == []
    page.close()


def test_a_live_version_keeps_the_reader_on_the_same_margin_location(browser, serve):
    """Replacing authored main must not discard focus held by retained map chrome."""
    version_url = serve(
        DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION]
    )
    page, errors = open_page(browser, live_url(version_url))
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment outcome"]')
    marker.focus()
    expect(marker).to_be_focused()

    (serve.page_dir / "index.html").write_text(
        DECISION_PAGE.replace("Three jobs", "Four jobs")
    )
    told(page)
    expect(page.get_by_role("heading", name="Four jobs")).to_be_visible()
    expect(marker).to_be_focused()

    assert errors == []
    page.close()


def test_a_live_version_retargets_an_open_margin_preview(browser, serve):
    """A retained preview must outline the new document's matching destination."""
    version_url = serve(
        DECISION_PAGE, events=[OUTCOME_ON_DECISION, COMMENT_ON_DECISION]
    )
    page, errors = open_page(browser, live_url(version_url))
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment outcome"]')
    marker.click()
    action = page.locator(".lf-margin-preview-action")
    action.focus()
    expect(action).to_be_focused()
    expect(page.locator("#bracket")).to_have_class(re.compile(r"lf-margin-target"))

    (serve.page_dir / "index.html").write_text(
        DECISION_PAGE.replace("Three jobs", "Four jobs")
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
    url = serve(DECISION_PAGE)
    _publish(
        serve.page_dir,
        2,
        DECISION_PAGE.replace("Three jobs", "Four jobs"),
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
