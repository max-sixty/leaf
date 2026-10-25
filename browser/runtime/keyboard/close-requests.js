/* The platform's close request, answered as Escape. Android's back gesture asks the
 * page to close something, as does an Escape keydown no listener canceled (HTML,
 * "Close requests and close watchers"). While Escape has a step to take, the page
 * holds one CloseWatcher, and its close takes that step, so a finger leaves a menu, a
 * view, a mode or a selection the way a key does (AGENTS.md, "Escape"). With nothing to
 * take, the page holds none and the gesture is the browser's: it goes back in history.
 * The browser's own modals and popovers hold watchers of their own, and a newer one
 * closes first, as Escape leaves them in the browser's order.
 *
 * Escape's keydown stays the dispatcher's. A press it answers is canceled, which ends
 * the close request before any watcher hears it, so one key never takes two steps.
 *
 * Whether to hold a watcher is read in the repaint frame (repaint.js), where the
 * register is read, so it follows whatever changes Escape's answer. A watcher that
 * closes is spent, which no other owner sees, so its close asks for the frame that
 * takes the next one.
 */
import { escapeTakesAStep, pressEscape } from "./dispatch.js";
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
    pressEscape();
    repaint();
  });
  watcher = held;
}
