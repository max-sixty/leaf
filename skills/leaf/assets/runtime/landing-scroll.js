/* Document-local scrolling through the boxes holding a destination.
 *
 * Anchor travel and widget walks share this operation: the owning reading region
 * places the destination at its landing band, then each enclosing region reveals
 * what the inner move leaves out of view. Start and end landings reveal that edge
 * through enclosing regions even when the item's full extent is taller than them.
 * Vertical reading-band moves preserve sideways reading position. Full placement
 * also reveals inner overflow horizontally, using the same geometry and nearest rule.
 * Every walk ends at this document, so navigation in an embedded sample cannot
 * scroll its containing page.
 * CSS scroll-padding and the destination's scroll-margin clear pinned headers, and a
 * nearest landing takes its bottom margin too, which clears a pinned foot such as a long
 * thread's reply row.
 */
import {
  landingBand,
  shownBox,
  scrollAxes,
  localScrollBy,
  placeHolder,
} from "./geometry.js";
import { renderedParent } from "./shadow.js";
import { scrollersOf } from "./reading-regions.js";
import { moveScrollerBy, reachable, pageScroller } from "./scrolling.js";

// Native nearest alignment, including an oversized destination wholly above or
// below its band. One rule serves inner inspection and enclosing reading regions.
const nearestBy = (start, end, low, high) => {
  if (start < low && end > high) return 0;
  const oversized = end - start > high - low;
  if (start < low) return oversized ? end - high : start - low;
  if (end > high) return oversized ? start - low : end - high;
  return 0;
};

const scrollMargin = (where, side = "Top") =>
  where instanceof Range
    ? 0
    : Number.parseFloat(getComputedStyle(where)[`scrollMargin${side}`]) || 0;

function placementBy(where, block, box) {
  const rect = where instanceof Range ? where.getBoundingClientRect() : shownBox(where);
  const band = landingBand(box);
  const room = band.bottom - band.top;
  const margin = scrollMargin(where);
  const place =
    block === "start"
      ? margin
      : block === "end"
        ? room - rect.height - scrollMargin(where, "Bottom")
        : where instanceof Range
          ? (room - rect.height) / 2
          : Math.max((room - rect.height) / 2, margin);
  const movement =
    block === "nearest"
      ? nearestBy(
          rect.top - margin,
          rect.bottom + scrollMargin(where, "Bottom"),
          band.top,
          band.bottom,
        )
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
  } else if (block === "end") {
    // Carry the closing edge through outer regions, including its footer clearance.
    top = bottom - 1;
    bottom += scrollMargin(where, "Bottom");
  }
  let { local, moved } = verticalTravel(box, placementBy(where, block, box));
  if (Math.abs(moved) >= 1) moveScrollerBy(box, local, behavior);
  for (const outer of around) {
    top -= moved;
    bottom -= moved;
    const band = landingBand(outer);
    if (!band) return;
    ({ local, moved } = verticalTravel(
      outer,
      nearestBy(top, bottom, band.top, band.bottom),
    ));
    if (Math.abs(moved) >= 1) moveScrollerBy(outer, local, behavior);
  }
}

// Reveal inner overflow before aligning its owning reading region. The ancestry
// walk ends at this document's scrollport or a fixed box; native scrollIntoView
// would continue through same-origin frames and move their containing pages.
// Horizontal inspection is nearest; vertical alignment is start, center, end,
// or nearest. An explicit alignment lets a passage prepare its inner overflow
// before its enclosing context lands in the reading band.
export function scrollIntoView(
  where,
  { alignment = where, behavior = "auto", block = "start" } = {},
) {
  if (!where) return;
  const holder = placeHolder(alignment);
  if (!holder) return;
  const targetScroller = scrollersOf(holder).next().value;
  if (!targetScroller) return;
  // Horizontal inspection can belong to any ancestor, the owning region included.
  // Only inner scrollports prepare Y; the region and its outers glide below.
  let inside = true;
  for (
    let box = placeHolder(where);
    box instanceof Element;
    box = renderedParent(box)
  ) {
    if (box === targetScroller) inside = false;
    const band = landingBand(box);
    if (!band) continue;
    const { left, right, top, bottom } = band;
    const destination = where.getBoundingClientRect();
    const byX = nearestBy(destination.left, destination.right, left, right);
    const byY = inside
      ? nearestBy(destination.top, destination.bottom, top, bottom)
      : 0;
    if (byX || byY)
      box.scrollBy({
        ...localScrollBy(box, { x: byX, y: byY }),
        behavior: "instant",
      });
    if (box === pageScroller || getComputedStyle(box).position === "fixed") break;
  }
  scrollIntoReadingBand(alignment, holder, block, behavior);
}
