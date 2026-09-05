/* What a disclosure answers to, read off the element rather than declared per row.

   A disclosure adds ← and →, which no browser answers, so its row runs the press itself —
   through the element's own click, so keyboard and pointer stay one behaviour. They sit
   on the row that already carries Enter and Space rather than a row of their own, because
   two rows changing one thing spend both of the key line's hints saying one word twice.

   Only the direction that changes something is bound: → over a shut section, ← over an
   open one, and both where the reader is standing on no disclosure at all, which is the
   question the reference asks. So every key a surface names is a key that works, and the
   row's one word covers the three keys it binds.

   `DISCLOSE` answers that for an element, and every row over a disclosure reads it — this
   scope's, and a widget's own row re-wording the same press. Two rows naming different
   sets is not two promises but one: `lineRows` prints the nearer row and drops the other
   whole, so a widget naming one key fewer takes the rest off the line, and one key more
   promises what nothing runs. It also answers where the element stands, the arrows being
   named only where this scope reaches: a widget's disclosure inside a comment message
   keeps the platform's pair alone.

   One scope covers both spellings, `details > summary` and ARIA's disclosure pattern
   (`aria-expanded` on a button), because a reader standing on a settled group cannot see
   which of the two they are standing on. A widget keeping the pattern is covered by
   keeping it rather than by being named. The attribute alone would be too wide: a
   combobox wears it over a box words are typed into, and a treeitem in a walk of its own,
   where the arrows belong to the caret and the walk.

   Which way a disclosure stands is watched as state, not heard as an event. A `toggle` is
   not composed, so one from a shadow-staged `<details>` reaches no document listener, and
   an `aria-expanded` control fires nothing anywhere. Both keep that state in an
   attribute, so one `MutationObserver` over `open` and `aria-expanded` repaints for both,
   and `shadowStage` hands it each root. */
import { PRESS } from "./bindings.js";
import { paintKeys } from "./scopes.js";
import { disclosed } from "./page.js";
import { inChrome } from "../passages.js";

// Where a disclosure keeps which way it stands, in both spellings. Declared up here
// because `shadowStage` calls it, far above the surfaces it repaints for.
// This pair is what DISCLOSE reads, so a toggle moves every row bound through it — and a
// row's keys are named on two surfaces, the line the reader sees and the
// `aria-keyshortcuts` a listener is read. Repainting the line alone left the attribute
// standing whichever way the row was when its scope was declared, naming the arrow that no
// longer moves the section and withholding the one that does. `paintKeys()` is the superset
// — it revalidates the connected scopes and ends in `paintHere()` — so the watcher that
// already hears this write is the one place both surfaces are kept together, rather than a
// repaint each DISCLOSE row has to remember for itself.
// A write that says what the attribute already said is not a disclosure changing, and
// taking it for one closes a loop: paintCoreControls paints `aria-expanded` on the key
// line's More control, so every paint scheduled the next one and the page repainted for
// as long as it was open. Reading the old value is what tells the two apart. A real
// toggle still arrives, including one that lands back where it started, because the
// record for its return leg carries the other value.
const disclosureWatch = new MutationObserver((records) => {
  if (records.some((r) => r.target.getAttribute(r.attributeName) !== r.oldValue))
    paintKeys();
});
export const watchDisclosures = (root) =>
  disclosureWatch.observe(root, {
    subtree: true,
    attributeFilter: ["open", "aria-expanded"],
    attributeOldValue: true,
  });

export const DISCLOSE = (el) => {
  const open = disclosed(el);
  if (open === null) return [...PRESS, "ArrowLeft", "ArrowRight"];
  return inChrome(el) ? PRESS : [...PRESS, open ? "ArrowLeft" : "ArrowRight"];
};
