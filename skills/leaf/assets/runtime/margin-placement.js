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
// marker at the same height stand apart and stay where they are. `fixed` are boxes a row
// may not stand on and that never move — the page's own controls under a pin, such as a
// card's grip — so a pin level with one goes below it rather than taking its presses.
//
// Each row is `{ key, rect, priority }`, its rect the one it takes with no push. The answer
// maps each key to its push.
export function packRows(rows, gap, fixed = []) {
  const placed = fixed.map(({ left, right, top, bottom }) => ({
    left,
    right,
    top,
    bottom,
  }));
  const pushes = new Map();
  const order = [...rows].sort(
    (a, b) => a.priority - b.priority || a.rect.top - b.rect.top,
  );
  for (const { key, rect, priority } of order) {
    const height = rect.bottom - rect.top;
    let top = rect.top;
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
      priority,
    });
  }
  return pushes;
}

// Where a pin stands. A pin has a seat: right after the end of a run of text, where a
// reader finishes it, or inside the top-right corner of a block. It takes that seat
// wherever the seat covers nothing. Where the seat would cover words, a control, another
// block, or a pin placed before it, the pin takes the room of its own size nearest the
// seat that covers none of them and still touches its target: the free end of the line
// the target ends on, the leading above or below it, the gap before the next block. The
// room is found, never made; a pin that finds none stands at `home`, its target's corner,
// over the words, and packing moves it off whatever pin already stands there.
//
// `parts` are the boxes of the target, one per line for a run of text. `cover` is what
// the pin may not stand on; another block counts whole, since a pin anywhere on it, even
// over its empty end, reads as that block's. `bounds` is the box the pin must stay inside
// (the window across, or what a pane shows), `reach` how far from the nearest part it may
// stand, and `gap` the clearance kept from what it avoids.
export function pinSpot({ seat, home, parts, cover, bounds, reach, gap }) {
  const width = seat.right - seat.left;
  const height = seat.bottom - seat.top;
  const top = Math.min(...parts.map((part) => part.top)) - height - reach - gap;
  const bottom = Math.max(...parts.map((part) => part.bottom)) + height + reach + gap;
  const near = cover.filter((box) => box.bottom > top && box.top < bottom);
  const clear = (rect) =>
    rect.left >= bounds.left &&
    rect.right <= bounds.right &&
    rect.top >= bounds.top &&
    rect.bottom <= bounds.bottom &&
    !near.some((box) => overlaps(box, rect));
  if (clear(seat)) return seat;
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
  for (const box of near) {
    xs.add(box.right + gap);
    xs.add(box.left - width - gap);
    ys.add(box.bottom + gap);
    ys.add(box.top - height - gap);
  }
  const apart = (rect, box) =>
    Math.hypot(
      Math.max(0, box.left - rect.right, rect.left - box.right),
      Math.max(0, box.top - rect.bottom, rect.top - box.bottom),
    );
  let best = null;
  let bestScore = Infinity;
  for (const x of xs)
    for (const y of ys) {
      const rect = { left: x, right: x + width, top: y, bottom: y + height };
      const score = Math.hypot(rect.left - seat.left, rect.top - seat.top);
      if (score >= bestScore || !clear(rect)) continue;
      if (Math.min(...parts.map((part) => apart(rect, part))) > reach) continue;
      best = rect;
      bestScore = score;
    }
  return best ?? home;
}
