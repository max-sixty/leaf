import assert from "node:assert/strict";
import test from "node:test";

import { adoptRegistry } from "/runtime/registry.js";
import { watchThreadSurfaces } from "/runtime/thread/surfaces.js";

test("a surface widget whose constructor threw is not waited for", async () => {
  // A failed upgrade leaves the element undefined while its definition stands, so a
  // watch that waited for the definition would re-offer the element on every
  // resolution and spin forever. Waits are counted, and capped so that spin fails here
  // rather than starving the event loop.
  adoptRegistry({ "lf-broken-surface": { "x-thread-surface": true } });
  const real = customElements.whenDefined.bind(customElements);
  let waits = 0;
  customElements.whenDefined = (name) =>
    ++waits > 20 ? new Promise(() => {}) : real(name);
  try {
    const widget = document.createElement("lf-broken-surface");
    document.body.append(widget);
    try {
      customElements.define(
        "lf-broken-surface",
        class extends HTMLElement {
          constructor() {
            super();
            throw new Error("surface constructor failed");
          }
        },
      );
    } catch {
      // A browser reports the failed upgrade rather than throwing from define.
    }
    watchThreadSurfaces({ invalidate() {}, composition: {}, reveal() {} });
    for (let turn = 0; turn < 5; turn++)
      await new Promise((resolve) => setTimeout(resolve, 0));
    assert.equal(widget.matches(":defined"), false);
    assert.equal(waits, 0);
    widget.remove();
  } finally {
    customElements.whenDefined = real;
  }
});
