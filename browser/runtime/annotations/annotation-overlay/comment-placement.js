/* Where a comment's surfaces stand: the comment box the user types in
   (annotations/composing/surface.js) and the thread card the sent comment becomes
   (thread-preview.js). They are one comment at two moments, so one rule places
   both, and Send changes the surface without moving the place. What a reader sees
   them do is stated rule by rule in `placement-rules.json`, beside this module; this
   header says how the code keeps each rule, by its id, and which designs it rejected.
   Floating UI does the placing (floating.js): this module chooses the side and names
   the boxes, and Floating UI's offset, size and shift do the rest.

   A comment stands by what it is about. `clear` is the box it keeps
   clear of, as the page shows it: the paragraph holding a passage, the element, or the
   row a pointing gesture named in it (readings/pointed-place.js). `extent` is that box whole,
   however much of it a scroll has clipped, which is what the room around it is measured
   from. `row` is the first line it stands level with beside `clear`, and `lastRow` the
   last: a passage's first line for both, else `extent`'s top and foot. Both come from
   the unclipped box: the top of a clipped box is the window's edge, and a card level
   with it in the page's plane would be carried by each scroll frame and placed back.
   `column` is the passage's inline start when it quotes words;
   without one, the card's width ends at `clear`'s right edge. Under or over, a card's
   place keeps room for the measure (`--lf-thread-card`), or the boundary's width where
   that is narrower, so where it would carry the card past the boundary's right edge it
   starts further left rather than narrowing (`place-under-or-over`). A slim box or card
   stands at the end of that place nearer the quoted words' first character, or nearer
   the element's right edge on a whole element, and widens toward the other end, so the
   comment box stands where its card will. `margin` is where
   across the page the margin row for it stands,
   or would stand in the rail once its thread is sent (margin-layout.js, `marginSpot`),
   or nothing where no row stands and its rows would be pins. A caller requesting
   window placement without a visible attachment supplies `clear: null` and stands
   at its upper inline edge through the same sizing and placement machinery.
   A target that is not drawn has no attachment: seated surfaces withhold their native
   editing state until it returns. An explicit open can request the unanchored window
   posture while retaining the hidden subject as its semantic anchor. A drawn target's
   geometry may have zero area; its whole extent still supplies the fallback seat.
   The comment box is solved again at each scroll, as the card is
   (`composing/floating-response.js`).

   Both stand in one boundary (`commentBoundary`), the room the rules' `room-*` rows
   give: the part of the window the page shows, within the region whose flow holds the
   pointed row, else the target, where that region holds a card, else within the page
   shell. That region is the box that scrolls the row (`scrollerFor`), unless the row
   is in a bounded block; then it is the box that scrolls the block (margin-layout.js,
   `flowOf`), which also decides where the row's margin row stands, so the card and the
   row follow one rule. The boundary's `cut` holds the region's edges and each edge of
   a block around the row that the row has crossed (`scroll-cut`). The cut never bounds
   the room, so a crossed edge never moves the card (`scroll-with-text`). A region in
   flow scrolls nothing itself, so a surface on words in a pane the page scrolls stands
   in the page, or in whatever box scrolls that pane; which boxes scroll is the
   stylesheet's to say (readings/reading-regions.js). Rejected: the
   block that scrolls the row, which capped a card on a log row at the log's height and,
   once a short log filled, moved its card from the rail into the log. Also rejected:
   the innermost reading region around the row, whether or not it scrolled, which
   stopped a card on words in a pane the page scrolls at that pane's foot while the
   window had room; the innermost box with rows to scroll, which stood a comment in a
   workspace pane whose rows all show over the pane beside it; and the region that
   scrolls the target, which stood a comment pointed at a row deep in a pane that is
   itself the target over the pane beside it.

   `commentSide` chooses the side (`side-order`, `side-under-or-over`) for the thread's
   footprint rather than the box's, so the box stands where its card can, and counts
   what the reading region can still scroll toward a side's room. A touch screen
   prefers under because Leaf cannot read where the platform's selection menu stands.
   `commentPlacement` holds the side (`side-held`) until the boundary's `key` or
   `extent`'s width changes.

   On every side it stands clear of what it is about by `subjectGap` (`place-clear`).
   Beside (`place-beside`), message width takes priority over keeping the margin row
   clear: where clearing it would narrow the message, the surface stands over the row,
   and the card carries its own close and step controls, so the row shows again once
   it closes. Neither choice reads the surface's own width or height, so the box and
   the card make the same one. Under or over (`place-under-or-over`), its place
   follows `column`, independently of the block it keeps clear. That clearance chooses
   the initial seat. Once seated, quoted
   words carry both coordinates through scrolling, including out of view, even when the
   containing scrollport stays still (`scroll-with-text`). Held offsets use the
   passage's line and column, so renewing the seat cannot put it back beside a
   stationary scrollport.

   It grows away from what it is about (`size-grows-away`; floating.js, `held`).
   Floating UI's shift keeps it inside the boundary (`scroll-held-in`), and its limiter
   lets it leave beside with `row` or `lastRow`, whichever the scroll carries away, or
   with `clear` under or over; held in beside an element whose top has scrolled away,
   it stands in the window's plane. Arrival and departure use this same attachment
   limit, including the first placement: an offscreen target carries its surface into
   view as scrolling approaches it. A surface that outgrows the room on its side slides
   inside the boundary, over its passage or element if it must, and once it fills the
   boundary scrolls its own content. Only `makeRoom` scrolls, for a card opening under
   or over its target (`size-page-still`). A surface is opening until it first
   stands. The first move Leaf then starts in its scroller before any later input
   (dom/scrolling.js, `scrollStarts`) opens it once more, until it stands again. A walk
   opens its card before its landing brings the card's words in from beyond the
   window, so the card makes its room again where that landing leaves them, on the
   side it chose. A scroll a later input makes, or one Leaf doesn't start, such as a
   keeper holding the reader's place, makes no room, so a card growing as an answer
   arrives never moves the page.

   A surface keeps one line of itself still as its content changes (`keeps`), in
   client pixels from the rule's line: `row` beside, and under or over the edge of
   `clear` it stands clear of, so a reflow of what it is about carries it. The line is
   its top, its foot, or a line of its own, which stands as far above its foot as the
   surface says (`under`). What stands over the kept line grows the surface up, and
   what stands under it grows it down: the card's reply box keeps its top that way as
   a turn joins the transcript above it and as the words typed in it wrap. A surface
   keeping its top has the room below that top, and any other the room above its
   foot, which stands as far below the kept line as what is under the line reaches.
   So what stands over the line scrolls once the surface's top meets the boundary's,
   and the boundary's foot lifts the surface, line and all, once what stands under
   the line passes it.

   A held surface grows no taller than that room, or than the tallest it has stood
   since the rule's line last moved (`fit`'s `stood`), whichever is more
   (`size-room`). The tallest is of what stood over its own line, with what stands
   under that line now, so a surface the boundary's head holds in, as one beside a
   tall element scrolled part out of the window is, still grows down as its user
   types, and a line taken from the draft gives its height back rather than room to
   the transcript, which would move the line. What joins it under its line never
   stands it taller than the room, unless it has stood that tall: in a card that
   fills the room, the transcript gives way to the draft and the line rises. One
   that `rises` (`size-rises`, decided in thread-preview.js)
   holds its top but has the boundary's whole height, so the boundary
   lifts it as it outgrows the room below; its held top is the spot before that lift,
   so shrinking brings it back down to where it stood. Against
   the window's foot the boundary keeps a card's foot, so content that shrinks it, a
   rewrite opening over long words, a fold, an edit, lowers its top, and growing back
   raises it again to where it stood. A scroll moves the line and keeps only the
   height the card stands at. Its top rising this way also lets a reply drafted after
   shorter words were saved grow the card back up the page. Rejected: keeping only the
   height it last stood at, which made every shrink at the foot permanent, so an
   unchanged rewrite closed as a clipped scrolling box; holding its top where the
   window had kept it as it shrank, which a press holding its foot undid; and a floor
   in the rewrite for that one cause of shrinking.

   The comment box's frame reserves its card's head and reply rows around the editor,
   unpainted, and the boundary holds all of it, as it holds the card, so the card Send
   grows out of the field (annotation-chrome.css) stands where the frame stood and no
   word moves. Near the window's foot the field therefore rises while room still shows
   below it. Rejected: letting the reserved row the box grows toward stand past the
   window's edge, which kept the words still while typing but moved them at
   Send by that row; and painting the frame as the card while it is written,
   which left Send nothing to grow.

   Send hands the editor's frame to the card (`adopt`). Its next choice keeps the
   frame's side, the inline edge it held and where that edge stood, where the boundary
   still matches, and returns its block offsets for the card to hold. The attachment is then the card's current one:
   scrolling retains it, while a boundary or target-width change chooses afresh.
   A surface the user carries by its grip (surface-grip.js) adopts its own dropped frame
   the same way, marked `moved` (`place-carried`). A moved surface carries its inline offset on every
   side, the left included, and its attachment limit stretches to take in the spot it
   was dropped at, so it stands there and still leaves with what it is about.

   The card's preview (`thread-preview.js`) chooses the edge to preserve.
   This solver knows only its physical attachment and landed rectangle. Focus and
   transcript landing at Send belong to `records/thread/reply-landing.js`; width retention
   belongs to the preview's lifetime (`thread-preview.js`).

   Every box here is a client rectangle. Floating UI works in the surface's positioning
   space, which a transformed ancestor scales, so each length crosses by the reference's
   scale, and `fit` is handed lengths in that space, as CSS sizes the surface in it. */

