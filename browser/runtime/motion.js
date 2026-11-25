// Arrival is not a gesture. Restored design-mode, widget, and
// reading-position state appears at rest. `playMotion` (lib/motion.js) plays nothing
// before `data-lf-presented`, and theme transitions use the same presentation stamp.
//
// After presentation, changes that remove a visible unit use a short fold. The semantic
// state is true at the start of the fold, while the old pixels collapse so the eye can
// follow them. Reconciliation, not the originating press, owns the fold because the same
// change can arrive from another tab or the agent. A resolved thread leaves the
// open-thread vocabulary at once, folds in place, then moves under the resolved
// disclosure. A message leaving a thread, as a reply the log refuses does, folds where
// it stood (thread/transcript.js), and the thread gives its room back as it folds
// (thread/reply-continuity.js).
//
// Projection composes the complete final state before rendering. Ordered containers
// measure once around that composition and show one FLIP from the current layout to the
// final layout. A widget whose drag moves its own nodes defers its correction.

import { motionTime } from "./lib/motion-timing.js";
import { playMotion } from "./lib/motion.js";

// Smooth scrolls driven from JS follow the user's motion preference, as the theme's
// reduced-motion guard covers CSS animation and transitions; Web-Animations moves go
// through the library's `playMotion` (lib/motion.js), which answers it for every caller.
const preference = matchMedia("(prefers-reduced-motion: reduce)");
export const scrollBehavior = () => (preference.matches ? "instant" : "smooth");
/** @param {(reduced: boolean) => void} listener */
export function onMotionPreferenceChange(listener) {
  const changed = (/** @type {MediaQueryListEvent} */ event) => listener(event.matches);
  preference.addEventListener("change", changed);
  return () => preference.removeEventListener("change", changed);
}

// A cue supplies only its starting tint. Its target's live CSS owns the endpoint,
// so hover, theme changes and transparent surfaces never snap back when it ends. A box
// drawn inside the element that paints a background of its own, such as an option's
// row, would cover the element's tint, so it takes the tint too, and the whole element
// reads as one tinted box. Theirs end with the element's, which is the one returned.
// A flash lasts as long as the theme sets (`--lf-motion-flash`), whoever asks for it,
// so the page marks each arrival and change alike.
/** @param {Element} el */
export function backgroundFlash(el) {
  const ms = motionTime("--lf-motion-flash");
  /** @param {Element} box */
  const tint = (box) =>
    playMotion(box, [{ backgroundColor: "var(--lf-hi-tint)", offset: 0 }], {
      duration: ms,
    });
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
/** @param {HTMLElement} el @param {{container: Element, priorSize: number} | null} [allocation] */
export function foldBlock(el, allocation = null) {
  const adjustment = allocation
    ? allocation.priorSize - allocation.container.getBoundingClientRect().height
    : 0;
  const native = CSS.supports("block-size", "calc-size(auto, size)");
  const frames = (/** @type {string} */ blockSize) => [
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
  const played = playMotion(
    el,
    frames(native ? `calc-size(auto, size + ${adjustment}px)` : "auto"),
    { duration: motionTime("--lf-motion-fold") },
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
