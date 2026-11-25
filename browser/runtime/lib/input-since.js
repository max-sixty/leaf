/* Whether the user has given this document any input since a moment: a key, a press, a
   wheel or a touch. Work a gesture starts that has to wait, such as a step that opens
   a file before landing in it, asks before it moves focus or scroll, so a newer act of
   the user's wins over the older one's landing:

       const intended = noInputSince();
       await open(file);
       if (intended()) land(file);

   Called while the starting gesture's own event is dispatched, it hears none of that
   event, since the window's capture phase has passed. Input inside an embedded
   document reaches this one as no event. */
const INPUTS = ["keydown", "pointerdown", "wheel", "touchstart"];

/** @returns {() => boolean} */
export function noInputSince() {
  let none = true;
  const heard = () => {
    none = false;
    for (const type of INPUTS) window.removeEventListener(type, heard, true);
  };
  for (const type of INPUTS)
    window.addEventListener(type, heard, { capture: true, passive: true });
  return () => none;
}
