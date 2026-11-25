/* Writes that say only what changed.

   A write that restates what a node already says still reaches everything watching
   the page: the mutation stream a screen reader rebuilds its buffer from, a fresh dirty
   box for whatever reads next, and, while CSS highlight ranges hold a quoted
   comment's marks, Chrome's paint of the whole document. A render that runs on every change of
   the state it draws writes at that rate on a page nobody has touched, and a placement
   that follows the scroll writes at the scroll's.

   The guards here are the door for the attributes, flags and words that have no other.
   `toggleAttribute` keeps the rule for a flag by construction, where the `disabled` and
   `hidden` setters rewrite the attribute on every set, and `classList.toggle(name,
   force)` keeps it for a class, where `add` and `remove` rewrite the attribute whether
   or not the class changes. An inline style property set to the value and priority it
   holds, or removed where it is absent, is no write in Chromium, Firefox and WebKit, so
   a style write needs no guard reading the property first. Lit writes a binding only
   when its value moved. Leaf's suite fails a write that changes nothing
   (tests/write_watch.js).

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

// Set attribute `name` on `node` to `value` as a string, or remove it for null or
// undefined, writing only where the attribute would read back differently. Pass a
// boolean or a count as it is. A missing node writes nothing.
/** @param {Element | null | undefined} node @param {string} name @param {unknown} value */
export const keeps = (node, name, value) => {
  const next = value == null ? null : String(value);
  if (!node || node.getAttribute(name) === next) return;
  if (next === null) node.removeAttribute(name);
  else node.setAttribute(name, next);
};

// Set `node.hidden`, writing only where it changes; `"until-found"` is a value too.
/** @param {HTMLElement | null | undefined} node @param {HTMLElement["hidden"]} hidden */
export function keepsHidden(node, hidden) {
  if (node && node.hidden !== hidden) node.hidden = hidden;
}

// Set the words of `node` to `text` as a string, writing only where they differ. Null
// clears the words, as the `textContent` setter reads it.
/** @param {Node | null | undefined} node @param {unknown} text */
export function keepsText(node, text) {
  const said = String(text ?? "");
  if (node && node.textContent !== said) node.textContent = said;
}

// A flag one element wears at a time, as a cursor's paint stands on the element under
// the pointer: the returned call moves it to `element`, or takes it off with null,
// writing only when that changes. An element can arrive wearing it already, as a copy
// of the one that wore it does.
/** @param {string} name */
export function keepsOnOne(name) {
  /** @type {Element | null} */
  let on = null;
  return (/** @type {Element | null} */ element) => {
    if (element === on) return;
    on?.removeAttribute(name);
    element?.toggleAttribute(name, true);
    on = element;
  };
}

// An attribute a set of elements wears, as a mark stands on each box an element shows
// through: the returned call gives it to each element `next` names, with the value it
// names, and takes it off every other element an earlier call gave it to, writing only
// what changes, and answers every element that wore it before the call or wears it
// after. It must be the attribute's only writer: it finds what to take the attribute
// off by what it gave it to, not by a query of the page.
/** @param {string} name */
export function keepsOnEach(name) {
  /** @type {ReadonlyMap<Element, unknown>} */
  let on = new Map();
  return (/** @type {ReadonlyMap<Element, unknown>} */ next) => {
    const reached = new Set(on.keys());
    for (const element of reached) if (!next.has(element)) keeps(element, name, null);
    for (const [element, value] of next) {
      keeps(element, name, value);
      reached.add(element);
    }
    on = next;
    return reached;
  };
}

// `length` rounded to layout's 1/64px, for a measure written where a unit can't go,
// such as a scale.
/** @param {number} length */
export const atLayoutPrecision = (length) => Math.round(length * 64) / 64;

// `length` in pixels at layout's 1/64px, for a measure written into a style.
/** @param {number} length */
export const layoutPx = (length) => `${atLayoutPrecision(length)}px`;

// A room a box must fit in, at layout precision and never past it: rounding a room
// up would leave its box a fraction too large for the space it was measured from.
/** @param {number} length */
export const roomPx = (length) => `${Math.floor(length * 64) / 64}px`;

/** Native inline style belongs to HTML, SVG and MathML elements, in any window.
 * @param {Element} node @returns {node is HTMLElement | SVGElement | MathMLElement} */
const isStyledElement = (node) =>
  node.namespaceURI === "http://www.w3.org/1999/xhtml" ||
  node.namespaceURI === "http://www.w3.org/2000/svg" ||
  node.namespaceURI === "http://www.w3.org/1998/Math/MathML";

// The inline style of `element`, or a TypeError where it has none, as an element in
// another namespace has none.
/** @param {Element} element */
export function inlineStyle(element) {
  if (isStyledElement(element)) return element.style;
  throw new TypeError("This element has no native inline style");
}
