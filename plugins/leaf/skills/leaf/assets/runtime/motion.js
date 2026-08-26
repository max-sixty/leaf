import { runtime } from "./context.js";
import { PAGE_PAINT_ATTRIBUTE } from "./presentation.js";

// The theme's reduced-motion guard covers CSS animation and transitions; motion
// driven from JS — smooth scrolls here, Web-Animations moves in widgets — checks
// this instead.
export const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
export const SCROLL = REDUCED ? "instant" : "smooth";

// Web-Animations motion goes through here, so a reader who asked for stillness is
// answered in one place rather than by each widget remembering the check: null under
// reduce, and a caller treats "no animation" and "animation finished" as the same
// state. The board's FLIP and the folds (FOLD_MS) are the motions the product makes;
// they share one ease and one held-end-frame contract.
export function motion(el, keyframes, ms) {
  // First replay happens behind the presentation boundary. Its state should be the
  // first frame the reader sees, not a motion from authored state they never saw; it
  // collapses exactly as reduced motion does. This one shared check reaches folds and
  // FLIP alike without a widget learning whether the page has been presented.
  if (
    REDUCED ||
    runtime.projectingState ||
    !document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented)
  )
    return null;
  const played = el.animate(keyframes, {
    duration: ms,
    easing: "ease",
    fill: "forwards",
  });
  // Hold the last frame until the caller's direct `finished.then(cleanup)` has made
  // that frame true in DOM/CSS, then release the effect. The extra microtask is the
  // ordering: our reaction was registered first, so cancelling in it would expose the
  // unanimated box before the caller removed, hid or restated it. A FLIP has no cleanup
  // because its underlying placement already is its last frame; it still leaves no
  // filled animation behind. Cancellation is already the release, and the rejection
  // arm consumes it so an interrupted move reports no unhandled promise.
  played.finished.then(
    () => queueMicrotask(() => played.cancel()),
    () => {},
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
