/* A document region repaints for the parts its paint read, and for no others.

   `applicationPresenter` collects what a region's reading and the synchronous part of
   its paint read, and claims a paint when a publication moves one of those parts. These
   drive one region through the publisher's own phase. */
import assert from "node:assert/strict";
import test from "node:test";
import {
  applicationPresenter,
  applicationState,
  readPart,
  whenApplicationPresented,
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
