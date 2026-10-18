"""Reader code views retain source evidence while changing line presentation."""

from html import escape

from leaf.render_checks import rendered
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import leaf_page, open_page, scroll_settled, told


def test_code_wrapping_keeps_source_copy_and_reader_choice(browser, serve):
    code = 'def upload(client, job, payload, max_attempts=2):\n    key = f"upload:{job.tenant_id}:{job.id}"\n'
    source = leaf_page(
        "Code reading",
        '<h1 id="title">Code reading</h1><p id="note">Original review.</p>'
        f'<lf-code id="code" language="python"><pre>{escape(code)}</pre></lf-code>',
    )
    url = live_url(serve(source))
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        has_touch=True,
        is_mobile=True,
        permissions=["clipboard-read", "clipboard-write"],
    )
    page = open_page(browser, url, context=context)
    page.set_default_timeout(10000)
    host = page.locator("#code")
    pre = host.locator("pre")
    before = pre.evaluate("e => ({text:e.textContent, height:e.clientHeight})")
    page.evaluate(
        "window.sourceRows = [...document.querySelectorAll('#code .lf-code-line')]"
    )
    # A finger starts at the source, then uses the existing command reference.
    pre.tap(position={"x": 30, "y": 20})
    page.get_by_role("button", name="More page controls", exact=True).tap()
    page.get_by_role("button", name="Keyboard shortcuts", exact=True).tap()
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
    page.get_by_role("button", name="More page controls", exact=True).tap()
    page.get_by_role("button", name="Keyboard shortcuts", exact=True).tap()
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
        timeout=10000,
    )
    rendered(page)
    expect(pre).to_be_focused()
    assert pre.evaluate("e => e.scrollWidth > e.clientWidth")
    page.keyboard.press("Enter")
    assert "max_attempts=3" in page.evaluate("navigator.clipboard.readText()")


def test_code_reference_keeps_command_context_and_cancel_destination(browser, serve):
    source = leaf_page(
        "Code context",
        '<h1>Code context</h1><label>Notes <input id="notes"></label>'
        '<lf-code id="code"><pre>result = upload(client, job, payload, max_attempts=2)</pre></lf-code>',
    )
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True
    )
    page = open_page(browser, live_url(serve(source)), context=context)
    pre = page.locator("#code pre")
    more = page.get_by_role("button", name="More page controls", exact=True)
    reference = page.locator(".lf-command-reference")
    pre.tap()
    expect(pre).to_be_focused()
    more.tap()
    page.get_by_role("button", name="Keyboard shortcuts", exact=True).tap()
    page.keyboard.press("Escape")
    expect(more).to_be_focused()
    pre.tap()
    more.tap()
    page.get_by_role("button", name="Keyboard shortcuts", exact=True).tap()
    reference.locator(".lf-command-reference-close").tap()
    expect(more).to_be_focused()
    pre.tap()
    page.keyboard.press("?")
    reference.get_by_role("button", name="Unwrap lines", exact=True).tap()
    expect(pre).to_be_focused()
    assert pre.evaluate("e => e.scrollWidth > e.clientWidth")
    page.locator("#code").get_by_role("button", name="Copy code", exact=True).tap()
    more.tap()
    page.get_by_role("button", name="Keyboard shortcuts", exact=True).tap()
    reference.get_by_role("button", name="Wrap lines", exact=True).tap()
    rendered(page)
    assert pre.evaluate("e => e.scrollWidth <= e.clientWidth")
    notes = page.get_by_role("textbox", name="Notes")
    notes.tap()
    page.keyboard.type("w")
    expect(notes).to_have_value("w")
    assert pre.evaluate("e => e.scrollWidth <= e.clientWidth")
    more.tap()
    page.get_by_role("button", name="Keyboard shortcuts", exact=True).tap()
    page.keyboard.press("Escape")
    expect(more).to_be_focused()
