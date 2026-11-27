/* Browser input lifecycle. The dispatcher resolves declarations; this owner applies
   page policy around a real input (transient modes), and
   releases bootstrap's ordered keys as their declared input becomes available.

   Focus stays on a control the user has scrolled out of sight, but they are reading
   something else (readings/user-place.js, `focusPlace`), so a key they press there lets go of it
   first (dom/focus.js, `letGo`) and then acts from what they see: no Leaf command settles,
   chooses or toggles what they can't see, Space pages on from what they read and Tab
   moves on from it. The let-go lands on what they see, so it moves nothing, and they
   are not beside what they let go of, so no walk comes back to it (records/current-target.js,
   `walkOrigin`). It is not Escape's release: a card open beside what they left stays
   open where it rides. Chromium and WebKit still apply a radio's, slider's or select's
   own arrows at the control the key was aimed at, wherever focus has gone
   (notes/browser-support.md), so those are withheld, and that arrow scrolls nothing. The
   key stops at the document once it lets go, so no listener on the control or a widget
   around it hears it, and a page's own listener on the document or window hears it only
   in capture. Leaf's own command for the key still runs, and the browser's default runs
   from where focus landed unless that command prevents it. Escape takes its own
   step, a key typed into a text field keeps the field, since typing brings its box back
   (readings/off-flow.js), and a modifier alone is half a press. Tab types nothing, so it goes on
   from what they read. A select's letters let go, since
   they choose an option the user can't see. */
import { dispatchKey, keyReady } from "../../dom/keyboard/dispatch.js";
import { MODIFIER_KEYS } from "../../dom/control-selectors.js";
import { placeHandedBack, quickShortcuts } from "../../dom/keyboard/bindings.js";
import {
  claimsEsc,
  paintKeys,
  watchCommandAvailability,
} from "../../dom/keyboard/scopes.js";
import {
  controlNavigationKeys,
  letGo,
  onCurrentLocation,
  takesLetters,
  typesText,
  focused,
} from "../../dom/focus.js";
import { focusPlace } from "../../readings/user-place.js";
import { landForKey } from "../../dom/scrolling.js";
import { nextFrame } from "../../lib/frame-pass.js";
import { pageUpgraded } from "../../base/page-paint.js";
import { runtime } from "../../state/context.js";
import { UPGRADE, PRESENTATION } from "../../readings/presentation.js";
import { readLeavingKeys } from "../../base/field-keys.js";
import { authoredScope } from "../../readings/passages.js";
// A document the runtime gives up on before it upgrades, because it reloads or waits on
// a server serving another layer, ends bootstrap's hold: nothing in it will run what
// was held, so those keys are dropped and later ones reach the page as they come.
export function letHeldKeysGo() {
  /** @type {DocumentEventMap["lf-held-keys"]} */
  const taking = new CustomEvent("lf-held-keys", {
    detail: { ready: () => false, keep: () => false },
  });
  document.dispatchEvent(taking);
  taking.detail.release?.();
}

