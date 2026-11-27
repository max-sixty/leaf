// Compiled from motion.ts by build/typescript.mjs; edit that file.
// Arrival is not a gesture. Restored design-mode, widget, and
// reading-position state appears at rest. `motion` plays nothing before
// `data-lf-presented`, and theme transitions use the same presentation stamp.
//
// After presentation, changes that remove a visible unit use a short fold. The semantic
// state is true at the start of the fold, while the old pixels collapse so the eye can
// follow them. Reconciliation, not the originating press, owns the fold because the same
// change can arrive from another tab or the agent. A resolved thread leaves the
// open-thread vocabulary at once, folds in place, then moves under the resolved
// disclosure. A message leaving a thread, as a reply the log refuses does, folds where
// it stood (records/thread/transcript.js), and the thread gives its room back as it folds
// (records/thread/reply-continuity.js).
//
// Projection composes the complete final state before rendering. Ordered containers
// measure once around that composition and show one FLIP from the current layout to the
// final layout. A widget whose drag moves its own nodes defers its correction.

import { pagePresented } from "../base/page-paint.js";
import { motionTime } from "../lib/motion-timing.js";

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

// Whether motion plays now, which `playMotion` asks before every animation. First replay
// happens behind the presentation boundary. Its state should be the first frame the
// user sees, not a motion from authored state they never saw; it collapses exactly as
// reduced motion does. This one shared check reaches folds and FLIP alike without a
// widget learning whether the page has been presented. A caller that must choose
// before it animates, such as one keeping an old view drawn only while it fades, asks
// this too.
export const motionPlays = () => !reducedMotion() && pagePresented();

// Web-Animations motion goes through here, so a user who asked for stillness is
// answered in one place rather than by each widget remembering the check: null under
// reduce, and a caller treats "no animation" and "animation finished" as the same
// state. Every motion this module plays shares one held-end-frame contract. A duration
// a caller passes in is still a number this module has no reason for; see browser/AGENTS.md's
// "Motion is brief and keeps the user oriented". `motion` is the packages' door, and its signature is part of what an
// installed package calls, so it stays as pages know it.
export const motion = (el, keyframes, ms, pseudoElement = null) =>
  playMotion(el, keyframes, { duration: ms, pseudoElement });

// The same door with the runtime's own surfaces' further timing: the one ease unless
// the caller names its surface's curve (`easing`, read with lib/motion-timing.js's
// `motionEasing`).
export function playMotion(
  el,
  keyframes,
  { duration, easing = "ease", pseudoElement = null },
) {
  if (!motionPlays()) return null;
  const played = el.animate(keyframes, {
    duration,
    pseudoElement,
    easing,
    fill: "both",
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

// A cue supplies only its starting tint. Its target's live CSS owns the endpoint,
// so hover, theme changes and transparent surfaces never snap back when it ends. A box
// drawn inside the element that paints a background of its own, such as an option's
// row, would cover the element's tint, so it takes the tint too, and the whole element
// reads as one tinted box. Theirs end with the element's, which is the one returned.
// A flash lasts as long as the theme sets (`--lf-motion-flash`), whoever asks for it,
// so the page marks each arrival and change alike.
export function backgroundFlash(el) {
  const ms = motionTime("--lf-motion-flash");
  const tint = (box) =>
    motion(box, [{ backgroundColor: "var(--lf-hi-tint)", offset: 0 }], ms);
  const own = tint(el);
  if (!own) return own;
  const grounds = [...el.querySelectorAll("*")]
    .filter(
      (box) =>
        box.checkVisibility() &&
        getComputedStyle(box).backgroundColor !== "rgba(0, 0, 0, 0)",
    )
    .map(tint);
  own.finished.then(
    () => grounds.forEach((one) => one?.finish()),
    () => grounds.forEach((one) => one?.cancel()),
  );
  return own;
}

// Give a block's room back from its ordinary CSS shape, over the time room takes to
// go back (`--lf-motion-fold`, styles/tokens.css). Native intrinsic-size
// interpolation supplies the starting height, and the other lengths start at their
// underlying stylesheet values. No measured box or temporary inline styles survive
// the effect. `display` keeps an already-retired slot drawn until its pixels finish;
// semantic retirement is still true from the first frame.
// Clip without creating a scroller, so a folding thread's title stays sticky to its list.
// Where intrinsic interpolation is missing (Firefox), `auto` would jump
// discretely half way. There the effect first holds the block at `auto`, reads that
// height and restarts from it in pixels, all before the next frame. The pixels live
// only in the effect's keyframes, so content that changes mid-fold keeps the starting
// height it was read with. Firefox cannot animate `display` either, so an
// already-retired slot is drawn by an inline `display` that the effect's end or
// cancellation removes; the retirement rule then hides it again.
// When retiring also replaces adjacent UI, the container's prior allocation supplies
// the starting room: its final composition may replace an editor with a disclosure.
// Account for that difference in the retiring block's size, so the first
// frame preserves the container's old size and one fold gives back the net room.
// Unlike trailing margins, this room cannot collapse against a live neighbor's gap.
// The caller measures only the container before composing; this owner reads the new
// allocation, so consumers share the geometry rule.
export function foldBlock(el, allocation = null) {
  const adjustment = allocation
    ? allocation.priorSize - allocation.container.getBoundingClientRect().height
    : 0;
  const native = CSS.supports("block-size", "calc-size(auto, size)");
  const frames = (blockSize) => [
    { blockSize, display: "block", overflow: "clip", opacity: 1 },
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
  ];
  const played = motion(
    el,
    frames(native ? `calc-size(auto, size + ${adjustment}px)` : "auto"),
    motionTime("--lf-motion-fold"),
  );
  if (!played || native) return played;
  if (getComputedStyle(el).display === "none") {
    el.style.display = "block";
    const release = () => el.style.removeProperty("display");
    played.finished.then(release, release);
  }
  const size = parseFloat(getComputedStyle(el).blockSize) + adjustment;
  const effect = played.effect;
  if (effect instanceof KeyframeEffect) effect.setKeyframes(frames(`${size}px`));
  return played;
}
