"""Solid's keyed updates keep the native editing state Leaf promises."""

import pytest
from playwright.sync_api import expect
from render_harness import leaf_page, open_page, rendered


@pytest.mark.parametrize("native_move", [True, False])
def test_keyed_reordering_keeps_typed_words_focus_and_selection(
    browser, serve, native_move
):
    source = leaf_page(
        "Retained editing", '<h1>Retained editing</h1><div id="rows"></div>'
    )
    script = r"""
    <script type="module">
      import {createView, solidHtml, For} from "/runtime/widget-api.js";
      let rows = [{id: "first", label: "First"}, {id: "second", label: "Second"}];
      const reorder = (event) => {
        if (event.key !== "F2") return;
        event.preventDefault();
        rows = rows.toReversed().map((row) => ({...row}));
        drawing.update(rows);
      };
      const drawing = createView(document.getElementById("rows"),
        (props) => For({
          get each() { return props(); },
          keyed: (row) => row.id,
          children: (row) => solidHtml`<label>${() => row().label}
            <input aria-label=${() => row().label} onKeyDown=${reorder} />
          </label>`,
        }), rows);
    </script>
    """
    page = open_page(browser, serve(source.replace("</body>", script + "</body>")))
    if not native_move:
        page.evaluate("Element.prototype.moveBefore = undefined")
    field = page.get_by_role("textbox", name="First", exact=True)
    field.fill("Retained words")
    field.press("Home")
    for _ in range(8):
        field.press("Shift+ArrowRight")
    field.press("F2")
    rendered(page)
    expect(page.locator("#rows > label").first).to_have_text("Second")
    expect(field).to_be_focused()
    expect(field).to_have_value("Retained words")
    assert field.evaluate("node => [node.selectionStart, node.selectionEnd]") == [0, 8]
