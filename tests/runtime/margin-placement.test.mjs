/* Where a margin row stands: rail or pin, and how far down.

   A 1440px window with the column's padding box ending at 1057, so the rail's inner edge
   is 1079 and a 32px marker's half is 16. */

import assert from "node:assert/strict";
import test from "node:test";

import { packRows, pinSpot, rowPosture, seatRows } from "/runtime/margin-placement.js";

const posture = (blockRight, over = {}) =>
  rowPosture({
    railStands: true,
    besideRail: true,
    blockRight,
    railInner: 1079,
    half: 16,
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

test("without a rail, or in a region the rail is not beside, every row is a pin", () => {
  assert.equal(posture(700, { railStands: false }), "pin");
  assert.equal(posture(700, { besideRail: false }), "pin");
});

test("a row level with a note hanging in the margin stands on its block as a pin", () => {
  assert.equal(posture(700, { noted: true }), "pin");
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

// A paragraph's last two lines at a phone's width, 366px of column in a 390px window:
// the first fills its line, and a run that starts on it ends 280px into the second. The
// next block starts 30px below.
const box = (left, top, right, bottom) => ({ left, top, right, bottom });
const words = [box(24, 100, 366, 121), box(24, 127, 280, 148)];
const spot = (cover) =>
  pinSpot({
    // A 44px marker level with the run's last line, just after its end.
    seat: box(284, 115.5, 328, 159.5),
    home: box(318, 100, 362, 144),
    parts: [box(160, 100, 366, 121), box(24, 127, 280, 148)],
    cover,
    bounds: box(4, -Infinity, 386, Infinity),
    reach: 12,
    gap: 4,
  });

test("a pin whose seat covers nothing takes it", () => {
  assert.deepEqual(
    spot([words[1], box(24, 178, 366, 260)]),
    box(284, 115.5, 328, 159.5),
  );
});

test("a pin whose seat covers words takes the nearest room beside its target", () => {
  // The seat reaches up into the first line, so the pin drops below that line's words:
  // still level with the run's last line, and clear of the next block.
  assert.deepEqual(spot([...words, box(24, 178, 366, 260)]), box(284, 125, 328, 169));
});

test("another block counts whole, so a pin with no room of its own stays home", () => {
  // Brought up to the paragraph, the next block leaves the last line too little room
  // below, though nothing is drawn in its top 20px; the pin stands in the leading above
  // the run instead.
  const below = box(24, 152, 366, 260);
  assert.deepEqual(spot([...words, below]), box(284, 52, 328, 96));
  // With a heading 10px above the paragraph, that room is the heading's.
  assert.deepEqual(
    spot([...words, below, box(24, 40, 366, 90)]),
    box(318, 100, 362, 144),
  );
});

// Two pins by the same run: `first` the more important, `second` below it in packing.
const seat = box(284, 115.5, 328, 159.5);
const pin = (key, priority, held = null) => ({
  key,
  priority,
  held,
  rect: box(318, 100, 362, 144),
  seat,
  parts: [box(160, 100, 366, 121), box(24, 127, 280, 148)],
  cover: [words[1], box(24, 178, 366, 260)],
  bounds: box(4, -Infinity, 386, Infinity),
});
const overlap = (a, b) =>
  a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;

test("pins are seated the more important first, each clear of those before it", () => {
  const seats = seatRows([pin("second", 10), pin("first", 0)], { reach: 12, gap: 4 });
  assert.deepEqual(seats.get("first"), seat);
  assert.ok(!overlap(seats.get("second"), seat), seats);
});

test("a held pin keeps its seat, and a more important pin takes other room", () => {
  // `second` is under the pointer, at the seat `first` would otherwise take.
  const seats = seatRows([pin("second", 10, seat), pin("first", 0)], {
    reach: 12,
    gap: 4,
  });
  assert.deepEqual(seats.get("second"), seat);
  assert.ok(!overlap(seats.get("first"), seat), seats);
});

test("a held row is packed first, so nothing pushes it from under the press", () => {
  const pushes = packRows(
    [
      { key: "first", rect: rect(1079, 100), priority: 0 },
      { key: "held", rect: rect(1079, 110), priority: 10, held: true },
    ],
    4,
  );
  assert.deepEqual(Object.fromEntries(pushes), { held: 0, first: 46 });
});
