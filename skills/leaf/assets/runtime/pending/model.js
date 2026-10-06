/* Pure readings of the events an unresolved browser gesture carries.

   The ledger holding each gesture, and the lifecycle that decides when it leaves, belong
   to the application publisher (`build/browser/application.ts`). */
import { PENDING } from "../thread/identity.js";

export const isThreadEvent = (event) =>
  event.kind === "comment" || event.kind === "reply";

export const isMessageEvent = (event) => isThreadEvent(event) && !event.token;

// A gesture that speaks in a thread, so hands it to the agent: words, or the user
// rewriting words of theirs (`events.exchange`).
export const isTurnEvent = (event) => isMessageEvent(event) || event.kind === "edit";

// The message a turn shows on: a rewrite's message, else its own (`events.turn_message`).
export const turnMessage = (turn) => (turn.kind === "edit" ? turn.message : turn.id);

export const threadForAttempt = (event, timestamp) => ({
  ...event,
  id: `${PENDING}${event.attempt}`,
  author: "user",
  ts: timestamp,
  pending: true,
});

export const pendingForParent = (entries, id, kinds = null) =>
  entries.find(
    (entry) =>
      (entry.event.parent === id || entry.namedParent === id) &&
      (!kinds || kinds.includes(entry.event.kind)),
  );
