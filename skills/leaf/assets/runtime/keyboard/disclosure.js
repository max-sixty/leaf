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

let publishedDisclosure;
export const DISCLOSE = (...args) => publishedDisclosure(...args);

export function createDisclosure({ disclosed, inChrome }) {
  publishedDisclosure = (el) => {
    const open = disclosed(el);
    if (open === null) return [...PRESS, "ArrowLeft", "ArrowRight"];
    return inChrome(el) ? PRESS : [...PRESS, open ? "ArrowLeft" : "ArrowRight"];
  };
}
