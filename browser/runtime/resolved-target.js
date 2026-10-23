/* The canonical result of resolving a durable anchor into the current document.
 *
 * An element is the semantic hit and travel target; its optional visual `surface` changes
 * only contour paint. A passage carries text segments instead. Both kinds name `place`,
 * where panel order and attached chrome sit: a verified control face for a named
 * control passage, otherwise its readable block or authored item. Frame-bound paint uses only an exact
 * target; a fallback place remains useful for travel and attached chrome, but cannot
 * supply the original coordinates of an absent visual part. An element an agent sent in
 * a message, which the page draws only while a reader shows that message, resolves to
 * the message while none does: it names its `message` and no `place`, so it has no
 * mark, margin row or page order, and travel to it opens the message. */

import { shownParts } from "./geometry.js";
import { rangeOf } from "./passages.js";

export const resolvedElement = ({ element, place = element, surface = null }) => ({
  exact: true,
  status: "exact",
  datumElement: null,
  kind: "element",
  element,
  place,
  surface,
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

export function rangeGeometry(range) {
  return {
    range,
    contextNode:
      range.startContainer.nodeType === Node.TEXT_NODE
        ? range.startContainer
        : (range.startContainer.childNodes[range.startOffset] ?? range.startContainer),
    box: range.getBoundingClientRect(),
    attachment:
      [...range.getClientRects()].find((rect) => rect.width > 0 && rect.height > 0) ??
      null,
  };
}

// The boxes a passage's words are drawn in: each segment's own lines, never the box of
// an element the passage runs across. None where a revision has changed its text since
// it resolved (`targetRange`).
export const passageBoxes = (resolved) =>
  targetRange(resolved)
    ? targetSegments(resolved)
        .flatMap((segment) => [...rangeOf([segment]).getClientRects()])
        .filter((box) => box.width && box.height)
    : [];

export function passageGeometry(resolved) {
  const range = targetRange(resolved);
  return range && rangeGeometry(range);
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
