/* Complete obligation selections and typed activation, shared by core and packages.

   The application publisher alone derives membership. This boundary selects its
   immutable lists and correlates workflow context, without folding events or
   keeping another state. Activation resolves a stable kind/id key against the
   current reading; a stale row cannot end a different to-do or revive an old route.
   An ask is answered through its source; only a to-do on the user offers
   Done. Navigation is supplied once by the existing queue walk. */
import { readApplication } from "./semantic-state.js";
import { watchProjection } from "./projection-watch.js";
import { announce } from "./notifications.js";

export const queueItemKey = (item) => JSON.stringify([item.kind, item.id]);

export const readQueues = () => readApplication().effective.queues;

export function watchQueues(owner, callback) {
  return watchProjection(owner, () => callback(readQueues()));
}

export function createQueueActions({ post, arrive }) {
  return Object.freeze({
    open(key) {
      const reading = readQueues();
      const item = [...reading.questions, ...reading.tasks, ...reading.done].find(
        (candidate) => queueItemKey(candidate) === key,
      );
      return item?.offers.open ? arrive(item) : Promise.resolve(false);
    },
    done(key) {
      const reading = readQueues();
      const item = reading.questions.find(
        (candidate) => queueItemKey(candidate) === key,
      );
      if (!item?.offers.done) return null;
      const delivery = post({ kind: "todo_end", todo: item.id, outcome: "done" });
      announce("Done");
      return delivery;
    },
  });
}