import { scrollAxes } from "../../dom/element-frame.js";
import { visibleTargetParts } from "../../readings/visible-target-parts.js";
import {
  carried,
  shellRight,
  shownWindow,
  visualViewport,
  shownExtent,
  shownParts,
  shownRect,
  shownRectHeld,
} from "../../dom/geometry.js";
import { markRoom } from "../../readings/mark-room.js";
import { clamp, union } from "../../dom/rect.js";
import {
  glideBy,
  gliding,
  moveScrollerBy,
  pageScroller,
  scrollStarts,
  whereGlidesLand,
} from "../../dom/scrolling.js";
import { inputs } from "../../base/inputs.js";

import { scrollerFor } from "../../readings/reading-regions.js";
import { pointBand } from "../../readings/pointed-place.js";
import { flowOf, marginSpot } from "./margin-layout.js";
import { floatingGeometry, positioningScale } from "./floating.js";

// One fresh mechanical reading for the editor and the card it becomes. Resolving the
// durable subject or passage remains with the caller; both surfaces read its boxes here.
/** @typedef {import("../../base/box.js").Box} Box */
/** @typedef {Box & {width: number, height: number}} Extent */
/** @typedef {Pick<Box, "left" | "right">} Columns */
/** @typedef {import("@floating-ui/dom").Side} Side */
/** @typedef {import("@floating-ui/dom").MiddlewareState} MiddlewareState */
/** @typedef {import("@floating-ui/dom").ComputePositionReturn} Position */
/** @typedef {readonly [number, number, number, number]} BoundaryKey */
/** @typedef {DOMRectReadOnly & {holders: {top: Element | null, bottom: Element | null}}} Room */
/** @typedef {Room & {across: (columns: Columns | null) => Room,
 * cut: Box | null, scroller: Element, key: BoundaryKey}} Boundary */
/** @import { CapturedPlacement } from "../../records/thread/destination.js" */
/** @typedef {{box: Extent, placement: CapturedPlacement}} AdoptedFrame */
/** @typedef {{top: number, height: number, under: number}} HeldBox */
/** @typedef {{clear: Extent | null, room?: MarkRoom, row: number, lastRow?: number,
 * column?: number | null, margin?: Columns | null, boundary: Boundary,
 * fit: (room: {side: Side, width: number, height: number, room: DOMRectReadOnly,
 * stood: number, stationary: boolean,
 * scale: {x: number, y: number}}) => void,
 * keeps?: "top" | "foot" | "line", under?: (() => number) | null,
 * rises?: boolean}} PlacementRequest */
/** @typedef {{reference: DOMRect,
 * placement: import("@floating-ui/dom").Placement,
 * middleware: import("@floating-ui/dom").Middleware[],
 * plane: (answer: Position) => "page" | "window" | Element}} PlacementOptions */
/** @typedef {import("../../readings/mark-room.js").MarkRoom} MarkRoom */
/** @typedef {{element: Element, clear: Extent, extent: Extent, room: MarkRoom}} Clearance */
/** @typedef {{element: Element, contextNode: Node,
 * geometry: ReturnType<typeof floatingGeometry>, clear: Extent | null, extent: Extent, room: MarkRoom,
 * row: number, lastRow: number, column: number | null,
 * margin: ReturnType<typeof marginSpot>, scroller: Element}} Attachment */
/** @typedef {{target: Element | null, point?: Element | null,
 * passage?: {range?: Range, contextNode?: Node | null, attachment?: Extent | null} | null,
 * boundary?: ReturnType<typeof commentBoundary> | null}} AttachmentRequest */
