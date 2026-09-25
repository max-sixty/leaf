/* Where a margin row stands, folded from rectangles the layout pass has already read.

   A row stands in one of two postures. In the rail it hangs off the column, in the strip
   the page reserves beside it. As a pin it stands over the page at the top-right of its
   target's block. Nothing here moves the page's content: a row's posture, its offset and
   its push are the row's own geometry, and the stylesheet places it from them by anchor
   positioning (theme.css, at .lf-margin-cluster).

   The layout pass (`margin-layout.js`) reads every rectangle first, asks these folds, and
   then writes. Each fold answers from its arguments alone, so `tests/runtime/` runs them
   without a browser. */

// A row stands in the rail when the page has one, its target scrolls with the document,
// and its block does not reach into the rail. A block grown past the rail's inner edge by
// more than half a marker would stand under a rail marker, so its row stands on it as a
// pin instead: the figure keeps its shape and the comment lands on what it is about.
//
// `wide: "step"` is the look pass's alternate (B4): the row stays in the rail and steps
// out past whatever grown box stands level with it (`stepPast`).
export function rowPosture({
  railStands,
  rootLane,
  blockRight,
  railInner,
  half,
  wide,
}) {
  if (!railStands || !rootLane) return "pin";
  if (wide === "step") return "rail";
  return blockRight - half > railInner ? "pin" : "rail";
}

// How far past its block's right edge a pin's right edge stands. `room` is what the page
// leaves free there: to the shell's edge for a block standing in `main`, and the nearest
// frame's inline-end padding for a block inside a card, a cell or a pane. `size` is the
// pin's own width: it stands wholly beside the block where the room holds it, and
// otherwise takes what room there is and covers the rest of the block.
//
// `pin` selects the look pass's alternates: "straddle" centres every pin on its block's
// edge with no reading of the room, and "corner" stands it wholly inside the block's
// top-right corner.
export function pinOffset({ room, size, pin = "room" }) {
  if (pin === "straddle") return size / 2;
  if (pin === "corner") return -4;
  return Math.max(0, Math.min(size, room));
}

// How far a rail row steps right to hang past the widest grown box level with it, held
// inside the shell. The look pass's B4 alternate; B3 never steps.
export function stepPast({ left, width, hang, top, height, wide, shellRight }) {
  const reach = Math.max(
    left - hang,
    ...wide
      .filter((box) => box.top < top + height && box.bottom > top)
      .map((box) => box.right),
  );
  return Math.max(0, Math.min(reach + hang - left, shellRight - (left + width)));
}

const overlapsAcross = (a, b) => a.left < b.right && b.left < a.right;

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
