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
   the preview of a control draws (annotations/preview.js) as it shows, and `paintCoreControls` puts
   the same presses in the control's `aria-keyshortcuts`, since a screen reader announces
   the attribute with no context to say where a key works. A control's attribute also
   names the keys its own scopes take while it has focus (scopes.js,
   `reflectElementShortcuts`), which no chip draws, so every chip's key is in it. Each
   press is one key: a sequence reaches its destination only once its first key is
   pressed, and `aria-keyshortcuts` has no syntax for one; the whole sequence stays in the
   command reference and the page's controls (`commandSteps`).

   The reading is made once per task and place (`reachingNow`); the frame's command hints
   read it afresh, after the painters before them moved what is live (readings/key-badges/command-hints.js),
   and `paintCoreControls` reflects each control whose keys moved since the last frame.
   A reflection between frames reads the frame's keys, never the dispatcher, which may be
   reading the register as it reflects. The pass runs in the fixed chrome's frame, so
   every attribute it writes goes through `keeps` and says nothing where the control
   already says it. Restated shortcut metadata is news to whatever is reading the page —
   the mutation stream a screen reader rebuilds its buffer from.

   Rejected: a control's chips and attribute naming every key any row binds to
   it wherever the user stands, and a close control Escape too: the Inspect button inside a
   suggestion then says `x y` while the user is on the suggestion, where only its digit
   works, and keeps `x` after a nearer declaration takes `x`. A close control says
   Escape where a row says Escape presses it, as the image viewer's does. */
import {
  advertisesKeys,
  ariaBindings,
  bindings,
  commandEntries,
  declaredCommandAvailable,
  labelOf,
  live,
  parsed,
  spell,
  spokenBinding,
  titleOf,
  word,
} from "./bindings.js";
import { activeCommandBinding, availableCommandRoutes, pressRuns } from "./dispatch.js";
import { ELEMENTS, pageScopes } from "./register.js";
import { projectControlShortcuts, reflectElementShortcuts } from "./scopes.js";
import { nativeActivationAt } from "./text-entry.js";
import { focused, focusRevision } from "../focus.js";
import { untracked } from "/vendor/signals-core.js";
import type { Command, Scope } from "./bindings.js";

/** The page's commands that open a scope (`opens`, bindings.js), each with that scope:
 * `g` with Go-to's, `g V` with Versions'. Each is listed once by its id, though a Go-to
 * destination stands in two scopes, keyless among the page's commands. */
function doors() {
  const found: Map<string, { door: Command; opened: Scope }> = new Map();
  for (const scope of pageScopes())
    if (scope !== ELEMENTS)
      for (const door of scope.rows) {
        const opened = door.opens?.();
        if (opened && !found.has(door.id)) found.set(door.id, { door, opened });
      }
  return [...found.values()];
}
/** The presses that open a scope, each spelled as a key chip spells it: the steps of
 * the command whose press enters it (`opens`), or null where no command opens it. */
export function doorSteps(scope: Scope): string[] | null {
  const entry = doors().find(({ opened }) => opened === scope);
  return entry ? commandSteps(entry.door.id) : null;
}
const stepsBefore = (scope: Scope | null | undefined): readonly string[] =>
  (scope && doorSteps(scope)) ?? word(scope?.sequence) ?? [];
// The presses that reach a row, each spelled as a key chip spells it: a step is one
// press, so a label's own words never split into steps.
const stepsIn = (scope: Scope, row: Command): string[] =>
  [...stepsBefore(scope), labelOf(row)].filter(Boolean);

/** The complete shortcut one command advertises, each press a step as a key chip
 * spells it, for a presentation that draws a command as words with its keys
 * (base/page-controls.js, a row's `shortcut`). Empty for a command no key reaches. Resolved by
 * command id rather than by row identity: a scope may carry another owner's command as a
 * row of its own — a `g` destination wraps the declaration it stands for — and the
 * shortcut the user presses is the one that scope prefixes. */
export function commandSteps(id: string): string[] {
  for (const scope of pageScopes().filter((scope) => scope !== ELEMENTS))
    for (const row of scope.rows)
      if (row.id === id && bindings(row).length) return stepsIn(scope, row);
  return [];
}

