/* The rectangle arithmetic placements share. It reads no document, so the pure placement
   folds (`margin-placement.js`, `thread-card-geometry.js`, the hint seating in
   `keyboard/hints.js`) take it as readily as the passes that measure. */

// Whether two boxes share any pixel.
export const overlaps = (a, b) =>
  a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;

// Whether two boxes share any column: they would collide if they stood level.
export const overlapsAcross = (a, b) => a.left < b.right && b.left < a.right;

// A value held between two bounds, the lower winning where they cross.
export const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
