/* Where a hint chip stands: clear of the window's edge, the key line and the chips seated
   before it.

   A 1000×800 window whose browsed band is 2px, so a chip keeps 2px from each edge and
   from every barrier, and a 20×16 chip. */

import assert from "node:assert/strict";
import test from "node:test";

import { seatHints } from "/runtime/keyboard/hints.js";

const viewport = { left: 0, top: 0, right: 1000, bottom: 800 };
const box = (left, top, width, height) => ({
  left,
  top,
  right: left + width,
  bottom: top + height,
  width,
  height,
});
const chip = (left, top) => box(left, top, 20, 16);
const seat = (faces, over = {}) =>
  seatHints(faces, { band: 2, viewport, ...over }).map(
    ({ box }) => box && { left: box.left, top: box.top },
  );

test("a chip drawn on another is seated below it", () => {
  const target = box(100, 100, 200, 20);
  assert.deepEqual(
    seat([
      { start: chip(100, 100), target },
      { start: chip(100, 100), target },
    ]),
    [
      { left: 100, top: 100 },
      { left: 100, top: 118 },
    ],
  );
});

test("a chip below its target is centred under it and clears it", () => {
  const target = box(200, 50, 100, 20);
  assert.deepEqual(seat([{ start: chip(0, 0), target, placement: "below" }]), [
    { left: 240, top: 72 },
  ]);
});

test("a chip past the window's corner is held inside the band", () => {
  // The last few pixels of a control show in the window's corner.
  const target = box(990, 795, 10, 5);
  assert.deepEqual(seat([{ start: chip(980, 787), target }]), [
    { left: 978, top: 782 },
  ]);
});

// Whether each seated chip reads as its own row's: no other row's band is nearer the
// chip's middle than its own row's.
const readsAsOwnRow = (seated, rows) => {
  for (const { face, box: at } of seated.filter(({ box }) => box)) {
    const middle = (at.top + at.bottom) / 2;
    const off = (row) => Math.max(row.top - middle, middle - row.bottom, 0);
    assert.ok(
      rows.every((row) => off(row) >= off(face.target)),
      `the chip for the row at ${face.target.top} stands at ${at.top}`,
    );
  }
};
const overlapping = (boxes) =>
  boxes.flatMap((one, at) =>
    boxes
      .slice(at + 1)
      .filter(
        (other) =>
          one.left < other.right &&
          other.left < one.right &&
          one.top < other.bottom &&
          other.top < one.bottom,
      )
      .map((other) => `${one.top} and ${other.top}`),
  );

// The middle of a box, down the page.
const middle = (one) => (one.top + one.bottom) / 2;

test("a crowded column levels each chip with its row and steps every other one out a column", () => {
  // Rows closer together than a chip and its gap. Spread down the column, each chip
  // stood further past its own row than the last, twelve rows in by four rows.
  const rows = Array.from({ length: 12 }, (_, at) => box(100, 100 + 14 * at, 300, 14));
  const seated = seatHints(
    rows.map((target) => ({ start: chip(90, target.top - 8), target })),
    { band: 2, viewport },
  );
  assert.deepEqual(
    seated.map(({ face, box }) => [box.left, middle(box) === middle(face.target)]),
    rows.map((_, at) => [at % 2 ? 68 : 90, true]),
  );
  assert.deepEqual(overlapping(seated.map(({ box }) => box)), []);
});

test("a crowded column at the window's edge withholds every other row's chip, the rest level", () => {
  const rows = Array.from({ length: 12 }, (_, at) => box(4, 100 + 14 * at, 300, 14));
  const seated = seatHints(
    rows.map((target) => ({ start: chip(-6, target.top - 8), target })),
    { band: 2, viewport },
  );
  assert.deepEqual(
    seated.map(({ face, box }) => box && middle(box) === middle(face.target)),
    rows.map((_, at) => (at % 2 ? null : true)),
  );
});

test("a typed prefix that puts every other row's chip away leaves the rest level", () => {
  const rows = Array.from({ length: 12 }, (_, at) => box(100, 100 + 14 * at, 300, 14));
  const kept = rows.filter((_, at) => at % 2);
  const seated = seatHints(
    kept.map((target) => ({ start: chip(90, target.top - 8), target })),
    { band: 2, viewport, targets: rows },
  );
  assert.ok(
    seated.every(({ face, box }) => box && middle(box) === middle(face.target)),
    seated,
  );
});

test("a chip the window's edge holds stands level with no other row", () => {
  // Two pixels of the first row show at the window's head, above two whole rows.
  const rows = [box(100, 0, 300, 2), box(100, 2, 300, 14), box(100, 16, 300, 14)];
  const seated = seatHints(
    rows.map((target) => ({ start: chip(90, target.top - 8), target })),
    { band: 2, viewport },
  );
  readsAsOwnRow(seated, rows);
});

