/* What a visible control says about the key that reaches it.

   A control the keyboard reaches names its shortcut from the row, never from a sentence
   written beside it: `control` is where a row says which control it duplicates, and this
   projection follows liveness too, so a disabled ask does not advertise a shortcut the
   dispatcher has withdrawn. A row inside a sequence scope carries that sequence's steps,
   so a destination reached through `g` says the whole shortcut.

   This pass is the one writer of such a control's `title`. The control's owner names it
   in `data-lf-key-title`, and a static control's first title is taken as that name, so
   the owner and this pass never take turns rewriting the one attribute.

   The pass runs in the fixed chrome's frame, so every name it writes goes through
   `keeps` and says nothing where the control already says it. Restated title or shortcut
   metadata is news to whatever is reading the page — the mutation stream a screen reader
   rebuilds its buffer from — and these controls stand on the banner the margin projection
   watches. */
import { ariaShortcuts, bindings, labelOf, live, word } from "./bindings.js";
import { pageScopes, universalCommandReference } from "./register.js";
import { buttonCommand } from "./scopes.js";
import { keeps } from "../keeps.js";

const stepsBefore = (scope) => word(scope?.sequencePrefix ?? scope?.sequence) ?? [];
// The presses that reach a row, each spelled as a key chip spells it: a step is one
// press, so a label's own words never split into steps.
const stepsIn = (scope, row) => [...stepsBefore(scope), labelOf(row)].filter(Boolean);
const shortcutIn = (scope, row) => stepsIn(scope, row).join(" ");

/** The complete shortcut one command advertises, for a control whose own shortcut spans
 * more than one row and so cannot be painted by the pass below. Resolved by command id rather
 * than by row identity: a scope may carry another owner's command as a row of its own —
 * a `g` destination wraps the declaration it stands for — and the shortcut the user
 * presses is the one that scope prefixes. */
export function commandShortcut(id) {
  for (const scope of pageScopes())
    for (const row of scope?.rows ?? [])
      if (row.id === id && bindings(row).length) return shortcutIn(scope, row);
  return "";
}

// Each visible control a page row names, with the row that reaches it.
function controlRows() {
  // The shortcut bar owns the permanent More control because its binding must first pass
  // through the same contextual shadowing as the line's ordinary rows.
  const more = universalCommandReference();
  const controls = new Map();
  for (const scope of pageScopes())
    for (const row of scope?.rows ?? []) {
      if (row === more) continue;
      const control = word(row.control);
      if (!control) continue;
      const active = live(row) && bindings(row).length > 0;
      const prior = controls.get(control);
      // One native control may also have an unbound semantic route for reference
      // activation. Project it once, preferring the live keyboard presentation;
      // the unbound row must not erase that route or rewrite its title each frame.
      if (!prior || (!prior.active && active))
        controls.set(control, { scope, row, active });
    }
  return controls;
}

/** The steps of the complete shortcut that reaches each visible control now, by
 * control, for a presentation that draws a control as words rather than the control
 * itself, as a menu built from the banner's rows does (banner-toolbar.js, `bannerRows`),
 * and draws each step as a key (key-sequence.js). */
export function controlShortcuts() {
  const shortcuts = new Map();
  for (const [control, { scope, row, active }] of controlRows())
    if (active) shortcuts.set(control, stepsIn(scope, row));
  return shortcuts;
}

export function paintCoreControls() {
  for (const [control, { scope, row, active }] of controlRows()) {
    if (!("lfKeyTitle" in control.dataset)) control.dataset.lfKeyTitle = control.title;
    keeps(
      control,
      "title",
      control.dataset.lfKeyTitle + (active ? ` (${shortcutIn(scope, row)})` : ""),
    );
    // Native command buttons receive exact reachable shortcuts from command-hints.
    if (buttonCommand(control)) continue;
    // aria-keyshortcuts has no syntax for sequential shortcuts: its spaces separate
    // alternatives. The complete sequence remains in the overlay, tooltip, and
    // accessible command reference instead of claiming its final press works alone.
    keeps(
      control,
      "aria-keyshortcuts",
      active && !scope.sequence ? ariaShortcuts([row], false) : null,
    );
  }
}
