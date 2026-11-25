/* What an obligation record says of how it is answered, read from the record and the
   registry alone: the `awaits` its widget declares, and whether it is answered in
   words. The records themselves are the page's reading (place.js, `readObligations`). */
import { registry } from "../../state/registry.js";
import { hasObligationSource } from "../../state/obligations/source.js";

/** @param {import("../../state/semantic-application.js").ObligationRecord | null | undefined} obligation */
export const obligationEntry = (obligation) =>
  obligation?.source.kind === "widget"
    ? registry[obligation.source.tag]?.awaits
    : undefined;
// An agent message's obligation is answered in words: in its thread, it reads and is
// answered as a message.
/** @param {import("../../state/semantic-application.js").ObligationRecord | null | undefined} obligation */
export const answeredInWords = (obligation) =>
  hasObligationSource(obligation, "message");
