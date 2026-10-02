/* Stable DOM relations shared by thread views and focus recovery. */
import { TEXT_FIELD } from "../control-selectors.js";
// A drawn thread: a card in the Threads list, or a thread on the page, in the margin or
// on a seat.
export const THREAD = ".lf-thread, .lf-page-thread";
// Where a box the user writes in belongs: a drawn thread, or a seat holding none yet.
export const SAYS_IN = `${THREAD}, .lf-thread-seat`;
export const SAY_BOX = `:scope > .lf-compose ${TEXT_FIELD}, :scope > .lf-say ${TEXT_FIELD}`;
