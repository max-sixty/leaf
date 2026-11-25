/* Applying the server's reading against the frames the page owes, and only as the page
   adopts it.

   The real semantic publisher and rendering loop run under a controlled frame clock:
   a frame runs only when the test runs the callbacks the page asked the browser for. */
import assert from "node:assert/strict";
import { setImmediate } from "node:timers/promises";
import test from "node:test";
import { servedState, servedThread } from "../served.mjs";

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

const { applicationState } = await import("/runtime/state/semantic-state.js");
const { nextRender } = await import("/runtime/lib/frame-pass.js");
const { createStateApplication } = await import("/runtime/host/state-application.js");

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
// (base/rendering.js, `afterOwedFrame`).
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

// A reading's messages bring their widgets only as the page adopts it. One the page
// refuses leaves no widget for a node to take up, as a renderer's replacement for a
// widget's node does, nor any element under the widget's id; one it adopts gives both.
test("a refused reading leaves its messages' widgets unfound, and an adopted one finds them", async () => {
  const { adoptRegistry } = await import("/runtime/state/registry.js");
  const { widgetDescriptor } = await import("/runtime/records/widget-descriptors.js");
  const { addressableAt } = await import("/runtime/records/thread/messages.js");
  adoptRegistry({ $layer: { generation: "refused-reading" }, "lf-refused": {} });
  const message = {
    id: "refused-message",
    kind: "comment",
    author: "agent",
    text: '<lf-refused id="refused-widget">Words</lf-refused>',
    html: true,
    seq: 1,
    ts: "2026-03-01T12:00:00Z",
  };
  /** @param {ReturnType<typeof reading>} state */
  const holdingMessage = (state) => {
    state.browser.views[state.active.revision].thread.threads = [
      servedThread([message]),
    ];
    return state;
  };
  const replacement = () =>
    Object.assign(document.createElement("lf-refused"), { id: "refused-widget" });

  // An answer about a revision this page doesn't show, which it can't adopt.
  const elsewhere = reading();
  const view = elsewhere.browser.views[1];
  elsewhere.active = { ...elsewhere.active, revision: 2 };
  elsewhere.browser.views = { 2: { ...view, basis: { ...view.basis, revision: 2 } } };
  await application.receiveState(holdingMessage(elsewhere));
  assert.equal(adopted(), false);
  assert.equal(widgetDescriptor(replacement()), null);
  assert.equal(addressableAt("refused-widget"), null);

  let shown = false;
  const showing = application
    .receiveState(holdingMessage(reading()))
    .then(() => (shown = true));
  await settle();
  assert.equal(adopted(), true);
  assert.equal(widgetDescriptor(replacement())?.document.message, "refused-message");
  assert.equal(addressableAt("refused-widget")?.localName, "lf-refused");
  while (!shown) {
    await frame();
    await settle();
  }
  await showing;
});
