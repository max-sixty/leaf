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
  seatHints(faces, { band: 2, viewport, ...over }).map(({ left, top }) => ({
    left,
    top,
  }));

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
  assert.deepEqual(seat([{ start: chip(0, 0), target, belowTarget: true }]), [
    { left: 240, top: 72 },
  ]);
});

test("a chip past the window's corner is held inside the band", () => {
  const target = box(900, 700, 90, 20);
  assert.deepEqual(seat([{ start: chip(990, 795), target }]), [
    { left: 978, top: 782 },
  ]);
});

test("a chip over the key line sits beside it on a wide target, and above it on a narrow one", () => {
  const lineBox = { left: 0, top: 760, right: 300, height: 19 };
  const wide = box(100, 760, 500, 30);
  const narrow = box(100, 760, 210, 30);
  assert.deepEqual(seat([{ start: chip(100, 770), target: wide }], { lineBox }), [
    { left: 302, top: 770 },
  ]);
  assert.deepEqual(seat([{ start: chip(100, 770), target: narrow }], { lineBox }), [
    { left: 100, top: 742 },
  ]);
});
