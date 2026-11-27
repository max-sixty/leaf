// Compiled from state.ts by build/typescript.mjs; edit that file.
/* The promises behind each event the browser is sending to the server.

   `applicationState` holds every unresolved event, in order, and where each stands.
   This ledger keeps only the promises a sender awaits, by attempt id: `answer`, which
   resolves with the admitted event or with null when it is refused, and `read`. A
   handle's `event` and `admitted` read the latest entry for its attempt. `read`
   resolves only in `present`, when the receipt is presented. */
import { applicationState, readApplication } from "../../state/semantic-state.js";

export function createPendingLedger({ newAttempt, enqueue }) {
  const handles = new Map();
  const snapshot = () => readApplication().unresolved;
  const sending = () => readApplication().effective.sending;

  return {
    enqueue(event) {
      const attempted = { ...event, attempt: event.attempt || newAttempt() };
      if (applicationState.entry(attempted.attempt)) return null;
      const { promise: answer, resolve } = Promise.withResolvers();
      const { promise: read, resolve: resolveRead } = Promise.withResolvers();
      const current = () => applicationState.entry(attempted.attempt);
      const handle = {
        get event() {
          return current()?.event ?? attempted;
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
    nextSending: () => {
      const [attempt] = sending();
      return attempt ? handles.get(attempt) : null;
    },
    releasable: () => applicationState.releasable(),
    release: (entries) =>
      applicationState.release(new Set(entries.map((entry) => entry.event.attempt))),
    /** The gestures refused with `entry`, each answered null here. */
    refuse(entry) {
      return applicationState.refuse(entry.event.attempt).flatMap((attempt) => {
        const handle = handles.get(attempt);
        handle?.resolve(null);
        return handle ? [{ attempt, answer: handle.answer }] : [];
      });
    },
    accept(entry, event) {
      applicationState.accept(entry.event.attempt, event);
    },
    // A document pass drawing these logged events has run; each that carries an
    // attempt is that gesture's receipt.
    present(events) {
      applicationState.present(events);
      for (const event of events)
        if (event.attempt) handles.get(event.attempt)?.resolveRead(event);
    },
    nameEvents(entry) {
      return applicationState.nameEvents(entry.event.attempt);
    },
  };
}
