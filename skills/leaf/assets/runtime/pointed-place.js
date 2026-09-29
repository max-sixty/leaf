/* Where inside its target a comment stands: the row a pointing gesture landed on.

   A comment's target is its anchor's, whatever size that is; a pointing gesture also
   says where in the target the user was looking. ⌥-clicking the sixth line of a diff
   that is one addressable whole comments on the whole diff, and the box to write in, the
   comment's margin row, the card it opens and the travel back to it stand level with
   that line rather than at the diff's top, which may be a screen above it. The point is
   presentation, not an event fact: the anchor stays the target, and nothing the log or
   the agent reads changes.

   The point is the row the press landed in: the nearest box around the pressed node
   that lays out as a line or a block rather than inline, inside its target and never
   the target itself. A press on the target's own box, or a gesture with no pointer (`c`,
   a selection), has none and stands at the target's top. Its box is read afresh at every
   placement, so a reflow carries the place with the row.

   A point belongs to one comment. The composing surface holds a draft's point while the
   box is up; a sent comment's is committed here under its thread's key (`threadKey`, the
   attempt that survives the log's answer), with the row's words as a passage
   (`rangeAnchor`), the identity the page already resolves quotes by. Comments pointed at
   one row share that row's key, the first one's, so they stand as one margin row.

   Anchor paint's pass is the one writer of where each point stands now (`placePoints`,
   beside its resolution of every thread's anchor): a row still standing keeps its
   element, and one a re-render or a revision replaced is found again by its words, once
   per page reading. Everything else reads the result off the placement record. Points of
   threads no longer open, settled or a refused send's, are dropped there too. A
   point whose words no longer resolve, or that had none, stands at the target's top; a
   reload keeps none. */
import { resolveAnchor } from "./anchor-resolution.js";
import { clamp } from "./rect.js";
import { targetSegments } from "./resolved-target.js";
import { upFrom, under } from "./shadow.js";

// A sent comment's point by its thread's key: `{ element, passage, row, readFor }`.
const points = new Map();

// The row `node` lies in inside `target`: the nearest element around it that is not laid
// out inline, short of the target itself.
function rowIn(target, node) {
  let at = node?.nodeType === Node.ELEMENT_NODE ? node : (node?.parentElement ?? null);
  if (!target || !at || at === target || !under(at, target)) return null;
  for (let up = upFrom(at); up && up !== target; up = upFrom(up)) {
    const display = getComputedStyle(at).display;
    if (!display.startsWith("inline") && display !== "contents") break;
    at = up;
  }
  return at;
}

// The row a press on `node` points at inside `target`, or null for none.
export const pointInto = rowIn;

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

// Where the thread `key` stands: `element`, and `passage`, its words or null. A comment
// pointed at a row another comment already stands at shares that row's key.
export function commitPoint(key, element, passage) {
  const beside = [...points.values()].find(
    (held) => held.element === element && element.isConnected,
  );
  points.set(key, { element, passage, row: beside?.row ?? key, readFor: null });
}

// Where each of `threads` pointed into its target stands on this page reading `text`:
// `{ key, target }` in, and `key → { element, row }` out for each that stands. The one
// writer, run by anchor paint's pass. `known` is the key of every open thread the log
// holds, and a point whose thread is not among them, settled or refused, is forgotten;
// a pass with none, offline or before the log is read, says nothing about which
// threads the log holds and forgets nothing.
export function placePoints(threads, known, text) {
  const placed = new Map();
  for (const { key, target } of threads) {
    const point = points.get(key);
    if (!point) continue;
    let element = standingPoint(target, point.element);
    if (!element && point.passage && point.readFor !== text) {
      point.readFor = text;
      const found = resolveAnchor(point.passage, text);
      element = standingPoint(target, rowIn(target, targetSegments(found)[0]?.node));
      if (element) point.element = element;
    }
    if (element) placed.set(key, { element, row: point.row });
  }
  if (known.size)
    for (const key of points.keys()) if (!known.has(key)) points.delete(key);
  return placed;
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
