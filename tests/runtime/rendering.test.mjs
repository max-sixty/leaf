/* The rendering loop and the settled reading: which update runs a callback, and which
   updates leave the page settled.

   A rendering update here is the browser's order written out: the animation-frame
   callbacks queued before it run, each followed by the microtasks it queued, then the
   size observers deliver, then the tasks those callbacks queued run. The reading's own
   check is one of those tasks. */

import assert from "node:assert/strict";
import test from "node:test";

const queued = new Map();
let nextId = 1;
globalThis.requestAnimationFrame = (callback) => {
  queued.set(nextId, callback);
  return nextId++;
};
globalThis.cancelAnimationFrame = (id) => queued.delete(id);
const reported = [];
globalThis.reportError = (error) => reported.push(error);
globalThis.ResizeObserver = class {
  constructor(callback) {
    this.callback = callback;
  }
  observe() {}
  disconnect() {}
};

const { nextRender, nextFrame, cancelRender, sizeObserver, renderingSettled } =
  await import("/runtime/rendering.js");

async function update({ delivering = [] } = {}) {
  const due = [...queued.values()];
  queued.clear();
  // Awaiting a callback stands for the microtask checkpoint after it.
  for (const callback of due) await callback(0);
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

test("work a callback queues runs before the same update paints", async () => {
  const ran = [];
  nextRender(() => {
    ran.push("repaint");
    nextRender(() => ran.push("follower"));
  });
  nextRender(() => ran.push("other owner"));
  await update();
  assert.deepEqual(ran, ["repaint", "other owner", "follower"]);
  assert.equal(renderingSettled(), true);
});

test("a step that asks for the next frame waits for it and holds the reading open", async () => {
  const ran = [];
  nextRender(() => nextFrame(() => ran.push("tick")));
  await update();
  assert.deepEqual(ran, []);
  assert.equal(renderingSettled(), false);
  await update();
  assert.deepEqual(ran, ["tick"]);
  assert.equal(renderingSettled(), true);
});

test("the next frame asked for outside a pass is the one about to paint", async () => {
  let ran = false;
  nextFrame(() => (ran = true));
  await update();
  assert.equal(ran, true);
});

test("a chain that keeps asking finishes on the next frame", async () => {
  let runs = 0;
  const again = () => {
    runs += 1;
    if (runs < 20) nextRender(again);
  };
  nextRender(again);
  await update();
  assert.ok(runs > 1 && runs < 20, `ran ${runs} times in one update`);
  await update();
  await update();
  assert.equal(runs, 20);
});

test("each callback reads what the microtasks before it did", async () => {
  let published = false;
  let seen = null;
  nextRender(() => queueMicrotask(() => (published = true)));
  nextRender(() => (seen = published));
  await update();
  assert.equal(seen, true);
});

test("a callback cancelled by an earlier one in the same pass does not run", async () => {
  let ran = false;
  nextRender(() => cancelRender(later));
  const later = nextRender(() => (ran = true));
  await update();
  assert.equal(ran, false);
});

test("a failing callback is reported and the rest still run", async () => {
  const failure = new Error("one owner broke");
  let ran = false;
  nextRender(() => {
    throw failure;
  });
  nextRender(() => (ran = true));
  await update();
  assert.equal(ran, true);
  assert.deepEqual(reported.splice(0), [failure]);
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
