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
} from "/runtime/state/semantic-state.js";
import { clockValue, tickClock } from "/runtime/state/presence.js";

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
  const { PRESENTATION_DOM } = await import("/runtime/state/semantic-state.js");
  let dom = "old";
  const seen = [];
  // The DOM the projection waits for, none until an owner upstream of it draws.
  const upstream = Promise.withResolvers();
  let owed = [];
  const projection = applicationPresenter({
    region: "projection:chrome",
    after: () => owed,
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
  owed = [upstream.promise];
  void consumer.present();
  const finished = projection.present();
  await new Promise((resolve) => setTimeout(resolve, 0));
  const beforeCommit = [...seen];
  upstream.resolve();
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
  const { tick } = await import("/runtime/state/version-signal.js");
  const { signal } = await import("/vendor/signals-core.js");
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
