/* What a queue item offers and what a row calls it. The server selects the queues
 * (`served_state.queues`) and the application publisher places this tab's sends
 * against them; a Question is answered through its source, and only a task on the
 * user, one the agent opened on them, offers Done. */

export const queueOffers = (item, ready, onYou) => ({
  open: ready,
  done: ready && onYou && item.kind === "task",
});

export const taskNoun = (item) =>
  item.kind === "answer" && item.answer?.kind === "reply" ? "reply" : item.kind;
