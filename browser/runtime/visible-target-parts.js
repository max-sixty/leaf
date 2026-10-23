/* One reading of the drawn parts behind a semantic target.

   A target with its own box is drawn even when one dimension is zero, as an SVG line is.
   A boxless target such as `display: contents` is drawn through its visible parts.
   Callers choose their own clipping, bounds and seat from these parts; this reading only
   answers whether the target has a drawn representation at all. */
import { drawn } from "./focus.js";
import { shownParts } from "./geometry.js";

export function visibleTargetParts(target) {
  const parts = shownParts(target).filter(drawn);
  return drawn(target) ? [target, ...parts.filter((part) => part !== target)] : parts;
}
