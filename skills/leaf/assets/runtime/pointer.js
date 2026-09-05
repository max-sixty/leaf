/* The one unrounded pointer position shared by hit-test consumers. */
let x = -1;
let y = -1;

// Read pointer events rather than legacy mouse events, whose client coordinates are
// rounded away from the point the browser hit-tested. A snapshot keeps consumers from
// becoming another writer of the position they read.
const remember = (ev) => {
  x = ev.clientX;
  y = ev.clientY;
};
document.addEventListener("pointermove", remember, { capture: true });
// A finger can arrive already down, with no preceding pointermove. The press is its
// position too, and for a tap it is the only statement of it.
document.addEventListener("pointerdown", remember, { capture: true });

export const pointerAt = () => ({ x, y });
