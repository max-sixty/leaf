/* Stable DOM relations shared by thread views and focus recovery. */
import { closestAcross } from "../passages.js";
import { upFrom } from "../shadow.js";
import { TEXT_FIELD } from "../control-selectors.js";
// A drawn thread: a thread on the page, in the margin or on a seat, or a chrome's view
// of one thread (`data-lf-thread-view`, as the floating panel's thread view and its head
// are), whose reply and Resolve the presentation draws outside it and declares on it
// (`threadPart`, below). Each names its thread's id in `data-thread`, so focus
// anywhere in one stands in that thread for every reading of it, `c` included.
export const THREAD = ".lf-page-thread, [data-lf-thread-view]";
// The logged id a drawn thread carries. Each reader of the id takes it from here.
export const drawnThreadId = (node) => node?.dataset.thread ?? null;
// Where a box the user writes in belongs: a drawn thread, or a seat holding none yet.
export const SAYS_IN = `${THREAD}, .lf-thread-seat`;
export const SAY_ROW = ".lf-thread-reply, .lf-say";
export const SAY_BOX = SAY_ROW.split(", ")
  .map((row) => `:scope > ${row} ${TEXT_FIELD}`)
  .join(", ");

// A drawn thread's own parts: the box its reply is written in, and the control that
// settles it, whose `lf-resolve` or `lf-reopen` says which way. A card draws both inside
// itself. A presentation that draws one elsewhere, as the floating panel draws the reply
// as its field and Resolve on its view's head line, declares on the thread element
// where each stands (`declareThreadParts`): `reply` and `settlement`, each a function of
// that element answering the part, or null while the thread has none there. Every reading
// of a thread's reply or settlement goes through here (`threadPart`), so Enter, `r` and
// `c` answer alike whichever chrome draws the thread. A thread drawn in pieces within
// one that declares, as a reader's message parts in the panel's view, has the
// enclosing drawing's parts where it holds none (`drawingsOf`).
//
// Such a presentation also declares `whole`, the element standing for the thread as a
// whole where its pieces stand apart, as the panel's view does for its head and its
// field (`wholeThread`).
const declaredParts = new WeakMap();
export const declareThreadParts = (thread, parts) => declaredParts.set(thread, parts);
const ownParts = {
  reply: (thread) => thread.querySelector(SAY_BOX),
  settlement: (thread) =>
    [...thread.querySelectorAll(".lf-resolve, .lf-reopen")].find(
      (control) => control.closest(THREAD) === thread,
    ) ?? null,
};
// The drawings of one thread from `thread` outward: itself, then each drawing of the
// same thread around it.
function* drawingsOf(thread) {
  const id = drawnThreadId(thread);
  for (
    let at = thread;
    at === thread || (at && id && drawnThreadId(at) === id);
    at = closestAcross(upFrom(at), THREAD)
  )
    yield at;
}
// The whole of the thread drawn at `thread`: its outermost drawing, or the element that
// drawing declares as the whole. It holds the thread's messages, so a reading of them
// searches it, and it is the thread a keyboard stands on, as a reply box's way back.
export function wholeThread(thread) {
  const outer = [...drawingsOf(thread)].at(-1);
  return declaredParts.get(outer)?.whole(outer) ?? outer;
}
export function threadPart(thread, name) {
  for (const at of drawingsOf(thread)) {
    const part = (declaredParts.get(at) ?? ownParts)[name](at);
    if (part) return part;
  }
  return null;
}
