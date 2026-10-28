"""Visual review keeps readable evidence and stable controls in its dashboard."""

import json

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_cases_navigation import source_revision
from render_harness import (
    CORPUS_SOURCES,
    example_media,
    expect_on_me,
    expect_panel_says,
    leaf_page,
    open_page,
    resized,
    root_overflow,
    scroll_settled,
    sending,
    told,
    undo,
)

from leaf import data as data_model
from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed
VISUAL_REVIEW_GALLERY = next(
    path for path in CORPUS_SOURCES if path.stem == "visual-review-gallery"
)
SELECTED = ".lf-vr-case:not([hidden])"


def test_visual_review_controls_keep_keyboard_navigation_local(browser, serve):
    """Widget commands navigate and approve; typing in feedback keeps its letters."""
    page = open_page(browser, serve(VISUAL_REVIEW_GALLERY))
    widget = page.locator("#visual-review-run")
    case = widget.locator(SELECTED)
    first = case.get_attribute("data-lf-datum")
    widget.locator('.lf-vr-case-button[aria-current="true"]').click()
    page.keyboard.press("n")
    expect(case).not_to_have_attribute("data-lf-datum", first)
    # The walk says where it stands among the cases, as every walk does.
    expect_panel_says(page, "Case 2 of")
    page.keyboard.press("Shift+n")
    expect(case).to_have_attribute("data-lf-datum", first)
    expect_panel_says(page, "Case 1 of")
    with sending(page, "approve the selected comparison"):
        page.keyboard.press("a")
    expect(case.get_by_role("checkbox", name="Looks right")).to_be_checked()
    undo(page)
    expect(case.get_by_role("checkbox", name="Looks right")).not_to_be_checked()
    page.keyboard.press("i")
    expect(case.locator(".lf-vr-details")).to_be_visible()
    page.keyboard.press("Escape")
    expect(case.locator(".lf-vr-details")).to_be_hidden()
    page.keyboard.press("c")
    field = case.locator(".lf-fab-input")
    expect(field).to_be_focused()
    page.keyboard.type("a nice detail")
    expect(field).to_have_js_property("value", "a nice detail")
    expect(case).to_have_attribute("data-lf-datum", first)
    expect(case.get_by_role("checkbox", name="Looks right")).not_to_be_checked()


def test_visual_review_cases_are_independent_on_me_obligations(browser, serve):
    """The global work walk reaches hidden cases, and approval answers only that case."""
    page = open_page(browser, serve(VISUAL_REVIEW_GALLERY))
    widget = page.locator("#visual-review-run")
    case = widget.locator(SELECTED)
    count = page.locator(".lf-fp-on-user")
    expect_on_me(page, 3)
    first = "open-mobile-package-catalog"
    second = "keep-mobile-destinations"
    third = "check-desktop-navigation"
    case.get_by_role("checkbox", name="Looks right").focus()
    page.keyboard.press("m")
    expect(case).to_have_attribute("data-lf-datum", second)
    expect(case).to_be_focused()
    page.keyboard.press("m")
    expect(case).to_have_attribute("data-lf-datum", third)
    expect(case).to_be_focused()
    page.keyboard.press("Shift+m")
    expect(case).to_have_attribute("data-lf-datum", second)
    with sending(page, "approve one independent case"):
        page.keyboard.press("a")
    expect(case.get_by_role("checkbox", name="Looks right")).to_be_checked()
    expect_on_me(page, 2)
    undo(page)
    expect_on_me(page, 3)
    expect(case.get_by_role("checkbox", name="Looks right")).not_to_be_checked()

    # The On me row uses the same destination, even while another case is shown.
    count.click()
    card = page.locator(".lf-fp-on-item").filter(
        has=page.get_by_text("Optional packages get focused destinations", exact=True)
    )
    expect(card).to_be_visible()
    card.get_by_role("button", name="Show", exact=True).click()
    expect(case).to_have_attribute("data-lf-datum", first)
    expect(case).to_be_focused()
    page.keyboard.press("c")
    field = case.locator(".lf-fab-input")
    expect(field).to_be_focused()
    page.keyboard.type("m means mobile")
    expect(field).to_have_js_property("value", "m means mobile")
    expect(case).to_have_attribute("data-lf-datum", first)
    with sending(page, "hand feedback on this case to the agent"):
        page.keyboard.press("Enter")
    expect_on_me(page, 2)
    case.get_by_role("checkbox", name="Looks right").focus()
    page.keyboard.press("m")
    expect(case).to_have_attribute("data-lf-datum", second)


