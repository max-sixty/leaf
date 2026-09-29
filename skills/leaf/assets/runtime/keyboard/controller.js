/* Browser input lifecycle. The dispatcher resolves declarations; this owner applies
   page policy around a real input (transient modes and the expanded shortcut bar), and presses the keys
   the prepaint bootstrap held before presentation once the page presents. */
import { dispatchKey } from "./dispatch.js";
import { MODIFIER_KEYS } from "./bindings.js";
import { beforeShortcutCommand } from "./shortcut-bar.js";
import { claimsEsc, focused } from "./scopes.js";
import { placingChrome, takesLetters, typesText } from "../focus.js";
import { nextFrame } from "../rendering.js";
import { PRESENTATION } from "../presentation.js";
export function mountKeyboard({
  goToSequenceActive,
  setGoToSequence,
  reactArmed,
  setReact,
}) {
  const run = (event) => dispatchKey(event, { beforeCommand: beforeShortcutCommand });
  const press = (ev) => {
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
  };
  document.addEventListener("keydown", press);
  // Keys pressed before the page presented were held by the prepaint bootstrap
  // (runtime/bootstrap.js), since the commands they name read state the page did not
  // have yet. The presented page takes them and presses them in order, a frame apart as
  // a hand would, so each lands on the page the one before it left. The hold keeps
  // queueing behind them until the queue is empty, and only then lets keys through.
  document.addEventListener(
    PRESENTATION,
    () => {
      const taking = new CustomEvent("lf-held-keys", { detail: {} });
      document.dispatchEvent(taking);
      const { keys, release } = taking.detail;
      // A hold that ended unpresented has nothing to hand over.
      if (!keys) return;
      const next = () => {
        if (!keys.length) {
          release();
          return;
        }
        const key = keys.shift();
        // The hold prevented each key's own insertion, so one whose turn comes in a box
        // an earlier key opened is typed into it here, as the browser would have.
        if (key.key.length === 1 && typesText(focused()))
          document.execCommand("insertText", false, key.key);
        else press(key);
        nextFrame(next);
      };
      nextFrame(next);
    },
    { once: true },
  );
  // Focus entering a box, or a control that claims Escape, disarms the sequence — a
  // digit typed in a box is text, and a chip left blooming would promise a cancel the
  // control would consume. The paint that answers the move is repaint.js's. A chrome
  // placement moves no one (focus.js, `placeChrome`), so it disarms nothing either.
  document.addEventListener("focusin", () => {
    if (placingChrome()) return;
    // The same question `setGoToSequence` asks before arming, so it takes the same answer: two
    // readings of where the user is standing would refuse to arm somewhere they then
    // failed to disarm.
    const active = focused();
    if (reactArmed() && (takesLetters(active) || claimsEsc(active))) setReact(false);
    if (goToSequenceActive() && (takesLetters(active) || claimsEsc(active))) {
      setGoToSequence(false);
    }
  });
}
