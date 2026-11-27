/* Optional persistent element-target marks.
 *
 * The selected annotation renderer constructs this painter and supplies resolved
 * targets; it neither resolves anchors nor changes semantic state. Each box a target's
 * surface's marks stand on (`markedParts`) draws its own mark, named by its states in
 * `data-lf-mark` (element-marks.css), and each target wears `data-lf-projected-mark`, so the focus
 * floor leaves the mark to say where focus is. Importing this module writes nothing. */

import { keepsOnEach } from "../lib/keeps.js";
import { markedParts, readMarkRoom } from "../dom/geometry.js";

/** @typedef {{element: Element, surface: Element, states: ReadonlySet<string>}} VisualTarget */
export function createVisualMarkPaint() {
  const paintMarks = keepsOnEach("data-lf-mark");
  const paintProjected = keepsOnEach("data-lf-projected-mark");

  /** @param {Iterable<VisualTarget>} next */
  function setTargets(next) {
    const targets = [...next].filter((target) => target.states.size);
    // Two targets can stand on one box, as a part does on the frame its parent is drawn
    // in, and the box draws both their states.
    /** @type {Map<Element, Set<string>>} */
    const marks = new Map();
    for (const { surface, states } of targets)
      for (const box of markedParts(surface))
        marks.set(box, new Set([...(marks.get(box) ?? []), ...states]));
    const room = readMarkRoom([...marks.keys()]);
    paintProjected(new Map(targets.map(({ element }) => [element, ""])));
    paintMarks(
      new Map([...marks].map(([box, held]) => [box, [...held].sort().join(" ")])),
    );
    room();
  }

  return { setTargets };
}
