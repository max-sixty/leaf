/* Indication (experimental): one widget pointing at part of another.

   `indicate(owner, attribute, key)` marks the elements that `key` addresses under the
   widget `owner`'s declared `x-refers` attribute names — a film marking the source lines
   it is executing in a code block beside it. Resolution is `addressedElements`
   (anchor-resolution.js), the key space `navigateToDatum` reads too. The signature and
   the `lfElementsFor` hook may still change.

   An indication is mechanical browser state, like hover: the log never records it, no
   publication carries it, and a revision install does not carry it across. It never
   hydrates, reveals, focuses, scrolls or announces; the page holds still under the
   user's aim, and a driver may move its indication every animation frame.

   Each driver holds at most one key per attribute, and a new key replaces the last. A
   `null` key clears it, which a driver owes in its `disconnectedCallback`. The runtime
   paints the union of every driver's elements with `data-lf-indicated` and
   `aria-current`, diffing against the last union so one driver never clears another's.
   A target that re-renders what a key addresses states it through `layoutChanged`, and
   every live indication is resolved again then. */

import {
  addressedElements,
  referencedProjection,
  requireReference,
} from "./anchor-resolution.js";
import { PAGE_PAINT_ATTRIBUTE } from "./presentation.js";
import { LAYOUT } from "./widget-elements.js";

const INDICATED = PAGE_PAINT_ATTRIBUTE.indicated;

// driver → attribute → key
const held = new Map();
let painted = new Set();
let listening = false;

const resolve = (owner, attribute, key) => {
  const source = referencedProjection(owner, attribute);
  return source ? addressedElements(source, key) : [];
};

function repaint() {
  const next = new Set();
  for (const [owner, keys] of held)
    for (const [attribute, key] of keys)
      for (const element of resolve(owner, attribute, key)) next.add(element);
  for (const element of painted)
    if (!next.has(element)) {
      element.removeAttribute(INDICATED);
      element.removeAttribute("aria-current");
    }
  for (const element of next)
    if (!painted.has(element)) {
      element.setAttribute(INDICATED, "");
      element.setAttribute("aria-current", "true");
    }
  painted = next;
}

/** Mark what `key` addresses in the widget `owner.getAttribute(attribute)` names, in
    place of what this owner last marked there; `null` clears. Returns whether anything
    is marked for this call. */
export function indicate(owner, attribute, key) {
  requireReference("indicate", owner, attribute);
  if (key !== null && (typeof key !== "string" || !key))
    throw new TypeError("indicate key must be a non-empty string or null");
  if (!listening) {
    listening = true;
    document.addEventListener(LAYOUT, () => {
      if (held.size || painted.size) repaint();
    });
  }
  const keys = held.get(owner) ?? new Map();
  if (key === null) keys.delete(attribute);
  else keys.set(attribute, key);
  if (keys.size) held.set(owner, keys);
  else held.delete(owner);
  repaint();
  return key !== null && resolve(owner, attribute, key).length > 0;
}