/** The bindings that would make a command's press now, as the dispatcher reads them, or
 * null. They are the command's own binding where a key reaches it here, else the
 * bindings of a command that would open the scope holding it (`opens`), found the same
 * way, then its own binding: `g i` makes Resume writing's through Go-to, and `g V l`
 * Open latest's through Go-to and then Versions. A row in a scope that already stands
 * is reached by its own binding or not at all, so its door is passed over. A row behind
 * a door is available by what it declares, since its control is drawn only once the
 * door opens. Null where no key would make it, as with the caret in a box, where each
 * is a letter typed. */
function pressNow(id: string): string[] | null {
  const own = activeCommandBinding([id]);
  if (own !== null) return [own];
  for (const { door, opened } of doors()) {
    if (opened.at?.()) continue;
    const row = opened.rows.find(
      (row) => row.id === id && declaredCommandAvailable(row),
    );
    const [binding] = row ? bindings(row) : [];
    if (binding === undefined) continue;
    const opening = pressNow(door.id);
    if (opening) return [...opening, binding];
  }
  return null;
}
/** The bindings that would make a command's press now (`pressNow`), for a surface that
 * hands them on to be spelled, as a preview's `keys` (annotations/preview.js), or none, as on a
 * page that shows no keys, a touchscreen's. */
export function commandBindingsNow(id: string) {
  return (advertisesKeys() && pressNow(id)) || [];
}
/** Those bindings, each spelled as a key chip spells it. */
export const commandKeysNow = (id: string) => commandBindingsNow(id).map(spell);

type Reaching = {
  revision: number;
  available: ReturnType<typeof availableCommandRoutes>;
  controls: Map<Element, string[]>;
};
let reading: Reaching | null = null;
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
    const controls = new Map<Element, string[]>();
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

export const controlKeys = (control: Element): string[][] =>
  (reachingNow().controls.get(control) ?? []).map((binding) => [spell(binding)]);
// Each control's keys as `aria-keyshortcuts` spells them, as of the frame's reading:
// a control's reflection reads them here rather than asking the dispatcher, which may
// be reading the register as it reflects.
let painted = new Map<Element, string>();
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

/** What a listener hears of the keys that would run `rows` if pressed now, each resolved
 * as its press would be (dispatch.js, `pressRuns`), read out as key names, since a screen
 * reader renders a chip's "esc" literally. Every announcement that names a key names it
 * here, after words that name none, so it names no key a nearer scope, a focused field or
 * an earlier step of Escape takes, as a drawing's composer takes `z` and a grabbed card
 * Escape. Each key costs what its press would. Rows doing one thing under one title, as a
 * mode's own key and the Escape that leaves it, are said once ("w or Escape exit Draw
 * mode"). A touchscreen hears no keys, as it is shown none (`advertisesKeys`); a finger
 * uses the controls on screen. */
export const saying = (rows: readonly Command[]) => {
  if (!advertisesKeys()) return "";
  const said = new Map<string, string[]>();
  for (const row of rows) {
    if (!live(row)) continue;
    const reached = bindings(row).filter((binding) => pressRuns(binding, row));
    if (!reached.length) continue;
    const title = titleOf(row);
    said.set(title, [...(said.get(title) ?? []), spoken(row, reached)]);
  }
  return [...said].map(([title, keys]) => `${keys.join(" or ")} ${title}`).join(", ");
};
// A row's own label where it has one, read the way every other surface reads a cell, and
// the bindings where it has none — which is what keeps a listener hearing "Escape" rather
// than the keycap's "esc". Asking whether the label was written as a string made the same fact
// announce two ways by accident: an option group's digits are spelled "1–3" because its label
// happens to be a string, while the sequence's were read out as "1 or 2 or 3" because its label
// counts what the page holds and so has to be a function.
const spoken = (row: Command, reached: string[]) => {
  if (reached.some((binding) => parsed(binding).mods.length))
    return reached.map(spokenBinding).join(" or ");
  return word(row.label) ?? reached.map(spokenBinding).join(" or ");
};
