// Arrival is not a gesture. Restored panel, tray, drawn-width, design-mode, widget, and
// reading-position state appears at rest. `motion` finishes Web Animations immediately
// before `data-lf-presented`; theme transitions use the same presentation stamp.
//
// After presentation, changes that remove a visible unit use a short fold. The semantic
// state is true at the start of the fold, while the old pixels collapse so the eye can
// follow them. Reconciliation, not the originating press, owns the fold because the same
// change can arrive from another tab or the agent. A resolved thread leaves the
// open-thread vocabulary at once, folds in place, then moves under the resolved
// disclosure.
//
// Projection composes the complete final state before rendering. Ordered containers
// measure once around that composition and show one FLIP from the current layout to the
// final layout. A live drag defers the whole correction.

import { runtime } from "./context.js";
import { PAGE_PAINT_ATTRIBUTE } from "./presentation.js";

// The theme's reduced-motion guard covers CSS animation and transitions; motion
// driven from JS — smooth scrolls here, Web-Animations moves in widgets — checks
// this instead.
const preference = matchMedia("(prefers-reduced-motion: reduce)");
const active = new Set();
export const reducedMotion = () => preference.matches;
export const scrollBehavior = () => (preference.matches ? "instant" : "smooth");
export function onMotionPreferenceChange(listener) {
  const changed = (event) => listener(event.matches);
  preference.addEventListener("change", changed);
  return () => preference.removeEventListener("change", changed);
}
preference.addEventListener("change", (event) => {
  // Preference changes apply to motion already under the reader as well as the next
  // gesture. Finishing reaches each caller's ordinary cleanup path; cancelling here
  // would reject `finished` and strand folds whose end state is installed there.
  if (event.matches) for (const played of [...active]) played.finish();
});

// Web-Animations motion goes through here, so a reader who asked for stillness is
// answered in one place rather than by each widget remembering the check: null under
// reduce, and a caller treats "no animation" and "animation finished" as the same
// state. The board's FLIP, the shell carry, and the folds (FOLD_MS) are the motions the
// product makes; they share one ease and one held-end-frame contract.
export function motion(el, keyframes, ms) {
  // First replay happens behind the presentation boundary. Its state should be the
  // first frame the reader sees, not a motion from authored state they never saw; it
  // collapses exactly as reduced motion does. This one shared check reaches folds and
  // FLIP alike without a widget learning whether the page has been presented.
  if (
    reducedMotion() ||
    runtime.projectingState ||
    !document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented)
  )
    return null;
  const played = el.animate(keyframes, {
    duration: ms,
    easing: "ease",
    fill: "forwards",
  });
  active.add(played);
  // Hold the last frame until the caller's direct `finished.then(cleanup)` has made
  // that frame true in DOM/CSS, then release the effect. The extra microtask is the
  // ordering: our reaction was registered first, so cancelling in it would expose the
  // unanimated box before the caller removed, hid or restated it. Presentation offsets
  // such as a FLIP or shell carry need no cleanup because their underlying placement
  // already is their last frame; they still leave no filled animation behind.
  // Cancellation is already the release, and the rejection arm consumes it so an
  // interrupted move reports no unhandled promise.
  played.finished.then(
    () =>
      queueMicrotask(() => {
        active.delete(played);
        played.cancel();
      }),
    () => active.delete(played),
  );
  return played;
}

// How long room takes to go back. Long enough that the eye can follow a paragraph's
// worth of page closing, short enough that the act still reads as having happened at
// the press: the board's own FLIP is 150ms over a card's width, and this is a taller
// distance travelled by the whole column below it. One number, because the product
// makes this motion twice for one reason — a decided suggestion's retired slot and a
// resolved thread's place in the list are both room the reader watches come back —
// and two numbers would be that reason written down twice, free to disagree.
export const FOLD_MS = 220;
