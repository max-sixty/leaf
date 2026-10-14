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
