/* What a visible control says about the key that reaches it.

   A control the keyboard reaches names its shortcut from the row, never from a sentence
   written beside it: `control` is where a row, or one route of it, says which control it
   duplicates, and this projection follows liveness too, so a disabled obligation does not
   advertise a shortcut the dispatcher has withdrawn. A row inside a sequence scope carries
   that sequence's steps, so a destination reached through `g` says the whole shortcut.

   A key that presses a control another command owns, as `r` presses a thread's Resolve,
   names the control with no `run` of its own: its press is the control's activation
   (bindings.js, `commandRun`), so the button keeps one command and the key is one more
   way to press it. A row that both names a button and runs a result claims the button's
   activation, and two such claims on one button are refused (scopes.js, `chosenCommand`).

   `controlKeys` is what the preview of a control names (preview.js), read when the
   preview shows, and `controlShortcuts` the same presses for a screen reader: each one
   press long, since `aria-keyshortcuts` has no syntax for a sequence, its spaces
   separating alternatives. The complete sequence stays in the preview, the overlay and
   the command reference. A control's `aria-keyshortcuts` also names the keys its own
   scopes take while it has focus (scopes.js, `reflectElementShortcuts`), which no chip
   draws, so every chip's key is in it. `paintCoreControls` keeps that attribute on
   every control a page row names, as the rows' liveness moves. The pass runs in the
   fixed chrome's frame, so every attribute it writes goes through `keeps` and says
   nothing where the control already says it. Restated shortcut metadata is news to
   whatever is reading the page — the mutation stream a screen reader rebuilds its
   buffer from. */
import {
  ariaBindings,
  ariaShortcuts,
  bindings,
  commandAvailable,
  commandRoutes,
  labelOf,
  live,
  spell,
  word,
} from "./bindings.js";
import { ELEMENTS, pageScopes } from "./register.js";
import {
  buttonCommand,
  projectControlShortcuts,
  reflectElementShortcuts,
} from "./scopes.js";
import { ACTIONS, shownAction } from "../icon-paths.js";

/** @param {import("./bindings.js").Scope | null | undefined} scope */
const stepsBefore = (scope) => word(scope?.sequencePrefix ?? scope?.sequence) ?? [];
// The presses that reach a row, each spelled as a key chip spells it: a step is one
// press, so a label's own words never split into steps.
/** @param {import("./bindings.js").Scope} scope @param {import("./bindings.js").Command} row */
const stepsIn = (scope, row) => [...stepsBefore(scope), labelOf(row)].filter(Boolean);

/** The complete shortcut one command advertises, each press a step as a key chip
 * spells it, for a presentation that draws a command as words with its keys
 * (page-controls.js, a row's `shortcut`). Empty for a command no key reaches. Resolved by
 * command id rather than by row identity: a scope may carry another owner's command as a
 * row of its own — a `g` destination wraps the declaration it stands for — and the
 * shortcut the user presses is the one that scope prefixes. */
/** @param {string} id */
export function commandSteps(id) {
  for (const scope of pageScopes().filter((scope) => scope !== ELEMENTS))
    for (const row of scope?.rows ?? [])
      if (row.id === id && bindings(row).length) return stepsIn(scope, row);
  return [];
}

// Each visible control a page row names, or one of its routes does, with the press that
// reaches it: a route's control names that route's binding alone.
/** @param {import("./bindings.js").Command} row */
function* namedControls(row) {
  if (row.control)
    yield {
      control: row.control,
      active: live(row) && bindings(row).length > 0,
      press: labelOf(row),
      shortcuts: () => ariaShortcuts([row], false),
    };
  for (const route of commandRoutes(row))
    if (route.control && route.binding !== undefined) {
      const binding = route.binding;
      yield {
        control: route.control,
        active: commandAvailable(row, route) && bindings(row).includes(binding),
        press: spell(binding),
        shortcuts: () => ariaShortcuts([{ ...route, keys: [binding] }], false),
      };
    }
}

/** @typedef {{steps: string[], aria: string}} Press */
// Every control the page's rows and routes name, with the live presses each gives it:
// one walk of the rows, kept for the task that made it, so a pass reading many
// controls walks them once, and a paint walks them again (`paintCoreControls`).
/** @type {Map<Element, Map<string, Press>> | null} */
let named = null;
/** @param {Map<string, Press>} presses @param {import("./bindings.js").Scope | null | undefined} scope @param {string} press @param {string} aria */
function addPress(presses, scope, press, aria) {
  const before = stepsBefore(scope);
  const steps = [...before, press].filter(Boolean);
  if (steps.length)
    presses.set(steps.join(" "), { steps, aria: before.length ? "" : aria });
}
function namedByRows() {
  if (named) return named;
  /** @type {Map<Element, Map<string, Press>>} */
  const controls = new Map();
  for (const scope of pageScopes().filter((scope) => scope !== ELEMENTS))
    for (const row of scope?.rows ?? [])
      for (const each of namedControls(row)) {
        const control = word(each.control);
        if (!control) continue;
        const presses = controls.get(control) ?? new Map();
        controls.set(control, presses);
        if (each.active) addPress(presses, scope, each.press, each.shortcuts());
      }
  named = controls;
  queueMicrotask(() => {
    named = null;
  });
  return controls;
}

// Every press that reaches `control`, each its steps as key chips spell them and, one
// press long, as `aria-keyshortcuts` names it: the live page rows and routes that name
// it, the command a scope declares away from it that claims its press, as the image
// viewer's `z` claims its zoom, and the key the action it shows names, as Escape for a
// surface's close. Keys a scope declares on the control itself are its own activation,
// the platform's press, not a shortcut.
/** @param {Element} control @returns {Press[]} */
function pressesReaching(control) {
  const presses = new Map(namedByRows().get(control));
  const shared = ACTIONS[shownAction(control) ?? ""]?.key;
  if (shared) addPress(presses, null, spell(shared), ariaBindings(shared).join(" "));
  const own = buttonCommand(control);
  if (own && own.source !== control && bindings(own.row).length) {
    const route = own.entry === own.row ? null : own.entry;
    if (commandAvailable(own.row, route))
      addPress(
        presses,
        own.scope,
        route?.binding !== undefined ? spell(route.binding) : labelOf(own.row),
        route?.binding !== undefined
          ? ariaBindings(route.binding).join(" ")
          : ariaShortcuts([own.row], false),
      );
  }
  return [...presses.values()];
}
/** @param {Element} control @returns {string[][]} */
export const controlKeys = (control) =>
  pressesReaching(control).map(({ steps }) => steps);
/** @param {Element} control */
const controlShortcuts = (control) =>
  [
    ...new Set(
      pressesReaching(control).flatMap(({ aria }) => aria.split(" ").filter(Boolean)),
    ),
  ].join(" ");

projectControlShortcuts(controlShortcuts);

export function paintCoreControls() {
  named = null;
  for (const control of namedByRows().keys()) reflectElementShortcuts(control);
}
