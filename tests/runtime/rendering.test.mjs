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

const {
  nextRender,
  nextFrame,
  cancelRender,
  afterScript,
  sizeObserver,
  renderingState,
  holdRendering,
  observePreparations,
} = await import("/runtime/rendering.js");

const { observeQueuedWork } = await import("/runtime/queued-work.js");

async function update({ delivering = [] } = {}) {
  const due = [...queued.values()];
  queued.clear();
  // Awaiting a callback stands for the microtask checkpoint after it.
  for (const callback of due) await callback(0);
  for (const observer of delivering) observer.callback([], observer);
  await new Promise((resolve) => setTimeout(resolve, 0));
}

test("a page starts unsettled and settles on its first quiet update", async () => {
  assert.equal(Object.values(renderingState()).every(Boolean), false);
  await update();
  assert.equal(Object.values(renderingState()).every(Boolean), true);
});

test("queued work unsettles at once and settles with the update that runs it", async () => {
  let ran = false;
  nextRender(() => (ran = true));
  assert.equal(Object.values(renderingState()).every(Boolean), false);
  await update();
  assert.equal(ran, true);
  assert.equal(Object.values(renderingState()).every(Boolean), true);
});

test("finite preparation retires once and owes its final quiet update", async () => {
  const first = holdRendering();
  const second = holdRendering();
  assert.equal(renderingState().updatesSettled, false);
  for (let i = 0; i < 10; i++) await update();
  assert.deepEqual(
    renderingState(),
    { updatesSettled: true, preparationsSettled: false },
    "the counted queue rests while preparation waits",
  );
  assert.equal(queued.size, 0, "a pending preparation does not poll frames");

  let painted = false;
  nextRender(() => (painted = true));
  assert.equal(renderingState().updatesSettled, false);
  const observer = sizeObserver(() => {});
  await update({ delivering: [observer] });
  assert.equal(painted, true);
  assert.deepEqual(
    renderingState(),
    { updatesSettled: false, preparationsSettled: false },
    "the observer still owes a quiet update",
  );
  await update();
  assert.deepEqual(
    renderingState(),
    { updatesSettled: true, preparationsSettled: false },
    "queue quietness does not retire preparation",
  );

  first();
  first();
  await update();
  assert.equal(
    Object.values(renderingState()).every(Boolean),
    false,
    "another preparation still stands",
  );
  second();
  assert.deepEqual(
    renderingState(),
    { updatesSettled: false, preparationsSettled: true },
    "the preparation's commit owes a quiet update",
  );
  await update();
  assert.deepEqual(renderingState(), {
    updatesSettled: true,
    preparationsSettled: true,
  });
});

test("preparation observers follow one hold through exactly one terminal", async () => {
  const first = [];
  const stopFirst = observePreparations((...event) => first.push(event));
  const cancel = holdRendering();
  stopFirst();
  const second = [];
  const stopSecond = observePreparations((...event) => second.push(event));
  cancel("cancel");
  cancel();
  const settle = holdRendering();
  settle();
  settle("cancel");
  stopSecond();
  assert.deepEqual(
    first.map(([phase]) => phase),
    ["begin", "cancel"],
  );
  assert.deepEqual(
    second.map(([phase]) => phase),
    ["begin", "settle"],
  );
  assert.equal(first[0][1], first[1][1]);
  assert.equal(second[0][1], second[1][1]);
  assert.notEqual(first[0][1], second[0][1]);
  assert.ok(Object.isFrozen(first[0][1]));
  assert.ok(Object.isFrozen(second[0][1]));
  await update();
  assert.equal(Object.values(renderingState()).every(Boolean), true);
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
  assert.equal(Object.values(renderingState()).every(Boolean), true);
});

test("a step that asks for the next frame waits for it and holds the reading open", async () => {
  const ran = [];
  nextRender(() => nextFrame(() => ran.push("tick")));
  await update();
  assert.deepEqual(ran, []);
  assert.equal(Object.values(renderingState()).every(Boolean), false);
  await update();
  assert.deepEqual(ran, ["tick"]);
  assert.equal(Object.values(renderingState()).every(Boolean), true);
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

test("a rendering turn drains direct publication before the next callback, not a deeper tail", async () => {
  const seen = [];
  let state = "before";
  nextRender(() =>
    queueMicrotask(() => {
      state = "published";
      queueMicrotask(() => {
        state = "tail";
      });
    }),
  );
  nextRender(() => seen.push(state));
  await update();
  assert.deepEqual(seen, ["published"]);
  assert.equal(state, "tail");
});

test("job observation follows an enqueued cohort through cancellation and failure", async () => {
  const events = [];
  const phases = new Map();
  const stop = observeQueuedWork((phase, job) => {
    assert.equal(Object.isFrozen(job), true);
    const heard = phases.get(job) ?? [];
    heard.push(phase);
    phases.set(job, heard);
    events.push([phase, job.callback]);
  });
  const cancelled = () => assert.fail("cancelled work ran");
  const failure = new Error("observed callback failure");
  const broken = () => {
    throw failure;
  };
  const id = nextRender(cancelled);
  nextRender(broken);
  stop();
  cancelRender(id);
  nextRender(() => {});
  await update();
  assert.deepEqual(
    [...phases.values()],
    [
      ["enqueue", "cancel"],
      ["enqueue", "run", "finish"],
    ],
  );
  assert.deepEqual(
    events.map(([phase, callback]) => [
      phase,
      callback === cancelled ? "cancelled" : "broken",
    ]),
    [
      ["enqueue", "cancelled"],
      ["enqueue", "broken"],
      ["cancel", "cancelled"],
      ["run", "broken"],
      ["finish", "broken"],
    ],
  );
  assert.deepEqual(reported.splice(0), [failure]);
});

test("afterScript observes one coalesced job and jobs its callback appends", async () => {
  const events = [];
  const stop = observeQueuedWork((phase, job) => events.push([phase, job.callback]));
  const appended = () => {};
  const first = () => afterScript(appended);
  afterScript(first);
  afterScript(first);
  await Promise.resolve();
  stop();
  assert.deepEqual(events, [
    ["enqueue", first],
    ["run", first],
    ["enqueue", appended],
    ["finish", first],
    ["run", appended],
    ["finish", appended],
  ]);
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
  assert.equal(Object.values(renderingState()).every(Boolean), false);
  await update();
  assert.equal(Object.values(renderingState()).every(Boolean), true);
});

test("cancelled work stops holding the reading", async () => {
  let ran = false;
  const id = nextRender(() => (ran = true));
  cancelRender(id);
  await update();
  assert.equal(ran, false);
  assert.equal(Object.values(renderingState()).every(Boolean), true);
});

test("a hidden page reads settled while work waits for an update it will not get", () => {
  nextRender(() => {});
  assert.equal(Object.values(renderingState()).every(Boolean), false);
  Object.defineProperty(document, "hidden", { value: true, configurable: true });
  try {
    assert.equal(Object.values(renderingState()).every(Boolean), true);
  } finally {
    delete document.hidden;
  }
});
