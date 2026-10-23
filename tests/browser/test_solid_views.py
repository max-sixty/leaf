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
      import {createView, html, For} from "/runtime/widget-api.js";
      let rows = [{id: "first", label: "First"}, {id: "second", label: "Second"}];
      const reorder = (event) => {
        if (event.key !== "F2") return;
        event.preventDefault();
        rows = rows.toReversed().map((row) => ({...row}));
        drawing.update({rows});
      };
      const drawing = createView(document.getElementById("rows"),
        (props) => For({
          get each() { return props().rows; },
          keyed: (row) => row.id,
          children: (row) => html`<label>${() => row().label}
            <input aria-label=${() => row().label} onKeyDown=${reorder} />
          </label>`,
        }), {rows});
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


def test_views_deliver_immediate_events_upgrade_refs_and_release_detached_roots(
    browser, serve
):
    page = open_page(
        browser, serve(leaf_page("View lifetime", "<h1>View lifetime</h1>"))
    )
    result = page.evaluate(
        """async () => {
      const {createView, html} = await import('/runtime/widget-api.js');
      customElements.define('lf-native-ref-probe', class extends HTMLElement {
        inspect() { return 'upgraded'; }
      });
      let clicks = 0, focuses = 0, inspected, sibling;
      const host = document.createElement('section');
      const drawing = createView(host, read => html`
        <div><span ref=${node => node.append(html`<i>Nested</i>`)}></span>
          <b data-probe="sibling" ref=${node => sibling = node.dataset.probe}></b></div>
        <lf-native-ref-probe ref=${node => inspected = node.inspect()}></lf-native-ref-probe>
        <button onClick=${() => clicks++}>Press</button>
        <input onFocusIn=${() => focuses++} /><output>${() => read().label}</output>`, {label:'first'});
      const input = host.querySelector('input');
      input.value = 'retained words';
      document.body.append(host);
      host.querySelector('button').click(); input.focus(); input.setSelectionRange(2, 9);
      host.remove();
      await new Promise(resolve => queueMicrotask(resolve));
      drawing.update({label:'second'});
      document.body.append(host);
      host.querySelector('button').click(); input.focus();
      const result = {clicks, focuses, inspected, sibling, same: host.querySelector('input') === input,
        value:input.value, selection:[input.selectionStart,input.selectionEnd], label:host.querySelector('output').textContent};
      drawing.dispose(); host.remove();
      window.detachedViewRefs = [];
      for (let i = 0; i < 20; i++) {
        const transient = document.createElement('section');
        createView(transient, () => html`<button onClick=${() => {}}>Temporary</button>`, {});
        document.body.append(transient);
        window.detachedViewRefs.push(new WeakRef(transient));
        transient.remove();
      }
      return result;
    }"""
    )
    assert result == {
        "clicks": 2,
        "focuses": 2,
        "inspected": "upgraded",
        "sibling": "sibling",
        "same": True,
        "value": "retained words",
        "selection": [2, 9],
        "label": "second",
    }
    session = page.context.new_cdp_session(page)
    session.send("HeapProfiler.collectGarbage")
    session.send("HeapProfiler.collectGarbage")
    assert page.evaluate("detachedViewRefs.filter(ref => ref.deref()).length") == 0
    session.detach()
