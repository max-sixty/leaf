/* Where a margin row stands, folded from rectangles the layout pass has already read.

   A row stands in one of two postures. In the rail it hangs off the column, in the strip
   the page reserves beside it. As a pin it stands over the page inside the top-right
   corner of its target's block. Nothing here moves the page's content: a row's posture
   and its push are the row's own geometry, and the stylesheet places it from them by anchor
   positioning (theme.css, at .lf-margin-cluster).

   The layout pass (`margin-layout.js`) reads every rectangle first, asks these folds, and
   then writes. Each fold answers from its arguments alone, so `tests/runtime/` runs them
   without a browser. */

import { overlapsAcross } from "./rect.js";

// A row stands in the rail when the page has one, its target scrolls with the document,
// and its block does not reach into the rail. A block grown past the rail's inner edge by
// more than half a marker would stand under a rail marker, so its row stands on it as a
// pin instead: the figure keeps its shape and the comment lands on what it is about.
export function rowPosture({ railStands, rootLane, blockRight, railInner, half }) {
  if (!railStands || !rootLane) return "pin";
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
