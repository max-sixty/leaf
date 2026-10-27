/* How many of a set of obligations are still open and whose turn each is, in the words
   `lf-tally` shows and `lf-deck`'s bar repeats, so the two never count one queue
   differently.

   The open ones split by the server's next actor. Those waiting on the user, which Next
   on me walks (`readObligations().user`), are "left to answer". Those whose next actor is
   the agent, such as one the user commented on and whose reply the agent owes
   (`obligations.discussed`), are counted under the agent's name, as its On list names
   it (`agentName`): "7 left to answer", "2 left to answer · 1 on Claude", "1 on Claude".
   So the words say something is the user's to answer exactly when Next on me is
   enabled. A frozen obligation in a resolved thread is open with no next actor, so it
   counts on neither side, and a set of only such ones reads "1 open". An earlier tally
   counted every open obligation as to answer and read "1 of 8 to answer" beside a
   disabled Next on me once the last one went to the agent. One the user set aside
   (later.js) has no next actor until its Later brings it back, and counts as later:
   "2 left to answer · 1 later". The words name no total:
   "4 of 5 to answer" beside the deck's cards read as the fifth card's position. */

import { setAside } from "./later-model.js";

export function tally(held) {
  const open = held.filter((item) => item.status === "open");
  return {
    onUser: open.filter((item) => item.next_actor === "user").length,
    onAgent: open.filter((item) => item.next_actor === "agent").length,
    later: open.filter(setAside).length,
    open: open.length,
    total: held.length,
  };
}

// The count's words, or that none is open.
export function tallyWords({ onUser, onAgent, later = 0, open, total }, agent) {
  if (!total) return "Nothing to answer";
  const parts = [
    onUser ? `${onUser} left to answer` : "",
    onAgent ? `${onAgent} on ${agent}` : "",
    later ? `${later} later` : "",
  ].filter(Boolean);
  if (parts.length) return parts.join(" · ");
  if (open) return `${open} open`;
  return total === 1 ? "Answered" : `All ${total} answered`;
}