test("a chip with no seat beside its own target is withheld", () => {
  // Three pixels of a row show at the window's foot, under the panel's band.
  const panel = box(50, 760, 900, 40);
  const target = box(100, 797, 300, 3);
  assert.deepEqual(seat([{ start: chip(90, 789), target }], { barriers: [panel] }), [
    null,
  ]);
});

test("adjacent footnote markers' chips all stand, stacked around the markers", () => {
  const markers = [300, 308, 316].map((left) => box(left, 100, 8, 24));
  const seated = seat(
    markers.map((target) => ({ start: chip(target.left - 10, 92), target })),
  );
  assert.ok(seated.every(Boolean), seated);
  const boxes = seated.map(({ left, top }) => box(left, top, 20, 16));
  for (const [at, one] of boxes.entries())
    for (const other of boxes.slice(at + 1))
      assert.ok(
        one.bottom <= other.top || other.bottom <= one.top,
        `${one.top} and ${other.top} collide`,
      );
});

test("before-target chips stay outside the words, including when the window clamps them", () => {
  assert.deepEqual(
    seat([
      { start: chip(100, 100), target: box(100, 100, 200, 20), placement: "before" },
    ]),
    [{ left: 78, top: 102 }],
  );
  const target = box(0, 100, 200, 20);
  assert.deepEqual(seat([{ start: chip(0, 100), target, placement: "before" }]), [
    { left: 2, top: 82 },
  ]);
});

test("a before chip whose target fills the window stands on its target", () => {
  const page = box(0, 0, 1000, 800);
  assert.deepEqual(seat([{ start: chip(0, 0), target: page, placement: "before" }]), [
    { left: 2, top: 2 },
  ]);
});

test("a before chip stands level with its target's first line, so each row in a list keeps its own", () => {
  const rows = [100, 130].map((top) => box(100, top, 200, 30));
  assert.deepEqual(
    seat(
      rows.map((target) => ({
        start: chip(target.left, target.top),
        target,
        placement: "before",
      })),
    ),
    [
      { left: 78, top: 107 },
      { left: 78, top: 137 },
    ],
  );
  assert.deepEqual(
    seat([
      { start: chip(100, 100), target: box(100, 100, 200, 400), placement: "before" },
    ]),
    [{ left: 78, top: 108 }],
  );
});

test("a before chip that would cover a neighbouring target keeps its own target's corner", () => {
  const buttons = [box(100, 100, 100, 30), box(205, 100, 100, 30)];
  assert.deepEqual(
    seat(
      buttons.map((target) => ({
        start: chip(target.left, target.top),
        target,
        placement: "before",
      })),
    ),
    [
      { left: 78, top: 107 },
      { left: 183, top: 100 },
    ],
  );
});

test("control chips sit above their own left edge", () => {
  const target = box(800, 400, 120, 30);
  // The chip's CSS centres its face on the seat. Its measured start already carries
  // that translation; outside placement follows the target edge rather than it.
  assert.deepEqual(seat([{ start: chip(790, 392), target, placement: "above" }]), [
    { left: 800, top: 382 },
  ]);
});

test("before chips of nested targets stand one step out per level, the deepest where they would alone", () => {
  const group = box(200, 100, 400, 300);
  const option = box(200, 100, 400, 100);
  const later = box(200, 200, 400, 100);
  const heading = box(200, 420, 300, 30);
  assert.deepEqual(
    seat(
      [group, option, later, heading].map((target) => ({
        start: chip(target.left, target.top),
        target,
        placement: "before",
      })),
    ),
    [
      { left: 168, top: 108 },
      { left: 178, top: 126 },
      { left: 178, top: 208 },
      { left: 178, top: 427 },
    ],
  );
});

test("the nesting step narrows to the room before the outermost target", () => {
  const outer = box(40, 100, 400, 300);
  const middle = box(40, 100, 400, 200);
  const inner = box(40, 100, 400, 100);
  const lefts = seat(
    [outer, middle, inner].map((target) => ({
      start: chip(target.left, target.top),
      target,
      placement: "before",
    })),
  ).map(({ left }) => left);
  // 40 − 20 − 2 leaves 18 − 2 = 16 before the window's band: two levels of 8.
  assert.deepEqual(lefts, [2, 10, 18]);
});

test("a target in no nest keeps its chip beside it, and a clamped chip does not narrow the step", () => {
  const group = box(200, 100, 400, 300);
  const option = box(200, 100, 400, 100);
  const alone = box(200, 500, 400, 50);
  const tight = box(10, 600, 100, 50);
  const tightInner = box(10, 600, 100, 20);
  const lefts = seat(
    [group, option, alone, tight, tightInner].map((target) => ({
      start: chip(target.left, target.top),
      target,
      placement: "before",
    })),
  ).map(({ left }) => left);
  assert.deepEqual(lefts, [168, 178, 178, 2, 2]);
});
