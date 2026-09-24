// Arrival is not a gesture. Restored panel, tray, drawn-width, design-mode, widget, and
// reading-position state appears at rest. `motion` finishes Web Animations immediately
// before `data-lf-presented` and while an already-standing state is being restored into
// replacement markup; theme transitions use the same presentation stamp.
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
  // Preference changes apply to motion already under the user as well as the next
  // gesture. Finishing reaches each caller's ordinary cleanup path; cancelling here
  // would reject `finished` and strand folds whose end state is installed there.
  if (event.matches) for (const played of [...active]) played.finish();
});

// Web-Animations motion goes through here, so a user who asked for stillness is
// answered in one place rather than by each widget remembering the check: null under
// reduce, and a caller treats "no animation" and "animation finished" as the same
// state. Every motion this module plays shares one ease and one held-end-frame
// contract. A duration a caller passes in is still a number this module has no reason
// for; see AGENTS.md's "Motion".
export function motion(el, keyframes, ms) {
  // First replay happens behind the presentation boundary. Its state should be the
  // first frame the user sees, not a motion from authored state they never saw; it
  // collapses exactly as reduced motion does. This one shared check reaches folds and
  // FLIP alike without a widget learning whether the page has been presented.
  if (
    reducedMotion() ||
    runtime.restoringState ||
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
  // unanimated box before the caller removed, hid or restated it. A presentation offset
  // such as a FLIP needs no cleanup because its underlying placement already is its last
  // frame; it still leaves no filled animation behind.
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
// resolved thread's place in the list are both room the user watches come back —
// and two numbers would be that reason written down twice, free to disagree.
export const FOLD_MS = 220;

// An edge-held auxiliary surface slides in from the edge it is held to and back out to it:
// the trays from the left, the thread panel from the right. It stands over the page, so the
// slide moves only the surface. Out is quicker than in, since a surface going away is
// nothing the user has to follow. A new slide replaces one still running on the same
// surface and starts from where that one had carried it, so a reopen mid-exit comes
// straight back rather than finishing the exit first; the replaced slide's `finished`
// rejects, which is how its caller knows not to hide.
// A slide moves what the surface shows without a scroll, resize or mutation, so its end
// is announced as `SLIDE_END` on the surface for readers of what is on screen.
export const SLIDE_END = "lf-slide-end";
const SLIDE_IN_MS = 200;
const SLIDE_OUT_MS = 160;
const slides = new WeakMap();
export function slide(el, side, direction) {
  const running = slides.get(el);
  const at = running && { transform: getComputedStyle(el).transform };
  running?.cancel();
  const away = { transform: `translateX(${side === "left" ? "-100%" : "100%"})` };
  const home = { transform: "translateX(0)" };
  const played =
    direction === "in"
      ? motion(el, [at ?? away, home], SLIDE_IN_MS)
      : motion(el, [at ?? home, away], SLIDE_OUT_MS);
  if (!played) return null;
  slides.set(el, played);
  played.finished.then(
    () => {
      slides.delete(el);
      el.dispatchEvent(new Event(SLIDE_END, { bubbles: true, composed: true }));
    },
    () => {},
  );
  return played;
}
