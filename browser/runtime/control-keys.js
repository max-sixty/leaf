/* Direction-aware disclosure keys, read from the control: the library's press and
   row arrows (lib/keys.js), with the arrow that opens or shuts a disclosure on the
   page. A disclosure in Leaf's chrome, such as one in a widget a Thread reply holds,
   keeps the press alone. A host may bind the declared keys; computing them needs no
   page dispatcher. */
import { PRESS, rowArrows } from "./lib/keys.js";
import { inChrome } from "./ui-marks.js";

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
