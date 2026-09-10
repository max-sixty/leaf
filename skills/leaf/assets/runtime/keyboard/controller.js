/* Browser input lifecycle. The dispatcher resolves declarations; this owner applies
   page policy around a real input (transient modes, shelf, and return origins). */
import { dispatchKey, readerIn } from "./dispatch.js";
import { MODIFIER_KEYS } from "./bindings.js";
import { beforeShortcutCommand } from "./shortcut-bar.js";
import { claimsEsc, focused } from "./scopes.js";
import { takesLetters } from "../focus.js";
import { runtime } from "../context.js";
import { repaint } from "../repaint.js";
const standing = (scope) => readerIn(scope) && (!scope.when || scope.when());
export function mountKeyboard({
  isSequenceActive,
  setSequence,
  REACT,
  setReact,
  captureReturnPlace,
}) {
  const run = (event) =>
    dispatchKey(event, {
      beforeCommand: beforeShortcutCommand,
      captureOrigin: captureReturnPlace,
    });
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
    if ((isSequenceActive() || standing(REACT)) && !MODIFIER_KEYS.includes(ev.key)) {
      setSequence(false);
      setReact(false);
      run(ev);
    }
  });
  // A focus move is the one change in where the reader is standing that no state writer
  // sees, so it asks for the paint itself — the ring and the line both, which is why one
  // call answers for it. Focus entering a box, or a control that claims Escape, also disarms
  // the sequence — a digit typed in a box is text, and a chip left blooming would promise a
  // cancel the control would consume.
  //
  // Not for a placement, which emits the same pair around a focus that never left: the
  // margin takes a docked cluster out of flow to measure where it can hang and puts it and
  // the reader back, once per layout pass. Answering that as a move painted the standing
  // chrome, whose layout pass asked for the next placement, and a page with the reader
  // standing in a docked cluster laid its margin out on every frame for as long as they
  // stood there. The reader has not moved and nothing they can see has changed, so there
  // is nothing here to paint.
  document.addEventListener("focusin", () => {
    if (runtime.placingChrome) return;
    // The same question `setSequence` asks before arming, so it takes the same answer: two
    // readings of where the reader is standing would refuse to arm somewhere they then
    // failed to disarm.
    const active = focused();
    if (standing(REACT) && (takesLetters(active) || claimsEsc(active))) setReact(false);
    if (isSequenceActive() && (takesLetters(active) || claimsEsc(active))) {
      setSequence(false);
    }
    repaint();
  });
  document.addEventListener("focusout", () => {
    if (!runtime.placingChrome) repaint();
  });
}
