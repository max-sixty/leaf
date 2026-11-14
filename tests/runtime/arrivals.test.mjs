/* Owner lifetimes retain resources across moves, release them on departure, and
   keep deferred rendering from outliving the element it paints. Real DOM mutations
   drive arrival delivery; only rendering frames are advanced explicitly. */
import assert from "node:assert/strict";
import test from "node:test";
import { setFlagsFromString } from "node:v8";
import { runInNewContext } from "node:vm";

const frames = new Map();
let nextFrame = 0;
globalThis.requestAnimationFrame = (callback) => {
  frames.set(++nextFrame, callback);
  return nextFrame;
};
globalThis.cancelAnimationFrame = (id) => frames.delete(id);

const {
  watchOwner,
  watchArrivalsIn,
  whileConnected,
  frameFor,
  browserScrolls,
  holdScroll,
  readerScrolls,
  scrolling,
  setScroll,
  startReaderScroll,
  stopWhereItStands,
  watchScrollEnds,
} = await import("/runtime/arrivals.js");
const { clockValue, tickClock } = await import("/runtime/presence.js");
const { observeQueuedWork } = await import("/runtime/queued-work.js");

// A second observer acknowledges delivery of the same mutation batch as arrivals, in
// the tree the change is made in.
async function mutate(change, tree = document.body) {
  const observed = new Promise((resolve) => {
    const observer = new MutationObserver(() => {
      observer.disconnect();
      resolve();
    });
    observer.observe(tree, { childList: true, subtree: true });
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

// First in the file, so its owner is the first the shared watch serves.
test("the first owner the shared watch serves is collected once it leaves", async () => {
  setFlagsFromString("--expose-gc");
  const collect = runInNewContext("gc");
  const ref = (() => {
    const owner = document.createElement("section");
    document.body.append(owner);
    whileConnected(owner, () => {});
    owner.remove();
    return new WeakRef(owner);
  })();
  for (let turn = 0; turn < 12 && ref.deref(); turn++) {
    await new Promise((resolve) => setTimeout(resolve));
    collect();
  }
  assert.equal(ref.deref(), undefined);
});

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

// An owner arrives inside what a change adds, not only as the added node itself: a
// widget inside a section a revision patches in, or inside a shadow stage's content.
/** @param {Element} owner */
function connections(owner) {
  /** @type {string[]} */
  const log = [];
  const stop = watchOwner(owner, {
    connect: () => log.push("connect"),
    disconnect: () => log.push("disconnect"),
  });
  return { log, stop };
}

test("an owner inside an added subtree connects, leaves with it and returns with it", async () => {
  const section = document.createElement("section");
  const paragraph = document.createElement("p");
  const owner = document.createElement("span");
  paragraph.append(owner);
  section.append(paragraph);
  const { log, stop } = connections(owner);
  try {
    assert.deepEqual(log, []);
    await mutate(() => document.body.append(section));
    assert.deepEqual(log, ["connect"]);
    await mutate(() => section.remove());
    assert.deepEqual(log, ["connect", "disconnect"]);
    await mutate(() => document.body.append(section));
    assert.deepEqual(log, ["connect", "disconnect", "connect"]);
  } finally {
    stop();
    section.remove();
  }
});

test("an owner inside a shadow stage connects, leaves with its host and returns with it", async () => {
  const outer = document.createElement("div");
  const host = document.createElement("div");
  outer.append(host);
  document.body.append(outer);
  const stage = host.attachShadow({ mode: "open" });
  watchArrivalsIn(stage);
  const content = document.createElement("div");
  const owner = document.createElement("span");
  content.append(owner);
  const { log, stop } = connections(owner);
  try {
    await mutate(() => stage.append(content), stage);
    assert.deepEqual(log, ["connect"]);
    await mutate(() => outer.remove());
    assert.deepEqual(log, ["connect", "disconnect"]);
    await mutate(() => document.body.append(outer));
    assert.deepEqual(log, ["connect", "disconnect", "connect"]);
  } finally {
    stop();
    outer.remove();
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
  const { LeafElement } = await import("/runtime/widget-api.js");
  const { html } = await import("/vendor/lit.js");
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

test("a scroll a script holds ends once, after its release, and stays the script's until the box moves on", async () => {
  const box = document.createElement("div");
  document.body.append(box);
  let at = 0;
  Object.defineProperties(box, {
    clientHeight: { value: 100 },
    scrollHeight: { value: 400 },
    clientWidth: { value: 100 },
    scrollWidth: { value: 100 },
    scrollLeft: { value: 0 },
    scrollTop: {
      get: () => at,
      set: (/** @type {number} */ to) => {
        at = to;
      },
    },
    scrollTo: {
      value: (/** @type {ScrollToOptions} */ { top = at }) => {
        at = Math.min(Math.max(top, 0), 300);
      },
    },
  });
  /** @type {Element[]} */
  const ended = [];
  const stop = watchScrollEnds((end) => ended.push(end));
  const send = () => {
    box.dispatchEvent(new window.Event("scroll"));
    box.dispatchEvent(new window.Event("scrollend"));
  };
  /** @param {number} top */
  const frame = (top) => {
    setScroll(box, { top });
    send();
  };
  try {
    const release = holdScroll(box);
    frame(10);
    await renderFrame();
    frame(20);
    await renderFrame();
    assert.deepEqual(ended, []);
    assert.equal(scrolling(), true);
    release();
    assert.equal(
      browserScrolls(box),
      false,
      "the released scroll's last frame read as the browser moving the box",
    );
    send();
    await renderFrame();
    assert.deepEqual(ended, [box]);
    assert.equal(scrolling(), false);
    // A scroll that takes the box from where the script left it is the browser's.
    box.scrollTop = 30;
    box.dispatchEvent(new window.Event("scroll"));
    assert.equal(browserScrolls(box), true);
    box.dispatchEvent(new window.Event("scrollend"));
  } finally {
    stop();
    box.remove();
  }
});

test("an instant write reaches a box only where it moves it, and a stop writes where it stands", () => {
  /** @param {number} low @param {number} high @param {number} at */
  const scroller = (low, high, at) => {
    const box = document.createElement("div");
    document.body.append(box);
    /** @type {number[]} */
    const writes = [];
    let top = at;
    Object.defineProperties(box, {
      clientHeight: { value: 100 },
      scrollHeight: { value: 100 + high - low },
      clientWidth: { value: 100 },
      scrollWidth: { value: 100 },
      scrollLeft: { value: 0 },
      scrollTop: { get: () => top },
      scrollTo: {
        value: (/** @type {ScrollToOptions} */ { top: to = top }) => {
          writes.push(to);
          top = Math.min(Math.max(to, low), high);
        },
      },
    });
    return { box, writes };
  };
  // At its end, a box takes no write that would leave it there, clamped or a pixel short.
  const ended = scroller(0, 300, 300);
  setScroll(ended.box, { top: 300.4 });
  setScroll(ended.box, { top: 1000 });
  assert.deepEqual(ended.writes, []);
  setScroll(ended.box, { top: 250 });
  assert.deepEqual(ended.writes, [250]);
  ended.box.remove();
  // Off zero, the side the box stands on is the side it scrolls on.
  const reversed = scroller(-300, 0, -300);
  setScroll(reversed.box, { top: -1000 });
  setScroll(reversed.box, { top: 0 });
  assert.deepEqual(reversed.writes, [0]);
  reversed.box.remove();
  // While the browser drives a scroll in the box, a restated position still writes
  // nothing, and only a stop writes where the box stands, smoothly and then at once,
  // which leaves it the script's.
  const moving = scroller(0, 300, 120);
  moving.box.dispatchEvent(new window.Event("scroll"));
  assert.equal(browserScrolls(moving.box), true);
  assert.equal(readerScrolls(moving.box), false);
  setScroll(moving.box, { top: moving.box.scrollTop });
  assert.deepEqual(moving.writes, []);
  stopWhereItStands(moving.box);
  assert.deepEqual(moving.writes, [120, 120]);
  assert.equal(browserScrolls(moving.box), false);
  moving.box.dispatchEvent(new window.Event("scrollend"));
  // The reader's input makes the box the browser's, and the reader's, before it moves,
  // and the end of a scroll heard while it still stands where the input found it ends
  // nothing of theirs.
  startReaderScroll(moving.box);
  assert.equal(browserScrolls(moving.box), true);
  assert.equal(readerScrolls(moving.box), true);
  moving.box.dispatchEvent(new window.Event("scrollend"));
  assert.equal(browserScrolls(moving.box), true);
  assert.equal(readerScrolls(moving.box), true);
  moving.box.scrollTo({ top: 60 });
  moving.box.dispatchEvent(new window.Event("scrollend"));
  assert.equal(browserScrolls(moving.box), false);
  assert.equal(readerScrolls(moving.box), false);
  // Where the browser applied the input's scroll before the input was heard, as
  // Chromium can a wheel's, the input found the box where the page last heard it, so
  // the end of that scroll ends the reader's sequence.
  moving.box.dispatchEvent(new window.Event("scroll"));
  moving.box.dispatchEvent(new window.Event("scrollend"));
  moving.box.scrollTo({ top: 200 });
  startReaderScroll(moving.box);
  assert.equal(browserScrolls(moving.box), true);
  moving.box.dispatchEvent(new window.Event("scrollend"));
  assert.equal(browserScrolls(moving.box), false);
  moving.box.remove();
});
