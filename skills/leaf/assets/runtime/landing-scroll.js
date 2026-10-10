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
 *
 * Room and being shown are this module's too, so a landing that asks whether to move
 * reads the same arithmetic the move then does. A destination's room (`landingRoom`) is
 * the least extent, on each axis, of the window and of every landing band clipping it
 * there, less the clearance each region the landing moves leaves at its top, and the
 * destination's own at its foot: what a landing can show of it at once. `fitsWhole` compares it with that room. A destination
 * is already shown (`alreadyShown`) when the user sees all of it along each axis where
 * it fits, and any of it along one where it does not: a box longer than its room never
 * shows whole, and moving one partly in view takes the user from what they see of it to
 * an edge they did not ask for. "Seen" is `seenRect`'s. A landing that follows the user,
 * such as entering a reply or standing back on a thread, asks it before moving anything.
 * Navigation does not: `nearest` stays the native alignment (rect.js,
 * `nearestScrollBy`), which fills the band with a tall destination partly in view, so a
 * fold the user goes to opens from its start.
 */
import {
  landingBand,
  localScrollBy,
  placeHolder,
  seenRect,
  shownBox,
  shownWindow,
  scrollAxes,
  visibleBand,
} from "./geometry.js";
import { scrollersOf } from "./reading-regions.js";
import { moveScrollerBy, reachable, pageScroller } from "./scrolling.js";
import { clippingAxes, nearestScrollBy } from "./rect.js";
import { renderedParent, renderedUnder } from "./shadow.js";

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

// The room a landing has for `where`, as a width and a height (see the header). Each box
// bounds the axes it clips. Each region the landing moves also takes the clearance the
// move leaves at its top: the destination's own in the region that lands it, and in each
// region around that, what stands over the inner region's box, as
// `scrollIntoReadingBand` reads it. With `until`, the height is the room for the run
// from `where`'s top to `until`'s foot, which is what a landing at `where`'s start
// promises of a later node; only the boxes holding the whole run bound it.
export function landingRoom(where, until = where) {
  const regions = [...scrollersOf(placeHolder(where))];
  let { width, height } = shownWindow();
  for (
    let box = renderedParent(where);
    box instanceof Element;
    box = renderedParent(box)
  ) {
    const band = (until === where || renderedUnder(until, box)) && landingBand(box);
    if (band) {
      const axes =
        box === pageScroller
          ? { x: true, y: true }
          : clippingAxes(getComputedStyle(box));
      const at = regions.indexOf(box);
      const clearance =
        at === 0
          ? topMargin(where, box) + scrollMargin(until, "Bottom")
          : at > 0
            ? Math.max(0, readingTop(regions[at - 1], box) - band.top)
            : 0;
      if (axes.x) width = Math.min(width, band.right - band.left);
      if (axes.y) height = Math.min(height, band.bottom - band.top - clearance);
    }
    if (box === pageScroller || getComputedStyle(box).position === "fixed") break;
  }
  return { width, height };
}

export function fitsWhole(where) {
  const box = shownBox(where);
  const room = landingRoom(where);
  return box.height <= room.height && box.width <= room.width;
}

export function alreadyShown(where) {
  const seen = seenRect(where, new Map());
  if (!seen) return false;
  const box = shownBox(where);
  const room = landingRoom(where);
  return (
    (box.height > room.height || (seen.top <= box.top && seen.bottom >= box.bottom)) &&
    (box.width > room.width || (seen.left <= box.left && seen.right >= box.right))
  );
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
    block === "nearest"
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
// before its enclosing context lands in the reading band. A destination in a
// fixed layer, such as a modal's list, has no reading region: its boxes reveal it
// nearest, out to that layer.
export function scrollIntoView(
  where,
  { alignment = where, behavior = "auto", block = "start" } = {},
) {
  if (!where) return;
  const holder = placeHolder(alignment);
  if (!holder) return;
  const targetScroller = scrollersOf(holder).next().value;
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
    if (band) {
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
    }
    if (box === pageScroller || getComputedStyle(box).position === "fixed") break;
  }
  if (targetScroller) scrollIntoReadingBand(alignment, holder, block, behavior);
}
