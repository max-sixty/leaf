"""Diff controls share canonical fields and preserve the compact source reader."""

from html import escape

import pytest
from leaf import data as data_model
from leaf.render_checks import rendered
from playwright.sync_api import expect
from render_harness import leaf_page, open_page, write


@pytest.mark.parametrize("width,scheme", [(1280, "light"), (390, "dark")])
def test_diff_filter_has_one_frame_and_clears_with_its_count_inside(
    browser, serve, width, scheme
):
    """The canonical search owns the frame, count, and Clear; filtering owns the rows."""
    patch = "".join(
        f"diff --git a/src/file-{index}.py b/src/file-{index}.py\n"
        f"--- a/src/file-{index}.py\n+++ b/src/file-{index}.py\n"
        "@@ -1 +1 @@\n-old\n+new\n"
        for index in range(12)
    )
    context = browser.new_context(
        viewport={"width": width, "height": 844}, color_scheme=scheme
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Changed files",
                f'<h1>Changed files</h1><lf-diff id="patch"><pre>{escape(patch)}</pre></lf-diff>',
            )
        ),
        context=context,
    )
    diff = page.locator("#patch")
    field = diff.locator(".lf-diff-search")
    editor = field.locator("input")
    count = diff.locator(".lf-diff-progress")
    rows = diff.locator(".lf-diff-file:not(.lf-diff-filtered)")
    expect(editor).to_have_accessible_name("Filter diff files")
    page.get_by_role("heading", name="Changed files").click()
    for _ in range(8):
        page.keyboard.press("Tab")
        if editor.evaluate("node => node === node.getRootNode().activeElement"):
            break
    expect(editor).to_be_focused()
    assert editor.evaluate("node => node.matches(':focus-visible')")
    field.scroll_into_view_if_needed()
    rendered(page)
    frame = field.bounding_box()
    assert diff.locator(".lf-diff-tools").bounding_box() == frame
    count_box = count.bounding_box()
    assert (
        frame["x"]
        <= count_box["x"]
        < count_box["x"] + count_box["width"]
        <= frame["x"] + frame["width"]
    )
    for query, matches in (("file-0", 1), ("no-match", 0)):
        editor.fill(query)
        expect(rows).to_have_count(matches)
        expect(count).to_have_text(f"{matches} of 12")
        expect(field.get_by_role("button", name="Clear")).to_be_visible()
        assert field.bounding_box() == frame
    field.get_by_role("button", name="Clear").click()
    expect(editor).to_have_value("")
    expect(editor).to_be_focused()
    expect(rows).to_have_count(12)
    expect(count).to_have_text("12 files")
    assert field.bounding_box() == frame
    editor.fill("file-0")
    expect(rows).to_have_count(1)
    editor.press("ControlOrMeta+A")
    editor.press("Backspace")
    expect(rows).to_have_count(12)
    expect(count).to_have_text("12 files")


@pytest.mark.parametrize("touch", [False, True])
def test_diff_thread_controls_leave_line_numbers_readable(browser, serve, touch):
    """A hover mark fits the native margin without changing its reading geometry.

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
            '<h1>Config change</h1><lf-diff id="patch" source="patch-data"><pre></pre></lf-diff>'
            f'<lf-diff id="native"><pre>{escape(patch)}</pre></lf-diff>',
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
          const bounds = button.querySelector('.lf-diff-line-plus').getBoundingClientRect();
          return {right: bounds.right, number: ink.getBoundingClientRect().left,
                  height: button.parentElement.getBoundingClientRect().height,
                  hitHeight: button.getBoundingClientRect().height,
                  background: getComputedStyle(button).backgroundColor,
                  opacity: getComputedStyle(button).opacity};
        })""")

    before = geometry()
    for reading in before:
        assert reading["right"] <= reading["number"], reading
        assert reading["hitHeight"] == reading["height"], reading
        assert reading["opacity"] == "0", reading
    native = page.locator("#native [data-gutter] > [data-line-index]").first
    assert before[0]["height"] == native.bounding_box()["height"]
    assert (
        diff.locator("[data-gutter]").bounding_box()["width"]
        == page.locator("#native [data-gutter]").bounding_box()["width"]
    )
    diff.locator("[data-content] > [data-line]").first.hover()
    after = geometry()
    assert after[0]["opacity"] == "1"
    assert after[0]["background"] == "rgba(0, 0, 0, 0)"
    assert [{k: v for k, v in r.items() if k != "opacity"} for r in after] == [
        {k: v for k, v in r.items() if k != "opacity"} for r in before
    ]
    buttons.first.hover()
    assert geometry()[0] == after[0]
    assert buttons.first.get_attribute("title") is None
    expect(buttons.first.locator('[data-lf-icon="comment"]')).to_have_count(0)
    expect(
        diff.locator('.lf-diff-file-comment [data-lf-icon="comment"]')
    ).to_have_count(1)

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
