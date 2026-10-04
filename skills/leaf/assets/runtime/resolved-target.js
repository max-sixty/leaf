/* The canonical result of resolving a durable anchor into the current document.
 *
 * An element is the semantic hit and travel target; its optional visual `surface` changes
 * only contour paint. A passage carries text segments instead. Both kinds name `place`,
 * where panel order and attached chrome sit. */

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

export const targetElement = (resolved) =>
  resolved?.kind === "element" ? resolved.element : null;

export const targetSegments = (resolved) =>
  resolved?.kind === "passage" ? resolved.segments : [];

export const targetPlace = (resolved) => resolved?.place ?? null;

// A passage's whole box decides visibility; its first nonempty fragment attaches
// chrome. A later line can begin further left without changing that attachment.
// Native selections and durable passages read the same Range geometry.
export const targetRange = (resolved) => {
  const segments = targetSegments(resolved);
  return segments.length ? rangeOf(segments) : null;
};

export function rangeGeometry(range) {
  return {
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
