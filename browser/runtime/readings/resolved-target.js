// Compiled from resolved-target.ts by build/typescript.mjs; edit that file.
/* The canonical result of resolving a durable anchor into the current document.
 *
 * An element is the semantic hit and travel target; its optional visual `surface` changes
 * only contour paint, and a part of a picture carries the `label` its visual registers
 * for it (state/visual-parts.js). A passage carries text segments instead. Both kinds name `place`,
 * where panel order and attached chrome sit: a verified control face for a named
 * control passage, otherwise its readable block or authored item. Frame-bound paint uses only an exact
 * target; a fallback place remains useful for travel and attached chrome, but cannot
 * supply the original coordinates of an absent visual part. An element an agent sent in
 * a message, which the page draws only while a reader shows that message, resolves to
 * the message while none does: it names its `message` and no `place`, so it has no
 * mark, margin row or page order, and travel to it opens the message. */

import { shownParts } from "../dom/geometry.js";
import { renderedOrder } from "../lib/shadow-tree.js";
import { rangeOf, segmentLines, segmentsBox, segmentsIn } from "./passages.js";

export const resolvedElement = ({
  element,
  place = element,
  surface = null,
  label = null,
}) => ({
  exact: true,
  status: "exact",
  datumElement: null,
  kind: "element",
  element,
  place,
  surface,
  label,
});

export const resolvedPassage = ({ place, segments }) => ({
  exact: true,
  status: "exact",
  datumElement: null,
  kind: "passage",
  place,
  segments,
});

export const resolvedInMessage = ({ message }) => ({
  exact: true,
  status: "exact",
  datumElement: null,
  kind: "message",
  message,
  place: null,
});

export const targetElement = (resolved) =>
  resolved?.kind === "element" ? resolved.element : null;

// Where a target stands in the page's reading order: the node it stands by, the
// element it points into or its passage's first text node or its element, and where in
// that node its passage starts; and the order two such places are read in, by the
// page's rendered order (lib/shadow-tree.js, `renderedOrder`, or the `renderedOrdering` a sort
// of many passes), then, in one text node, by where each starts. Every list of the page's targets is in this order: the margin's entries
// (features/annotation-inventory.js) and the threads a passage's mark names (annotations/anchor-paint.js).
export const readingPlace = (resolved, point = null) => {
  const [first] = targetSegments(resolved);
  return {
    node: point ?? first?.node ?? targetElement(resolved),
    start: first?.start ?? -1,
  };
};
export function readingOrder(left, right, nodeOrder = renderedOrder) {
  if (left.node !== right.node) {
    if (!left.node) return 1;
    if (!right.node) return -1;
    const order = nodeOrder(left.node, right.node);
    if (order) return order;
  }
  return left.start - right.start;
}

export const targetSegments = (resolved) =>
  resolved?.kind === "passage" ? resolved.segments : [];

export const targetPlace = (resolved) => resolved?.place ?? null;

export const exactTarget = (resolved) =>
  resolved?.exact ? (targetElement(resolved) ?? targetPlace(resolved)) : null;

// A passage's whole box decides visibility; its first nonempty fragment attaches
// chrome. A later line can begin further left without changing that attachment.
// Native selections and durable passages read the same Range geometry.
export const targetRange = (resolved) => {
  const segments = targetSegments(resolved);
  // A document revision can shorten a live text node before the next anchor reading.
  // Its old offsets no longer describe a passage; callers use the place until the
  // publication resolves the anchor again.
  if (
    !segments.length ||
    segments.some(
      ({ node, start, end }) =>
        !node.isConnected || start > node.length || end > node.length,
    )
  )
    return null;
  return rangeOf(segments);
};

// A selection's geometry. It attaches to the first line its words are drawn in, as a
// passage does (`passageGeometry`), never to the box of an element it starts across,
// whose padding stands above and before that line.
export function rangeGeometry(range) {
  return {
    range,
    contextNode:
      range.startContainer.nodeType === Node.TEXT_NODE
        ? range.startContainer
        : (range.startContainer.childNodes[range.startOffset] ?? range.startContainer),
    box: range.getBoundingClientRect(),
    attachment:
      segmentLines(segmentsIn(range)).find(
        (rect) => rect.width > 0 && rect.height > 0,
      ) ?? null,
  };
}

// The boxes a passage's words are drawn in: each segment's own lines, never the box of
// an element the passage runs across. None where a revision has changed its text since
// it resolved (`targetRange`).
export const passageBoxes = (resolved) =>
  targetRange(resolved)
    ? segmentLines(targetSegments(resolved)).filter((box) => box.width && box.height)
    : [];

// A passage's geometry as `rangeGeometry` gives a selection's, read from its segments'
// own lines, which hold where one range across a shadow root collapses (passages.js,
// `rangeOf`).
export function passageGeometry(resolved) {
  const range = targetRange(resolved);
  const segments = targetSegments(resolved);
  const [first] = segments;
  if (!range || !first) return null;
  const lines = segmentLines(segments);
  return {
    range,
    contextNode: first.node,
    box: segmentsBox(segments),
    attachment: lines.find((rect) => rect.width > 0 && rect.height > 0) ?? null,
  };
}

export const targetSurface = (resolved) =>
  resolved?.kind === "element" ? resolved.surface : null;

export const targetParts = (resolved) => {
  const element = targetElement(resolved);
  if (!element) return [];
  const surface = targetSurface(resolved);
  // A visual surface is paint, not identity. The semantic element must continue to own
  // hit testing when a package narrows its contour to exclude decoration.
  return surface ? [element] : shownParts(element);
};
