"""Authenticated website-journey proof for the visual-review package."""

import json
import shutil

import pytest
from leaf import data as data_model
from leaf import event_log as events_model
from leaf import exporting as exporting_model
from leaf import hosting as hosting_model
from leaf import media as media_model
from playwright.sync_api import expect
from render_cases_navigation import source_revision
from render_harness import (
    consume_browser_errors,
    leaf_page,
    open_page,
    resized,
    scroll_settled,
    sending,
    stamp_page,
    told,
    undo,
)

pytestmark = pytest.mark.shifts_unsurveyed

from browser.test_render_visual_review_journey import (
    VISUAL_REVIEW_GALLERY,
    assert_keyboard_focus,
    comment_on_target,
    go_to,
    target_document,
)


def test_an_authenticated_navigation_journey_becomes_credential_free_review_evidence(
    browser, serve, tmp_path
):
    """Capture owns target access; the visual run owns only durable evidence.

    The capture browser follows a rendered link through a protected target, then a
    separate user reviews the stills without inheriting that browser's credential.
    Replacing the source after a correction preserves the decision and the comment's
    original data provenance.
    """
    catalog_base = target_document(
        "Releases",
        """<h1>Recent releases</h1><p class="meta">Three production changes.</p>
<article class="release"><div><h2>Release 17</h2><p>User navigation cleanup.</p>
<a href="/versions/v2.html">Open release 17</a></div></article>""",
    )
    catalog_candidate = target_document(
        "Releases",
        """<h1>Recent releases</h1><p class="meta">Three production changes.</p>
<article class="release"><div><h2>Release 17</h2><p>User navigation cleanup.</p>
<a href="/versions/v2.html">Open release 17</a></div><span class="status">Ready</span></article>""",
    )
    detail_base = target_document(
        "Release 17",
        """<a href="/versions/v1.html">Back to releases</a><h1>Release 17</h1>
<p>User navigation cleanup is ready for review.</p><h2>Audit</h2>
<p class="meta">No open checks.</p>""",
    )
    detail_regression = target_document(
        "Release 17",
        """<h1>Release 17</h1><p>User navigation cleanup is ready for review.</p>
<h2>Audit</h2><p class="meta">Checked by the release owner · No open checks.</p>""",
    )
    detail_corrected = target_document(
        "Release 17",
        """<a href="/versions/v1.html">Back to releases</a><h1>Release 17</h1>
<p>User navigation cleanup is ready for review.</p><h2>Audit</h2>
<p class="meta">Checked by the release owner · No open checks.</p>""",
    )

    def target_history(name, catalog, detail):
        serve(catalog)
        source = serve.page_dir
        stamp_page(source, detail, f"{name} detail")
        target = tmp_path / name
        shutil.copytree(source, target)
        return target

    base_dir = target_history("base-target", catalog_base, detail_base)
    candidate_dir = target_history(
        "candidate-target", catalog_candidate, detail_regression
    )
    corrected_dir = target_history(
        "corrected-target", catalog_candidate, detail_corrected
    )

    review_url = serve(
        leaf_page(
            "authenticated navigation review",
            '<lf-visual-review id="journey" source="journey-run"></lf-visual-review>',
        ),
        packages=("visual-review",),
    )
    review_dir = serve.page_dir

    capture_key = "capture-only-secret"
    capture_files = {}
    targets = [
        hosting_model.TemporaryPageServer(directory, token=capture_key).start()
        for directory in (base_dir, candidate_dir, corrected_dir)
    ]
    serve.servers.extend(targets)
    base_target, candidate_target, corrected_target = targets
    denied = browser.new_page()
    response = denied.goto(f"{base_target.origin}/versions/v1.html")
    assert response and response.status == 401
    # The refusal is the point of this page: the reviewer has no capture credential.
    consume_browser_errors(denied, {"code": "failed-load", "status": 401})
    denied.close()

    context = browser.new_context(
        viewport={"width": 900, "height": 600},
        device_scale_factor=2,
        color_scheme="light",
        locale="en-US",
        timezone_id="America/Los_Angeles",
        reduced_motion="reduce",
    )
    capture = context.new_page()

    def save(name):
        expect(capture.locator("body")).to_have_attribute("data-lf-presented", "1")
        capture.evaluate("window.scrollTo(0, 0)")
        capture.wait_for_function("window.scrollY === 0")
        path = tmp_path / f"{name}.png"
        path.write_bytes(capture.screenshot())
        capture_files[name] = path

    capture.goto(f"{base_target.origin}/versions/v1.html?t={capture_key}")
    expect(capture.get_by_role("heading", name="Recent releases")).to_be_visible()
    save("base-catalog")
    capture.get_by_role("link", name="Open release 17").click()
    expect(capture).to_have_url(f"{base_target.origin}/versions/v2.html")
    expect(capture.get_by_role("link", name="Back to releases")).to_be_visible()
    save("base-detail")

    capture.goto(f"{candidate_target.origin}/versions/v1.html?t={capture_key}")
    expect(capture.get_by_text("Ready", exact=True)).to_be_visible()
    save("candidate-catalog")
    capture.get_by_role("link", name="Open release 17").click()
    expect(capture).to_have_url(f"{candidate_target.origin}/versions/v2.html")
    expect(capture.get_by_text("Checked by the release owner")).to_be_visible()
    expect(capture.get_by_role("link", name="Back to releases")).to_have_count(0)
    save("candidate-detail")

    capture.goto(f"{corrected_target.origin}/versions/v1.html?t={capture_key}")
    capture.get_by_role("link", name="Open release 17").click()
    expect(capture).to_have_url(f"{corrected_target.origin}/versions/v2.html")
    expect(capture.get_by_role("link", name="Back to releases")).to_be_visible()
    save("candidate-detail-corrected")
    context.close()

    target_base = f"{base_target.origin}/versions/"
    target_candidate = f"{candidate_target.origin}/versions/"
    corrected_candidate = f"{corrected_target.origin}/versions/"

    media = {
        name: media_model.cmd_media(review_dir, [path])[0][1]
        for name, path in capture_files.items()
    }
    conditions = {
        "observedAt": "2026-09-11T19:00:00-07:00",
        "browser": "Chromium",
        "browserVersion": browser.version,
        "viewport": {"width": 900, "height": 600},
        "deviceScaleFactor": 2,
        "colorScheme": "light",
        "locale": "en-US",
        "timezone": "America/Los_Angeles",
    }
    record = {
        "title": "Release navigation through a protected preview",
        "base": {"revision": "northstar-16", "url": target_base},
        "candidate": {"revision": "northstar-17", "url": target_candidate},
        "cases": [
            {
                "id": "open-release-list",
                "title": "Release readiness is visible",
                "path": "/v1.html",
                "action": "Open the protected release list.",
                "result": "Release 17 gains a compact Ready status without moving its navigation link.",
                "classification": "changed",
                "capture": conditions,
                "before": media["base-catalog"],
                "after": media["candidate-catalog"],
            },
            {
                "id": "follow-release-link",
                "title": "The detail page keeps its return route",
                "path": "/v2.html",
                "action": "Follow Open release 17 from the protected list.",
                "result": "Seeded regression for review: the candidate detail page loses Back to releases.",
                "classification": "changed",
                "capture": conditions,
                "before": media["base-detail"],
                "after": media["candidate-detail"],
            },
        ],
    }
    # The capture page retains its share link, but the reviewer receives only the
    # recorded stills and metadata, never the capture browser's access link.
    assert capture_key not in json.dumps(record)
    data_model.cmd_data_set(review_dir, "journey-run", record)
    # The draft begun on this value keeps its revision across the replacement below.
    drafted_revision = source_revision(review_dir, "journey-run")

    user = open_page(browser, review_url)
    resized(user, 1366, 768)
    response = user.context.request.get(f"{target_base}v1.html")
    assert response.status == 401
    widget = user.locator("#journey")
    first = widget.locator('[data-lf-datum="open-release-list"]')
    second = widget.locator('[data-lf-datum="follow-release-link"]')
    first_images = first.locator("lf-shot img")
    expect(first_images).to_have_count(2)
    assert first_images.evaluate_all(
        "images => images.every(image => image.complete && image.naturalWidth > 0)"
    )
    details = first.locator(".lf-vr-details")
    details_summary = first.locator(".lf-vr-details-summary")
    go_to(user, details_summary, "Fold")
    assert_keyboard_focus(user, details_summary)
    expect(details).to_have_attribute("open", "")
    user.keyboard.press("Enter")
    expect(details).not_to_have_attribute("open", "")
    widget.get_by_text("Inspect comparison", exact=True).click()
    overlay = widget.get_by_role("radio", name="Overlay")
    go_to(user, overlay)
    assert_keyboard_focus(user, overlay)
    expect(widget).to_have_attribute("data-inspection-mode", "overlay")
    compare = widget.get_by_role("radio", name="Compare")
    go_to(user, compare)
    assert_keyboard_focus(user, compare)
    expect(widget).to_have_attribute("data-inspection-mode", "compare")
    user.keyboard.press("ArrowDown")
    expect(widget).to_have_attribute("data-inspection-mode", "flip")
    expect(widget.locator(".lf-vr-case-select")).to_have_js_property(
        "value", "open-release-list"
    )
    user.keyboard.press("ArrowUp")
    expect(widget).to_have_attribute("data-inspection-mode", "compare")
    assert_keyboard_focus(user, compare)
    first_stage = first.locator(".lf-vr-shot-host")
    assert first_stage.evaluate("node => node.scrollHeight <= node.clientHeight + 1")

    first_looks_right = first.get_by_role("button", name="Looks right")
    with sending(user, "the intended authenticated-navigation change"):
        go_to(user, first_looks_right)
    assert_keyboard_focus(user, first_looks_right)
    user.keyboard.press("ArrowDown")
    expect(widget.locator(".lf-vr-case-select")).to_have_js_property(
        "value", "follow-release-link"
    )
    expect(second).to_have_attribute("aria-label", "Visual review case 2 of 2")
    second_looks_right = second.get_by_role("button", name="Looks right")
    # Case browsing from a verdict reveals its counterpart. Evidence navigation
    # has its own heading destination, covered by the Next unreviewed journey.
    assert_keyboard_focus(user, second_looks_right)
    assert second.locator("lf-shot img").evaluate_all(
        "images => images.every(image => image.complete && image.naturalWidth > 0)"
    )
    second_needs_work = second.get_by_role("button", name="Needs work")
    with sending(user, "the missing return route"):
        go_to(user, second_needs_work)
    assert_keyboard_focus(user, second_needs_work)

    # Case verdicts follow their captures; bring its heading back into view before
    # choosing that case through the visible keyboard target map.
    second.locator(".lf-vr-case-title").scroll_into_view_if_needed()
    scroll_settled(user)
    comment_on_target(user, second)
    field = user.locator(".lf-fab-input")
    expect(field).to_be_focused()
    user.keyboard.type("Restore Back to releases")
    resized(user, 390, 760)
    field.scroll_into_view_if_needed()
    scroll_settled(user)
    expect(field).to_have_js_property("value", "Restore Back to releases")
    assert_keyboard_focus(user, field)
    field.evaluate("node => node.setSelectionRange(8, 12, 'backward')")
    shifted = record | {
        "cases": [
            record["cases"][0],
            record["cases"][1]
            | {
                "result": "The candidate detail page drops Back to releases and leaves the user without a return route after checking the expanded audit context."
            },
        ]
    }
    data_model.cmd_data_set(review_dir, "journey-run", shifted)
    told(user)
    expect(second.locator(".lf-vr-result")).to_contain_text("without a return route")
    expect(field).to_have_js_property("value", "Restore Back to releases")
    assert_keyboard_focus(user, field)
    assert field.evaluate(
        "node => [node.selectionStart, node.selectionEnd, node.selectionDirection]"
    ) == [8, 12, "backward"]
    user.keyboard.press("Escape")
    expect(field).to_be_hidden()
    # The composer returns to the reviewed case; the covered Threads panel uses a
    # native modal envelope, which makes the page inert without an inert attribute.
    expect(second).to_be_focused()
    user.keyboard.press("g")
    user.keyboard.press("Shift+t")
    expect(user.get_by_role("dialog")).to_be_visible()
    expect(user.locator(".lf-threads")).to_be_focused()
    expect(user.locator(".lf-auxiliary-envelope:modal")).to_have_count(1)
    user.keyboard.press("Escape")
    expect(user.get_by_role("dialog")).to_be_hidden()
    assert user.evaluate("() => document.activeElement === document.body")
    user.keyboard.press("g")
    user.keyboard.press("i")
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", "Restore Back to releases")
    scroll_settled(user)
    assert_keyboard_focus(user, field)

    resized(user, 1366, 768)
    # Widening rewraps the review, and continuity brings the editor back on a later frame.
    expect(field).to_be_in_viewport(ratio=1)
    expect(field).to_have_js_property("value", "Restore Back to releases")
    assert_keyboard_focus(user, field)
    user.keyboard.press("Escape")
    expect(field).to_be_hidden()
    expect(second).to_be_focused()
    user.keyboard.press("g")
    user.keyboard.press("Shift+t")
    expect(user.get_by_role("dialog")).to_be_visible()
    expect(user.locator(".lf-threads")).to_be_focused()
    expect(user.locator(".lf-auxiliary-envelope:modal")).to_have_count(0)
    user.keyboard.press("Escape")
    expect(user.get_by_role("dialog")).to_be_hidden()
    assert user.evaluate("() => document.activeElement === document.body"), (
        user.evaluate("() => document.activeElement.outerHTML.slice(0, 300)")
    )
    user.keyboard.press("g")
    user.keyboard.press("i")
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", "Restore Back to releases")
    field.press("End")
    user.keyboard.type(" on the candidate detail page.")
    with sending(user, "the navigation correction comment"):
        user.keyboard.press("ControlOrMeta+Enter")
    comments = [
        event
        for event in events_model.read_events(review_dir)
        if event["kind"] == "comment"
    ]
    assert comments, "the keyboard comment gesture wrote no comment"
    comment = comments[-1]
    assert comment["anchor"] == {
        "section": "journey",
        "datum": "follow-release-link",
        "source": "journey-run",
        "source_revision": drafted_revision,
        "identity": "follow-release-link",
    }
    review_events = [
        event
        for event in events_model.read_events(review_dir)
        if event["kind"] == "action" and event["widget"] == "journey"
    ]
    assert [event["detail"] for event in review_events] == [
        {"case": "open-release-list", "disposition": "looks-right"},
        {"case": "follow-release-link", "disposition": "needs-work"},
    ]

    user.keyboard.press("Escape")
    user.keyboard.press("Escape")
    assert user.evaluate("() => document.activeElement === document.body")
    go_to(user, compare)
    assert_keyboard_focus(user, compare)
    corrected = shifted | {
        "candidate": {"revision": "northstar-18", "url": corrected_candidate},
        "cases": [
            shifted["cases"][0],
            shifted["cases"][1]
            | {
                "result": "The candidate detail page keeps Back to releases beside the expanded audit line.",
                "after": media["candidate-detail-corrected"],
            },
        ],
    }
    data_model.cmd_data_set(review_dir, "journey-run", corrected)
    told(user)
    assert_keyboard_focus(user, compare)
    expect(second).to_have_attribute("data-disposition", "needs-work")
    expect(second.locator(".lf-vr-result")).to_contain_text("keeps Back to releases")
    expect(second.locator("lf-shot")).to_have_attribute(
        "after", media["candidate-detail-corrected"]
    )
    corrected_image = second.locator('.lf-shotframe[data-lf-state="after"] img')
    expect(corrected_image).to_have_js_property("complete", True)
    assert corrected_image.evaluate("image => image.naturalWidth") > 0
    with sending(user, "the corrected navigation disposition"):
        go_to(user, second_looks_right)
    expect(second).to_have_attribute("data-disposition", "looks-right")
    assert_keyboard_focus(user, second_looks_right)
    user.keyboard.press("g")
    user.keyboard.press("Shift+t")
    threads = user.get_by_role("dialog")
    expect(threads).to_contain_text("Restore Back to releases")
    expect(threads.locator(".lf-quote")).to_have_attribute(
        "title", "Jump to this passage"
    )

    review_events = [
        event
        for event in events_model.read_events(review_dir)
        if event["kind"] == "action" and event["widget"] == "journey"
    ]
    assert [event["detail"] for event in review_events] == [
        {"case": "open-release-list", "disposition": "looks-right"},
        {"case": "follow-release-link", "disposition": "needs-work"},
        {"case": "follow-release-link", "disposition": "looks-right"},
    ]

    exported = tmp_path / "review.html"
    exporting_model.cmd_export(review_dir, exported, None)
    data_text = (review_dir / "data.json").read_text() + data_model.source_file(
        review_dir, "journey-run"
    ).read_text()
    assert capture_key not in exported.read_text(encoding="utf-8")
    assert capture_key not in data_text
    assert "?t=" not in data_text


