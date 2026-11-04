/* Complete obligation selections and typed activation, shared by core and packages.

   The application publisher alone derives membership. This boundary selects its
   immutable lists and correlates workflow context, without folding events or
   keeping another state. Activation resolves a stable kind/id key against the
   current reading, so a stale row cannot revive an old route. An obligation is
   answered only through its source, so no list action answers one. Navigation is
   supplied once by the existing queue walk. */
import { readPart } from "./semantic-state.js";

/** @param {Pick<import("./framework/application.js").QueueItem, "kind" | "id">} item */
export const queueItemKey = (item) => JSON.stringify([item.kind, item.id]);

export const readQueues = readPart((root) => root.effective.queues);
export const readPlan = readPart((root) => root.effective.plan);

/** @typedef {ReturnType<typeof readQueues>["on_user"][number]} CurrentQueueItem */
/** @param {{arrive: ReturnType<typeof import("./queue-walk.js").createQueueWalk>["arriveAtItem"]}} dependencies */
export function createQueueActions({ arrive }) {
  return Object.freeze({
    /** @param {string} key */
    open(key) {
      const reading = readQueues();
      const item = [...reading.on_user, ...reading.on_agent, ...reading.done].find(
        (candidate) => queueItemKey(candidate) === key,
      );
      return item ? arrive(item) : Promise.resolve(false);
    },
  });
}
