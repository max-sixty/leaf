/* Where inside its target a comment stands: the row a pointing gesture landed on.

   A comment's target is its anchor's, whatever size that is; a pointing gesture also
   says where in the target the user was looking. ⌥-clicking the sixth line of a diff
   that is one addressable whole comments on the whole diff, and the box to write in, the
   comment's margin row, the card it opens and the travel back to it stand level with
   that line rather than at the diff's top, which may be a screen above it. The point is
   presentation, not an event fact: the anchor stays the target, and nothing the log or
   the agent reads changes.

   The point is the line the press landed on: the nearest box around the pressed node,
   inside its target and never the target itself, that is a line or a block of its own
   (a diff's line, a paragraph in a section, a table's row), decided by how it lays out.
   Words, a link or code inline in the target's own lines have none, nor does a drawing's
   shape, nor the target's first line, where the target's own margin row already stands,
   nor a press on the target's own box or a gesture with no pointer (`c`, a selection):
   those stand at the target's top. Which line a point is comes from the document, and
   only its box is read afresh at every placement, so a reflow carries the place with the
   row and never moves a comment from one margin row to another.

   A point belongs to one comment. The composing surface holds a draft's point while the
   box is up; a send hands its point over under its thread's key (`threadKey`, the
   attempt that survives the log's answer), with the row's words as a passage
   (`rangeAnchor`), the identity the page already resolves quotes by. Comments pointed at
   one row share that row's key, the first one's, so they stand as one margin row.

   Anchor paint's pass is the one writer of the points (`placePoints`, beside its
   resolution of every thread's anchor): it takes in what sends handed over, keeps a row
   still standing, finds one a re-render or a revision replaced again by its words, once
   per page reading, and forgets the points of threads the log does not hold. A settled
   thread keeps its point, so undoing the settle brings it back where it stood. Everything
   else reads the result off the placement record. A point whose words no longer
   resolve, or that had none, stands at the target's top; a reload keeps none. */
import { resolveAnchor } from "./anchor-resolution.js";
import { inChrome } from "./passages.js";
import { clamp } from "./rect.js";
import { targetSegments } from "./resolved-target.js";
import { upFrom, under } from "./shadow.js";

// A sent comment's point by its thread's key: `{ element, passage, row, readFor }`.
const points = new Map();
// Points a send has handed over (`commitPoint`), until the pass takes them in.
const handed = new Map();

// Boxes that are not a line of their own: laid out within one, or drawing no box.
const WITHIN_A_LINE = /^(inline|contents$)/;

// The line `node` lies on inside `target`: the nearest element around it that lays out
// as a line or a block of its own, short of the target itself. Words, a link or code
// inline in the target's own lines have none, and neither does a drawing's shape, whose
// `display` says nothing about lines.
//
// Inside a table's cell the line is the cell's row, whatever blocks the cell holds, so
// the climb goes on past a block it found to see whether a cell holds it.
//
// The target's first line is none either: the target's own margin row stands there
// already, so a comment pointed at an Ask's heading joins the Ask's row rather than
// standing as a second one pushed below it. First is read off the document, as nothing
// drawn coming before it in the target, so no reflow, zoom or font moves a comment
// between the two rows.
function rowIn(target, node) {
  let at = node?.nodeType === Node.ELEMENT_NODE ? node : (node?.parentElement ?? null);
  if (!target || target instanceof SVGElement || !at || !under(at, target)) return null;
  let line = null;
  for (; at && at !== target; at = upFrom(at)) {
    if (at instanceof SVGElement) continue;
    const display = getComputedStyle(at).display;
    if (display === "table-row") {
      line = at;
      break;
    }
    if (display === "table-cell") line = null;
    else if (!line && !WITHIN_A_LINE.test(display)) line = at;
  }
  return line && !opens(target, line) ? line : null;
}

// Whether `line` is the first thing `target` draws: no words and no box the page draws
// come before it inside the target. Leaf's own chrome seated there is not the page's.
function opens(target, line) {
  for (let at = line; at && at !== target; at = upFrom(at))
    for (let before = at.previousSibling; before; before = before.previousSibling)
      if (drawn(before)) return false;
  return true;
}

const drawn = (node) =>
  node.nodeType === Node.TEXT_NODE
    ? Boolean(node.data.trim()) && Boolean(node.parentElement?.checkVisibility())
    : node.nodeType === Node.ELEMENT_NODE &&
      !inChrome(node) &&
      node.checkVisibility() &&
      [...node.getClientRects()].some((box) => box.width && box.height);

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

// A send hands its thread's point over: `element`, and `passage`, its words or null.
export function commitPoint(key, element, passage) {
  handed.set(key, { element, passage });
}

// Where each of `threads` pointed into its target stands on this page reading `text`:
// `{ key, target }` in, and `key → { element, row, words }` out for each that stands. The one
// writer of the points, run by anchor-placement's read. It takes in what sends handed over,
// a comment pointed at a row another stands at sharing that row's key. `known` is the key
// of every thread the log holds, settled ones included, so undoing a settle finds its
// point again; a point whose thread the log does not hold, a refused send's, is
// forgotten. A pass with none, before the log is read, says nothing about which threads
// it holds and forgets nothing.
export function placePoints(threads, known, text) {
  for (const [key, { element, passage }] of handed) {
    if (!known.has(key)) continue;
    handed.delete(key);
    const beside = [...points.values()].find(
      (held) => held.element === element && element.isConnected,
    );
    points.set(key, { element, passage, row: beside?.row ?? key, readFor: null });
  }
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
    if (element)
      placed.set(key, { element, row: point.row, words: point.passage?.quote ?? null });
  }
  if (known.size)
    for (const store of [points, handed])
      for (const key of store.keys()) if (!known.has(key)) store.delete(key);
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
