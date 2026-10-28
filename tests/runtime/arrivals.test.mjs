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

const { whileConnected, frameFor } = await import("/runtime/arrivals.js");
const { clockValue, tickClock } = await import("/runtime/presence.js");
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

// A revision evicts a replaced widget before its replacement connects, in one batch.
// A registration only one element may hold passes from the first to the second.
test("an owner replaced within one batch releases before its replacement starts", async () => {
  const held = [];
  const hold = (owner) =>
    whileConnected(owner, () => {
      if (held.length) throw new Error("already held");
      held.push(owner);
      return () => held.splice(held.indexOf(owner), 1);
    });
  const outgoing = document.createElement("section");
  const arriving = document.createElement("section");
  document.body.append(outgoing);
  const stops = [hold(outgoing)];
  try {
    await mutate(() => {
      outgoing.remove();
      document.body.append(arriving);
      stops.push(hold(arriving));
    });
    assert.deepEqual(held, [arriving]);
    // A returning owner arrives through the batch, which still releases first.
    await mutate(() => arriving.remove());
    assert.deepEqual(held, []);
    await mutate(() => document.body.append(outgoing));
    assert.deepEqual(held, [outgoing]);
    await mutate(() => outgoing.replaceWith(arriving));
    assert.deepEqual(held, [arriving]);
  } finally {
    for (const stop of stops) stop();
    outgoing.remove();
    arriving.remove();
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

test("a clock render reports its failure once and recovers on the next reading", async () => {
  const { reportCarried } = await import("/runtime/layer-client.js");
  const { LeafElement, html } = await import("/runtime/widget-api.js");
  const { setPresentationFailureReporter } = await import("/runtime/semantic-state.js");
  setPresentationFailureReporter(reportCarried);
  let clock = 0;
  customElements.define(
    "leaf-clocked",
    class extends LeafElement {
      render() {
        if (clockValue(() => clock) === 1) throw new Error("clock refused");
        return html`Ready`;
      }
    },
  );
  const owner = document.createElement("leaf-clocked");
  owner.id = "clocked";
  const settle = async () => {
    await new Promise((resolve) => setTimeout(resolve));
    await owner.updateComplete;
  };
  document.body.append(owner);
  const reports = [];
  const consoleError = console.error;
  console.error = (line) => reports.push(line.split("\n")[0]);
  try {
    await settle();
    clock = 1;
    await tickClock(reportCarried);
    await settle();
    assert.equal(reports.length, 1, JSON.stringify(reports));
    assert.match(reports[0], /clock refused/);
    assert.match(owner.textContent, /failed: clock refused/);
    clock = 2;
    await tickClock(reportCarried);
    await settle();
    assert.equal(owner.textContent, "Ready");
    assert.equal(reports.length, 1);
  } finally {
    console.error = consoleError;
    owner.remove();
  }
});
