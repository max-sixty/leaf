import assert from "node:assert/strict";
import test from "node:test";
import { createRef, html, ref, render, repeat } from "/runtime/framework.js";

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

test("removing repeated chrome rows does not leave accumulating markers", () => {
  const host = document.createElement("div");
  document.body.append(host);
  try {
    const draw = (items) =>
      render(
        html`${repeat(
          items,
          (item) => item,
          (item) => html`<span>${item}</span>`,
        )}`,
        host,
      );
    draw(["first", "second"]);
    draw([]);
    const emptySize = host.childNodes.length;
    for (let index = 0; index < 20; index += 1) {
      draw(["first", "second"]);
      draw([]);
    }
    assert.equal(host.childNodes.length, emptySize);
  } finally {
    host.remove();
  }
});
