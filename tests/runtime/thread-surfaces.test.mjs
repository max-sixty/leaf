import assert from "node:assert/strict";
import test from "node:test";

import { adoptRegistry } from "/runtime/registry.js";
import { bindVocabulary, rememberVocabulary } from "/runtime/widget-contexts.js";
import { watchThreadSurfaces, threadSurface } from "/runtime/thread/surfaces.js";

test("surface arrivals read their publication and never wait for a failed upgrade", async () => {
  // A failed upgrade leaves the element undefined while its definition stands, so a
  // watch that waited for the definition would re-offer the element on every
  // resolution and spin forever. Waits are counted, and capped so that spin fails here
  // rather than starving the event loop.
  adoptRegistry({
    "lf-broken-surface": { "x-thread-surface": true },
    "lf-later-surface": { "x-thread-surface": false },
  });
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
    let invalidations = 0;
    watchThreadSurfaces({
      invalidate() {
        invalidations++;
      },
      composition: {
        outlet() {
          return null;
        },
      },
      reveal() {},
    });
    for (let turn = 0; turn < 5; turn++)
      await new Promise((resolve) => setTimeout(resolve, 0));
    assert.equal(widget.matches(":defined"), false);
    assert.equal(waits, 0);
    // These constructors are known to have succeeded. Happy DOM does not supply
    // :defined, so provide only that platform reading at this owner boundary.
    const arrival = (tag, context) => {
      customElements.define(tag, class extends HTMLElement {});
      const node = document.createElement(tag);
      const matches = node.matches.bind(node);
      node.matches = (selector) => selector === ":defined" || matches(selector);
      bindVocabulary(node, context);
      document.body.append(node);
      return node;
    };
    // The later publication introduces a capability absent from startup, both
    // under a new tag and under a tag the initial publication does not seat.
    const later = {
      revision: 2,
      declarations: {
        "lf-new-surface": { "x-thread-surface": true },
        "lf-later-surface": { "x-thread-surface": true },
      },
    };
    rememberVocabulary(later);
    const fresh = arrival("lf-new-surface", later);
    const changed = arrival("lf-later-surface", later);
    for (let turn = 0; turn < 5; turn++)
      await new Promise((resolve) => setTimeout(resolve, 0));
    assert.equal(invalidations, 2);
    threadSurface(changed).update();
    await Promise.resolve();
    assert.equal(invalidations, 3);
    fresh.remove();
    changed.remove();
    widget.remove();
  } finally {
    customElements.whenDefined = real;
  }
});
