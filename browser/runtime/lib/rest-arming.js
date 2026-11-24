/* When a control standing over words the user types takes presses: once the pointer has
   rested on it, so a press aimed at the words beneath reaches them. A composer's Send over
   its last line and a draft's toolbar over its first both stand there. The owner hands
   each pointer move and leave over the box to `move`, and calls `reset` as the user types
   or presses the words, so the control waits for the pointer to come back and rest again.

   Where the pointer is decides, read from the coordinates of each move and leave alike
   rather than from which element it entered or left: a leave can come with the pointer
   still over the control, as a Firefox process whose mouse tracking has gone wrong sends
   one after every move until it restarts, and a leave taken as the pointer going would
   disarm the control while the pointer rests there. A finger arms nothing, since it rests
   nowhere; its owner stands the control apart from the words instead.

   ```js
   const arming = restArming(() => send, {
     point: () => box.setAttribute("data-pointed", ""),
     arm: () => box.setAttribute("data-armed", ""),
     unpoint: () => box.removeAttribute("data-pointed"),
   });
   box.addEventListener("pointermove", arming.move);
   box.addEventListener("pointerleave", arming.move);
   field.addEventListener("input", arming.reset);
   ``` */

// How long the pointer rests on the control before it takes presses: longer than a
// press aimed at the words' end takes to land.
const DWELL = 150;

/**
 * @param {() => Element | null | undefined} control
 * @param {{point?: () => void, arm: () => void, unpoint?: () => void}} on `point` as the
 *   pointer comes onto the control, `arm` once it has rested there, `unpoint` as it
 *   leaves or the owner resets
 */
export function restArming(control, { point, arm, unpoint }) {
  let dwell = 0;
  let pointed = false;
  const reset = () => {
    clearTimeout(dwell);
    dwell = 0;
    pointed = false;
    unpoint?.();
  };
  /** @param {PointerEvent} event */
  const move = (event) => {
    if (event.pointerType === "touch") return;
    const at = control()?.getBoundingClientRect();
    const on =
      at &&
      event.clientX >= at.left &&
      event.clientX < at.right &&
      event.clientY >= at.top &&
      event.clientY < at.bottom;
    if (!on) return reset();
    if (pointed) return;
    pointed = true;
    point?.();
    dwell = setTimeout(() => {
      dwell = 0;
      arm();
    }, DWELL);
  };
  return { move, reset };
}
