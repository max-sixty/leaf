/* Optional persistent element-target marks.
 *
 * The selected annotation renderer constructs this painter and supplies resolved
 * targets; it neither resolves anchors nor changes semantic state. Each target's
 * surface draws its own mark, named by its states in `data-lf-mark` (surfaces.css), and
 * each target wears `lf-projected-mark`, so the focus floor leaves the mark to say
 * where focus is. Importing this module writes nothing. */

import { keeps } from "../keeps.js";

const PROJECTED = "lf-projected-mark";
/** @typedef {{element: Element, surface: Element, states: ReadonlySet<string>}} VisualTarget */
export function createVisualMarkPaint() {
  /** @type {Map<Element, Element>} */
  const marked = new Map(); // target → the surface wearing its mark

  /** @param {Iterable<VisualTarget>} next */
  function setTargets(next) {
    const targets = new Map(
      [...next]
        .filter((target) => target.states?.size)
        .map((target) => [target.element, target]),
    );
    for (const [element, surface] of marked)
      if (targets.get(element)?.surface !== surface) {
        element.classList.toggle(PROJECTED, false);
        surface.removeAttribute("data-lf-mark");
        marked.delete(element);
      }
    for (const [element, { surface, states }] of targets) {
      element.classList.toggle(PROJECTED, true);
      keeps(surface, "data-lf-mark", [...states].sort().join(" "));
      marked.set(element, surface);
    }
  }

  return { setTargets };
}
