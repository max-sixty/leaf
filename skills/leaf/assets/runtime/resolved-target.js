/* The canonical result of resolving a durable anchor into the current document.
 *
 * An element is the semantic hit and travel target; its optional visual `surface` changes
 * only contour paint. A passage carries text segments instead. Both kinds name `place`,
 * where panel order and attached chrome sit. */

import { shownParts } from "./geometry.js";

export const resolvedElement = ({ element, place = element, surface = null }) => ({
  kind: "element",
  element,
  place,
  surface,
});

export const resolvedPassage = ({ place, segments }) => ({
  kind: "passage",
  place,
  segments,
});

export const targetElement = (resolved) =>
  resolved?.kind === "element" ? resolved.element : null;

export const targetSegments = (resolved) =>
  resolved?.kind === "passage" ? resolved.segments : [];

export const targetPlace = (resolved) => resolved?.place ?? null;

// The box a passage's words take, from its first segment's start to its last's end.
export function passageBox(resolved) {
  const segments = targetSegments(resolved);
  if (!segments.length) return null;
  const range = document.createRange();
  range.setStart(segments[0].node, segments[0].start);
  range.setEnd(segments.at(-1).node, segments.at(-1).end);
  return range.getBoundingClientRect();
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
