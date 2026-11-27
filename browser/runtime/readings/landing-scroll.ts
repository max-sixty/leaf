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
 * Where the glides under way leave the destination is read where they land: each box a
 * glide moves is scrolled to its goal, the destination read, and the box put back in
 * one task (dom/scrolling.js, `whereGlidesLand`), a write and a write back for each.
 *
 * Room and being shown are this module's too, so a landing that asks whether to move
 * reads the same arithmetic the move then does. A destination's room (`landingRoom`) is
 * the least extent, on each axis, of the window and of every landing band clipping it
 * there, less the clearance each region the landing moves leaves at its top, and the
 * destination's own at its foot: what a landing can show of it at once. `fitsWhole`
 * compares it with that room. Where a landing would leave a destination (`landedBox`)
 * is read by the same arithmetic, so a surface that would stand over it there can give
 * way first (panel/floating-panel.js, `clearFor`).
 *
 * Every nearest landing first asks whether the destination is already shown
 * (`alreadyShown`), so one that follows the user, a Tab's arrival, entering a reply or
 * returning to a thread, and one that takes them somewhere, travel and the walks, ask
 * one question: whether the user sees it. They see it whole (dom/geometry.js,
 * `seenRect`, which takes away the box the chrome covers where its motion leaves it, so
 * a control beside the floating panel stays put, and one a view of the panel is opening
 * over is not shown) along each axis where it fits its room, all of it but what the
 * boxes between it and the nearest box that scrolls it clip (`landable`), since no
 * landing moves those. Where the user is on or inside it, they also see its ring's room
 * (see below), cut the same way, unless a nearest landing would move nothing
 * (`landsStill`), as where the room runs past an edge no scroll carries the control
 * away from: a window's side the page can't scroll toward, either end of a strip that
 * stands at that end, or the window's edge around a box fixed in the window, such as
 * the comment box. Where it is taller than its room, a nearest landing's own moves
 * bring no more of it in, so a box taller than the window that the user sees only part
 * of still comes in as far as it fits, and a fold the user goes to opens from its
 * start. Travel and the walks land a destination at its start or centre rather than
 * nearest, and ask the question of that landing (`block`): a box taller than its room
 * is shown there only where that landing would move nothing, so travel to a section the
 * user is reading inside, or to a file of a diff they have read down, still lands its
 * opening. Its edges are compared at layout precision (lib/keeps.js,
 * `atLayoutPrecision`): a box a landing put flush at an edge reads back a float's
 * rounding past it in Firefox, and a reading that counted it unseen would land it again
 * and enter travel's history. A box a glide under way is carrying
 * (scroll-containers.js, `glideTravel`) is shown only where it is seen both where it
 * stands and where that motion will leave it, as a key pressed while the page moves
 * acts as if the motion had landed: `Shift+m` just after `m` finds the obligation `m`
 * is leaving already gone. Only a box growing under the user's keystrokes skips the
 * question, keeping its foot in the band as the browser keeps a caret (`keepInBand`).
 * `sideways: false` keeps every box's sideways place, for a landing that aligns what
 * the user is already reading, such as `g z` and a diff's file.
 *
 * The question asks what the user sees rather than whether a landing would move,
 * because a landing keeps a box further in than the user needs to see it: below the
 * room it keeps under the headers, and above the room it keeps over the floating
 * panel's cover in every column (dom/geometry.js, `footCover`). So a landing would move
 * a box the user already sees there. Where the user doesn't see a ring's room, the
 * landing is asked whether it would move at all, so a control whose room runs past such
 * an edge moves into the band when it stands in the room under the headers or over the
 * panel's cover. A landing also places room an
 * inner box hides, so a row flush with a scrolling pane's end, at the band's edge,
 * moves the page by that room. These paths are rare, and on a rare path the page may
 * move (SOUL.md, "Keep Leaf's code plain"): asking the landing axis by axis kept the
 * first still at the cost of an axis parameter through its moves, and keeping both
 * still takes a model of which edges a scroll can carry a control away from.
 *
 * A landing is the reader's choice of where each box it moves stands (dom/scrolling.js).
 * Count it as it starts, including an instant landing: navigation can change layout
 * in the same task, so its scroll end alone cannot distinguish the landing from
 * anchoring or a clamp before the keeper restores that layout change.
 *
 * A destination the user is on is measured by the box that wears its focus ring
 * (dom/focus.js, `ringBox`), with its own margins, the ring's room: a playground's choice
 * rings its radio and words together, and a landing that measured the radio left the
 * face's ring cut at its pane's foot. Where that box is longer than its room, the
 * destination is its own box again, so the user still sees the control. Every other
 * destination is its own box, without its margins: a landing that takes the user
 * somewhere asks before focus arrives, and a row under a pinned file header, whose top
 * margin is that header's height, is shown where it stands just below it.
 *
 * A Tab's arrival lands here too, after the browser's own reveal. The browser reveals a
 * focus arrival only when it counts it out of view: Firefox when less than about a line
 * of it shows, on either axis, and Chromium across only when none of it shows; and
 * neither knows the box that wears its ring. So a control partly past a scroller's edge
 * stayed cut there, a link at a wide table's end in both engines, and in Firefox a
 * radio whose box showed whole while its ring was cut. An arrival lands nearest, which
 * moves nothing where its ring already shows (`alreadyShown`, out to its margins), so a
 * control in a stuck header the user sees whole stays put, and reads the margins and
 * padding the browser's reveal reads.
 */