// What a surface attached to `target`, or to the row `point` names in it, stands clear
// of (`clear`) and beside (`extent`), read where the page stands; null where the target
// isn't drawn. A surface making its room reads this alone (`makeRoom`).
/** @param {Element} target @param {Element | null} [point] @returns {Clearance | null} */
export function attachmentClearance(target, point = null) {
  if (!visibleTargetParts(target).length) return null;
  const clips = new Map();
  const shown = union(
    shownParts(target)
      .map(/** @param {Element} part */ (part) => shownRect(part, clips))
      .filter((box) => box !== null),
  );
  const whole = shownExtent(target) ?? target.getBoundingClientRect();
  const extent = point ? pointBand(whole, point) : whole;
  return {
    element: point ?? target,
    clear: point ? extent : (shown ?? whole),
    extent,
    room: markRoom(target, whole, COMMENT_GAP),
  };
}
/** @overload @param {AttachmentRequest & {target: null}} options @returns {Attachment} */
/** @overload @param {AttachmentRequest & {target: Element}} options @returns {(Attachment & {clear: Extent}) | null} */
/** @overload @param {AttachmentRequest} options @returns {Attachment | null} */
/** @param {AttachmentRequest} options @returns {Attachment | null} */
export function commentAttachment({
  target,
  point = null,
  passage = null,
  boundary = null,
}) {
  // A detached draft keeps its original semantic coordinate and uses the existing
  // unanchored window posture. A window seat is geometry, never a replacement anchor.
  if (!target) {
    const element = document.documentElement;
    const extent = boundary ?? commentBoundary();
    return {
      element,
      contextNode: element,
      geometry: floatingGeometry([element]),
      clear: null,
      extent,
      room: NO_ROOM,
      row: extent.top,
      lastRow: extent.top,
      column: null,
      margin: null,
      scroller: pageScroller,
    };
  }
  // If the target is not drawn, a seated editor or card must withhold until it
  // returns; an explicit Resume can request the window posture above without changing
  // that target. A drawn target may have a zero-area box, as an SVG line does, and
  // still supplies the geometry fallback below.
  const near = attachmentClearance(target, point);
  if (!near) return null;
  const { element, extent } = near;
  const context = point ?? passage?.contextNode ?? target;
  return {
    ...near,
    contextNode: context,
    geometry: floatingGeometry([element, context]),
    row: (passage?.attachment ?? extent).top,
    lastRow: passage?.attachment ? passage.attachment.top : extent.bottom,
    column: passage?.attachment?.left ?? null,
    margin: marginSpot(target, point, passage?.range),
    scroller: scrollerFor(element),
  };
}

// The clear box chooses the initial seat; quoted words carry that seat through
// scrolling on every side, including under or over their stationary scrollport.
/** @param {Attachment} place @param {DOMRectReadOnly} reference */
export function commentReference(place, reference) {
  return {
    contextElement: place.element,
    contextNode: place.contextNode,
    geometry: place.geometry,
    getBoundingClientRect: () => reference,
  };
}

// The gap a surface keeps from the edge of its room, and beside its text, from above
// the text's first line.
export const COMMENT_GAP = 8;
// The room no mark takes, round a surface with no subject.
/** @type {MarkRoom} */
const NO_ROOM = { left: 0, top: 0, right: 0, bottom: 0 };
// The least room a surface stands in: a floor chosen to hold the comment box's words
// and its controls over a few lines, which the room under the words must reach for a
// touch screen to prefer it, and a reading region must show for a surface to stand in it.
export const LEAST_HEIGHT = 96;
/** @type {readonly ("x" | "y")[]} */
const AXES = ["x", "y"];

// The room both surfaces stand in: the part of the window the page shows, within the
// shown bounds of the region whose flow holds the surfaces' row (`flowOf` the box that
// scrolls the row, `scroller`), where those hold the card's minimum width and the least
// height, else within the page shell, whose right edge stops short of the root
// scrollport's gutter and, for the comment box, an open panel's left edge (`right`). A
// pane a resize narrowed, or a short strip of one a scroll left, so yields to the window,
// which carries the surface rather than withdrawing a draft the user is writing. The
// boundary names the box that scrolls that room (`scroller`), which makes room for a
// surface, and the edges that cut the card (`cut`), or null where none do: the
// region's, and each edge of a bounded block around the row that the attachment `at`
// (the row's line and column) has crossed. Its top cuts once the card's own top, a gap
// above the line, has passed it, so the cut grows from nothing. Crossing an edge cuts
// the card and never moves it: bounding the room there pushed a card hanging past a
// log's foot up over its row once the row's line passed the foot. Its
// `key` is what holds the side (`choose`): the window's edges, or the region's whole box
// size and the window's, since a scroll of the page moves and clips a region's shown
// bounds without changing the room it has, and a resize changes it.
// It spans every column the surface could stand in, so the side is chosen from it;
// `across(columns)` is the same room for a surface standing in those columns, where
// chrome beside them, such as the floating panel's row under the page column, takes
// none of its height (`shownWindow`). Each room names the box holding its top and its
// foot (`holders`): the region, or a box whose band clips the region there
// (`shownRectHeld`), where that edge cuts the room further in than the window and the
// chrome's covers alone do, and null where they bound it.
/** @param {{scroller?: Element | undefined, at?: {x: number, y: number} | null}} [options] @returns {Boundary} */
export function commentBoundary({ scroller = pageScroller, at = null } = {}) {
  /** @param {Partial<Box> & {holders?: import("../../dom/geometry.js").Holders}} within */
  const room = (within) => {
    /** @param {Columns | null} columns @returns {Room} */
    const across = (columns) => {
      const shown = shownWindow({ within, gap: COMMENT_GAP, across: columns });
      const held = within.holders;
      if (!held) return Object.assign(shown, { holders: { top: null, bottom: null } });
      const open = shownWindow({ gap: COMMENT_GAP, across: columns });
      return Object.assign(shown, {
        holders: {
          top: shown.top > open.top ? held.top : null,
          bottom: shown.bottom < open.bottom ? held.bottom : null,
        },
      });
    };
    return Object.assign(across(null), { across });
  };
  const { blocks, flow } = flowOf(scroller);
  const bounds = flow !== pageScroller ? shownRectHeld(flow, new Map()) : null;
  const region = bounds ? { bounds, room: room(bounds) } : null;
  const inRegion =
    region &&
    Math.ceil(region.room.width) >= Math.ceil(cardMinimum()) &&
    region.room.height >= LEAST_HEIGHT
      ? region
      : null;
  const cut = inRegion
    ? {
        left: inRegion.bounds.left,
        top: inRegion.bounds.top,
        right: inRegion.bounds.right,
        bottom: inRegion.bounds.bottom,
      }
    : { left: -Infinity, top: -Infinity, right: Infinity, bottom: Infinity };
  if (at)
    for (const block of blocks) {
      const shown = shownRect(block, new Map());
      if (!shown) continue;
      if (at.y - COMMENT_GAP < shown.top) cut.top = Math.max(cut.top, shown.top);
      if (at.y > shown.bottom) cut.bottom = Math.min(cut.bottom, shown.bottom);
      if (at.x < shown.left) cut.left = Math.max(cut.left, shown.left);
      if (at.x > shown.right) cut.right = Math.min(cut.right, shown.right);
    }
  const shell = inRegion ? inRegion.room : room({ right: shellRight() });
  const whole = inRegion ? flow.getBoundingClientRect() : shell;
  /** @type {BoundaryKey} */
  const key = inRegion
    ? [whole.width, whole.height, visualViewport.width, visualViewport.height]
    : [whole.left, whole.top, whole.right, whole.bottom];
  return Object.assign(shell, {
    cut: inRegion || Object.values(cut).some(Number.isFinite) ? cut : null,
    scroller: flow,
    key,
  });
}

