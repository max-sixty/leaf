// Compiled from queue-api.ts by build/typescript.mjs; edit that file.
/* Complete obligation selections and typed activation, shared by core and packages.

   The application publisher alone derives membership. This boundary selects its
   immutable lists and correlates workflow context, without folding events or
   keeping another state. A row is named by its record's id, which no other row of any
   list shares; activation resolves that id against the current reading, so a stale
   row cannot revive an old route. An obligation is answered only through its source,
   so no list action answers one. Navigation is supplied once by the existing queue
   walk. */
import { readPart } from "./semantic-state.js";

export const readQueues = readPart((root) => root.effective.queues);
// What waits on the user, as the panel's badge and the tab's title count it: one reading.
export const onUserCount = () => {
  const queues = readQueues();
  return queues.phase === "ready" ? queues.on_user.length : 0;
};
export const readPlan = readPart((root) => root.effective.plan);

export function createQueueActions({ arrive }) {
  return Object.freeze({
    open(id) {
      const reading = readQueues();
      const item = [...reading.on_user, ...reading.on_agent, ...reading.done].find(
        (candidate) => candidate.id === id,
      );
      return item ? arrive(item) : Promise.resolve(false);
    },
  });
}
