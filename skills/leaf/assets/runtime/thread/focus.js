/* Focus readings shared by thread paint and commands. */
import { focused } from "../keyboard/scopes.js";
import { closestAcross } from "../passages.js";

// Native disclosure owns the panel thread's focus stop. Inline divs have no summary,
// so their established root remains the destination.
export function focusThread(thread, options) {
  (thread.querySelector(":scope > summary:not([hidden])") ?? thread).focus(options);
}

// An inline thread root may itself hold focus. A control inside it keeps its own
// command scope, while panel summaries are mapped by focusedThreadTarget below.
export function focusedThread() {
  const active = focused();
  return active?.matches?.(".lf-thread, .lf-page-thread") ? active : null;
}

// A native panel summary stands for its details in commands that move the whole
// thread. Controls deeper in the thread keep their own command scope.
export function focusedThreadTarget() {
  const active = focused();
  return active?.matches?.(".lf-thread-summary")
    ? active.closest(".lf-thread")
    : focusedThread();
}

// The thread the user is in, wherever it is drawn — the Threads list, the margin card, a
// seat on the page — with a control inside one standing in it too. Climbing from the
// inner focus reaches a seat a widget stages in its shadow tree. The box's way out climbs
// further, to a seat holding no thread yet (landing.js, `heldThreadOrSeat`).
export const heldThread = () => closestAcross(focused(), ".lf-thread, .lf-page-thread");

// Its logged id: a list thread carries it as `data-id`, a card or seat as `data-thread`.
export function heldThreadId() {
  const thread = heldThread();
  return thread?.dataset.id ?? thread?.dataset.thread ?? null;
}
