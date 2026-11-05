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
   preview shows; `paintCoreControls` keeps the control's `aria-keyshortcuts`, the same
   reading for a screen reader. The pass runs in the fixed chrome's frame, so every
   attribute it writes goes through `keeps` and says nothing where the control already
   says it. Restated shortcut metadata is news to whatever is reading the page — the
   mutation stream a screen reader rebuilds its buffer from. */
import {
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
import { buttonCommand } from "./scopes.js";
import { keeps } from "../keeps.js";

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

function controlRows() {
  /** @type {Map<Element, {scope: import("./bindings.js").Scope, control: import("./bindings.js").Cell<Element | null>, active: boolean, press: string, shortcuts: () => string}>} */
  const controls = new Map();
  for (const scope of pageScopes().filter((scope) => scope !== ELEMENTS))
    for (const row of scope?.rows ?? [])
      for (const named of namedControls(row)) {
        const control = word(named.control);
        if (!control) continue;
        const prior = controls.get(control);
        // One native control may also have an unbound semantic route for reference
        // activation. Project it once, preferring the live keyboard presentation;
        // the unbound row must not erase that route or rewrite its title each frame.
        if (!prior || (!prior.active && named.active))
          controls.set(control, { scope, ...named });
      }
  return controls;
}

// Every press that reaches `control`, each its steps as key chips spell them: the live
// page rows and routes that name it, and the command its press answers where that is
// declared away from it, as a box's send key presses its Send. Keys a scope declares on
// the control itself are its own activation, the platform's press, not a shortcut.
/** @param {Element} control @returns {string[][]} */
export function controlKeys(control) {
  /** @type {Map<string, string[]>} */
  const presses = new Map();
  /** @param {import("./bindings.js").Scope | null | undefined} scope @param {string} press */
  const add = (scope, press) => {
    const steps = [...stepsBefore(scope), press].filter(Boolean);
    if (steps.length) presses.set(steps.join(" "), steps);
  };
  for (const scope of pageScopes().filter((scope) => scope !== ELEMENTS))
    for (const row of scope?.rows ?? [])
      for (const named of namedControls(row))
        if (named.active && word(named.control) === control) add(scope, named.press);
  const own = buttonCommand(control);
  if (own && own.source !== control && bindings(own.row).length) {
    const route = own.entry === own.row ? null : own.entry;
    if (commandAvailable(own.row, route))
      add(
        own.scope,
        route?.binding !== undefined ? spell(route.binding) : labelOf(own.row),
      );
  }
  return [...presses.values()];
}

export function paintCoreControls() {
  for (const [control, { scope, active, shortcuts }] of controlRows()) {
    // Native command buttons receive exact reachable shortcuts from command-hints.
    if (buttonCommand(control)) continue;
    // aria-keyshortcuts has no syntax for sequential shortcuts: its spaces separate
    // alternatives. The complete sequence remains in the overlay, the preview, and
    // accessible command reference instead of claiming its final press works alone.
    keeps(control, "aria-keyshortcuts", active && !scope.sequence ? shortcuts() : null);
  }
}
