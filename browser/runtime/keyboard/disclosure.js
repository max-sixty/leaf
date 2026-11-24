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

   Which way a disclosure stands is watched as state, not heard as an event. A `toggle` is
   not composed, so one from a shadow-staged `<details>` reaches no document listener, and
   an `aria-expanded` control fires nothing anywhere. Both keep that state in an
   attribute, so one `MutationObserver` over `open` and `aria-expanded` repaints for both,
   and `shadowStage` hands it each root. */
import { PRESS, rowArrows } from "../lib/keys.js";
import { inChrome } from "../ui-marks.js";
import { paintKeysWithin } from "./scopes.js";

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

// Where a disclosure keeps which way it stands, in both spellings. Declared up here
// because `shadowStage` calls it, far above the surfaces it repaints for.
// A toggle writes one of this pair and reports nothing to the keyboard, so the watch
// reports it: the scopes on, in and around the control that moved read their rows again
// (scopes.js, `paintKeysWithin`), since a row may read which way it stands. The
// page's own row needs no repaint, the dispatcher reading DISCLOSE as it is asked.
// A write that says what the attribute already said is not a disclosure changing, and
// taking it for one closes a loop: a key paint that writes `aria-expanded` on a
// control would schedule the next paint with every paint, and the page would repaint
// for as long as the disclosure stood open. Reading the old value is what tells the two apart. A real
// toggle still arrives, including one that lands back where it started, because the
// record for its return leg carries the other value.
const disclosureWatch = new MutationObserver((records) => {
  // Every record is an attribute's, so its target is an element.
  for (const r of records)
    if (
      r.target instanceof Element &&
      r.attributeName !== null &&
      r.target.getAttribute(r.attributeName) !== r.oldValue
    )
      paintKeysWithin(r.target);
});
/** @param {Node} root */
export const watchDisclosures = (root) =>
  disclosureWatch.observe(root, {
    subtree: true,
    attributeFilter: ["open", "aria-expanded"],
    attributeOldValue: true,
  });
