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
   or not the class changes. An inline style property set to the value it holds is no
   write, and Lit writes a binding only when its value moved. The suite's browser
   fixture fails a write that changes nothing (tests/write_watch.js).

   The comparison is against what the node would read back, not what the caller held:
   `getAttribute` and `textContent` answer with a string and their setters stringify,
   so a boolean or a count compared raw is never equal to what already stands and
   rewrites on every pass.

   A length measured off the page goes through `atLayoutPrecision` before it is written.
   Layout resolves lengths to 1/64px, and a measurement repeated on an unmoved box can
   differ below that; the style serializer rounds to six significant digits, so such a
   length rewrites the style attribute to the text it already held. */

export function keeps(node, name, value) {
  const said = String(value);
  if (node && node.getAttribute(name) !== said) node.setAttribute(name, said);
}

export function keepsHidden(node, hidden) {
  if (node && node.hidden !== hidden) node.hidden = hidden;
}

// Null clears the words, as the `textContent` setter reads it.
export function keepsText(node, text) {
  const said = String(text ?? "");
  if (node && node.textContent !== said) node.textContent = said;
}

export const atLayoutPrecision = (length) => Math.round(length * 64) / 64;
