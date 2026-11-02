"""The portable staging helper on a host without Leaf's runtime."""

import json

from playwright.sync_api import expect
from smoke.test_plain_page import ROOT, host_page, install

from leaf.revision_delivery import layer_import_map


def test_a_host_stages_retained_shadow_content_without_leaf(browser):
    markup = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Shadow host</title>
<script type="importmap">{json.dumps(layer_import_map(ROOT))}</script>
</head><body><div id="host"><pre>authored input</pre></div>
<script type="module">
try {{
  const {{ shadowStage, move, setChildren, setChildLists, keeps, keepsText }} =
    await import("/runtime/portable-api.js");
  const host = document.querySelector("#host");
  const field = document.createElement("input");
  field.value = "reader's draft";
  shadowStage(host, [field]);
  field.focus();
  field.setSelectionRange(2, 5);
  const words = document.createElement("p");
  keepsText(words, "Replacement content");
  keeps(words, "aria-label", "Evidence");
  shadowStage(host, [words, field]);
  shadowStage(host, [field, words]);
  window.staged = {{
    retained: host.shadowRoot.querySelector("input") === field,
    focused: host.shadowRoot.activeElement === field,
    value: field.value,
    selection: [field.selectionStart, field.selectionEnd],
    authoredChildren: host.childNodes.length,
  }};
  const left = document.createElement("section");
  const right = document.createElement("section");
  setChildren(host.shadowRoot, [left, right]);
  move(left, field);
  field.focus();
  field.setSelectionRange(2, 5);
  setChildLists([[left, [words]], [right, [field]]]);
  setChildren(right, [words, field]);
  window.reconciled = {{
    retained: right.querySelector("input") === field,
    focused: host.shadowRoot.activeElement === field,
    value: field.value,
    selection: [field.selectionStart, field.selectionEnd],
    order: [...right.children].map(node => node.localName),
  }};
}} catch (error) {{
  document.querySelector("#failure").textContent = error.stack;
}} finally {{ window.hostReady = true; }}
</script><pre id="failure"></pre></body></html>"""
    with host_page(markup, install()) as url:
        page = browser.new_page()
        page.goto(url)
        page.wait_for_function("window.hostReady")
        assert page.locator("#failure").inner_text() == ""
        assert page.evaluate("staged") == {
            "retained": True,
            "focused": True,
            "value": "reader's draft",
            "selection": [2, 5],
            "authoredChildren": 0,
        }
        assert page.evaluate("reconciled") == {
            "retained": True,
            "focused": True,
            "value": "reader's draft",
            "selection": [2, 5],
            "order": ["p", "input"],
        }
        expect(page.locator("#host p")).to_have_text("Replacement content")
        expect(page.locator("#host p")).to_have_attribute("aria-label", "Evidence")
        assert page.evaluate("!window.lfRootState")
