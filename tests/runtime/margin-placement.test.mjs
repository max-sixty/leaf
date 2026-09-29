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
  const pushes = packRows(
    [{ key: "pin", rect: rect(1045, 96), priority: 10, fixed: [grip] }],
    4,
  );
  assert.deepEqual(Object.fromEntries(pushes), { pin: 22 });
  // A control beside the pin rather than under it moves nothing.
  const aside = packRows(
    [
      {
        key: "pin",
        rect: rect(1045, 96),
        priority: 10,
        fixed: [{ left: 900, right: 916, top: 98, bottom: 114 }],
      },
    ],
    4,
  );
  assert.deepEqual(Object.fromEntries(aside), { pin: 0 });
});

// A paragraph's last two lines at a phone's width, 366px of column in a 390px window:
// the first fills its line, and a run that starts on it ends 280px into the second. The
// next block starts 30px below.
const box = (left, top, right, bottom) => ({ left, top, right, bottom });
const words = [box(24, 100, 366, 121), box(24, 127, 280, 148)];
const spot = (cover, neighbours = [], walls = []) =>
  pinSpot({
    // A 44px marker level with the run's last line, just after its end.
    seat: box(284, 115.5, 328, 159.5),
    home: box(318, 100, 362, 144),
    parts: [box(160, 100, 366, 121), box(24, 127, 280, 148)],
    cover,
    walls,
    neighbours,
    others: [],
    bounds: box(4, -Infinity, 386, Infinity),
    reach: 12,
    line: 27,
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

test("a box in cover counts whole, so a pin with no room of its own stays home", () => {
  // Brought up to the paragraph, a block that paints its box (`coverIn`) leaves the
  // last line too little room below, though no word stands in its top 20px; the pin
  // stands in the leading above the run instead.
  const below = box(24, 152, 366, 260);
  assert.deepEqual(spot([...words, below]), box(284, 52, 328, 96));
  // With a painted heading 10px above the paragraph, that room is the heading's, and
  // the room above the heading lies further out than a line.
  const painted = box(24, 40, 366, 90);
  assert.deepEqual(
    spot([...words, below, painted], [], [below, painted]),
    box(318, 100, 362, 144),
  );
});

test("where its target has no room, a pin takes a neighbour's empty end", () => {
  // The same heading painting nothing is a neighbour: its words end at 111px, and the
  // pin stands past them, within reach of the run, rather than over the run's words.
  const below = box(24, 152, 366, 260);
  assert.deepEqual(
    spot([...words, below, box(24, 50, 111, 80)], [box(24, 40, 366, 90)]),
    box(284, 52, 328, 96),
  );
});

test("a pin keeps to its target's own room before a neighbour's empty end", () => {
  // A block whose heading line fills the corner seat: room below that line is its own,
  // though the empty end of the paragraph above is nearer the seat, and a pin there
  // would read as the paragraph's.
  const corner = box(340, 100, 366, 126);
  const place = (neighbours) =>
    pinSpot({
      seat: corner,
      home: corner,
      parts: [box(24, 100, 366, 300)],
      cover: [
        box(24, 100, 366, 130),
        box(24, 180, 200, 200),
        box(24, 20, 366, 41),
        box(24, 69, 100, 90),
      ],
      walls: [],
      neighbours,
      others: [],
      bounds: box(4, -Infinity, 386, Infinity),
      reach: 12,
      line: 27,
      gap: 4,
    });
  assert.deepEqual(place([box(24, 20, 366, 90)]), box(340, 134, 366, 160));
  // Were the paragraph above not a neighbour, its empty end would be the nearer room.
  assert.deepEqual(place([]), box(340, 70, 366, 96));
});

// A section at a phone's width: a framed draft above, then the heading "API", whose
// word ends at 62px, and a paragraph whose first line is full. A deletion starts on the
// paragraph's second line and ends 278px into its third, and another framed draft starts
// just below, so no room of a 96px pair touches the run.
const draft = box(24, 469, 366, 573);
const heading = box(24, 621, 366, 651);
const api = box(24, 621, 62, 651);
const lines = [box(24, 667, 309, 688), box(24, 694, 316, 715), box(24, 721, 278, 742)];
const next = box(24, 761, 366, 900);
const section = {
  seat: box(282, 709.5, 378, 753.5),
  home: box(270, 694, 366, 738),
  parts: [box(162, 694, 316, 715), box(24, 721, 278, 742)],
  cover: [draft, api, ...lines, next],
  walls: [draft, next],
  neighbours: [heading],
  others: [],
  bounds: box(4, -Infinity, 386, Infinity),
  reach: 12,
  line: 27,
  gap: 4,
};

test("with no room within reach, a pin reaches past a line of words", () => {
  // The heading's empty end stands one full line above the run's first part, 31px out.
  assert.deepEqual(pinSpot(section), box(282, 619, 378, 663));
  // A line further than that is too far: with the paragraph a line longer, the pin
  // stays home.
  const lower = (b) => box(b.left, b.top + 27, b.right, b.bottom + 27);
  assert.deepEqual(
    pinSpot({
      ...section,
      seat: lower(section.seat),
      home: lower(section.home),
      parts: section.parts.map(lower),
      cover: [draft, api, lines[0], ...lines.map(lower), lower(next)],
      walls: [draft, lower(next)],
    }),
    lower(section.home),
  );
});

test("a pin reaching further passes no wall and no other pin's target", () => {
  // A rule drawn across the top of the paragraph lies between the heading and the run.
  const rule = box(24, 664, 366, 666);
  assert.deepEqual(
    pinSpot({
      ...section,
      cover: [...section.cover, rule],
      walls: [draft, rule, next],
    }),
    section.home,
  );
  // With the heading a pin's target, a pin on its empty end would read as that one's,
  // and so it would with a pin's target on the heading's line, though further off.
  assert.deepEqual(pinSpot({ ...section, others: [heading] }), section.home);
  assert.deepEqual(pinSpot({ ...section, others: [api] }), section.home);
});

test("a pin that reaches further keeps to its own target's pins", () => {
  // A comment on the whole section holds the run, so its target does not keep the
  // run's pin from the heading's end; a comment on the heading does.
  const pin = (key, parts, priority) => ({
    ...section,
    key,
    rect: section.home,
    priority,
    held: null,
    parts,
    cover: section.cover,
  });
  const run = pin("run", section.parts, 10);
  const whole = {
    ...pin("section", [box(24, 621, 366, 900)], 20),
    seat: box(342, 621, 366, 645),
  };
  assert.deepEqual(
    seatRows([run, whole], { reach: 12, gap: 4 }).get("run"),
    box(282, 619, 378, 663),
  );
  const titled = { ...pin("heading", [heading], 20), seat: box(342, 621, 366, 645) };
  assert.deepEqual(
    seatRows([run, titled], { reach: 12, gap: 4 }).get("run"),
    section.home,
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
  walls: [box(24, 178, 366, 260)],
  neighbours: [],
  line: 27,
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
