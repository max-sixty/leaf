/* Semantic projection is a selector; only deferred DOM work is local to rendering.

   Deferral is mechanical: a user's drag holds the document-wide projection pass while
   their own controller owns the value. It publishes no semantic epoch, so it is a
   reading of its own (`outsideReading`): a paint that reads it is followed on it as on
   the parts of the publication it read, as every projection watcher is. */
import { readPart } from "../semantic-state.js";
import { outsideReading } from "../../vendor/browser-runtime.js";

let deferred = false;
const heard = new Set();

export const currentProjection = readPart((root) => root.effective.projection);
const deferral = outsideReading(
  () => deferred,
  (moved) => {
    heard.add(moved);
    return () => heard.delete(moved);
  },
);
export const projectionDeferred = () => deferral.read();

export function setProjectionDeferred(next) {
  if (deferred === next) return;
  deferred = next;
  const round = {};
  for (const moved of [...heard]) moved(round);
}
