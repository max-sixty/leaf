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

export const readQuestions = () => readApplication().effective.questions;

export const questionEntry = (question) => registry[question?.source.tag]?.["x-awaits"];
// Approval is irreversible, so its gate never reads an unknown as an empty list: with
// no admitted reading nothing says which Questions still stand, and this answers null.
export function approvalBlockingQuestions() {
  const reading = readQuestions();
  return reading.phase === "ready" ? reading.unanswered.filter((question) => question.source.kind === "widget" && question.next_actor !== null) : null;
}

export function watchQuestions(owner, callback) {
  if (typeof callback !== "function")
    throw new TypeError("A Question watcher needs a callback");
  return watchProjection(owner, () => callback(readQuestions()));
}
