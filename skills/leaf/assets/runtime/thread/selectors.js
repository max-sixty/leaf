/* Stable DOM relations shared by thread views and focus recovery. */
import { TEXT_FIELD } from "../control-selectors.js";
// A drawn thread: a card in the Threads list, or a thread on the page, in the margin or
// on a seat.
export const THREAD = ".lf-thread, .lf-page-thread";
// The logged id a drawn thread carries: a Threads card as `data-id`, a thread on the page,
// in the margin or on a seat as `data-thread`, so a selector says which surface it means
// (`.lf-thread[data-id]` is a Threads card). Each reader of the id takes it from here.
export const drawnThreadId = (node) => node?.dataset.id ?? node?.dataset.thread ?? null;
// Where a box the user writes in belongs: a drawn thread, or a seat holding none yet.
export const SAYS_IN = `${THREAD}, .lf-thread-seat`;
export const SAY_ROW = ".lf-thread-reply, .lf-say";
export const SAY_BOX = SAY_ROW.split(", ")
  .map((row) => `:scope > ${row} ${TEXT_FIELD}`)
  .join(", ");
