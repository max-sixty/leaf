/* Native text-entry ownership, shared by core and element scopes. */
import { parsed } from "./bindings.js";

export function EVERYTHING() {
  return true;
}

// A character key belongs to the box with any modifier: Shift changes its case, Alt may
// compose it, and Mod sequences copy, select, or undo. The editing keys below stay the box's
// with modifiers too, so Shift+Arrow can extend a selection and Mod+Backspace can delete a
// word without an ancestor widget turning either into its own action. An exact element
// scope still stands nearer and can specialise a sequence such as Mod+Enter for send.
function CHARACTER(binding) {
  return [...parsed(binding).key].length === 1;
}

const EDITING = new Set([
  "Enter",
  "Backspace",
  "Delete",
  "ArrowLeft",
  "ArrowRight",
  "ArrowUp",
  "ArrowDown",
  "Home",
  "End",
  "PageUp",
  "PageDown",
]);

export function TEXT_ENTRY(binding) {
  return CHARACTER(binding) || EDITING.has(parsed(binding).key);
}