def test_on_me_materializes_a_frozen_review_at_its_requested_case(browser, serve):
    """A reply's record is reachable before its widget or selected case is drawn."""
    url = serve(VISUAL_REVIEW_GALLERY)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "text": "Review the comparisons in this reply.",
            "markup": '<lf-visual-review id="reply-review" source="gallery-visual-run"></lf-visual-review>',
        },
    )
    page = open_page(browser, url)
    count = page.locator(".lf-fp-on-user")
    expect_on_me(page, 6)
    count.click()
    card = page.locator(
        '.lf-fp-on-item[data-obligation="widget:reply-review:keep-mobile-destinations"]'
    )
    card.get_by_role("button", name="Show", exact=True).click()
    case = page.locator("#reply-review").locator(SELECTED)
    expect(case).to_have_attribute("data-lf-datum", "keep-mobile-destinations")
    expect(case).to_be_focused()
    expect(case.get_by_role("checkbox", name="Looks right")).to_be_visible()


def test_visual_review_empty_navigation_is_unavailable(browser, serve):
    page = open_page(
        browser,
        live_url(
            serve(
                leaf_page(
                    "empty visual review",
                    '<lf-visual-review id="visual-run" source="missing-run"></lf-visual-review>',
                ),
                packages=("visual-review",),
            )
        ),
    )
    widget = page.locator("#visual-run")
    expect(widget.get_by_role("button")).to_have_count(0)
    expect(widget.get_by_text("Waiting for visual evidence.")).to_be_visible()


@pytest.mark.parametrize("width", [390, 702, 1366])
def test_visual_review_keeps_the_dashboard_stable_while_inspecting(
    browser, serve, width
):
    """Cases and the inspection popover never move the approval or evidence rows."""
    page = open_page(browser, serve(VISUAL_REVIEW_GALLERY))
    resized(page, width, 900)
    widget = page.locator("#visual-review-run")
    case = widget.locator(SELECTED)
    reading = """node => {
      const box = selector => node.querySelector(selector).getBoundingClientRect();
      return {decision: box('.lf-vr-decision').y, evidence: box('.lf-vr-evidence').y};
    }"""
    baseline = case.evaluate(reading)
    # The header names size and browser; Capture details holds the rest.
    expect(case.locator(".lf-vr-evidence-note")).to_have_text("390 × 844 · Chromium")
    buttons = widget.locator(".lf-vr-case-button")
    expect(buttons).to_have_count(3)
    for button in buttons.all():
        button.click()
        assert case.evaluate(reading) == baseline
        case.get_by_role("button", name="Capture details").click()
        details = case.locator(".lf-vr-details")
        expect(details).to_be_visible()
        expect(details.get_by_role("checkbox")).to_have_count(0)
        expect(details.locator(".lf-vr-provenance")).to_contain_text("Capture")
        assert case.evaluate(reading) == baseline
        bounds = details.bounding_box()
        assert (
            bounds and 0 <= bounds["x"] and bounds["x"] + bounds["width"] <= width + 1
        )
        page.keyboard.press("Escape")
        expect(details).to_be_hidden()
        assert root_overflow(page) == 0


