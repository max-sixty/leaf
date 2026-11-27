/* What an obligation record says of how it is answered, read from the record and the
   registry alone: the `awaits` its widget declares, and whether it is answered in
   words. The records themselves are the page's reading (place.js, `readObligations`). */
import { registry } from "../../state/registry.js";
import { hasObligationSource } from "../../state/obligations/source.js";
import type { ObligationRecord } from "../../state/semantic-application.js";

export const obligationEntry = (obligation: ObligationRecord | null | undefined) =>
  obligation?.source.kind === "widget"
    ? registry[obligation.source.tag]?.awaits
    : undefined;
// An agent message's obligation is answered in words: in its thread, it reads and is
// answered as a message.
export const answeredInWords = (obligation: ObligationRecord | null | undefined) =>
  hasObligationSource(obligation, "message");
