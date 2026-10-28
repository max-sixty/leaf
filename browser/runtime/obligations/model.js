/* Immutable obligation selections from the application publisher.

   Python folds the page and frozen-thread obligation readings under the page transaction
   that answers each state read, and the publisher carries them; nothing here or under
   the publisher folds those declarations again. This module is only the public
   selection boundary. DOM resolution belongs to the views that need controls, words,
   focus, or geometry; it cannot change which obligations exist or whether they await the
   user. */
import { readPart } from "../semantic-state.js";
import { registry } from "../registry.js";

export const readObligations = readPart((root) => root.effective.obligations);

export const obligationEntry = (obligation) =>
  registry[obligation?.source.tag]?.["x-awaits"];
// An agent message's obligation is answered in words: in its thread, it reads and is
// answered as a message.
export const answeredInWords = (obligation) => obligation?.source.kind === "message";
