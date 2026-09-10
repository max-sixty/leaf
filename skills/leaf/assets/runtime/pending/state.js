/* The one ordered ledger of browser gestures not yet accounted by an applied state.

   This module owns records only. Delivery and presentation receive the ledger from the
   application composition root; readers receive snapshots and narrow queries. */
import {
  conversationForAttempt,
  isConversationEvent,
  isMessageEvent,
} from "./model.js";
import { PENDING } from "../conversation/identity.js";

export function createPendingLedger({ newAttempt, now }) {
  const entries = [];
  let order = 0;

  const remove = (entry) => {
    const index = entries.indexOf(entry);
    if (index >= 0) entries.splice(index, 1);
  };

  const withdrawChildren = (entry) => {
    const parent = entry.message?.id;
    if (!parent) return;
    for (const child of [...entries])
      if (child !== entry && child.event.parent === parent) {
        remove(child);
        child.resolve(null);
      }
  };

  return {
    enqueue(event) {
      const attempted = { ...event, attempt: event.attempt || newAttempt() };
      if (entries.some((entry) => entry.event.attempt === attempted.attempt))
        return null;
      let resolve;
      let resolveRead;
      const answer = new Promise((done) => {
        resolve = done;
      });
      const read = new Promise((done) => {
        resolveRead = done;
      });
      const conversation = isConversationEvent(attempted)
        ? conversationForAttempt(attempted, now())
        : null;
      const entry = {
        event: attempted,
        answer,
        resolve,
        read,
        resolveRead,
        answered: false,
        rejected: false,
        readEvent: null,
        order: ++order,
        localId: Symbol("uncommitted local action"),
        projection: null,
        conversation,
        message: isMessageEvent(attempted) ? conversation : null,
      };
      entries.push(entry);
      return entry;
    },
    snapshot: () => [...entries],
    nextUnanswered: () => entries.find((entry) => !entry.answered) ?? null,
    hasUnresolved: () => entries.length > 0,
    remove,
    reject(entry) {
      entry.answered = true;
      entry.acceptedId = null;
      entry.rejected = entry.event.kind === "action";
      withdrawChildren(entry);
      if (entry.event.kind !== "action") remove(entry);
    },
    accept(entry, event) {
      entry.answered = true;
      entry.acceptedId = event?.id ?? null;
      if (entry.event.kind !== "action" && entry.readEvent) remove(entry);
    },
    account(receipts) {
      let removed = false;
      for (const entry of [...entries]) {
        const accepted = receipts.find(
          (candidate) => candidate.attempt === entry.event.attempt,
        );
        if (!accepted) continue;
        entry.readEvent = accepted;
        entry.resolveRead(accepted);
        if (entry.answered && entry.event.kind !== "action") {
          remove(entry);
          removed = true;
        }
      }
      return removed;
    },
    nameParent(entry, receipts) {
      const parent = entry.event.parent;
      if (typeof parent !== "string" || !parent.startsWith(PENDING)) return;
      const attempt = parent.slice(PENDING.length);
      const named =
        entries.find((candidate) => candidate.event.attempt === attempt)?.acceptedId ??
        receipts.find((candidate) => candidate.attempt === attempt)?.id;
      if (!named) return;
      entry.namedParent = parent;
      entry.event.parent = named;
    },
  };
}
