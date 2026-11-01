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
 * Sideways it takes the destination's inline margins, so a focused control brought in
 * from a sideways scroller's end keeps its ring's room there as it does at a foot.
 * Full placement first reveals inner overflow, each box moving the destination
 * nearest with the clearance a nearest landing keeps in its reading region. A box no
 * reading region moves reveals it the same way, as a fixed layer's list and a reveal
 * bounded `within` one box do, so a walked item keeps its ring's room at that box's
 * edge too. Both operations stop at this document, so a sample never scrolls its
 * containing page, and a reveal bounded `within` one box stops there. End alignment
 * reveals a tall destination's closing edge through enclosing reading regions. Every
 * script reveal comes through here, a reveal bounded to one box included: a
 * hand-rolled `scrollTop` sum is one more reading of the band that can disagree with
 * this one (eslint.config.mjs, "architecture/scroll-writes").
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
 * such as entering a reply or returning to a thread, asks it before moving anything.
 * Navigation does not: `nearest` stays the native alignment (rect.js,
 * `nearestScrollBy`), which fills the band with a tall destination partly in view, so a
 * fold the user goes to opens from its start. Where a landing would leave a
 * destination (`landedBox`) is read by the same arithmetic, so a surface that would
 * stand over it there can give way first (floating-panel.js, `clearFor`).
 *
 * A landing is the reader's choice of where each box it moves stands (scrolling.js).
 * Count it as it starts, including an instant landing: navigation can change layout
 * in the same task, so its scroll end alone cannot distinguish the landing from
 * anchoring or a clamp before the keeper restores that layout change.
 *
 * A destination the user is on is measured by the box that wears its focus ring
 * (focus.js, `ringBox`), with its own margins, the ring's room: a playground's choice
 * rings its radio and words together, and a landing that measured the radio left the
 * face's ring cut at its pane's foot. Where that box is longer than its room, the
 * destination is its own box again, so the user still sees the control. Every other
 * destination is its own box.
 *
 * A Tab's arrival lands here too, after the browser's own reveal. The browser reveals a
 * focus arrival only when it counts it out of view: Firefox when less than about a line
 * of it shows, on either axis, and Chromium across only when none of it shows; and
 * neither knows the box that wears its ring. So a control partly past a scroller's edge
 * stayed cut there, a link at a wide table's end in both engines, and in Firefox a
 * radio whose box showed whole while its ring was cut. An arrival whose ring the user
 * does not see, its box out to its margins on each axis where that fits the room a
 * landing has, lands nearest, reading the margins and padding the browser's reveal
 * reads. One whose ring shows moves nothing, so a control in a stuck header, whose
 * margin counts it as shown, stays put, as does a box longer than its room that shows
 * in part.
 * A marked decision also wears a ring around its own box while Tab is inside
 * it. Once the focused control is visible, reveal that ring if the decision
 * fits the room. Its own scroll margin already reserves the outline's gap.
 */
import { localScrollBy, scrollAxes } from "./element-frame.js";
import { deepFocus, onCurrentLocation, ringBox } from "./focus.js";
import {
  landingBand,
  placeBox,
  placeHolder,
  seenRect,
  shownWindow,
  visibleBand,
} from "./geometry.js";
import { scrollersOf } from "./scroll-containers.js";
import { startScroll, reachable, pageScroller } from "./scrolling.js";
import { clippingAxes, nearestScrollBy } from "./rect.js";
import { nextRender } from "./rendering.js";
import { renderedParent, renderedUnder } from "./shadow-tree.js";
import { setScroll } from "./arrivals.js";

/** @typedef {Element | Range} Destination
 * @typedef {import("./rect.js").Box} Box
 * @typedef {"Top" | "Right" | "Bottom" | "Left"} MarginSide
 * @typedef {{box: Element, local: number, moved: number}} ScrollMove
 */
/** @param {Element} box @param {{top?: number, left?: number}} by @param {ScrollBehavior} behavior */
const land = (box, by, behavior) => {
  startScroll(box);
  setScroll(box, {
    top: box.scrollTop + (by.top ?? 0),
    left: box.scrollLeft + (by.left ?? 0),
    behavior,
  });
};

