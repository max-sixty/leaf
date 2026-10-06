/* Press and hold to read, release to press.

   Some controls show only part of their word: a reaction shows its glyph, and a diff
   file's row cuts its path short at the folders. The whole word is the control's
   tooltip, which a finger never sees, so such a control wears `HOLDS_WORD`, and a press
   held on it reads the word. The control under the pointer wears `data-lf-held-word`
   for as long as the press is held, and its surface paints the word for that state as
   it does while the keyboard stands on the control (shadow.css for a reaction, theme.css
   for a margin entry's label, the diff package's shadow.css for a file's path). Sliding
   onto a neighbouring control of the same parent reads that one instead, and the
   release presses the control it ends on, or none when it ends off them. So a tap still
   presses, and a finger that reads the wrong word slides off before letting go.

   The release presses by dispatching the control's click, counted as the pointer's
   (surfaces read the count to tell a pointer from the keyboard), and the browser's own
   click after it is swallowed: a finger held long enough to read may get none, so the
   release, not the click, is the commit. A keyboard press carries no count and passes
   untouched; the keyboard reads a word by focusing its control, which paints the same.
   Touch capture is released at the press so the slide is heard over each control. A
   finger that starts scrolling instead ends the press with `pointercancel`, which
   presses nothing; a control that should not scroll from a press says so with
   `touch-action`.

   A press or release with a modifier held is not this gesture: ctrl-click is the Mac's
   context menu, and Option/Alt aims at the item. Such a press is left to the platform
   and the control's own click handling, and a modifier arriving before the release
   takes the hold back without pressing. */

export const HOLDS_WORD = "lf-holds-word";

const HOLDER = `.${HOLDS_WORD}`;
const modified = (event) =>
  event.ctrlKey || event.metaKey || event.altKey || event.shiftKey;

export function holdToRead() {
  let hold = null;
  let released = null;
  const holderIn = (event) =>
    event
      .composedPath()
      .find((node) => node instanceof Element && node.matches(HOLDER));
  const read = (holder) => {
    if (hold.reading === holder) return;
    hold.reading?.removeAttribute("data-lf-held-word");
    hold.reading = holder;
    holder?.setAttribute("data-lf-held-word", "");
  };
  const under = (event) => {
    const holder = holderIn(event);
    return holder?.parentElement === hold.parent ? holder : null;
  };
  const end = (event, commit) => {
    if (hold?.pointerId !== event.pointerId) return;
    const holder = commit && !modified(event) ? under(event) : null;
    read(null);
    hold = null;
    if (!holder) return;
    released = holder;
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
      released = null;
      if (hold) read(null);
      hold = null;
      if (!event.isPrimary || event.button !== 0 || modified(event)) return;
      const holder = holderIn(event);
      if (!holder || holder.matches(":disabled, [aria-disabled='true']")) return;
      const origin = event.composedPath()[0];
      if (origin.hasPointerCapture?.(event.pointerId))
        origin.releasePointerCapture(event.pointerId);
      hold = { pointerId: event.pointerId, parent: holder.parentElement, reading: null };
      read(holder);
    },
    { capture: true },
  );
  document.addEventListener(
    "pointermove",
    (event) => {
      if (hold?.pointerId === event.pointerId) read(under(event));
    },
    { capture: true },
  );
  document.addEventListener("pointerup", (event) => end(event, true), {
    capture: true,
  });
  document.addEventListener("pointercancel", (event) => end(event, false), {
    capture: true,
  });
  document.addEventListener(
    "click",
    (event) => {
      if (!released || !event.isTrusted || !event.detail || !holderIn(event)) return;
      released = null;
      event.preventDefault();
      event.stopImmediatePropagation();
    },
    { capture: true },
  );
  // A held control would offer the platform's own long-press menu instead.
  document.addEventListener(
    "contextmenu",
    (event) => {
      if (hold) event.preventDefault();
    },
    { capture: true },
  );
}
