"""Every response on a selection is reachable without a keyboard."""

import json

import pytest
from leaf import data as data_model
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE
from render_harness import ROOT, leaf_page, open_page, rendered, write
from test_render_reactions import select_paragraph


@pytest.mark.parametrize("touch,width", [(False, 1280), (True, 390)])
@pytest.mark.parametrize(
    "seat,reactions", [("floating", True), ("inline", True), ("inline", False)]
)
def test_other_responses_preserve_the_comment_and_open_by_pointer(
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
    more = bar.get_by_role("button", name="Other responses", exact=True)
    if not reactions:
        expect(more).to_be_hidden()
        return
    expect(more).to_be_visible()
    more.tap() if touch else more.click()
    rendered(page)
    expect(more).to_have_attribute("aria-expanded", "true")
    expect(field).to_have_js_property("value", "Keep this draft")
    after = field.bounding_box()
    assert abs(after["width"] - before["width"]) <= 1, (before, after)
    if seat == "floating":
        expect(bar.get_by_role("button", name="Suggest", exact=True)).to_be_visible()
    expect(bar.get_by_role("button", name="keep", exact=True)).to_be_visible()
    more.tap() if touch else more.click()
    expect(more).to_have_attribute("aria-expanded", "false")
    expect(field).to_have_js_property("value", "Keep this draft")
