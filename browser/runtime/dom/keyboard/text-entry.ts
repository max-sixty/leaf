/* The platform's own keys at the focused control, shared by core and element scopes:
   text entry, a widget's typeahead, a choice's arrow navigation, and native activation. */
import { controlNavigationKeys, takesLetters } from "../focus.js";
import { parsed } from "./bindings.js";
import { CARET_KEYS } from "../control-selectors.js";
import { ROLE_BUTTON_OFFER } from "../../lib/role-button-press.js";
import { PRESS } from "../../lib/keys.js";

export function EVERYTHING() {
  return true;
}

// A character key belongs to the box with any modifier: Shift changes its case, Alt may
// compose it, and Mod sequences copy, select, or undo. The editing keys below stay the box's
// with modifiers too, so Shift+Arrow can extend a selection and Mod+Backspace can delete a
// word without an ancestor widget turning either into its own action. An exact element
// scope still stands nearer and can specialise Enter for send.
function CHARACTER(binding: string) {
  return [...parsed(binding).key].length === 1;
}

const EDITING = new Set(["Enter", "Backspace", "Delete", ...CARET_KEYS]);

export function TEXT_ENTRY(binding: string) {
  return CHARACTER(binding) || EDITING.has(parsed(binding).key);
}

// A widget whose ARIA pattern types ahead moves to the item whose name starts with the
// letter or digit typed: a menu, a tree, a listbox or a select-only combobox, whether
// focus is on the widget or its item, and anything inside an application, which takes
// the keyboard whole. Focus there claims those characters, alone or shifted, so Leaf's
// page letters wait until focus leaves, as they do in a select (`takesLetters`, which
// also covers an editable combobox's text box). Leaf reads a key after the page's
// elements have heard it (panel/page-keys/controller.js), so a widget that prevents each letter it
// handles keeps it without a claim. A typeahead widget needs one all the same, since it
// prevents only a letter some name starts with, as Web Awesome's dropdown does, or none,
// and Leaf would otherwise offer page letters the widget answers. Leaf's own file tree
// types into its search this way.
const TYPES_AHEAD = [
  ...["listbox", "menu", "menubar", "menuitem", "menuitemcheckbox", "menuitemradio"],
  ...["tree", "treeitem", "combobox", "application"],
]
  .map((role) => `[role="${role}"]`)
  .concat('[role="application"] *')
  .join(", ");

function NAME_CHARACTER(binding: string) {
  const { key, mods } = parsed(binding);
  return /^[\p{L}\p{N}]$/u.test(key) && mods.every((mod) => mod === "Shift");
}

// The platform's claim at one exact control. Dispatch and accessible shortcut
// projection use this same reading; context aliases always stand behind it.
export function nativeClaimAt(control: Element | null) {
  if (takesLetters(control)) return TEXT_ENTRY;
  const navigation = controlNavigationKeys(control);
  const typesAhead = Boolean(control?.matches(TYPES_AHEAD));
  return navigation.length || typesAhead
    ? (binding: string) =>
        (typesAhead && NAME_CHARACTER(binding)) ||
        navigation.includes(parsed(binding).key)
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
// Leaf offers as a button presses as a button does, by the default action
// role-button-press.js gives it, so it is native activation here too.
export const LINK = "a[href], area[href]";
const ACTIVATION: readonly (readonly [string, readonly string[]])[] = [
  [LINK, ["Enter"]],
  [
    `button, ${ROLE_BUTTON_OFFER}, details > summary, input:is([type="button"], [type="submit"], [type="reset"], [type="image"])`,
    PRESS,
  ],
  ['input:is([type="checkbox"], [type="radio"])', [" "]],
];
export function nativeActivationAt(control: Element | null) {
  const presses = ACTIVATION.find(([selector]) => control?.matches(selector))?.[1];
  return presses ? (binding: string) => presses.includes(binding) : null;
}
