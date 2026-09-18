/* Semantic projection is a selector; only deferred DOM work is local to rendering.

   Deferral is mechanical: a reader's drag holds the document-wide projection pass while
   their own controller owns the value. It publishes no semantic epoch, so readings that
   change with it — the approval gate's Ask selection, every projection watcher — hear
   about it here instead. */
import { readApplication } from "../semantic-state.js";

let deferred = false;
const watchers = new Set();

export const currentProjection = () => readApplication().effective.projection;
export const projectionDeferred = () => deferred;

export function watchProjectionDeferral(callback) {
  watchers.add(callback);
  return () => watchers.delete(callback);
}

export function setProjectionDeferred(next) {
  if (deferred === next) return;
  deferred = next;
  for (const watcher of [...watchers]) watcher();
}
