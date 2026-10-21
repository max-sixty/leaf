/* A Solid view tracks the fields it draws while preserving native editing state. */
import assert from "node:assert/strict";
import test from "node:test";
import { createView, solidHtml, For } from "/vendor/browser-runtime.js";

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

test("reordering keyed records preserves each row's kind and native editor", () => {
  const host = document.createElement("section");
  document.body.append(host);
  const row = { key: "command", kind: "entry", entry: { label: "Run" } };
  const heading = { key: "heading", kind: "heading", title: "Commands" };
  const view = createView(
    host,
    (read) =>
      For({
        get each() {
          return read().items;
        },
        keyed: (item) => item.key,
        children: (item) =>
          item().kind === "entry"
            ? solidHtml`<label>${() => item().entry.label}<input /></label>`
            : solidHtml`<h2>${() => item().title}</h2>`,
      }),
    { items: [row, heading] },
  );
  const input = host.querySelector("input");
  input.value = "Unfinished";
  input.focus();
  input.setSelectionRange(2, 6);
  view.update({
    items: [
      { ...heading, title: "Available" },
      { ...row, entry: { label: "Execute" } },
    ],
  });
  assert.equal(host.firstElementChild.tagName, "H2");
  assert.equal(host.firstElementChild.textContent, "Available");
  assert.equal(host.querySelector("label").textContent, "Execute");
  assert.equal(host.querySelector("input"), input);
  assert.equal(document.activeElement, input);
  assert.equal(input.value, "Unfinished");
  assert.deepEqual([input.selectionStart, input.selectionEnd], [2, 6]);
  view.dispose();
  host.remove();
});