/** @param {BoundaryKey} a @param {BoundaryKey} b */
const sameBoundary = (a, b) =>
  Math.abs(a[0] - b[0]) <= 0.5 &&
  Math.abs(a[1] - b[1]) <= 0.5 &&
  Math.abs(a[2] - b[2]) <= 0.5 &&
  Math.abs(a[3] - b[3]) <= 0.5;

/** @param {Side | null} side */
const vertical = (side) => side === "top" || side === "bottom";

// How far, in viewport pixels, scrolling `scroller` toward the end that brings room in
// on `side` carries `element` before it first stops riding (dom/geometry.js, `carried`).
// The browser scrolls in local CSS pixels, which the scroller's transformed axis
// projects; an inverted axis reverses which local end brings room in on that side.
/** @param {Side} side @param {Element} scroller @param {Element} element */
function roomTravel(side, scroller, element) {
  const projection = scrollAxes(scroller).y.y;
  const way = (side === "top" ? -1 : 1) * Math.sign(projection);
  return Math.abs(carried(element, scroller, way * scroller.scrollHeight) * projection);
}

// The room on `side` of `extent` the page can make: what shows there plus the room a
// scroll of `scroller` brings in (`roomTravel`), never more than the boundary holds.
// It is read where the page stands, not where a glide under way would leave it: a
// walk's card chooses its side before the walk's own landing moves the page, and a
// side read where an earlier glide was headed opened `t`'s card, pressed as `m` set
// off, on the other side of its passage, which the walk's landing then left out of
// the window.
/** @param {"top" | "bottom"} side @param {Extent} extent @param {MarkRoom} room @param {Boundary} boundary @param {Element} scroller @param {Element} element */
function reachableRoom(side, extent, room, boundary, scroller, element) {
  const gap = subjectGap(room, side);
  const shown =
    side === "top"
      ? extent.top - boundary.top - gap
      : boundary.bottom - extent.bottom - gap;
  return {
    shown,
    reachable: Math.max(
      0,
      Math.min(
        boundary.height - extent.height - gap,
        shown + roomTravel(side, scroller, element),
      ),
    ),
  };
}

// Scrolls `scroller` to make the room a surface `height` tall needs on `side` of what it
// is about, under or over it, as far as the scroller travels; whether it asked for a
// move. `read` reads what the surface stands clear of (`attachmentClearance`) where the
// page stands: null while its subject isn't drawn, and false once the surface has
// closed. Where the subject's `extent` and this surface cannot show together, no scroll
// makes that room. The boundary then holds the
// surface over its subject instead of scrolling the subject away. The room is read where
// the scroller is headed (dom/scrolling.js, `whereGlidesLand`), as a key pressed while the
// page glides acts as though the glide had landed. A glide under way takes the room
// into its goal and reads it again at each frame, though the room asks for no move yet
// (dom/scrolling.js, `glideBy`), so the page lands once, with the room made, wherever layout
// moves the subject meanwhile. The move carries `clear` only until its `element` first
// stops riding it (dom/geometry.js, `carried`), so a subject in a sticky box the scroll can't
// carry asks for no move.
/** @param {"top" | "bottom"} side @param {() => Clearance | null | false} read @param {number} height @param {Boundary} boundary @param {Element} scroller */
export function makeRoom(side, read, height, boundary, scroller) {
  // The move left to make, read with the scroller where it stands.
  const further = () => {
    const near = read();
    if (near === false) return null;
    if (!near) return 0;
    const { clear, extent, room, element } = near;
    const gap = subjectGap(room, side);
    const projection = scrollAxes(scroller).y.y;
    if (!projection || extent.height + gap + height > boundary.height) return 0;
    const overflow =
      side === "top"
        ? boundary.top - (clear.top - gap - height)
        : clear.bottom + gap + height - boundary.bottom;
    if (overflow <= 0.5) return 0;
    return carried(
      element,
      scroller,
      ((side === "top" ? -1 : 1) * overflow) / projection,
    );
  };
  const by = whereGlidesLand([scroller], further) ?? 0;
  const asks = Math.abs(by * scrollAxes(scroller).y.y) > 0.5;
  if (gliding(scroller)) {
    glideBy(scroller, further);
    return asks;
  }
  if (!asks) return false;
  const before = scroller.scrollTop;
  moveScrollerBy(scroller, by);
  return scroller.scrollTop !== before;
}

// The side a comment's surface takes, as a Floating UI side.
/** @param {{clear: Extent, extent: Extent, room: MarkRoom, boundary: Boundary, width: number, scroller: Element, element: Element, coarse: boolean}} reading @returns {Side} */
export function commentSide({
  clear,
  extent,
  room,
  boundary,
  width,
  scroller,
  element,
  coarse,
}) {
  /** @param {number} space */
  const fits = (space) => Math.ceil(space) >= Math.ceil(width);
  if (fits(boundary.right - clear.right - subjectGap(room, "right"))) return "right";
  if (fits(clear.left - boundary.left - subjectGap(room, "left"))) return "left";
  const below = reachableRoom("bottom", extent, room, boundary, scroller, element);
  const above = reachableRoom("top", extent, room, boundary, scroller, element);
  // Prefer a side that already shows the compact surface. Reachable room breaks
  // the tie; a fresh card may then use makeRoom to open clear of its target.
  const fitsBelow = below.shown >= LEAST_HEIGHT;
  const fitsAbove = above.shown >= LEAST_HEIGHT;
  if (fitsBelow !== fitsAbove) return fitsBelow ? "bottom" : "top";
  if (coarse && below.reachable >= LEAST_HEIGHT) return "bottom";
  return below.reachable > above.reachable ||
    (below.reachable === above.reachable && below.shown > above.shown)
    ? "bottom"
    : "top";
}

