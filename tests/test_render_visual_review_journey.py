"""Authenticated website-journey proof for the visual-review package."""

import hashlib
import json
import re
import shutil

import pytest
from leaf import data as data_model
from leaf import event_log as events_model
from leaf import exporting as exporting_model
from leaf import hosting as hosting_model
from leaf import media as media_model
from playwright.sync_api import expect
from render_cases_layout import (
    ring_faults,
    standing_ring,
)
from render_harness import (
    CORPUS_SOURCES,
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

pytestmark = pytest.mark.nightly

VISUAL_REVIEW_GALLERY = next(
    path for path in CORPUS_SOURCES if path.stem == "visual-review-gallery"
)


def test_a_visual_review_in_flow_takes_its_evidence_height(browser, serve):
    """In a document the review's evidence is as tall as its captures in every view,
    so the page scrolls through it rather than a smaller pane inside it."""
    url = serve(VISUAL_REVIEW_GALLERY)
    stamp_page(
        serve.page_dir,
        leaf_page(
            "visual inspection in flow",
            """<h1>Review the package change</h1>
<p style="min-height: 28rem">The review follows this context.</p>
<section><lf-visual-review id="visual-review-run" source="gallery-visual-run"></lf-visual-review></section>
<p style="min-height: 40rem">The decision record continues after the evidence.</p>""",
        ),
        "put visual inspection in document flow",
    )
    url = url.rsplit("/versions/", 1)[0] + "/?" + url.partition("?")[2]
    page = open_page(browser, url)
    resized(page, 1000, 700)
    widget = page.locator("#visual-review-run")
    expect(widget.get_by_role("button", name="Expand inspection")).to_have_count(0)
    widget.scroll_into_view_if_needed()
    host = widget.locator(".lf-vr-case:not([hidden]) .lf-vr-shot-host")
    whole = """node => {
      const shot = node.querySelector('lf-shot').getBoundingClientRect();
      const stage = node.getBoundingClientRect();
      return node.scrollHeight <= node.clientHeight + 1
        && shot.bottom <= stage.bottom + 1;
    }"""
    widget.get_by_text("Inspect comparison", exact=True).click()
    widget.get_by_role("radio", name="Full frame").click()
    for scale in ("Fit", "100%"):
        widget.get_by_role("radio", name=scale).click()
        for mode in ("Compare", "Flip", "Overlay"):
            widget.get_by_role("radio", name=mode).click()
            page.wait_for_function(whole, arg=host.element_handle())
    point = host.evaluate(
        "node => { const r = node.getBoundingClientRect();"
        " return {x: r.left + r.width / 2, y: r.top + r.height / 2}; }"
    )
    page.mouse.move(point["x"], point["y"])
    document_start = page.evaluate("document.scrollingElement.scrollTop")
    page.mouse.wheel(0, 320)
    page.wait_for_function(f"document.scrollingElement.scrollTop > {document_start}")
    assert host.evaluate("node => node.scrollTop") == 0
    # The reading keys page the same scroller from a press on the captures.
    page.evaluate("scrollTo({top: 0, behavior: 'instant'})")
    scroll_settled(page)
    host.click()
    page.keyboard.press("d")
    page.wait_for_function("document.scrollingElement.scrollTop > 0")


def go_to(page, target, kind="Control"):
    """Type the opaque hint painted beside one rendered destination."""
    # Hints label what the window shows, so the reader scrolls the page to it first.
    target.scroll_into_view_if_needed()
    scroll_settled(page)
    page.keyboard.press("g")
    hints = page.locator(".lf-go-to-hint[data-lf-hint-code]")
    expect(hints.first).to_be_visible()
    code = target.evaluate(
        """(target, kind) => {
          const at = target.getBoundingClientRect();
          const chips = [...document.querySelectorAll(
            '.lf-go-to-hint[data-lf-hint-code]')]
            .filter(chip => chip.dataset.lfGoToKind === kind);
          return chips.map(chip => {
            const box = chip.getBoundingClientRect();
            return {code: chip.dataset.lfHintCode,
              distance: Math.hypot(box.left - at.left, box.top - at.top)};
          }).sort((a, b) => a.distance - b.distance)[0]?.code ?? null;
        }""",
        kind,
    )
    assert code, f"the rendered {kind.lower()} had no Go-to hint"
    page.keyboard.type(code)


def comment_on_target(page, target):
    """Choose one rendered datum through Leaf's keyboard target map."""
    page.keyboard.press("s")
    hints = page.locator(".lf-target-picker-hint[data-lf-hint-code]")
    expect(hints.first).to_be_visible()
    code = target.evaluate(
        """target => {
          const at = target.getBoundingClientRect();
          const chips = [...document.querySelectorAll(
            '.lf-target-picker-hint[data-lf-hint-code]')];
          return chips.map(chip => {
            const box = chip.getBoundingClientRect();
            return {code: chip.dataset.lfHintCode,
              distance: Math.hypot(box.left - at.left, box.top - at.top)};
          }).sort((a, b) => a.distance - b.distance)[0]?.code ?? null;
        }"""
    )
    assert code, "the rendered datum had no target-picker hint"
    page.keyboard.type(code)


def assert_keyboard_focus(page, control):
    """The focused destination declares a visible treatment and is not covered.

    A text field always shows its focus, as a textarea does. Chrome never gives a host
    that delegates focus `:focus-visible`, so the field's treatment keys on `:focus`,
    and that is the state asked of it here."""
    expect(control).to_be_focused()
    focus = control.evaluate(
        """node => {
          const box = node.getBoundingClientRect();
          const hit = document.elementFromPoint(
            box.left + box.width / 2, box.top + box.height / 2);
          const shown = node.localName === 'leaf-text' ? ':focus' : ':focus-visible';
          return {
            focusVisible: node.matches(shown),
            unobscured: Boolean(hit && (hit === node || node.contains(hit))),
            inViewport: box.top >= 0 && box.left >= 0
              && box.bottom <= innerHeight && box.right <= innerWidth,
          };
        }"""
    )
    assert focus == {
        "focusVisible": True,
        "unobscured": True,
        "inViewport": True,
    }, f"the keyboard destination has no visible, reachable focus treatment: {focus}"
    ring = standing_ring(page)
    assert ring, "the focused destination paints no keyboard ring"
    assert not (faults := ring_faults([ring], "the focused destination")), "\n".join(
        faults
    )


def target_document(title, body):
    """One small release site whose links and pixels are the capture subject."""
    style = """<style>
    * { box-sizing: border-box; }
    body { margin: 0; color: #25231f; background: #f7f5ef;
      font: 16px/1.45 system-ui, sans-serif; }
    main { width: min(760px, calc(100% - 48px)); margin: 48px auto; }
    header { display: flex; align-items: baseline; justify-content: space-between;
      border-bottom: 1px solid #cfc9bd; margin-bottom: 28px; }
    h1 { font: 700 34px/1.05 Georgia, serif; }
    a { color: #174f82; }
    .release { display: grid; grid-template-columns: 1fr auto; gap: 12px;
      padding: 18px; margin: 12px 0; background: white;
      border: 1px solid #d7d1c7; border-radius: 8px; }
    .status { align-self: start; padding: 3px 8px; color: #245734;
      background: #e0efe3; border-radius: 999px; font-size: 13px; font-weight: 700; }
    .meta { color: #68635a; }
  </style>"""
    return leaf_page(
        title,
        f"<header><strong>Northstar releases</strong><span>Acme team</span></header>{body}",
        head=style,
    )


def test_visual_review_keeps_its_inline_comment_editor_in_view_after_phone_resize(
    browser, serve
):
    """A focused comment editor remains reachable when its visual-review seat narrows."""
    page = open_page(browser, serve(VISUAL_REVIEW_GALLERY))
    resized(page, 1366, 768)
    widget = page.locator("#visual-review-run")
    widget.get_by_role("button", name="Next", exact=True).click()
    expect(widget.locator(".lf-vr-case-select")).to_have_js_property(
        "value", "keep-mobile-destinations"
    )
    datum = widget.locator('[data-lf-datum="keep-mobile-destinations"]')
    comment_on_target(page, datum)
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    page.keyboard.type("Keep the destinations together")
    assert_keyboard_focus(page, field)

    # Resizing alone must keep the focused editor in view. The reader has not scrolled.
    resized(page, 390, 760)
    expect(field).to_have_js_property("value", "Keep the destinations together")
    assert_keyboard_focus(page, field)


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
            layout="wide",
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
    consume_browser_errors(denied, "401")
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
        assert capture_key not in capture.content()
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
    data_model.cmd_data_set(review_dir, "journey-run", record)
    # The draft begun on this value keeps its revision across the replacement below.
    drafted_revision = hashlib.sha256(
        data_model.source_file(review_dir, "journey-run").read_bytes()
    ).hexdigest()[:16]

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
    expect(second.locator(".lf-vr-case-title")).to_be_focused()
    expect(second.locator(".lf-vr-case-title")).to_be_in_viewport()
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


def test_a_visual_review_states_where_its_pair_differs_in_every_view(browser, serve):
    """lf-shot's rail is hidden outside Flip, and the default focus crop hides the
    outlines, since it shows one part of the frame. A focus authored on an area that
    did not change would then show nothing, so the case's position line states the
    reading, with the strong changes the focus leaves out, and the full frame outlines
    every region."""
    page = open_page(browser, serve(VISUAL_REVIEW_GALLERY))
    widget = page.locator("#visual-review-run")
    case = widget.locator(".lf-vr-case:not([hidden])")
    marks = case.locator(".lf-shotframe").first.locator(".lf-shotdiff > span")
    expect(widget).to_have_attribute("data-inspection-scope", "focus")
    # Computed analysis belongs in the disclosed capture facts; it cannot grow
    # the heading after presentation and move the evidence the reader is viewing.
    case.get_by_text("Capture details", exact=True).click()
    expect(case.locator(".lf-vr-analysis")).to_have_text(
        re.compile(
            r"Case 1 of 3 · Changed · [1-9]\d* changed areas "
            r"\([1-9]\d* outside the focus\)"
        )
    )
    expect(marks.first).to_be_hidden()

    widget.get_by_text("Inspect comparison", exact=True).click()
    widget.get_by_role("radio", name="Full frame").click()
    expect(widget).to_have_attribute("data-inspection-scope", "full")
    expect(case.locator(".lf-vr-shot-host")).to_have_attribute(
        "data-focus-active", "false"
    )
    expect(marks.first).to_be_visible()
    # Below the compare view's frame label, where the image starts.
    image_top, first_mark_top = case.locator(".lf-shotframe").first.evaluate(
        """frame => [frame.querySelector('img').getBoundingClientRect().top,
                    frame.querySelector('.lf-shotdiff').getBoundingClientRect().top]"""
    )
    assert first_mark_top == pytest.approx(image_top, abs=1)


# The frame a box draws, beside the theme tokens it might draw from, resolved where it
# stands so a dark scheme or a page's own token reads the same way.
FRAME = """box => {
  const s = getComputedStyle(box);
  const token = (name) => {
    const probe = document.createElement('span');
    probe.style.color = `var(${name})`;
    box.append(probe);
    const color = getComputedStyle(probe).color;
    probe.remove();
    return color;
  };
  const r = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--r'));
  return {border: s.borderTopColor, width: s.borderTopWidth,
    radius: parseFloat(s.borderTopLeftRadius), gap: s.rowGap, r,
    rule: token('--rule'), border2: token('--border-2')};
}"""


def test_a_visual_review_keeps_its_own_frame_where_a_pane_grid_meets_at_hairlines(
    browser, serve
):
    """A workspace draws a page's grid of panes as one frame, the panes meeting at a
    1px ring. A visual review that is the workspace's body composes its own regions,
    and its evidence is a pane it generates standing directly in it, so the grid rules
    took it for a page's grid: the review wore the grid's rule-coloured border, `--r`
    corners and 1px row gap, and the evidence the ring, in place of the review's
    `--border-2` frame at 1.25×`--r` with an evidence pane drawing only its inner rule.
    The page's own grid of panes is the control that keeps the hairline grid."""
    url = serve(VISUAL_REVIEW_GALLERY)
    stamp_page(
        serve.page_dir,
        leaf_page(
            "visual review as a workspace body",
            '<lf-visual-review id="visual-review-run" source="gallery-visual-run">'
            "</lf-visual-review>",
            layout="workspace",
        ),
        "make the review a workspace's body",
    )
    url = url.rsplit("/versions/", 1)[0] + "/?" + url.partition("?")[2]
    page = open_page(browser, url)
    resized(page, 1280, 800)
    review = page.locator("main.layout-workspace > lf-visual-review")
    evidence = review.locator(":scope > .lf-vr-evidence-region")
    expect(evidence).to_have_attribute("data-lf-reading-role", "pane")
    frame = review.evaluate(FRAME)
    assert frame["border"] == frame["border2"] != frame["rule"], frame
    assert frame["radius"] == pytest.approx(1.25 * frame["r"]), frame
    assert frame["gap"] == "normal", frame
    expect(evidence).to_have_css("box-shadow", "none")
    page.close()

    grid = leaf_page(
        "pane grid",
        """
  <header><h1>Alerts</h1></header>
  <div id="regions">
    <lf-pane id="queue" label="Queue"><div><p>Three alerts wait.</p></div></lf-pane>
    <lf-pane id="detail" label="Detail"><div><p>Disk pressure on db-2.</p></div></lf-pane>
  </div>
""",
        head="<style>#regions { display: grid; grid-template-columns: 1fr 2fr; }</style>",
        layout="workspace",
    )
    page = open_page(browser, serve(grid, packages=()))
    resized(page, 1280, 800)
    frame = page.locator("#regions").evaluate(FRAME)
    assert frame["border"] == frame["rule"] and frame["width"] == "1px", frame
    assert frame["radius"] == pytest.approx(frame["r"]) and frame["gap"] == "1px", frame
    for pane in ("#queue", "#detail"):
        ring = page.locator(pane).evaluate("node => getComputedStyle(node).boxShadow")
        assert ring == f"{frame['rule']} 0px 0px 0px 1px", (pane, ring)


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
    with sending(page, "first visual verdict"):
        case.get_by_role("button", name="Looks right").click()
    expect(selected).to_have_js_property("value", first_id)
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


def test_visual_review_refresh_hands_focus_across_replaced_evidence(browser, serve):
    """The data owner takes its focus hold before replacing comparisons or cases."""
    page = open_page(browser, serve(VISUAL_REVIEW_GALLERY))
    widget = page.locator("#visual-review-run")
    case = widget.locator(".lf-vr-case:not([hidden])")
    widget.get_by_text("Inspect comparison", exact=True).click()
    widget.get_by_role("radio", name="Flip", exact=True).click()
    case.locator(".lf-shotcap").first.focus()
    expect(case.locator(".lf-shotcap").first).to_be_focused()
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
    expect(case.locator(".lf-vr-case-title")).to_be_focused()
    expect(case.locator(".lf-vr-case-title")).to_be_in_viewport()
    case.locator(".lf-shotcap").first.focus()
    expect(case.locator(".lf-shotcap").first).to_be_focused()
    data_model.cmd_data_set(
        serve.page_dir, "gallery-visual-run", record | {"cases": record["cases"][1:]}
    )
    told(page)
    expect(case.locator(".lf-vr-case-title")).to_be_focused()
    expect(case.locator(".lf-vr-case-title")).to_have_text(record["cases"][1]["title"])
    expect(case.locator(".lf-vr-case-title")).to_be_in_viewport()


def test_visual_review_refresh_keeps_the_focused_verdict_in_place(browser, serve):
    """A source revision reflows reading content without moving the aimed action."""
    page = open_page(browser, serve(VISUAL_REVIEW_GALLERY))
    resized(page, 390, 844)
    widget = page.locator("#visual-review-run")
    case = widget.locator(".lf-vr-case:not([hidden])")
    verdict = case.get_by_role("button", name="Looks right")
    verdict.scroll_into_view_if_needed()
    verdict.focus()
    scroll_settled(page)
    before = verdict.bounding_box()
    record = json.loads(VISUAL_REVIEW_GALLERY.with_suffix(".data.json").read_text())[
        "gallery-visual-run"
    ]
    result = (
        "Updated observation with enough reading text to occupy several lines. " * 8
    )
    changed = record | {
        "cases": [record["cases"][0] | {"result": result}, *record["cases"][1:]]
    }
    data_model.cmd_data_set(serve.page_dir, "gallery-visual-run", changed)
    told(page)
    expect(case.locator(".lf-vr-result")).to_contain_text(result.strip())
    expect(verdict).to_be_focused()
    after = verdict.bounding_box()
    assert abs(after["y"] - before["y"]) <= 1, (before, after)
    assert abs(after["x"] - before["x"]) <= 1, (before, after)


def test_visual_review_text_refresh_retains_comparison_choice_and_focus(browser, serve):
    """An accessible description change does not replace the aligned image pair."""
    page = open_page(browser, serve(VISUAL_REVIEW_GALLERY))
    widget = page.locator("#visual-review-run")
    case = widget.locator(".lf-vr-case:not([hidden])")
    widget.get_by_text("Inspect comparison", exact=True).click()
    widget.get_by_role("radio", name="Flip", exact=True).click()
    caption = case.locator('.lf-shotcap[data-lf-state="before"]')
    caption.click()
    expect(caption).to_have_attribute("aria-pressed", "true")
    caption.focus()
    old_caption = caption.element_handle()
    before = caption.bounding_box()
    record = json.loads(VISUAL_REVIEW_GALLERY.with_suffix(".data.json").read_text())[
        "gallery-visual-run"
    ]
    result = "The accessible description changes without replacing captured evidence."
    changed = record | {
        "cases": [record["cases"][0] | {"result": result}, *record["cases"][1:]]
    }
    data_model.cmd_data_set(serve.page_dir, "gallery-visual-run", changed)
    told(page)
    expect(caption).to_be_focused()
    assert caption.evaluate("(node, old) => node === old", old_caption)
    expect(caption).to_have_attribute("aria-pressed", "true")
    expect(caption).to_have_attribute(
        "aria-label", f"before — {record['cases'][0]['title']}. {result}"
    )
    expect(case.locator("lf-shot img").first).to_have_attribute(
        "alt", f"before: {record['cases'][0]['title']}. {result}"
    )
    expect(case.locator(".lf-shotflip")).to_have_attribute(
        "aria-label",
        f"Compare before and after — {record['cases'][0]['title']}. {result}",
    )
    after = caption.bounding_box()
    assert abs(after["y"] - before["y"]) <= 1, (before, after)


def test_visual_review_selected_caption_owns_its_activation_keys(browser, serve):
    """A selectable caption keeps Space as activation after reaching its endpoint."""
    page = open_page(browser, serve(VISUAL_REVIEW_GALLERY))
    widget = page.locator("#visual-review-run")
    case = widget.locator(".lf-vr-case:not([hidden])")
    widget.get_by_text("Inspect comparison", exact=True).click()
    widget.get_by_role("radio", name="Flip", exact=True).click()
    for state in ("before", "after"):
        caption = case.locator(f'.lf-shotcap[data-lf-state="{state}"]')
        caption.click()
        caption.focus()
        expect(caption).to_have_attribute("aria-pressed", "true")
        scroll_settled(page)
        before = page.evaluate("scrollY")
        for key in ("Space", "Space", "Enter"):
            page.keyboard.press(key)
            scroll_settled(page)
            expect(caption).to_be_focused()
            expect(caption).to_have_attribute("aria-pressed", "true")
            assert abs(page.evaluate("scrollY") - before) <= 1
