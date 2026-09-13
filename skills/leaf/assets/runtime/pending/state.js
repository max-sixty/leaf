/* Transport handles for the application's immutable, ordered pending attempts.

   The semantic root owns every event and status. This adapter retains only promises
   and their resolvers; an in-flight delivery reads its latest record by attempt id.
   Presentation accounting is the only door that resolves a receipt read race. */
import { applicationState, readApplication } from "../semantic-state.js";

export function createPendingLedger({ newAttempt, now }) {
  const handles = new Map();
  const snapshot = () => readApplication().unresolved;
  const remove = (entry) => applicationState.remove(new Set([entry.event.attempt]));

  return {
    enqueue(event) {
      const attempted = { ...event, attempt: event.attempt || newAttempt() };
      if (applicationState.entry(attempted.attempt)) return null;
      let resolve;
      let resolveRead;
      const answer = new Promise((done) => {
        resolve = done;
      });
      const read = new Promise((done) => {
        resolveRead = done;
      });
      const current = () => applicationState.entry(attempted.attempt);
      const handle = {
        get event() {
          return current()?.event ?? attempted;
        },
        get projection() {
          return current()?.projection ?? null;
        },
        get message() {
          return current()?.message ?? null;
        },
        get readEvent() {
          return current()?.readEvent ?? null;
        },
        answer,
        read,
        resolve(value) {
          resolve(value);
          handles.delete(attempted.attempt);
        },
        resolveRead,
      };
      handles.set(attempted.attempt, handle);
      applicationState.enqueue(attempted, now());
      return handle;
    },
    snapshot,
    nextUnanswered: () => {
      const entry = snapshot().find((entry) => !entry.answered);
      return entry ? handles.get(entry.event.attempt) : null;
    },
    hasUnresolved: () => snapshot().length > 0,
    remove,
    reject(entry) {
      for (const attempt of applicationState.reject(entry.event.attempt))
        if (attempt !== entry.event.attempt) handles.get(attempt)?.resolve(null);
    },
    accept(entry, event) {
      applicationState.accept(entry.event.attempt, event);
    },
    account(receipts) {
      const removed = applicationState.accountPresented(receipts);
      for (const receipt of receipts)
        handles.get(receipt.attempt)?.resolveRead(receipt);
      return removed.length > 0;
    },
    nameParent(entry, receipts) {
      applicationState.nameParent(entry.event.attempt, receipts);
    },
    nameUndo(entry, receipts) {
      return applicationState.nameUndo(entry.event.attempt, receipts);
    },
  };
}
