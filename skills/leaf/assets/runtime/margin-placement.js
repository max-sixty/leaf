/* Where a margin row stands, folded from rectangles the layout pass has already read.

   A row stands in one of two postures. In the rail it hangs off the column, in the strip
   the page reserves beside it. As a pin it stands over the page by its target, in room
   that covers none of the page's words where it finds some (`pinSpot`). Nothing here
   moves the page's content: a row's posture, seat and push are the row's own geometry,
   and the stylesheet places it from them by anchor positioning (theme.css, at
   .lf-margin-cluster).

   The layout pass (`margin-layout.js`) reads every rectangle first, asks these folds, and
   then writes. Each fold answers from its arguments alone, so `tests/runtime/` runs them
   without a browser. */

import { overlaps, overlapsAcross } from "./rect.js";

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

// Rows that would stand over one another are pushed down, the more important first and
// then from the top. Two rows collide only where their rectangles do: a pin and a rail
// marker at the same height stand apart and stay where they are. A row's `fixed` are
// boxes it may not stand on and that never move — the page's own controls under a pin,
// such as a card's grip — so a pin level with one goes below it rather than taking its
// presses. They are each row's own, since which controls a row can take presses from
// depends on the scroller it stands in: a pane body's options scrolled behind the pane's
// footer are there for a pin in the body and nobody else.
//
// Each row is `{ key, rect, priority, held, fixed }`, its rect the one it takes with no
// push. A row the user holds, under the pointer or with focus in it, comes before every
// other (`inSeatingOrder`), so no row pushes it out from under the press. The answer maps
// each key to its push.
export function packRows(rows, gap) {
  const placed = [];
  const pushes = new Map();
  const order = inSeatingOrder(rows);
  for (const { key, rect, priority, fixed = [] } of order) {
    const height = rect.bottom - rect.top;
    let top = rect.top;
    const across = [...placed, ...fixed]
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
      priority,
    });
  }
  return pushes;
}

// The order rows take their places in: held rows first, then the more important, then
// from the top.
const inSeatingOrder = (rows) =>
  [...rows].sort(
    (a, b) =>
      Number(Boolean(b.held)) - Number(Boolean(a.held)) ||
      a.priority - b.priority ||
      a.rect.top - b.rect.top,
  );

// Where every pin stands, in seating order, so a pin seated first is one the next keeps
// off (`pinSpot`). A held pin keeps the rect it holds: unfolding its options widens it,
// and a seat taken again at that width could move the control the user is pressing. It is
// seated first, so no other pin takes its room. A pin with no `parts` to read around,
// such as one inside a shadow tree, stands at its home.
//
// Each pin is `{ key, rect, priority, held, seat, parts, cover, walls, neighbours, line,
// bounds }`, `rect` its home and `held` the rect it holds or null. A pin seated first is
// a wall to the next, and every other pin's target is one a pin reaching further out must
// not stand nearer to, unless the two targets meet, as a passage in a commented block
// does. The answer maps each key to its seat.
export function seatRows(pins, { reach, gap }) {
  const seats = new Map();
  const seated = [];
  for (const pin of inSeatingOrder(pins)) {
    const own = pin.parts ?? [];
    const rect =
      pin.held ??
      (own.length
        ? pinSpot({
            seat: pin.seat,
            home: pin.rect,
            parts: own,
            cover: [...pin.cover, ...seated],
            walls: [...pin.walls, ...seated],
            neighbours: pin.neighbours,
            others: pins
              .filter(
                (other) =>
                  other !== pin &&
                  !other.parts?.some((part) =>
                    own.some((mine) => overlaps(part, mine)),
                  ),
              )
              .flatMap((other) => other.parts ?? []),
            bounds: pin.bounds,
            reach,
            line: pin.line,
            gap,
          })
        : pin.rect);
    seats.set(pin.key, rect);
    seated.push(rect);
  }
  return seats;
}

