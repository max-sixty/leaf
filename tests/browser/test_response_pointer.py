"""One anchored response picker preserves the composer across every seat and input route."""

import json

import pytest
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE
from render_harness import ROOT, leaf_page, open_page, rendered, selection_field, write

from browser.test_render_reactions import select_paragraph
from leaf import data as data_model


@pytest.mark.parametrize("touch,width", [(False, 1280), (True, 390)])
@pytest.mark.parametrize(
    "seat,reactions",
    [("floating", True), ("panel", True), ("inline", True), ("inline", False)],
)
def test_response_picker_keeps_the_comment_in_place(
    browser, serve, touch, width, seat, reactions
):
    context = browser.new_context(
        has_touch=touch, viewport={"width": width, "height": 900}
    )
    if seat in {"floating", "panel"}:
        source = (
            PANEL_PAGE.replace("<body>", '<body data-annotations="page">', 1)
            if seat == "panel"
            else PANEL_PAGE
        )
        page = open_page(browser, serve(source), context=context)
        select_paragraph(page, "#how-cap")
        if touch:
            selection_field(page).tap()
        elif seat == "panel":
            selection_field(page).click()
    else:
        registry = json.loads((ROOT / "packages/default/registry.json").read_text())
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
                '<h1>Review</h1><lf-diff id="patch" source="patch-data"></lf-diff>',
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
    trigger = bar.get_by_role("button", name="Other responses", exact=True)
    # The empty field holds the ⋯ in its corner, and the draft's first word takes it
    # away without widening the field.
    if reactions:
        expect(trigger).to_be_visible()
        empty = field.bounding_box()
        corner = trigger.bounding_box()
        assert empty["x"] < corner["x"], (empty, corner)
        assert corner["x"] + corner["width"] <= empty["x"] + empty["width"], (
            empty,
            corner,
        )
    else:
        expect(trigger).to_be_hidden()
    write(field, "Keep this draft")
    before = field.bounding_box()
    expect(trigger).to_be_hidden()
    if reactions:
        assert abs(before["width"] - empty["width"]) <= 1, (empty, before)
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
    assert abs(after["y"] - before["y"]) <= 1, (before, after)
    assert abs(after["height"] - before["height"]) <= 1, (before, after)
    if seat == "floating":
        expect(bar.get_by_role("button", name="Suggest", exact=True)).to_be_visible()
    expect(bar.get_by_role("button", name="keep", exact=True)).to_be_visible()
    page.keyboard.press("Escape")
    expect(bar.locator(".lf-response-options")).to_be_hidden()
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", "Keep this draft")
    write(field, "")
    trigger.tap() if touch else trigger.click()
    expect(bar.locator(".lf-response-options")).to_be_visible()
    picker = bar.locator(".lf-response-options").bounding_box()
    assert picker["y"] + picker["height"] <= trigger.bounding_box()["y"] + 1, picker
    assert picker["x"] >= 0 and picker["x"] + picker["width"] <= width, picker
    trigger.tap() if touch else trigger.click()
    expect(bar.locator(".lf-response-options")).to_be_hidden()
    expect(field).to_have_js_property("value", "")
