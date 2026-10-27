/* A document region repaints for the parts its paint read, and for no others.

   Native effects follow a region's reading and each synchronous stretch of its paint,
   claiming a paint when a publication moves one of those parts. These
   drive one region through the publisher's own phase. */
import assert from "node:assert/strict";
import test from "node:test";
import {
  applicationPresenter,
  applicationState,
  readPart,
  whenApplicationPresented,
  queueWidgetUpdate,
} from "/runtime/semantic-state.js";
import { clockValue, tickClock } from "/runtime/presence.js";

const phase = readPart((root) => root.phase);

test("a region repaints when a part its paint read moves, and not for another", async () => {
  const paints = [];
  const region = applicationPresenter({
    region: "probe-moves",
    reading: () => true,
    paint: () => {
      paints.push(phase());
      return true;
    },
  });
  applicationState.setPhase("waiting");
  await region.present();
  await whenApplicationPresented();
  applicationState.setPhase("offline");
  await whenApplicationPresented();
  assert.deepEqual(paints, ["waiting", "offline"]);
  const host = applicationState.read().hostAvailable;
  applicationState.setHostAvailable(!host);
  await whenApplicationPresented();
  assert.notEqual(applicationState.read().hostAvailable, host);
  assert.deepEqual(paints, ["waiting", "offline"]);
  region.disconnect();
});

test("a paint that moves a part it read paints again with the part as it stands", async () => {
  applicationState.setPhase("waiting");
  const paints = [];
  const region = applicationPresenter({
    region: "probe-publishes",
    reading: () => true,
    paint: () => {
      const now = phase();
      paints.push(now);
      if (now === "waiting") applicationState.setPhase("offline");
      return now;
    },
  });
  await region.present();
  await whenApplicationPresented();
  assert.deepEqual(paints, ["waiting", "offline"]);
  region.disconnect();
});

test("a reading that moves a part it read is refused", () => {
  applicationState.setPhase("waiting");
  assert.throws(
    () =>
      applicationPresenter({
        region: "probe-reading",
        reading: () => {
          if (phase() === "waiting") applicationState.setPhase("offline");
          return true;
        },
        paint: () => true,
      }),
    /reading moved a part it read/,
  );
});

test("a part a paint reads after it waits is followed only where it resumes", async () => {
  applicationState.setPhase("waiting");
  const host = readPart((root) => root.hostAvailable);
  const paints = { resumed: [], bare: [] };
  const regions = Object.entries(paints).map(([name, seen]) =>
    applicationPresenter({
      region: `probe-${name}`,
      reading: () => true,
      paint: async (value, current, resume) => {
        await null;
        const after = () => seen.push(host());
        if (name === "resumed") resume(after)();
        else after();
        return true;
      },
    }),
  );
  await Promise.all(regions.map((region) => region.present()));
  await whenApplicationPresented();
  applicationState.setHostAvailable(!applicationState.read().hostAvailable);
  await whenApplicationPresented();
  assert.equal(paints.resumed.length, 2);
  assert.equal(paints.bare.length, 1);
  for (const region of regions) region.disconnect();
});

test("a region repaints when a time its paint shows ages, wherever the paint read it", async () => {
  let clock = 0;
  const paints = { synchronous: [], resumed: [], bare: [] };
  const regions = Object.entries(paints).map(([name, seen]) =>
    applicationPresenter({
      region: `probe-clock-${name}`,
      reading: () => true,
      paint: async (value, current, resume) => {
        const after = () => seen.push(clockValue(() => clock));
        if (name === "synchronous") after();
        else {
          await null;
          if (name === "resumed") resume(after)();
          else after();
        }
        return true;
      },
    }),
  );
  await Promise.all(regions.map((region) => region.present()));
  await whenApplicationPresented();
  clock += 1;
  await tickClock((message) => {
    throw new Error(message);
  });
  await whenApplicationPresented();
  // A second tick that moves nothing paints nothing.
  await tickClock((message) => {
    throw new Error(message);
  });
  await whenApplicationPresented();
  assert.deepEqual(paints, { synchronous: [0, 1], resumed: [0, 1], bare: [0] });
  for (const region of regions) region.disconnect();
});