// Where a pin stands. A pin has a seat: right after the end of a run of text, where a
// reader finishes it, or inside the top-right corner of a block. It takes that seat
// wherever the seat covers nothing. Where the seat would cover words, a control, another
// block, or a pin placed before it, the pin takes the room of its own size nearest the
// seat that covers none of them, searching outwards in four stages and taking the first
// that finds room:
//
// 1. Room that touches its target, within `reach`, clear of neighbouring blocks: the free
//    end of the line the target ends on, the leading above or below it, the gap before
//    the next block.
// 2. Room within `reach` that stands on a neighbouring block's empty end, such as the
//    short heading just above a run whose lines are full. A pin there can read as the
//    neighbour's, so it comes only after the target's own room.
// 3. and 4. The same two, reaching one `line` further out: past one line of words to the
//    room beyond it, such as the empty end of a section's heading above the paragraph
//    line the target's run starts below.
//
// Room beyond `reach` still reads as the target's only while words alone lie between:
// the pin passes no wall (a box that paints its extent, a widget, a pin seated before it)
// on the way to its target's nearest part, and stands neither level with any other pin's
// target, where it would read as that line's, nor nearer one than its own. Over its own
// words would hide what the pin is about, so each of these is better; room is found,
// never made, and a pin that finds none stands at `home`, its target's corner, over the
// words, and packing moves it off whatever pin already stands there.
//
// `parts` are the boxes of the target, one per line for a run of text. `cover` is what
// the pin may never stand on, each box whole: words, controls, a block that paints its
// box. `walls` are those of them that are not words or controls. `neighbours` are the
// other blocks that paint nothing, whose words `cover` holds already (`coverIn`).
// `others` are the parts of every other pin's target. `bounds` is the box the pin must
// stay inside: the window across, or the whole content of the pane that scrolls it, never
// the part the pane shows, which would seat the same page differently at each scroll.
// `reach` is how far from the nearest part a pin touches it, `line` the height of a line
// of its target's words, and `gap` the clearance kept from what it avoids.
export function pinSpot({
  seat,
  home,
  parts,
  cover,
  walls,
  neighbours,
  others,
  bounds,
  reach,
  line,
  gap,
}) {
  const width = seat.right - seat.left;
  const height = seat.bottom - seat.top;
  const far = reach + line;
  const top = Math.min(...parts.map((part) => part.top)) - height - far - gap;
  const bottom = Math.max(...parts.map((part) => part.bottom)) + height + far + gap;
  const band = (box) => box.bottom > top && box.top < bottom;
  const avoided = cover.filter(band);
  const beside = neighbours.filter(band);
  const between = walls.filter(band);
  const xs = new Set([seat.left, bounds.right - width]);
  const ys = new Set([seat.top]);
  for (const part of parts) {
    for (const x of [
      part.right + gap,
      part.right - width,
      part.left,
      part.left - width - gap,
    ])
      xs.add(x);
    for (const y of [
      part.top,
      part.bottom - height,
      (part.top + part.bottom - height) / 2,
      part.top - height - gap,
      part.bottom + gap,
    ])
      ys.add(y);
  }
  for (const box of [...avoided, ...beside]) {
    xs.add(box.right + gap);
    xs.add(box.left - width - gap);
    ys.add(box.bottom + gap);
    ys.add(box.top - height - gap);
  }
  // Along one axis, the stretch between two boxes: the gap where they stand apart, and
  // what they share where they overlap.
  const stretch = (lowA, highA, lowB, highB) =>
    highA <= lowB
      ? [highA, lowB]
      : highB <= lowA
        ? [highB, lowA]
        : [Math.max(lowA, lowB), Math.min(highA, highB)];
  const apart = (rect, box) =>
    Math.hypot(
      Math.max(0, box.left - rect.right, rect.left - box.right),
      Math.max(0, box.top - rect.bottom, rect.top - box.bottom),
    );
  // Whether room at most `limit` from the target reads as the target's: within `reach`
  // it touches it; further out, only words lie between them, and no other pin's target
  // is nearer or level with it.
  const reads = (rect, limit) => {
    const closest = parts.reduce((a, b) => (apart(rect, a) <= apart(rect, b) ? a : b));
    const distance = apart(rect, closest);
    if (distance <= reach) return true;
    if (distance > limit) return false;
    const [left, right] = stretch(rect.left, rect.right, closest.left, closest.right);
    const [top, bottom] = stretch(rect.top, rect.bottom, closest.top, closest.bottom);
    return (
      !between.some((wall) => overlaps(wall, { left, right, top, bottom })) &&
      others.every(
        (part) =>
          apart(rect, part) > distance &&
          !(rect.top < part.bottom && part.top < rect.bottom),
      )
    );
  };
  // The room nearest the seat, clear of `boxes`, inside `bounds`, and read as the
  // target's within `limit`.
  const nearest = (boxes, limit) => {
    const clear = (rect) =>
      rect.left >= bounds.left &&
      rect.right <= bounds.right &&
      rect.top >= bounds.top &&
      rect.bottom <= bounds.bottom &&
      !boxes.some((box) => overlaps(box, rect));
    if (clear(seat)) return seat;
    let best = null;
    let bestScore = Infinity;
    for (const x of xs)
      for (const y of ys) {
        const rect = { left: x, right: x + width, top: y, bottom: y + height };
        const score = Math.hypot(rect.left - seat.left, rect.top - seat.top);
        if (score >= bestScore || !clear(rect) || !reads(rect, limit)) continue;
        best = rect;
        bestScore = score;
      }
    return best;
  };
  for (const limit of [reach, far])
    for (const boxes of [[...avoided, ...beside], avoided]) {
      const room = nearest(boxes, limit);
      if (room) return room;
    }
  return home;
}
