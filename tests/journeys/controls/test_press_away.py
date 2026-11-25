"""Tests scheduled by the measured cost of their boundary."""

from browser.controls.test_press_away import centre, drag, tap
from browser.test_render_reactions import select_paragraph
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE
from render_harness import (
    leaf_page,
    open_page,
)


def test_a_press_away_puts_the_response_bar_away(browser, serve):
    page = open_page(browser, serve(PANEL_PAGE))
    bar = page.locator(".lf-fab-bar")
    outside = centre(page.locator("h1"))
    select_paragraph(page, "#how-store")
    expect(bar).to_be_visible()
    # Selecting the words typed in its field past its edge leaves it standing.
    drag(page, centre(bar.locator(".lf-fab-input")), outside)
    expect(bar).to_be_visible()
    tap(page, outside)
    expect(bar).to_be_hidden()
    select_paragraph(page, "#how-store")
    expect(bar).to_be_visible()
    page.mouse.click(*outside)
    expect(bar).to_be_hidden()
    select_paragraph(page, "#how-store")
    expect(bar).to_be_visible()
    page.keyboard.press("Escape")
    expect(bar).to_be_hidden()


def test_a_press_survives_a_frame_return_but_ends_when_its_document_loses_input(
    webkit_browser, serve
):
    page = open_page(
        webkit_browser,
        serve(
            leaf_page(
                "A press across frame focus",
                """
<label>Parent editor<input id="parent-editor"></label>
<button id="handoff">Return to the preview</button>
<lf-sample id="preview" label="Preview">
  <template id="preview-document" data-sample>
    <input id="child-editor" value="Preview input">
  </template>
</lf-sample>
<script type="module">
  const {focusDestination, onPressAway, onUserInput} = await window.__lfCheckApi();
  window.completed = 0;
  window.inputBlurs = [];
  window.nativeBlurs = [];
  onPressAway(path => path.some(node => node.id === 'handoff'), () => completed++);
  onUserInput(event => {
    if (event.type === 'blur') inputBlurs.push(document.hasFocus());
  });
  window.addEventListener('blur', () => nativeBlurs.push(document.hasFocus()));
  document.querySelector('#handoff').addEventListener('mousedown', event => {
    event.preventDefault();
    const sample = document.querySelector('#preview');
    focusDestination(sample.querySelector('iframe'), 'return');
    void sample.restoreCurrentLocation();
  });
</script>
""",
            )
        ),
    )
    parent = page.get_by_role("textbox", name="Parent editor")
    child = page.frame_locator("#preview iframe").locator("#child-editor")
    child.click()
    parent.click()
    page.evaluate("inputBlurs.length = 0; nativeBlurs.length = 0")
    page.get_by_role("button", name="Return to the preview").click()
    assert page.evaluate("nativeBlurs.includes(true)")
    assert page.evaluate("inputBlurs") == []
    assert page.evaluate("completed") == 1

    # Losing the child document's input is a real departure, even while the parent
    # document stays active. Its held press must not complete when release arrives.
    child.evaluate("""async () => {
      const {onPressAway, onUserInput} = await import('/runtime/focus.js');
      window.completed = 0;
      window.inputBlurs = [];
      onPressAway(() => true, () => completed++);
      onUserInput(event => {
        if (event.type === 'blur') inputBlurs.push(document.hasFocus());
      });
    }""")
    child.click()
    child.evaluate("completed = 0; inputBlurs.length = 0")
    page.mouse.move(*centre(child))
    page.mouse.down()
    parent.focus()
    assert child.evaluate("document.hasFocus()") is False
    page.mouse.up()
    assert child.evaluate("inputBlurs") == [False]
    assert child.evaluate("completed") == 0
