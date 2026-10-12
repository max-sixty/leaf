/* What an item on Questions or Tasks offers and what a row calls it. The server selects the queues
 * (`served_state.queues`) and the application publisher places this tab's sends
 * against them; an ask is answered through its source, and only a to-do on the
 * user, one the agent opened on them, offers Done. */

export const queueOffers = (item, ready, onUser) => ({
  open: ready,
  done: ready && onUser && item.kind === "todo",
});

export const taskNoun = (item) =>
  item.kind === "answer" && item.answer?.kind === "reply" ? "reply" : item.kind;
