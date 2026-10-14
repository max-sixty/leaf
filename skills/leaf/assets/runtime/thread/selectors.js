/* Stable DOM relations shared by thread views and focus recovery. */
import { TEXT_FIELD } from "../control-selectors.js";
// A drawn thread: a card in the Threads list, a thread on the page, in the margin or
// on a seat, or a chrome's view of one thread (`data-lf-thread-view`, as the floating
// panel's thread view is), whose reply the presentation draws outside it and names as
// the thread's reply destination (mirrors.js, `replyBox`). Each names its thread's id
// in `data-id` or `data-thread`, so focus anywhere in one stands in that thread for
// every reading of it, `c` included.
export const THREAD = ".lf-thread, .lf-page-thread, [data-lf-thread-view]";
// Where a box the user writes in belongs: a drawn thread, or a seat holding none yet.
export const SAYS_IN = `${THREAD}, .lf-thread-seat`;
export const SAY_ROW = ".lf-thread-reply, .lf-say";
export const SAY_BOX = SAY_ROW.split(", ")
  .map((row) => `:scope > ${row} ${TEXT_FIELD}`)
  .join(", ");
