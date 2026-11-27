/* Optional persistent element-target marks.
 *
 * The selected annotation renderer constructs this painter and supplies resolved
 * targets; it neither resolves anchors nor changes semantic state. Each box a target's
 * surface shows through (`shownParts`) draws its own mark, named by its states in
 * `data-lf-mark` (element-marks.css), and each target wears `data-lf-projected-mark`, so the focus
 * floor leaves the mark to say where focus is. Importing this module writes nothing. */

import { keepsOnEach } from "../lib/keeps.js";
import { readMarkRoom, shownParts } from "../dom/geometry.js";

type VisualTarget = {
  element: Element;
  surface: Element;
  states: ReadonlySet<string>;
};
export function createVisualMarkPaint() {
  const paintMarks = keepsOnEach("data-lf-mark");
  const paintProjected = keepsOnEach("data-lf-projected-mark");

  function setTargets(next: Iterable<VisualTarget>) {
    const targets = [...next].filter((target) => target.states.size);
    const marks = new Map<Element, string>();
    for (const { surface, states } of targets)
      for (const box of shownParts(surface))
        marks.set(box, [...states].sort().join(" "));
    const room = readMarkRoom([...marks.keys()]);
    paintProjected(new Map(targets.map(({ element }) => [element, ""])));
    paintMarks(marks);
    room();
  }

  return { setTargets };
}
