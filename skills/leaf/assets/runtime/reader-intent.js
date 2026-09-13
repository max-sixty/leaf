/* A delayed completion may move the reader only while the gesture that started it
   remains their latest intent. Runtime-owned repaint and focus changes do not supersede
   that intent; a later reader input or leaving the window does. */
let intent = 0;
const leave = () => intent++;
for (const type of ["pointerdown", "keydown", "input", "wheel"])
  addEventListener(type, leave, { capture: true, passive: true });
addEventListener("blur", leave);

export function retainReaderIntent() {
  const retained = intent;
  return () => retained === intent;
}
