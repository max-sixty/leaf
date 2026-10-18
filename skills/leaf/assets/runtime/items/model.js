/* Immutable ask selections from the application publisher.

   Python folds the page and frozen-thread ask readings under the page transaction
   that answers each state read, and the publisher carries them; nothing here or under
   the publisher folds those declarations again. This module is only the public
   selection boundary. DOM resolution belongs to the views that need controls, words,
   focus, or geometry; it cannot change which asks exist or whether they await the
   user. */
import { readPart } from "../semantic-state.js";
import { registry } from "../registry.js";

export const readItems = readPart((root) => root.effective.items);

export const itemEntry = (item) => registry[item?.source.tag]?.["x-awaits"];
// Whether the user's words answer this ask (`x-awaits.reply`), as they do an `lf-ask`
// holding no widget: in its thread, it reads and is answered as a message.
export const answeredInWords = (item) => Boolean(itemEntry(item)?.reply);
// The asks approving the shown version waits on, which the server names
// (`asks.approval_blocking`, the rule its append door refuses a sign-off by).
// Approval needs an admitted inventory, so its gate never reads unknown as empty: with
// no admitted reading nothing says which asks still stand, and this answers null.
export const approvalBlockingItems = readPart((root) => {
  const { items, view } = root.effective;
  if (items.phase !== "ready" || !view) return null;
  const held = new Set(view.approval_blocking);
  return items.all.filter((item) => held.has(item.id));
});
