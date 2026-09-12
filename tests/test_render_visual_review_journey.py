"""Authenticated website-journey proof for the visual-review package."""

import shutil

import pytest
from leaf import data as data_model
from leaf import event_log as events_model
from leaf import exporting as exporting_model
from leaf import hosting as hosting_model
from leaf import media as media_model
from playwright.sync_api import expect
from render_support import leaf_page, open_page, sending, stamp_page, told

pytestmark = pytest.mark.nightly


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


def test_an_authenticated_navigation_journey_becomes_credential_free_review_evidence(
    browser, serve, tmp_path
):
    """Capture owns target access; the visual run owns only durable evidence.

    The capture browser follows a rendered link through a protected target, then a
    separate reader reviews the stills without inheriting that browser's credential.
    Replacing the source after a correction preserves the decision and the comment's
    original data provenance.
    """
    catalog_base = target_document(
        "Releases",
        """<h1>Recent releases</h1><p class="meta">Three production changes.</p>
<article class="release"><div><h2>Release 17</h2><p>Reader navigation cleanup.</p>
<a href="/versions/v2.html">Open release 17</a></div></article>""",
    )
    catalog_candidate = target_document(
        "Releases",
        """<h1>Recent releases</h1><p class="meta">Three production changes.</p>
<article class="release"><div><h2>Release 17</h2><p>Reader navigation cleanup.</p>
<a href="/versions/v2.html">Open release 17</a></div><span class="status">Ready</span></article>""",
    )
    detail_base = target_document(
        "Release 17",
        """<a href="/versions/v1.html">Back to releases</a><h1>Release 17</h1>
<p>Reader navigation cleanup is ready for review.</p><h2>Audit</h2>
<p class="meta">No open checks.</p>""",
    )
    detail_regression = target_document(
        "Release 17",
        """<h1>Release 17</h1><p>Reader navigation cleanup is ready for review.</p>
<h2>Audit</h2><p class="meta">Checked by the release owner · No open checks.</p>""",
    )
    detail_corrected = target_document(
        "Release 17",
        """<a href="/versions/v1.html">Back to releases</a><h1>Release 17</h1>
<p>Reader navigation cleanup is ready for review.</p><h2>Audit</h2>
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
    assert response and response.status == 403
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

    capture.goto(f"{candidate_target.origin}/versions/v1.html")
    expect(capture.get_by_text("Ready", exact=True)).to_be_visible()
    save("candidate-catalog")
    capture.get_by_role("link", name="Open release 17").click()
    expect(capture).to_have_url(f"{candidate_target.origin}/versions/v2.html")
    expect(capture.get_by_text("Checked by the release owner")).to_be_visible()
    expect(capture.get_by_role("link", name="Back to releases")).to_have_count(0)
    save("candidate-detail")

    capture.goto(f"{corrected_target.origin}/versions/v1.html")
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
        "observedAt": "2026-09-11T19:00:00-07:00",
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

    reader, errors = open_page(browser, review_url)
    response = reader.context.request.get(f"{target_base}v1.html")
    assert response.status == 403
    widget = reader.locator("#journey")
    first = widget.locator('[data-lf-datum="open-release-list"]')
    second = widget.locator('[data-lf-datum="follow-release-link"]')
    first_images = first.locator("lf-shot img")
    expect(first_images).to_have_count(2)
    assert first_images.evaluate_all(
        "images => images.every(image => image.complete && image.naturalWidth > 0)"
    )
    with sending(reader, "the intended authenticated-navigation change"):
        first.get_by_role("button", name="Looks right").click()
    reader.keyboard.press("ArrowDown")
    assert second.locator("lf-shot img").evaluate_all(
        "images => images.every(image => image.complete && image.naturalWidth > 0)"
    )
    with sending(reader, "the missing return route"):
        second.get_by_role("button", name="Needs work").click()

    second.click(modifiers=["Alt"])
    field = reader.locator(".lf-fab-input")
    expect(field).to_be_focused()
    field.fill("Restore Back to releases on the candidate detail page.")
    with sending(reader, "the navigation correction comment"):
        reader.keyboard.press("ControlOrMeta+Enter")
    comment = [
        event
        for event in events_model.read_events(review_dir)
        if event["kind"] == "comment" and event.get("anchor", {}).get("datum")
    ][-1]
    assert comment["anchor"] == {
        "section": "journey",
        "datum": "follow-release-link",
        "source": "journey-run",
        "data_revision": 1,
    }

    corrected = record | {
        "candidate": {"revision": "northstar-18", "url": corrected_candidate},
        "cases": [
            record["cases"][0],
            record["cases"][1]
            | {
                "result": "The candidate detail page keeps Back to releases beside the expanded audit line.",
                "after": media["candidate-detail-corrected"],
            },
        ],
    }
    data_model.cmd_data_set(review_dir, "journey-run", corrected)
    told(reader)
    expect(second).to_have_attribute("data-disposition", "needs-work")
    expect(second.locator(".lf-vr-result")).to_contain_text("keeps Back to releases")
    expect(second.locator("lf-shot")).to_have_attribute(
        "after", media["candidate-detail-corrected"]
    )
    corrected_image = second.locator('.lf-shotframe[data-lf-state="after"] img')
    expect(corrected_image).to_have_js_property("complete", True)
    assert corrected_image.evaluate("image => image.naturalWidth") > 0
    with sending(reader, "the corrected navigation disposition"):
        second.get_by_role("button", name="Looks right").click()
    expect(second).to_have_attribute("data-disposition", "looks-right")
    reader.get_by_role("button", name="Threads (1)", exact=True).click()
    threads = reader.get_by_role("dialog")
    expect(threads).to_contain_text("Restore Back to releases")
    expect(threads).to_contain_text("Outdated")

    standalone = exporting_model.export_page(
        browser, review_url, review_dir, "authenticated navigation review"
    )
    data_text = (review_dir / "data.json").read_text()
    assert capture_key not in standalone
    assert capture_key not in data_text
    assert "?t=" not in data_text
    assert errors == []
    reader.close()
