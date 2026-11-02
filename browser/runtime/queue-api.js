/* Complete obligation selections and typed activation, shared by core and packages.

   The application publisher alone derives membership. This boundary selects its
   immutable lists and correlates workflow context, without folding events or
   keeping another state. Activation resolves a stable kind/id key against the
   current reading; a stale row cannot end a different to-do or revive an old route.
   An obligation is answered through its source; only a to-do on the user offers
   Done. Navigation is supplied once by the existing queue walk. */
import { readPart } from "./semantic-state.js";
import { announce } from "./notifications.js";

/** @param {Pick<import("./framework/application.js").QueueItem, "kind" | "id">} item */
export const queueItemKey = (item) => JSON.stringify([item.kind, item.id]);

export const readQueues = readPart((root) => root.effective.queues);
export const readPlan = readPart((root) => root.effective.plan);

/** @typedef {ReturnType<typeof readQueues>["on_user"][number]} CurrentQueueItem */
/** @param {{post: ReturnType<typeof import("./pending/dispatch.js").createCommandDispatch>["post"], arrive: ReturnType<typeof import("./queue-walk.js").createQueueWalk>["arriveAtItem"]}} dependencies */
export function createQueueActions({ post, arrive }) {
  return Object.freeze({
    /** @param {string} key */
    open(key) {
      const reading = readQueues();
      const item = [...reading.on_user, ...reading.on_agent, ...reading.done].find(
        (candidate) => queueItemKey(candidate) === key,
      );
      return item?.offers.open ? arrive(item) : Promise.resolve(false);
    },
    /** @param {string} key */
    done(key) {
      const reading = readQueues();
      const item = reading.on_user.find((candidate) => queueItemKey(candidate) === key);
      if (!item?.offers.done) return null;
      const delivery = post({ kind: "todo_end", todo: item.id, outcome: "done" });
      announce("Done");
      return delivery;
    },
  });
}
