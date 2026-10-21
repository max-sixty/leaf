/* A Solid view tracks the fields it draws while preserving native editing state. */
import assert from "node:assert/strict";
import test from "node:test";
import { createView, solidHtml } from "/vendor/browser-runtime.js";

test("updating one field leaves an independent binding and native editor alone", () => {
  const host = document.createElement("section");
  document.body.append(host);
  let labelReads = 0;
  const view = createView(
    host,
    (props) => solidHtml`
    <label>${() => {
      labelReads++;
      return props().label;
    }}<input /></label>
    <output>${() => props().count}</output>`,
    { label: "Notes", count: 0 },
  );
  const input = host.querySelector("input");
  input.value = "An unfinished sentence";
  input.focus();
  input.setSelectionRange(3, 13);
  view.update({ label: "Notes", count: 1 });
  assert.equal(host.querySelector("output").textContent, "1");
  assert.equal(labelReads, 1);
  assert.equal(host.querySelector("input"), input);
  assert.equal(document.activeElement, input);
  assert.equal(input.value, "An unfinished sentence");
  assert.deepEqual([input.selectionStart, input.selectionEnd], [3, 13]);
  view.dispose();
  host.remove();
});
