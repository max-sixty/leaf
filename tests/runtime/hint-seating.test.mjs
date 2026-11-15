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
    rows.map((_, at) => [at % 2 ? 64 : 90, true]),
  );
  assert.deepEqual(overlapping(seated.map(({ box }) => box)), []);
});

test("a crowded column whose codes grow a letter keeps both columns' left edges", () => {
  // Chips centre on their corners, so a longer code would start further left.
  const rows = Array.from({ length: 12 }, (_, at) => box(100, 100 + 14 * at, 300, 14));
  const seated = seatHints(
    rows.map((target, at) => {
      const width = at < 6 ? 20 : 30;
      return { start: box(100 - width / 2, target.top - 8, width, 16), target };
    }),
    { band: 2, viewport },
  );
  assert.deepEqual(
    seated.map(({ box }) => box.left),
    rows.map((_, at) => (at % 2 ? 49 : 85)),
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

test("a crowded row's chip steps out no further than a target beside the column", () => {
  // Stepped out past the narrow target beside the second row, its chip would stand
  // before that target and read as its.
  const rows = [box(100, 100, 300, 14), box(100, 114, 300, 14), box(60, 114, 30, 14)];
  const seated = seatHints(
    rows.map((target) => ({ start: chip(target.left - 10, target.top - 8), target })),
    { band: 2, viewport },
  );
  assert.equal(seated[1].box, null);
});

test("a walk onto a crowded row moves no chip where every row's chip stands", () => {
  const rows = Array.from({ length: 8 }, (_, at) => box(100, 100 + 14 * at, 300, 14));
  const faces = rows.map((target) => ({ start: chip(90, target.top - 8), target }));
  const lefts = (browsed) =>
    seatHints(faces, { band: 2, viewport, browsed }).map(({ box }) => box.left);
  assert.deepEqual(lefts(faces[3]), lefts(undefined));
});

test("a walk onto a row whose chip the window's edge withholds shows that chip", () => {
  const rows = Array.from({ length: 8 }, (_, at) => box(4, 100 + 14 * at, 300, 14));
  const faces = rows.map((target) => ({ start: chip(-6, target.top - 8), target }));
  const seated = seatHints(faces, { band: 2, viewport, browsed: faces[3] });
  assert.equal(middle(seated[3].box), middle(rows[3]));
  readsAsOwnRow(seated, rows);
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

test("a run of targets narrower than a key gets no chips, and a walk onto one shows its own", () => {
  // Adjacent footnote markers: no seat beside one says which of the three it names.
  const markers = [300, 308, 316].map((left) => box(left, 100, 8, 24));
  const faces = markers.map((target) => ({
    start: chip(target.left - 10, 92),
    target,
  }));
  const seatedWith = (browsed) =>
    seatHints(faces, { band: 2, viewport, browsed }).map(({ box }) => Boolean(box));
  assert.deepEqual(seatedWith(undefined), [false, false, false]);
  assert.deepEqual(seatedWith(faces[1]), [false, true, false]);
});

test("rows narrower than a key stacked one under another keep their chips", () => {
  // As a contents list's marks are: they share no line, so none is bunched.
  const marks = Array.from({ length: 5 }, (_, at) => box(100, 100 + 30 * at, 10, 20));
  assert.ok(
    seat(marks.map((target) => ({ start: chip(90, target.top - 8), target }))).every(
      Boolean,
    ),
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

test("chips side by side stand further apart than a code's own keycaps", () => {
  // A film's slots each as wide as a two-letter chip, whose seats above them would touch:
  // touching, `na` and `ng` read as `n a n g`.
  const slots = Array.from({ length: 8 }, (_, at) => box(100 + 30 * at, 100, 30, 60));
  const seated = seatHints(
    slots.map((target) => ({
      start: box(target.left, target.top, 30, 16),
      target,
      placement: "above",
    })),
    { band: 2, viewport },
  );
  const shown = seated.flatMap(({ box }) => (box ? [box] : []));
  assert.ok(shown.length > 1);
  for (const one of shown)
    for (const other of shown)
      if (one !== other && one.top < other.bottom && other.top < one.bottom)
        assert.ok(
          one.right + 6 <= other.left || other.right + 6 <= one.left,
          `${one.left}–${one.right} and ${other.left}–${other.right} stand side by side`,
        );
});

test("a before chip that would stand on a neighbouring target stands above its own", () => {
  const buttons = [box(100, 100, 100, 30), box(205, 100, 100, 30)];
  const before = (targets) =>
    seat(
      targets.map((target) => ({
        start: chip(target.left, target.top),
        target,
        placement: "before",
      })),
    );
  assert.deepEqual(before(buttons), [
    { left: 78, top: 107 },
    { left: 205, top: 82 },
  ]);
  // Where another target stands above it too, as in a grid of buttons, the chip stands
  // on its own target's corner.
  assert.deepEqual(
    before([...buttons, box(100, 135, 100, 30), box(205, 135, 100, 30)]),
    [
      { left: 78, top: 107 },
      { left: 205, top: 82 },
      { left: 78, top: 142 },
      { left: 205, top: 135 },
    ],
  );
  // The seat above is read where the window lets it stand: pushed in from the window's
  // right edge, it would read as the target above and left of its own, so the chip
  // stands on its own target's corner, its middle still nearer its own target.
  const edge = before([
    box(940, 100, 45, 30),
    box(990, 100, 10, 30),
    box(960, 65, 25, 25),
  ]);
  assert.deepEqual(edge[1], { left: 978, top: 100 });
  // A target around its own is no neighbour: the first slot of a film keeps its seat
  // before the film's edge, below the film's own chip rather than touching it, and the
  // next slot's chip stands above it.
  const film = box(100, 100, 300, 60);
  const slots = [box(110, 110, 30, 40), box(145, 110, 30, 40)];
  assert.deepEqual(
    seat(
      [film, ...slots].map((target) => ({
        start: chip(target.left, target.top),
        target,
        placement: "before",
      })),
    ),
    [
      { left: 68, top: 108 },
      { left: 88, top: 126 },
      { left: 145, top: 92 },
    ],
  );
});

test("a chip beside its own target reads as its own though another target's edge is nearer", () => {
  // A choice beside a card: its chip stands in the gutter, over the card's edge, level
  // with the choice.
  const card = box(40, 100, 297, 200);
  const choice = box(355, 150, 200, 30);
  assert.deepEqual(
    seat(
      [card, choice].map((target) => ({
        start: chip(target.left, target.top),
        target,
        placement: "before",
      })),
    )[1],
    { left: 333, top: 157 },
  );
  // A corner chip whose middle stands on its own target stands, though the link beside
  // overlaps that corner by a pixel.
  const links = [box(32, 480, 320, 22), box(351, 490, 226, 230)];
  assert.deepEqual(
    seat(
      links.map((target) => ({
        start: chip(target.left - 10, target.top - 8),
        target,
      })),
    ),
    [
      { left: 22, top: 472 },
      { left: 341, top: 482 },
    ],
  );
});

test("control chips sit above their own left edge, and before it where that seat reads as the control above", () => {
  const target = box(800, 400, 120, 30);
  // The chip's CSS centres its face on the seat. Its measured start already carries
  // that translation; outside placement follows the target edge rather than it.
  assert.deepEqual(seat([{ start: chip(790, 392), target, placement: "above" }]), [
    { left: 800, top: 382 },
  ]);
  const stacked = [box(800, 362, 120, 30), target];
  assert.deepEqual(
    seat(
      stacked.map((one) => ({
        start: chip(790, one.top - 8),
        target: one,
        placement: "above",
      })),
    ),
    [
      { left: 800, top: 344 },
      { left: 778, top: 407 },
    ],
  );
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

test("a target in no nest keeps its chip beside it, and one with no room before it does not narrow the step", () => {
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
  assert.deepEqual(lefts, [168, 178, 178, 10, 10]);
});
