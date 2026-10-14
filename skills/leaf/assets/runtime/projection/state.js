/* Semantic projection is a selector; only deferred DOM work is local to rendering.

   Deferral is mechanical: a user's drag holds the document-wide projection pass while
   their own controller owns the value. It publishes no semantic epoch, so its
   followers hear it here, one round per change; every projection watcher reads it as
   a reading of its own (`projection-watch.js`). */
import { readPart } from "../semantic-state.js";

let deferred = false;
const heard = new Set();

export const currentProjection = readPart((root) => root.effective.projection);
export const projectionDeferred = () => deferred;

export function watchProjectionDeferral(moved) {
  heard.add(moved);
  return () => heard.delete(moved);
}

export function setProjectionDeferred(next) {
  if (deferred === next) return;
  deferred = next;
  const round = {};
  for (const moved of [...heard]) moved(round);
}
