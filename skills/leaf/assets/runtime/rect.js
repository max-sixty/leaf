/* The rectangle arithmetic placements share. It reads no document, so the pure placement
   folds (`margin-placement.js`, `comment-placement.js`, the hint seating in
   `keyboard/hints.js`) take it as readily as the passes that measure. */

// Whether two boxes share any pixel.
export const overlaps = (a, b) =>
  a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;

// Whether two boxes share any column: they would collide if they stood level.
export const overlapsAcross = (a, b) => a.left < b.right && b.left < a.right;

// The box that covers every one of some boxes, or null for none.
export function union(boxes) {
  if (!boxes.length) return null;
  const left = Math.min(...boxes.map((box) => box.left));
  const top = Math.min(...boxes.map((box) => box.top));
  const right = Math.max(...boxes.map((box) => box.right));
  const bottom = Math.max(...boxes.map((box) => box.bottom));
  return { left, top, right, bottom, width: right - left, height: bottom - top };
}

// A value held between two bounds, the lower winning where they cross.
export const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