// A destination's landing margin on one side. A range has none of its own and takes the
// larger of those of the elements it starts and ends with, so a side list's run of a
// group's label and a tab keeps the room the tab's ring needs (lf-tabs.js, `#showTab`).
/** @param {Destination} where @param {MarginSide} [side] @returns {number} */
function scrollMargin(where, side = "Top") {
  if (!(where instanceof Range))
    return (
      Number.parseFloat(
        getComputedStyle(where).getPropertyValue(`scroll-margin-${side.toLowerCase()}`),
      ) || 0
    );
  const edges = [
    where.startContainer.childNodes[where.startOffset],
    where.endContainer.childNodes[where.endOffset - 1],
  ].filter((edge) => edge instanceof Element);
  return edges.length ? Math.max(...edges.map((edge) => scrollMargin(edge, side))) : 0;
}

// The element a landing shows of `where` (see the header): the box wearing its ring
// where that fits the room a landing has, and otherwise `where` itself, since a ring
// box longer than its room never shows whole and the user must still see the control
// they stand on. Every walk out to the scrollers that move starts there, so a scroller
// between the control and that box, such as a file editor's, is never moved to show it.
/** @param {Destination} where @returns {Destination} */
function shownFor(where) {
  const ring = ringBox(where);
  if (ring === where) return where;
  const box = placeBox(ring);
  const room = roomAround(ring, where);
  return box.height <= room.height && box.width <= room.width ? ring : where;
}
/** @param {Destination} where */
const destinationBox = (where) => placeBox(shownFor(where));
/** @param {Destination} where */
const holderOf = (where) => placeHolder(shownFor(where));

// What stands over `holder` in `box`. A sideways scroller restarts the header slot
// without becoming the vertical reading region; `visibleBand` reads the headers outside
// it.
/** @param {Element | null} holder @param {Element} box @param {Box} band */
const readingTop = (holder, box, band) => visibleBand(box, holder)?.top ?? band.top;

/** @param {Destination} where @param {Element} box @param {Box} band @param {Element | null} [holder] */
function topMargin(where, box, band, holder = holderOf(where)) {
  return Math.max(scrollMargin(where), readingTop(holder, box, band) - band.top);
}

// The room a landing has for `where`, as a width and a height (see the header). Each box
// bounds the axes it clips. Each region the landing moves also takes the clearance the
// move leaves at its top: the destination's own in the region that lands it, and in each
// region around that, what stands over the inner region's box, as
// `scrollIntoReadingBand` reads it. With `until`, the height is the room for the run
// from `where`'s top to `until`'s foot, which is what a landing at `where`'s start
// promises of a later node; only the boxes holding the whole run bound it.
/** @param {Destination} where @param {Element} [until] */
export const landingRoom = (where, until) => roomAround(shownFor(where), where, until);

// The same room for `where` shown as `shown`, the box it or its ring stands in. The
// boxes clipping a range start at the element holding it, and an element's at its parent.
/** @param {Destination} shown @param {Destination} where @param {Element} [until] */
function roomAround(shown, where, until) {
  const holder = placeHolder(shown);
  /** @type {Map<Element, Element | null>} */
  const regions = new Map();
  let previous = null;
  for (const box of scrollersOf(holder)) {
    regions.set(box, previous);
    previous = box;
  }
  let { width, height } = shownWindow();
  for (
    let box = shown instanceof Range ? holder : renderedParent(shown);
    box instanceof Element;
    box = renderedParent(box)
  ) {
    const band =
      (!until || until === where || renderedUnder(until, box)) && landingBand(box);
    if (band) {
      const axes =
        box === pageScroller
          ? { x: true, y: true }
          : clippingAxes(getComputedStyle(box));
      const inner = regions.get(box);
      const clearance =
        inner === null
          ? topMargin(where, box, band, holder) + scrollMargin(until ?? where, "Bottom")
          : inner
            ? Math.max(0, readingTop(inner, box, band) - band.top)
            : 0;
      if (axes.x) width = Math.min(width, band.right - band.left);
      if (axes.y) height = Math.min(height, band.bottom - band.top - clearance);
    }
    if (box === pageScroller || getComputedStyle(box).position === "fixed") break;
  }
  return { width, height };
}

