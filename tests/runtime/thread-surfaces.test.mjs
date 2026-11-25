import assert from "node:assert/strict";
import test from "node:test";

import { effect } from "/vendor/signals-core.js";
import { adoptRegistry } from "/runtime/state/registry.js";
import {
  claimed,
  placePageThreads,
  renderSurfaces,
  watchThreadSurfaces,
} from "/runtime/records/thread/surfaces.js";
import { readThreadRecords } from "/runtime/state/thread/model.js";
import { threadSurface } from "/runtime/records/thread/surface-handles.js";
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

// A thread of one comment about the element `section` names, as the publisher reads it.
const threadAbout = (id, section) =>
  readThreadRecords(
    [
      servedThread(
        [
          {
            id,
            kind: "comment",
            author: "user",
            text: "Seat me",
            seq: 1,
            ts: "2026-03-01T12:00:00Z",
          },
        ],
        { anchor: { section } },
      ),
    ],
    { registry: {}, descriptors: new Map(), messageBodies: new Map() },
    new Map(),
    [],
  )[0];

// What a surface asks of the page: a composer standing in no outlet, but for what
// `composition` says of it.
const surfaceCommands = (composition = {}) => ({
  composition: {
    active: () => null,
    outlet: () => null,
    node: () => null,
    seat: () => false,
    restore() {},
    ...composition,
  },
  read: {
    observeMessage: () => () => {},
    observeFeedback: () => () => {},
    observeSummary: () => () => {},
  },
  reply: { wireInput },
  reaction: {},
  placedAt: () => null,
  invalidate() {},
  reveal() {},
});

test("a surface widget whose constructor threw is not waited for", async () => {
  // A failed upgrade leaves the element undefined while its definition stands, so a
  // watch that waited for the definition would re-offer the element on every
  // resolution and spin forever. Waits are counted, and capped so that spin fails here
  // rather than starving the event loop.
  adoptRegistry({
    "lf-broken-surface": {},
    $modules: { "lf-broken-surface": "widgets/lf-broken-surface.js" },
  });
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
    watchThreadSurfaces({ invalidate() {}, composition: {}, reveal() {} });
    for (let turn = 0; turn < 5; turn++)
      await new Promise((resolve) => setTimeout(resolve, 0));
    assert.equal(widget.matches(":defined"), false);
    assert.equal(waits, 0);
    widget.remove();
  } finally {
    customElements.whenDefined = real;
  }
});

test("a surface releases the composer from its own outlet under the node named", async () => {
  // A widget releases a node before removing it, so the page's one composer leaves
  // while it is still in the document. The handle answers for the outlets its own
  // surface seated: the composer standing elsewhere, or under a node the widget is
  // not removing, stays where it is.
  const thread = threadAbout("released", "release-target");
  const owner = document.createElement("section");
  const target = document.createElement("p");
  target.id = "release-target";
  const row = document.createElement("div");
  const outlet = document.createElement("div");
  const sibling = document.createElement("div");
  row.append(outlet);
  owner.append(row, sibling);
  const stranger = document.createElement("section");
  document.body.append(target, owner, stranger);
  /** @type {Element | null} */
  let seated = null;
  let restores = 0;
  const commands = surfaceCommands({
    outlet: () => seated,
    restore: () => void restores++,
  });
  const handle = threadSurface(owner);
  handle.release(owner);
  assert.equal(restores, 0, "a widget with no surface has nothing to release");
  const surface = placePageThreads(owner, (batch) => batch.map(() => outlet), commands);
  try {
    const seating = renderSurfaces(
      { phase: "ready", threads: [thread] },
      {
        placedAt: (id) =>
          id === thread.id ? { status: "exact", place: target } : null,
        pendingAt: () => null,
      },
      commands,
    );
    await seating.completion;
    seating.commit();
    seated = outlet;
    restores = 0;
    handle.release(sibling);
    assert.equal(restores, 0, "the composer stands outside the node");
    threadSurface(stranger).release(document.body);
    assert.equal(
      restores,
      0,
      "another element's handle answers for no outlet of this one",
    );
    handle.release(row);
    assert.equal(restores, 1, "the composer leaves the outlet under the node");
    seated = stranger;
    handle.release(document.body);
    assert.equal(restores, 1, "the composer stands in no outlet of this surface");
  } finally {
    surface.unregister();
    owner.remove();
    target.remove();
    stranger.remove();
  }
});

test("a paint follows a surface's opener lifetime and the threads its seat claims", async () => {
  // The margin lists a thread no seat draws (features/annotation-inventory.js), so its paint
  // reads `claimed`. Nothing else tells it a commit seated or released a thread: the
  // thread pass paints no region but its own, and the margin's presenter repaints
  // when a reading its paint followed moves.
  const thread = threadAbout("seated", "target");
  const owner = document.createElement("section");
  owner.id = "rail";
  const target = document.createElement("p");
  target.id = "target";
  const outlet = document.createElement("div");
  owner.append(outlet);
  document.body.append(target, owner);
  const commands = surfaceCommands();
  const portable = threadSurface(owner);
  const openers = [];
  const stopOpeners = effect(() => openers.push(portable.open));
  assert.deepEqual(openers, [null], "a host without registration offers no opener");
  const draw = (batch) => batch.map(() => outlet);
  let surface = placePageThreads(owner, draw, commands);
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
    // The thread pass commits inside its own paint (records/thread/presentation.js), so a
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
    surface = placePageThreads(owner, draw, commands);
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
    surface = placePageThreads(owner, draw, commands);
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
