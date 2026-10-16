/* The platform's own keys at the focused control, shared by core and element scopes:
   text entry, a choice's arrow navigation, and native activation. */
import { controlNavigationKeys, takesLetters } from "../focus.js";
import { parsed, PRESS } from "./bindings.js";
import { CARET_KEYS } from "../control-selectors.js";

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

const EDITING = new Set(["Enter", "Backspace", "Delete", ...CARET_KEYS]);

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

// Native activation: Enter follows a link, Enter or Space presses a button or works a
// <summary>, and Space checks a checkbox or radio button. The press belongs to the focused
// control, so no scope above it runs a different Leaf command on it: a container
// answering Enter, such as a code block's Copy, leaves a link or button inside it its own
// press. A row that only names the press, with nothing of its own to run (a link's
// Follow, a list naming what its buttons open), still names it, since the browser does
// what it says. The control's own scopes stand nearer and may take the press, whether
// its exact element scope or a page scope rooted at it (dispatch.js, `shadow`), while a
// contextual alias on it yields, as it yields to native editing. Modified presses stay
// with the scopes: they are the browser's or Leaf's shortcuts, not activation. A span
// offered with a button's role has no platform activation, so its owner declares the
// press (`selectableOffer`).
export const LINK = "a[href], area[href]";
const ACTIVATION = [
  [LINK, ["Enter"]],
  [
    'button, details > summary, input:is([type="button"], [type="submit"], [type="reset"], [type="image"])',
    PRESS,
  ],
  ['input:is([type="checkbox"], [type="radio"])', [" "]],
];
export function nativeActivationAt(control) {
  const presses = ACTIVATION.find(([selector]) => control?.matches?.(selector))?.[1];
  return presses ? (binding) => presses.includes(binding) : null;
}
