/* Optional persistent element-target marks.
 *
 * The selected annotation renderer constructs this painter and supplies resolved
 * targets; it neither resolves anchors nor changes semantic state. Each box a target's
 * surface shows through (`shownParts`) draws its own mark, named by its states in
 * `data-lf-mark` (surfaces.css), and each target wears `lf-projected-mark`, so the focus
 * floor leaves the mark to say where focus is. Importing this module writes nothing. */

import { keeps } from "../keeps.js";
import { shownParts } from "../geometry.js";

const PROJECTED = "lf-projected-mark";
/** @typedef {{element: Element, surface: Element, states: ReadonlySet<string>}} VisualTarget */
export function createVisualMarkPaint() {
  /** @type {Map<Element, Element[]>} */
  const marked = new Map(); // target → the boxes wearing its mark

  /** @param {Iterable<VisualTarget>} next */
  function setTargets(next) {
    const targets = new Map(
      [...next]
        .filter((target) => target.states?.size)
        .map((target) => [
          target.element,
          { boxes: shownParts(target.surface), states: target.states },
        ]),
    );
    const wearing = new Set([...targets.values()].flatMap(({ boxes }) => boxes));
    for (const [element, boxes] of marked) {
      if (!targets.has(element)) element.classList.toggle(PROJECTED, false);
      for (const box of boxes)
        if (!wearing.has(box)) box.removeAttribute("data-lf-mark");
    }
    marked.clear();
    for (const [element, { boxes, states }] of targets) {
      element.classList.toggle(PROJECTED, true);
      for (const box of boxes) keeps(box, "data-lf-mark", [...states].sort().join(" "));
      marked.set(element, boxes);
    }
  }

  return { setTargets };
}
