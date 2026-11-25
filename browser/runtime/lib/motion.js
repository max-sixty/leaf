/* Motion a script plays with the Web Animations API, on the terms the page's stylesheet
   plays its own: nothing for a user who asked for less motion, and nothing before the
   page first presents (`body[data-lf-presented]`, which Leaf stamps), since arrival is
   not a gesture and restored state appears at rest. In a document Leaf did not compose
   nothing stamps it, so nothing plays. A caller treats "no animation" and "animation
   finished" as the same state.

   Every motion holds its last frame until the caller's `finished.then(cleanup)` has
   made that frame true in the DOM or CSS, then lets the effect go, so no filled
   animation outlives it. A user who turns reduced motion on has every motion still
   running finished at once, which reaches each caller's ordinary cleanup; cancelling
   would reject `finished` and strand a fold whose end state is installed there. A
   duration a caller passes is still a number this module has no reason for; see
   browser/AGENTS.md's "Motion is brief and keeps the user oriented". */

const preference = matchMedia("(prefers-reduced-motion: reduce)");
/** @type {Set<Animation>} */
const active = new Set();
preference.addEventListener("change", (event) => {
  if (event.matches) for (const played of [...active]) played.finish();
});

/** Whether the user asked for less motion. */
export const reducedMotion = () => preference.matches;

/** Whether motion plays now, which `playMotion` asks before every animation, and a caller
 * that must choose before it animates, such as one keeping an old view drawn only while
 * it fades, asks too. */
export const motionPlays = () =>
  !preference.matches && document.body?.hasAttribute("data-lf-presented") === true;

/** Play `keyframes` on `el`, or nothing where motion doesn't play: the one ease unless
 * the caller names its surface's curve (`easing`, read with motion-timing.js's
 * `motionEasing`), and a `delay` that holds the first frame until the motion starts.
 * @param {Element} el @param {Keyframe[] | PropertyIndexedKeyframes} keyframes
 * @param {{duration: number, easing?: string, delay?: number, pseudoElement?: string | null}} options */
export function playMotion(
  el,
  keyframes,
  { duration, easing = "ease", delay = 0, pseudoElement = null },
) {
  if (!motionPlays()) return null;
  const played = el.animate(keyframes, {
    duration,
    delay,
    pseudoElement,
    easing,
    fill: "both",
  });
  active.add(played);
  // The release waits one microtask more than the caller's own `finished.then`, which
  // was registered after this one, so the caller's cleanup lands before the effect
  // lets go. A presentation offset such as a FLIP needs no cleanup, since its underlying
  // placement already is its last frame. A cancel is already the release, and the
  // rejection arm consumes it so an interrupted move reports nothing unhandled.
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
