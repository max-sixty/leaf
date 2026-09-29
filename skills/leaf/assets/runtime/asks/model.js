/* Immutable Ask selections from the application publisher.

   Python folds the page and frozen-thread Ask readings under the page transaction
   that answers each state read, and the publisher carries them; nothing here or under
   the publisher folds those declarations again. This module is only the public
   selection boundary. DOM resolution belongs to the views that need controls, words,
   focus, or geometry; it cannot change which Asks exist or whether they await the
   user. */
import { readApplication } from "../semantic-state.js";
import { registry } from "../registry.js";
import { watchProjection } from "../projection-watch.js";

const reading = () => readApplication().effective.asks;

export const askEntry = (ask) => registry[ask?.sourceTag]?.["x-awaits"];
export const allAsks = () => reading().all;
export const openAsks = () => reading().user;
export const unansweredAsks = () => reading().unanswered;
// Approval is irreversible, so its gate never reads an unknown as an empty list: with
// no admitted reading nothing says which Asks still stand, and this answers null.
export function approvalBlockingAsks() {
  const application = readApplication();
  if (application.phase !== "ready") return null;
  return application.effective.asks.unanswered;
}

export function watchAsks(owner, callback) {
  if (typeof callback !== "function")
    throw new TypeError("An Ask watcher needs a callback");
  return watchProjection(owner, () => callback(openAsks()));
}
