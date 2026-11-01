/* Where a margin row stands, folded from rectangles the layout pass has already read.

   A row stands in one of two postures. In the rail it hangs off the column, in the strip
   the page reserves beside it. As a pin it stands over the page by its target, on the
   first seat touching the target that covers nothing (`seatRow`). Nothing here
   moves the page's content: a row's posture, seat and push are the row's own geometry.
   The layout pass writes them as `--lf-margin-x` and `--lf-margin-y`, which
   annotation-theme.css reads at .lf-margin-cluster; only the carrier a row stands in is
   anchor-positioned.

   The layout pass (`margin-layout.js`) reads every rectangle first, asks these folds, and
   then writes. Each fold answers from its arguments alone, so `tests/runtime/` runs them
   without a browser. */

import { clamp, overlaps, overlapsAcross, union } from "../rect.js";

/** @typedef {import("../rect.js").Box} Box */
/** @typedef {{before: readonly (Box | null)[], home: Box, after: readonly (Box | null)[]}} SeatSet */
/** @typedef {{rect: Box, came?: number | undefined, held?: boolean | Box | null, pushed?: number | undefined}} Row */
/** @typedef {{came?: number | undefined, held: Box | null, seats: SeatSet, floor: number,
 * cover: readonly Box[], controls: readonly Box[], bounds: Box,
 * folds: {seats: SeatSet, open: number} | null, folded: boolean}} Pin */

// A row stands in the rail when the page has one, the rail stands beside the box that
// scrolls its target (the document, or a bounded block in its flow; never a pane), and
// its block does not reach into the rail. A block grown past the rail's inner edge by
// more than half a marker would stand under a rail marker, so its row stands on it as a
// pin instead: the figure keeps its shape and the comment lands on what it is about. A
// note hanging in the right margin level with the row holds the rail's strip there, so
// that row pins too (`noted`).
/** @param {{railStands: boolean, besideRail: boolean, blockRight: number, railInner: number, half: number, noted: boolean}} reading */
export function rowPlacement({
  railStands,
  besideRail,
  blockRight,
  railInner,
  half,
  noted,
}) {
  if (!railStands || !besideRail || noted) return "pin";
  return blockRight - half > railInner ? "pin" : "rail";
}

// A rail row that would stand over an occupied footprint is pushed down. The layout
// owns the shared seating order (`inSeatingOrder`); bands across the page do not
// collide. Pins use `seatRow`: packing a chosen pin again could move it into words.
// `occupied` holds the final footprints already placed in the shared seating order,
// including revealed held labels. Later rows in either posture avoid those footprints.
//
// A row supplies `{ rect, held, pushed }`: its rect the one it takes with
// no push, `came` the layout pass it came at, and `pushed` the push it stands at now. A
// held row is packed from where it stands, its rect pushed by `pushed`, so holding a row
// that stands pushed leaves it there; every other row is packed from its rect, and comes
// back up as the room above it frees. The answer is this row's push.
/** @param {Pick<Row, "rect" | "held" | "pushed">} row @param {number} gap @param {readonly Box[]} occupied */
export function packRow({ rect, held, pushed = 0 }, gap, occupied = []) {
  const height = rect.bottom - rect.top;
  let top = rect.top + (held ? pushed : 0);
  const across = occupied
    .filter((box) => overlapsAcross(box, rect))
    .toSorted((a, b) => a.top - b.top);
  for (const box of across)
    if (top < box.bottom + gap && top + height > box.top - gap) top = box.bottom + gap;
  return top - rect.top;
}

// The pass each row came at, carried from the last pass's answer (`previous`) to this
// one's. Each of this pass's rows is `{ row, at }`: the row's node and what it stands by,
// its target or the row inside it a comment pointed at, or null where it has no target
// shown. A row is news, coming at `pass`, only when neither the row nor what it stands by
// was there at the last pass: the projection builds a row again when an edit shifts an
// id-less target's path, and a renderer or a revision replaces a target's node under the
// same key, and neither is news. A row hidden and shown again keeps the pass it came at,
// and what has no row at this pass is forgotten, so a row it gains later is news. The
// answer maps each row, and what each stands by, to the pass it came at.
/** @template K @param {ReadonlyMap<K, number>} previous
 * @param {readonly {row: K, at: K | null}[]} rows @param {number} pass */
