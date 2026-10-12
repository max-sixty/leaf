/* Owner lifetimes retain resources across moves, release them on departure, and
   keep deferred rendering from outliving the element it paints. Real DOM mutations
   drive arrival delivery; only rendering frames are advanced explicitly. */
import assert from "node:assert/strict";
import test from "node:test";

const frames = new Map();
let nextFrame = 0;
globalThis.requestAnimationFrame = (callback) => {
  frames.set(++nextFrame, callback);
  return nextFrame;
};
globalThis.cancelAnimationFrame = (id) => frames.delete(id);

const { whileConnected, frameFor, readingPaint } = await import("/runtime/arrivals.js");
const { observeQueuedWork } = await import("/runtime/queued-work.js");

// A second observer acknowledges delivery of the same mutation batch as arrivals.
async function mutate(change) {
  const observed = new Promise((resolve) => {
    const observer = new MutationObserver(() => {
      observer.disconnect();
      resolve();
    });
    observer.observe(document.body, { childList: true, subtree: true });
  });
  change();
  await observed;
}

async function renderFrame() {
  const due = [...frames.values()];
  frames.clear();
  // Invoke callbacks before yielding, including when departure delivery is pending.
  await Promise.all(due.map((callback) => callback(0)));
  await new Promise((resolve) => setTimeout(resolve, 0));
}

test("resources survive a move, release on departure, and restart with a fresh signal", async () => {
  const owner = document.createElement("section");
  const holder = document.createElement("div");
  document.body.append(holder);
  const signals = [];
  const released = [];
  let heard = 0;
  const stop = whileConnected(owner, (signal) => {
    signals.push(signal);
    document.addEventListener("owner-probe", () => heard++, { signal });
    return () => released.push(signal.aborted);
  });
  const send = () => document.dispatchEvent(new Event("owner-probe"));
  try {
    assert.equal(signals.length, 0);
    await mutate(() => holder.append(owner));
    send();
    assert.equal(heard, 1);
    await mutate(() => document.body.append(owner));
    assert.equal(signals.length, 1);
    assert.equal(signals[0].aborted, false);
    await mutate(() => owner.remove());
    send();
    assert.equal(heard, 1);
    assert.deepEqual(released, [true]);
    await mutate(() => holder.append(owner));
    assert.equal(signals.length, 2);
    assert.notEqual(signals[0], signals[1]);
    send();
    assert.equal(heard, 2);
    stop();
    stop();
    send();
    assert.equal(heard, 2);
    assert.deepEqual(released, [true, true]);
    await mutate(() => owner.remove());
    await mutate(() => holder.append(owner));
    assert.equal(signals.length, 2);
  } finally {
    stop();
    owner.remove();
    holder.remove();
  }
});

test("connected registration starts synchronously and may own only signal listeners", () => {
  const owner = document.createElement("section");
  document.body.append(owner);
  let signal;
  const stop = whileConnected(owner, (value) => {
    signal = value;
  });
  assert.equal(signal.aborted, false);
  stop();
  assert.equal(signal.aborted, true);
  owner.remove();
});

test("synchronous setup is released when its owner leaves before its first arrival", async () => {
  for (const leaveDuringSetup of [false, true]) {
    const owner = document.createElement("section");
    document.body.append(owner);
    let signal;
    let released = false;
    let stop;
    await mutate(() => {
      stop = whileConnected(owner, (value) => {
        signal = value;
        if (leaveDuringSetup) owner.remove();
        return () => (released = true);
      });
      if (!leaveDuringSetup) owner.remove();
    });
    assert.equal(signal.aborted, true);
    assert.equal(released, true);
    stop();
  }
});