import { localScrollBy, scrollAxes } from "../dom/element-frame.js";
import { deepFocus, onCurrentLocation, onUserInput, ringBox } from "../dom/focus.js";
import {
  carried,
  clippedPlace,
  fixedInWindow,
  landingBand,
  placeBox,
  placeHolder,
  scrollContainer,
  seenRect,
  shownWindow,
  visibleBand,
} from "../dom/geometry.js";
import { atLayoutPrecision } from "../lib/keeps.js";
import { scrollMoves } from "../lib/scroll-range.js";
import { glideTravel, scrollersOf, seenGlided } from "./scroll-containers.js";
import {
  glideTo,
  glides,
  pageScroller,
  placeKept,
  scrollGoal,
  startScroll,
  steerGlide,
  stopGlide,
  whereGlidesLand,
} from "../dom/scrolling.js";
import { clippingAxes, nearestScrollBy } from "../dom/rect.js";
import { cancelRender, nextRender } from "../lib/frame-pass.js";
import { renderedParent, renderedUnder } from "../lib/shadow-tree.js";
import { setScroll } from "../dom/arrivals.js";
import type { Box } from "../base/box.js";

type Destination = Element | Range;
type MarginSide = "Top" | "Right" | "Bottom" | "Left";
type ScrollMove = { box: Element; local: number; moved: number; ahead: number };
// The browser snaps a scroll to the device's pixels, so a move asked to travel a
// fraction goes up to a pixel further than asked about half the time. A box held at the
// band's edge, as a growing reply row is (`keepInBand`), would be carried past it by a
// pixel under the user's aim, so its move travels only the whole pixels, leaving it less
// than a pixel short. Every other landing reveals, and keeps the browser's snapping: cut
// short, a target a fraction past an inner scrollport's edge would stay clipped there.
const snappedToward = (from: number, top: number) => {
  const scale = window.devicePixelRatio || 1;
  const snapped = (top > from ? Math.floor : Math.ceil)(top * scale) / scale;
  return top > from ? Math.max(from, snapped) : Math.min(from, snapped);
};

// A smooth landing glides (dom/scrolling.js, `glides`); only the reading band's vertical
// moves are smooth, so it moves only scrollTop. An instant one is the reader's choice
// from its start (`startScroll`), unless it returns them to a place they had (`kept`,
// dom/scrolling.js, `placeKept`). `by.top` counts from `from`: where the box stands, or
// for the reading band's moves where its glide is headed (`readingBandMoves`). An
// instant landing takes the box from a glide under way, even to put it where it
// stands, unless it only moves the box across: that move, as the walk before a
// reading region makes to reveal a box sideways (`innerMoves`), leaves the glide going,
// so the region's landing after it still aims from the glide's goal. Stopped there, a
// sideways reveal pressed during a glide landed from where the page stood. A `held`
// landing keeps a box at the band's edge (`snappedToward`). A glide asks `aim` at each
// frame where the landing now puts the box (dom/scrolling.js, `aimed`), so content drawn
// above the destination after the landing starts, in the same task or during the glide,
// still leaves the destination where the landing puts it.
const land = (
  box: Element,
  by: { top?: number; left?: number },
  behavior: ScrollBehavior,
  {
    kept = false,
    from = box.scrollTop,
    held = false,
    aim,
  }: {
    kept?: boolean;
    from?: number;
    held?: boolean;
    aim?: (() => number | null) | undefined;
  } = {},
) => {
  const asked = from + (by.top ?? 0);
  if (glides(box, behavior)) return glideTo(box, asked, aim);
  const top = held ? snappedToward(from, asked) : asked;
  const { scrollTop, scrollLeft } = box;
  if (by.top || from !== scrollTop) stopGlide(box);
  setScroll(box, { top, left: scrollLeft + (by.left ?? 0), behavior: "instant" });
  if (box.scrollTop === scrollTop && box.scrollLeft === scrollLeft) return;
  if (kept) placeKept(box);
  else startScroll(box);
};

