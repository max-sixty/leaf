/* Applying the server's reading against the frames the page owes.

   The real semantic publisher and rendering loop run under a controlled frame clock:
   a frame runs only when the test runs the callbacks the page asked the browser for. */
import assert from "node:assert/strict";
import { setImmediate } from "node:timers/promises";
import test from "node:test";
import { servedState } from "../served.mjs";

/** @type {FrameRequestCallback[]} */
let asked = [];
globalThis.requestAnimationFrame = (callback) => asked.push(callback);
globalThis.cancelAnimationFrame = () => {};
// One rendering update: the frame callbacks asked for, then the tasks they queued.
async function frame() {
  const due = asked;
  asked = [];
  for (const callback of due) await callback(0);
  await new Promise((resolve) => setTimeout(resolve, 0));
}

const { applicationState } = await import("/runtime/semantic-state.js");
const { nextRender } = await import("/runtime/rendering.js");
const { createStateApplication } = await import("/runtime/state-application.js");

applicationState.identify(1);
applicationState.captureDocument({
  ...applicationState.read().document,
  registry: {},
  authored: new Map(),
  descriptors: new Map(),
});
const application = createStateApplication({
  prepareActivation: async () => null,
  acceptData: () => false,
  notifyDataSubscribers: () => {},
  accountPending: () => {},
});
let taken = 0;
// A reading from the layer this page was served with, which declares none here.
const reading = () => {
  const state = servedState({ taken: ++taken });
  state.layer.generation = undefined;
  return state;
};
// Whether the page has adopted its latest reading.
const adopted = () => applicationState.read().authoritative?.taken === taken;
// Let a reading's preparation and every task it queues run, but no frame.
const settle = async () => {
  for (let step = 0; step < 5; step++) await setImmediate();
};

// After a long gesture task the browser may run an arriving reading before the frame
// that paints what the gesture drew; the reading waits for that frame instead
// (rendering.js, `afterOwedFrame`).
test("a reading arriving while a gesture's frame is owed is adopted after that frame", async () => {
  applicationState.enqueue(
    { kind: "comment", attempt: "sent", text: "Keep my words", revision: 1 },
    "now",
  );
  nextRender(() => {});
  void application.receiveState(reading());
  await settle();
  assert.equal(adopted(), false);
  await frame();
  await settle();
  assert.equal(adopted(), true);
  applicationState.refuse("sent");
  applicationState.release(new Set(["sent"]));
  while (asked.length) await frame();
});

// With no gesture in flight nothing on screen is owed first, so a reading is adopted
// as it arrives, as while the page loads.
test("a reading with no gesture in flight is adopted without waiting for a frame", async () => {
  assert.deepEqual(applicationState.read().unresolved, []);
  nextRender(() => {});
  void application.receiveState(reading());
  await settle();
  assert.equal(adopted(), true);
  while (asked.length) await frame();
});
