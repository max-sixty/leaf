"""Authenticated website-journey proof for the visual-review package."""

import json
import shutil

import pytest
from playwright.sync_api import expect
from render_cases_navigation import source_revision
from render_harness import (
    consume_browser_errors,
    http_error_console,
    leaf_page,
    open_page,
    panel_settled,
    panel_view,
    reported_browser_errors,
    resized,
    scroll_settled,
    sending,
    stamp_page,
    told,
)

from leaf import data as data_model
from leaf import event_log as events_model
from leaf import exporting as exporting_model
from leaf import hosting as hosting_model
from leaf import media as media_model

pytestmark = pytest.mark.shifts_unsurveyed

from browser.test_render_visual_review_journey import (
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
    consume_browser_errors(denied, http_error_console(401))
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
        name: media_model.cmd_media(review_dir, [path])[0]["path"]
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
    record: dict = {
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
    details_button = first.get_by_role("button", name="Capture details")
    go_to(user, details_button)
    expect(first.locator(".lf-vr-details")).to_be_visible()
    user.keyboard.press("Escape")
    expect(first.locator(".lf-vr-details")).to_be_hidden()
    first_looks_right = first.get_by_role("checkbox", name="Looks right")
    with sending(user, "approve the authenticated-navigation change"):
        go_to(user, first_looks_right)
    assert_keyboard_focus(user, first_looks_right)
    widget.locator(".lf-vr-case-button").nth(1).click()
    expect(second).to_be_visible()
    second_looks_right = second.get_by_role("checkbox", name="Looks right")
    expect(second_looks_right).not_to_be_checked()
    assert second.locator("lf-shot img").evaluate_all(
        "images => images.every(image => image.complete && image.naturalWidth > 0)"
    )

    # Case verdicts follow their captures; bring its heading back into view before
    # choosing that case through the visible keyboard target map.
    second.locator(".lf-vr-title").scroll_into_view_if_needed()
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
    shifted: dict = record | {
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
    # The composer returns to the reviewed case; Threads opens over it in the panel and
    # Escape puts it away, leaving the page to the reader.
    expect(second).to_be_focused()
    threads = user.locator(panel_view("threads"))
    user.keyboard.press("g")
    user.keyboard.press("Shift+t")
    expect(threads).to_be_visible()
    expect(threads).to_be_focused()
    user.keyboard.press("Escape")
    panel_settled(user, open=False)
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
    expect(threads).to_be_visible()
    expect(threads).to_be_focused()
    user.keyboard.press("Escape")
    panel_settled(user, open=False)
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
        {"case": "open-release-list", "approved": True},
    ]

    user.keyboard.press("Escape")
    user.keyboard.press("Escape")
    assert user.evaluate("() => document.activeElement === document.body")
    compare = second.get_by_role("radio", name="Pair", exact=True)
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
    expect(second_looks_right).not_to_be_checked()
    expect(second.locator(".lf-vr-result")).to_contain_text("keeps Back to releases")
    expect(second.locator("lf-shot")).to_have_attribute(
        "after", media["candidate-detail-corrected"]
    )
    corrected_image = second.locator('.lf-shotframe[data-lf-state="after"] img')
    expect(corrected_image).to_have_js_property("complete", True)
    assert corrected_image.evaluate("image => image.naturalWidth") > 0
    with sending(user, "the corrected navigation disposition"):
        go_to(user, second_looks_right)
    expect(second_looks_right).to_be_checked()
    assert_keyboard_focus(user, second_looks_right)
    user.keyboard.press("g")
    user.keyboard.press("Shift+t")
    expect(threads).to_contain_text("Restore Back to releases")

    review_events = [
        event
        for event in events_model.read_events(review_dir)
        if event["kind"] == "action" and event["widget"] == "journey"
    ]
    assert [event["detail"] for event in review_events] == [
        {"case": "open-release-list", "approved": True},
        {"case": "follow-release-link", "approved": True},
    ]

    exported = tmp_path / "review.html"
    exporting_model.cmd_export(review_dir, exported, None)
    data_text = data_model.source_file(review_dir, "journey-run").read_text()
    assert capture_key not in exported.read_text(encoding="utf-8")
    assert capture_key not in data_text
    assert "?t=" not in data_text


import hashlib

import pytest
from browser.test_render_visual_review_journey import VISUAL_REVIEW_GALLERY
from render_cases_layout import (
    solid_png,
)


@pytest.mark.shifts_unsurveyed
@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_visual_review_refresh_retains_inspection_and_hands_focus_off_removed_cases(
    request, serve, engine
):
    """New captures retain inspection; a removed case returns focus to the next case."""
    browser = request.getfixturevalue(engine)
    captures = [
        solid_png(1200, 1000, color) for color in ((220, 230, 240), (240, 230, 220))
    ]
    sources = [
        f"/media/{hashlib.sha256(data).hexdigest()[:16]}.png" for data in captures
    ]
    page = open_page(
        browser,
        serve(VISUAL_REVIEW_GALLERY, media=dict(zip(sources, captures, strict=True))),
    )
    widget = page.locator("#visual-review-run")
    case = widget.locator(".lf-vr-case:not([hidden])")
    shot = case.locator("lf-shot")
    control = case.get_by_role("radio", name="Slider", exact=True)
    control.click()
    case.get_by_role("button", name="Image options").click()
    case.get_by_role("button", name="100%", exact=True).click()
    divider = shot.get_by_role("scrollbar")
    divider.press("Home")
    divider.press("ArrowRight")
    control.focus()
    expect(control).to_be_focused()
    original = shot.element_handle()
    record = json.loads(VISUAL_REVIEW_GALLERY.with_suffix(".data.json").read_text())[
        "gallery-visual-run"
    ]
    changed = record | {
        "cases": [
            record["cases"][0]
            | {
                "before": record["cases"][0]["after"],
                "after": record["cases"][0]["before"],
            },
            *record["cases"][1:],
        ]
    }
    data_model.cmd_data_set(serve.page_dir, "gallery-visual-run", changed)
    told(page)
    expect(control).to_be_focused()
    assert shot.evaluate("(node, original) => node === original", original)
    expect(control).to_have_attribute("aria-checked", "true")
    expect(shot.locator("wa-comparison")).to_have_attribute("position", "1")
    expect(
        case.get_by_role("button", name="100%", exact=True, include_hidden=True)
    ).to_have_attribute("aria-pressed", "true")

    # A refused replacement leaves usable old evidence, and correcting it must
    # publish new dimensions even in Firefox, whose reused-image decode can be stale.
    invalid = changed | {
        "cases": [changed["cases"][0] | {"after": sources[1]}, *changed["cases"][1:]]
    }
    data_model.cmd_data_set(serve.page_dir, "gallery-visual-run", invalid)
    told(page)
    expect(shot.locator(".lf-error")).to_contain_text(
        "a pair has to be shot at one viewport"
    )
    reported_browser_errors(page, "a pair has to be shot at one viewport")
    expect(control).to_be_focused()
    changed = invalid | {
        "cases": [
            invalid["cases"][0]
            | {
                "before": sources[0],
                "capture": invalid["cases"][0]["capture"]
                | {"viewport": {"width": 600, "height": 500}, "deviceScaleFactor": 2},
                "focus": {"x": 300, "y": 200, "width": 200, "height": 200},
            },
            *invalid["cases"][1:],
        ]
    }
    data_model.cmd_data_set(serve.page_dir, "gallery-visual-run", changed)
    told(page)
    expect(shot.locator(".lf-error")).to_have_count(0)
    expect(control).to_be_focused()
    assert shot.locator(".lf-shotframe img").evaluate_all(
        "images => images.map(image => [image.naturalWidth, image.naturalHeight, image.getBoundingClientRect().width])"
    ) == [[1200, 1000, 600], [1200, 1000, 600]]

    # Refreshing captures also replaces the cached pixel mask and its background.
    pixels = case.get_by_role("radio", name="Pixels", exact=True)
    pixels.click()
    page.wait_for_function(
        """() => document.querySelector(
          '.lf-vr-case:not([hidden]) .lf-shotpixels .lf-shot-pixel-mask'
        )?.style.getPropertyValue('--lf-shot-pixels')"""
    )
    painted_pixels = """node => ({
      ground: node.querySelector('.lf-shotpixels img').src,
      mask: node.querySelector('.lf-shotpixels .lf-shot-pixel-mask')
        .style.getPropertyValue('--lf-shot-pixels'),
    })"""
    previous_pixels = shot.evaluate(painted_pixels)
    # Hold the platform's mask encoding at an actual asynchronous boundary.
    # Refresh must keep the whole old difference until the new mask is ready.
    page.evaluate(
        """() => {
          const encode = OffscreenCanvas.prototype.convertToBlob;
          window.heldShotMasks = [];
          OffscreenCanvas.prototype.convertToBlob = async function(...args) {
            const blob = await encode.apply(this, args);
            await new Promise(resolve => window.heldShotMasks.push(resolve));
            return blob;
          };
          window.releaseShotMasks = () => {
            OffscreenCanvas.prototype.convertToBlob = encode;
            for (const release of window.heldShotMasks) release();
          };
        }"""
    )
    identical = changed | {
        "cases": [
            changed["cases"][0] | {"after": changed["cases"][0]["before"]},
            *changed["cases"][1:],
        ]
    }
    data_model.cmd_data_set(serve.page_dir, "gallery-visual-run", identical)
    told(page)
    page.wait_for_function("window.heldShotMasks.length === 1")
    assert shot.evaluate(painted_pixels) == previous_pixels
    # Metadata arriving after image validation owns a new request; it cannot
    # smuggle an invalid crop into the already-preparing pair.
    invalid_focus = identical | {
        "cases": [
            identical["cases"][0]
            | {"focus": {"x": 900, "y": 200, "width": 200, "height": 200}},
            *identical["cases"][1:],
        ]
    }
    data_model.cmd_data_set(serve.page_dir, "gallery-visual-run", invalid_focus)
    told(page)
    expect(shot.locator(".lf-error")).to_contain_text(
        "falls outside its captured images"
    )
    reported_browser_errors(page, "falls outside its captured images")
    assert shot.evaluate(painted_pixels) == previous_pixels
    page.evaluate("window.releaseShotMasks()")
    # Correcting metadata alone must recover without changing either image URL.
    data_model.cmd_data_set(serve.page_dir, "gallery-visual-run", identical)
    told(page)
    expect(shot.locator(".lf-error")).to_have_count(0)
    expect(pixels).to_be_focused()
    expect(pixels).to_have_attribute("aria-checked", "true")
    expect(shot.locator(".lf-shotstage")).to_have_attribute(
        "aria-description", "identical"
    )
    corrected_pixels = shot.evaluate(painted_pixels)
    assert corrected_pixels["mask"]
    assert corrected_pixels["mask"] != previous_pixels["mask"]
    assert shot.locator(".lf-shotpixels img").evaluate(
        "node => node.src"
    ) == shot.locator('.lf-shotframe[data-lf-state="after"] img').evaluate(
        "node => node.src"
    )
    data_model.cmd_data_set(
        serve.page_dir, "gallery-visual-run", record | {"cases": record["cases"][1:]}
    )
    told(page)
    expect(case.locator(".lf-vr-title")).to_be_focused()
    expect(case.locator(".lf-vr-title")).to_have_text(record["cases"][1]["title"])
    expect(case.locator(".lf-vr-title")).to_be_in_viewport()