/** @param {{goToSequenceActive: () => boolean, setGoToSequence: (on: boolean) => void, reactArmed: () => boolean, setReact: (on: boolean) => void}} options */
export function mountKeyboard({
  goToSequenceActive,
  setGoToSequence,
  reactArmed,
  setReact,
}) {
  /** @param {KeyboardEvent} event @param {boolean} [waiting] */
  const run = (event, waiting = false) => {
    const handled = dispatchKey(event, waiting);
    // A Leaf command that ran keeps its key from the listeners after it, the page's
    // on the document and the window. Native activation is left to the focused control.
    if (handled && event.defaultPrevented) event.stopPropagation();
    return handled;
  };
  const armed = () => goToSequenceActive() || reactArmed();
  const disarm = () => {
    setGoToSequence(false);
    setReact(false);
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
    if (armed() && !MODIFIER_KEYS.includes(ev.key)) {
      disarm();
      run(ev);
    }
  };
  // Whether `ev` lets go of focus the user can't see (see the header).
  /** @param {KeyboardEvent} ev */
  const letsGo = (ev) => {
    if (ev.isComposing || ev.key === "Escape" || MODIFIER_KEYS.includes(ev.key))
      return false;
    const at = focused();
    if (!at || at === document.body) return false;
    if (typesText(at) && ev.key !== "Tab") return false;
    if (focusPlace()) return false;
    if (controlNavigationKeys(at).includes(ev.key)) ev.preventDefault();
    return true;
  };
  // Outside its own fields, which read their keys themselves (below), Leaf hears a key
  // in three places.
  //
  // In capture, ahead of every listener of the page's: a key that lets go, which stops
  // there so every key reads from where the user is; a key aimed at the page itself,
  // `body` with nothing focused, since no element of the page's has the user's focus to
  // answer it, so Leaf's command for it runs first and keeps it from a page listener
  // whatever that listener prevents; and, while Go-to or reactions are armed, a key they
  // answer, since they own the keyboard. Any other key disarms them there and keeps its
  // ordinary meaning, read below.
  document.addEventListener(
    "keydown",
    (ev) => {
      const away = letsGo(ev);
      if (away) {
        letGo();
        ev.stopPropagation();
      }
      // Tab and the paging keys go on to the browser, which moves focus or scrolls from
      // where the page stands, so the glides under way land first (dom/scrolling.js,
      // `landForKey`), once the let-go has read where they were headed.
      landForKey(ev);
      if (away || ev.target === document.body) press(ev);
      else if (armed() && !ev.isComposing) {
        if (run(ev)) ev.stopPropagation();
        else if (!MODIFIER_KEYS.includes(ev.key)) disarm();
      }
    },
    { capture: true },
  );
  // On the root element, where every other key is read, printed letters among them:
  // after the listeners on the control and on every element around it, the page's and
  // Leaf's own, and before the page's listeners on the document and the window, which
  // hear only a key Leaf leaves. So a key keeps the order a widget's own listener would
  // give it: the focused element's handling comes first, then Leaf's command there, then
  // a page-wide shortcut. A key aimed inside an authored document, the page's `body` or
  // a message's body (`authoredScope`), whose default is already prevented by then is
  // its author's, as role-button-press.js reads a press, so a widget that answers a
  // letter itself and prevents it keeps it from Leaf's page command, in the page or in a
  // message the panel shows. The event's path, fixed as it was dispatched, says where
  // the key was aimed even where that answer redrew or removed the element. Read again
  // here, it would act at wherever that code had moved focus, such as the trigger a
  // page's menu hands focus back to. The rest of Leaf's chrome stands outside both, so
  // its keys stay Leaf's whatever a page listener prevents, and a key aimed at `body`
  // itself was read in capture.
  document.documentElement.addEventListener("keydown", (ev) => {
    if (ev.target === document.body) return;
    const authored =
      ev.defaultPrevented &&
      ev
        .composedPath()
        .some((node) => node instanceof Element && authoredScope(node) === node);
    if (!authored) press(ev);
  });
  // A row that `waits` is what Leaf does with a key only once nothing else has taken
  // it, as Escape lets go of a control in the page (panel/page-keys/page.js), so it is read
  // last, after the page's listeners on the document and the window. A popup that hears
  // Escape there from the moment it opens, as UI SDK's tooltip, Web Awesome's select and
  // Headless UI's dialog do, puts itself away first and prevents the key, and focus
  // stays on its trigger.
  /** @param {KeyboardEvent} ev */
  const last = (ev) => {
    if (!ev.defaultPrevented && !ev.isComposing) run(ev, true);
  };
  // The window hears a key twice, first in capture and last in bubble, and the browser
  // copies its list of listeners afresh for each (DOM, "inner invoke"). Adding `last`
  // again in capture puts it behind every listener a page has added to the window
  // since, so "last" holds whenever the page's listener was added.
  window.addEventListener(
    "keydown",
    () => {
      window.removeEventListener("keydown", last);
      window.addEventListener("keydown", last);
    },
    { capture: true },
  );
  // A key typed in a Leaf field stops at the field (base/field-keys.js), so this pass reads
  // it there, a waiting row included: no listener past the field is left to take the key.
  readLeavingKeys((ev) => {
    if (ev.type !== "keydown") return;
    press(ev);
    if (ev.key.length !== 1 && !ev.defaultPrevented && !ev.isComposing) run(ev, true);
  });
  document.addEventListener("lf-keyboard-preference", () => {
    paintKeys();
    if (!quickShortcuts()) disarm();
  });
  let pressingHeld = false;
  // Upgrade opens commands about the shown document. A command needing private
  // history keeps its key and every printed key behind it in the same queue until
  // the saved reading. New ready keys otherwise pass straight through bootstrap.
  // Until a reload's place is handed back, the run waits wherever focus is, even in a
  // box the page opened before the hand-back put the user back in theirs, and the hold
  // lets it go at any other input (bootstrap.js, `holdEarlyKeys`); the hand-back begins
  // before the page upgrades (features/version.js, `installArrival`).
  const takeHeldKeys = () => {
    if (!pageUpgraded() || pressingHeld || !placeHandedBack()) return;
    /** @type {DocumentEventMap["lf-held-keys"]} */
    const taking = new CustomEvent("lf-held-keys", {
      detail: {
        ready: keyReady,
        keep: () => runtime.statePhase === "waiting",
      },
    });
    document.dispatchEvent(taking);
    const { keys, pressed, pause, release } = taking.detail;
    // An empty or ended hold has nothing to hand over.
    if (!keys) return;
    pressingHeld = true;
    const next = () => {
      // With single-key commands off, a held key only ever types into a box; the
      // release lets go of the rest.
      const [key] = keys;
      if (!key || (!quickShortcuts() && !typesText(focused()))) {
        release();
        pressingHeld = false;
        return;
      }
      if (!typesText(focused()) && !keyReady(key)) {
        pause();
        pressingHeld = false;
        return;
      }
      pressed();
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
  // control would consume. The paint that answers the move is dom/repaint.js's. A chrome
  // placement handing the user straight back to the node it moved moves no one, so it
  // publishes nothing to disarm (dom/focus.js, `onCurrentLocation`).
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
