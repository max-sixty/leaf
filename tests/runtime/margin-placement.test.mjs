/* Where a margin row stands: rail or pin, how far past its block, and how far down.

   A 1440px window with the column's padding box ending at 1057, so the rail's inner edge
   is 1079 and a 32px marker's half is 16. */

import assert from "node:assert/strict";
import test from "node:test";

import {
  packRows,
  pinOffset,
  rowPosture,
  stepPast,
} from "/runtime/margin-placement.js";

const posture = (blockRight, over = {}) =>
  rowPosture({
    railStands: true,
    rootLane: true,
    blockRight,
    railInner: 1079,
    half: 16,
    wide: "pin",
    ...over,
  });

test("a row stands in the rail beside a block that stays in the column", () => {
  assert.equal(posture(1033), "rail");
  // A block reaching into the rail by less than half a marker keeps it.
  assert.equal(posture(1094), "rail");
});

test("a row whose block grows past the rail stands on the block as a pin", () => {
  assert.equal(posture(1300), "pin");
});

test("without a rail, or inside a pane that scrolls, every row is a pin", () => {
  assert.equal(posture(700, { railStands: false }), "pin");
  assert.equal(posture(700, { rootLane: false }), "pin");
});

test("the step alternate keeps every root-lane row in the rail", () => {
  assert.equal(posture(1300, { wide: "step" }), "rail");
  assert.equal(posture(1300, { wide: "step", railStands: false }), "pin");
});

test("a pin takes the room beside its block, up to its own width", () => {
  assert.equal(pinOffset({ room: 64, size: 32 }), 32);
  assert.equal(pinOffset({ room: 24, size: 32 }), 24);
  // No room at all: the pin stands wholly inside the block's corner.
  assert.equal(pinOffset({ room: -3, size: 32 }), 0);
});

test("the look pass's alternates ignore the room", () => {
  assert.equal(pinOffset({ room: 64, size: 32, pin: "straddle" }), 16);
  assert.equal(pinOffset({ room: 64, size: 24, pin: "corner" }), -4);
});

const rect = (left, top, width = 37, height = 32) => ({
  left,
  right: left + width,
  top,
  bottom: top + height,
});

test("rows that would overlap are pushed below the one placed first", () => {
  const pushes = packRows(
    [
      { key: "b", rect: rect(1079, 110), priority: 10 },
      { key: "a", rect: rect(1079, 100), priority: 10 },
      { key: "c", rect: rect(1079, 300), priority: 10 },
    ],
    4,
  );
  assert.deepEqual(Object.fromEntries(pushes), { a: 0, b: 26, c: 0 });
});

test("a pin and a rail marker level with each other both stay where they are", () => {
  const pushes = packRows(
    [
      { key: "rail", rect: rect(1079, 100), priority: 10 },
      { key: "pin", rect: rect(900, 100), priority: 10 },
    ],
    4,
  );
  assert.deepEqual(Object.fromEntries(pushes), { rail: 0, pin: 0 });
});

test("the more important row keeps its place and the other moves", () => {
  const pushes = packRows(
    [
      { key: "late", rect: rect(1079, 90), priority: 10 },
      { key: "first", rect: rect(1079, 100), priority: 0 },
    ],
    4,
  );
  assert.deepEqual(Object.fromEntries(pushes), { first: 0, late: 46 });
});

test("rows are packed from the top, so a push carries on down the stack", () => {
  const pushes = packRows(
    [
      { key: "a", rect: rect(1079, 100), priority: 10 },
      { key: "b", rect: rect(1079, 136), priority: 10 },
      { key: "c", rect: rect(1079, 104), priority: 10 },
    ],
    4,
  );
  // c goes under a, which is where b stands, so b goes under c.
  assert.deepEqual(Object.fromEntries(pushes), { a: 0, c: 32, b: 36 });
});

test("the step alternate hangs a rail row past a grown box level with it", () => {
  const wide = [{ top: 90, bottom: 400, right: 1200 }];
  const step = (top) =>
    stepPast({
      left: 1079,
      width: 37,
      hang: 22,
      top,
      height: 32,
      wide,
      shellRight: 1440,
    });
  assert.equal(step(100), 143);
  assert.equal(step(500), 0);
  // Never past the shell's edge.
  assert.equal(
    stepPast({
      left: 1079,
      width: 37,
      hang: 22,
      top: 100,
      height: 32,
      wide,
      shellRight: 1200,
    }),
    84,
  );
});

test("a pin level with a control of the page goes below it", () => {
  const grip = { left: 1060, right: 1076, top: 98, bottom: 114 };
  const pushes = packRows([{ key: "pin", rect: rect(1045, 96), priority: 10 }], 4, [
    grip,
  ]);
  assert.deepEqual(Object.fromEntries(pushes), { pin: 22 });
  // A control beside the pin rather than under it moves nothing.
  const aside = packRows([{ key: "pin", rect: rect(1045, 96), priority: 10 }], 4, [
    { left: 900, right: 916, top: 98, bottom: 114 },
  ]);
  assert.deepEqual(Object.fromEntries(aside), { pin: 0 });
});
