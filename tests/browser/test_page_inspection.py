"""A reader can inspect and copy a page without changing the page being inspected."""

import json
from socket import gethostname

from model_folds import leaf_page
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    consume_browser_errors,
    holding,
    http_error_console,
    open_page,
    panel_control,
    stamp_page,
    wait_for_revision,
)


def test_page_diagnostics_reads_and_copies_the_opening_view(browser, serve):
    source = leaf_page(
        "Inspection",
        '<h1 id="heading">Inspect this page</h1>'
        '<details id="evidence"><summary>Evidence</summary><p>Kept closed</p></details>'
        '<p id="last">The page stays in place.</p>',
        head="<style>#last { color: var(--muted); }</style>",
    )
    page = open_page(browser, serve(source, packages=()))
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    requests = []
    page.on("request", lambda request: requests.append(request.url))
    before = page.locator("main").evaluate(
        "el => ({html:el.innerHTML,top:el.getBoundingClientRect().top,scroll:scrollY})"
    )
    assert (
        page.evaluate(
            "performance.getEntriesByType('resource').filter(entry => entry.name.includes('api/inspect')).length"
        )
        == 0
    )
    panel_control(page, "inspection").click()
    dialog = page.get_by_role("dialog", name="About this page", exact=True)
    expect(dialog).to_be_visible()
    expect(dialog).to_contain_text("Source captured for r1")
    expect(page.locator("#evidence")).not_to_have_attribute("open", "")
    expect(
        dialog.get_by_role("button", name="Close about this page", exact=True)
    ).to_be_focused()
    assert len([url for url in requests if "api/inspect" in url]) == 1

    dialog.get_by_role("button", name="Copy diagnostics", exact=True).click()
    page.wait_for_function(
        "navigator.clipboard.readText().then(text => text.startsWith('{'))"
    )
    expect(dialog.get_by_text("Diagnostics copied", exact=True)).to_be_visible()
    report = json.loads(page.evaluate("navigator.clipboard.readText()"))
    assert report["basis"]["revision"] == 1
    assert report["css"]["page"]["declarations"] == 1
    assert report["current_view"]["revision"] == 1
    assert report["current_view"]["observed_at"]
    identity = report["current_view"]["identity"]
    assert identity["delivery"]["runtime"]
    assert identity["layer"]["fingerprint"]
    assert "t=" not in identity["url"]
    assert identity["browser"]["user_agent"] == page.evaluate("navigator.userAgent")
    assert report["current_view"]["checks"]["identity"] == identity
    assert report["current_view"]["checks"] is not None, report["current_view"].get(
        "unavailable"
    )
    assert (
        report["current_view"]["checks"]["reading"]["checks"]["horizontal_overflow_px"]
        == 0
    )
    assert not report["source_pending"]

    page.keyboard.press("Escape")
    expect(dialog).not_to_be_visible()
    expect(page.locator(".lf-fp-leaf")).to_be_focused()
    assert (
        page.locator("main").evaluate(
            "el => ({html:el.innerHTML,top:el.getBoundingClientRect().top,scroll:scrollY})"
        )
        == before
    )
    panel_control(page, "inspection").click()
    expect(dialog).to_contain_text("Source captured for r1")
    expect(dialog.get_by_text("Diagnostics copied", exact=True)).not_to_be_visible()
    page.keyboard.press("Escape")


def test_page_diagnostics_retry_keeps_a_way_out_while_pending(browser, serve):
    page = open_page(
        browser, serve(leaf_page("Inspection", "<h1>Inspect</h1>"), packages=())
    )
    held = []

    def inspect(route):
        held.append(route)
        if len(held) == 1:
            route.fulfill(
                status=503,
                content_type="application/json",
                body='{"error":"Inspection paused"}',
            )

    page.route("**/api/inspect?*", inspect)
    panel_control(page, "inspection").click()
    dialog = page.get_by_role("dialog", name="About this page", exact=True)
    expect(dialog).to_contain_text("Inspection paused")
    consume_browser_errors(page, http_error_console(503))
    dialog.get_by_role("button", name="Retry source inspection").click()
    holding(page, held, 2, "the inspection retry")
    expect(
        dialog.get_by_role("button", name="Close about this page", exact=True)
    ).to_be_focused()
    expect(dialog).to_contain_text("Reading source…")
    page.keyboard.press("Escape")
    expect(dialog).not_to_be_visible()
    expect(page.locator(".lf-fp-leaf")).to_be_focused()
    held[-1].abort("aborted")


