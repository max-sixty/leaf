/* Writes that say only what changed.

   A write that restates what a node already says still reaches everything watching
   the page: the mutation stream a screen reader rebuilds its buffer from, a fresh dirty
   box for whatever reads next, the document's disclosure watch, which repaints every
   key on the page, and, while CSS highlight ranges hold a quoted comment's marks,
   Chrome's paint of the whole document. A render bound to semantic publication writes
   at that rate on a page nobody has touched, and a placement that follows the scroll
   writes at the scroll's.

   These three are the door for the names, states, and words that have no other.
   `toggleAttribute` keeps the rule for a flag by construction, where the `disabled` and
   `hidden` setters rewrite the attribute on every set, and `classList.toggle(name,
   force)` keeps it for a class, where `add` and `remove` rewrite the attribute whether
   or not the class changes. An inline style property set to the value and priority it
   holds, or removed where it is absent, is no write in Chromium, Firefox and WebKit, so
   a style write needs no keeper and no guard reading the property first. Lit writes a
   binding only when its value moved. The suite's browser fixture fails a write that
   changes nothing (tests/write_watch.js).

   The comparison is against what the node would read back, not what the caller held:
   `getAttribute` and `textContent` answer with a string and their setters stringify,
   so a boolean or a count compared raw is never equal to what already stands and
   rewrites on every pass.

   A length measured off the page is written to a style property through `layoutPx`.
   Layout resolves lengths to 1/64px, but a length recombined from client coordinates and
   a fractional scroll offset differs below that from one pass to the next on a box that
   has not moved. The style serializer keeps six significant digits, so the property
   reads back the same while the set still rewrites the style attribute. A custom
   property keeps its text verbatim instead, so the same drift there is a write of
   different text; a measured length written to one goes through `layoutPx` too. */

import { isStyledElement } from "./shadow-tree.js";

/** @type {LeafRootState["keeps"]} */
export const keeps = (node, name, value) => {
  const next = value == null ? null : String(value);
  if (!node || node.getAttribute(name) === next) return;
  if (next === null) node.removeAttribute(name);
  else node.setAttribute(name, next);
};

/** @param {HTMLElement | null | undefined} node @param {HTMLElement["hidden"]} hidden */
export function keepsHidden(node, hidden) {
  if (node && node.hidden !== hidden) node.hidden = hidden;
}

// Null clears the words, as the `textContent` setter reads it.
/** @param {Node | null | undefined} node @param {unknown} text */
export function keepsText(node, text) {
  const said = String(text ?? "");
  if (node && node.textContent !== said) node.textContent = said;
}

// A flag one element wears at a time, as a cursor's paint stands on the element under
// the pointer (annotation-overlay/anchor-paint.js, page-geometry.js): the returned call
// moves it to `element`, or takes it off with null, writing only when that changes.
/** @param {string} name */
export function keepsOnOne(name) {
  /** @type {Element | null} */
  let on = null;
  return (/** @type {Element | null} */ element) => {
    if (element === on) return;
    on?.removeAttribute(name);
    element?.setAttribute(name, "");
    on = element;
  };
}

/** @param {number} length */
export const atLayoutPrecision = (length) => Math.round(length * 64) / 64;

/** @param {number} length */
export const layoutPx = (length) => `${atLayoutPrecision(length)}px`;

// A room a box must fit in, at layout precision and never past it: rounding a room
// up would leave its box a fraction too large for the space it was measured from.
/** @param {number} length */
export const roomPx = (length) => `${Math.floor(length * 64) / 64}px`;

/** @param {Element} element */
export function inlineStyle(element) {
  if (isStyledElement(element)) return element.style;
  throw new TypeError("This element has no native inline style");
}