test("explicit presentation rereads mechanical inputs without duplicate claims", async () => {
  let mounted = false;
  const paints = [];
  const region = applicationPresenter({
    region: "probe-mechanical-reading",
    reading: () => (mounted ? "mounted" : null),
    paint: (value) => paints.push(value),
  });
  mounted = true;
  await region.present();
  await whenApplicationPresented();
  assert.deepEqual(paints, ["mounted"]);
  await region.present();
  await whenApplicationPresented();
  assert.deepEqual(paints, ["mounted", "mounted"]);
  region.disconnect();
});

test("an unchanged intermediary still carries its upstream DOM dependencies", async () => {
  const { PRESENTATION_DOM } = await import("/runtime/semantic-state.js");
  let dom = "old";
  const seen = [];
  const projection = applicationPresenter({
    region: "projection:chrome",
    after: PRESENTATION_DOM.widgets,
    reading: () => true,
    paint: () => {
      dom = "projected";
    },
  });
  const thread = applicationPresenter({
    region: "thread",
    after: PRESENTATION_DOM.projection,
    reading: () => true,
    paint: () => {},
  });
  await thread.present();
  const consumer = applicationPresenter({
    region: "transitive-dom-consumer",
    after: PRESENTATION_DOM.thread,
    reading: () => true,
    paint: () => seen.push(dom),
  });
  const nativeCommit = Promise.withResolvers();
  const updated = queueWidgetUpdate(
    "pending-native-widget",
    () => {
      dom = "widget";
    },
    () => nativeCommit.promise,
  );
  void consumer.present();
  const finished = projection.present();
  await updated;
  await new Promise((resolve) => setTimeout(resolve, 0));
  const beforeCommit = [...seen];
  nativeCommit.resolve();
  await finished;
  projection.disconnect();
  thread.disconnect();
  consumer.disconnect();
  assert.deepEqual(
    beforeCommit,
    [],
    "an idle thread is not proof of committed projection DOM",
  );
  assert.deepEqual(seen, ["projected"]);
});

test("a paint advancing a version it does not read claims no second pass", async () => {
  // An owner's commit advances the version its readers follow, inside the paint that
  // commits. `tick` writes without reading, so the paint is not subscribed to its own
  // write; `x.value += 1` reads first, and claims the region again for nothing.
  const { tick } = await import("/runtime/version-signal.js");
  const { signal } = await import("/runtime/framework.js");
  const paints = { ticked: 0, added: 0 };
  const ticked = signal(0);
  const added = signal(0);
  const quiet = applicationPresenter({
    region: "probe-tick",
    reading: () => true,
    paint: () => {
      paints.ticked += 1;
      tick(ticked);
    },
  });
  const noisy = applicationPresenter({
    region: "probe-added",
    reading: () => true,
    paint: () => {
      paints.added += 1;
      // Once, as an owner whose commit moved something does; `+=` would spin forever.
      if (paints.added === 1) added.value = added.value + 1;
    },
  });
  await quiet.present();
  await noisy.present();
  await whenApplicationPresented();
  await new Promise((resolve) => setTimeout(resolve, 0));
  quiet.disconnect();
  noisy.disconnect();
  assert.equal(paints.ticked, 1);
  assert.equal(paints.added, 2, "reading the version first subscribes the paint");
});

