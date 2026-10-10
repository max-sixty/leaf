// @ts-check
/* Transport handles for the application's immutable, ordered pending attempts.

   The semantic root owns every event and its lifecycle state. This adapter retains only
   promises and their resolvers; an in-flight delivery reads its latest record by attempt
   id. Presentation accounting is the only door that resolves a receipt read race. */
import { applicationState, readApplication } from "../semantic-state.js";

/** @typedef {import("../../../../../build/browser/domain.ts").Event} Event */
/** @typedef {import("../../../../../build/browser/domain.ts").PendingCommand} PendingCommand */
/** @typedef {import("../../../../../build/browser/domain.ts").Command} Command */
/** @typedef {NonNullable<ReturnType<typeof applicationState.entry>>} Entry */
/** @typedef {{
 * event: Command, message: Entry["message"], admitted: Event | null,
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
    /** @param {readonly Pick<Entry, "event">[]} entries */
    release: (entries) =>
      applicationState.release(new Set(entries.map((entry) => entry.event.attempt))),
    /** @param {DeliveryHandle} entry */
    refuse(entry) {
      for (const attempt of applicationState.refuse(entry.event.attempt))
        handles.get(attempt)?.resolve(null);
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
    /** @param {DeliveryHandle} entry @param {Event[]} receipts */
    nameParent(entry, receipts) {
      applicationState.nameParent(entry.event.attempt, receipts);
    },
    /** @param {DeliveryHandle} entry @param {Event[]} receipts */
    nameUndo(entry, receipts) {
      return applicationState.nameUndo(entry.event.attempt, receipts);
    },
  };
}
