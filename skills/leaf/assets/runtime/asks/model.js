/* Immutable Ask selections from the application publisher.

   The server's admitted page and frozen-thread inventory, the effective widget
   projection, request lifecycle, conversation turns, and ordered unresolved ledger
   are folded together by the publisher. This module is only the public selection
   boundary. DOM resolution belongs to the views that need controls, words, focus, or
   geometry; it cannot change which Asks exist or whether they await the reader. */
import { applicationState, readApplication } from "../semantic-state.js";
import { registry } from "../registry.js";
import { projectionDeferred } from "../projection/state.js";

const reading = () => readApplication().effective.asks;

export const askEntry = (ask) => registry[ask?.sourceTag]?.["x-awaits"];
export const allAsks = () => reading().all;
export const openAsks = () => reading().reader;
export const unansweredAsks = () => reading().unanswered;
// A deferred projection has not committed the optimistic answer to the document yet.
// Approval is irreversible enough to keep reading the admitted selection until it has.
export const approvalBlockingAsks = () =>
  projectionDeferred()
    ? readApplication().effective.admittedUnansweredAsks
    : reading().unanswered;

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
