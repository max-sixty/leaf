/* What an item on On me or On <agent> offers and what a row calls it. The server selects
 * the queues (`served_state.queues`) and the application publisher places this tab's sends
 * against them; an ask is answered through its source, and only a to-do on the
 * user, one the agent opened on them, offers Done. */

export const queueOffers = (item, ready, onUser) => ({
  open: ready,
  done: ready && onUser && item.kind === "todo",
});

export const itemNoun = (item) =>
  item.kind === "answer" && item.answer?.kind === "reply" ? "reply" : item.kind;

// How a finished item other than an ask ended, in the words its row says: a reply the
// agent sent, or a to-do's outcome. An ask says its own ending (asks/answer.js).
const OUTCOMES = Object.freeze({ done: "Done", failed: "Failed", dropped: "Dropped" });
export const itemOutcome = (item) =>
  item.kind === "answer" ? "Sent" : (OUTCOMES[item.state] ?? item.state);