export function arrivals(previous, rows, pass) {
  const next = new Map();
  for (const { row, at } of rows) {
    const first =
      previous.get(row) ?? (at === null ? undefined : previous.get(at)) ?? pass;
    next.set(row, first);
    if (at) next.set(at, first);
  }
  return next;
}

// The order rows take their places in, each yielding to those before it. A row the user
// holds (`held`: under the pointer, with focus in it, or with its thread card open) comes
// first, so no row pushes it out from under the press or moves the card it opened. Then
// by the pass each came at, the earliest first (`came`), so a row that has just come
// takes the room those already there leave rather than moving them: news moves nothing
// already seated. Then from the top, which is how rows that came together, as a page's
// do at load, take their places.
/** @template {Row} R @param {readonly R[]} rows */
export const inSeatingOrder = (rows) =>
  [...rows].sort(
    (a, b) =>
      Number(Boolean(b.held)) - Number(Boolean(a.held)) ||
      (a.came ?? 0) - (b.came ?? 0) ||
      a.rect.top - b.rect.top,
  );

// The seats by one subject, in the order a pin takes them, `size` wide and as tall as
// `home`, the pin's seat inside the subject's top-right corner, `gap` from the subject
// where they stand off it; `parts` are the subject's boxes, `inline` whether it is a
// run of words, which adds the seat after its last word, and `passage` whether the
// above seat hangs off quoted words. `cover` is what a pin keeps off, and `beside` says
// whether another block stands across a rect (margin-layout.js, `coverIn`).
//
// A seat outside the subject, beside its corner or its last word, is offered only where
// no other block stands level with the part it stands by: a pin in a neighbour's box
// reads as the neighbour's, as a card's pin in the gap between board columns reads as
// the next column's card. Only the seat's span level with that part is asked, since a
// pin is taller than a line and its foot overhangs the block below, where it reads as
// the line's still. A seat not offered is null; `home` names the inside one.
/** @param {readonly Box[]} parts @param {Box} home @param {boolean} inline @param {boolean} passage
 * @param {{cover: readonly Box[], beside: (rect: Box) => boolean}} room @param {number} size @param {number} gap
 * @returns {SeatSet} */
export function seatsBy(parts, home, inline, passage, { cover, beside }, size, gap) {
  const height = home.bottom - home.top;
  const box = union(parts) ?? home;
  const end = parts.at(-1);
  /** @param {Box} part */
  const outside = (part) => {
    const seat = {
      left: part.right + gap,
      right: part.right + gap + size,
      top: part.top,
      bottom: part.top + height,
    };
    const level = { ...seat, bottom: Math.min(seat.bottom, part.bottom) };
    return beside(level) ? null : seat;
  };
  // Below the corner only where the row under the subject is empty from its left edge
  // to the corner: beside the next block's words, a pin reads as that block's.
  // Measured from the subject's own foot, not its home's: a subject shorter than a pin
  // would otherwise skip the block below it.
  const under = {
    left: Math.min(home.left, box.left),
    right: home.right,
    top: box.bottom + gap,
    bottom: box.bottom + gap + height,
  };
  const belowClear = !cover.some((box) => overlaps(box, under));
  return {
    before: [outside(box), ...(inline && end ? [outside(end)] : [])],
    home: { ...home, left: home.right - size },
    after: [
      {
        left: passage ? box.right : home.right - size,
        right: passage ? box.right + size : home.right,
        top: box.top - gap - height,
        bottom: box.top - gap,
      },
      ...(belowClear ? [{ ...under, left: home.right - size }] : []),
    ],
  };
}

