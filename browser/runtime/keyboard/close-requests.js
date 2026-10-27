/* The platform's close request, answered as Escape. Android's back gesture asks the
 * page to close something, as does an Escape keydown no listener canceled (HTML,
 * "Close requests and close watchers"). While Escape has a step to take, the page
 * holds one CloseWatcher, and its close takes that step, so a finger leaves a menu, a
 * view, a mode or a selection the way a key does (AGENTS.md, "Escape"). With nothing to
 * take, the page holds none and the gesture is the browser's: it goes back in history.
 * The browser's own modals and popovers hold watchers of their own, and the newest
 * closes first. So where a layer opens over the page's watcher while Escape still has
 * a step of Leaf's to take, as a command inside a modal dialog, the watcher is made
 * again above it, and back takes that step as Escape does before the layer closes. A
 * layer in which Escape has no step of Leaf's leaves the page holding none, and back
 * closes it as the browser does.
 *
 * Back never throws away words the user wrote and hasn't sent (Max's decision,
 * 2026-10-25), though Escape may: on a phone back comes before any key, and an edge
 * swipe made by accident after the keyboard hides would otherwise lose an edit nothing
 * undoes. A row whose `run` discards such words declares `keep` (bindings.js), which
 * back takes instead: it closes the editor without losing the words. An `lf-draft`,
 * which a press away saves, saves them too, so a stray swipe sends a turn as a stray
 * tap does (Max's decision, 2026-10-27). A message rewrite saves only on Enter or
 * Save, so back keeps its words where reopening finds them and says so, as a composer
 * closed over its words does, showing them beside the control that reopens them.
 * Rejected: back taking no step in a changed editor, which held the user on the page,
 * since Chrome and Firefox let a watcher rebuilt after each close catch every back,
 * leaving only Save, Discard or a tap elsewhere.
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
import { nativeLayers, watchLayerChanges } from "./layer-stack.js";
import { repaint } from "../repaint.js";

let watcher = null;
// The native layers standing when the watcher was made. One opened since stands above
// it, its own watcher closing first.
let under = [];
watchLayerChanges(() => repaint());

export function paintCloseRequests() {
  // Safari lacks CloseWatcher.
  if (!("CloseWatcher" in window)) return;
  const step = escapeTakesAStep();
  const top = nativeLayers().at(-1);
  const coveredOver = Boolean(watcher) && top !== undefined && !under.includes(top);
  if (step === Boolean(watcher) && !coveredOver) return;
  watcher?.destroy();
  watcher = null;
  if (!step) return;
  const held = new window.CloseWatcher();
  held.addEventListener("close", () => {
    if (watcher === held) watcher = null;
    answerCloseRequest();
    repaint();
  });
  watcher = held;
  under = nativeLayers();
}
