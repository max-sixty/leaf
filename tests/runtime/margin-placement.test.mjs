/* Where a margin row stands: rail or pin, and how far down.

   A 1440px window with the column's padding box ending at 1057, so the rail's inner edge
   is 1079 and a 32px marker's half is 16. */

import assert from "node:assert/strict";
import test from "node:test";

import {
  arrivals,
  packRows,
  pinSpot,
  rowPosture,
  seatRows,
} from "/runtime/annotation-overlay/margin-placement.js";

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
      { key: "b", rect: rect(1079, 110) },
      { key: "a", rect: rect(1079, 100) },
      { key: "c", rect: rect(1079, 300) },
    ],
    4,
  );
  assert.deepEqual(Object.fromEntries(pushes), { a: 0, b: 26, c: 0 });
});

test("rail rows in separate bands stay where they are", () => {
  const pushes = packRows(
    [
      { key: "rail", rect: rect(1079, 100) },
      { key: "aside", rect: rect(900, 100) },
    ],
    4,
  );
  assert.deepEqual(Object.fromEntries(pushes), { rail: 0, aside: 0 });
});

test("a row that came earlier keeps its place and one that has just come moves", () => {
  const pushes = packRows(
    [
      { key: "late", rect: rect(1079, 90), came: 2 },
      { key: "first", rect: rect(1079, 100), came: 1 },
    ],
    4,
  );
  assert.deepEqual(Object.fromEntries(pushes), { first: 0, late: 46 });
});

test("a held row is packed from where it stands, not from its home", () => {
  // Held where it was pushed to, `late` stays there, and `first` keeps its place too.
  const pushes = packRows(
    [
      { key: "late", rect: rect(1079, 90), came: 2, held: true, pushed: 46 },
      { key: "first", rect: rect(1079, 100), came: 1 },
    ],
    4,
  );
  assert.deepEqual(Object.fromEntries(pushes), { late: 46, first: 0 });
});

test("rows are packed from the top, so a push carries on down the stack", () => {
  const pushes = packRows(
    [
      { key: "a", rect: rect(1079, 100) },
      { key: "b", rect: rect(1079, 136) },
      { key: "c", rect: rect(1079, 104) },
    ],
    4,
  );
  // c goes under a, which is where b stands, so b goes under c.
  assert.deepEqual(Object.fromEntries(pushes), { a: 0, c: 32, b: 36 });
});

// A card at a phone's width, 342px of column in a 390px window, and its pin's seats as
// the layout pass offers them for a 44px marker: just outside the card's top-right
// corner, just inside it, and just above it. The first stands past the window's edge.
const box = (left, top, right, bottom) => ({ left, top, right, bottom });
const outside = box(370, 100, 414, 144);
const corner = box(318, 100, 362, 144);
const above = box(322, 52, 366, 96);
const heading = box(24, 60, 366, 96);
const title = box(24, 104, 362, 140);
const action = box(300, 104, 362, 140);
const pin = (over = {}) => ({
  key: "card",
  came: 1,
  held: null,
  seats: [outside, corner, above],
  corner: 1,
  cover: [],
  controls: [],
  bounds: box(4, -Infinity, 386, Infinity),
  folds: null,
  folded: false,
  ...over,
});
const seatOf = (...pins) => seatRows(pins, { gap: 4 });

test("a pin takes the first of its seats that stands inside its bounds and covers nothing", () => {
  assert.deepEqual(pinSpot([outside, corner, above], [], box(4, 0, 500, 900)), outside);
  assert.deepEqual(seatOf(pin()).get("card"), { rect: corner, folded: false });
  assert.deepEqual(seatOf(pin({ cover: [title] })).get("card"), {
    rect: above,
    folded: false,
  });
});

test("with no clear seat, a pin stands over words but keeps off a control", () => {
  // The card's own words fill its corner, and the heading's the room above: the pin
  // takes whichever covers less.
  assert.deepEqual(seatOf(pin({ cover: [heading, title] })).get("card").rect, corner);
  const short = box(24, 60, 330, 96);
  assert.deepEqual(seatOf(pin({ cover: [short, title] })).get("card").rect, above);
  // A control at the corner sends the pin over the heading's words instead.
  assert.deepEqual(
    seatOf(pin({ cover: [heading, action], controls: [action] })).get("card").rect,
    above,
  );
  // Controls in every seat slide the pin left along its target's top, past them.
  const buttons = [box(300, 40, 386, 150)];
  assert.deepEqual(
    seatOf(pin({ cover: buttons, controls: buttons })).get("card").rect,
    box(252, 100, 296, 144),
  );
  // With no room left of them either, the pin keeps its corner, over the controls.
  const across = [box(4, 40, 386, 150)];
  assert.deepEqual(
    seatOf(pin({ cover: across, controls: across })).get("card").rect,
    corner,
  );
});

