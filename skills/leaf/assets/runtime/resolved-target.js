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