// The minimum width chooses the side: a side whose room holds less stands nothing. The
// measure is the widest a box or card stands (`size-width`), and decides whether
// clearing the margin row would sacrifice it. `commentPlacement` reads both, so the comment box and its sent
// card share the same placement rule.
/** @param {string} name */
const rootLength = (name) =>
  parseFloat(getComputedStyle(document.documentElement).getPropertyValue(name));
export const cardMinimum = () => rootLength("--lf-thread-card-min");
export const cardMeasure = () => rootLength("--lf-thread-card");
// Where `size-width` widens a card by its text: a block of words wider than it is tall
// reads at a glance at the least width; a taller one reads as a column, which the
// measure's lines halve. The shape needs no constant, so it follows the card's width
// and face (thread-preview.js records the choice).
/** Whether any of `texts`, laid out at the width it stands at, stands taller than wide.
 * @param {Iterable<Element>} texts */
export const standsTall = (texts) => {
  for (const text of texts) {
    const style = getComputedStyle(text);
    const height =
      text.scrollHeight -
      parseFloat(style.paddingTop) -
      parseFloat(style.paddingBottom);
    const width =
      text.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
    if (height > width) return true;
  }
  return false;
};
// How far a surface on `side` stands from what it is about (`place-clear`): the room the
// marks round it take past its box on that side (the attachment's `room`, readings/mark-room.js
// `markRoom`), their gap and band and any reach over a list marker, then the gap the
// surface keeps from the edge of its room, so the mark's line and the surface's edge
// have that gap between them too. It holds whether or not a mark shows, since one
// comes and goes under the pointer and the surface stays where it stands.
/** @param {MarkRoom} room @param {Side} side */
export const subjectGap = (room, side) => room[side] + COMMENT_GAP;

// The block edge a surface on `side` is attached by, which it keeps still as it grows
// unless asked to keep another line (`keeps`): its foot above what it is about, its top
// elsewhere.
/** @param {Side} side @returns {"top" | "foot"} */
export const attachedEdge = (side) => (side === "top" ? "foot" : "top");

/* One surface's placement: the side it holds and its inline attachment.

   `choose` holds a side, choosing one where none is held or the boundary or `extent`'s
   width has changed, and says whether it chose afresh, and whether the surface is
   opening (`opening`). `options` then gives
   `computePosition` the reference to stand by, its placement and its middleware.
   `landed` takes the answer's inline start and where the rule stood the surface's top
   and foot before the boundary shifted it in, from the rule's line. `options` keeps
   the requested line of that rectangle (`keeps`); `landed` returns the surface's `scale`. `plane` names
   the constraint that bound the answer (floating.js): `"page"` where the rule's line
   holds the surface, and where the boundary shifted it in, the edge it stands against
   and that edge's client line.
   `forget` drops the side so the next placement chooses again, and `scrolled` keeps it
   across the scroll the surface itself asked for (`makeRoom`).

   `capture` is an opaque reading carried inside the editor's frame, whose `box` is a
   client rectangle. `adopt(frame)` queues that handoff for the next `choose`, which
   reports `adopted` until `landed` confirms a position.
   A superseded computation retains that hold. The placement owns its carried inline
   offset, of the edge it holds from the passage's column, else `clear`'s left edge. That column moves with
   quoted words even when their scrollport stays still. A normal beside landing owns
   the same offset, so renewing placement follows the attachment native motion carries.
   `keeps` supplied to `options` names the line the surface keeps still, relative to
   the passage's line when quoted, else the initial side's clearance edge. Without
   one, the landed seat keeps its growing surface's foot above and top elsewhere, so
   an editor needs no transcript reading to keep its attachment while typing; before
   that landing, an adopted frame's offsets are the ones held. `under` reads, at each
   placement and landing, how far above its foot the surface's own line stands, in
   client pixels, whichever line it keeps, so the line it keeps next is known from
   its last landing. `rises` offers a surface
   keeping its top the boundary's whole height for `fit`, rather than the room below.

   `fit({ side, width, height, room, stood, scale, stationary })` sizes the surface for the room its
   side gives, in its positioning space; `room` is the client rectangle that room stands
   in, the boundary across the surface's columns (`commentBoundary`, `across`); `stood`
   is the height a held surface caps no lower than, or 0. `stationary` says its
   attachment line has not moved since its last landing. Its width is limited only by the
   boundary, never by its passage's column.

   A surface narrower than the measure, as the box and a slim card are, widens with its
   words away from the inline edge the placement holds (`holds`, `size-width`), in the
   same way wherever it stands: beside its subject, the edge facing it; under or over,
   the end of its place nearer the quoted words or the element's right edge, a place
   that reserves the measure's width (`place-under-or-over`); carried, its left edge
   where the user dropped it; with nothing to stand by, the room's left edge. So a
   change of its room moves its far edge and never carries it across the words it
   comments on. Held by the edge its words end at, its words move as it widens: its
   right edge in a left-to-right page, as left of its subject, and its left edge in a
   right-to-left one, as right of its subject, under quoted words or carried. A first
   line typed into the box then slides the words before the caret toward its start,
   and a card's one widening moves its words where elsewhere it moves its far
   controls.

   Rejected: holding the edge its words start at. Left of its subject, or under words
   its place starts left of, a slim surface held that way would stand apart from them,
   so it took the measure at once and opened much wider than beside a paragraph, which
   the user saw as an inconsistency. Also rejected: standing a slim surface at its
   place's start everywhere, which keeps its words still but stands a box left of its
   subject as far from it as the measure has width to spare. Choosing the edge facing
   the subject over that design was an agent's call. */
