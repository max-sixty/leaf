/* A delayed completion may move the user only while the gesture that started it
   remains their latest intent. Runtime-owned repaint and focus changes do not supersede
   that intent; a later user input, leaving the window, or focus moving away from the
   surface that began the work does.

   Intent is captured at the gesture and handed to what the work later does: `reveal`
   takes it as a required argument, so no delayed caller can take a fresh one after its
   wait. `scroll` is not among the superseding inputs, because it is not one: the runtime's
   own landings and place holds fire it, and so does the delayed work's own first move.
   The user's ways of scrolling each begin with an input that is here: a scrollbar
   press is a `pointerdown` on the scroller, a wheel or trackpad is `wheel`, a touch
   scroll `touchstart`, a key `keydown`, and find-in-page takes focus from the window,
   which is `blur`. */
import { focused } from "./keyboard/scopes.js";

let intent = 0;
const leave = () => intent++;
for (const type of ["pointerdown", "keydown", "input", "wheel", "touchstart"])
  addEventListener(type, leave, { capture: true, passive: true });
addEventListener("blur", leave);

// Capture before the first asynchronous step. Pass this same predicate into nested
// reveals; capturing again after a wait gives stale work a newer gesture's authority.
export function retainUserIntent({
  source = focused(),
  available = () => true,
  fallback = null,
} = {}) {
  const retained = intent;
  const current = () => {
    const at = focused();
    const withinSource =
      source === document.body ? at === document.body : source?.contains(at);
    return (
      available() &&
      retained === intent &&
      (at === document.body || at === fallback || withinSource)
    );
  };
  // Synchronous work may already have transferred focus, as a connected widget can
  // during replacement. Keep that destination instead of running the old focus move,
  // and adopt it for subsequent continuity without renewing the input generation.
  // A delayed caller must check current() before beginning its synchronous handoff.
  current.handoff = (move) => {
    if (!available() || retained !== intent) return false;
    const moved = current();
    if (moved) move();
    source = focused();
    return moved && current();
  };
  return current;
}
