/* Document-local scrolling through the boxes holding a destination.
 *
 * Anchor travel and widget walks share this operation: the owning reading region
 * places the destination at its landing band, then each enclosing region reveals
 * what the inner move leaves out of view. A start landing reveals a short destination
 * whole and the opening of one taller than its enclosing region.
 * The moves change only scrollTop, so a
 * shadow boundary or smooth motion never takes away sideways reading position.
 * CSS scroll-padding and the destination's scroll-margin state landing room. The
 * destination's inherited header slot also clears headers over only its own region,
 * such as an embedded tab strip; a declared margin and that slot are alternative
 * readings of the same clearance, never added twice. A nearest landing takes its
 * bottom margin too, which clears a pinned foot such as a long thread's reply row.
 * Full placement first reveals inner overflow. Both operations stop at this
 * document, so a sample never scrolls its containing page. End alignment reveals
 * a tall destination's closing edge through enclosing reading regions.
 */
import {
  landingBand,
  localScrollBy,
  placeHolder,
  shownBox,
  scrollAxes,
  visibleBand,
} from "./geometry.js";
import { scrollersOf } from "./reading-regions.js";
import { moveScrollerBy, reachable, pageScroller } from "./scrolling.js";
import { nearestScrollBy } from "./rect.js";
import { renderedParent } from "./shadow.js";

const scrollMargin = (where, side = "Top") =>
  where instanceof Range
    ? 0
    : Number.parseFloat(getComputedStyle(where)[`scrollMargin${side}`]) || 0;

function readingTop(where, box) {
  const destination = placeHolder(where);
  let top = visibleBand(box, destination)?.top ?? landingBand(box).top;
  // A sideways scroller restarts the header slot without becoming the vertical
  // reading region. Read every enclosing box in that region too: its own view
  // retains the headers outside it that its descendants no longer inherit.
  for (
    let at = renderedParent(destination);
    destination !== box && at && at !== box;
    at = renderedParent(at)
  ) {
    const reading = visibleBand(box, at);
    if (reading) top = Math.max(top, reading.top);
  }
  return top;
}

function topMargin(where, box) {
  const band = landingBand(box);
  return Math.max(scrollMargin(where), readingTop(where, box) - band.top);
}

function placementBy(where, block, box, margin) {
  const rect = where instanceof Range ? where.getBoundingClientRect() : shownBox(where);
  const band = landingBand(box);
  const room = band.bottom - band.top;
  const place =
    block === "start"
      ? margin
      : block === "end"
        ? room - rect.height - scrollMargin(where, "Bottom")
        : Math.max((room - rect.height) / 2, margin);
  const movement =
    block === "nearest" && !(where instanceof Range)
      ? nearestScrollBy(
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
  const margin = topMargin(where, box);
  let { top, bottom } = rect;
  if (block === "start") {
    top -= margin;
  } else if (block === "end") {
    top = bottom - 1;
    bottom += scrollMargin(where, "Bottom");
  }
  let { local, moved } = verticalTravel(box, placementBy(where, block, box, margin));
  if (Math.abs(moved) >= 1) moveScrollerBy(box, local, behavior);
  let inner = box;
  for (const outer of around) {
    top -= moved;
    bottom -= moved;
    const band = landingBand(outer);
    if (!band) return;
    // An inner scroller restarts its own header slot. Read what covers its box
    // from the enclosing region, rather than reading the destination's reset slot.
    band.top = Math.max(band.top, readingTop(inner, outer));
    // Preserve a short destination's full extent. A tall one promises its opening
    // and as much as this region can show, rather than demanding its whole height.
    if (block === "start") bottom = Math.min(bottom, top + band.bottom - band.top);
    ({ local, moved } = verticalTravel(
      outer,
      nearestScrollBy(top, bottom, band.top, band.bottom),
    ));
    if (Math.abs(moved) >= 1) moveScrollerBy(outer, local, behavior);
    inner = outer;
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
    const byX = nearestScrollBy(destination.left, destination.right, left, right);
    const byY = inside
      ? nearestScrollBy(destination.top, destination.bottom, top, bottom)
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
