/* Immutable ask selections from the application publisher.

   Python folds the page and frozen-thread ask readings under the page transaction
   that answers each state read, and the publisher carries them; nothing here or under
   the publisher folds those declarations again. This module is only the public
   selection boundary. DOM resolution belongs to the views that need controls, words,
   focus, or geometry; it cannot change which asks exist or whether they await the
   user. */
import { readApplication } from "../semantic-state.js";
import { registry } from "../registry.js";
import { watchProjection } from "../projection-watch.js";

export const readAsks = () => readApplication().effective.asks;

export const askEntry = (ask) => registry[ask?.source.tag]?.["x-awaits"];
// The asks approving the shown version waits on, which the server names
// (`asks.approval_blocking`, the rule its append door refuses a sign-off by).
// Approval needs an admitted inventory, so its gate never reads unknown as empty: with
// no admitted reading nothing says which asks still stand, and this answers null.
export function approvalBlockingAsks() {
  const { asks, view } = readApplication().effective;
  if (asks.phase !== "ready" || !view) return null;
  const blocking = new Set(view.approval_blocking);
  return asks.all.filter((ask) => blocking.has(ask.id));
}

// What approval's control reads: the asks, the ones holding approval, and the shown
// document's stamp against the active revision.
export const approvalSelection = (root) => ({
  asks: root.effective.asks,
  blocking: root.effective.view?.approval_blocking ?? null,
  document: root.document,
  active: root.authoritative?.active ?? null,
});

export function watchAsks(owner, callback) {
  return watchProjection(owner, (root) => root.effective.asks, callback);
}
