/* Pure readings of unresolved browser gestures. */
import { PENDING } from "../conversation/identity.js";

export const isConversationEvent = (event) =>
  event.kind === "comment" || event.kind === "reply";

export const isMessageEvent = (event) => isConversationEvent(event) && !event.token;

export const conversationForAttempt = (event, timestamp) => ({
  ...event,
  id: `${PENDING}${event.attempt}`,
  author: "user",
  ts: timestamp,
  pending: true,
});

export const unresolvedAttempts = (entries) =>
  entries.filter((entry) => !entry.answered).map((entry) => entry.event.attempt);

export const unreadMessages = (entries, receipts) => {
  const read = new Set(receipts.map((receipt) => receipt.attempt).filter(Boolean));
  return entries
    .filter(
      (entry) => entry.message && !entry.rejected && !read.has(entry.event.attempt),
    )
    .map((entry) => entry.message);
};

const unreadEvents = (entries, receipts, kinds) => {
  const read = new Set(receipts.map((receipt) => receipt.attempt).filter(Boolean));
  return entries
    .filter(
      (entry) =>
        !entry.rejected &&
        kinds.includes(entry.event.kind) &&
        !read.has(entry.event.attempt),
    )
    .map((entry) => entry.event);
};

export const pendingReactions = (entries, receipts) => {
  const read = new Set(receipts.map((receipt) => receipt.attempt).filter(Boolean));
  return entries
    .filter(
      (entry) =>
        entry.conversation?.token && !entry.rejected && !read.has(entry.event.attempt),
    )
    .map((entry) => entry.conversation);
};

export const pendingSettlements = (entries, receipts) => {
  const read = new Set(receipts.map((receipt) => receipt.attempt).filter(Boolean));
  return entries
    .filter(
      (entry) =>
        !entry.rejected &&
        (entry.event.kind === "resolve" || entry.event.kind === "unresolve") &&
        !read.has(entry.event.attempt),
    )
    .map((entry) => ({ ...entry.event, localParent: entry.namedParent }));
};

export const pendingApprovals = (entries, receipts) =>
  unreadEvents(entries, receipts, ["done"]);

export const pendingRequests = (entries, receipts) =>
  unreadEvents(entries, receipts, ["request"]);

export const pendingProjectionEntries = (entries, receipts) => {
  const read = new Set(receipts.map((receipt) => receipt.attempt).filter(Boolean));
  return entries
    .filter(
      (entry) => entry.projection && !entry.rejected && !read.has(entry.event.attempt),
    )
    .map((entry) => entry.projection);
};

export const pendingForParent = (entries, id, kinds = null) =>
  entries.find(
    (entry) =>
      (entry.event.parent === id || entry.namedParent === id) &&
      (!kinds || kinds.includes(entry.event.kind)),
  );
