/* Browser input lifecycle. The dispatcher resolves declarations; this owner applies
   page policy around a real input (transient modes and the shelf). */
import { dispatchKey } from "./dispatch.js";
import { MODIFIER_KEYS } from "./bindings.js";
import { beforeShortcutCommand } from "./shortcut-bar.js";
import { claimsEsc, focused } from "./scopes.js";
import { takesLetters } from "../focus.js";
import { runtime } from "../context.js";
import { repaint } from "../repaint.js";
export function mountKeyboard({
  goToSequenceActive,
  setGoToSequence,
  reactArmed,
  setReact,
}) {
  const run = (event) => dispatchKey(event, { beforeCommand: beforeShortcutCommand });
  document.addEventListener("keydown", (ev) => {
    if (ev.isComposing) return;
    if (run(ev)) return;
    // Any other key disarms the sequence and keeps its ordinary meaning, so a mistyped g costs
    // nothing: g T is a panel trip and g g re-arms. A key naming no destination disarms the
    // same way. Spelled as walking
    // again rather than as a rule, so the meaning a key keeps is the meaning the register
    // gives it. A modifier alone is half a press rather than a key: the Shift that
    // capitalizes G arrives as a keydown of its own ahead of it, and disarming on that
    // took the window down before the G it was armed for.
    if ((goToSequenceActive() || reactArmed()) && !MODIFIER_KEYS.includes(ev.key)) {
      setGoToSequence(false);
      setReact(false);
      run(ev);
    }
  });
  // A focus move is the one change in where the user is standing that no state writer
  // sees, so it asks for the paint itself — the ring and the line both, which is why one
  // call answers for it. Focus entering a box, or a control that claims Escape, also disarms
  // the sequence — a digit typed in a box is text, and a chip left blooming would promise a
  // cancel the control would consume.
  //
  // Not for a placement, which emits the same pair around a focus that never left: the
  // margin moves a row between lanes when its target's scroller changes, and puts the
  // user back where they stood. Answering that as a move paints the standing chrome,
  // whose layout pass asks for the next placement. The user has not moved and nothing
  // they can see has changed, so there is nothing here to paint.
  document.addEventListener("focusin", () => {
    if (runtime.placingChrome) return;
    // The same question `setGoToSequence` asks before arming, so it takes the same answer: two
    // readings of where the user is standing would refuse to arm somewhere they then
    // failed to disarm.
    const active = focused();
    if (reactArmed() && (takesLetters(active) || claimsEsc(active))) setReact(false);
    if (goToSequenceActive() && (takesLetters(active) || claimsEsc(active))) {
      setGoToSequence(false);
    }
    repaint();
  });
  document.addEventListener("focusout", () => {
    if (!runtime.placingChrome) repaint();
  });
}
