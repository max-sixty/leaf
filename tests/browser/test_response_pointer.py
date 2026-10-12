"""The comment field keeps one primary action; keys disclose its other responses."""

import json

import pytest
from leaf import data as data_model
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE
from render_harness import ROOT, leaf_page, open_page, rendered, write

from browser.test_render_reactions import select_paragraph


@pytest.mark.parametrize("touch,width", [(False, 1280), (True, 390)])
@pytest.mark.parametrize(
    "seat,reactions", [("floating", True), ("inline", True), ("inline", False)]
)
def test_comment_has_one_action_and_keys_preserve_its_other_responses(
    browser, serve, touch, width, seat, reactions
):
    context = browser.new_context(
        has_touch=touch, viewport={"width": width, "height": 900}
    )
    if seat == "floating":
        page = open_page(browser, serve(PANEL_PAGE), context=context)
        select_paragraph(page, "#how-cap")
        if touch:
            page.get_by_role("button", name="Comment on selection", exact=True).tap()
    else:
        registry = json.loads(
            (ROOT / "skills/leaf/packages/default/registry.json").read_text()
        )
        layer = (
            None
            if reactions
            else {
                "$reactions": {
                    "tokens": {name: None for name in registry["$reactions"]["tokens"]}
                }
            }
        )
        url = serve(
            leaf_page(
                "Review",
                '<h1>Review</h1><lf-diff id="patch" source="patch-data"><pre></pre></lf-diff>',
            ),
            layer_registry=layer,
        )
        data_model.cmd_data_set(
            serve.page_dir,
            "patch-data",
            "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
            "@@ -1 +1 @@\n-old\n+new\n",
        )
        page = open_page(
            browser,
            url,
            context=context,
        )
        control = page.locator("#patch .lf-diff-line-comment").first
        control.tap() if touch else control.click()
    bar = page.locator(".lf-fab-bar")
    field = bar.locator(".lf-fab-input")
    write(field, "Keep this draft")
    before = field.bounding_box()
    expect(bar.get_by_role("button", name="Other responses", exact=True)).to_have_count(
        0
    )
    expect(bar.locator(".lf-compose-field button:visible")).to_have_count(1)
    expect(bar.locator(".lf-compose-submit")).to_be_visible()
    field.press("Tab")
    if not reactions:
        expect(bar.locator(".lf-response-options")).to_be_hidden()
        expect(field).to_have_js_property("value", "Keep this draft")
        return
    rendered(page)
    expect(bar.locator(".lf-response-options")).to_be_visible()
    expect(field).to_have_js_property("value", "Keep this draft")
    after = field.bounding_box()
    assert abs(after["width"] - before["width"]) <= 1, (before, after)
    if seat == "floating":
        expect(bar.get_by_role("button", name="Suggest", exact=True)).to_be_visible()
    expect(bar.get_by_role("button", name="keep", exact=True)).to_be_visible()
    page.keyboard.press("Escape")
    expect(bar.locator(".lf-response-options")).to_be_hidden()
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", "Keep this draft")