def test_visual_review_ignores_a_late_load_from_superseded_evidence(browser, serve):
    authored = leaf_page(
        "visual review replacement",
        '<lf-visual-review id="visual-run" source="docs-run"></lf-visual-review>',
    )
    media = {
        "/media/3cf0e3efe80c6b01.png": (
            example_media() / "3cf0e3efe80c6b01.png"
        ).read_bytes(),
        "/media/4f465a0582ab00fe.png": (
            example_media() / "4f465a0582ab00fe.png"
        ).read_bytes(),
    }
    url = live_url(serve(authored, packages=("visual-review",), media=media))
    capture = {
        "observedAt": "2026-09-10T10:30:00-07:00",
        "browser": "Chrome",
        "browserVersion": "140",
        "viewport": {"width": 900, "height": 373},
        "deviceScaleFactor": 2,
        "colorScheme": "light",
        "locale": "en-US",
        "timezone": "America/Los_Angeles",
    }

    def run(before, after, *, viewport_width):
        return {
            "title": "Replacement run",
            "base": {"revision": "base", "url": "https://base.example/"},
            "candidate": {
                "revision": "candidate",
                "url": "https://candidate.example/",
            },
            "cases": [
                {
                    "id": "changed",
                    "title": "Changed surface",
                    "path": "/changed",
                    "action": "Open the surface.",
                    "result": "The evidence remains aligned.",
                    "classification": "changed",
                    "capture": capture
                    | {"viewport": capture["viewport"] | {"width": viewport_width}},
                    "focus": {"x": 20, "y": 80, "width": 300, "height": 150},
                    "before": before,
                    "after": after,
                }
            ],
        }

    data_model.cmd_data_set(
        serve.page_dir,
        "docs-run",
        run(
            "/media/3cf0e3efe80c6b01.png",
            "/media/4f465a0582ab00fe.png",
            viewport_width=900,
        ),
    )
    context = browser.new_context(viewport={"width": 1200, "height": 900})
    held = []
    context.route("**/media/111111111111111*.svg", lambda route: held.append(route))
    # Pending images stay off-document while the current evidence remains readable.
    # Wait for their native load callbacks before asserting a stale load had no effect.
    context.add_init_script("""(() => {
      window.delayedEvidence = [];
      const source = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src');
      Object.defineProperty(HTMLImageElement.prototype, 'src', {
        ...source,
        set(value) {
          if (value.includes('/media/111111111111111')) {
            const evidence = {loaded: false};
            window.delayedEvidence.push(evidence);
            this.addEventListener('load', () => evidence.loaded = true, {once: true});
          }
          source.set.call(this, value);
        },
      });
    })();""")
    page = None
    try:
        page = open_page(browser, url, context=context)
        data_model.cmd_data_set(
            serve.page_dir,
            "docs-run",
            run(
                "/media/1111111111111110.svg",
                "/media/1111111111111111.svg",
                viewport_width=900,
            ),
        )
        told(page)
        # The case's article follows its case by id into the run it now shows.
        case = page.locator('#visual-run [data-lf-datum="changed"]')
        expect(case).to_have_attribute(
            "data-lf-source-revision", source_revision(serve.page_dir, "docs-run")
        )
        expect(case).to_have_attribute("data-lf-identity", "changed")
        assert json.loads(case.get_attribute("data-lf-origin"))["path"] == ["cases", 0]
        shot = page.locator("#visual-run lf-shot")
        expect(shot).to_have_attribute("before", "/media/1111111111111110.svg")
        images = shot.locator("img")
        expect(images).to_have_count(2)
        page.wait_for_function("() => window.delayedEvidence.length >= 2")
        # Replacement evidence stays on screen until both new images have loaded.
        expect(images.first).to_have_attribute("src", "/media/3cf0e3efe80c6b01.png")
        assert len(held) == 2

        data_model.cmd_data_set(
            serve.page_dir,
            "docs-run",
            run(
                "/media/3cf0e3efe80c6b01.png",
                "/media/4f465a0582ab00fe.png",
                viewport_width=900,
            ),
        )
        told(page)
        host = page.locator("#visual-run .lf-vr-capture")
        expect(host.locator("lf-shot img")).to_have_count(2)
        expect(shot).to_have_attribute("before", "/media/3cf0e3efe80c6b01.png")
        expect(host.locator("lf-shot img").first).to_have_js_property(
            "naturalWidth", 780
        )
        rendered(page, facts=("updatesSettled",))
        shown = host.locator("lf-shot").bounding_box()

        stale_svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="746"/>'
        )
        while held:
            held.pop(0).fulfill(content_type="image/svg+xml", body=stale_svg)
        page.wait_for_function(
            "() => window.delayedEvidence.every(evidence => evidence.loaded)"
        )
        rendered(page)
        expect(images.first).to_have_attribute("src", "/media/3cf0e3efe80c6b01.png")
        expect(images.first).to_have_js_property("naturalWidth", 780)
        assert host.locator("lf-shot").bounding_box() == shown
    finally:
        while held:
            held.pop(0).abort()


def test_visual_review_preserves_capture_reading_when_returning_to_a_case(
    browser, serve
):
    """Moving through the queue restores the exact scroll position of tall evidence."""
    page = open_page(browser, serve(VISUAL_REVIEW_GALLERY))
    resized(page, 1366, 700)
    widget = page.locator("#visual-review-run")
    case = widget.locator(SELECTED)
    case.get_by_role("button", name="Pair", exact=True).click()
    case.get_by_role("button", name="Image options").click()
    case.get_by_role("checkbox", name="Full frame").check()
    page.keyboard.press("Escape")
    case.get_by_role("button", name="Image options").click()
    case.get_by_role("button", name="100%", exact=True).click()
    capture = case.locator(".lf-shotviewport").first
    assert capture.evaluate("node => node.scrollHeight > node.clientHeight")
    capture.hover()
    page.mouse.wheel(0, 180)
    page.wait_for_function("node => node.scrollTop > 0", arg=capture.element_handle())
    scroll_settled(page)
    before = capture.evaluate("node => node.scrollTop")
    widget.locator(".lf-vr-case-button").nth(1).click()
    widget.locator(".lf-vr-case-button").first.click()
    rendered(page)
    assert capture.evaluate("node => node.scrollTop") == before
