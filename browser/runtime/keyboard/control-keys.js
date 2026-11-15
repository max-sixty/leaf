/* What a visible control says about the keys that reach it.

   A control the keyboard reaches names its shortcut from the row, never from a sentence
   written beside it: `control` is where a row, or one route of it, says which control it
   duplicates. A key that presses a control another command owns, as `r` presses a
   thread's Resolve, names the control with no `run` of its own: its press is the
   control's activation (bindings.js, `commandRun`), so the button keeps one command and
   the key is one more way to press it. A row that both names a button and runs a result
   claims the button's activation, and two such claims on one button are refused
   (scopes.js, `chosenCommand`).

   A control says the keys that reach it from where the user is now, and no others: the
   bindings the dispatcher would answer here (dispatch.js, `availableCommandRoutes`), each
   under the control its row or route names, a contextual alias's under the control of the
   command it routes to. So a key a nearer scope takes, one a disabled command withdraws,
   and one only another place reaches go unsaid, as an obligation's digit is said only
   while the user is on the obligation, and so does the platform's own press of the
   control the user is on, its Enter and Space (text-entry.js, `nativeActivationAt`),
   which every control of its kind takes. `controlKeys` is that reading as key chips, which
   the preview of a control draws (preview.js) as it shows, and `paintCoreControls` puts
   the same presses in the control's `aria-keyshortcuts`, since a screen reader announces
   the attribute with no context to say where a key works. A control's attribute also
   names the keys its own scopes take while it has focus (scopes.js,
   `reflectElementShortcuts`), which no chip draws, so every chip's key is in it. Each
   press is one key: a sequence reaches its destination only once its first key is
   pressed, and `aria-keyshortcuts` has no syntax for one; the whole sequence stays in the
   command reference and the page's controls (`commandSteps`).

   The reading is made once per task and place (`reachingNow`); the frame's command hints
   read it afresh, after the painters before them moved what is live (command-hints.js),
   and `paintCoreControls` reflects each control whose keys moved since the last frame.
   A reflection between frames reads the frame's keys, never the dispatcher, which may be
   reading the register as it reflects. The pass runs in the fixed chrome's frame, so
   every attribute it writes goes through `keeps` and says nothing where the control
   already says it. Restated shortcut metadata is news to whatever is reading the page —
   the mutation stream a screen reader rebuilds its buffer from.

   Until 7 November 2026 a control's chips and attribute named every key any row bound to
   it wherever the user stood, and a close control Escape too: the Inspect button inside a
   suggestion said `x y` while the user was on the suggestion, where only its digit
   worked, and kept `x` after a nearer declaration took `x`. A close control now says
   Escape where a row says Escape presses it, as the image viewer's does. */
import {
  ariaBindings,
  bindings,
  commandEntries,
  labelOf,
  spell,
  word,
} from "./bindings.js";
import { availableCommandRoutes } from "./dispatch.js";
import { ELEMENTS, pageScopes } from "./register.js";
import { projectControlShortcuts, reflectElementShortcuts } from "./scopes.js";
import { nativeActivationAt } from "./text-entry.js";
import { focused, focusRevision } from "../focus.js";
import { untracked } from "/runtime/framework.js";

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

/** @typedef {{revision: number, available: ReturnType<typeof availableCommandRoutes>, controls: Map<Element, string[]>}} Reaching */
/** @type {Reaching | null} */
let reading = null;
/** The dispatcher's reachable bindings from where the user is now, and each control they
 * press, read once per task and place unless `fresh`. Read untracked: a reflection that
 * asks it subscribes to none of the page's rows, and `paintCoreControls` reflects what
 * moved. */
export function reachingNow({ fresh = false } = {}) {
  const revision = untracked(focusRevision);
  if (reading && !fresh && reading.revision === revision) return reading;
  const made = untracked(() => {
    const available = availableCommandRoutes();
    // On a control, its own Enter and Space are the platform's press, which every
    // control of its kind takes, and no shortcut of its own.
    const on = focused();
    const activation = on && nativeActivationAt(on);
    /** @type {Map<Element, string[]>} */
    const controls = new Map();
    for (const [row, reached] of available)
      for (const binding of reached) {
        if (binding === undefined) continue;
        for (const { route } of commandEntries(row, [binding])) {
          const control = word(route?.control ?? row.control);
          if (!(control instanceof Element) || !control.isConnected) continue;
          if (control === on && activation?.(binding)) continue;
          const keys = controls.get(control) ?? [];
          if (!keys.includes(binding)) keys.push(binding);
          controls.set(control, keys);
        }
      }
    return { revision, available, controls };
  });
  reading = made;
  queueMicrotask(() => {
    if (reading === made) reading = null;
  });
  return made;
}

/** @param {Element} control @returns {string[][]} */
export const controlKeys = (control) =>
  (reachingNow().controls.get(control) ?? []).map((binding) => [spell(binding)]);
// Each control's keys as `aria-keyshortcuts` spells them, as of the frame's reading:
// a control's reflection reads them here rather than asking the dispatcher, which may
// be reading the register as it reflects.
/** @type {Map<Element, string>} */
let painted = new Map();
projectControlShortcuts((control) => painted.get(control) ?? "");

export function paintCoreControls() {
  const was = painted;
  painted = new Map(
    [...reachingNow().controls].map(([control, keys]) => [
      control,
      [...new Set(keys.flatMap(ariaBindings))].join(" "),
    ]),
  );
  for (const control of new Set([...was.keys(), ...painted.keys()]))
    if (was.get(control) !== painted.get(control)) reflectElementShortcuts(control);
}
