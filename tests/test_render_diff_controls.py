"""Diff comment controls keep line coordinates readable and use Leaf's shared face."""

import pytest
from leaf import data as data_model
from playwright.sync_api import expect
from render_harness import leaf_page, open_page, write


@pytest.mark.parametrize("touch", [False, True])
def test_diff_thread_controls_leave_line_numbers_readable(browser, serve, touch):
    """Every line has a stable comment lane, including under a finger.

    Measuring the number's ink catches an overlay even when the gutter's own box
    contains both the number and the button. Hover must preserve that separation.
    """
    patch = """diff --git a/config.py b/config.py
--- a/config.py
+++ b/config.py
@@ -998,3 +998,3 @@
 before = True
-enabled = False
+enabled = True
 after = True
"""
    patch = patch.replace(
        " after = True", " after = True  # " + "long-source-value" * 20
    )
    url = serve(
        leaf_page(
            "Config change",
            '<h1>Config change</h1><lf-diff id="patch" source="patch-data"><pre></pre></lf-diff>',
        )
    )
    data_model.cmd_data_set(serve.page_dir, "patch-data", patch)
    context = browser.new_context(
        viewport={"width": 390 if touch else 1280, "height": 844},
        has_touch=touch,
        is_mobile=touch,
    )
    page = open_page(browser, url, context=context)
    diff = page.locator("#patch")
    buttons = diff.locator(".lf-diff-line-comment")
    expect(buttons).to_have_count(4)
    expect(diff.locator(".lf-diff-wrap, .lf-diff-review, .lf-diff-next")).to_have_count(
        0
    )

    def geometry():
        return buttons.evaluate_all("""buttons => buttons.map(button => {
          const number = button.parentElement.querySelector('[data-line-number-content]');
          const ink = new Range(); ink.selectNodeContents(number);
          const bounds = button.getBoundingClientRect();
          return {right: bounds.right, number: ink.getBoundingClientRect().left,
                  height: bounds.height, width: bounds.width,
                  opacity: getComputedStyle(button).opacity};
        })""")

    before = geometry()
    for reading in before:
        assert reading["right"] <= reading["number"], reading
        assert reading["height"] >= (44 if touch else 24), reading
        assert reading["width"] >= (44 if touch else 24), reading
        assert reading["opacity"] == "1", reading
    buttons.first.hover()
    assert geometry() == before
    assert buttons.first.get_attribute("title") is None
    expect(buttons.first.locator('[data-lf-icon="comment"]')).to_have_count(1)

    buttons.nth(2).click()
    editor = diff.locator(".lf-fab-input")
    expect(editor).to_be_visible()
    expect(editor).to_be_focused()
    reader = diff.locator("code[data-code]")

    def conversation_fits():
        viewport = reader.bounding_box()
        box = diff.locator(".lf-diff-thread-outlet").bounding_box()
        assert viewport["x"] <= box["x"], (viewport, box)
        assert box["x"] + box["width"] <= viewport["x"] + viewport["width"] + 1, (
            viewport,
            box,
        )

    conversation_fits()
    write(editor, "Does this affect existing settings?")
    editor.press("Control+Enter" if touch else "Enter")
    expect(diff.locator(".lf-page-thread")).to_contain_text(
        "Does this affect existing settings?"
    )
    reader.evaluate("node => node.scrollLeft = 200")
    conversation_fits()
    context.close()
