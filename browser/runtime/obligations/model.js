/* Immutable obligation selections from the application publisher.

   Python folds the page and frozen-thread obligation readings under the page transaction
   that answers each state read, and the publisher carries them; nothing here or under
   the publisher folds those declarations again. This module is only the public
   selection boundary. DOM resolution belongs to the views that need controls, words,
   focus, or geometry; it cannot change which obligations exist or whether they await the
   user. */
import { readPart } from "../semantic-state.js";
import { registry } from "../registry.js";
import { hasObligationSource } from "./source.js";

export const readObligations = readPart((root) => root.effective.obligations);

/** @param {import("../framework/application.js").ObligationRecord | null | undefined} obligation */
export const obligationEntry = (obligation) =>
  obligation?.source.kind === "widget"
    ? registry[obligation.source.tag]?.["x-awaits"]
    : undefined;
// An agent message's obligation is answered in words: in its thread, it reads and is
// answered as a message.
/** @param {import("../framework/application.js").ObligationRecord | null | undefined} obligation */
export const answeredInWords = (obligation) =>
  hasObligationSource(obligation, "message");
