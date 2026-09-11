/* The one ordered ledger of browser gestures not yet accounted by an applied state.

   This module owns records only. Delivery and presentation receive the ledger from the
   application composition root; readers receive snapshots and narrow queries. An undo
   may retain the exact pending action record it depends on, so serialized delivery can
   replace that local identity with the accepted event id or discard both on refusal. */
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

  const withdrawDependents = (entry) => {
    const parent = entry.message?.id;
    for (const child of [...entries])
      if (
        child !== entry &&
        ((parent && child.event.parent === parent) || child.undoTarget === entry)
      ) {
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
        undoTarget:
          attempted.kind === "undo" && typeof attempted.undoes === "symbol"
            ? (entries.find((candidate) => candidate.localId === attempted.undoes) ??
              null)
            : null,
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
      withdrawDependents(entry);
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
    nameUndo(entry, receipts) {
      if (entry.event.kind !== "undo" || typeof entry.event.undoes !== "symbol")
        return true;
      const target = entry.undoTarget;
      const named =
        target?.acceptedId ??
        receipts.find((candidate) => candidate.attempt === target?.event.attempt)?.id;
      if (named) {
        entry.event.undoes = named;
        return true;
      }
      return false;
    },
  };
}
