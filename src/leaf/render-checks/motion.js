/* Motion the page keeps for a reader who asked for less.
 *
 * Leaf stops its own stylesheets' motion under `prefers-reduced-motion` and leaves the
 * page's to the page (state.css), so a page that ignores the preference animates
 * anyway. The render gate sets the preference and asks this which animations on the
 * page's content are still running: an endless spinner or pulse, or a long animation
 * not yet done. Leaf's own interface is held out, since its motion is Leaf's to stop.
 * A transition runs only while a property changes, so a settled page shows none; one
 * the page starts on a gesture is outside this reading. */
import { at } from "./locate.js";

export function unreducedMotion() {
  const found = new Map();
  for (const animation of document.getAnimations()) {
    const { effect } = animation;
    const target = effect instanceof KeyframeEffect ? effect.target : null;
    if (!(target instanceof Element) || animation.playState !== "running") continue;
    if (!target.closest("main") || target.closest(".lf-chrome, .lf-ui")) continue;
    found.set(target, { code: "unreduced-motion", at: at(target) });
  }
  return [...found.values()];
}
