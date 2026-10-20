/* What a visible control says about the key that reaches it.

   A control the keyboard reaches names its shortcut from the row, never from a sentence
   written beside it: `control` is where a row, or one route of it, says which control it
   duplicates, and this projection follows liveness too, so a disabled obligation does not
   advertise a shortcut the dispatcher has withdrawn. A row inside a sequence scope carries
   that sequence's steps, so a destination reached through `g` says the whole shortcut.

   This pass is the one writer of such a control's `title`. The control's owner names it
   in `data-lf-key-title`, and a static control's first title is taken as that name, so
   the owner and this pass never take turns rewriting the one attribute.

   The pass runs in the fixed chrome's frame, so every name it writes goes through
   `keeps` and says nothing where the control already says it. Restated title or shortcut
   metadata is news to whatever is reading the page — the mutation stream a screen reader
   rebuilds its buffer from. */
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
import { pageScopes } from "./register.js";
import { buttonCommand } from "./scopes.js";
import { keeps } from "../keeps.js";

const stepsBefore = (scope) => word(scope?.sequencePrefix ?? scope?.sequence) ?? [];
// The presses that reach a row, each spelled as a key chip spells it: a step is one
// press, so a label's own words never split into steps.
const stepsIn = (scope, row) => [...stepsBefore(scope), labelOf(row)].filter(Boolean);

/** The complete shortcut one command advertises, each press a step as a key chip
 * spells it, for a presentation that draws a command as words with its keys
 * (page-controls.js, a row's `shortcut`). Empty for a command no key reaches. Resolved by
 * command id rather than by row identity: a scope may carry another owner's command as a
 * row of its own — a `g` destination wraps the declaration it stands for — and the
 * shortcut the user presses is the one that scope prefixes. */
export function commandSteps(id) {
  for (const scope of pageScopes())
    for (const row of scope?.rows ?? [])
      if (row.id === id && bindings(row).length) return stepsIn(scope, row);
  return [];
}

// Each visible control a page row names, or one of its routes does, with the press that
// reaches it: a route's control names that route's binding alone.
function* namedControls(row) {
  if (row.control)
    yield {
      control: row.control,
      active: live(row) && bindings(row).length > 0,
      press: labelOf(row),
      shortcuts: () => ariaShortcuts([row], false),
    };
  for (const route of commandRoutes(row))
    if (route.control)
      yield {
        control: route.control,
        active: commandAvailable(row, route) && bindings(row).includes(route.binding),
        press: spell(route.binding),
        shortcuts: () => ariaShortcuts([{ keys: [route.binding] }], false),
      };
}

function controlRows() {
  const controls = new Map();
  for (const scope of pageScopes())
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

export function paintCoreControls() {
  for (const [control, { scope, active, press, shortcuts }] of controlRows()) {
    if (!("lfKeyTitle" in control.dataset)) control.dataset.lfKeyTitle = control.title;
    const steps = [...stepsBefore(scope), press].filter(Boolean).join(" ");
    keeps(control, "title", control.dataset.lfKeyTitle + (active ? ` (${steps})` : ""));
    // Native command buttons receive exact reachable shortcuts from command-hints.
    if (buttonCommand(control)) continue;
    // aria-keyshortcuts has no syntax for sequential shortcuts: its spaces separate
    // alternatives. The complete sequence remains in the overlay, tooltip, and
    // accessible command reference instead of claiming its final press works alone.
    keeps(control, "aria-keyshortcuts", active && !scope.sequence ? shortcuts() : null);
  }
}
