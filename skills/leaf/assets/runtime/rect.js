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

// Native nearest scroll alignment on either axis. A destination spanning both edges
// stays; an oversized one partly in view lands its far edge, retaining the visible end.
export function nearestScrollBy(start, end, low, high) {
  if (start < low && end > high) return 0;
  const oversized = end - start > high - low;
  if (start < low) return oversized ? end - high : start - low;
  if (end > high) return oversized ? start - low : end - high;
  return 0;
}

// Which padding-box edges clip descendants. Overflow is per axis; paint containment
// and content visibility clip both even when overflow computes visible.
export const clippingAxes = (style) => {
  const both =
    /paint|strict|content/.test(style.contain) || style.contentVisibility !== "visible";
  return {
    x: both || style.overflowX !== "visible",
    y: both || style.overflowY !== "visible",
  };
};
