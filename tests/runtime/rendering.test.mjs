/* The settled reading's fold: which rendering updates leave the page settled.

   A rendering update here is the browser's order written out: the animation-frame
   callbacks queued before it run, then the size observers deliver, then the tasks those
   callbacks queued run. The reading's own check is one of those tasks. */

import assert from "node:assert/strict";
import test from "node:test";

const queued = new Map();
let nextId = 1;
globalThis.requestAnimationFrame = (callback) => {
  queued.set(nextId, callback);
  return nextId++;
};
globalThis.cancelAnimationFrame = (id) => queued.delete(id);
globalThis.ResizeObserver = class {
  constructor(callback) {
    this.callback = callback;
  }
  observe() {}
  disconnect() {}
};

const { nextRender, cancelRender, sizeObserver, renderingSettled } =
  await import("/runtime/rendering.js");

async function update({ delivering = [] } = {}) {
  const due = [...queued.values()];
  queued.clear();
  for (const callback of due) callback(0);
  for (const observer of delivering) observer.callback([], observer);
  await new Promise((resolve) => setTimeout(resolve, 0));
}

test("a page starts unsettled and settles on its first quiet update", async () => {
  assert.equal(renderingSettled(), false);
  await update();
  assert.equal(renderingSettled(), true);
});

test("queued work unsettles at once and settles with the update that runs it", async () => {
  let ran = false;
  nextRender(() => (ran = true));
  assert.equal(renderingSettled(), false);
  await update();
  assert.equal(ran, true);
  assert.equal(renderingSettled(), true);
});

test("work a callback queues for the next update holds the reading open", async () => {
  nextRender(() => nextRender(() => {}));
  await update();
  assert.equal(renderingSettled(), false);
  await update();
  assert.equal(renderingSettled(), true);
});

test("an observer delivery after the callbacks holds the reading for one more update", async () => {
  const observer = sizeObserver(() => {});
  nextRender(() => {});
  await update({ delivering: [observer] });
  assert.equal(renderingSettled(), false);
  await update();
  assert.equal(renderingSettled(), true);
});

test("cancelled work stops holding the reading", async () => {
  let ran = false;
  const id = nextRender(() => (ran = true));
  cancelRender(id);
  await update();
  assert.equal(ran, false);
  assert.equal(renderingSettled(), true);
});

test("a hidden page reads settled while work waits for an update it will not get", () => {
  nextRender(() => {});
  assert.equal(renderingSettled(), false);
  Object.defineProperty(document, "hidden", { value: true, configurable: true });
  try {
    assert.equal(renderingSettled(), true);
  } finally {
    delete document.hidden;
  }
});
