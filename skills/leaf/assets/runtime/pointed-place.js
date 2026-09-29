/* Where inside its target a comment stands: the row a pointing gesture landed on.

   A comment's target is its anchor's, whatever size that is; a pointing gesture also
   says where in the target the user was looking. ⌥-clicking the sixth line of a diff
   that is one addressable whole comments on the whole diff, and the box to write in, the
   margin cluster and the card it opens stand level with that line rather than at the
   diff's top, which may be a screen above it. The point is presentation, not an event
   fact: the anchor stays the target, and nothing the log or the agent reads changes.

   The point is the element the press landed on inside its target, never the target
   itself, so a press on a target's own box (or a gesture with no pointer, such as `c`)
   has none and stands at the target's top. Its box is read afresh at every placement, so
   a reflow carries the place with the row. It lives as long as that node: a target
   re-rendered, a revision that replaced it, or a reload stands the comment at its
   target's top again.

   The composing surface holds a draft's point while the box is up and commits it here
   when the comment is sent; the margin reads the committed point for the cluster about
   that target. One point per target, the latest sent comment's, since a target has one
   cluster (`margin-projection.js`). */
import { clamp } from "./rect.js";
import { under } from "./shadow.js";

const points = new WeakMap();

// The element `node` names inside `target`, when it is inside it and not the target
// itself.
export function pointInto(target, node) {
  const at = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement;
  return target && at && at !== target && under(at, target) ? at : null;
}

// A point still standing inside `target` with a box to stand by, or null.
export function standingPoint(target, point) {
  return target &&
    point?.isConnected &&
    point !== target &&
    under(point, target) &&
    point.getClientRects().length
    ? point
    : null;
}

// Where a sent comment on `target` stands; null returns it to the target's top.
export function commitPoint(target, point) {
  if (!target) return;
  if (point) points.set(target, point);
  else points.delete(target);
}

export const committedPoint = (target) =>
  target ? standingPoint(target, points.get(target)) : null;

// The band of `box` (the target's) level with `point`: across, the target's; down, the
// row's, kept inside the target.
export function pointBand(box, point) {
  const row = point.getBoundingClientRect();
  const top = clamp(row.top, box.top, box.bottom);
  const bottom = clamp(row.bottom, top, box.bottom);
  const { left, right } = box;
  return { left, top, right, bottom, width: right - left, height: bottom - top };
}
