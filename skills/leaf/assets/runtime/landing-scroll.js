/* Vertical landings through the reading regions holding a destination.
 *
 * Anchor travel and widget walks share this operation: the owning reading region
 * places the destination at its landing band, then each enclosing region reveals
 * what the inner move leaves out of view. The moves change only scrollTop, so a
 * shadow boundary or smooth motion never takes away sideways reading position.
 * CSS scroll-padding and the destination's scroll-margin clear pinned headers.
 */
import { landingBand, shownBox } from "./geometry.js";
import { scrollersOf } from "./reading-regions.js";
import { moveScrollerBy, reachable } from "./scrolling.js";

function placementBy(where, block, box) {
  const rect = where instanceof Range ? where.getBoundingClientRect() : shownBox(where);
  const band = landingBand(box);
  const room = band.bottom - band.top;
  const margin =
    where instanceof Range
      ? 0
      : Number.parseFloat(getComputedStyle(where).scrollMarginTop) || 0;
  const place =
    where instanceof Range
      ? (room - rect.height) / 2
      : block === "start"
        ? margin
        : Math.max((room - rect.height) / 2, margin);
  return rect.top - band.top - place;
}

export function scrollIntoReadingBand(where, holder, block, behavior) {
  const [box, ...around] = scrollersOf(holder);
  if (!box) return;
  const rect = where instanceof Range ? where.getBoundingClientRect() : shownBox(where);
  let { top, bottom } = rect;
  const by = placementBy(where, block, box);
  let moved = reachable(box, by);
  moveScrollerBy(box, by, behavior);
  for (const outer of around) {
    top -= moved;
    bottom -= moved;
    const band = landingBand(outer);
    if (!band) return;
    const by =
      top < band.top
        ? top - band.top
        : bottom > band.bottom
          ? Math.min(bottom - band.bottom, top - band.top)
          : 0;
    moved = reachable(outer, by);
    if (Math.abs(moved) >= 1) moveScrollerBy(outer, moved, behavior);
  }
}
