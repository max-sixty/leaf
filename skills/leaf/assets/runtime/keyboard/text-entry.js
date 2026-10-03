/* Native text-entry ownership, shared by core and element scopes. */
import { controlNavigationKeys, takesLetters } from "../focus.js";
import { parsed } from "./bindings.js";

export function EVERYTHING() {
  return true;
}

// A character key belongs to the box with any modifier: Shift changes its case, Alt may
// compose it, and Mod sequences copy, select, or undo. The editing keys below stay the box's
// with modifiers too, so Shift+Arrow can extend a selection and Mod+Backspace can delete a
// word without an ancestor widget turning either into its own action. An exact element
// scope still stands nearer and can specialise Enter for send.
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

// The platform's claim at one exact control. Dispatch and accessible shortcut
// projection use this same reading; context aliases always stand behind it.
export function nativeClaimAt(control) {
  if (takesLetters(control)) return TEXT_ENTRY;
  const navigation = controlNavigationKeys(control);
  return navigation.length
    ? (binding) => navigation.includes(parsed(binding).key)
    : null;
}
