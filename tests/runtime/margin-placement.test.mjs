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
} from "/runtime/margin-placement.js";

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

test("a pin and a rail marker level with each other both stay where they are", () => {
  const pushes = packRows(
    [
      { key: "rail", rect: rect(1079, 100) },
      { key: "pin", rect: rect(900, 100) },
    ],
    4,
  );
  assert.deepEqual(Object.fromEntries(pushes), { rail: 0, pin: 0 });
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

test("a pin level with a control of the page goes below it", () => {
  const grip = { left: 1060, right: 1076, top: 98, bottom: 114 };
  const pushes = packRows([{ key: "pin", rect: rect(1045, 96), fixed: [grip] }], 4);
  assert.deepEqual(Object.fromEntries(pushes), { pin: 22 });
  // A control beside the pin rather than under it moves nothing.
  const aside = packRows(
    [
      {
        key: "pin",
        rect: rect(1045, 96),
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

test("a box in cover counts whole, so a pin with no room of its own finds none", () => {
  // Brought up to the paragraph, a block that paints its box (`coverIn`) leaves the
  // last line too little room below, though no word stands in its top 20px; the pin
  // stands in the leading above the run instead.
  const below = box(24, 152, 366, 260);
  assert.deepEqual(spot([...words, below]), box(284, 52, 328, 96));
  // With a painted heading 10px above the paragraph, that room is the heading's, and
  // the room above the heading lies further out than a line.
  const painted = box(24, 40, 366, 90);
  assert.equal(spot([...words, below, painted], [], [below, painted]), null);
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
  rect: box(270, 694, 366, 738),
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

// The same section with the paragraph a line longer, so the run starts a line lower.
const lower = (b) => box(b.left, b.top + 27, b.right, b.bottom + 27);
const longer = {
  ...section,
  seat: lower(section.seat),
  rect: lower(section.rect),
  parts: section.parts.map(lower),
  cover: [draft, api, lines[0], ...lines.map(lower), lower(next)],
  walls: [draft, lower(next)],
};

test("with no room within reach, a pin reaches past a line of words", () => {
  // The heading's empty end stands one full line above the run's first part, 31px out.
  assert.deepEqual(pinSpot(section), box(282, 619, 378, 663));
  // A line further than that is too far: with the paragraph a line longer, the pin
  // finds no room.
  assert.equal(pinSpot(longer), null);
});

test("a pin reaching further passes no wall and no other pin's target", () => {
  // A rule drawn across the top of the paragraph lies between the heading and the run.
  const rule = box(24, 664, 366, 666);
  assert.equal(
    pinSpot({
      ...section,
      cover: [...section.cover, rule],
      walls: [draft, rule, next],
    }),
    null,
  );
  // With the heading a pin's target, a pin on its empty end would read as that one's,
  // and so it would with a pin's target on the heading's line, though further off.
  assert.equal(pinSpot({ ...section, others: [heading] }), null);
  assert.equal(pinSpot({ ...section, others: [api] }), null);
});

test("a pin that reaches further keeps to its own target's pins", () => {
  // A comment on the whole section holds the run, so its target does not keep the
  // run's pin from the heading's end; a comment on the heading does.
  const pin = (key, parts, came) => ({
    ...section,
    key,
    came,
    held: null,
    parts,
    cover: section.cover,
  });
  const run = pin("run", section.parts, 1);
  const whole = {
    ...pin("section", [box(24, 621, 366, 900)], 2),
    seat: box(342, 621, 366, 645),
  };
  assert.deepEqual(seatRows([run, whole], { reach: 12, gap: 4 }).get("run"), {
    rect: box(282, 619, 378, 663),
    folded: false,
  });
  const titled = { ...pin("heading", [heading], 2), seat: box(342, 621, 366, 645) };
  assert.deepEqual(seatRows([run, titled], { reach: 12, gap: 4 }).get("run"), {
    rect: section.rect,
    folded: false,
  });
});

// The longer section's pin as `seatRows` takes it: the pair, and folded, one 44px
// control, the toggle to its options, which opens 140px wide to Accept, Reject and the
// toggle.
const pair = (over = {}) => ({
  ...longer,
  key: "pair",
  held: null,
  folds: {
    rect: box(322, longer.rect.top, 366, longer.rect.bottom),
    seat: box(282, longer.seat.top, 326, longer.seat.bottom),
    open: 140,
  },
  folded: false,
  ...over,
});
const seatOf = (pins) => seatRows(pins, { reach: 12, gap: 4 }).get("pair");

test("a pin with no room for its face stands folded where one control finds room", () => {
  // Past the end of the line above the run's last, level with that last line.
  assert.deepEqual(seatOf([pair()]), {
    rect: box(320, 736.5, 364, 780.5),
    folded: true,
  });
  // One that finds room for its face keeps it whole.
  assert.deepEqual(
    seatOf([
      pair({
        ...section,
        folds: {
          rect: box(322, 694, 366, 738),
          seat: box(282, 709.5, 326, 753.5),
          open: 140,
        },
      }),
    ]),
    { rect: box(282, 619, 378, 663), folded: false },
  );
});

test("cramped pins remain reachable within their bounds", () => {
  const crowded = [...longer.cover, box(4, 560, 386, 900)];
  for (const input of [pair({ folds: null }), pair({ cover: crowded })]) {
    const seat = seatOf([input]);
    assert.ok(seat);
    assert.ok(seat.rect.right > seat.rect.left && seat.rect.bottom > seat.rect.top);
    assert.ok(
      seat.rect.left >= input.bounds.left && seat.rect.right <= input.bounds.right,
    );
    if (input.folds === null) assert.equal(seat.folded, false);
  }
});

test("a folded pin stands only where its opened actions stay inside its bounds", () => {
  // A one-word run at the column's left edge, in full lines, with room for one control
  // only above its paragraph's first line, left of a framed block. The toggle would fit
  // there, but it opens leftward to 140px, past the window's left edge; so it takes its
  // home instead, moved right until the opened pin fits inside the window.
  const walls = [box(4, 560, 386, 650), box(100, 650, 386, 717), box(4, 800, 386, 900)];
  const lines = [
    box(24, 721, 366, 742),
    box(24, 748, 366, 769),
    box(24, 775, 366, 796),
  ];
  const edge = pair({
    seat: box(66, 736.5, 162, 780.5),
    rect: box(-38, 748, 58, 792),
    parts: [box(24, 748, 62, 769)],
    cover: [...walls, ...lines],
    walls,
    neighbours: [],
    folds: {
      rect: box(14, 748, 58, 792),
      seat: box(66, 736.5, 110, 780.5),
      open: 140,
    },
  });
  assert.deepEqual(seatOf([edge]), { rect: box(100, 748, 144, 792), folded: true });
  // Opening no wider than itself, the same pin takes the room above.
  const narrow = seatOf([{ ...edge, folds: { ...edge.folds, open: 44 } }]);
  assert.equal(narrow.folded, true);
  assert.ok(narrow.rect.bottom <= 717, narrow);
  // Bounds narrower than the opened pin, as in a thin pane, keep the toggle inside them.
  const thin = seatOf([{ ...edge, folds: { ...edge.folds, open: 600 } }]);
  assert.equal(thin.folded, true);
  assert.ok(thin.rect.right <= edge.bounds.right, thin);
});

test("a folded pin held open keeps its fold, and the others keep to its toggle", () => {
  // Open under the finger, the pin is three controls wide, its toggle at the right.
  const open = box(222, 736.5, 364, 780.5);
  const seats = seatRows(
    [
      pair({ held: open, folded: true }),
      {
        ...pair({ key: "beside" }),
        // A pin whose seat is where the open pin's actions now stand.
        seat: box(230, 740, 274, 784),
        parts: [box(24, 748, 226, 769)],
        folds: null,
        cover: [],
        walls: [],
      },
    ],
    { reach: 12, gap: 4 },
  );
  assert.deepEqual(seats.get("pair"), {
    rect: box(320, 736.5, 364, 780.5),
    folded: true,
  });
  assert.deepEqual(seats.get("beside"), {
    rect: box(230, 740, 274, 784),
    folded: false,
  });
});

// Two pins by the same run: `first` came at an earlier pass than `second`.
const seat = box(284, 115.5, 328, 159.5);
const pin = (key, came, held = null) => ({
  key,
  came,
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

test("a pin that came earlier is seated first, and a later one keeps clear of it", () => {
  const seats = seatRows([pin("second", 2), pin("first", 1)], {
    reach: 12,
    gap: 4,
  });
  assert.deepEqual(seats.get("first").rect, seat);
  assert.ok(!overlap(seats.get("second").rect, seat), seats);
});

test("a held pin keeps its seat, and a pin that came earlier takes other room", () => {
  // `second` is under the pointer, at the seat `first` would otherwise take.
  const seats = seatRows([pin("second", 2, seat), pin("first", 1)], {
    reach: 12,
    gap: 4,
  });
  assert.deepEqual(seats.get("second").rect, seat);
  assert.ok(!overlap(seats.get("first").rect, seat), seats);
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