// Where one pin stands among the footprints the layout has already seated. It
// offers its seats in the order it prefers them (`seats`, margin-layout.js says
// which), and takes the first that covers nothing (`pinSpot`). Its home seat
// stands for the first spot down the target's right edge, as far as the target's
// `floor`, that clears what is there: the empty end of a line below a full one.
//
// A pin is meant to read as its target's, so every seat touches the target. Its corner
// seat slid left along the target's top, past the controls, pins and words there, to the
// first room that covers nothing, is one more clear seat, tried after the others: beside
// an option's mark, in the room its title leaves, rather than over the heading above.
// Where no seat is clear, the pin still stands by its target rather than wandering off
// to room elsewhere on the page, and the reader hides annotations to see what it covers.
// It takes, of the seats that cover no control (where a press would reach the pin
// instead), the one that covers least, so a pin over the end of a heading's line beats
// one over a paragraph. Failing that it takes whichever covers less, of the corner slid
// past the controls and pins alone, as a card's header keeps its buttons at its right,
// and the corner pushed below any pin already seated there, as a
// short list item's pin stands below its neighbour's rather than over its words; the
// slid seat wins a tie. The pushed seat competes only while it ends within
// one pin's height of `floor`, the room `cover` was read from, so what it covers is
// known. Failing both, the corner pushed below anyway, or the corner itself.
//
// A held pin keeps the rect it holds: unfolding its options widens it, and a seat taken
// again at that width could move the control the user is pressing. It is seated first,
// so no other pin takes its room. A held seat that no longer fits the current bounds is
// seated again, so narrowing a window keeps its controls reachable.
//
// A pin that finds no clear seat for its resting face stands folded where it can fold:
// one control, its options' toggle, seated as any pin is at that size, so it takes room
// the whole face could not. Held open, a folded pin spreads leftward from the toggle
// over whatever stands beside it, and every other pin keeps to its toggle, so opening it
// moves nothing the user sees but the pin itself. So that every action it opens to lands
// inside `bounds`, the toggle is seated only where the open width fits to its left: the
// search's bounds give up that width on the left.
//
// Each pin is `{ held, seats, floor, cover, controls, bounds, folds,
// folded }`: `held` the rect it holds or null, `seats` its candidate rects, null where
// one is not offered, `home` the nonnull one inside its target's corner, and `floor`
// its target's bottom,
// `cover` what it keeps
// off (words, controls, media), `controls` the controls among them, `folds` the same pin
// folded, `{ seats, open }` with `open` its width opened, where it can fold, and `folded`
// whether it stands folded now, which a held pin keeps. `occupied` holds the final
// footprints already placed, which every pin keeps off as it does a pin seated before it.
// The answer is its seat, `{ rect, folded }`.
/** @param {Pin} pin @param {{gap: number, occupied?: readonly Box[]}} options */
export function seatRow(pin, { gap, occupied = [] }) {
  const open = { seats: pin.seats, bounds: pin.bounds, folded: false };
  const fold = pin.folds;
  const closed = fold && {
    seats: fold.seats,
    bounds: {
      ...pin.bounds,
      left: Math.min(
        pin.bounds.left + fold.open - (fold.seats.home.right - fold.seats.home.left),
        pin.bounds.right - (fold.seats.home.right - fold.seats.home.left),
      ),
    },
    folded: true,
  };
  let posture = pin.folded && closed ? closed : open;
  const held = pin.held && {
    ...pin.held,
    left: posture.folded
      ? pin.held.right - (posture.seats.home.right - posture.seats.home.left)
      : pin.held.left,
  };
  let rect = held && inside(held, posture.bounds) ? held : null;
  const avoiding = [...pin.cover, ...occupied];
  const pressed = [...pin.controls, ...occupied];
  /** @param {SeatSet} seats */
  const lowered = (seats) => [
    ...seats.before,
    slid(seats.home, avoiding, gap, "down", pin.floor),
    ...seats.after,
  ];
  /** @param {SeatSet} seats @param {Box} bounds @param {readonly Box[]} [past] */
  const asideOf = (seats, bounds, past = pressed) =>
    slid(boundedHome(seats.home, bounds), past, gap, "left", bounds.left);
  /** @param {SeatSet} seats @param {Box} bounds */
  const clearAside = (seats, bounds) =>
    pinSpot([asideOf(seats, bounds, avoiding)], [], bounds);
  /** @param {typeof open} next @param {Box | null} seat */
  const take = (next, seat) => {
    if (!seat) return false;
    posture = next;
    rect = seat;
    return true;
  };
  if (
    !rect &&
    !take(open, pinSpot(lowered(open.seats), avoiding, open.bounds)) &&
    !(
      closed && take(closed, pinSpot(lowered(closed.seats), avoiding, closed.bounds))
    ) &&
    !take(open, clearAside(open.seats, open.bounds)) &&
    !(closed && take(closed, clearAside(closed.seats, closed.bounds)))
  )
    posture = closed ?? open;
  const { seats, bounds, folded } = posture;
  const choices = [...seats.before, seats.home, ...seats.after];
  const corner = boundedHome(seats.home, bounds);
  const aside = asideOf(seats, bounds);
  rect ??= leastCovering(choices, pin.cover, pressed, bounds);
  if (!rect) {
    const push = packRow({ rect: corner }, gap, occupied);
    const below = { ...corner, top: corner.top + push, bottom: corner.bottom + push };
    const read = below.bottom <= pin.floor + gap + (corner.bottom - corner.top);
    rect =
      leastCovering(read ? [aside, below] : [aside], pin.cover, pressed, bounds) ??
      (inside(below, bounds) ? below : corner);
  }
  return { rect, folded };
}

