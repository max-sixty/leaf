/* One reading of the drawn parts behind a semantic target.

   A target with its own box is drawn even when one dimension is zero, as an SVG line is.
   A boxless target such as `display: contents` is drawn through its visible parts.
   Callers choose their own clipping, bounds and seat from these parts; this reading only
   answers whether the target has a drawn representation at all. A target in content the
   browser skips, such as a closed disclosure's, has none, and is answered without a
   geometry read, which would lay that content out to say so (lib/shadow-tree.js, `skipped`);
   so has a boxless target's part there, such as a closed tab's panel holds. */
import { drawn } from "../dom/focus.js";
import { shownParts } from "../dom/geometry.js";
import { skipped } from "../lib/shadow-tree.js";

export function visibleTargetParts(target: Element) {
  if (skipped(target)) return [];
  const parts = shownParts(target, { leaveSkipped: true }).filter(drawn);
  return drawn(target) ? [target, ...parts.filter((part) => part !== target)] : parts;
}
