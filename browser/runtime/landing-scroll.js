/* One landing: bring a destination into the region each box that scrolls it keeps for
 * landings, and say whether it already stands there.
 *
 * The region is the browser's: each scroller's scrollport less its `scroll-padding`,
 * which chrome over a scroller states for the room it takes (the floating panel's reach
 * and the head room on the root, base.css; a page tab strip through
 * `--lf-root-headers`), and the destination's box out to its `scroll-margin`, which a
 * header over part of a scroller states from the slot and a focused control states for
 * its ring's room (surfaces.css). The padding spans the scroller's width, so a landing
 * clears the floating panel's reach even beside it; a box that only clips, such as a
 * joined option group, is no room a landing can make.
 *
 * Every nearest landing first asks whether the destination is already shown
 * (`alreadyShown`), so a caller that follows the user, a Tab's arrival, entering a
 * reply or returning to a thread, and one that takes them somewhere, travel and the
 * walks, ask one question. It is shown where nearest would move nothing: the user sees
 * it (geometry.js, `seenRect`, which takes away the box the chrome covers, so a control
 * beside the floating panel stays put) out to its margins, as far as the boxes between
 * it and its scroller let them show (`landable`), along each axis where it fits its
 * room, and it shows as much as the room holds along one where it is longer, since a box
 * taller than the window that the user sees only part of still comes in as far as it
 * fits. The room is what a landing could give it (`roomOf`), not what the boxes around
 * it show where they stand now: a box a pane holds whole, with the pane's foot below the
 * window, is not yet shown. Its edges are compared at layout precision (keeps.js,
 * `atLayoutPrecision`): a box a landing put flush at an edge reads back a float's
 * rounding past it in Firefox, and a reading that counted it unseen would land it again
 * and enter travel's history.
 * A box a motion under way is carrying (scrolling.js, `scrollGoal`) is shown only where
 * it is seen both where it stands and where that motion will leave it, as a key pressed
 * while the page moves acts as if the motion had landed: `Shift+m` just after `m` finds
 * the obligation `m` is leaving already gone. Only a box growing under the user's
 * keystrokes skips the question, keeping its foot in the band as the browser keeps a
 * caret (`keepInBand`).
 *
 * The move walks the boxes that scroll the destination, from it out: its own reading
 * region (scroll-containers.js, `scrollersOf`) puts the margin box at `block` in its
 * landing band, and the boxes inside and around that region reveal it there nearest, so
 * a `g z` in a bounded pane leaves the page where it stands; around the region, a start
 * landing reveals the opening of a destination taller than a band and an end landing
 * its closing edge. Each box reveals it sideways at the nearest edge, as far as it can
 * scroll, and moves only along its own axes, scrollTop for the vertical landing and
 * scrollLeft for the sideways one, so a quarter-turned box whose scrollLeft would carry
 * the destination up the window leaves that to the box around it, and a smooth landing
 * glides scrollTop alone (scrolling.js, `glideTo`). `sideways: false` moves nothing
 * sideways, for a landing that aligns what the user is already reading, such as `g z`
 * and a diff's file, and keeps their place across its lines. A centred landing opens a
 * destination taller than its room at its start, where centring would put its middle in
 * the band and its opening above the window. An `alignment` first reveals the
 * destination nearest in the boxes inside its own region's scroller, and then lands the
 * alignment, as an obligation's arrival lands the words that lead to it
 * (obligations/view.js).
 *
 * The walk runs in script rather than through native `Element.scrollIntoView`: a Range
 * has no native reveal; a sample's native reveal Chromium and Firefox carry into the
 * containing page across its opaque origin; Firefox's `container: "nearest"` still
 * scrolls the boxes around one bounded `within` (notes/browser-support.md, "Native reveal
 * bounded to its scroller"); and a native glide starts before Leaf can count it as the
 * reader's, which let a later reading put the page back (a `t` landing from On me left
 * the page at its top in 2 of 9 runs). It ends at this document's scroller or a fixed
 * box, so a sample never scrolls its containing page, and at `within` where one is given.
 * Every script reveal comes through here: a hand-rolled `scrollTop` sum is one more
 * reading of the band that can disagree with this one (eslint.config.mjs,
 * "architecture/scroll-writes").
 *
 * A landing is the reader's choice of where each box it moves stands (scrolling.js).
 * Count it as it starts, including an instant landing: navigation can change layout
 * in the same task, so its scroll end alone cannot distinguish the landing from
 * anchoring or a clamp before the keeper restores that layout change.
 *
 * A destination the user is on is measured by the box that wears its focus ring
 * (focus.js, `ringBox`), out to the destination's own margins, the ring's room: a
 * playground's choice rings its radio and words together, and a landing that measured
 * the radio left the face's ring cut at its pane's foot. Where that box is longer than
 * its room, the destination is its own box again, so the user still sees the control.
 *
 * A Tab's arrival lands here too, after the browser's own reveal. The browser reveals a
 * focus arrival only when it counts it out of view: Firefox when less than about a line
 * of it shows, on either axis, and Chromium across only when none of it shows; and
 * neither knows the box that wears its ring. So a control partly past a scroller's edge
 * stayed cut there, a link at a wide table's end in both engines, and in Firefox a
 * radio whose box showed whole while its ring was cut. An arrival lands nearest, which
 * moves nothing where its ring already shows, so a control in a stuck header, whose
 * margin counts it as shown, stays put. A marked decision also wears a ring around its
 * own box while Tab is inside it, so the arrival then lands that box nearest too.
 */
