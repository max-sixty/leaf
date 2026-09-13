/* Semantic projection is a selector; only deferred DOM work is local to rendering. */
import { readApplication } from "../semantic-state.js";

let deferred = false;

export const currentProjection = () => readApplication().effective.projection;
export const projectionDeferred = () => deferred;

export function setProjectionDeferred(next) {
  deferred = next;
}
