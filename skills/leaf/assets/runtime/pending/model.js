/* Pure readings of unresolved browser gestures.

   An entry stands here from the gesture until the log's receipt for its attempt has
   been accounted; `accounted` is that set of attempts. */
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

export const unresolvedAttempts = (entries) =>
  entries.filter((entry) => !entry.answered).map((entry) => entry.event.attempt);

const accountedAttempts = (receipts) =>
  new Set(receipts.map((receipt) => receipt.attempt).filter(Boolean));

// The standing entries the log has not yet accounted for, which the page still draws
// from the gesture rather than from the log.
const unaccounted = (entries, receipts) => {
  const accounted = accountedAttempts(receipts);
  return entries.filter(
    (entry) => !entry.rejected && !accounted.has(entry.event.attempt),
  );
};

export const pendingMessages = (entries, receipts) =>
  unaccounted(entries, receipts)
    .filter((entry) => entry.message)
    .map((entry) => entry.message);

const pendingEvents = (entries, receipts, kinds) =>
  unaccounted(entries, receipts)
    .filter((entry) => kinds.includes(entry.event.kind))
    .map((entry) => entry.event);

export const pendingReactions = (entries, receipts) =>
  unaccounted(entries, receipts)
    .filter((entry) => entry.thread?.token)
    .map((entry) => entry.thread);

export const pendingSettlements = (entries, receipts) =>
  unaccounted(entries, receipts)
    .filter(
      (entry) => entry.event.kind === "resolve" || entry.event.kind === "unresolve",
    )
    .map((entry) => ({ ...entry.event, localParent: entry.namedParent }));

export const pendingApprovals = (entries, receipts) =>
  pendingEvents(entries, receipts, ["done"]);

export const pendingRequests = (entries, receipts) =>
  pendingEvents(entries, receipts, ["request"]);

export const pendingProjectionEntries = (entries, receipts) =>
  unaccounted(entries, receipts)
    .filter((entry) => entry.projection)
    .map((entry) => entry.projection);

export const pendingForParent = (entries, id, kinds = null) =>
  entries.find(
    (entry) =>
      (entry.event.parent === id || entry.namedParent === id) &&
      (!kinds || kinds.includes(entry.event.kind)),
  );