// Whether `where` is still on the page to be landed: in the document and drawing a box,
// since one removed or not rendered reads as an empty box at the window's corner.
function standsOnPage(where: Destination) {
  const { x, y, width, height } = destinationBox(where);
  return Boolean(holderOf(where)?.isConnected && (x || y || width || height));
}

// A destination's landing margin on one side. A range has none of its own and takes the
// larger of those of the elements it starts and ends with, so a side list's run of a
// group's label and a tab keeps the room the tab's ring needs (lf-tabs.js, `#showTab`).
function scrollMargin(where: Destination, side: MarginSide = "Top"): number {
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
function shownFor(where: Destination): Destination {
  const ring = ringBox(where);
  if (ring === where) return where;
  const box = placeBox(ring);
  const room = roomAround(ring, where);
  return box.height <= room.height && box.width <= room.width ? ring : where;
}
// The box a landing has to show of `where` (`shownFor`).
const destinationBox = (where: Destination) => placeBox(shownFor(where));
const holderOf = (where: Destination) => placeHolder(shownFor(where));

// What stands over `holder` in `box`. A sideways scroller restarts the header slot
// without becoming the vertical reading region; `visibleBand` reads the headers outside
// it.
const readingTop = (holder: Element | null, box: Element, band: Box) =>
  visibleBand(box, holder)?.top ?? band.top;

function topMargin(
  where: Destination,
  box: Element,
  band: Box,
  holder: Element | null = holderOf(where),
) {
  return Math.max(scrollMargin(where), readingTop(holder, box, band) - band.top);
}

// The room a landing has for `where`, as a width and a height (see the header). Each box
// bounds the axes it clips. Each region the landing moves also takes the clearance the
// move leaves at its top: the destination's own in the region that lands it, and in each
// region around that, what stands over the inner region's box, as
// `scrollIntoReadingBand` reads it. With `until`, the height is the room for the run
// from `where`'s top to `until`'s foot, which is what a landing at `where`'s start
// promises of a later node; only the boxes holding the whole run bound it.
export const landingRoom = (where: Destination, until?: Element) =>
  roomAround(shownFor(where), where, until);

// The same room for `where` shown as `shown`, the box it or its ring stands in. The
// boxes clipping a range start at the element holding it, and an element's at its parent.
function roomAround(shown: Destination, where: Destination, until?: Element) {
  const holder = placeHolder(shown);
  const regions = new Map<Element, Element | null>();
  let previous = null;
  for (const box of scrollersOf(holder)) {
    regions.set(box, previous);
    previous = box;
  }
  const across = placeBox(shown);
  let { width, height } = shownWindow({ across });
  for (
    let box = shown instanceof Range ? holder : renderedParent(shown);
    box instanceof Element;
    box = renderedParent(box)
  ) {
    const band =
      (!until || until === where || renderedUnder(until, box)) &&
      landingBand(box, across);
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
    if (box === pageScroller || fixedInWindow(box)) break;
  }
  return { width, height };
}

export function fitsWhole(where: Destination) {
  const box = destinationBox(where);
  const room = landingRoom(where);
  return box.height <= room.height && box.width <= room.width;
}

// `where`'s box (`destinationBox`) out to its margins, the ring's room. A negative
// margin, which lets a landing leave a control above the band's top, as one in a stuck
// header (element-marks.css), takes nothing from the box: the user must see all of it.
function marginBox(where: Destination, box: DOMRect) {
  const margin = (side: MarginSide) => Math.max(0, scrollMargin(where, side));
  const top = margin("Top");
  const left = margin("Left");
  return new DOMRect(
    box.left - left,
    box.top - top,
    box.width + left + margin("Right"),
    box.height + top + margin("Bottom"),
  );
}

// What of `out` a landing can show: all of it but what the boxes between `shown` and the
// nearest box that scrolls it clip, which no landing moves, as a joined option group's
// own edge cuts the ring's room around its row. A box that scrolls, as a wide table's
// does sideways, is one a landing moves.
function landable(shown: Destination, out: DOMRect): Box {
  for (
    let box = shown instanceof Range ? placeHolder(shown) : renderedParent(shown);
    box instanceof Element;
    box = renderedParent(box)
  )
    if (scrollContainer(box)) return clippedPlace(shown, new Map(), out, box) || out;
  return out;
}

// Whether `seen`, what the user sees of `want`, covers it along each axis where `box`
// fits `room`. Along an axis where it is longer, the landing's own arithmetic answers
// (see `alreadyShown`), so this asks nothing there.
function seesWhole(
  seen: Box,
  box: DOMRect,
  want: Box,
  room: { width: number; height: number },
) {
  const along = (
    start: "top" | "left",
    end: "bottom" | "right",
    length: number,
    size: number,
  ) =>
    atLayoutPrecision(length) > atLayoutPrecision(size) ||
    (atLayoutPrecision(seen[start]) <= atLayoutPrecision(want[start]) &&
      atLayoutPrecision(seen[end]) >= atLayoutPrecision(want[end]));
  return (
    along("top", "bottom", box.height, room.height) &&
    along("left", "right", box.width, room.width)
  );
}

// Whether the user is on `where` or inside it, so it wears its ring and is measured out
// to the ring's room (see the header).
const ringed = (where: Destination) =>
  where instanceof Element && where.matches(":focus-within, [data-lf-focus-within]");

// `ringed` measures it out to its ring's room before the user is on it, for a choice of
// where focus will land made before it arrives (margin-projection.js, `seenRows`).
export function alreadyShown(
  where: Destination,
  {
    block = "nearest",
    ringed: on = ringed(where),
  }: { block?: ScrollLogicalPosition; ringed?: boolean } = {},
) {
  const shown = shownFor(where);
  const box = destinationBox(where);
  const out = on ? marginBox(where, box) : box;
  // Past the chrome's covers where their motion leaves them, against which a landing
  // places the box, so one a view is opening over counts as covered.
  const seen = seenRect(shown, new Map(), out, true);
  if (!seen) return false;
  const room = landingRoom(where);
  // What the user will see of it where the glides under way leave it
  // (scroll-containers.js, `seenGlided`).
  const travel = glideTravel(shown);
  const ahead = travel && seenGlided(shown, out, travel);
  if (travel && !ahead) return false;
  const { x, y } = travel ?? { x: 0, y: 0 };
  const sees = (want: Box) =>
    seesWhole(seen, box, want, room) &&
    (!ahead ||
      seesWhole(
        ahead,
        box,
        {
          left: want.left + x,
          right: want.right + x,
          top: want.top + y,
          bottom: want.bottom + y,
        },
        room,
      ));
  if (!sees(landable(shown, box))) return false;
  if (box.width > room.width && seen.right - seen.left < room.width) return false;
  const tall = box.height > room.height;
  if (!tall && (out === box || sees(landable(shown, out)))) return true;
  // A box longer than its room is shown where the landing would bring no more of it in,
  // by its own moves: a nearest landing filling its boxes, or as far as they can scroll,
  // and one at its start or centre with its opening at the band's top. One whose ring's
  // room the user doesn't see is shown where a nearest landing would move nothing (see
  // the header).
  return landsStill(where, tall ? block : "nearest");
}

// How far to scroll a box down so that `box`, where `where` stands, lands at `block` in
// `band`, as though the box carried it the whole way.
function placementBy(
  where: Destination,
  box: Box & { height: number },
  block: ScrollLogicalPosition,
  band: Box,
  margin: number,
) {
  const room = band.bottom - band.top;
  const place =
    block === "start"
      ? margin
      : block === "end"
        ? room - box.height - scrollMargin(where, "Bottom")
        : Math.max((room - box.height) / 2, margin);
  return block === "nearest"
    ? nearestScrollBy(
        box.top - margin,
        box.bottom + scrollMargin(where, "Bottom"),
        band.top,
        band.bottom,
      )
    : box.top - band.top - place;
}

// The moves a landing in the reading band makes, region by region from the one
// holding `where` outward: each a box, the local offset it scrolls by from where its
// glide is headed, how far that move carries the destination up the window (`moved`),
// and how far the glide under way in the box has still to scroll it (`ahead`), with
// how far the glides and the moves together carry it (`moved` of the whole).
// Scrolling and its prediction (`landedBox`) both read it, so they can't disagree.
// Every region is read where the glides under way will leave it (dom/scrolling.js,
// `whereGlidesLand`), and its move counts from its glide's goal, since a key pressed
// while the page moves acts where the motion lands: `/` pressed as `d` sets off, in a
// diff whose filter the glide is carrying out of view, brings the filter in as the same
// keys typed slowly do, where a landing read from the page as it stood found it shown
// and left the page stopped mid-way. A region its landing doesn't move goes on gliding.
// A start or centre landing aims at the same place either way.
//
// A region's move carries the destination only until it first stops riding it
// (dom/geometry.js, `carried`), read where the glides leave it, and each region around it
// then finds the destination carried that far. A sidebar's track standing short of
// the line it sticks at rides the page only to that line, so `m` pressed as `d` sets
// off, for an ask in the track, finds it in the window where `d` lands and moves the
// page no further; read as riding the whole glide, the ask left the window above, and
// `m` pulled the page back most of the way. A move past that first stop would scroll
// the text beside the track, to where its own place or its holder's end carries it on:
// a side list stuck beside the item it opens would scroll the item's start away.
function readingBandMoves(
  where: Destination,
  holder: Element | null,
  block: ScrollLogicalPosition,
): { moves: ScrollMove[]; moved: number } {
  const boxes = [...scrollersOf(holder)];
  const shown = shownFor(where);
  const node = placeHolder(shown);
  const from = placeBox(shown);
  const regions = boxes.map((box) => {
    const scale = scrollAxes(box).y.y;
    return { box, scale, ahead: (scrollGoal(box) - box.scrollTop) * scale };
  });
  return whereGlidesLand(boxes, () => {
    const landed = placeBox(shown);
    const moves: ScrollMove[] = [];
    let margin = 0;
    // How far the moves found so far carry the destination up the window.
    let carry = 0;
    let inner: Element | null = null;
    for (const { box, scale, ahead } of regions) {
      const rect = new DOMRect(landed.x, landed.y - carry, landed.width, landed.height);
      const band = landingBand(box, rect);
      if (!band) break;
      let by;
      if (!inner) {
        margin = topMargin(where, box, band);
        by = placementBy(where, rect, block, band, margin);
      } else {
        // An inner scroller restarts its own header slot. Read what covers its box
        // from the enclosing region, rather than reading the destination's reset slot.
        band.top = Math.max(band.top, readingTop(inner, box, band));
        let { top, bottom } = rect;
        if (block === "start") top -= margin;
        else if (block === "end") {
          top = bottom - 1;
          bottom += scrollMargin(where, "Bottom");
        }
        // Preserve a short destination's full extent. A tall one promises its opening
        // and as much as this region can show, rather than demanding its whole height.
        if (block === "start") bottom = Math.min(bottom, top + band.bottom - band.top);
        by = nearestScrollBy(top, bottom, band.top, band.bottom);
      }
      const local = scale === 0 || !node ? 0 : carried(node, box, by / scale);
      moves.push({ box, local, moved: local * scale, ahead });
      carry += local * scale;
      inner = box;
    }
    return { moves, moved: from.top - landed.top + carry };
  });
}

// Where travel's landing (`scrollIntoReadingBand`, centred, as anchor travel lands)
// would leave `where`: in the band where its regions can scroll that far, and short
// of it at a region's end.
export function landedBox(where: Destination) {
  const rect = destinationBox(where);
  const { moved } = readingBandMoves(where, holderOf(where), "center");
  return new DOMRect(rect.x, rect.y - moved, rect.width, rect.height);
}

// A region whose glide already heads where the landing would take it moves no further,
// unless the landing is instant: then the glide lands at once, since an instant landing
// shows its destination now, as a replaced view must, and not at the glide's end. A
// region's glide asks `aim` where the landing now puts it (`landingAim`).
function scrollIntoReadingBand(
  where: Destination,
  holder: Element | null,
  block: ScrollLogicalPosition,
  behavior: ScrollBehavior,
  {
    kept = false,
    held = false,
    aim,
  }: {
    kept?: boolean;
    held?: boolean;
    aim?: (box: Element) => () => number | null;
  } = {},
) {
  const { moves } = readingBandMoves(where, holder, block);
  for (const { box, local, moved, ahead } of moves)
    if (Math.abs(moved) >= 1 || (Math.abs(ahead) >= 1 && !glides(box, behavior)))
      land(box, { top: local }, behavior, {
        kept,
        from: scrollGoal(box),
        held,
        aim: aim?.(box),
      });
}

// Where a landing now puts each box it moves, for the box's glide to ask at each frame
// (dom/scrolling.js, `aimed`), each read afresh as at the landing's start: a reading
// region's move from where the glides under way land, a box the walk inside `within`
// moves from where it stands, and nowhere further for a `nearest` landing whose
// destination is already shown (`alreadyShown`). Null once the destination is removed or
// not rendered (`standsOnPage`).
function landingAim(
  where: Destination,
  aligned: Destination,
  holder: Element,
  {
    block,
    within,
    sideways,
    targetScroller,
  }: {
    block: ScrollLogicalPosition;
    within: Element | null;
    sideways: boolean;
    targetScroller: Element | null | undefined;
  },
): (box: Element) => () => number | null {
  return (box) => () => {
    if (!standsOnPage(where)) return null;
    if (block === "nearest" && aligned === where && alreadyShown(where))
      return scrollGoal(box);
    if (within) {
      for (const move of innerMoves(where, targetScroller, within, sideways))
        if (move.box === box) return box.scrollTop + move.by.top;
      return null;
    }
    const move = readingBandMoves(aligned, holder, block).moves.find(
      (move) => move.box === box,
    );
    return move ? scrollGoal(box) + move.local : null;
  };
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
// A reveal that returns the reader to a place they had, as a restore brings back the
// control they were on, is `kept`: it is no choice of theirs, so a hold on their place
// open meanwhile still keeps it (user-place.js, `holdUserPlace`). Counted as their
// choice, a resize while a diff's new source drew took the hold's correction away and
// left the control they were on 262px down. `including` is a larger destination holding
// the target, such as a run from a group's label to the item, which the landing takes
// in its place where it fits whole (`fitsWhole`), so the label comes in with the item
// where there is room and the item comes in alone where there is not.
export function scrollIntoView(
  target: Destination | null | undefined,
  {
    alignment,
    behavior = "auto",
    block = "start",
    within = null,
    sideways = true,
    kept = false,
    including = null,
  }: {
    alignment?: Destination;
    behavior?: ScrollBehavior;
    block?: ScrollLogicalPosition;
    within?: Element | null;
    sideways?: boolean;
    kept?: boolean;
    including?: Destination | null;
  } = {},
) {
  if (!target) return;
  const where = including && fitsWhole(including) ? including : target;
  const aligned = alignment ?? where;
  const holder = holderOf(aligned);
  if (!holder) return;
  const targetScroller = within ? null : scrollersOf(holder).next().value;
  const aim = landingAim(where, aligned, holder, {
    block,
    within,
    sideways,
    targetScroller,
  });
  // The landing takes the glides under way in the boxes it would move, even where it
  // moves them no further, so each lands this destination rather than the one an
  // earlier landing set it off for.
  const moved = within
    ? [...innerMoves(where, targetScroller, within, sideways)].map(({ box }) => box)
    : scrollersOf(holder);
  for (const box of moved) steerGlide(box, aim(box));
  if (block === "nearest" && aligned === where && alreadyShown(where)) return;
  // Only a box that will move is asked to, as a first tab's ring room at its strip's
  // start moves nothing: a call that moves nothing still reads as a scroll the gesture
  // made (tests/shift_watch.js, "Scrolls a gesture makes").
  for (const { box, by } of innerMoves(where, targetScroller, within, sideways))
    if (by.left || by.top) land(box, by, "instant", { kept, aim: aim(box) });
  if (!targetScroller) return;
  scrollIntoReadingBand(aligned, holder, block, behavior, { kept, aim });
}

// The moves the walk before a destination's reading region makes (`scrollIntoView`),
// each read when the caller asks for it, after it made the last: every box clipping the
// destination reveals it across at the nearest edge, and each inside `targetScroller`
// down too.
function* innerMoves(
  where: Destination,
  targetScroller: Element | null | undefined,
  within: Element | null,
  sideways: boolean,
) {
  // Horizontal inspection can belong to any ancestor, the owning region included.
  // Only inner scrollports prepare Y; the region and its outers glide below.
  let inside = true;
  const start = holderOf(where);
  for (let box = start; box instanceof Element; box = renderedParent(box)) {
    if (box === targetScroller) inside = false;
    // A box that clips without scrolling, as `overflow: clip` does, moves for nothing.
    const destination = destinationBox(where);
    const band = scrollContainer(box) && landingBand(box, destination);
    if (band) {
      const { left, right } = band;
      const byX = !sideways
        ? 0
        : nearestScrollBy(
            destination.left - scrollMargin(where, "Left"),
            destination.right + scrollMargin(where, "Right"),
            left,
            right,
          );
      const byY = inside
        ? placementBy(
            where,
            destination,
            "nearest",
            band,
            topMargin(where, box, band, start),
          )
        : 0;
      yield { box, by: localScrollBy(box, { x: byX, y: byY }) };
    }
    if (box === within || box === pageScroller || fixedInWindow(box)) return;
  }
}

// Whether a landing on `where` at `block` would move no box a pixel or more: neither the
// walk before its reading region, which lands it nearest whatever the block, nor the
// region and those around it (`readingBandMoves`). A pixel, as a scroll write asks
// (lib/scroll-range.js, `scrollMoves`): Firefox stands a strip scrolled to its end a
// fraction past the whole-pixel end its range reads, and a move back by that fraction
// counted the strip's last control unshown however often it landed.
// Each move is read where the destination stands now, which holds while every move
// before it is none, and every one is asked rather than their sum: a pane bringing in
// more of a box while the page carries the pane back leaves the box where it stood,
// and still shows more of it.
function landsStill(where: Destination, block: ScrollLogicalPosition) {
  const holder = holderOf(where);
  const targetScroller = scrollersOf(holder).next().value;
  for (const { box, by } of innerMoves(where, targetScroller, null, true))
    if (
      scrollMoves(box, {
        top: box.scrollTop + by.top,
        left: box.scrollLeft + by.left,
      })
    )
      return false;
  return (
    !targetScroller ||
    readingBandMoves(where, holder, block).moves.every(
      ({ moved }) => Math.abs(moved) < 1,
    )
  );
}

// A box growing under the user's keystrokes keeps its foot in the band, as the browser's
// caret reveal keeps a caret in its scrollport less the padding, whether or not the user
// already sees it: a row seen whole but growing into the band's clearance moves with each
// keystroke, where one that waited until it passed under the chrome would jump by a line
// and the clearance at once (records/thread/reply-landing.js, `revealWritingArea`).
export const keepInBand = (where: Destination) =>
  scrollIntoReadingBand(where, holderOf(where), "nearest", "instant", { held: true });

// A Tab's arrival (see the header), read once the browser's own reveal has moved: at
// the next render, or at the user's next key where that comes first. The key's readers
// then find the page as the same keys typed slowly leave it: a control Tab reached
// under the floating panel, which this landing brings above it, is where the user is
// (user-place.js, `focusPlace`), so Enter pressed before the frame follows it rather
// than letting go of it.
let arrival: { node: Element; render: number } | null = null;
function landArrival(node: Element) {
  arrival = null;
  if (deepFocus() !== node) return;
  scrollIntoView(node, { block: "nearest" });
}
onCurrentLocation((node: Element | null, cause: string | null) => {
  if (cause !== "step" || !node) return;
  cancelRender(arrival?.render);
  arrival = { node, render: nextRender(() => landArrival(node)) };
});
// A pointer press aims where things are drawn, so only a key lands the arrival early.
onUserInput((event) => {
  if (event.type !== "keydown" || !arrival) return;
  cancelRender(arrival.render);
  landArrival(arrival.node);
});
