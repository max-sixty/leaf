/* Press and hold to read, release to press.

   Some controls show only part of their word: a reaction shows its glyph, a margin
   entry its icon (its label and status are its tooltip), and a diff file's row
   narrower than its path cuts it short, from the folders. The whole word is the
   control's tooltip, which a finger never sees, so such a control wears `HOLDS_WORD`,
   and a press held on it reads the word. The control under the pointer wears
   `data-lf-held-word` for as long as the press is held, and its surface paints the word
   for that state as it does while the keyboard stands on the control (shadow.css for a
   reaction, base.css for a margin entry's label, the diff package's shadow.css for a
   file's path, only while the row cuts it short; a row showing its whole path paints
   nothing and keeps the gesture). Sliding onto a neighbouring control of the same parent
   reads that one instead, and the release presses the control it ends on, or none when
   it ends off them. So a tap still presses, and a finger that reads the wrong word
   slides off before letting go.

   The release presses by dispatching the control's click, counted as the pointer's
   (surfaces read the count to tell a pointer from the keyboard), and the release claims
   the browser's own click after it (`claimReleaseClick`, focus.js): a finger held
   long enough to read may get none, so the release, not the click, is the commit, and
   the press may have put something else under the finger, such as the thread a margin
   entry opens. The release first focuses the control
   without a ring, as a pointer's press does. A finger's press is focused only by the
   browser's events after the release, so without this what the press opens is laid
   out with nothing marking where the user is: a margin pin unfolding lost the seat it
   keeps while focused (margin-layout.js, `HELD`). A keyboard press carries no count
   and passes untouched; the keyboard reads a word by focusing its control, which
   paints the same.
   Touch capture is released at the press so the slide is heard over each control. A
   finger that starts scrolling instead ends the press with `pointercancel`, which
   presses nothing; a control that should not scroll from a press says so with
   `touch-action`.

   A press or release with a modifier held is not this gesture: ctrl-click is the Mac's
   context menu, and Option/Alt aims at the item. Such a press is left to the platform
   and the control's own click handling. A modifier arriving before the release ends the
   hold without this gesture's press and leaves the press to the browser's own click. */
import { claimReleaseClick, nativeFocusTarget } from "./focus.js";
import { plainPress } from "./pointer.js";
import { isElement } from "./shadow-tree.js";

export const HOLDS_WORD = "lf-holds-word";

const HOLDER = `.${HOLDS_WORD}`;

export function holdToRead() {
  /** @typedef {{pointerId: number, parent: Element | null, reading: Element | null}} HeldWord */
  /** @type {HeldWord | null} */
  let hold = null;
  /** @param {Event} event */
  const holderIn = (event) => {
    for (const node of event.composedPath())
      if (isElement(node) && node.matches(HOLDER)) return node;
    return null;
  };
  /** @param {HeldWord} held @param {Element | null} holder */
  const read = (held, holder) => {
    if (held.reading === holder) return;
    held.reading?.removeAttribute("data-lf-held-word");
    held.reading = holder;
    holder?.setAttribute("data-lf-held-word", "");
  };
  /** @param {HeldWord} held @param {Event} event */
  const under = (held, event) => {
    const holder = holderIn(event);
    return holder?.parentElement === held.parent ? holder : null;
  };
  /** @param {PointerEvent} event @param {boolean} commit */
  const end = (event, commit) => {
    if (!hold || hold.pointerId !== event.pointerId) return;
    const holder = commit && plainPress(event) ? under(hold, event) : null;
    read(hold, null);
    hold = null;
    if (!holder) return;
    claimReleaseClick();
    nativeFocusTarget(holder).focus({ preventScroll: true, focusVisible: false });
    holder.dispatchEvent(
      new MouseEvent("click", {
        bubbles: true,
        cancelable: true,
        composed: true,
        detail: 1,
        clientX: event.clientX,
        clientY: event.clientY,
      }),
    );
  };
  document.addEventListener(
    "pointerdown",
    (event) => {
      if (hold) read(hold, null);
      hold = null;
      if (!event.isPrimary || !plainPress(event)) return;
      const holder = holderIn(event);
      if (!holder || holder.matches(":disabled, [aria-disabled='true']")) return;
      const origin = event.composedPath()[0];
      if (isElement(origin) && origin.hasPointerCapture(event.pointerId))
        origin.releasePointerCapture(event.pointerId);
      hold = {
        pointerId: event.pointerId,
        parent: holder.parentElement,
        reading: null,
      };
      read(hold, holder);
    },
    { capture: true },
  );
  document.addEventListener(
    "pointermove",
    (event) => {
      if (hold?.pointerId === event.pointerId) read(hold, under(hold, event));
    },
    { capture: true },
  );
  document.addEventListener("pointerup", (event) => end(event, true), {
    capture: true,
  });
  document.addEventListener("pointercancel", (event) => end(event, false), {
    capture: true,
  });
  // A held control would offer the platform's own long-press menu instead.
  document.addEventListener(
    "contextmenu",
    (event) => {
      if (hold) event.preventDefault();
    },
    { capture: true },
  );
}
