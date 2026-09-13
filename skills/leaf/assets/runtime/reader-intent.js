/* A delayed completion may move the reader only while the gesture that started it
   remains their latest intent. Runtime-owned repaint and focus changes do not supersede
   that intent; a later reader input, leaving the window, or focus moving away from the
   surface that began the work does. */
import { focused } from "./keyboard/scopes.js";

let intent = 0;
const leave = () => intent++;
for (const type of ["pointerdown", "keydown", "input", "wheel"])
  addEventListener(type, leave, { capture: true, passive: true });
addEventListener("blur", leave);

export function retainReaderIntent({
  source = focused(),
  available = () => true,
  fallback = null,
} = {}) {
  const retained = intent;
  return () => {
    const at = focused();
    const withinSource =
      source === document.body ? at === document.body : source?.contains(at);
    return (
      available() &&
      retained === intent &&
      (at === document.body || at === fallback || withinSource)
    );
  };
}
