/* The one unrounded pointer position shared by hit-test consumers. */
let x = -1;
let y = -1;
let when = 0;

// Read pointer events rather than legacy mouse events, whose client coordinates are
// rounded away from the point the browser hit-tested. A snapshot keeps consumers from
// becoming another writer of the position they read.
const remember = (ev) => {
  x = ev.clientX;
  y = ev.clientY;
  when = ev.timeStamp;
};
document.addEventListener("pointermove", remember, { capture: true });
// A finger can arrive already down, with no preceding pointermove. The press is its
// position too, and for a tap it is the only statement of it.
document.addEventListener("pointerdown", remember, { capture: true });
document.addEventListener("wheel", remember, { capture: true, passive: true });

export const pointerAt = () => ({ x, y });
export const pointerWhen = () => when;

// Whether a press event was made by the keyboard rather than by the pointer, asked of
// the event itself. A `click` with no click count is Enter or Space on the control, or
// the page's own `element.click()` standing for one — a keyboard route — while every
// mousedown, mouseup, dblclick and counted click follows a physical press. A mode that
// captures presses across the whole document has to let the keyboard one through: it
// belongs to the control it is on, whatever the pointer did a moment ago, and a mode
// that eats it makes the control unreachable from the keyboard for as long as the claim
// stands.
export const pressIsKeyboardActivation = (event) =>
  event.type === "click" && !event.detail;

// An automatic revision activation replaces the document, not the user's pointer.
// New input wins over a handoff captured by the departing document.
export function restorePointer(point) {
  if (x !== -1 || y !== -1 || !Number.isFinite(point?.x) || !Number.isFinite(point?.y))
    return;
  x = point.x;
  y = point.y;
}
