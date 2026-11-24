/* The name Leaf's own surfaces show for a thing, for packages (`nameOf`): an element's,
   the page's, a thread's or an On list row's. Each owner keeps its rule, and the
   runtime's surfaces call the owner; this module only chooses among them by what it is
   handed, so a widget that names one of these agrees with the panel, Threads and On Me
   without knowing which rule names it.

   Two decisions, each with the alternative a later change might reach for:

   - A comment's anchor is not a kind `nameOf` takes. Its words are its place and the
     words it quotes, read in its thread's `about`, so a caller passes a second argument
     only an anchor reads and must know it holds an anchor to pass it. Folding it in
     would put that rule under this name behind an option; `anchorLabel` stays its
     own function.
   - An element with no name gets "", not the word for its kind. Callers fall back
     differently (the kind word, "the" and the word, the page's title, nothing), and
     each fallback is words the user reads, so a fallback here would change them. */
import { addressableLabel } from "./addressable-names.js";
import { queueTitle } from "./queue-title.js";
import { authoredTitle } from "./tab-title.js";
import { threadName } from "./thread/messages.js";

/** @typedef {import("./thread/workflow.js").ThreadRecord} Thread */
/** @typedef {import("./queue-api.js").CurrentQueueItem} Row */

/** The name Leaf's surfaces show for `thing`, or "" where they show none.
    @param {Element | Document | Thread | Row | null | undefined} thing */
export function nameOf(thing) {
  if (!thing) return "";
  if ("nodeType" in thing)
    return thing.nodeType === Node.DOCUMENT_NODE
      ? authoredTitle(/** @type {Document} */ (thing))
      : addressableLabel(/** @type {Element} */ (thing));
  return "msgs" in thing ? threadName(thing) : queueTitle(thing);
}
