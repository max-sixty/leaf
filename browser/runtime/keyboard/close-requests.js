/* The platform's close request, answered as Escape. Android's back gesture asks the
 * page to close something, as does an Escape keydown no listener canceled (HTML,
 * "Close requests and close watchers"). While Escape has a step to take, the page
 * holds one CloseWatcher, and its close takes that step, so a finger leaves a menu, a
 * view, a mode or a selection the way a key does (AGENTS.md, "Escape"). With nothing to
 * take, the page holds none and the gesture is the browser's: it goes back in history.
 * The browser's own modals and popovers hold watchers of their own, and a newer one
 * closes first, as Escape leaves them in the browser's order.
 *
 * Back never throws away words the user wrote and hasn't sent (Max's decision,
 * 2026-10-25), though Escape may: on a phone back comes before any key, and an edge
 * swipe made by accident after the keyboard hides would otherwise lose an edit nothing
 * undoes. A row whose `run` discards such words declares `keep` (bindings.js), which
 * back takes instead: it closes the editor as Escape would, keeps the words where
 * reopening finds them, and says so, as a composer closed over its words does. Each
 * owner shows the kept words where they stand, beside the control that reopens them,
 * and Resume writing reaches them from the panel's menu. Rejected: back taking no step
 * in a changed editor, which held the user on the page, since Chrome and Firefox let a
 * watcher rebuilt after each close catch every back, leaving only Save, Discard or a
 * tap elsewhere; and back saving the words, which sends a turn the user didn't ask
 * for.
 *
 * Escape's keydown stays the dispatcher's. A press it answers is canceled, which ends
 * the close request before any watcher hears it, so one key never takes two steps.
 *
 * Whether to hold a watcher is read in the repaint frame (repaint.js), where the
 * register is read, so it follows whatever changes Escape's answer. A watcher that
 * closes is spent, which no other owner sees, so its close asks for the frame that
 * takes the next one.
 */
import { answerCloseRequest, escapeTakesAStep } from "./dispatch.js";
import { repaint } from "../repaint.js";

let watcher = null;

export function paintCloseRequests() {
  // Safari lacks CloseWatcher.
  if (!("CloseWatcher" in window)) return;
  const step = escapeTakesAStep();
  if (step === Boolean(watcher)) return;
  if (!step) {
    watcher.destroy();
    watcher = null;
    return;
  }
  const held = new window.CloseWatcher();
  held.addEventListener("close", () => {
    if (watcher === held) watcher = null;
    answerCloseRequest();
    repaint();
  });
  watcher = held;
}
