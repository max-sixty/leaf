/* Immutable Question selections from the application publisher.

   Python folds the page and frozen-thread Question readings under the page transaction
   that answers each state read, and the publisher carries them; nothing here or under
   the publisher folds those declarations again. This module is only the public
   selection boundary. DOM resolution belongs to the views that need controls, words,
   focus, or geometry; it cannot change which Questions exist or whether they await the
   user. */
import { readApplication } from "../semantic-state.js";
import { registry } from "../registry.js";
import { watchProjection } from "../projection-watch.js";

export const readQuestions = () => readApplication().effective.asks;

export const questionEntry = (question) => registry[question?.source.tag]?.["x-awaits"];
// The Questions approving the shown version waits on, which the server names
// (`questions.approval_blocking`, the rule its append door refuses a sign-off by).
// Approval needs an admitted inventory, so its gate never reads unknown as empty: with
// no admitted reading nothing says which Questions still stand, and this answers null.
export function approvalBlockingQuestions() {
  const { asks: questions, view } = readApplication().effective;
  if (questions.phase !== "ready" || !view) return null;
  const blocking = new Set(view.approval_blocking);
  return questions.all.filter((question) => blocking.has(question.id));
}

export function watchQuestions(owner, callback) {
  if (typeof callback !== "function")
    throw new TypeError("A Question watcher needs a callback");
  return watchProjection(owner, () => callback(readQuestions()));
}
