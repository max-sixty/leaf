"""Reader code views retain source evidence while changing line presentation."""

import pytest
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    consume_browser_errors,
    leaf_page,
    open_page,
    over_plain_http,
    panel_menu,
)


@pytest.mark.parametrize("gesture", ["click", "Enter"])
def test_code_copy_on_plain_http_machine_name(browser, serve, gesture):
    source = leaf_page(
        "Code copy over HTTP",
        "<h1>Code copy over HTTP</h1><pre><code>echo hello</code></pre>",
    )
    local_url = live_url(serve(source))
    context, remote_url = over_plain_http(browser, local_url)
    page = open_page(browser, remote_url, context=context)
    assert page.evaluate("!isSecureContext && navigator.clipboard === undefined")
    if gesture == "click":
        page.locator("pre").hover()
        page.get_by_role("button", name="Copy code", exact=True).click()
    else:
        page.locator("pre").focus()
        page.keyboard.press("Enter")
        expect(page.locator("pre")).to_be_focused()
    copy_state = page.locator(".lf-code-copy").evaluate(
        "e => ({status: e.status, value: e.value})"
    )
    assert copy_state["status"] == "success"
    assert copy_state["value"] == "echo hello"

    page.goto(local_url)
    assert page.evaluate("navigator.clipboard.readText()") == "echo hello"


def test_sample_code_copy_keeps_its_clipboard_boundary(browser, serve):
    source = leaf_page(
        "Sample copy boundary",
        '<h1>Sample copy boundary</h1><lf-sample id="sample" label="Sample">'
        '<template id="sample-page" data-sample>'
        "<pre><code>private sample</code></pre></template></lf-sample>",
    )
    context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
    page = open_page(browser, live_url(serve(source)), context=context)
    page.evaluate("navigator.clipboard.writeText('kept')")
    sample = page.frame_locator("#sample iframe")
    sample.locator("pre").hover()
    sample.get_by_role("button", name="Copy code", exact=True).click()
    assert page.evaluate("navigator.clipboard.readText()") == "kept"
    consume_browser_errors(page, "Permissions policy violation: The Clipboard API")


def open_keyboard_shortcuts(page):
    """Tap the panel's leaf, unfolding it first where it rests as the mark, then its
    menu's Keyboard shortcuts row: a finger's door to the command reference."""
    panel_menu(page, touch=True).locator('.lf-fp-item[data-lf-row="keyboard"]').tap()


@pytest.mark.parametrize("surface", ["panel", "margin"])
def test_thread_code_block_copies_just_its_source(browser, serve, surface):
    from render_cases_interaction import PANEL_PAGE, panel_comment

    from browser.threads import append_agent_reply, open_panel_thread

    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Which command?", {"section": "lede"})
    append_agent_reply(
        serve.page_dir, root, "Run this:\n\n```sh\necho hello\n```\n\nThen continue."
    )
    context = browser.new_context(
        permissions=["clipboard-read", "clipboard-write"], has_touch=True
    )
    page = open_page(browser, url, context=context)
    if surface == "panel":
        thread = open_panel_thread(page, root)
    else:
        page.locator(".lf-margin-marker").first.click()
        thread = page.locator(".lf-margin-preview .lf-page-thread")
    block = thread.locator("pre")
    expect(block).to_have_text("echo hello\n")
    block.hover()
    anchor = block.evaluate("e => e.style.anchorName")
    copy = page.locator(f'.lf-code-copy[style*="position-anchor: {anchor};"]')
    assert copy.count() == 1
    copy.evaluate("e => e.feedbackDuration = 0")
    assert copy.evaluate(
        "e => {const r=e.getBoundingClientRect();return e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}"
    )
    copy.get_by_role("button", name="Copy code", exact=True).click()
    assert page.evaluate("navigator.clipboard.readText()") == "echo hello\n"
    expect(thread).to_be_visible()
    # Touch reveals the same control, then copies only this source.
    expect(copy).to_have_js_property("isCopying", False)
    page.evaluate("navigator.clipboard.writeText('reset')")
    block.tap()
    copy.get_by_role("button", name="Copy code", exact=True).tap()
    assert page.evaluate("navigator.clipboard.readText()") == "echo hello\n"
    # Tab reaches the source's stop; Enter keeps the thread open and copies it.
    block.click()
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    expect(block).to_be_focused()
    expect(copy).to_have_js_property("isCopying", False)
    page.evaluate("navigator.clipboard.writeText('reset')")
    page.keyboard.press("Enter")
    assert page.evaluate("navigator.clipboard.readText()") == "echo hello\n"
    expect(thread).to_be_visible()
