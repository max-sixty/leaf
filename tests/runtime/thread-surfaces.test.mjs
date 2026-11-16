import assert from "node:assert/strict";
import test from "node:test";

import { effect } from "/runtime/framework.js";
import { adoptRegistry } from "/runtime/registry.js";
import {
  claimed,
  placePageThreads,
  renderSurfaces,
  watchThreadSurfaces,
} from "/runtime/thread/surfaces.js";
import { readThreadRecords } from "/runtime/thread/model.js";
import { threadSurface } from "/runtime/thread/surface-handles.js";
import { servedThread } from "../served.mjs";

// Every card draws its reply box; this stands in for the box's input wiring, which
// composing-input.test.mjs covers.
const wireInput = () =>
  Object.assign(() => {}, {
    value: () => "",
    button: null,
    load() {},
    cancelDictation() {},
  });

test("a surface widget whose constructor threw is not waited for", async () => {
  // A failed upgrade leaves the element undefined while its definition stands, so a
  // watch that waited for the definition would re-offer the element on every
  // resolution and spin forever. Waits are counted, and capped so that spin fails here
  // rather than starving the event loop.
  adoptRegistry({ "lf-broken-surface": { "x-thread-surface": true } });
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
    watchThreadSurfaces({ invalidate() {}, composition: {} });
    for (let turn = 0; turn < 5; turn++)
      await new Promise((resolve) => setTimeout(resolve, 0));
    assert.equal(widget.matches(":defined"), false);
    assert.equal(waits, 0);
    widget.remove();
  } finally {
    customElements.whenDefined = real;
  }
});

test("a paint follows a surface's opener lifetime and the threads its seat claims", async () => {
  // The margin lists a thread no seat draws (annotation-inventory.js), so its paint
  // reads `claimed`. Nothing else tells it a commit seated or released a thread: the
  // thread pass paints no region but its own, and the margin's presenter repaints
  // when a reading its paint followed moves.
  const root = {
    id: "seated",
    kind: "comment",
    author: "user",
    text: "Seat me",
    seq: 1,
    ts: "2026-03-01T12:00:00Z",
  };
  const [thread] = readThreadRecords(
    [servedThread([root], { anchor: { section: "target" } })],
    { registry: {}, descriptors: new Map(), messageBodies: new Map() },
    new Map(),
    [],
  );
  const owner = document.createElement("section");
  owner.id = "rail";
  const target = document.createElement("p");
  target.id = "target";
  const outlet = document.createElement("div");
  owner.append(outlet);
  document.body.append(target, owner);
  const composition = {
    active: () => null,
    outlet: () => null,
    node: () => null,
    seat: () => false,
    restore() {},
  };
  const read = { observeMessage: () => () => {}, observeFeedback: () => () => {} };
  const commands = {
    composition,
    read,
    reply: { wireInput },
    reaction: {},
    invalidate() {},
  };
  const portable = threadSurface(owner);
  const openers = [];
  const stopOpeners = effect(() => openers.push(portable.open));
  assert.deepEqual(openers, [null], "a host without registration offers no opener");
  const draw = (batch) => batch.map(() => outlet);
  let surface = placePageThreads(owner, draw, {}, commands);
  assert.equal(
    openers.at(-1),
    surface.open,
    "late registration offers the real opener",
  );
  const placements = {
    placedAt: (id) => (id === thread.id ? { status: "exact", place: target } : null),
    pendingAt: () => null,
  };
  const readings = [];
  const stop = effect(() => readings.push(claimed(thread.id)));
  try {
    assert.deepEqual(readings, [false]);
    const seating = renderSurfaces(
      { phase: "ready", threads: [thread] },
      placements,
      commands,
    );
    await seating.completion;
    assert.deepEqual(readings, [false], "preparation claims nothing");
    // The thread pass commits inside its own paint (thread/presentation.js), so a
    // commit that followed what it moves would have the pass claim a second one.
    let passes = 0;
    effect(() => {
      passes += 1;
      if (passes === 1) seating.commit();
    })();
    assert.equal(passes, 1, "the pass that commits follows nothing the commit moved");
    assert.deepEqual(
      readings,
      [false, true],
      "the commit that seats the thread is followed",
    );
    const same = renderSurfaces(
      { phase: "ready", threads: [thread] },
      placements,
      commands,
    );
    await same.completion;
    same.commit();
    assert.deepEqual(
      readings,
      [false, true],
      "a commit that seats the same threads moves nothing",
    );
    const releasing = renderSurfaces(
      { phase: "ready", threads: [] },
      placements,
      commands,
    );
    await releasing.completion;
    releasing.commit();
    assert.deepEqual(
      readings,
      [false, true, false],
      "releasing the thread is followed too",
    );
    surface.unregister();
    assert.equal(openers.at(-1), null, "retirement removes the capability");
    surface = placePageThreads(owner, draw, {}, commands);
    assert.equal(
      openers.at(-1),
      surface.open,
      "registration can return on the same owner",
    );
    owner.remove();
    await renderSurfaces({ phase: "ready", threads: [] }, placements, commands)
      .completion;
    assert.equal(
      openers.at(-1),
      null,
      "disconnected cleanup also removes the capability",
    );
    const departed = surface;
    assert.equal(departed.open(target), false, "a captured departed opener is retired");
    document.body.append(owner);
    surface = placePageThreads(owner, draw, {}, commands);
    departed.unregister();
    assert.equal(
      portable.open,
      surface.open,
      "old cleanup cannot retire a new registration",
    );
  } finally {
    stop();
    stopOpeners();
    surface.unregister();
    owner.remove();
    target.remove();
  }
});

test("a page surface's update is the pass that places its threads", async () => {
  // A page widget that changes which threads it draws waits for the placement before
  // it measures or focuses what an outlet holds. Several asks before the pass starts
  // are one pass, and each ask gets that pass's own outcome.
  const owner = document.createElement("section");
  document.body.append(owner);
  /** @type {PromiseWithResolvers<void>[]} */
  const passes = [];
  const surface = placePageThreads(
    owner,
    () => [],
    {},
    {
      composition: {},
      invalidate() {
        const pass = Promise.withResolvers();
        passes.push(pass);
        return pass.promise;
      },
    },
  );
  try {
    // Registration asks for the first pass.
    await Promise.resolve();
    assert.equal(passes.length, 1);
    passes[0].resolve();
    let placed = false;
    const first = surface.update();
    const second = surface.update();
    assert.equal(first, second, "asks before the pass starts share it");
    void first.then(() => (placed = true));
    await Promise.resolve();
    assert.equal(passes.length, 2, "one pass for both asks");
    await Promise.resolve();
    assert.equal(placed, false, "the update waits for the pass to show");
    passes[1].resolve();
    await first;
    assert.equal(placed, true);
    const failing = surface.update();
    await Promise.resolve();
    passes[2].reject(new Error("the pass failed"));
    await assert.rejects(failing, /the pass failed/);
  } finally {
    surface.unregister();
    owner.remove();
  }
});
