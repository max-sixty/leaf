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
import type { Segment } from "./passages.js";

type Resolution = {
  exact: boolean;
  status: "exact" | "fallback" | "outdated";
  datumElement: Element | null;
};
export type ElementTarget = Resolution & {
  kind: "element";
  element: Element;
  place: Element;
  surface: Element | null;
  label: string | null;
};
export type PassageTarget = Resolution & {
  kind: "passage";
  place: Element | null;
  segments: Segment[];
  ranges?: readonly Range[];
};
type MessageTarget = Resolution & {
  kind: "message";
  message: string;
  place: null;
};
export type ResolvedTarget = ElementTarget | PassageTarget | MessageTarget;

export const resolvedElement = ({
  element,
  place = element,
  surface = null,
  label = null,
}: {
  element: Element;
  place?: Element;
  surface?: Element | null;
  label?: string | null;
}): ElementTarget => ({
  exact: true,
  status: "exact",
  datumElement: null,
  kind: "element",
  element,
  place,
  surface,
  label,
});

export const resolvedPassage = ({
  place,
  segments,
}: {
  place: Element | null;
  segments: Segment[];
}): PassageTarget => ({
  exact: true,
  status: "exact",
  datumElement: null,
  kind: "passage",
  place,
  segments,
});

export const resolvedInMessage = ({ message }: { message: string }): MessageTarget => ({
  exact: true,
  status: "exact",
  datumElement: null,
  kind: "message",
  message,
  place: null,
});

export const targetElement = (resolved: ResolvedTarget | null | undefined) =>
  resolved?.kind === "element" ? resolved.element : null;

// Where a target stands in the page's reading order: the node it stands by, the
// element it points into or its passage's first text node or its element, and where in
// that node its passage starts; and the order two such places are read in, by the
// page's rendered order (lib/shadow-tree.js, `renderedOrder`, or the `renderedOrdering` a sort
// of many passes), then, in one text node, by where each starts. Every list of the page's targets is in this order: the margin's entries
// (features/annotation-inventory.js) and the threads a passage's mark names (annotations/anchor-paint.js).
export const readingPlace = (
  resolved: ResolvedTarget | null | undefined,
  point: Element | null = null,
) => {
  const [first] = targetSegments(resolved);
  return {
    node: point ?? first?.node ?? targetElement(resolved),
    start: first?.start ?? -1,
  };
};
export function readingOrder(
  left: ReturnType<typeof readingPlace>,
  right: ReturnType<typeof readingPlace>,
  nodeOrder: (a: Node, b: Node) => number = renderedOrder,
) {
  if (left.node !== right.node) {
    if (!left.node) return 1;
    if (!right.node) return -1;
    const order = nodeOrder(left.node, right.node);
    if (order) return order;
  }
  return left.start - right.start;
}

export const targetSegments = (resolved: ResolvedTarget | null | undefined) =>
  resolved?.kind === "passage" ? resolved.segments : [];

export const targetPlace = (resolved: ResolvedTarget | null | undefined) =>
  resolved?.place ?? null;

export const exactTarget = (resolved: ResolvedTarget | null | undefined) =>
  resolved?.exact ? (targetElement(resolved) ?? targetPlace(resolved)) : null;

// A passage's whole box decides visibility; its first nonempty fragment attaches
// chrome. A later line can begin further left without changing that attachment.
// Native selections and durable passages read the same Range geometry.
export const targetRange = (resolved: ResolvedTarget | null | undefined) => {
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
export function rangeGeometry(range: Range) {
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
export const passageBoxes = (resolved: ResolvedTarget | null | undefined) =>
  targetRange(resolved)
    ? segmentLines(targetSegments(resolved)).filter((box) => box.width && box.height)
    : [];

// A passage's geometry as `rangeGeometry` gives a selection's, read from its segments'
// own lines, which hold where one range across a shadow root collapses (passages.js,
// `rangeOf`).
export function passageGeometry(resolved: ResolvedTarget | null | undefined) {
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

export const targetSurface = (resolved: ResolvedTarget | null | undefined) =>
  resolved?.kind === "element" ? resolved.surface : null;

export const targetParts = (resolved: ResolvedTarget | null | undefined) => {
  const element = targetElement(resolved);
  if (!element) return [];
  const surface = targetSurface(resolved);
  // A visual surface is paint, not identity. The semantic element must continue to own
  // hit testing when a package narrows its contour to exclude decoration.
  return surface ? [element] : shownParts(element);
};
