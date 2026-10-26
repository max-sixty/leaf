"""A reader can inspect and copy a page without changing the page being inspected."""

import json

from model_folds import leaf_page
from playwright.sync_api import expect
from render_harness import (
    consume_browser_errors,
    holding,
    http_error_console,
    open_page,
    panel_control,
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
    dialog = page.get_by_role("dialog", name="Page diagnostics", exact=True)
    expect(dialog).to_be_visible()
    expect(dialog).to_contain_text("Source captured for r1")
    expect(page.locator("#evidence")).not_to_have_attribute("open", "")
    expect(
        dialog.get_by_role("button", name="Close page diagnostics", exact=True)
    ).to_be_focused()
    assert len([url for url in requests if "api/inspect" in url]) == 1

    dialog.get_by_role("button", name="Copy diagnostics", exact=True).click()
    page.wait_for_function(
        "navigator.clipboard.readText().then(text => text.startsWith('{'))"
    )
    report = json.loads(page.evaluate("navigator.clipboard.readText()"))
    assert report["basis"]["revision"] == 1
    assert report["css"]["page"]["declarations"] == 1
    assert report["current_view"]["revision"] == 1
    assert report["current_view"]["observed_at"]
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
    dialog = page.get_by_role("dialog", name="Page diagnostics", exact=True)
    expect(dialog).to_contain_text("Inspection paused")
    consume_browser_errors(page, http_error_console(503))
    dialog.get_by_role("button", name="Retry source inspection").click()
    holding(page, held, 2, "the inspection retry")
    expect(
        dialog.get_by_role("button", name="Close page diagnostics", exact=True)
    ).to_be_focused()
    expect(dialog).to_contain_text("Reading source…")
    page.keyboard.press("Escape")
    expect(dialog).not_to_be_visible()
    expect(page.locator(".lf-fp-leaf")).to_be_focused()
    held[-1].abort("aborted")
