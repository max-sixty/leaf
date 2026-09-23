/* Focus readings shared by conversation paint and commands. */
import { focused, documentFocused } from "../keyboard/scopes.js";

// Native disclosure owns the panel thread's focus stop. Inline divs have no summary,
// so their established root remains the destination.
export function focusThread(thread, options) {
  (thread.querySelector(":scope > summary:not([hidden])") ?? thread).focus(options);
}

// An inline conversation root may itself hold focus. A control inside it keeps its own
// command scope, while panel summaries are mapped by focusedThreadTarget below.
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

// The panel thread the user is in, asked by class because that is the anchors module's
// question: which logged thread's passage to paint. It is not the box's way out, which
// climbs further and answers for a seat on the page too — the two readings stayed apart
// rather than one standing in for the other.
export function focusedThreadOf() {
  return documentFocused()?.closest?.(".lf-thread");
}

// The thread the user is standing in, on either side — a card in the panel, a seat on
// the page — and a control inside one stands in it too: the standing floor's question,
// which is where letting go lands rather than which passage to paint.
export function standingThreadOf() {
  return documentFocused()?.closest?.(".lf-thread, .lf-conversation-thread");
}