/** @param {Destination} where */
export function fitsWhole(where) {
  const box = destinationBox(where);
  const room = landingRoom(where);
  return box.height <= room.height && box.width <= room.width;
}

// Whether the user sees `out` of `where` along each axis where its box fits the room,
// and any of it along one where it does not (see the header).
/** @param {Destination} where @param {DOMRect} box @param {DOMRect} out */
function seesWhole(where, box, out) {
  const seen = seenRect(shownFor(where), new Map(), out);
  if (!seen) return false;
  const room = landingRoom(where);
  return (
    (box.height > room.height || (seen.top <= out.top && seen.bottom >= out.bottom)) &&
    (box.width > room.width || (seen.left <= out.left && seen.right >= out.right))
  );
}

/** @param {Destination} where */
export function alreadyShown(where) {
  const box = destinationBox(where);
  return seesWhole(where, box, box);
}

// Whether the user sees the ring of the control they stand on: its box out to its
// margins.
/** @param {Destination} where */
function ringShown(where) {
  const box = destinationBox(where);
  const top = scrollMargin(where, "Top");
  const right = scrollMargin(where, "Right");
  const bottom = scrollMargin(where, "Bottom");
  const left = scrollMargin(where, "Left");
  return seesWhole(
    where,
    box,
    new DOMRect(
      box.left - left,
      box.top - top,
      box.width + left + right,
      box.height + top + bottom,
    ),
  );
}

