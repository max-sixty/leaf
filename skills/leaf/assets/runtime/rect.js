/* The rectangle arithmetic placements share. It reads no document, so the pure placement
   folds (`margin-placement.js`, `comment-placement.js`, the hint seating in
   `keyboard/hints.js`) take it as readily as the passes that measure. */

// Whether two boxes share any pixel.
export const overlaps = (a, b) =>
  a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;

// Whether two boxes share any column: they would collide if they stood level.
export const overlapsAcross = (a, b) => a.left < b.right && b.left < a.right;

// The part of `a` inside `b`, cut only on the axes given. Where the edges cross the result
// has no area (`hasArea`); callers that need an empty box as nothing ask that.
const BOTH = { x: true, y: true };
/** @param {{x?: boolean, y?: boolean}} [axes] */
export const intersect = (a, b, axes = BOTH) => ({
  left: axes.x ? Math.max(a.left, b.left) : a.left,
  top: axes.y ? Math.max(a.top, b.top) : a.top,
  right: axes.x ? Math.min(a.right, b.right) : a.right,
  bottom: axes.y ? Math.min(a.bottom, b.bottom) : a.bottom,
});
export const hasArea = (box) => box.right > box.left && box.bottom > box.top;

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
// and content visibility clip both even when overflow computes visible. Each names the
// values that clip rather than the one that does not, so an engine that computes no
// value for a property, as WebKit before 18 does for `content-visibility`, reads as not
// clipping rather than clipping every box. The function names nothing outside itself:
// the shift watch carries its source into the page under test (`shift_watch_source` in
// tests/render_harness.py).
export const clippingAxes = (style) => {
  const clips = /^(hidden|clip|scroll|auto)$/;
  const both =
    /paint|strict|content/.test(style.contain) ||
    /^(auto|hidden)$/.test(style.contentVisibility);
  return {
    x: both || clips.test(style.overflowX),
    y: both || clips.test(style.overflowY),
  };
};
