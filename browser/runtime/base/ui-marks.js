// Compiled from ui-marks.ts by build/typescript.mjs; edit that file.
/* Which layer a node stands in: Leaf's chrome, a label a widget declared as the page
   speaking, or the document. Every reading that climbs out of a widget asks it, so it is
   answered here, from the marks Leaf's chrome wears, where dom/geometry.js and the passage
   readings both ask it and neither imports the other for it. The climb itself is the
   library's (lib/shadow-tree.js). */
import { closestAcross, isElement, overIn } from "../lib/shadow-tree.js";

// Which document an element is in is not a question about looks at all, so the class
// `.lf-ui` doesn't answer it. The runtime's layer is one container, so a
// widget inside a reply — markup the log carries, and no version — is exactly
// what that container holds, and the reading position is a place in the page rather than
// in the panel over it. `.lf-ui` reaches those elements and a widget's own controls out
// on the page besides, which would make the look stand in for the place.
// Across the boundary as closestAcross does: the marker lives out in
// the document, so a node inside a widget's shadow tree can only reach it by leaving the
// tree, and a widget staged inside a reply would otherwise read as page content.
export const inChrome = (node) => Boolean(node && closestAcross(node, ".lf-chrome"));

// A label a widget declared as the page speaking, which the anchor pass reads over the
// chrome it sits in.
export const SAID = "[data-lf-said]";
// The pair `uiInside` weighs, the nearer deciding. The passage walk reads the same pair one
// element at a time on its way down (readings/passages.js, `chromeMark`).
export const UI_MARKS = `.lf-ui, ${SAID}`;
// The same question one node at a time: is this the runtime's own chrome rather than the
// document? Every affordance asks it before acting on where the pointer or the caret is.
// The nearest element that answers wins: a declared label is the page's words inside the
// control it labels, and a control nested inside one is chrome again. `.lf-ui` alone is
// no answer, since it is a look: taken as one, it leaves a user reading a heading they
// cannot point at.
//
// Bounded or not, by the second argument, and that is the whole difference between the
// two ways this gets asked. Unbounded — `inUi` — the answer is about the page: a
// control is the runtime's apparatus wherever it stands, which is what a pointer or a
// caret needs to know. Bounded at an element, the answer is about that element's own
// insides, which is what a reading of one widget needs: the panel holding a widget an
// agent sent in a reply is itself `.lf-ui`, so asked the unbounded way every child of
// such a widget answers yes, and the widget reads as having nothing of its own left.
// The text readings took the same seam (quotable, shownParts, settledAway, authored);
// it is stated once here so
// that what a mark may hang on, what a settlement has emptied, and what a quote may
// name cannot come apart.
export const uiInside = (el, within) => {
  const near = el && overIn(el, UI_MARKS, within);
  return !!near && !near.matches(SAID);
};
export const inUi = (node) =>
  uiInside(isElement(node) ? node : node?.parentElement, null);
