/* Where a margin row stands, folded from rectangles the layout pass has already read.

   A row stands in one of two postures. In the rail it hangs off the column, in the strip
   the page reserves beside it. As a pin it stands over the page by its target, on the
   first seat touching the target that covers nothing (`seatRows`). Nothing here
   moves the page's content: a row's posture, seat and push are the row's own geometry.
   The layout pass writes them as `--lf-margin-x` and `--lf-margin-y`, which
   annotation-theme.css reads at .lf-margin-cluster; only the carrier a row stands in is
   anchor-positioned.

   The layout pass (`margin-layout.js`) reads every rectangle first, asks these folds, and
   then writes. Each fold answers from its arguments alone, so `tests/runtime/` runs them
   without a browser. */

import { clamp, overlaps, overlapsAcross } from "../rect.js";

// A row stands in the rail when the page has one, the rail stands beside the box that
// scrolls its target (the document, or a bounded block in its flow; never a pane), and
// its block does not reach into the rail. A block grown past the rail's inner edge by
// more than half a marker would stand under a rail marker, so its row stands on it as a
// pin instead: the figure keeps its shape and the comment lands on what it is about. A
// note hanging in the right margin level with the row holds the rail's strip there, so
// that row pins too (`noted`).
export function rowPosture({
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

// Rail rows that would stand over one another are pushed down, in seating order
// (`inSeatingOrder`). Separate bands across the page do not collide. Pins use
// `seatRows`: packing a chosen pin again could move a clear seat into words or controls.
// `occupied` holds the final footprints already placed in the shared seating order,
// including revealed held labels. Later rows in either posture avoid those footprints.
//
// Each row is `{ key, rect, came, held, pushed }`: its rect the one it takes with
// no push, `came` the layout pass it came at, and `pushed` the push it stands at now. A
// held row is packed from where it stands, its rect pushed by `pushed`, so holding a row
// that stands pushed leaves it there; every other row is packed from its rect, and comes
// back up as the room above it frees. The answer maps each key to its push.
export function packRows(rows, gap, occupied = []) {
  const placed = [...occupied];
  const pushes = new Map();
  const order = inSeatingOrder(rows);
  for (const { key, rect, held, pushed = 0 } of order) {
    const height = rect.bottom - rect.top;
    let top = rect.top + (held ? pushed : 0);
    const across = placed
      .filter((box) => overlapsAcross(box, rect))
      .sort((a, b) => a.top - b.top);
    for (const box of across)
      if (top < box.bottom + gap && top + height > box.top - gap)
        top = box.bottom + gap;
    pushes.set(key, top - rect.top);
    placed.push({
      left: rect.left,
      right: rect.right,
      top,
      bottom: top + height,
    });
  }
  return pushes;
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
export function arrivals(previous, rows, pass) {
  const next = new Map();
  for (const { row, at } of rows) {
    const first = previous.get(row) ?? previous.get(at) ?? pass;
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
export const inSeatingOrder = (rows) =>
  [...rows].sort(
    (a, b) =>
      Number(Boolean(b.held)) - Number(Boolean(a.held)) ||
      (a.came ?? 0) - (b.came ?? 0) ||
      a.rect.top - b.rect.top,
  );

// Where every pin stands, in seating order, so a pin seated first is one the next keeps
// off. Each pin offers its seats in the order it prefers them (`seats`, margin-layout.js
// says which), and takes the first that covers nothing (`pinSpot`). Its corner seat
// stands for the first spot down the target's right edge, as far as the target's
// `floor`, that clears what is there: the empty end of a line below a full one.
//
// A pin is meant to read as its target's, so every seat touches the target. Where none
// is clear, the pin still stands by its target rather than wandering off to room
// elsewhere on the page, and the reader hides annotations to see what it covers. It
// takes, of the seats that cover no control (where a press would reach the pin
// instead), the one that covers least, so a pin over the end of a heading's line beats
// one over a paragraph. Failing that it takes whichever covers less, of its corner seat
// slid left along the target's top past the controls and pins there, as a card's header
// keeps its buttons at its right, and the corner pushed below any pin already seated
// there, as a short list item's pin stands below its neighbour's rather than over its
// words; the slid seat wins a tie. The pushed seat competes only while it ends within
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
// Each pin is `{ key, came, held, seats, corner, floor, cover, controls, bounds, folds,
// folded }`: `held` the rect it holds or null, `seats` its candidate rects, `corner` the
// index among them of the one inside its target's corner, `floor` its target's bottom,
// `cover` what it keeps
// off (words, controls, media), `controls` the controls among them, `folds` the same pin
// folded, `{ seats, open }` with `open` its width opened, where it can fold, and `folded`
// whether it stands folded now, which a held pin keeps. `occupied` holds the final
// footprints already placed, which every pin keeps off as it does a pin seated before it.
// The answer maps each key to its seat, `{ rect, folded }`.
export function seatRows(pins, { gap, occupied = [] }) {
  const seats = new Map();
  const seated = [...occupied];
  for (const pin of inSeatingOrder(pins)) {
    const fold = pin.folds;
    let folded = Boolean(fold && pin.folded);
    const foldWidth = fold && fold.seats[0].right - fold.seats[0].left;
    const foldBounds = fold && {
      ...pin.bounds,
      // Reserve the opened actions to the toggle's left. Where the whole group
      // cannot fit, keep at least its toggle inside the right edge.
      left: Math.min(
        pin.bounds.left + fold.open - foldWidth,
        pin.bounds.right - foldWidth,
      ),
    };
    const held = pin.held && {
      ...pin.held,
      left: folded ? pin.held.right - foldWidth : pin.held.left,
    };
    const heldBounds = folded ? foldBounds : pin.bounds;
    let rect = held && inside(held, heldBounds) ? held : null;
    const avoiding = [...pin.cover, ...seated];
    const lowered = (list) => [
      ...list.slice(0, pin.corner),
      slid(list[pin.corner], avoiding, gap, "down", pin.floor),
      ...list.slice(pin.corner + 1),
    ];
    if (!rect) {
      rect = pinSpot(lowered(pin.seats), avoiding, pin.bounds);
      folded = !rect && Boolean(fold);
      if (folded) rect = pinSpot(lowered(fold.seats), avoiding, foldBounds);
    }
    const seatsNow = folded ? fold.seats : pin.seats;
    const boundsNow = folded ? foldBounds : pin.bounds;
    const pressed = [...pin.controls, ...seated];
    const corner = boundedHome(seatsNow[pin.corner], boundsNow);
    const aside = slid(corner, pressed, gap, "left", boundsNow.left);
    rect ??= leastCovering(seatsNow, pin.cover, pressed, boundsNow);
    if (!rect) {
      const push = packRows([{ key: pin.key, rect: corner }], gap, seated).get(pin.key);
      const below = { ...corner, top: corner.top + push, bottom: corner.bottom + push };
      const read = below.bottom <= pin.floor + gap + (corner.bottom - corner.top);
      rect =
        leastCovering(
          [aside, read && below].filter(Boolean),
          pin.cover,
          pressed,
          boundsNow,
        ) ?? (inside(below, boundsNow) ? below : corner);
    }
    seats.set(pin.key, { rect, folded });
    seated.push(rect);
  }
  return seats;
}

const inside = (rect, bounds) =>
  rect.left >= bounds.left &&
  rect.right <= bounds.right &&
  rect.top >= bounds.top &&
  rect.bottom <= bounds.bottom;

function boundedHome(home, bounds) {
  const width = home.right - home.left;
  const height = home.bottom - home.top;
  const left = clamp(home.left, bounds.left, bounds.right - width);
  const top = clamp(home.top, bounds.top, bounds.bottom - height);
  return { left, right: left + width, top, bottom: top + height };
}

// Of the `seats` inside `bounds` that overlap none of `pressed`, the first of those that
// cover the least area of `cover`, or null.
function leastCovering(seats, cover, pressed, bounds) {
  const shared = (a, b) =>
    Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left)) *
    Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
  let best = null;
  let least = Infinity;
  for (const seat of seats) {
    if (!inside(seat, bounds) || pressed.some((box) => overlaps(box, seat))) continue;
    const covered = cover.reduce((sum, box) => sum + shared(box, seat), 0);
    if (covered < least) [best, least] = [seat, covered];
  }
  return best;
}

// `seat` moved past each of `boxes` it overlaps, `left` or `down`, or null once it
// passes `limit`: the left edge it may not cross, or the bottom it may not.
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
export const pinSpot = (seats, boxes, bounds) =>
  seats.find(
    (seat) => seat && inside(seat, bounds) && !boxes.some((box) => overlaps(box, seat)),
  ) ?? null;