/** @param {Destination} where @param {ScrollLogicalPosition} block @param {Box} band @param {number} margin */
function placementBy(where, block, band, margin) {
  const rect = destinationBox(where);
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

/** @param {Element} box @param {number} movement */
function verticalTravel(box, movement) {
  const scale = scrollAxes(box).y.y;
  const local = scale === 0 ? 0 : reachable(box, movement / scale);
  return { local, moved: local * scale };
}

// The moves a landing in the reading band makes, region by region from the one
// holding `where` outward, each a box and the local offset it scrolls by, and how far
// they carry the destination down the window together (`moved`). Scrolling and its
// prediction (`landedBox`) both read it, so they can't disagree.
/** @param {Destination} where @param {Element | null} holder @param {ScrollLogicalPosition} block @returns {{moves: ScrollMove[], moved: number}} */
function readingBandMoves(where, holder, block) {
  const [box, ...around] = scrollersOf(holder);
  if (!box) return { moves: [], moved: 0 };
  const band = landingBand(box);
  if (!band) return { moves: [], moved: 0 };
  const rect = destinationBox(where);
  const margin = topMargin(where, box, band);
  let { top, bottom } = rect;
  if (block === "start") {
    top -= margin;
  } else if (block === "end") {
    top = bottom - 1;
    bottom += scrollMargin(where, "Bottom");
  }
  let { local, moved } = verticalTravel(box, placementBy(where, block, band, margin));
  const moves = [{ box, local, moved }];
  let inner = box;
  for (const outer of around) {
    top -= moved;
    bottom -= moved;
    const band = landingBand(outer);
    if (!band) break;
    // An inner scroller restarts its own header slot. Read what covers its box
    // from the enclosing region, rather than reading the destination's reset slot.
    band.top = Math.max(band.top, readingTop(inner, outer, band));
    // Preserve a short destination's full extent. A tall one promises its opening
    // and as much as this region can show, rather than demanding its whole height.
    if (block === "start") bottom = Math.min(bottom, top + band.bottom - band.top);
    ({ local, moved } = verticalTravel(
      outer,
      nearestScrollBy(top, bottom, band.top, band.bottom),
    ));
    moves.push({ box: outer, local, moved });
    inner = outer;
  }
  return { moves, moved: moves.reduce((sum, move) => sum + move.moved, 0) };
}

// Where travel's landing (`scrollIntoReadingBand`, centred, as anchor travel lands)
// would leave `where`: in the band where its regions can scroll that far, and short
// of it at a region's end.
/** @param {Destination} where */
export function landedBox(where) {
  const rect = destinationBox(where);
  const { moved } = readingBandMoves(where, holderOf(where), "center");
  return new DOMRect(rect.x, rect.y - moved, rect.width, rect.height);
}

/** @param {Destination} where @param {Element | null} holder @param {ScrollLogicalPosition} block @param {ScrollBehavior} behavior */
export function scrollIntoReadingBand(where, holder, block, behavior) {
  for (const { box, local, moved } of readingBandMoves(where, holder, block).moves)
    if (Math.abs(moved) >= 1) land(box, { top: local }, behavior);
}

// Reveal inner overflow before aligning its owning reading region. The ancestry
// walk ends at this document's scrollport or a fixed box; native scrollIntoView
// would continue through same-origin frames and move their containing pages.
// Horizontal inspection is nearest; vertical alignment is start, center, end,
// or nearest. Each box the walk moves reveals the destination nearest as the reading
// region does (`placementBy`), with its margins. An explicit alignment lets a passage
// prepare its inner overflow before its enclosing context lands in the reading band. A destination in a
// fixed layer, such as a modal's list, has no reading region: its boxes reveal it
// nearest, out to that layer. `within` ends the walk at that box, so only it and the
// boxes inside it move, each revealing the destination nearest: an item comes into
// its own strip or list while the page around it stays where the user reads. Native
// `scrollIntoView({container: "nearest"})` is no substitute: Firefox still scrolls the
// boxes around it (notes/browser-support.md, "Native reveal bounded to its scroller").
/** @param {Destination | null | undefined} where @param {{alignment?: Destination, behavior?: ScrollBehavior, block?: ScrollLogicalPosition, within?: Element | null}} [options] */
export function scrollIntoView(
  where,
  { alignment, behavior = "auto", block = "start", within = null } = {},
) {
  if (!where) return;
  const aligned = alignment ?? where;
  const holder = holderOf(aligned);
  if (!holder) return;
  const targetScroller = within ? null : scrollersOf(holder).next().value;
  // Horizontal inspection can belong to any ancestor, the owning region included.
  // Only inner scrollports prepare Y; the region and its outers glide below.
  let inside = true;
  const start = holderOf(where);
  for (let box = start; box instanceof Element; box = renderedParent(box)) {
    if (box === targetScroller) inside = false;
    const band = landingBand(box);
    if (band) {
      const { left, right } = band;
      const destination = destinationBox(where);
      const byX = nearestScrollBy(
        destination.left - scrollMargin(where, "Left"),
        destination.right + scrollMargin(where, "Right"),
        left,
        right,
      );
      const byY = inside
        ? placementBy(where, "nearest", band, topMargin(where, box, band, start))
        : 0;
      // Only a box that will move is asked to, as a first tab's ring room at its
      // strip's start moves nothing: a call that moves nothing still reads as a
      // scroll the gesture made (tests/shift_watch.js, "Scrolls a gesture makes").
      const by = localScrollBy(box, { x: byX, y: byY });
      if (by.left || by.top) land(box, by, "instant");
    }
    if (
      box === within ||
      box === pageScroller ||
      getComputedStyle(box).position === "fixed"
    )
      break;
  }
  if (targetScroller) scrollIntoReadingBand(aligned, holder, block, behavior);
}

// A Tab's arrival (see the header), read once the browser's own reveal has moved.
onCurrentLocation(
  /** @param {Element | null} node @param {string | null} cause */ (node, cause) => {
    if (cause !== "step" || !node) return;
    nextRender(() => {
      if (deepFocus() !== node) return;
      if (!ringShown(node)) scrollIntoView(node, { block: "nearest" });
      // A decision's attention ring is worn by its box, even while Tab stands on
      // a control inside it. Native focus reveal knows only the control's box.
      /** @type {Element | null} */
      let box = node;
      for (; box; box = renderedParent(box)) {
        if (!box.matches("[data-lf-obligation]")) continue;
        if (getComputedStyle(box).outlineStyle === "none") continue;
        if (!ringShown(box)) scrollIntoView(box, { block: "nearest" });
        break;
      }
    });
  },
);
