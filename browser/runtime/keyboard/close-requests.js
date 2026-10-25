/* The platform's close request, answered as Escape. Android's back gesture asks the
 * page to close something, as does an Escape keydown no listener canceled (HTML,
 * "Close requests and close watchers"). While Escape has a step to take, the page
 * holds one CloseWatcher, and its close takes that step, so a finger leaves a menu, a
 * view, a mode or a selection the way a key does (AGENTS.md, "Escape"). With nothing to
 * take, the page holds none and the gesture is the browser's: it goes back in history.
 * The browser's own modals and popovers hold watchers of their own, and a newer one
 * closes first, as Escape leaves them in the browser's order.
 *
 * Back never throws away words the user wrote and hasn't sent. A step whose row says
 * it would (`discards`, keyboard/bindings.js), such as Discard in a changed draft
 * editor or message rewrite, is left to Escape and the visible control: the close
 * takes no step, the editor stays open with its words, and a notice says they are
 * kept. The watcher still stands, so the gesture doesn't leave the page either. Back
 * comes before the keyboard on a phone, and an edge swipe made by accident after the
 * keyboard hides would otherwise lose the edit with no undo (Max's decision,
 * 2026-10-25). Rejected: back saving the words, as Mod+Enter does, which sends a turn
 * the user didn't ask for; and back closing the editor while the store keeps the
 * words, which leaves a closed box holding words it gives no sign of, the reading
 * lf-draft.js and message-edit.js already rejected for Escape.
 *
 * Escape's keydown stays the dispatcher's. A press it answers is canceled, which ends
 * the close request before any watcher hears it, so one key never takes two steps.
 *
 * Whether to hold a watcher is read in the repaint frame (repaint.js), where the
 * register is read, so it follows whatever changes Escape's answer. A watcher that
 * closes is spent, which no other owner sees, so its close asks for the frame that
 * takes the next one.
 */
import { word } from "./bindings.js";
import { escapeStep, pressEscape } from "./dispatch.js";
import { notice } from "../notifications.js";
import { repaint } from "../repaint.js";

let watcher = null;

export function paintCloseRequests() {
  // Safari lacks CloseWatcher.
  if (!("CloseWatcher" in window)) return;
  const step = Boolean(escapeStep());
  if (step === Boolean(watcher)) return;
  if (!step) {
    watcher.destroy();
    watcher = null;
    return;
  }
  const held = new window.CloseWatcher();
  held.addEventListener("close", () => {
    if (watcher === held) watcher = null;
    if (word(escapeStep()?.discards)) notice("The unsent words are kept");
    else pressEscape();
    repaint();
  });
  watcher = held;
}