def test_diagnostics_arrival_reveals_captured_location_and_rejects_replacement(
    browser, serve
):
    """Opening is passive; explicit arrival reaches the same captured box through a disclosure."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Location",
                '<h1>Locations</h1><details id="fold" open><summary>Evidence</summary>'
                '<div id="arrangement" style="display:grid;grid-template-columns:1fr 1fr">'
                "<p>First</p><p>Second</p></div></details>",
            ),
            packages=(),
        ),
    )
    panel_control(page, "inspection").click()
    dialog = page.get_by_role("dialog", name="About this page", exact=True)
    show = (
        dialog.get_by_role("listitem")
        .filter(has_text="<div id=arrangement>:")
        .get_by_role("button", name="Show on page", exact=True)
    )
    expect(show).to_have_count(1)
    # Disclosure state is browser-owned and may change independently of a revision.
    page.locator("#fold").evaluate("el => el.open = false")
    show.focus()
    page.keyboard.press("Enter")
    expect(dialog).not_to_be_visible()
    expect(page.locator("#fold")).to_have_attribute("open", "")
    expect(page.locator("#arrangement")).to_be_focused()

    panel_control(page, "inspection").click()
    expect(show).to_have_count(1)
    page.locator("#arrangement").evaluate(
        "el => { const next = el.cloneNode(true); next.firstElementChild.textContent = 'Replacement'; el.replaceWith(next); }"
    )
    show.click()
    expect(dialog).to_be_visible()
    expect(dialog).to_contain_text("This location changed")
    page.keyboard.press("Escape")


def test_diagnostics_arrival_inside_sample_stays_in_child_document(browser, serve):
    """A child report reaches its own observation, even when its parent has the same id."""
    source = leaf_page(
        "Nested location",
        '<h1 id="arrangement">Parent</h1>'
        '<lf-sample id="practice" label="Nested page"><template id="practice-source" data-sample>'
        '<h1>Child</h1><div id="arrangement" style="display:grid;grid-template-columns:1fr 1fr">'
        "<p>First</p><p>Second</p></div></template></lf-sample>",
    )
    page = open_page(browser, serve(source))
    sample = page.locator("#practice")
    sample.evaluate("async el => await el.ready")
    child = sample.locator("iframe").element_handle().content_frame()
    before = page.evaluate("scrollY")
    panel_control(child, "inspection").click()
    dialog = child.get_by_role("dialog", name="About this page", exact=True)
    dialog.get_by_role("listitem").filter(has_text="<div id=arrangement>:").get_by_role(
        "button", name="Show on page", exact=True
    ).click()
    expect(dialog).not_to_be_visible()
    expect(child.locator("#arrangement")).to_be_focused()
    assert page.evaluate("scrollY") == before


def test_diagnostics_does_not_navigate_a_new_revision(browser, serve):
    source = leaf_page(
        "Revision",
        "<h1>Before</h1>"
        '<div id="arrangement" style="display:grid;grid-template-columns:1fr 1fr">'
        "<p>First</p><p>Second</p></div>",
    )
    page = open_page(browser, live_url(serve(source, packages=())))
    panel_control(page, "inspection").click()
    dialog = page.get_by_role("dialog", name="About this page", exact=True)
    show = (
        dialog.get_by_role("listitem")
        .filter(has_text="<div id=arrangement>:")
        .get_by_role("button", name="Show on page", exact=True)
    )
    expect(show).to_have_count(1)
    stamp_page(serve.page_dir, source.replace("Before", "After"), "Revised heading")
    wait_for_revision(page, 2)
    show.click()
    expect(dialog).to_be_visible()
    expect(dialog).to_contain_text("This location changed")
    page.keyboard.press("Escape")


def test_sample_diagnostics_copy_failure_keeps_a_visible_manual_copy_route(
    browser, serve
):
    source = leaf_page(
        "Copy host",
        "<h1>Parent</h1>"
        '<lf-sample id="practice" label="Nested page"><template id="practice-source" data-sample>'
        "<h1>Child</h1><p>Clipboard access is restricted here.</p></template></lf-sample>",
    )
    page = open_page(browser, serve(source))
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    sample = page.locator("#practice")
    sample.evaluate("async el => await el.ready")
    child = sample.locator("iframe").element_handle().content_frame()
    panel_control(child, "inspection").click()
    dialog = child.get_by_role("dialog", name="About this page", exact=True)
    expect(dialog).to_contain_text("Source captured for r1")
    dialog.get_by_role("button", name="Copy diagnostics", exact=True).click()
    failure = dialog.get_by_text(
        "Diagnostics not copied. Select the report text to copy it manually.",
        exact=True,
    )
    expect(failure).to_be_visible()
    consume_browser_errors(
        page, "Permissions policy violation: The Clipboard API has been blocked"
    )
    manual = dialog.get_by_role("button", name="Select report text", exact=True)
    manual.focus()
    page.keyboard.press("Enter")
    text = dialog.get_by_label("Structured diagnostics", exact=True)
    expect(text).to_be_focused()
    assert (
        json.loads(child.evaluate("getSelection().toString()"))["basis"]["revision"]
        == 1
    )
    assert (
        child.evaluate("document.featurePolicy.allowsFeature('clipboard-write')")
        is False
    )
    page.keyboard.press("Escape")
    expect(dialog).not_to_be_visible()


def test_about_combines_page_identity_and_diagnostics_with_copyable_text(
    browser, serve
):
    page = open_page(
        browser, serve(leaf_page("About", "<h1>Page details</h1>"), packages=())
    )
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    panel_control(page, "inspection").click()
    dialog = page.get_by_role("dialog", name="About this page", exact=True)
    expect(dialog).to_be_visible()
    expect(dialog).to_contain_text("Source captured for r1")
    version = dialog.get_by_label("Leaf version", exact=True)
    expect(version).to_contain_text("Leaf layer")
    dialog.get_by_role("button", name="Copy Leaf version", exact=True).click()
    page.wait_for_function(
        "navigator.clipboard.readText().then(text => text.startsWith('Leaf layer'))"
    )
    assert page.evaluate("navigator.clipboard.readText()") == version.text_content()
    dialog.get_by_text("Rendering environment", exact=True).click()
    dialog.get_by_role("button", name="Copy rendering environment", exact=True).click()
    page.wait_for_function(
        "navigator.clipboard.readText().then(text => text.startsWith('{'))"
    )
    identity = json.loads(page.evaluate("navigator.clipboard.readText()"))
    assert identity["delivery"]["runtime"]
    page.keyboard.press("Escape")
    expect(dialog).not_to_be_visible()


def test_about_copy_on_plain_http_machine_name(browser, serve):
    host = gethostname().lower()
    local_url = live_url(
        serve(leaf_page("About over HTTP", "<h1>Page details</h1>"), packages=())
    )
    remote_url = local_url.replace("127.0.0.1", host)
    context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])

    def fetch_from_loopback(route):
        response = route.fetch(url=route.request.url.replace(host, "127.0.0.1"))
        route.fulfill(response=response)

    context.route(f"http://{host}:**/*", fetch_from_loopback)
    page = open_page(browser, remote_url, context=context)
    assert page.evaluate("!isSecureContext && navigator.clipboard === undefined")
    panel_control(page, "inspection").click()
    dialog = page.get_by_role("dialog", name="About this page", exact=True)
    expect(dialog).to_contain_text("Source captured for r1")
    dialog.get_by_role("button", name="Copy Leaf version", exact=True).click()
    page.keyboard.press("Escape")
    page.goto(local_url)
    assert page.evaluate("navigator.clipboard.readText()").startswith("Leaf layer\n")