test("a pin that finds every seat taken by pins before it stands below them", () => {
  const filled = [box(4, 40, 386, 150)];
  const seats = seatOf(
    pin({ key: "first", cover: filled, controls: filled }),
    pin({ key: "second", came: 2, cover: filled, controls: filled }),
  );
  assert.deepEqual(seats.get("first").rect, corner);
  assert.deepEqual(seats.get("second").rect, box(318, 148, 362, 192));
});

// The same card's pin folded to its one control, opening leftward to 140px.
const folds = {
  seats: [outside, corner, above].map((seat) => ({ ...seat, left: seat.right - 44 })),
  open: 140,
};
const wide = (seat) => ({ ...seat, left: seat.right - 96 });

test("a pin with no clear seat for its face stands folded where one control finds one", () => {
  // The whole face would cover the card's Action and the heading's end above; the
  // toggle alone clears both, in the card's corner.
  const cover = [box(24, 60, 300, 96), box(250, 104, 300, 140)];
  const input = pin({
    seats: [outside, corner, above].map(wide),
    cover,
    controls: [cover[1]],
    folds,
  });
  assert.deepEqual(seatOf(input).get("card"), { rect: corner, folded: true });
});

test("a folded pin stands only where its opened actions stay inside its bounds", () => {
  const input = pin({
    seats: [outside, corner, above].map(wide),
    cover: [box(24, 40, 386, 150)],
    folds,
    bounds: box(200, -Infinity, 386, Infinity),
  });
  // Every seat covers words, so the toggle takes the first whose opened actions stay
  // inside the bounds, over those words.
  const seat = seatOf(input).get("card");
  assert.deepEqual(seat, { rect: corner, folded: true });
  assert.ok(seat.rect.right - folds.open >= 200, JSON.stringify(seat));
});

test("a held pin keeps its seat, and one that no longer fits its bounds is seated again", () => {
  const held = box(200, 300, 244, 344);
  assert.deepEqual(seatOf(pin({ held, cover: [held] })).get("card").rect, held);
  const narrowed = seatOf(pin({ held: box(380, 100, 424, 144) })).get("card");
  assert.deepEqual(narrowed.rect, corner);
});

test("a folded pin held open keeps its fold, and the others keep to its toggle", () => {
  // Open under the finger, the pin is three controls wide, its toggle at the right.
  const open = box(222, 52, 366, 96);
  const seats = seatOf(
    pin({ held: open, folded: true, folds }),
    pin({ key: "beside", came: 2, seats: [box(240, 52, 284, 96), corner] }),
  );
  assert.deepEqual(seats.get("card"), { rect: above, folded: true });
  assert.deepEqual(seats.get("beside").rect, box(240, 52, 284, 96));
});

test("a pin that came earlier is seated first, and a held pin before either", () => {
  const seats = seatOf(pin({ key: "second", came: 2 }), pin({ key: "first" }));
  assert.deepEqual(seats.get("first").rect, corner);
  assert.deepEqual(seats.get("second").rect, above);
  const held = seatOf(
    pin({ key: "second", came: 2, held: corner }),
    pin({ key: "first" }),
  );
  assert.deepEqual(held.get("second").rect, corner);
  assert.deepEqual(held.get("first").rect, above);
});

test("a held row is packed first, so nothing pushes it from under the press", () => {
  const pushes = packRows(
    [
      { key: "first", rect: rect(1079, 100), came: 1 },
      { key: "held", rect: rect(1079, 110), came: 2, held: true },
    ],
    4,
  );
  assert.deepEqual(Object.fromEntries(pushes), { held: 0, first: 46 });
});

test("a row is news only when neither it nor what it stands by was there", () => {
  const [row, rebuilt, target, replaced, other] = ["row", "rebuilt", "t", "t2", "o"];
  const last = arrivals(new Map(), [{ row, at: target }], 1);
  // Built again for the same target, as an edit shifting an id-less path does.
  assert.equal(arrivals(last, [{ row: rebuilt, at: target }], 4).get(rebuilt), 1);
  // Its target's node replaced under the same key, the row kept.
  assert.equal(arrivals(last, [{ row, at: replaced }], 4).get(row), 1);
  // Both new: a row arriving.
  assert.equal(arrivals(last, [{ row: other, at: replaced }], 4).get(other), 4);
});

test("a hidden row keeps the pass it came at, and what has no row is forgotten", () => {
  const last = arrivals(new Map(), [{ row: "row", at: "t" }], 1);
  const hidden = arrivals(last, [{ row: "row", at: null }], 2);
  assert.equal(arrivals(hidden, [{ row: "row", at: "t" }], 3).get("row"), 1);
  // The row gone for a pass, a row its target gains later is news.
  const gone = arrivals(last, [], 2);
  assert.equal(arrivals(gone, [{ row: "new", at: "t" }], 3).get("new"), 3);
});

test("rail packing preserves already held pin footprints", () => {
  const held = rect(1141, 162, 31, 26);
  const pushes = packRows([{ key: "rail", rect: rect(1126, 162) }], 4, [held]);
  assert.equal(pushes.get("rail"), 30);
});
