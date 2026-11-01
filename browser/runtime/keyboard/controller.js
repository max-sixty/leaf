/* Browser input lifecycle. The dispatcher resolves declarations; this owner applies
   page policy around a real input (transient modes), and
   releases bootstrap's ordered keys as their declared input becomes available. */
import { dispatchKey, keyReady } from "./dispatch.js";
import { MODIFIER_KEYS } from "../control-selectors.js";
import { quickShortcuts } from "./bindings.js";
import { claimsEsc, paintKeys, watchCommandAvailability } from "./scopes.js";
import { onCurrentLocation, takesLetters, typesText, focused } from "../focus.js";
import { nextFrame } from "../rendering.js";
import { pageUpgraded } from "../page-paint.js";
import { runtime } from "../context.js";
import { UPGRADE, PRESENTATION } from "../presentation.js";
/** @param {{goToSequenceActive: () => boolean, setGoToSequence: (on: boolean) => void, reactArmed: () => boolean, setReact: (on: boolean) => void}} options */
export function mountKeyboard({
  goToSequenceActive,
  setGoToSequence,
  reactArmed,
  setReact,
}) {
  /** @param {KeyboardEvent} event */
  const run = (event) => {
    const handled = dispatchKey(event);
    // A declared Leaf command wins before a nested widget can interpret the
    // same key. Native activation is left to the focused control.
    if (handled && event.defaultPrevented) event.stopPropagation();
    return handled;
  };
  /** @param {KeyboardEvent} ev */
  const press = (ev) => {
    if (ev.isComposing) return;
    if (run(ev)) return;
    // Any other key disarms the sequence and keeps its ordinary meaning, so a mistyped g costs
    // nothing: g T is a panel navigation step and g g re-arms. A key naming no destination disarms the
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
  // Page shortcut characters need Leaf's scope resolution before a nested
  // library can use them for typeahead. Other keys keep the control's own
  // handling first, including search's Enter and Escape steps.
  document.addEventListener(
    "keydown",
    (ev) => {
      if (ev.key.length === 1) press(ev);
    },
    { capture: true },
  );
  document.addEventListener("keydown", (ev) => {
    if (ev.key.length !== 1) press(ev);
  });
  document.addEventListener("lf-keyboard-preference", () => {
    paintKeys();
    if (quickShortcuts()) return;
    setGoToSequence(false);
    setReact(false);
  });
  let pressingHeld = false;
  // Upgrade opens commands about the shown document. A command needing private
  // history keeps its key and every printed key behind it in the same queue until
  // the saved reading. New ready keys otherwise pass straight through bootstrap.
  const takeHeldKeys = () => {
    if (!pageUpgraded() || pressingHeld) return;
    /** @type {DocumentEventMap["lf-held-keys"]} */
    const taking = new CustomEvent("lf-held-keys", {
      detail: { ready: keyReady, keep: () => runtime.statePhase === "waiting" },
    });
    document.dispatchEvent(taking);
    const { keys, pause, release } = taking.detail;
    // An empty or ended hold has nothing to hand over.
    if (!keys) return;
    pressingHeld = true;
    const next = () => {
      if (!quickShortcuts()) keys.length = 0;
      const [key] = keys;
      if (!key) {
        release();
        pressingHeld = false;
        return;
      }
      if (!typesText(focused()) && !keyReady(key)) {
        pause();
        pressingHeld = false;
        return;
      }
      keys.shift();
      // The hold prevented each key's own insertion, so one whose turn comes in a box
      // an earlier key opened is typed into it here, as the browser would have.
      if (key.key.length === 1 && typesText(focused()))
        document.execCommand("insertText", false, key.key);
      else press(key);
      nextFrame(next);
    };
    nextFrame(next);
  };
  document.addEventListener(UPGRADE, takeHeldKeys, { once: true });
  document.addEventListener(PRESENTATION, takeHeldKeys, { once: true });
  // A declared initial input may arrive after presentation. Its owner already
  // repaints availability through paintKeys; that same reading releases held keys.
  watchCommandAvailability(takeHeldKeys);
  // Focus entering a box, or a control that claims Escape, disarms the sequence — a
  // digit typed in a box is text, and a chip left blooming would promise a cancel the
  // control would consume. The paint that answers the move is repaint.js's. A chrome
  // placement handing the user straight back to the node it moved moves no one, so it
  // publishes nothing to disarm (focus.js, `onCurrentLocation`).
  onCurrentLocation(() => {
    // The same question `setGoToSequence` asks before arming, so it takes the same answer: two
    // readings of where the user is would refuse to arm somewhere they then
    // failed to disarm.
    const active = focused();
    if (reactArmed() && (takesLetters(active) || claimsEsc(active))) setReact(false);
    if (goToSequenceActive() && (takesLetters(active) || claimsEsc(active))) {
      setGoToSequence(false);
    }
  });
}