import { localScrollBy, scrollAxes } from "./element-frame.js";
import { deepFocus, onCurrentLocation, ringBox } from "./focus.js";
import {
  clippedPlace,
  landingBand,
  placeBox,
  placeHolder,
  scrollContainer,
  seenRect,
  shownBand,
  visualViewport,
} from "./geometry.js";
import { atLayoutPrecision } from "./keeps.js";
import { PAGE_PAINT_ATTRIBUTE, locationStandsDown } from "./page-paint.js";
import {
  glideTo,
  glides,
  pageScroller,
  reachable,
  scrollGoal,
  startScroll,
  stopGlide,
} from "./scrolling.js";
import { hasArea, intersect, nearestScrollBy } from "./rect.js";
import { nextRender } from "./rendering.js";
import { renderedParent } from "./shadow-tree.js";
import { scrollersOf } from "./scroll-containers.js";
import { setScroll } from "./arrivals.js";

/** @typedef {Element | Range} Destination
 * @typedef {import("./rect.js").Box} Box
 * @typedef {"Top" | "Right" | "Bottom" | "Left"} MarginSide
 * @typedef {{box: Element, by: {left: number, top: number}}} Move
 */

// A destination's landing margin on one side. A range has none of its own and takes the
// larger of those of the elements it starts and ends with, so a side list's run of a
// group's label and a tab keeps the room the tab's ring needs (lf-tabs.js, `#showTab`).
/** @param {Destination} where @param {MarginSide} side @returns {number} */
function scrollMargin(where, side) {
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
// `shown`'s box out to `where`'s margins.
/** @param {Destination} shown @param {Destination} where */
function marginBox(shown, where) {
  const box = placeBox(shown);
  const top = scrollMargin(where, "Top");
  const left = scrollMargin(where, "Left");
  return new DOMRect(
    box.left - left,
    box.top - top,
    box.width + left + scrollMargin(where, "Right"),
    box.height + top + scrollMargin(where, "Bottom"),
  );
}

// The boxes a landing scrolls to show `where`, from the nearest out to `within`, this
// document's scroller or a fixed box. A Range starts at the element holding it, which
// may scroll it, and an element at its parent; a fixed element stands still while every
// box around it scrolls, so none of them shows it.
/** @param {Destination} where @param {Element | null} [within] */
function* scrollingBoxes(where, within = null) {
  if (!(where instanceof Range) && getComputedStyle(where).position === "fixed") return;
  for (
    let box = where instanceof Range ? placeHolder(where) : renderedParent(where);
    box instanceof Element;
    box = renderedParent(box)
  ) {
    if (scrollContainer(box)) yield box;
    if (
      box === within ||
      box === pageScroller ||
      getComputedStyle(box).position === "fixed"
    )
      return;
  }
}

// The room a landing has for `where`: on each axis, the least of the visible viewport
// and the landing band of every box that scrolls it, or null where one has none. Each
// box can move the ones inside it, so the room is the bands' sizes rather than their
// overlap where they stand now: a box whole in a pane whose foot is below the window
// fits the pane, which the page can bring up.
/** @param {Destination} where */
function roomOf(where) {
  let { width, height } = visualViewport;
  for (const box of scrollingBoxes(where)) {
    const band = landingBand(box);
    if (!band) continue;
    width = Math.min(width, band.right - band.left);
    height = Math.min(height, band.bottom - band.top);
  }
  return width > 0 && height > 0 ? { width, height } : null;
}

/** @typedef {{width: number, height: number}} Room */
/** @param {DOMRect} box @param {Room | null} room */
const fits = (box, room) =>
  room !== null && box.height <= room.height && box.width <= room.width;

// The element a landing shows of `where` (see the header): the box wearing its ring
// where that box fits the region, and otherwise `where` itself. The fit is the box's
// own, since the ring's room is wanted rather than owed: a joined option group's row
// spans its log's width, and measured with its room it never fit, so the radio landed
// flush with the log's foot instead, the row a float's rounding past it in Firefox.
/** @param {Destination} where @returns {Destination} */
function shownFor(where) {
  const ring = ringBox(where);
  return ring === where || !fits(placeBox(ring), roomOf(ring)) ? where : ring;
}

// The room a landing has for `where`, as a width and a height (`roomOf`).
/** @param {Destination} where */
export function landingRoom(where) {
  return roomOf(shownFor(where)) ?? { width: 0, height: 0 };
}

// Whether `where` and its margins fit the room a landing has for it.
/** @param {Destination} where */
export function fitsWhole(where) {
  const shown = shownFor(where);
  return fits(marginBox(shown, where), roomOf(shown));
}

// Whether `seen`, what the user sees of the margin box `box`, covers it along each axis
// where it fits `room`, and spans the room along one where it is longer (see the
// header).
/** @param {Box} seen @param {Box} box @param {Room} room */
function seesWhole(seen, box, room) {
  /** @param {"top" | "left"} start @param {"bottom" | "right"} end @param {number} size */
  const along = (start, end, size) =>
    atLayoutPrecision(box[end] - box[start]) > atLayoutPrecision(size)
      ? atLayoutPrecision(seen[end] - seen[start]) >= atLayoutPrecision(size)
      : atLayoutPrecision(seen[start]) <= atLayoutPrecision(box[start]) &&
        atLayoutPrecision(seen[end]) >= atLayoutPrecision(box[end]);
  return along("top", "bottom", room.height) && along("left", "right", room.width);
}

// What of `box` a landing can show: all of it but what the boxes between `shown` and the
// nearest box that scrolls it clip, which no landing moves, as a joined option group's
// own edge cuts the ring's room around its row.
/** @param {Destination} shown @param {DOMRect} box @returns {Box} */
function landable(shown, box) {
  const [scroller] = scrollingBoxes(shown);
  return (scroller && clippedPlace(shown, new Map(), box, scroller)) || box;
}

// What the user will see of `seen` once the motions under way in the boxes scrolling
// `shown` land (scrolling.js, `scrollGoal`), and how far they carry it, or null where no
// motion is under way. The boxes inside the outermost box that moves ride with the
// destination, so their cuts stand; that box and those around it read it where the
// motions leave it (geometry.js, `seenRect`).
/** @param {Destination} shown @param {Box} seen */
function seenAhead(shown, seen) {
  const carried = { x: 0, y: 0 };
  /** @type {Element | null} */
  let outer = null;
  for (const box of scrollingBoxes(shown)) {
    const left = scrollGoal(box) - box.scrollTop;
    if (!left) continue;
    const { y: axis } = scrollAxes(box);
    carried.x += left * axis.x;
    carried.y += left * axis.y;
    outer = box;
  }
  if (!outer) return null;
  const inside = document.createRange();
  inside.selectNodeContents(outer);
  return {
    carried,
    seen: seenRect(inside, new Map(), {
      left: seen.left - carried.x,
      top: seen.top - carried.y,
      right: seen.right - carried.x,
      bottom: seen.bottom - carried.y,
    }),
  };
}

/** @param {Destination} where */
export function alreadyShown(where) {
  const shown = shownFor(where);
  const room = roomOf(shown);
  const box = marginBox(shown, where);
  const seen = seenRect(shown, new Map(), box);
  if (!room || !seen) return false;
  const want = landable(shown, box);
  if (!seesWhole(seen, want, room)) return false;
  const ahead = seenAhead(shown, seen);
  if (!ahead) return true;
  const { x, y } = ahead.carried;
  return Boolean(
    ahead.seen &&
    seesWhole(
      ahead.seen,
      {
        left: want.left - x,
        top: want.top - y,
        right: want.right - x,
        bottom: want.bottom - y,
      },
      room,
    ),
  );
}

// How far a box scrolls to put `start`..`end` at `block` in `low`..`high`.
/** @param {number} start @param {number} end @param {number} low @param {number} high @param {ScrollLogicalPosition} block */
const alignBy = (start, end, low, high, block) =>
  block === "start"
    ? start - low
    : block === "end"
      ? end - high
      : block === "center"
        ? (start + end - low - high) / 2
        : nearestScrollBy(start, end, low, high);

// A smooth landing glides scrollTop (scrolling.js, `glides`); a sideways move is
// instant. A box is counted as the reader's only where the landing moves it.
/** @param {Element} box @param {{top: number, left: number}} by @param {ScrollBehavior} behavior */
function land(box, by, behavior) {
  if (by.top && glides(box, behavior)) {
    if (by.left)
      setScroll(box, { left: box.scrollLeft + by.left, behavior: "instant" });
    glideTo(box, box.scrollTop + by.top);
    return;
  }
  stopGlide(box);
  const { scrollTop, scrollLeft } = box;
  setScroll(box, {
    top: scrollTop + by.top,
    left: scrollLeft + by.left,
    behavior: "instant",
  });
  if (box.scrollTop !== scrollTop || box.scrollLeft !== scrollLeft) startScroll(box);
}

// How far a box around the destination's own reading region scrolls to reveal
// `start`..`end` in `low`..`high`: nearest, a start landing promising the opening of one
// longer than the band and an end landing its closing edge.
/** @param {number} start @param {number} end @param {number} low @param {number} high @param {ScrollLogicalPosition} block */
const revealBy = (start, end, low, high, block) =>
  block === "start"
    ? nearestScrollBy(start, Math.min(end, start + high - low), low, high)
    : block === "end"
      ? nearestScrollBy(Math.max(start, end - high + low), end, low, high)
      : nearestScrollBy(start, end, low, high);

// The moves a landing makes (see the header), box by box from `shown` out to `within`
// and before `until`: the destination's own reading region puts `where`'s margin box
// around `shown` at `block` in its landing band, and every other box reveals it there,
// each across at the nearest edge, as far as the box can scroll along its own axes. A
// box reveals what the boxes inside it will show of the destination, through their
// clips rather than their landing bands, so the page brings up the pane a tall item
// fills rather than the item's far end.
// `moved` is how far they carry the destination in the window together, so the move and
// its prediction (`landedBox`) are one reading.
/** @param {Destination} shown @param {Destination} where @param {ScrollLogicalPosition} block
 * @param {{within?: Element | null, until?: Element | null, sideways?: boolean}} [options] */
function movesOf(
  shown,
  where,
  block,
  { within = null, until = null, sideways = true } = {},
) {
  /** @type {Move[]} */
  const moves = [];
  const moved = { x: 0, y: 0 };
  const core = placeBox(shown);
  const rect = marginBox(shown, where);
  const owner = within ? null : (scrollersOf(placeHolder(shown)).next().value ?? null);
  let around = false;
  /** @type {Box | null} */
  let inside = null;
  for (const box of scrollingBoxes(shown, within)) {
    if (box === until) break;
    const band = landingBand(box);
    if (band) {
      // What the boxes inside this one will show of the destination, out to its
      // margins, which are room to leave rather than part of what they clip.
      const at = {
        left: core.left - moved.x,
        top: core.top - moved.y,
        right: core.right - moved.x,
        bottom: core.bottom - moved.y,
      };
      const cut = inside && intersect(at, inside);
      const seen = cut && hasArea(cut) ? cut : at;
      const left = seen.left - (core.left - rect.left);
      const top = seen.top - (core.top - rect.top);
      const right = seen.right + (rect.right - core.right);
      const bottom = seen.bottom + (rect.bottom - core.bottom);
      const axes = scrollAxes(box);
      const across = sideways ? nearestScrollBy(left, right, band.left, band.right) : 0;
      const down =
        box === owner
          ? alignBy(top, bottom, band.top, band.bottom, block)
          : around
            ? revealBy(top, bottom, band.top, band.bottom, block)
            : nearestScrollBy(top, bottom, band.top, band.bottom);
      const by = {
        left: across && localScrollBy(box, { x: across, y: 0 }).left,
        top: axes.y.y ? reachable(box, down / axes.y.y) : 0,
      };
      if (by.left || by.top) {
        moves.push({ box, by });
        moved.x += by.left * axes.x.x + by.top * axes.y.x;
        moved.y += by.left * axes.x.y + by.top * axes.y.y;
      }
      const clip = shownBand(box);
      if (clip) inside = inside ? intersect(inside, clip) : clip;
    }
    around ||= box === owner;
  }
  return { moves, moved };
}

// A centred landing opens a destination taller than its room at its start.
/** @param {Destination} where @param {ScrollLogicalPosition} block */
const placement = (where, block) =>
  block === "center" && !fitsWhole(where) ? "start" : block;

// Where travel's centred landing would leave `where`, so a surface that would stand over
// it there can give way first (floating-panel.js, `clearFor`).
/** @param {Destination} where */
export function landedBox(where) {
  const shown = shownFor(where);
  const box = placeBox(shown);
  const { moved } = movesOf(shown, where, placement(where, "center"));
  return new DOMRect(box.x - moved.x, box.y - moved.y, box.width, box.height);
}

/** @param {Destination | null | undefined} where
 * @param {{alignment?: Destination, behavior?: ScrollBehavior, block?: ScrollLogicalPosition, within?: Element | null, sideways?: boolean}} [options] */
export function scrollIntoView(
  where,
  {
    alignment = where ?? undefined,
    behavior = "auto",
    block = "start",
    within = null,
    sideways = true,
  } = {},
) {
  if (!where || !alignment || !placeHolder(where) || !placeHolder(alignment)) return;
  if (block === "nearest" && alignment === where && alreadyShown(where)) return;
  if (alignment !== where) {
    const [region = null] = scrollingBoxes(alignment, within);
    const shown = shownFor(where);
    for (const { box, by } of movesOf(shown, where, "nearest", {
      within,
      until: region,
      sideways,
    }).moves)
      land(box, by, "instant");
  }
  const shown = shownFor(alignment);
  for (const { box, by } of movesOf(shown, alignment, placement(alignment, block), {
    within,
    sideways,
  }).moves)
    land(box, by, behavior);
}

// A box growing under the user's keystrokes keeps its foot in the band, as the browser's
// caret reveal keeps a caret in its scrollport less the padding, whether or not the user
// already sees it: a row seen whole but growing into the band's clearance moves with each
// keystroke, where one that waited until it passed under the chrome would jump by a line
// and the clearance at once (thread/reply-landing.js, `revealWritingArea`).
/** @param {Destination} where */
export function keepInBand(where) {
  if (!placeHolder(where)) return;
  for (const { box, by } of movesOf(shownFor(where), where, "nearest").moves)
    land(box, by, "instant");
}

// A Tab's arrival (see the header), read once the browser's own reveal has moved.
onCurrentLocation(
  /** @param {Element | null} node @param {string | null} cause */ (node, cause) => {
    if (cause !== "step" || !node) return;
    nextRender(() => {
      if (deepFocus() !== node) return;
      scrollIntoView(node, { block: "nearest" });
      /** @type {Element | null} */
      let box = node;
      for (; box; box = renderedParent(box)) {
        if (!box.matches(`[${PAGE_PAINT_ATTRIBUTE.obligation}]`)) continue;
        if (locationStandsDown(box)) continue;
        scrollIntoView(box, { block: "nearest" });
        break;
      }
    });
  },
);
