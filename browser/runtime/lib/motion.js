// Motion a script plays: Web Animations that answer the user's motion preference and
// the stylesheet's hold on a page not yet presented (`motion`, `playMotion`,
// `motionPlays`), the times and curves the stylesheet sets for them (`motionTime`,
// `motionEasing`), the tint that marks an arrival or a change (`backgroundFlash`) and
// the fold that gives a block's room back (`foldBlock`).
//
// A page's arrival is not a gesture, so state restored at load appears at rest: nothing
// here plays while the page's stylesheet says the page is not yet presented
// (`motionPlays`).
//
// A change that removes a visible unit folds it (`foldBlock`). The change is true from
// the start of the fold, while the old pixels collapse so the eye can follow them. The
// code that reconciles state plays the fold, not the press that caused the change,
// since the same change can arrive from another tab or from an agent.
//
// A caller that moves boxes composes the complete final state, measures once around
// that composition and plays one FLIP from the current layout to the final one. A
// widget whose drag moves its own nodes defers its correction.

// The theme's reduced-motion guard covers CSS animation and transitions; motion
// driven from JS — smooth scrolls here, Web-Animations moves in widgets — checks
// this instead.
const preference = matchMedia("(prefers-reduced-motion: reduce)");
/** @type {Set<Animation>} */
const active = new Set();
export const reducedMotion = () => preference.matches;
export const scrollBehavior = () => (preference.matches ? "instant" : "smooth");
/** @param {(reduced: boolean) => void} listener */
export function onMotionPreferenceChange(listener) {
  const changed = (/** @type {MediaQueryListEvent} */ event) => listener(event.matches);
  preference.addEventListener("change", changed);
  return () => preference.removeEventListener("change", changed);
}
preference.addEventListener("change", (event) => {
  // Preference changes apply to motion already under the user as well as the next
  // gesture. Finishing reaches each caller's ordinary cleanup path; cancelling here
  // would reject `finished` and strand folds whose end state is installed there.
  if (event.matches) for (const played of [...active]) played.finish();
});

// A custom property's value as `on` inherits or declares it. Each call reads the live
// cascade.
/** @param {string} property @param {Element} on */
const token = (property, on) => getComputedStyle(on).getPropertyValue(property).trim();

// Whether motion plays now, which `playMotion` asks before every animation: the user
// has not asked for stillness, and the page's stylesheet does not hold motion. A page
// states the hold on its `body` as `--lf-before-presentation: 1`. Leaf's base.css
// states it on a screen while a page its runtime is starting has not presented, and
// stops its transitions by the same property, so a stylesheet's motion and a script's
// start together. A page's saved state is first replayed during that hold. The result
// should be the first frame the user sees, not a motion from authored state they never
// saw, so each motion collapses exactly as it does under reduced motion. This one
// shared check reaches folds and FLIP alike without a widget learning whether the page
// has been presented.
//
// The property is read on `body` rather than on the element to animate, which a caller
// may not have placed yet. A page that states no hold holds nothing: a document without
// Leaf's sheet, and on Leaf a page in print, a page that could not start, and a page
// whose sheet did not load, where a time read with `motionTime` is no number either.
//
// A caller that must choose before it animates, such as one keeping an old view drawn
// only while it fades, asks this too.
export const motionPlays = () =>
  !reducedMotion() && token("--lf-before-presentation", document.body) !== "1";

// Web-Animations motion goes through here, so a user who asked for stillness is
// answered in one place rather than by each widget remembering the check: null where
// motion does not play (`motionPlays`), and a caller treats "no animation" and
// "animation finished" as the same state. Where a caller must branch on the preference
// itself, as for the `behavior` of a smooth `scrollTo`, it reads `reducedMotion` or
// `scrollBehavior`. Every motion this module plays shares one held-end-frame contract.
// A duration a caller passes in is still a number this module has no reason for:
// motion the user waits on stays brief, and helps the eye follow a box from where it
// was to where it is. `pseudoElement` names a pseudo-element of `el` to animate, as a
// disclosure's `::details-content`.
/** @param {Element} el @param {Keyframe[] | PropertyIndexedKeyframes} keyframes @param {number} ms @param {string | null} [pseudoElement] */
export const motion = (el, keyframes, ms, pseudoElement = null) =>
  playMotion(el, keyframes, { duration: ms, pseudoElement });

// The same door with a surface's further timing: the one ease unless
// the caller names its surface's curve (`easing`, read with `motionEasing`), and a
// `delay` that holds the first frame until the motion starts, so a part fading in after
// another fades out stays unseen meanwhile. That is the backward half of the fill,
// which no undelayed motion reaches.
/** @param {Element} el @param {Keyframe[] | PropertyIndexedKeyframes} keyframes
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

// CSS owns the durations and curves shared with stylesheet motion: the document-wide
// ones on the root (styles/tokens.css says what each is for), and a surface's own on
// that surface, as the floating panel's are. A caller names the property it reads.
// Registered <time> values resolve variables and calculations before this read; each
// call reads the live cascade, so a revision or theme override changes CSS and Web
// Animations together.
// A `--lf-motion-*` duration, in milliseconds, as `on` inherits or declares it.
/** @param {string} property @param {Element} [on] */
export const motionTime = (property, on = document.documentElement) => {
  const value = token(property, on);
  return parseFloat(value) * (value.endsWith("ms") ? 1 : 1000);
};
// A `--lf-motion-*` curve, as Web Animations takes it.
/** @param {string} property @param {Element} [on] */
export const motionEasing = (property, on = document.documentElement) =>
  token(property, on);

// A brief tint that fades to the element's own background, from the theme's highlight
// (`--lf-hi-tint`). A cue supplies only its starting tint. Its target's live CSS owns
// the endpoint, so hover, theme changes and transparent surfaces never snap back when
// it ends. A box drawn inside the element that paints a background of its own, such as
// an option's row, would cover the element's tint, so it takes the tint too, and the
// whole element reads as one tinted box. Theirs end with the element's, which is the
// one returned. A flash lasts as long as the theme sets (`--lf-motion-flash`), whoever
// asks for it, so the page marks each arrival and change alike.
/** @param {Element} el */
export function backgroundFlash(el) {
  const ms = motionTime("--lf-motion-flash");
  /** @param {Element} box */
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
// go back (`--lf-motion-fold`). Native intrinsic-size
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
