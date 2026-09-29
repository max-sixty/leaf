/* Where inside its target a comment stands: the row a pointing gesture landed on.

   A comment's target is its anchor's, whatever size that is; a pointing gesture also
   says where in the target the user was looking. ⌥-clicking the sixth line of a diff
   that is one addressable whole comments on the whole diff, and the box to write in, the
   comment's margin row, the card it opens and the travel back to it stand level with
   that line rather than at the diff's top, which may be a screen above it. The point is
   presentation, not an event fact: the anchor stays the target, and nothing the log or
   the agent reads changes.

   A point belongs to one comment. The composing surface holds a draft's point while the
   box is up, and a sent comment's is kept under its thread's key (`threadKey`, the
   attempt that survives the log's answer). Nothing else on the target moves: its
   other threads, an Ask's marker, a widget's actions and reactions keep their row at
   the target's top, and the pointed thread stands as a row of its own
   (`margin-projection.js`). A thread that settles leaves the margin and its point with
   it; a refused send leaves no thread to read one.

   The point is the element the press landed on inside its target, never the target
   itself, so a press on a target's own box, or a gesture with no pointer (`c`, a
   selection), has none and stands at the target's top. Its box is read afresh at every
   placement, so a reflow carries the place with the row. A sent point also keeps the
   element's words as a passage (`rangeAnchor`), the identity the page already resolves
   quotes by, so a re-render or a revision that rewrote the target finds the same words
   again. A point whose element has gone and whose words no longer resolve, or that had
   none, stands at the target's top again; a reload keeps none. */
import { resolveAnchor } from "./anchor-resolution.js";
import { pageText } from "./passages.js";
import { clamp } from "./rect.js";
import { targetSegments } from "./resolved-target.js";
import { under } from "./shadow.js";

// A sent comment's point by its thread's key: `{ element, passage }`.
const points = new Map();

const elementOf = (node) =>
  node?.nodeType === Node.ELEMENT_NODE ? node : (node?.parentElement ?? null);

// The element `node` names inside `target`, when it is inside it and not the target
// itself.
export function pointInto(target, node) {
  const at = elementOf(node);
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

// Where the thread `key` stands; `passage` is the element's words, or null.
export function commitPoint(key, element, passage) {
  points.set(key, { element, passage });
}

// The element the thread `key` stands level with inside `target`, or null for the
// target's top: its own element while that stands, else the first element its words
// resolve to now, which is kept for the next reading.
export function pointOf(key, target) {
  const held = key == null ? null : points.get(key);
  if (!held || !target) return null;
  const standing = standingPoint(target, held.element);
  if (standing || !held.passage) return standing;
  const found = resolveAnchor(held.passage, pageText());
  const again = standingPoint(target, elementOf(targetSegments(found)[0]?.node));
  if (again) held.element = again;
  return again;
}

// The band of `box` (the target's) level with `point`: across, the target's; down, the
// row's, kept inside the target.
export function pointBand(box, point) {
  const row = point.getBoundingClientRect();
  const top = clamp(row.top, box.top, box.bottom);
  const bottom = clamp(row.bottom, top, box.bottom);
  const { left, right } = box;
  return { left, top, right, bottom, width: right - left, height: bottom - top };
}
