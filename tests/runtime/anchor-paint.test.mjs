/* Focus contours follow the obligation reading before its DOM paint catches up. */
import assert from "node:assert/strict";
import test from "node:test";
import { createAnchorPaint } from "/runtime/annotation-overlay/anchor-paint.js";

test("an obligation's own focus cue does not depend on a previous paint", () => {
  const active = document.createElement("textarea");
  active.id = "question";
  document.body.append(active);
  active.focus();
  let obligation = active;
  let targets;
  globalThis.Highlight ??= class {
    constructor() {}
  };
  Object.defineProperty(globalThis, "CSS", {
    configurable: true,
    value: { ...CSS, highlights: new Map() },
  });
  const painter = createAnchorPaint({
    targetPaint: {
      setTargets: (next) => {
        targets = next;
      },
    },
    pointer: () => ({ x: 0, y: 0 }),
    currentLocationThreadId: () => null,
    currentLocationObligation: () => obligation,
    rowThread: () => null,
    threadRow: () => null,
    marginThread: () => null,
  });
  try {
    painter.paintCurrentLocation();
    assert.deepEqual(targets, []);
    active.setAttribute("data-lf-obligation", "1");
    painter.paintCurrentLocation();
    assert.deepEqual(targets, []);
    // Once the obligation releases the location, stale paint must not hide focus.
    obligation = null;
    painter.paintCurrentLocation();
    assert.equal(targets.length, 1);
    assert.equal(targets[0].element, active);
    assert.deepEqual([...targets[0].states], ["focus"]);
  } finally {
    painter.destroy();
    active.remove();
  }
});
