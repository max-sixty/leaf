"""Reader code views retain source evidence while changing line presentation."""

import re
from html import escape
from socket import gethostname

import pytest
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    consume_browser_errors,
    leaf_page,
    open_page,
    panel_menu,
    scroll_settled,
    told,
)

from leaf.render_checks import rendered


@pytest.mark.parametrize("gesture", ["click", "Enter"])
def test_code_copy_on_plain_http_machine_name(browser, serve, gesture):
    source = leaf_page(
        "Code copy over HTTP",
        "<h1>Code copy over HTTP</h1><pre><code>echo hello</code></pre>",
    )
    # The browser lower-cases a URL's host, so the route rewrites that spelling to
    # loopback; the machine's name needn't resolve there, as on CI's macOS runner.
    host = gethostname().lower()
    local_url = live_url(serve(source))
    remote_url = local_url.replace("127.0.0.1", host)
    context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])

    def fetch_from_loopback(route):
        response = route.fetch(url=route.request.url.replace(host, "127.0.0.1"))
        route.fulfill(response=response)

    context.route(f"http://{host}:**/*", fetch_from_loopback)
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
    panel_menu(page, touch=True).locator('.lf-fp-item[data-row="keyboard"]').tap()


def test_code_wrapping_keeps_source_copy_and_reader_choice(browser, serve):
    code = 'def upload(client, job, payload, max_attempts=2):\n    key = f"upload:{job.tenant_id}:{job.id}"\n'
    source = leaf_page(
        "Code reading",
        '<h1 id="title">Code reading</h1><p id="note">Original review.</p>'
        f'<lf-code id="code" language="python" hi="2"><pre>{escape(code)}</pre></lf-code>',
    )
    url = live_url(serve(source))
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        has_touch=True,
        is_mobile=True,
        permissions=["clipboard-read", "clipboard-write"],
    )
    page = open_page(browser, url, context=context)
    host = page.locator("#code")
    pre = host.locator("pre")
    # What lf-code declares rather than asks for, which only Leaf reads: its `w`
    # (`lfCommands`), a Copy control standing after its block (`data-lf-copy`), and the
    # word its highlighted line says to a listener (`data-lf-quiet`).
    expect(host).to_have_attribute(
        "aria-keyshortcuts", re.compile(r"^w$", re.IGNORECASE)
    )
    expect(host.locator(":scope > pre + .lf-code-copy")).to_have_count(1)
    expect(host.locator(".lf-code-line.hi > .lf-quiet")).to_have_text("highlighted")
    before = pre.evaluate("e => ({text:e.textContent, height:e.clientHeight})")
    page.evaluate(
        "window.sourceRows = [...document.querySelectorAll('#code .lf-code-line')]"
    )
    # A finger starts at the source, then uses the existing command reference.
    pre.tap(position={"x": 30, "y": 20})
    open_keyboard_shortcuts(page)
    page.get_by_role("button", name="Unwrap lines", exact=True).tap()
    expect(pre).to_be_focused()
    assert pre.evaluate("e => e.scrollWidth > e.clientWidth")
    assert pre.evaluate("e => e.clientHeight") < before["height"]
    assert pre.text_content() == before["text"]
    assert page.evaluate(
        "sourceRows.every((n,i) => n === document.querySelectorAll('#code .lf-code-line')[i])"
    )
    rendered(page)
    pre.hover()
    page.mouse.wheel(200, 0)
    page.wait_for_function("document.querySelector('#code pre').scrollLeft > 0")
    scroll_settled(page, "#code pre", axis="x")
    horizontal = pre.evaluate("e => e.scrollLeft")
    page.keyboard.press("w")
    rendered(page)
    expect(pre).to_be_focused()
    assert pre.evaluate("e => e.scrollWidth <= e.clientWidth")
    page.keyboard.press("w")
    rendered(page)
    expect(pre).to_be_focused()
    assert pre.evaluate("e => e.scrollLeft") >= horizontal
    open_keyboard_shortcuts(page)
    page.locator(".lf-command-reference").get_by_role(
        "button", name="Copy code", exact=True
    ).tap()
    expect(pre).to_be_focused()
    assert page.evaluate("navigator.clipboard.readText()") == code.rstrip("\n")
    (serve.page_dir / "index.html").write_text(
        source.replace("Original review.", "Revised review.")
    )
    told(page)
    rendered(page)
    expect(pre).to_be_focused()
    assert pre.evaluate("e => e.scrollWidth > e.clientWidth")
    assert page.evaluate(
        "sourceRows.every((n,i) => n === document.querySelectorAll('#code .lf-code-line')[i])"
    )
    page.emulate_media(media="print")
    assert pre.evaluate("e => e.scrollWidth <= e.clientWidth")
    page.emulate_media(media="screen")
    assert pre.evaluate("e => e.scrollWidth > e.clientWidth")
    changed = source.replace("max_attempts=2", "max_attempts=3")
    (serve.page_dir / "index.html").write_text(changed)
    page.wait_for_function(
        "document.querySelector('#code pre').textContent.includes('max_attempts=3')",
    )
    rendered(page)
    expect(pre).to_be_focused()
    assert pre.evaluate("e => e.scrollWidth > e.clientWidth")
    page.keyboard.press("Enter")
    assert "max_attempts=3" in page.evaluate("navigator.clipboard.readText()")
