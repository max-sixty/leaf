/* Pure readings of the events an unresolved browser gesture carries.

   The ledger holding each gesture, and the lifecycle that decides when it leaves, belong
   to the application publisher (`build/browser/application.ts`). */
import { PENDING } from "../thread/identity.js";

export const isThreadEvent = (event) =>
  event.kind === "comment" || event.kind === "reply";

export const isMessageEvent = (event) => isThreadEvent(event) && !event.token;

export const threadForAttempt = (event, timestamp) => ({
  ...event,
  id: `${PENDING}${event.attempt}`,
  author: "user",
  ts: timestamp,
  pending: true,
});

// Whether a turn is the user's gesture in this page: `entries`, the ledger, still holds
// its attempt, as it does in the turn they send it. Their words from another tab, or a
// turn a surface first draws after the log answered it, arrive like the agent's.
export const sentHere = (entries) => {
  const attempts = new Set(entries.map(({ event }) => event.attempt));
  return ({ author, attempt }) => author === "user" && attempts.has(attempt);
};

export const pendingForParent = (entries, id, kinds = null) =>
  entries.find(
    (entry) =>
      (entry.event.parent === id || entry.namedParent === id) &&
      (!kinds || kinds.includes(entry.event.kind)),
  );
