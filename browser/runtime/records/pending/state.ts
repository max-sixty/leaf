/* The promises behind each event the browser is sending to the server.

   `applicationState` holds every unresolved event, in order, and where each stands.
   This ledger keeps only the promises a sender awaits, by attempt id: `answer`, which
   resolves with the admitted event or with null when it is refused, and `read`. A
   handle's `event` and `admitted` read the latest entry for its attempt. `read`
   resolves only in `present`, when the receipt is presented. */
import { applicationState, readApplication } from "../../state/semantic-state.js";
import type { Command, Event, PendingCommand } from "../../../types/domain.js";

type Entry = NonNullable<ReturnType<typeof applicationState.entry>>;
export type DeliveryHandle = {
  event: Command;
  admitted: Event | null;
  answer: Promise<Event | null>;
  read: Promise<Event>;
  resolve: (value: Event | null) => void;
  resolveRead: (value: Event) => void;
};

export function createPendingLedger({
  newAttempt,
  enqueue,
}: {
  newAttempt: () => string;
  enqueue: (event: Command) => unknown;
}) {
  const handles = new Map<string, DeliveryHandle>();
  const snapshot = () => readApplication().unresolved;
  const sending = () => readApplication().effective.sending;

  return {
    enqueue(event: PendingCommand) {
      const attempted = { ...event, attempt: event.attempt || newAttempt() };
      if (applicationState.entry(attempted.attempt)) return null;
      const { promise: answer, resolve }: PromiseWithResolvers<Event | null> =
        Promise.withResolvers();
      const { promise: read, resolve: resolveRead }: PromiseWithResolvers<Event> =
        Promise.withResolvers();
      const current = () => applicationState.entry(attempted.attempt);
      const handle: DeliveryHandle = {
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
    release: (entries: readonly Pick<Entry, "event">[]) =>
      applicationState.release(new Set(entries.map((entry) => entry.event.attempt))),
    /** The gestures refused with `entry`, each answered null here. */
    refuse(
      entry: DeliveryHandle,
    ): { attempt: string; answer: Promise<Event | null> }[] {
      return applicationState.refuse(entry.event.attempt).flatMap((attempt) => {
        const handle = handles.get(attempt);
        handle?.resolve(null);
        return handle ? [{ attempt, answer: handle.answer }] : [];
      });
    },
    accept(entry: DeliveryHandle, event: Event) {
      applicationState.accept(entry.event.attempt, event);
    },
    // A document pass drawing these logged events has run; each that carries an
    // attempt is that gesture's receipt.
    present(events: readonly Event[]) {
      applicationState.present(events);
      for (const event of events)
        if (event.attempt) handles.get(event.attempt)?.resolveRead(event);
    },
    nameEvents(entry: DeliveryHandle) {
      return applicationState.nameEvents(entry.event.attempt);
    },
  };
}
