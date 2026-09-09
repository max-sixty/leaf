/* Pure readings of unresolved browser gestures. */
import { PENDING } from "../conversation/identity.js";

export const isMessageEvent = (event) =>
  (event.kind === "comment" || event.kind === "reply") && !event.token;

export const messageForAttempt = (event, timestamp) => ({
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
    .filter((entry) => entry.message && !read.has(entry.event.attempt))
    .map((entry) => entry.message);
};

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
