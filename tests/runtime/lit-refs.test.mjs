import assert from "node:assert/strict";
import test from "node:test";
import { createRef, html, ref, render } from "/vendor/browser-runtime.js";

test("an optional template ref survives disconnection and reconnecting", () => {
  const host = document.createElement("div");
  const part = render(html`<span ${ref(undefined)}>Optional ref</span>`, host);
  part.setConnected(false);
  part.setConnected(true);
  render(html`<p>Replaced</p>`, host);
  assert.equal(host.textContent, "Replaced");
});

test("template refs clear across optional values and restore on reconnect", () => {
  const host = document.createElement("div");
  const reference = createRef();
  const calls = [];
  const callback = (element) => calls.push(element);
  const paint = (value) => render(html`<span ${ref(value)}>Ref</span>`, host);
  const part = paint(reference);
  const element = host.firstElementChild;
  assert.equal(reference.value, element);
  paint(undefined);
  assert.equal(reference.value, undefined);
  paint(callback);
  assert.deepEqual(calls, [element]);
  part.setConnected(false);
  assert.deepEqual(calls, [element, undefined]);
  part.setConnected(true);
  assert.deepEqual(calls, [element, undefined, element]);
  paint(undefined);
  assert.deepEqual(calls, [element, undefined, element, undefined]);
});