def test_visual_review_leads_with_evidence_and_walks_only_remaining_cases(
    browser, serve
):
    """Reviewing and browsing are distinct: judgments stay put, remaining navigation
    lands on the next evidence, and the picker can revisit completed cases."""
    page = open_page(browser, serve(VISUAL_REVIEW_GALLERY))
    resized(page, 390, 844)
    widget = page.locator("#visual-review-run")
    selected = widget.locator(".lf-vr-case-select")
    first_id = selected.evaluate("node => node.value")
    case = widget.locator(".lf-vr-case:not([hidden])")
    expect(widget.locator(".lf-vr-inspection")).not_to_have_attribute("open", "")
    geometry = case.evaluate("""node => {
      const box = selector => node.querySelector(selector).getBoundingClientRect();
      return {evidence: box('.lf-vr-shot-host'), verdict: box('.lf-vr-review')};
    }""")
    assert geometry["evidence"]["top"] < 450
    assert geometry["verdict"]["top"] >= geometry["evidence"]["bottom"]
    # Moving the shared inspector preserves the focused native disclosure header.
    inspector = widget.get_by_text("Inspect comparison", exact=True)
    inspector.click()
    page.keyboard.press("ArrowDown")
    expect(inspector).to_be_focused()
    expect(selected).not_to_have_js_property("value", first_id)
    page.keyboard.press("ArrowUp")
    expect(inspector).to_be_focused()
    expect(selected).to_have_js_property("value", first_id)
    inspector.click()
    # Browsing from a verdict moves to the matching action in the next case,
    # revealing it even when returning from a short capture to a tall one.
    verdict = case.get_by_role("button", name="Needs work")
    verdict.focus()
    page.keyboard.press("ArrowDown")
    expect(selected).not_to_have_js_property("value", first_id)
    expect(verdict).to_be_focused()
    expect(verdict).to_be_in_viewport(ratio=1)
    page.keyboard.press("ArrowUp")
    expect(selected).to_have_js_property("value", first_id)
    expect(verdict).to_be_focused()
    expect(verdict).to_be_in_viewport(ratio=1)
    with sending(page, "first visual verdict"):
        case.get_by_role("button", name="Looks right").click()
    expect(selected).to_have_js_property("value", first_id)
    expect(case).to_have_attribute("data-disposition", "looks-right")
    # A recorded article shares the disposition value with its verdict control.
    # Navigation lands on the matching native button, not that container.
    page.keyboard.press("ArrowDown")
    expect(selected).not_to_have_js_property("value", first_id)
    expect(case.get_by_role("button", name="Looks right")).to_be_focused()
    expect(case.get_by_role("button", name="Looks right")).to_be_in_viewport(ratio=1)
    page.keyboard.press("ArrowUp")
    expect(selected).to_have_js_property("value", first_id)
    expect(case.get_by_role("button", name="Looks right")).to_be_focused()
    expect(case.get_by_role("button", name="Looks right")).to_be_in_viewport(ratio=1)
    case.get_by_role("button", name="Next unreviewed").click()
    expect(selected).not_to_have_js_property("value", first_id)
    second_id = selected.evaluate("node => node.value")
    expect(case.locator(".lf-vr-case-title")).to_be_focused()
    expect(case.locator(".lf-vr-case-title")).to_be_in_viewport()
    expect(case.locator(".lf-vr-case-position")).to_be_in_viewport()
    with sending(page, "mobile navigation needs correction"):
        case.get_by_role("button", name="Needs work").click()
    # The all-case keyboard route also returns to evidence, including when it
    # starts deep in the previous case's metadata.
    case.get_by_text("Capture details", exact=True).click()
    page.keyboard.press("ArrowDown")
    expect(case.locator(".lf-vr-case-title")).to_be_focused()
    expect(case.locator(".lf-vr-case-title")).to_be_in_viewport()
    expect(case.locator(".lf-vr-case-position")).to_be_in_viewport()
    widget.get_by_role("button", name="Previous", exact=True).click()
    expect(selected).to_have_js_property("value", second_id)
    # All-case browsing can return to the completed first case.
    widget.get_by_role("button", name="Previous", exact=True).click()
    expect(selected).to_have_js_property("value", first_id)
    expect(case).to_have_attribute("data-disposition", "looks-right")
    case.get_by_role("button", name="Next unreviewed").focus()
    page.keyboard.press("Enter")
    expect(selected).not_to_have_js_property("value", first_id)
    expect(selected).not_to_have_js_property("value", second_id)
    with sending(page, "last visual verdict"):
        case.get_by_role("button", name="Looks right").click()
    expect(case.locator(".lf-vr-review-status")).to_have_text(
        "All cases reviewed · revisit any case above"
    )
    expect(case.get_by_role("button", name="Next unreviewed")).to_be_disabled()
    page.reload()
    expect(widget.locator(".lf-vr-progress")).to_have_text("3 of 3 cases reviewed")
    expect(widget.get_by_role("button", name="Next unreviewed")).to_be_disabled()
    undo(page)
    expect(widget.locator(".lf-vr-progress")).to_have_text("2 of 3 cases reviewed")
    expect(widget.get_by_role("button", name="Next unreviewed")).to_be_enabled()
    widget.get_by_role("button", name="Next unreviewed").click()
    expect(selected).not_to_have_js_property("value", first_id)
    expect(selected).not_to_have_js_property("value", second_id)
    expect(case).to_have_attribute("data-disposition", "")