export function commentPlacement() {
  /** @type {Side | null} */
  let side = null;
  /** @type {number | null} */
  let inline = null;
  /** @type {{unanchored: boolean, boundary: BoundaryKey, left: number, right: number} | null} */
  let input = null;
  /** @type {AdoptedFrame | null} */
  let pending = null;
  /** @type {number | null} */
  let carriedInline = null;
  /** @type {HeldBox | null} */
  let initialHold = null;
  // Whether the user carried the surface to where it stands (surface-grip.js).
  let moved = false;
  // Where the rule last stood the surface: its top in client pixels from the
  // attachment line, its height, and how much of it stood under its own line.
  /** @type {HeldBox | null} */
  let held = null;
  // The tallest the surface, and what stands over its own line, have each stood since
  // the rule's line last moved, and that line.
  /** @type {{whole: number, over: number, line: number} | null} */
  let tallest = null;
  // How much of the surface stands under its own line, as the last request reads it
  // (`under`), which each landing records.
  /** @type {(() => number) | null} */
  let underLine = null;
  // The input that opened the surface, and how many moves Leaf had started in its
  // scroller when it opened or last made room, until that input's landing reopens it.
  /** @type {{input: number, starts: number} | null} */
  let opened = null;
  // Whether that landing has reopened the surface, and no placement has stood it
  // since.
  let reopened = false;
  // The inline edge the placement holds the surface by, chosen with its side and held
  // with it, so words carried across their place's middle by a sideways scroll never
  // swap it.
  /** @type {"left" | "right" | null} */
  let holds = null;
  const forget = () => {
    side = null;
    holds = null;
    inline = null;
    input = null;
    opened = null;
    reopened = false;
    pending = null;
    carriedInline = null;
    initialHold = null;
    moved = false;
    held = null;
    tallest = null;
    underLine = null;
  };
  /** @param {Side} side @param {typeof import("/vendor/floating-ui.esm.js")} ui
   * @param {PlacementRequest} request @returns {PlacementOptions} */
  function options(
    side,
    ui,
    {
      clear,
      room = NO_ROOM,
      row,
      lastRow = row,
      column = null,
      margin = null,
      boundary,
      fit,
      keeps = attachedEdge(side),
      under = null,
      rises = false,
    },
  ) {
    underLine = under;
    const minimumWidth = cardMinimum();
    const across = vertical(side);
    const unanchored = !clear;
    // A surface with no subject stands by the room's edge, which wears no mark
    // (`NO_ROOM`).
    const gap = subjectGap(room, side);
    // Floating UI reads a window attachment point for the unanchored posture,
    // sharing the same sizing, shift and coordinate conversion as an anchored box.
    clear ??= new DOMRect(boundary.left, boundary.top, minimumWidth, 0);
    // Beside on the right, keep the margin row usable when the room past it
    // holds the whole message measure; otherwise give that space to the message.
    /** @param {{x: number}} scale */
    const past = (scale) =>
      side === "right" &&
      margin &&
      margin.right > clear.right + 0.5 &&
      boundary.right - margin.right - gap >= cardMeasure() * scale.x
        ? margin.right
        : null;
    const box = new DOMRect(
      clear.left,
      clear.top,
      (past({ x: 1 }) ?? clear.right) - clear.left,
      clear.height,
    );
    // Under or over, the compact editor and its sent card share one place, which
    // leaves the surface its whole width in client pixels at its positioning scale: the
    // measure, or the boundary's width where that is narrower.
    /** @param {{x: number}} scale */
    const span = (scale) => Math.min(cardMeasure() * scale.x, boundary.width);
    /** @param {{x: number}} scale */
    const inlineStart = (scale) =>
      unanchored
        ? boundary.left
        : clamp(
            column ?? box.right - span(scale),
            boundary.left,
            boundary.right - span(scale),
          );
    // The inline edge the placement holds (the header's `fit`): the one a carried
    // offset names; beside its subject, the edge facing it; under or over, the end of
    // its place nearer the quoted words or the element's right edge, and the left with
    // nothing to stand by.
    /** @param {{x: number}} scale */
    const holdsLeft = (scale) => {
      if (carriedInline !== null) return holds !== "right";
      holds ??= !across
        ? side === "left"
          ? "right"
          : "left"
        : unanchored || (column ?? box.right) - inlineStart(scale) <= span(scale) / 2
          ? "left"
          : "right";
      return holds === "left";
    };
    let heldIn = false;
    const attachment = ui.limitShift(() => ({
      mainAxis: !across,
      crossAxis: across,
    }));
    // Client pixels per positioning-space pixel, the rule's line there, and beside, the
    // last line the surface may still stand level with.
    /** @type {import("@floating-ui/dom").Middleware} */
    const scaled = {
      name: "scaled",
      async fn(state) {
        const { rects } = state;
        const scale = await positioningScale(state);
        // The platform knows the surface's actual positioning scale. Renew the
        // reference once in that space before offset and size read its rectangle.
        const right = past(scale) ?? clear.right;
        if (box.right !== right) {
          box.width = right - box.left;
          return { reset: { rects: true } };
        }
        return {
          data: {
            scale,
            column: rects.reference.x + (inlineStart(scale) - box.left) / scale.x,
            end:
              rects.reference.x +
              (inlineStart(scale) + span(scale) - box.left) / scale.x,
            attachmentInline:
              rects.reference.x + ((column ?? clear.left) - box.left) / scale.x,
            line:
              column !== null
                ? rects.reference.y + (row - box.top) / scale.y
                : side === "bottom"
                  ? rects.reference.y + rects.reference.height
                  : side === "top"
                    ? rects.reference.y
                    : rects.reference.y + (row - box.top) / scale.y,
            last: rects.reference.y + (lastRow - box.top) / scale.y,
          },
        };
      },
    };
    /** @param {Pick<MiddlewareState, "middlewareData">} state */
    const measure = (state) => state.middlewareData.scaled;
    // The room across the columns the surface stands in where the boundary lets it
    // stand, so chrome beside it takes none of its height (`commentBoundary`). The last
    // one read when the surface reads its answer (`plane`) is the room the answer stood
    // in. floating.js solves the placement again at the box's old size only after that
    // (`position`), and that solve writes it again. We could consider, in future,
    // returning `shown` and `heldIn` in the answer's middleware data, so `plane` reads
    // the answer it is given and the order of the two solves stops mattering.
    /** @type {Room} */
    let shown = boundary;
    // The room from the edge the surface is held by to the boundary, in client pixels,
    // and no more than the boundary's width where that edge has scrolled past it.
    /** @param {{x: number}} scale */
    const lane = (scale) =>
      Math.min(
        boundary.width,
        carriedInline !== null
          ? holds === "right"
            ? (column ?? clear.left) + carriedInline - boundary.left
            : boundary.right - (column ?? clear.left) - carriedInline
          : across
            ? holdsLeft(scale)
              ? boundary.right - (inlineStart(scale) + (inline ?? 0) * scale.x)
              : inlineStart(scale) +
                span(scale) +
                (inline ?? 0) * scale.x -
                boundary.left
            : side === "right"
              ? boundary.right - box.right - gap
              : clear.left - boundary.left - gap,
      );
    // A surface may widen away from its held edge, to the measure or its lane where
    // that is narrower, without being placed again (`size-width`), so it stands clear
    // of chrome across every column it may widen into, as of the window's foot.
    /** @param {MiddlewareState} state */
    const overflow = (state) => {
      const { scale } = measure(state);
      const width = state.rects.floating.width * scale.x;
      const reach = Math.min(
        Math.max(width, Math.min(cardMeasure() * scale.x, lane(scale))),
        boundary.width,
      );
      const left = clamp(
        box.left + (state.x - state.rects.reference.x) * scale.x,
        boundary.left,
        boundary.right - width,
      );
      const start = clamp(
        holdsLeft(scale) ? left : left + width - reach,
        boundary.left,
        boundary.right - reach,
      );
      shown = boundary.across({ left: start, right: start + reach });
      return { boundary: [], rootBoundary: shown, padding: 0 };
    };
    const spot = held ?? initialHold;
    // How much of a surface `height` tall stands under the line it keeps, where `own`
    // of it stands under its own line.
    /** @param {number} height @param {number} own */
    const underKept = (height, own) =>
      keeps === "top" ? height : keeps === "foot" ? 0 : own;
    // Where a solve stands a landed surface's top, in its positioning pixels from the
    // rule's line: where the line it keeps stays as far from the rule's as it landed,
    // with what stands under that line now under it. A solve for the size the surface
    // stood at is floating.js's, for where it would stand had it kept its size
    // (`position`): where it landed.
    /** @param {MiddlewareState} state @param {HeldBox} spot */
    const heldTop = (state, spot) => {
      const { scale } = measure(state);
      if (state.middlewareData.stood) return spot.top / scale.y;
      const height = state.rects.floating.height * scale.y;
      const kept = spot.top + spot.height - underKept(spot.height, spot.under);
      return (kept + underKept(height, under?.() ?? 0) - height) / scale.y;
    };
    // It also names the block edge floating.js stands the surface by, so growth moves
    // the other edge in the layout that grows it: its top where it keeps that, else
    // its foot. Where it keeps its own line, what grows over the line then grows it up
    // in that layout, and what grows under the line waits for the placement, which
    // lands before the frame paints.
    const holding = (spot || carriedInline !== null || across) && {
      name: "hold",
      /** @param {MiddlewareState} state */
      fn(state) {
        // A carried inline offset holds the edge it names, whichever side the surface
        // stands on, so a field growing as it is typed in grows away from it. Under or
        // over, the surface stands at the end of its place it is held by, in every
        // writing direction.
        const { line, attachmentInline, column, end, scale } = measure(state);
        const width = state.rects.floating.width;
        const edge =
          carriedInline !== null || across
            ? holdsLeft(scale)
              ? "left"
              : "right"
            : null;
        const data = {
          edge: spot && (keeps === "top" ? "top" : "bottom"),
          inline: edge,
        };
        /** @type {Partial<import("@floating-ui/dom").Coords>} */
        const position = {};
        if (carriedInline !== null)
          position.x =
            attachmentInline + carriedInline / scale.x - (edge === "right" ? width : 0);
        else if (edge === "left") position.x = column + (inline ?? 0);
        else if (edge === "right") position.x = end + (inline ?? 0) - width;
        if (spot && !across) position.y = line + heldTop(state, spot);
        // Where the rule stands it before the boundary shifts it in, which a carried
        // surface's attachment limit takes in.
        const rule = Object.assign({ x: state.x, y: state.y }, position);
        return { ...position, data: { ...data, spot: rule } };
      },
    };
    const size = ui.size((state) => ({
      ...overflow(state),
      apply(state) {
        const { scale, line } = measure(state);
        // The height a held surface caps no lower than (the header's `stood`): the
        // tallest what stands over its own line has stood while the rule's line
        // stood where it stands now, else what last stood over it, with what stands
        // under that line now. The room is read from where the rule stands the
        // surface, so where the boundary's head holds it in, lower than that, only
        // this lets what joins it under its line grow it. It grows that way as far
        // as the room's height, or the tallest the whole surface has stood, and past
        // that what stands over the line gives way.
        const stationary = Boolean(tallest && Math.abs(tallest.line - line) < 0.5);
        const tall =
          held &&
          (stationary && tallest
            ? tallest
            : { whole: held.height, over: held.height - held.under });
        const stood = tall
          ? Math.min(tall.over + (under?.() ?? 0), Math.max(tall.whole, shown.height)) /
            scale.y
          : 0;
        // Under or over, Floating UI's available width runs from the start its placement
        // names, while the surface may be held by its other edge, so the lane, measured
        // from the held edge, gives the width.
        fit({
          side,
          width: Math.max(
            Math.min(minimumWidth, boundary.width) / scale.x,
            across
              ? lane(scale) / scale.x
              : Math.min(state.availableWidth, lane(scale) / scale.x),
          ),
          height: rises ? shown.height / scale.y : state.availableHeight,
          room: shown,
          stationary,
          stood,
          scale,
        });
      },
    }));
    // A fresh surface may slide into the complete clipping rectangle: size after
    // shift. A held one grows toward the boundary its kept line faces away from: size
    // before shift, reading the edge it stands by as its sizing direction without
    // changing its attachment. Drop the preceding pass's shift data when size resets
    // the measurements; its permission to shift must not widen a held surface's
    // available height.
    const sizing = spot
      ? {
          ...size,
          /** @param {MiddlewareState} state */
          fn(state) {
            const { shift, ...middlewareData } = state.middlewareData;
            const foot = keeps !== "top";
            return size.fn({
              ...state,
              placement: across
                ? `${foot ? "top" : "bottom"}-start`
                : `${side}-${foot ? "end" : "start"}`,
              middlewareData,
            });
          },
        }
      : size;
    const middleware = [
      scaled,
      ui.offset((state) => {
        const { scale } = measure(state);
        // Declare the held separation to offset itself, so the attachment limiter
        // follows the same edge instead of pulling a shorter card toward its target.
        let mainAxis = gap / (across ? scale.y : scale.x);
        if (spot && across) {
          const top =
            measure(state).line - state.rects.reference.y + heldTop(state, spot);
          mainAxis =
            side === "top"
              ? -top - state.rects.floating.height
              : top - state.rects.reference.height;
        }
        return {
          mainAxis,
          crossAxis: across ? 0 : (row - COMMENT_GAP - box.top) / scale.y,
        };
      }),
      holding,
      spot && sizing,
      ui.shift((state) => ({
        ...overflow(state),
        mainAxis: true,
        crossAxis: true,
        limiter: {
          ...attachment,
          /** @param {Parameters<typeof attachment.fn>[0]} state */
          fn(state) {
            if (unanchored) {
              heldIn = true;
              return { x: state.x, y: state.y };
            }
            // shift first keeps the card inside the visible boundary. Limit that
            // correction to keep it attached: beside the target, its vertical
            // interval must overlap the target's first-to-last line; above/below,
            // Floating UI limits separation from the reference box. Only current
            // geometry decides, so reversing a scroll retraces the same positions.
            const limited = across
              ? attachment.fn(state)
              : {
                  x: state.x,
                  y: clamp(
                    state.y,
                    measure(state).line - state.rects.floating.height,
                    measure(state).last,
                  ),
                };
            // A surface the user carried counts the spot they put it at as attached
            // too, so it stands there and still leaves with what it is about.
            if (moved)
              for (const axis of AXES) {
                const own = state.middlewareData.hold.spot[axis];
                limited[axis] = clamp(
                  state[axis],
                  Math.min(limited[axis], own),
                  Math.max(limited[axis], own),
                );
              }
            heldIn = Math.abs(limited.y - state.y) < 0.5;
            return limited;
          },
        },
      })),
      !spot && sizing,
    ].filter((middleware) => !!middleware);
    return {
      reference: box,
      placement: `${side}-start`,
      middleware,
      plane: ({ middlewareData }) => {
        if (unanchored) return "window";
        const shift = middlewareData.shift?.y ?? 0;
        if (!heldIn || Math.abs(shift) < 0.5) return "page";
        // Held in, it stands in the plane of the box whose edge holds it, which the
        // room it stood in names, and in the window's where the window or the chrome
        // bounds the room there (`commentBoundary`).
        return shown.holders[shift > 0 ? "top" : "bottom"] ?? "window";
      },
    };
  }

  return {
    // Mechanical handoff between the editor's frame and its sent card.
    capture() {
      return { side, boundary: input?.boundary ?? null, moved, holds };
    },
    /** @param {AdoptedFrame} frame */
    adopt(frame) {
      forget();
      pending = frame;
    },
    forget,
    scrolled() {
      input = null;
    },
    /** @param {{clear: Extent | null, extent?: Extent | null, room?: MarkRoom, boundary: Boundary, row?: number, column?: number | null, scroller: Element, element: Element, coarse: boolean}} request */
    choose({
      clear,
      extent = clear,
      room = NO_ROOM,
      boundary,
      row = clear?.top ?? boundary.top,
      column = null,
      scroller,
      element,
      coarse,
    }) {
      // No visible attachment puts the editor in the window. The authored subject
      // remains its semantic anchor; no rectangle here pretends to represent it.
      const unanchored = !clear;
      extent ??= boundary;
      const key = {
        unanchored,
        boundary: boundary.key,
        left: extent.left,
        right: extent.right,
      };
      const frame = pending;
      pending = null;
      const adopted =
        frame?.placement.boundary &&
        sameBoundary(boundary.key, frame.placement.boundary);
      if (adopted) {
        // A draft can have lost its visible attachment before Send. Its card still
        // starts at that frame, then follows the card's attachment from this choice.
        // The card holds the edge the frame held, where it stood, the left one where
        // the user carried the frame.
        ({ side, moved, holds } = frame.placement);
        if (moved) holds = "left";
        carriedInline =
          (holds === "right" ? frame.box.right : frame.box.left) -
          (column ?? clear?.left ?? boundary.left);
        const line =
          column !== null
            ? row
            : side === "bottom"
              ? (clear?.bottom ?? row)
              : side === "top"
                ? (clear?.top ?? row)
                : row;
        const top = frame.box.top - line;
        initialHold = { top, height: frame.box.height, under: 0 };
      } else if (
        input &&
        (key.unanchored !== input.unanchored ||
          !sameBoundary(key.boundary, input.boundary) ||
          Math.abs(key.left - input.left) > 0.5 ||
          Math.abs(key.right - input.right) > 0.5)
      ) {
        forget();
      } else if (!input && opened) {
        // The scroll the surface asked for (`scrolled`) is no landing of the input's.
        opened.starts = scrollStarts(scroller);
      }
      input = key;
      // A choice is fresh where it picks the side. The surface is opening until it
      // first lands: a placement a newer one supersedes before it fits never opened it,
      // and a card opened while Floating UI first loads is placed again before that, so
      // only `opening` says it has yet to make room clear of its target. A choice after
      // the first keeps what that one began, such as the transcript's reading, until
      // the landing of the input that opened it, as a walk's, takes its subject
      // somewhere else, and it opens there once more (`size-page-still`).
      const fresh = side === null;
      if (
        opened &&
        opened.input === inputs.count &&
        scrollStarts(scroller) > opened.starts
      ) {
        opened = null;
        reopened = true;
      }
      const opening = (held === null && initialHold === null) || reopened;
      side ??= unanchored
        ? "bottom"
        : commentSide({
            clear,
            extent,
            room,
            boundary,
            width: cardMinimum(),
            scroller,
            element,
            coarse,
          });
      if (fresh && !unanchored)
        opened = { input: inputs.count, starts: scrollStarts(scroller) };
      return {
        side,
        fresh,
        opening,
        adopted: initialHold !== null,
        options: options.bind(null, side),
      };
    },
    /** @param {Position} answer */
    landed({ x, y, middlewareData }) {
      initialHold = null;
      reopened = false;
      const { scale, column, end, attachmentInline, line } = middlewareData.scaled;
      const { width } = middlewareData.held;
      // A surface keeps the edge it is held by where it landed. One held by its right
      // edge beside the target keeps that edge there, so a change of its room moves its
      // left edge, never the edge by the words.
      if (vertical(side)) inline ??= holds === "right" ? x + width - end : x - column;
      else if (holds === "left") carriedInline ??= (x - attachmentInline) * scale.x;
      const top = (y - (middlewareData.shift?.y ?? 0) - line) * scale.y;
      const height = middlewareData.held.height * scale.y;
      const under = underLine?.() ?? 0;
      const last = tallest && Math.abs(tallest.line - line) < 0.5 ? tallest : null;
      tallest = {
        whole: Math.max(last?.whole ?? 0, height),
        over: Math.max(last?.over ?? 0, height - under),
        line,
      };
      held = { top, height, under };
      return { scale };
    },
  };
}
