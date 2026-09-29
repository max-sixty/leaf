/* Transport handles for the application's immutable, ordered pending attempts.

   The semantic root owns every event and its lifecycle state. This adapter retains only
   promises and their resolvers; an in-flight delivery reads its latest record by attempt
   id. Presentation accounting is the only door that resolves a receipt read race. */
import { applicationState, readApplication } from "../semantic-state.js";

export function createPendingLedger({ newAttempt, enqueue }) {
  const handles = new Map();
  const snapshot = () => readApplication().unresolved;
  const sending = () => readApplication().effective.sending;

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
        get admitted() {
          return current()?.admitted ?? null;
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
      enqueue(attempted);
      return handle;
    },
    snapshot,
    sending,
    nextSending: () => {
      const [attempt] = sending();
      return attempt ? handles.get(attempt) : null;
    },
    releasable: () => applicationState.releasable(),
    release: (entries) =>
      applicationState.release(new Set(entries.map((entry) => entry.event.attempt))),
    refuse(entry) {
      for (const attempt of applicationState.refuse(entry.event.attempt))
        handles.get(attempt)?.resolve(null);
    },
    accept(entry, event) {
      applicationState.accept(entry.event.attempt, event);
    },
    present(receipts) {
      const left = applicationState.present(receipts);
      for (const receipt of receipts)
        handles.get(receipt.attempt)?.resolveRead(receipt);
      return left.length > 0;
    },
    nameParent(entry, receipts) {
      applicationState.nameParent(entry.event.attempt, receipts);
    },
    nameUndo(entry, receipts) {
      return applicationState.nameUndo(entry.event.attempt, receipts);
    },
  };
}
