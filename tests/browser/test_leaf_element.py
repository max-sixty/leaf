"""The element lifecycle follows host properties without Leaf page services."""

import json

from playwright.sync_api import expect
from smoke.test_plain_page import ROOT, host_page, install

from leaf.revision_delivery import layer_import_map


def test_a_host_updates_and_reconnects_a_portable_element(browser):
    markup = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Element host</title>
<script type="importmap">{json.dumps(layer_import_map(ROOT))}</script>
</head><body><div id="host"><host-reading id="reading"></host-reading></div>
<script type="module">
try {{
  const {{ LeafElement, html, shadowStage, whileConnected, publishOutput, loadDeferred }} = await import("/runtime/portable-api.js");
  window.reading = document.querySelector("#reading");
  shadowStage(document.querySelector("#host"), [reading]);
  customElements.define("host-reading", class extends LeafElement {{
    static properties = {{ value: {{ attribute: false }} }};
    setup() {{
      this.setups = (this.setups ?? 0) + 1;
      this.connections = [];
      whileConnected(this, () => {{
        this.connections.push("connected");
        return () => this.connections.push("disconnected");
      }});
    }}
    render() {{ return html`<p>${{this.value}}</p>`; }}
    updated(changed) {{
      super.updated(changed);
      this.dispatchEvent(new CustomEvent("drawn", {{detail: {{value: this.value}}}}));
    }}
  }});
  window.outputs = [];
  reading.addEventListener("lf-output", event => outputs.push(event.detail));
  window.publish = value => publishOutput(reading, "rows", value);
  window.loadUnowned = () => loadDeferred({{files: []}}, "missing")
    .then(() => "unexpected value", error => error.message);
  window.drawings = [];
  reading.addEventListener("drawn", event => drawings.push({{
    value: event.detail.value, words: reading.querySelector("p").textContent,
  }}));
  reading.value = "First reading";
}} catch (error) {{
  document.querySelector("#failure").textContent = error.stack;
}} finally {{ window.hostReady = true; }}
</script><pre id="failure"></pre></body></html>"""
    with host_page(markup, install()) as url:
        page = browser.new_page()
        page.goto(url)
        page.wait_for_function("window.hostReady")
        assert page.locator("#failure").inner_text() == ""
        expect(page.locator("#reading p")).to_have_text("First reading")
        page.evaluate("reading.value = 'Second reading'")
        expect(page.locator("#reading p")).to_have_text("Second reading")
        page.evaluate("""async () => {
          reading.remove();
          // Let the connection owner observe departure before returning.
          await Promise.resolve();
          reading.value = 'Away reading';
          await reading.updateComplete;
        }""")
        assert (
            page.evaluate("reading.querySelector('p').textContent") == "Second reading"
        )
        assert page.evaluate("reading.connections") == ["connected", "disconnected"]
        page.evaluate("document.querySelector('#host').shadowRoot.append(reading)")
        expect(page.locator("#reading p")).to_have_text("Away reading")
        assert page.evaluate("reading.setups") == 1
        assert page.evaluate("reading.connections") == [
            "connected",
            "disconnected",
            "connected",
        ]
        assert page.evaluate("drawings") == [
            {"value": "First reading", "words": "First reading"},
            {"value": "Second reading", "words": "Second reading"},
            {"value": "Away reading", "words": "Away reading"},
        ]
        # A plain host can hear derived output without installing Leaf's data owner.
        page.evaluate("publish({rows: ['first']}); publish(null)")
        assert page.evaluate("outputs") == [
            {"output": "rows", "value": {"rows": ["first"]}},
            {"output": "rows", "value": None},
        ]
        assert page.evaluate("loadUnowned()") == (
            "loadDeferred(missing) needs a source value Leaf delivered"
        )
        assert page.evaluate("!document.documentElement.lfRootState")
