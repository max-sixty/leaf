// Arrival is not a gesture. Restored design-mode, widget, and
// reading-position state appears at rest. `motion` plays nothing before
// `data-lf-presented`, and theme transitions use the same presentation stamp.
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
// final layout. A widget whose drag moves its own nodes defers its correction.

import { pagePresented } from "./page-paint.js";

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
  if (reducedMotion() || !pagePresented()) return null;
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

// CSS owns the document-wide durations shared with stylesheet motion. Registered
// <time> values resolve variables and calculations before this read; each call reads the live
// cascade, so a revision or theme override changes CSS and Web Animations together.
const time = (property) => {
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(property)
    .trim();
  return parseFloat(value) * (value.endsWith("ms") ? 1 : 1000);
};

// A thread's arrival tint and the navigation flash on the surface it revealed.
export const flashDuration = () => time("--lf-motion-flash");
// Independently rendered carriers join the same finite agent-work arrival window.
export const agentArrivalDuration = () => time("--lf-motion-agent-arrival");

// A cue supplies only its starting tint. Its target's live CSS owns the endpoint,
// so hover, theme changes and transparent surfaces never snap back when it ends.
export function backgroundFlash(el, ms) {
  return motion(el, [{ backgroundColor: "var(--hi-tint)", offset: 0 }], ms);
}

// How long room takes to go back. Long enough that the eye can follow a paragraph's
// worth of page closing, short enough that the act still reads as having happened at
// the press: the board's own FLIP is 150ms over a card's width, and this is a taller
// distance travelled by the whole column below it. A decided suggestion's retired
// slot folds over it, and a picture's zoom (media.js) takes the same time.
export const foldDuration = () => time("--lf-motion-fold");

// Give a block's room back from its ordinary CSS shape. Native intrinsic-size
// interpolation supplies the starting height, and the other lengths start at their
// underlying stylesheet values. No measured box or temporary inline styles survive
// the effect. `display` keeps an already-retired slot drawn until its pixels finish;
// semantic retirement is still true from the first frame.
// Clip without creating a scroller, so a folding thread's title stays sticky to its list.
// Without intrinsic interpolation, which Firefox and WebKit lack, use the caller's
// immediate retirement path rather than a discrete height jump half way through an
// opacity animation.
export function foldBlock(el) {
  if (!CSS.supports("block-size", "calc-size(auto, size)")) return null;
  return motion(
    el,
    [
      {
        blockSize: "calc-size(auto, size)",
        display: "block",
        overflow: "clip",
        opacity: 1,
      },
      {
        blockSize: "0px",
        minBlockSize: "0px",
        marginBlockStart: "0px",
        marginBlockEnd: "0px",
        paddingBlockStart: "0px",
        paddingBlockEnd: "0px",
        borderBlockStartWidth: "0px",
        borderBlockEndWidth: "0px",
        display: "block",
        overflow: "clip",
        opacity: 0,
      },
    ],
    foldDuration(),
  );
}