test("failed setup aborts its listeners and permanently retires the subscription", async () => {
  const owner = document.createElement("section");
  document.body.append(owner);
  const failure = new Error("owner setup failed");
  let signal;
  let starts = 0;
  let heard = 0;
  assert.throws(
    () =>
      whileConnected(owner, (value) => {
        starts++;
        signal = value;
        document.addEventListener("failed-owner-probe", () => heard++, { signal });
        throw failure;
      }),
    (error) => error === failure,
  );
  assert.equal(signal.aborted, true);
  document.dispatchEvent(new Event("failed-owner-probe"));
  assert.equal(heard, 0);
  await mutate(() => owner.remove());
  await mutate(() => document.body.append(owner));
  assert.equal(starts, 1);
  owner.remove();
});

test("owner frames coalesce calls and keep pending work through a same-batch move", async () => {
  const owner = document.createElement("section");
  const holder = document.createElement("div");
  document.body.append(owner, holder);
  let paints = 0;
  const schedule = frameFor(owner, () => paints++);
  schedule();
  schedule();
  await mutate(() => holder.append(owner));
  schedule();
  await renderFrame();
  assert.equal(paints, 1);
  schedule();
  await renderFrame();
  assert.equal(paints, 2);
  owner.remove();
  holder.remove();
});

test("departure cancels queued rendering and reconnection accepts fresh work", async () => {
  const owner = document.createElement("section");
  document.body.append(owner);
  // Only this frame's own job: the runtime queues other work on any mutation, such as
  // focus.js refreshing its paint.
  const phases = [];
  const own = new Set();
  let scheduling = false;
  const stop = observeQueuedWork((phase, job) => {
    if (scheduling && phase === "enqueue") own.add(job);
    if (own.has(job)) phases.push(phase);
  });
  let paints = 0;
  const frame = frameFor(owner, () => paints++);
  const schedule = () => {
    scheduling = true;
    try {
      frame();
    } finally {
      scheduling = false;
    }
  };
  try {
    schedule();
    await mutate(() => owner.remove());
    assert.deepEqual(phases, ["enqueue", "cancel"]);
    schedule();
    assert.deepEqual(phases, ["enqueue", "cancel"]);
    await mutate(() => document.body.append(owner));
    await renderFrame();
    assert.equal(paints, 0);
    schedule();
    await renderFrame();
    assert.equal(paints, 1);
  } finally {
    stop();
    owner.remove();
  }
});

test("a frame refuses to paint after removal even before departure delivery", async () => {
  const owner = document.createElement("section");
  document.body.append(owner);
  let paints = 0;
  let departed = false;
  const stop = whileConnected(owner, () => () => (departed = true));
  const schedule = frameFor(owner, () => paints++);
  schedule();
  owner.remove();
  assert.equal(departed, false);
  await renderFrame();
  assert.equal(paints, 0);
  stop();
});

test("a returning owner draws a reading again only where its paint did not finish while it stood", async () => {
  const owner = document.createElement("section");
  await mutate(() => document.body.append(owner));
  const drawn = [];
  let finish;
  const paint = readingPaint(owner, (reading) => {
    drawn.push(reading);
    if (reading === "refused") throw new Error("refused");
    if (reading.startsWith("slow")) return new Promise((resolve) => (finish = resolve));
  });
  const leaveAndReturn = async () => {
    await mutate(() => owner.remove());
    await mutate(() => document.body.append(owner));
  };
  try {
    assert.throws(() => paint("refused", "refused"));
    await leaveAndReturn();
    paint("refused", "refused");
    // Left while the paint was running.
    paint("slow", "slow");
    await leaveAndReturn();
    paint("slow", "slow again");
    // Settled after the owner was removed, before its departure was delivered.
    finish();
    await mutate(() => owner.remove());
    await mutate(() => document.body.append(owner));
    paint("slow", "slow once more");
    finish();
    await Promise.resolve();
    await leaveAndReturn();
    paint("slow", "slow, finished");
    assert.deepEqual(drawn, ["refused", "slow", "slow again", "slow once more"]);
  } finally {
    paint.stop();
    owner.remove();
  }
});
