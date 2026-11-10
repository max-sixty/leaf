/* Where a margin row stands: rail or pin, and how far down.

   A 1440px window with the column's padding box ending at 1057, so the rail's inner edge
   is 1079 and a 32px marker's half is 16. */

import assert from "node:assert/strict";
import test from "node:test";

import { overlaps } from "/runtime/rect.js";

import {
  arrivals,
  inSeatingOrder,
  packReach,
  packRow,
  pinSpot,
  rowPlacement,
  seatReach,
  seatRow,
  seatsBy,
  shiftedPin,
} from "/runtime/annotation-overlay/margin-placement.js";

const posture = (blockRight, over = {}) =>
  rowPlacement({
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

// The layout seats both postures in one shared order, carrying each final footprint.
const packRows = (rows, gap, occupied = []) => {
  const placed = [...occupied];
  return new Map(
    inSeatingOrder(rows).map((row) => {
      const push = packRow(row, gap, placed);
      placed.push({
        ...row.rect,
        top: row.rect.top + push,
        bottom: row.rect.bottom + push,
      });
      return [row.key, push];
    }),
  );
};

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
const seatSet = (seats) => ({
  before: seats.slice(0, 1),
  home: seats[1],
  after: seats.slice(2),
});
const pin = (over = {}) => {
  const value = {
    key: "card",
    came: 1,
    held: null,
    seats: [outside, corner, above],
    corner: 1,
    floor: 144,
    cover: [],
    controls: [],
    bounds: box(4, -Infinity, 386, Infinity),
    folds: null,
    folded: false,
    ...over,
  };
  if (Array.isArray(value.seats)) value.seats = seatSet(value.seats);
  if (value.folds && Array.isArray(value.folds.seats))
    value.folds = { ...value.folds, seats: seatSet(value.folds.seats) };
  return value;
};
const seatRows = (pins, { gap, occupied = [] }) => {
  const placed = [...occupied];
  return new Map(
    inSeatingOrder(pins.map((pin) => ({ ...pin, rect: pin.seats.home }))).map((pin) => {
      const seat = seatRow(pin, { gap, occupied: placed });
      placed.push(seat.rect);
      return [pin.key, seat];
    }),
  );
};
const seatOf = (...pins) => seatRows(pins, { gap: 4 });

test("a pin takes the first of its seats that stands inside its bounds and covers nothing", () => {
  assert.deepEqual(pinSpot([outside, corner, above], [], box(4, 0, 500, 900)), outside);
  assert.deepEqual(seatOf(pin()).get("card"), { rect: corner, folded: false });
  assert.deepEqual(seatOf(pin({ cover: [title] })).get("card"), {
    rect: above,
    folded: false,
  });
});

test("a pin whose corner holds words takes the first clear spot down its target's edge", () => {
  // A taller target: its first line runs to the corner, its second ends short of it.
  const tall = pin({ floor: 300, cover: [title, box(24, 148, 200, 184)] });
  assert.deepEqual(seatOf(tall).get("card").rect, box(318, 144, 362, 188));
  // Below its floor is not the target's, so a short one takes the room above instead.
  assert.deepEqual(seatOf(pin({ cover: [title] })).get("card").rect, above);
});

test("with no clear seat, a pin stands over words but keeps off a control", () => {
  // The card's own words fill its corner, and the heading's the room above: the pin
  // takes whichever covers less.
  assert.deepEqual(seatOf(pin({ cover: [heading, title] })).get("card").rect, corner);
  const short = box(24, 60, 330, 96);
  assert.deepEqual(seatOf(pin({ cover: [short, title] })).get("card").rect, above);
  // A control at the corner, an option's mark beside a short title, slides the pin left
  // past it into the room the title leaves, rather than over the heading's words.
  assert.deepEqual(
    seatOf(pin({ cover: [heading, action], controls: [action] })).get("card").rect,
    box(252, 100, 296, 144),
  );
  // A title set right against the control leaves its room on its other side.
  const right = box(200, 104, 296, 140);
  assert.deepEqual(
    seatOf(pin({ cover: [heading, right, action], controls: [action] })).get("card")
      .rect,
    box(152, 100, 196, 144),
  );
  // Where the title runs from the control to the target's left edge, every room along
  // the top is words, and the pin takes the heading's end instead.
  const long = box(24, 104, 296, 140);
  assert.deepEqual(
    seatOf(pin({ cover: [heading, long, action], controls: [action] })).get("card")
      .rect,
    above,
  );
  // Controls in every seat slide the pin left along its target's top, past them.
  const buttons = [box(300, 40, 386, 150)];
  assert.deepEqual(
    seatOf(pin({ cover: buttons, controls: buttons })).get("card").rect,
    box(252, 100, 296, 144),
  );
  // A corner past the bounds' foot is brought inside them before it slides.
  const low = [box(300, 86, 386, 130)];
  assert.deepEqual(
    seatOf(pin({ cover: low, controls: low, bounds: box(4, -Infinity, 386, 130) })).get(
      "card",
    ).rect,
    box(252, 86, 296, 130),
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
  // The layout pass seats one pin at a time, handing over what is already placed.
  const alone = seatRows([pin({ cover: filled, controls: filled })], {
    gap: 4,
    occupied: [corner],
  });
  assert.deepEqual(alone.get("card").rect, box(318, 148, 362, 192));
  // A push that would leave the bounds keeps the corner instead.
  const short = seatRows(
    [pin({ cover: filled, controls: filled, bounds: box(4, 40, 386, 150) })],
    { gap: 4, occupied: [corner] },
  );
  assert.deepEqual(short.get("card").rect, corner);
});

test("a pin crowded off its seats takes the less covered of slid aside and pushed below", () => {
  // A pin already stands in the corner and a control above it; words run to 300px.
  const heading = box(24, 60, 366, 96);
  const words = box(24, 104, 300, 140);
  const crowded = (occupied) =>
    seatRows([pin({ cover: [heading, words], controls: [heading] })], {
      gap: 4,
      occupied,
    }).get("card").rect;
  // Slid left it would cover the words' end; pushed below the other pin, nothing.
  assert.deepEqual(crowded([corner]), box(318, 148, 362, 192));
  // Pushed past the room read below the target, what it covers is unknown, so the pin
  // takes the slid seat.
  assert.deepEqual(crowded([corner, box(318, 148, 362, 192)]), box(270, 100, 314, 144));
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

test("a seat the layout pass does not offer is passed over, at either size", () => {
  // The outside seat is not offered, as where another block stands beside the card.
  assert.deepEqual(
    seatOf(pin({ seats: [null, corner, above] })).get("card").rect,
    corner,
  );
  // With every offered seat over words, the pin takes the one covering least of them.
  const crowded = pin({ seats: [null, corner, above], cover: [box(24, 40, 386, 150)] });
  assert.deepEqual(seatOf(crowded).get("card").rect, corner);
  // Folded, its width is read from the corner seat, which is always offered.
  const input = pin({
    seats: [null, wide(corner), wide(above)],
    cover: [box(24, 60, 300, 96), box(250, 104, 300, 140)],
    controls: [box(250, 104, 300, 140)],
    folds: { ...folds, seats: [null, ...folds.seats.slice(1)] },
  });
  assert.deepEqual(seatOf(input).get("card"), { rect: corner, folded: true });
});

test("a seat beside its subject is offered only where no other block stands level", () => {
  // A 44px pin by a run of words whose last line, 27px tall, ends short of the first.
  const lines = [box(24, 600, 300, 627), box(24, 627, 270, 654)];
  const home = box(256, 600, 300, 644);
  const blocks = (...standing) => ({
    cover: [],
    beside: (rect) => standing.some((block) => overlaps(block, rect)),
  });
  const seats = (room) => seatsBy(lines, home, true, true, room, 44, 4);
  const corner = box(304, 600, 348, 644);
  const afterWord = box(274, 627, 318, 671);
  assert.deepEqual(seats(blocks()).before, [corner, afterWord]);
  // The next block starts 15px below the last line: the pin after it overhangs that
  // block and still reads as the line's, so both seats stay offered.
  const below = box(24, 669, 400, 720);
  assert.deepEqual(seats(blocks(below)).before, [corner, afterWord]);
  // A block level with the words, as the next column's card stands, takes both away;
  // the seat inside the corner keeps its index.
  const offered = seats(blocks(box(308, 560, 400, 720)));
  assert.deepEqual(
    { before: offered.before, home: offered.home },
    { before: [null, null], home: { ...home, left: 256 } },
  );
});

test("a pin level with a code line stands at the block's edge, or left of a control there", () => {
  // A line of code running to the block's right edge, and Copy over that edge.
  const line = box(24, 100, 366, 116);
  const edge = box(318, 95, 362, 121);
  const copy = box(334, 92, 362, 120);
  const level = (over) =>
    seatOf(
      pin({ level: true, seats: [null, edge], floor: 121, cover: [line], ...over }),
    ).get("card").rect;
  // Over the line's last words, where seats beside it would leave the line.
  assert.deepEqual(level({}), edge);
  // Off a control, slid left along the line rather than up, down or to the window's edge.
  assert.deepEqual(level({ controls: [copy] }), box(286, 95, 330, 121));
  const held = box(200, 95, 244, 121);
  assert.deepEqual(level({ held }), held);
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

// Footprints scattered over the card or the rail, from a seeded generator so a failure
// repeats.
const scatterer = (seed) => {
  const random = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const scatter = (count, left = 0, width = 420) =>
    Array.from({ length: count }, () => {
      const at = { left: left + random() * width, top: random() * 320 };
      return {
        ...at,
        right: at.left + 8 + random() * 90,
        bottom: at.top + 8 + random() * 60,
      };
    });
  // `kept` in its order, with each of `added` put in at a random place.
  const interleave = (kept, added) => {
    const all = [...kept];
    for (const one of added)
      all.splice(Math.floor(random() * (all.length + 1)), 0, one);
    return all;
  };
  return { scatter, interleave };
};

test("a footprint outside a pin's reach leaves its seat as it was", () => {
  // What the layout relies on to keep a row's seat when only rows elsewhere changed
  // (margin-layout.js, `seatings`): footprints added or taken away where they miss the
  // reach leave the pin its seat.
  const { scatter, interleave } = scatterer(11);
  const crowd = [box(24, 60, 366, 96), box(24, 104, 300, 140)];
  const pins = [
    pin(),
    pin({ cover: [title] }),
    pin({ floor: 300, cover: [title, box(24, 148, 200, 184)] }),
    pin({ cover: crowd, controls: [crowd[0]] }),
    pin({ seats: [outside, corner, above].map(wide), cover: crowd, folds }),
    pin({ level: true, seats: [null, corner], floor: 144, cover: [title] }),
    pin({ cover: crowd, controls: crowd, bounds: box(4, 40, 386, 260) }),
  ];
  let moved = 0;
  for (let round = 0; round < 2000; round += 1) {
    const input = pins[round % pins.length];
    const occupied = scatter(5);
    const seat = seatRow(input, { gap: 4, occupied });
    const reach = seatReach(input, seat.rect, 4);
    const within = occupied.filter((one) => overlaps(one, reach));
    const missing = scatter(12).filter((one) => !overlaps(one, reach));
    const again = seatRow(input, { gap: 4, occupied: interleave(within, missing) });
    assert.deepEqual(again, seat, JSON.stringify({ round, occupied, reach }));
    if (seatRow(input, { gap: 4 }).rect.top !== seat.rect.top) moved += 1;
  }
  // The footprints moved enough of the pins that keeping their seats proves something.
  assert.ok(moved > 40, `only ${moved} pins sat anywhere but where they sit alone`);
});

test("a footprint outside a rail row's reach leaves its push as it was", () => {
  const { scatter, interleave } = scatterer(5);
  let pushed = 0;
  for (let round = 0; round < 400; round += 1) {
    const held = round % 5 === 0;
    const row = {
      rect: rect(1079, 40 + (round % 7) * 30),
      held,
      pushed: held ? 12 : 0,
    };
    const occupied = scatter(6, 1040, 120);
    const push = packRow(row, 4, occupied);
    const reach = packReach(row, push, 4);
    const within = occupied.filter((one) => overlaps(one, reach));
    const missing = scatter(12, 1040, 120).filter((one) => !overlaps(one, reach));
    assert.equal(packRow(row, 4, interleave(within, missing)), push, `round ${round}`);
    if (push !== row.pushed) pushed += 1;
  }
  assert.ok(pushed > 40, `only ${pushed} rows were pushed`);
});

test("a pin read before a scroll seats where the scroll carried its seat", () => {
  const crowd = [box(24, 60, 366, 96), box(24, 104, 300, 140)];
  const input = pin({ seats: [outside, corner, above].map(wide), cover: crowd, folds });
  const occupied = [corner, box(318, 148, 362, 192)];
  /** @param {{left: number, right: number, top: number, bottom: number}} one */
  const carry = (one) => ({
    left: one.left + 13,
    right: one.right + 13,
    top: one.top - 250,
    bottom: one.bottom - 250,
  });
  const { rect: seat, folded } = seatRow(input, { gap: 4, occupied });
  assert.deepEqual(
    seatRow(shiftedPin(input, 13, -250), { gap: 4, occupied: occupied.map(carry) }),
    { rect: carry(seat), folded },
  );
});
