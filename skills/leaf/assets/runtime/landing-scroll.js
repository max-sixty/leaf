/* Vertical landings through the reading regions holding a destination.
 *
 * Anchor travel and widget walks share this operation: the owning reading region
 * places the destination at its landing band, then each enclosing region reveals
 * what the inner move leaves out of view. A start landing reveals the opening
 * through enclosing regions even when the item's full extent is taller than them.
 * The moves change only scrollTop, so a
 * shadow boundary or smooth motion never takes away sideways reading position.
 * CSS scroll-padding and the destination's scroll-margin clear pinned headers.
 */
import { landingBand, shownBox, scrollAxes } from "./geometry.js";
import { scrollersOf } from "./reading-regions.js";
import { moveScrollerBy, reachable } from "./scrolling.js";

const nearestBy = ({ top, bottom }, band) =>
  top < band.top && bottom > band.bottom
    ? 0
    : top < band.top
      ? top - band.top
      : bottom > band.bottom
        ? Math.min(bottom - band.bottom, top - band.top)
        : 0;

const scrollMargin = (where) =>
  where instanceof Range
    ? 0
    : Number.parseFloat(getComputedStyle(where).scrollMarginTop) || 0;

function placementBy(where, block, box) {
  const rect = where instanceof Range ? where.getBoundingClientRect() : shownBox(where);
  const band = landingBand(box);
  const room = band.bottom - band.top;
  const margin = scrollMargin(where);
  const place =
    block === "start"
      ? margin
      : where instanceof Range
        ? (room - rect.height) / 2
        : Math.max((room - rect.height) / 2, margin);
  const movement =
    block === "nearest" && !(where instanceof Range)
      ? nearestBy({ top: rect.top - margin, bottom: rect.bottom }, band)
      : rect.top - band.top - place;
  return movement;
}

function verticalTravel(box, movement) {
  const scale = scrollAxes(box).y.y;
  const local = scale === 0 ? 0 : reachable(box, movement / scale);
  return { local, moved: local * scale };
}

export function scrollIntoReadingBand(where, holder, block, behavior) {
  const [box, ...around] = scrollersOf(holder);
  if (!box) return;
  const rect = where instanceof Range ? where.getBoundingClientRect() : shownBox(where);
  let { top, bottom } = rect;
  if (block === "start") {
    // The opening, not the whole tall item, is the extent this landing promises.
    bottom = top + 1;
    top -= scrollMargin(where);
  }
  let { local, moved } = verticalTravel(box, placementBy(where, block, box));
  if (Math.abs(moved) >= 1) moveScrollerBy(box, local, behavior);
  for (const outer of around) {
    top -= moved;
    bottom -= moved;
    const band = landingBand(outer);
    if (!band) return;
    ({ local, moved } = verticalTravel(outer, nearestBy({ top, bottom }, band)));
    if (Math.abs(moved) >= 1) moveScrollerBy(outer, local, behavior);
  }
}
