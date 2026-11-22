"""Tests scheduled by the measured cost of their boundary."""

import json

from browser.test_page_inspection import MENU_ROOM
from model_folds import leaf_page
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    consume_browser_errors,
    open_page,
    over_plain_http,
    panel_control,
)


def test_diagnostics_arrival_inside_sample_stays_in_child_document(browser, serve):
    """A child report reaches its own observation, even when its parent has the same id."""
    source = leaf_page(
        "Nested location",
        '<h1 id="arrangement">Parent</h1>'
        '<lf-sample id="practice" label="Nested page"><template id="practice-source" data-sample>'
        '<h1>Child</h1><div id="arrangement" style="display:grid;grid-template-columns:1fr 1fr">'
        f"<p>First</p><p>Second</p></div>{MENU_ROOM}</template></lf-sample>",
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


def test_sample_diagnostics_copy_failure_keeps_a_visible_manual_copy_route(
    browser, serve
):
    source = leaf_page(
        "Copy host",
        "<h1>Parent</h1>"
        '<lf-sample id="practice" label="Nested page"><template id="practice-source" data-sample>'
        "<h1>Child</h1><p>Clipboard access is restricted here.</p>"
        f"{MENU_ROOM}</template></lf-sample>",
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


def test_about_copy_on_plain_http_machine_name(browser, serve):
    local_url = live_url(
        serve(leaf_page("About over HTTP", "<h1>Page details</h1>"), packages=())
    )
    context, remote_url = over_plain_http(browser, local_url)
    page = open_page(browser, remote_url, context=context)
    assert page.evaluate("!isSecureContext && navigator.clipboard === undefined")
    panel_control(page, "inspection").click()
    dialog = page.get_by_role("dialog", name="About this page", exact=True)
    expect(dialog).to_contain_text("Source captured for r1")
    dialog.get_by_role("button", name="Copy Leaf version", exact=True).click()
    page.keyboard.press("Escape")
    page.goto(local_url)
    assert page.evaluate("navigator.clipboard.readText()").startswith("Leaf layer\n")
