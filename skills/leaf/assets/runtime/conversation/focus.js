/* Focus readings shared by conversation paint and commands. */
import { focused, documentFocused } from "../keyboard/scopes.js";

// The focused thread, one predicate: the row the line paints and the press the dispatcher
// takes ask the same question, so they cannot disagree about which thread this is. Not a
// control inside it, whose own press is its own. Open and resolved threads both qualify:
// each has a primary Enter action for its reply or Reopen path.
export function focusedThread() {
  const active = focused();
  return active?.matches?.(".lf-thread, .lf-conversation-thread") ? active : null;
}

// The panel thread the reader is in, asked by class because that is the anchors module's
// question: which logged thread's passage to paint. It is not the box's way out, which
// climbs further and answers for a seat on the page too — the two readings stayed apart
// rather than one standing in for the other.
export function focusedThreadOf() {
  return documentFocused()?.closest?.(".lf-thread");
}
