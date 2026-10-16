// @ts-check
/* The promises behind each event the browser is sending to the server.

   `applicationState` holds every unresolved event, in order, and where each stands.
   This ledger keeps only the promises a sender awaits, by attempt id: `answer`, which
   resolves with the admitted event or with null when it is refused, and `read`. A
   handle's `event` and `admitted` read the latest entry for its attempt. `read`
   resolves only in `present`, when the receipt is presented. */
import { applicationState, readApplication } from "../semantic-state.js";

/** @typedef {import("../../../../../build/browser/domain.ts").Event} Event */
/** @typedef {import("../../../../../build/browser/domain.ts").PendingCommand} PendingCommand */
/** @typedef {import("../../../../../build/browser/domain.ts").Command} Command */
/** @typedef {NonNullable<ReturnType<typeof applicationState.entry>>} Entry */
/** @typedef {{
 * event: Command, admitted: Event | null,
 * answer: Promise<Event | null>, read: Promise<Event>,
 * resolve: (value: Event | null) => void, resolveRead: (value: Event) => void,
 * }} DeliveryHandle */

/** @param {{newAttempt: () => string, enqueue: (event: Command) => unknown}} options */
export function createPendingLedger({ newAttempt, enqueue }) {
  /** @type {Map<string, DeliveryHandle>} */
  const handles = new Map();
  const snapshot = () => readApplication().unresolved;
  const sending = () => readApplication().effective.sending;

  return {
    /** @param {PendingCommand} event */
    enqueue(event) {
      const attempted = { ...event, attempt: event.attempt || newAttempt() };
      if (applicationState.entry(attempted.attempt)) return null;
      /** @type {PromiseWithResolvers<Event | null>} */
      const { promise: answer, resolve } = Promise.withResolvers();
      /** @type {PromiseWithResolvers<Event>} */
      const { promise: read, resolve: resolveRead } = Promise.withResolvers();
      const current = () => applicationState.entry(attempted.attempt);
      /** @type {DeliveryHandle} */
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
    /** @param {readonly Pick<Entry, "event">[]} entries */
    release: (entries) =>
      applicationState.release(new Set(entries.map((entry) => entry.event.attempt))),
    /** The gestures refused with `entry`, each answered null here.
     * @param {DeliveryHandle} entry @returns {{attempt: string, answer: Promise<Event | null>}[]} */
    refuse(entry) {
      return applicationState.refuse(entry.event.attempt).flatMap((attempt) => {
        const handle = handles.get(attempt);
        handle?.resolve(null);
        return handle ? [{ attempt, answer: handle.answer }] : [];
      });
    },
    /** @param {DeliveryHandle} entry @param {Event} event */
    accept(entry, event) {
      applicationState.accept(entry.event.attempt, event);
    },
    /** @param {Event[]} receipts */
    present(receipts) {
      const left = applicationState.present(receipts);
      for (const receipt of receipts)
        if (receipt.attempt) handles.get(receipt.attempt)?.resolveRead(receipt);
      return left.length > 0;
    },
    /** @param {DeliveryHandle} entry */
    nameEvents(entry) {
      return applicationState.nameEvents(entry.event.attempt);
    },
  };
}
