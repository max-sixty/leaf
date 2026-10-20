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
// Whether the user's words answer this obligation (`x-awaits.reply`), as they do an `lf-ask`
// holding no widget: in its thread, it reads and is answered as a message.
export const answeredInWords = (obligation) =>
  Boolean(obligationEntry(obligation)?.reply);
// The obligations approving the shown version waits on, which the server names
// (`obligations.approval_blocking`, the rule its append door refuses a sign-off by).
// Approval needs an admitted inventory, so its gate never reads unknown as empty: with
// no admitted reading nothing says which obligations still stand, and this answers null.
export const approvalBlockingObligations = readPart((root) => {
  const { obligations, view } = root.effective;
  if (obligations.phase !== "ready" || !view) return null;
  const held = new Set(view.approval_blocking);
  return obligations.all.filter((obligation) => held.has(obligation.id));
});
