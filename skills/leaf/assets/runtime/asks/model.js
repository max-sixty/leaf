/* Immutable Ask selections from the application publisher.

   Python folds the page and frozen-thread Ask readings under the page transaction
   that answers each state read, and the publisher carries them; nothing here or under
   the publisher folds those declarations again. This module is only the public
   selection boundary. DOM resolution belongs to the views that need controls, words,
   focus, or geometry; it cannot change which Asks exist or whether they await the
   reader. */
import { applicationState, readApplication } from "../semantic-state.js";
import { registry } from "../registry.js";

const reading = () => readApplication().effective.asks;

export const askEntry = (ask) => registry[ask?.sourceTag]?.["x-awaits"];
export const allAsks = () => reading().all;
export const openAsks = () => reading().reader;
export const unansweredAsks = () => reading().unanswered;
// Approval is irreversible, so its gate never reads an unknown as an empty list: with
// no admitted reading nothing says which Asks still stand, and this answers null.
export function approvalBlockingAsks() {
  const application = readApplication();
  if (application.phase !== "ready") return null;
  return application.effective.asks.unanswered;
}

// The first reading is synchronous. The owner is a lifetime assertion for the public
// widget contract; callers still own disconnecting the returned subscription.
export function watchAsks(owner, callback) {
  if (!(owner instanceof Element))
    throw new TypeError("An Ask watcher needs an element owner");
  if (typeof callback !== "function")
    throw new TypeError("An Ask watcher needs a callback");
  return applicationState
    .select((root) => root.effective.asks.reader)
    .subscribe(() => callback(openAsks()));
}
