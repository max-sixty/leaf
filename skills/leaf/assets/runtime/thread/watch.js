/* Per-element subscriptions to the canonical Thread reading.

   The state selector stays pure. This adapter owns the browser subscription so
   each widget can derive its own display from one shared application collection. */
import { watchProjection } from "../projection-watch.js";
import { readThreads } from "./state.js";

export function watchThreads(owner, callback) {
  if (typeof callback !== "function")
    throw new TypeError("A Thread watcher needs a callback");
  return watchProjection(owner, () => callback(readThreads()));
}
