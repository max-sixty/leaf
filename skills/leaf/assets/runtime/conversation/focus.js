/* Focus readings shared by conversation paint and commands. */
import { focused, documentFocused } from "../keyboard/scopes.js";

// Native disclosure owns the panel thread's focus stop. Inline divs have no summary,
// so their established root remains the destination.
export function focusThread(thread, options) {
  (thread.querySelector(":scope > summary") ?? thread).focus(options);
}

// The focused thread, one predicate: the row the line paints and the press the dispatcher
// takes ask the same question, so they cannot disagree about which thread this is. Not a
// control inside it, whose own press is its own. Open and resolved threads both qualify:
// each has a primary Enter action for its reply or Reopen path.
export function focusedThread() {
  const active = focused();
  return active?.matches?.(".lf-thread, .lf-conversation-thread") ? active : null;
}

// A native panel summary stands for its details in commands that move the whole
// thread. Controls deeper in the conversation keep their own command scope.
export function focusedThreadTarget() {
  const active = focused();
  return active?.matches?.(".lf-thread-summary")
    ? active.closest(".lf-thread")
    : focusedThread();
}

// The panel thread the reader is in, asked by class because that is the anchors module's
// question: which logged thread's passage to paint. It is not the box's way out, which
// climbs further and answers for a seat on the page too — the two readings stayed apart
// rather than one standing in for the other.
export function focusedThreadOf() {
  return documentFocused()?.closest?.(".lf-thread");
}

// The thread the reader is standing in, on either side — a card in the panel, a seat on
// the page — and a control inside one stands in it too: the standing floor's question,
// which is where letting go lands rather than which passage to paint.
export function standingThreadOf() {
  return documentFocused()?.closest?.(".lf-thread, .lf-conversation-thread");
}
