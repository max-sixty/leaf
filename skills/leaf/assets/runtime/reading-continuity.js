/* Whether the reader has continuously seen this document's current layout.

   A hidden document breaks continuity; keyboard blur does not, since a reader can
   still see a page beside another window. Returning reveals the current reading and
   the first refreshed reading, even though both are geometrically on screen. The
   state feed closes that return after presentation (or an unchanged freshness answer).
   A generation prevents an older request from closing a later absence. This is
   disposable browser view state, never an application fact or a logged gesture. */

let generation = 0;
let interrupted = document.visibilityState === "hidden";

export const readingIsContinuous = () =>
  document.visibilityState !== "hidden" && !interrupted;
export const readingReturn = () => (interrupted ? generation : null);

// Presentation observers use the same boundary rather than a grace period after
// visibilitychange: the first refreshed reading can take arbitrarily long to arrive.
const changed = () =>
  document.dispatchEvent(
    new CustomEvent("lf-reading-continuity", {
      detail: { continuous: readingIsContinuous() },
    }),
  );

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "hidden") {
    generation += 1;
    interrupted = true;
  }
  changed();
});

export function completeReadingReturn(returned) {
  if (
    returned === null ||
    returned !== generation ||
    document.visibilityState === "hidden" ||
    !interrupted
  )
    return;
  interrupted = false;
  changed();
}
