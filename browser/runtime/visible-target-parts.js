/* One reading of the drawn parts behind a semantic target.

   A target with its own box is drawn even when one dimension is zero, as an SVG line is.
   A boxless target such as `display: contents` is drawn through its visible parts.
   Callers choose their own clipping, bounds and seat from these parts; this reading only
   answers whether the target has a drawn representation at all. A target in content the
   browser skips, such as a closed disclosure's, has none, and is answered without a
   geometry read, which would lay that content out to say so (shown-box.js, `skipped`).
   Nor does one under `opacity: 0`, which paints nothing though it keeps its box, as a
   deck keeps the slides beside the current one laid out for their transitions; the
   platform answers that with the rest (`checkVisibility`), as anchor resolution and
   reading places ask it.

   A transition or animation of what this reads is read where it starts, at the old
   value, so the margin reads it again as one ends (margin-layout.js,
   `hearTargetChanges`). */
import { drawn } from "./focus.js";
import { shownParts } from "./geometry.js";
import { skipped } from "./shown-box.js";

/** @param {Element} part */
const painted = (part) =>
  drawn(part) && part.checkVisibility({ opacityProperty: true });

/** @param {Element} target */
export function visibleTargetParts(target) {
  if (skipped(target)) return [];
  const parts = shownParts(target).filter(painted);
  return painted(target) ? [target, ...parts.filter((part) => part !== target)] : parts;
}
