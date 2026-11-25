/* What a disclosure answers to, read off the element rather than declared per row.

   A disclosure adds ← and →, which no browser answers, so its row runs the press itself —
   through the element's own click, so keyboard and pointer stay one behaviour. They sit
   on the row that already carries Enter and Space rather than a row of their own, because
   two rows changing one thing spend two hints saying one word twice.

   Only the direction that changes something is bound: → over a shut section, ← over an
   open one, mirrored in right-to-left text, where the marker points left; and both where
   the user is on no disclosure at all, which is the question the reference asks.
   So every key a surface names is a key that works, and the row's one word covers the
   three keys it binds.

   `DISCLOSE` answers that for an element, and the page's one row over every disclosure
   reads it (page.js), a widget's among them, so a widget declares no row for its own.
   A disclosure in Leaf's chrome, such as one in a widget a Thread reply holds, keeps
   the platform's pair alone. The row doesn't reach it there, so the reference, which
   lists the row wherever the user is, names no arrow while they are on one.

   One scope covers both spellings, `details > summary` and ARIA's disclosure pattern
   (`aria-expanded` on a button), because a user on a settled group cannot see
   which of the two they are on. A widget keeping the pattern is covered by
   keeping it rather than by being named. The attribute alone would be too wide: a
   combobox wears it over a box words are typed into, and a treeitem in a walk of its own,
   where the arrows belong to the caret and the walk.

   Which way a disclosure stands is read off its attribute, `open` or `aria-expanded`,
   each time the dispatcher or the reference asks. The row names no control and seats no
   badge, so no painted surface holds its keys between asks, and nothing watches for a
   toggle. */
import { PRESS, rowArrows } from "../../lib/keys.js";
import { inChrome } from "../../base/ui-marks.js";

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
