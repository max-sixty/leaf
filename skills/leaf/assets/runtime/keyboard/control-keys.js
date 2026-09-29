/* What a visible control says about the key that reaches it.

   A control the keyboard reaches names its shortcut from the row, never from a sentence
   written beside it: `control` is where a row says which control it duplicates, and this
   projection follows liveness too, so a disabled Ask does not advertise a shortcut the
   dispatcher has withdrawn. A row inside a sequence scope carries that sequence's steps,
   so a destination reached through `g` says the whole shortcut.

   This pass is the one writer of such a control's `title`. The control's owner names it
   in `data-lf-key-title`, and a static control's first title is taken as that name, so
   the owner and this pass never take turns rewriting the one attribute.

   The pass runs in the standing chrome's frame, so every name it writes goes through
   `keeps` and says nothing where the control already says it. Restated title or shortcut
   metadata is news to whatever is reading the page — the mutation stream a screen reader
   rebuilds its buffer from — and these controls stand on the banner the margin projection
   watches. */
import { ariaShortcuts, bindings, labelOf, live, word } from "./bindings.js";
import { pageScopes, universalCommandReference } from "./register.js";
import { keeps } from "../keeps.js";

const stepsBefore = (scope) => word(scope?.sequencePrefix ?? scope?.sequence) ?? [];
const shortcutIn = (scope, row) =>
  [...stepsBefore(scope), labelOf(row)].filter(Boolean).join(" ");

/** The complete shortcut one command advertises, for a control whose own shortcut spans
 * more than one row and so cannot be painted by the pass below. Resolved by command id rather
 * than by row identity: a scope may carry another owner's command as a row of its own —
 * a `g` destination wraps the declaration it stands for — and the shortcut the user
 * presses is the one that scope prefixes. */
export function commandShortcut(id) {
  for (const scope of pageScopes())
    for (const row of scope?.rows ?? [])
      if (row.id === id) return shortcutIn(scope, row);
  return "";
}

export function paintCoreControls() {
  // The shortcut bar owns the permanent More control because its binding must first pass
  // through the same contextual shadowing as the line's ordinary rows.
  const more = universalCommandReference();
  for (const scope of pageScopes())
    for (const row of scope?.rows ?? []) {
      if (row === more) continue;
      const control = word(row.control);
      if (!control) continue;
      if (!("lfKeyTitle" in control.dataset))
        control.dataset.lfKeyTitle = control.title;
      const active = live(row) && bindings(row).length > 0;
      keeps(
        control,
        "title",
        control.dataset.lfKeyTitle + (active ? ` (${shortcutIn(scope, row)})` : ""),
      );
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