test("the margin's own commit is reachable while a widget holds its paint", async () => {
  // Reply continuity waits for the margin's paint, not the whole pass nor the DOM
  // upstream of the margin: a widget that withholds its commit, as one does through a
  // drag, must not keep a displaced reply editor from its new box
  // (thread/presentation.js). The regions keep the page's own dependency chain.
  const { PRESENTATION_DOM, regionCommitted, whenDocumentPresented } =
    await import("/runtime/semantic-state.js");
  const paints = [];
  const chain = [
    ["projection:chrome", PRESENTATION_DOM.widgets],
    ["thread", PRESENTATION_DOM.projection],
    ["obligations", PRESENTATION_DOM.thread],
    ["annotations", PRESENTATION_DOM.obligations],
  ].map(([region, after]) =>
    applicationPresenter({
      region,
      after,
      reading: () => true,
      paint: () => paints.push(region),
    }),
  );
  await Promise.all(chain.map((presenter) => presenter.present()));
  assert.equal(paints.length, 4);

  const held = Promise.withResolvers();
  void queueWidgetUpdate(
    "probe-held-widget",
    () => {},
    () => held.promise,
  );
  let upstream = false;
  void Promise.allSettled(PRESENTATION_DOM.annotations()).then(() => {
    upstream = true;
  });
  let documentPresented = false;
  void whenDocumentPresented().then(() => {
    documentPresented = true;
  });
  await regionCommitted("annotations");
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(upstream, false, "the margin's transitive DOM waits for the widget");
  assert.equal(documentPresented, false, "the pass still waits for the widget");
  held.resolve();
  await whenDocumentPresented();
  assert.equal(upstream, true);
  for (const presenter of chain) presenter.disconnect();
});

test("an optimistic cyclic move cannot deadlock widget DOM before its refusal", async () => {
  const original = applicationState.read().document;
  const move = {
    unit: "unit",
    writer: "user",
    record: { kind: "position", within: "lf-cycle-box" },
  };
  const descriptor = (id, parent) => ({
    id,
    tag: "lf-cycle-box",
    document: { kind: "page", revision: 1 },
    declaration: { "x-state": {} },
    parent: parent && { id: parent, tag: "lf-cycle-box" },
    ancestors: [],
    quoted: false,
  });
  const board = {
    ...descriptor("board", null),
    tag: "lf-cycle-board",
    declaration: { "x-state": { move } },
  };
  applicationState.identify(1);
  applicationState.captureDocument({
    ...applicationState.read().document,
    registry: {
      [board.tag]: board.declaration,
      "lf-cycle-box": { "x-state": {} },
      $states: {
        [board.tag]: {
          move: {
            writer: "user",
            definition: {
              origin: board.tag,
              unit: move.unit,
              record: move.record,
              creates: null,
              detail: null,
            },
          },
        },
      },
    },
    descriptors: new Map([
      ["board", board],
      ["outer", descriptor("outer", "board")],
      ["inner", descriptor("inner", "outer")],
    ]),
    authored: new Map([
      [
        "board",
        {
          tag: board.tag,
          specs: new Map([["move", move]]),
          state: {
            move: {
              value: { board: ["outer"], outer: ["inner"], inner: [] },
              units: {},
              ranks: { outer: "1", inner: "1" },
            },
          },
        },
      ],
    ]),
  });
  try {
    applicationState.enqueue(
      {
        kind: "action",
        widget: "board",
        action: "move",
        detail: { unit: "outer", value: "inner", rank: "1" },
        revision: 1,
        attempt: "cyclic-move",
      },
      "now",
    );
    assert.equal(applicationState.read().effective.widgetParents.get("outer"), "inner");
    assert.equal(applicationState.read().effective.widgetParents.get("inner"), "outer");
    const drawn = [];
    await Promise.all(
      ["outer", "inner"].map((id) =>
        queueWidgetUpdate(
          id,
          () => drawn.push(id),
          () => Promise.resolve(),
        ),
      ),
    );
    assert.deepEqual(drawn.sort(), ["inner", "outer"]);
    applicationState.refuse("cyclic-move");
    assert.equal(applicationState.read().effective.widgetParents.get("outer"), "board");
  } finally {
    applicationState.refuse("cyclic-move");
    applicationState.captureDocument(original);
  }
});
