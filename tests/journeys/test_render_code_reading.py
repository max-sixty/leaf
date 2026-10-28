"Reader code views retain source evidence while changing line presentation."

from browser.test_render_code_reading import open_keyboard_shortcuts
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    leaf_page,
    open_page,
)

from leaf.render_checks import rendered


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
    # The leaf's menu goes away as its row opens the reference, so the leaf is the
    # door the reference returns to.
    leaf = page.locator(".lf-fp-leaf")
    reference = page.locator(".lf-command-reference")
    pre.tap()
    expect(pre).to_be_focused()
    open_keyboard_shortcuts(page)
    page.keyboard.press("Escape")
    expect(leaf).to_be_focused()
    pre.tap()
    open_keyboard_shortcuts(page)
    reference.locator(".lf-command-reference-close").tap()
    expect(leaf).to_be_focused()
    pre.tap()
    page.keyboard.press("?")
    reference.get_by_role("button", name="Unwrap lines", exact=True).tap()
    expect(pre).to_be_focused()
    assert pre.evaluate("e => e.scrollWidth > e.clientWidth")
    page.locator("#code").get_by_role("button", name="Copy code", exact=True).tap()
    open_keyboard_shortcuts(page)
    reference.get_by_role("button", name="Wrap lines", exact=True).tap()
    rendered(page)
    assert pre.evaluate("e => e.scrollWidth <= e.clientWidth")
    notes = page.get_by_role("textbox", name="Notes")
    notes.tap()
    page.keyboard.type("w")
    expect(notes).to_have_value("w")
    assert pre.evaluate("e => e.scrollWidth <= e.clientWidth")
    open_keyboard_shortcuts(page)
    page.keyboard.press("Escape")
    expect(leaf).to_be_focused()