/** @param {Box} rect @param {Box} bounds */
const inside = (rect, bounds) =>
  rect.left >= bounds.left &&
  rect.right <= bounds.right &&
  rect.top >= bounds.top &&
  rect.bottom <= bounds.bottom;

/** @param {Box} home @param {Box} bounds */
function boundedHome(home, bounds) {
  const width = home.right - home.left;
  const height = home.bottom - home.top;
  const left = clamp(home.left, bounds.left, bounds.right - width);
  const top = clamp(home.top, bounds.top, bounds.bottom - height);
  return { left, right: left + width, top, bottom: top + height };
}

// Of the offered `seats` inside `bounds` that overlap none of `pressed`, the first of
// those that cover the least area of `cover`, or null.
/** @param {readonly (Box | null)[]} seats @param {readonly Box[]} cover @param {readonly Box[]} pressed @param {Box} bounds */
function leastCovering(seats, cover, pressed, bounds) {
  /** @param {Box} a @param {Box} b */
  const shared = (a, b) =>
    Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left)) *
    Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
  /** @type {Box | null} */
  let best = null;
  let least = Infinity;
  for (const seat of seats) {
    if (!seat || !inside(seat, bounds) || pressed.some((box) => overlaps(box, seat)))
      continue;
    const covered = cover.reduce((sum, box) => sum + shared(box, seat), 0);
    if (covered < least) [best, least] = [seat, covered];
  }
  return best;
}

// `seat` moved past each of `boxes` it overlaps, `left` or `down`, or null once it
// passes `limit`: the left edge it may not cross, or the bottom it may not.
/** @param {Box} seat @param {readonly Box[]} boxes @param {number} gap @param {"left" | "down"} way @param {number} limit */
function slid(seat, boxes, gap, way, limit) {
  let rect = seat;
  for (let hit; (hit = boxes.find((box) => overlaps(box, rect)));) {
    const width = rect.right - rect.left;
    const height = rect.bottom - rect.top;
    rect =
      way === "left"
        ? { ...rect, left: hit.left - gap - width, right: hit.left - gap }
        : { ...rect, top: hit.bottom + gap, bottom: hit.bottom + gap + height };
    if (way === "left" ? rect.left < limit : rect.bottom > limit) return null;
  }
  return rect;
}

// The first of a pin's `seats` inside `bounds` that overlaps none of `boxes`, or null.
/** @param {readonly (Box | null)[]} seats @param {readonly Box[]} boxes @param {Box} bounds */
export const pinSpot = (seats, boxes, bounds) =>
  seats.find(
    (seat) => seat && inside(seat, bounds) && !boxes.some((box) => overlaps(box, seat)),
  ) ?? null;
