/* Native activation and direction-aware disclosure keys, read from the control.
   A host may bind the declared keys; computing them needs no page dispatcher. */
import { inChrome } from "./shadow-tree.js";

// What activates a focused button, stated once because it is the platform's fact and not
// any one row's. Four rows spelled it by hand — the runtime's own control scope, a card
// grip in each of its two states, and the version menu's row — and the fourth spelled it
// short, naming Enter over a real <button> that answers Space too. A near-copy that has to
// change whenever the original does is a primitive not yet extracted, and the drift here
// was invisible: the key worked and the page under-promised it.
//
// A link is the case that keeps this honest. Enter follows an <a> and Space scrolls the
// page, so All pages binds Enter alone and is right to — the shared fact is what a
// button answers, not what a control does.
export const PRESS = ["Enter", " "];

// The arrows that step back and ahead along a row of controls, as `[back, ahead]`. Back
// is the side the row's words run from: left in left-to-right text and right in
// right-to-left text, where the first item stands at the right, as the ARIA tabs,
// toolbar and slider patterns ask. Read from the directionality of the node the row
// lays out in (`:dir()`), which the `dir` attributes around it decide, as the theme's
// direction rules read it; a `direction` set in CSS alone moves neither. Key
// availability asks this of every disclosure on the page, in the frame's pass after
// other work has written to the document, so reading the computed `direction` made it
// recalculate style for those writes, several times a comment on a page of diffs.
/** @param {Element} node @returns {[string, string]} */
export const rowArrows = (node) =>
  node.matches(":dir(rtl)") ? ["ArrowRight", "ArrowLeft"] : ["ArrowLeft", "ArrowRight"];

/** @param {Element | null} el */
export const DISCLOSE = (el) => {
  const disclosure = disclosureAt(el);
  if (!disclosure) return [...PRESS, "ArrowLeft", "ArrowRight"];
  const { element, open } = disclosure;
  const [back, ahead] = rowArrows(element);
  return inChrome(element) ? PRESS : [...PRESS, open ? back : ahead];
};

export const DISCLOSURE_SELECTOR =
  'details > summary, :is(button, [role="button"])[aria-expanded]';

// The disclosure at this element and whether it is open, or null where none stands.
// The reference asks from wherever the user is, listing scopes the page has.
/** @param {Element | null} el */
export function disclosureAt(el) {
  if (!el?.matches(DISCLOSURE_SELECTOR)) return null;
  return {
    element: el,
    open: el.matches("details > summary")
      ? el.matches("details[open] > summary")
      : el.getAttribute("aria-expanded") === "true",
  };
}
