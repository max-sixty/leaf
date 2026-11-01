/* Where a comment's surfaces stand: the comment box the user types in
   (composing/surface.js) and the thread card the sent comment becomes
   (thread-preview.js). They are one comment at two moments, so one rule places
   both, and Send changes the surface without moving the place. Floating UI does the
   placing (floating.js): this module chooses the side and names the boxes, and
   Floating UI's offset, size and shift do the rest.

   A comment stands by what it is about. `clear` is the box it keeps
   clear of, as the page shows it: the paragraph holding a passage, the element, or the
   row a pointing gesture named in it (pointed-place.js). `extent` is that box whole,
   however much of it a scroll has clipped, which is what the room around it is measured
   from. `row` is the first line it stands level with beside `clear`, and `lastRow` the
   last: a passage's first line for both, else `extent`'s top and foot. Both come from
   the unclipped box: the top of a clipped box is the window's edge, and a card level
   with it in the page's plane would be carried by each scroll frame and placed back.
   `column` is the passage's inline start when it quotes words;
   without one, the card's minimum width ends at `clear`'s right edge. `margin` is where
   across the page the margin row for it stands,
   or would stand in the rail once its thread is sent (margin-layout.js, `marginSpot`),
   or nothing where no row stands and its rows would be pins. A caller requesting
   window placement without a visible attachment supplies `clear: null` and stands
   at its upper inline edge through the same sizing and placement machinery.
   A target that is not drawn has no attachment: seated surfaces withhold their native
   editing state until it returns. An explicit open can request the unanchored window
   posture while retaining the hidden subject as its semantic anchor. A drawn target's
   geometry may have zero area; its whole extent still supplies the fallback seat.
   The editing surface uses this solver for its initial attachment, then retains
   browser-owned following (`composing/floating-response.js`).

   Both stand in one boundary (`commentBoundary`): the part of the window the page
   shows, within the region that scrolls the pointed row, else the target
   (`scrollerFor`), where that holds a card, else within the page shell. That region's
   edges cut the row as it scrolls, so they cut the surface too. A region in flow
   scrolls nothing itself, so a surface on words in a pane the page scrolls stands in
   the page, or in whatever box scrolls that pane; which boxes scroll is the
   stylesheet's to say (reading-regions.js). Rejected: the innermost reading region
   around the row, whether or not it scrolled, which stopped a card on words in a pane
   the page scrolls at that pane's foot while the window had room. Also rejected: the
   innermost box with rows to scroll, which stood a comment in a workspace pane whose
   rows all show over the pane beside it; and the region that scrolls the target,
   which stood a comment pointed at a row deep in a pane that is itself the target
   over the pane beside it.

   The side is chosen once, for the thread's footprint rather than the box's, so the box
   stands where its card can: right of `clear` where that room holds the card's minimum
   width (`--thread-card-min`), else left of it where that room does, else under or over
   it, preferring a side that already shows the least room a surface stands in
   (`LEAST_HEIGHT`). Among those sides, the one the page can make more room on wins:
   what shows there plus what the reading region can still scroll there. A touch
   screen prefers under among sides with room, since the platform's selection menu
   stands over the words and Leaf cannot read where. The side is held until the boundary or `extent`'s width
   changes (a resize, a pane that narrows, a reflow), which chooses afresh; a scroll
   clipping `clear` does not.

   Beside, the surface's top stands level with `row`, and past its margin row where that
   reaches past `clear` and the room beyond it holds the card's full preferred measure
   (`--thread-card`). Message width takes priority over keeping the margin row clear:
   where clearing it would narrow the message, the surface stands over the row. The
   card carries its own close and step controls, and the row shows again once it closes.
   Neither choice reads the surface's own width or height, so the box
   and the card make the same one. Under or over, its inline start follows `column`,
   independently of the block it keeps clear, and it keeps that start as it widens.
   That clearance chooses the initial seat. Once seated, quoted words carry both
   coordinates through scrolling, including out of view, even when the containing
   scrollport stays still. Held offsets use the passage's line and column, so renewing
   the seat cannot put it back beside a stationary scrollport.

   It grows away from what it is about, down beside or under and up over it (floating.js,
   `held`), and the boundary holds it in only while what it stands by is in the window:
   Floating UI's shift keeps it inside, and its limiter lets it leave beside with
   `row` or `lastRow`, whichever the scroll carries away, or with `clear` under or
   over. Beside an element whose top has scrolled away, the card therefore waits at the
   window's top, in the window's plane, until the element's foot passes it. Arrival
   and departure use this same attachment limit, including the first placement:
   an offscreen target carries its surface into view as scrolling approaches it.
   Growing never scrolls the page. A surface that outgrows the room on its side slides
   inside the boundary, over its passage or element if it must, and once it fills the
   boundary scrolls its own content. Only a card opening under or over its target
   scrolls the reading region, as far as it can, to make the room it needs (`makeRoom`),
   so it opens clear of that target.

   A surface may choose which edge of its last rectangle to hold (`edge`), in client
   pixels from its line: `row` beside, and under or over the edge of `clear` it stands
   clear of, so a reflow of what it is about carries it. The card keeps its reply row
   still that way while a turn joins the transcript above it.

   A held surface grows no taller than the room from its held edge, or than the tallest
   it has stood since its line last moved (`fit`'s `stood`), whichever is more. One
   that `rises` holds its top but has the boundary's whole height, so the boundary
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
   window's edge (#3139), which kept the words still while typing but moved them at
   Send by that row; and painting the frame as the card while it is written (#3157),
   which left Send nothing to grow.

   Send hands the editor's frame to the card (`adopt`). Its next choice keeps the
   frame's side and inline start where the boundary still matches, and returns its
   block offsets for the card to hold. The attachment is then the card's current one:
   scrolling retains it, while a boundary or target-width change chooses afresh.
   A surface the user carries by its grip (surface-grip.js) adopts its own dropped frame
   the same way, marked `moved`. A moved surface carries its inline offset on every
   side, the left included, and its attachment limit stretches to take in the spot it
   was dropped at, so it stands there and still leaves with what it is about.

   The card's interaction owner (`thread/card-anchor.js`) chooses the edge to preserve.
   This solver knows only its physical attachment and landed rectangle. Focus and
   transcript landing at Send belong to `thread/reply-landing.js`; width retention
   belongs to the preview's lifetime (`thread-preview.js`).

   Every box here is a client rectangle. Floating UI works in the surface's positioning
   space, which a transformed ancestor scales, so each length crosses by the reference's
   scale, and `fit` is handed lengths in that space, as CSS sizes the surface in it. */

import { scrollAxes } from "../element-frame.js";
import { visibleTargetParts } from "../visible-target-parts.js";
import {
  shellRight,
  shownWindow,
  visualViewport,
  shownExtent,
  shownParts,
  shownRect,
} from "../geometry.js";
import { clamp, union } from "../rect.js";
import { moveScrollerBy, pageScroller, scrollLimit } from "../scrolling.js";

import { scrollerFor } from "../reading-regions.js";
import { pointBand } from "../pointed-place.js";
import { marginSpot } from "./margin-layout.js";
import { floatingGeometry, positioningScale } from "./floating.js";

// One fresh mechanical reading for the editor and the card it becomes. Resolving the
// durable subject or passage remains with the caller; both surfaces read its boxes here.
/** @typedef {import("../rect.js").Box} Box */
/** @typedef {Box & {width: number, height: number}} Extent */
/** @typedef {Pick<Box, "left" | "right">} Columns */
/** @typedef {import("@floating-ui/dom").Side} Side */
/** @typedef {import("@floating-ui/dom").MiddlewareState} MiddlewareState */
/** @typedef {import("@floating-ui/dom").ComputePositionReturn} Position */
/** @typedef {readonly [number, number, number, number]} BoundaryKey */
/** @typedef {DOMRectReadOnly & {across: (columns: Columns | null) => DOMRectReadOnly,
 * inRegion: Box | null, key: BoundaryKey}} Boundary */
/** @typedef {{side: Side | null, boundary: BoundaryKey | null, moved: boolean}} CapturedPlacement */
/** @typedef {{box: Extent, placement: CapturedPlacement}} AdoptedFrame */
/** @typedef {{top: number, foot: number}} HeldBox */
/** @typedef {{clear: Extent | null, row: number, lastRow?: number,
 * column?: number | null, margin?: Columns | null, boundary: Boundary,
 * fit: (room: {side: Side, width: number, height: number, room: DOMRectReadOnly,
 * stood: number, scale: {x: number, y: number}}) => void,
 * edge?: "top" | "foot", rises?: boolean}} PlacementRequest */
/** @typedef {{reference: DOMRect,
 * placement: import("@floating-ui/dom").Placement,
 * middleware: import("@floating-ui/dom").Middleware[],
 * plane: (answer: Position) => "page" | "window" | {edge: "top" | "bottom", at: number}}} PlacementOptions */
/** @typedef {{element: Element, contextNode: Node,
 * geometry: ReturnType<typeof floatingGeometry>, clear: Extent | null, extent: Extent,
 * row: number, lastRow: number, column: number | null,
 * margin: ReturnType<typeof marginSpot>, scroller: Element}} Attachment */
/** @typedef {{target: Element | null, point?: Element | null,
 * passage?: {range?: Range, contextNode?: Node | null, attachment?: Extent | null} | null,
 * boundary?: ReturnType<typeof commentBoundary> | null}} AttachmentRequest */
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
  if (!visibleTargetParts(target).length) return null;
  const margin = marginSpot(target, point, passage?.range);
  const context = point ?? passage?.contextNode ?? target;
  const element = point ?? target;
  const geometry = floatingGeometry([element, context]);
  const clips = new Map();
  const shown = union(
    shownParts(target)
      .map(/** @param {Element} part */ (part) => shownRect(part, clips))
      .filter((box) => box !== null),
  );
  const whole = shownExtent(target) ?? target.getBoundingClientRect();
  const extent = point ? pointBand(whole, point) : whole;
  const clear = point ? extent : (shown ?? whole);
  return {
    element,
    contextNode: context,
    geometry,
    clear,
    extent,
    row: (passage?.attachment ?? extent).top,
    lastRow: passage?.attachment ? passage.attachment.top : extent.bottom,
    column: passage?.attachment?.left ?? null,
    margin,
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

export const COMMENT_GAP = 8;
// The least room a surface stands in: a floor chosen to hold the comment box's words
// and its controls over a few lines, which the room under the words must reach for a
// touch screen to prefer it, and a reading region must show for a surface to stand in it.
export const LEAST_HEIGHT = 96;
/** @type {readonly ("x" | "y")[]} */
const AXES = ["x", "y"];

// The room both surfaces stand in: the part of the window the page shows, within the
// shown bounds of the reading region whose body is `scroller`, the box that scrolls the
// surfaces' row (`scrollerFor`), where those hold the card's minimum width and the least
// height, else within the page shell, whose right edge stops short of the root
// scrollport's gutter and, for the comment box, an open panel's left edge (`right`). A
// pane a resize narrowed, or a short strip of one a scroll left, so yields to the window,
// which carries the surface rather than withdrawing a draft the user is writing. The
// boundary names the region's shown bounds it stands in (`inRegion`), which then cut the
// surface. Its `key` is what holds the side (`choose`): the window's edges, or the
// region's whole box size and the window's, since a scroll of the page moves and clips a
// region's shown bounds without changing the room it has, and a resize changes it.
// It spans every column the surface could stand in, so the side is chosen from it;
// `across(columns)` is the same room for a surface standing in those columns, where
// chrome beside them, such as the floating panel's row under the page column, takes
// none of its height (`shownWindow`).
/** @param {{scroller?: Element | undefined, right?: number}} [options] @returns {Boundary} */
export function commentBoundary({ scroller = pageScroller, right = Infinity } = {}) {
  /** @param {Partial<Box>} within */
  const room = (within) => {
    /** @param {Columns | null} columns */
    const across = (columns) =>
      shownWindow({ within, gap: COMMENT_GAP, across: columns });
    return Object.assign(across(null), { across });
  };
  const bounds = scroller !== pageScroller && shownRect(scroller, new Map());
  const inRegion = bounds && room(bounds);
  if (
    inRegion &&
    Math.ceil(inRegion.width) >= Math.ceil(cardMinimum()) &&
    inRegion.height >= LEAST_HEIGHT
  ) {
    const whole = scroller.getBoundingClientRect();
    /** @type {BoundaryKey} */
    const key = [
      whole.width,
      whole.height,
      visualViewport.width,
      visualViewport.height,
    ];
    return Object.assign(inRegion, { inRegion: bounds, key });
  }
  const shell = room({ right: Math.min(shellRight(), right) });
  /** @type {BoundaryKey} */
  const key = [shell.left, shell.top, shell.right, shell.bottom];
  return Object.assign(shell, { inRegion: null, key });
}

/** @param {BoundaryKey} a @param {BoundaryKey} b */
const sameBoundary = (a, b) =>
  Math.abs(a[0] - b[0]) <= 0.5 &&
  Math.abs(a[1] - b[1]) <= 0.5 &&
  Math.abs(a[2] - b[2]) <= 0.5 &&
  Math.abs(a[3] - b[3]) <= 0.5;

/** @param {Side | null} side */
const vertical = (side) => side === "top" || side === "bottom";

// Vertical room is read in viewport pixels, while the browser scrolls in local CSS
// pixels. Project available travel through the scroller's actual transformed axis;
// an inverted axis reverses which local end can expose room on the requested side.
/** @param {Side} side @param {Element} scroller */
function roomTravel(side, scroller) {
  const projection = scrollAxes(scroller).y.y;
  const direction = side === "top" ? -1 : 1;
  const localDirection = direction * Math.sign(projection);
  const local =
    localDirection < 0
      ? scroller.scrollTop
      : Math.max(0, scrollLimit(scroller) - scroller.scrollTop);
  return { projection, direction, available: local * Math.abs(projection) };
}

// The room on `side` of `extent` the page can make: what shows there plus the scroll
// travel `scroller` has left that way, never more than the boundary holds.
/** @param {Side} side @param {Extent} extent @param {Boundary} boundary @param {Element} scroller */
function reachableRoom(side, extent, boundary, scroller) {
  const shown =
    side === "top"
      ? extent.top - boundary.top - COMMENT_GAP
      : boundary.bottom - extent.bottom - COMMENT_GAP;
  const { available: travel } = roomTravel(side, scroller);
  return {
    shown,
    reachable: Math.max(
      0,
      Math.min(boundary.height - extent.height - COMMENT_GAP, shown + travel),
    ),
  };
}

// Scrolls `scroller` to make the room a surface `height` tall needs on `side` of `clear`,
// under or over it, as far as the scroller travels; whether it moved. Where `extent`
// and this surface cannot show together, no scroll makes that room. The boundary
// then holds the surface over its subject instead of scrolling the subject away.
/** @param {Side} side @param {Extent} clear @param {Extent} extent @param {number} height @param {Boundary} boundary @param {Element} scroller */
export function makeRoom(side, clear, extent, height, boundary, scroller) {
  if (extent.height + COMMENT_GAP + height > boundary.height) return false;
  const overflow =
    side === "top"
      ? boundary.top - (clear.top - COMMENT_GAP - height)
      : clear.bottom + COMMENT_GAP + height - boundary.bottom;
  const { available: travel, projection, direction } = roomTravel(side, scroller);
  const movement = Math.max(0, Math.min(overflow, travel));
  if (movement <= 0.5) return false;
  const before = scroller.scrollTop;
  moveScrollerBy(scroller, (direction * movement) / projection);
  return Math.abs((scroller.scrollTop - before) * projection) > 0.5;
}

// The side a comment's surface takes, as a Floating UI side.
/** @param {{clear: Extent, extent: Extent, boundary: Boundary, width: number, scroller: Element, coarse: boolean}} reading @returns {Side} */
export function commentSide({ clear, extent, boundary, width, scroller, coarse }) {
  /** @param {number} room */
  const fits = (room) => Math.ceil(room) >= Math.ceil(width);
  if (fits(boundary.right - clear.right - COMMENT_GAP)) return "right";
  if (fits(clear.left - boundary.left - COMMENT_GAP)) return "left";
  const below = reachableRoom("bottom", extent, boundary, scroller);
  const above = reachableRoom("top", extent, boundary, scroller);
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

// The minimum width chooses the side; the preferred measure caps message width and
// decides whether clearing the margin row would sacrifice it. `commentPlacement`
// reads both, so the comment box and its sent card share the same placement rule.
/** @param {string} name */
const rootLength = (name) =>
  parseFloat(getComputedStyle(document.documentElement).getPropertyValue(name));
export const cardMinimum = () => rootLength("--thread-card-min");
export const cardMeasure = () => rootLength("--thread-card");

/* One surface's placement: the side it holds and its inline attachment.

   `choose` holds a side, choosing one where none is held or the boundary or `extent`'s
   width has changed, and says whether it chose afresh, and whether the surface has
   yet to land (`opening`). `options` then gives
   `computePosition` the reference to stand by, its placement and its middleware.
   `landed` takes the answer's inline start and where the rule stood the surface's top
   and foot before the boundary shifted it in, from the rule's line. `options` holds
   the requested `edge` of that rectangle; `landed` returns the surface's `scale`. `plane` names
   the constraint that bound the answer (floating.js): `"page"` where the rule's line
   holds the surface, and where the boundary shifted it in, the edge it stands against
   and that edge's client line.
   `forget` drops the side so the next placement chooses again, and `scrolled` keeps it
   across the scroll the surface itself asked for (`makeRoom`).

   `capture` is an opaque reading carried inside the editor's frame, whose `box` is a
   client rectangle. `adopt(frame)` queues that handoff for the next `choose`, which
   reports `adopted` until `landed` confirms a position.
   A superseded computation retains that hold. The placement owns its carried inline
   offset from the passage's column, else `clear`'s left edge. That column moves with
   quoted words even when their scrollport stays still. A normal beside landing owns
   the same offset, so renewing placement follows the attachment native motion carries.
   `edge` supplied to `options` names only a block edge, relative to the passage's
   line when quoted, else the initial side's clearance edge. Without an explicit
   edge, the landed seat holds its growing surface by its foot above and top elsewhere,
   so an editor needs no transcript reading to keep its attachment while typing; before
   that landing, an adopted frame's offsets are the ones held. `rises` offers a surface
   holding its top the boundary's whole height for `fit`, rather than the room below.

   `fit({ side, width, height, room, stood, scale })` sizes the surface for the room its
   side gives, in its positioning space; `room` is the client rectangle that room stands
   in, the boundary across the surface's columns (`commentBoundary`, `across`); `stood`
   is the height a held surface caps no lower than, or 0. Its declared minimum is limited only by the boundary, never by
   its passage's column.
   The intended inline start caps growth, before a restored draft's own width can
   shift it. On the left, the surface instead holds its right edge clear of the
   target and grows toward the boundary; keeping its initial left edge would let
   a longer draft grow across the words it comments on. */
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
  // The last landed rectangle, in client pixels from the attachment line.
  /** @type {HeldBox | null} */
  let held = null;
  // The tallest the surface has stood since its line last moved, and that line.
  /** @type {{height: number, line: number} | null} */
  let tallest = null;
  const forget = () => {
    side = null;
    inline = null;
    input = null;
    pending = null;
    carriedInline = null;
    initialHold = null;
    moved = false;
    held = null;
    tallest = null;
  };
  /** @param {Side} side @param {typeof import("/vendor/floating-ui.esm.js")} ui
   * @param {PlacementRequest} request @returns {PlacementOptions} */
  function options(
    side,
    ui,
    {
      clear,
      row,
      lastRow = row,
      column = null,
      margin = null,
      boundary,
      fit,
      edge = side === "top" ? "foot" : "top",
      rises = false,
    },
  ) {
    const minimumWidth = cardMinimum();
    const across = vertical(side);
    const unanchored = !clear;
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
      boundary.right - margin.right - COMMENT_GAP >= cardMeasure() * scale.x
        ? margin.right
        : null;
    const box = new DOMRect(
      clear.left,
      clear.top,
      (past({ x: 1 }) ?? clear.right) - clear.left,
      clear.height,
    );
    // The compact editor and its sent card share one start. Reserve the declared
    // card footprint before a shorter editor's own width can put that start too far
    // toward the boundary, where later typing or reopening would have to move it.
    const inlineStart = unanchored
      ? boundary.left
      : clamp(
          column ?? box.right - minimumWidth,
          boundary.left,
          boundary.right - Math.min(minimumWidth, boundary.width),
        );
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
            column: rects.reference.x + (inlineStart - box.left) / scale.x,
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
    // stand, so chrome beside it takes none of its height (`commentBoundary`); the
    // last one read is the room the answer stood in.
    /** @type {DOMRectReadOnly} */
    let shown = boundary;
    /** @param {MiddlewareState} state */
    const overflow = (state) => {
      const { scale } = measure(state);
      const width = state.rects.floating.width * scale.x;
      const left = clamp(
        box.left + (state.x - state.rects.reference.x) * scale.x,
        boundary.left,
        boundary.right - width,
      );
      shown = boundary.across({ left, right: left + width });
      return { boundary: [], rootBoundary: shown, padding: 0 };
    };
    const spot = held ?? initialHold;
    /** @type {{foot: number} | {top: number} | null} */
    const heldEdge =
      spot && (edge === "foot" ? { foot: spot.foot } : { top: spot.top });
    // It also names the block edge it keeps still, which floating.js stands the
    // surface by, so growth moves the other edge in the layout that grows it.
    const holding = (heldEdge || carriedInline !== null) && {
      name: "hold",
      /** @param {MiddlewareState} state */
      fn(state) {
        const edge = !across && heldEdge;
        // A carried inline offset holds the surface by its left edge, whichever side
        // it stands on, so a field growing as it is typed in grows away from it.
        const data = {
          edge: heldEdge && ("foot" in heldEdge ? "bottom" : "top"),
          inline: carriedInline !== null ? "left" : null,
        };
        const { line, attachmentInline, scale } = measure(state);
        /** @type {Partial<import("@floating-ui/dom").Coords>} */
        const position = {};
        if (carriedInline !== null)
          position.x = attachmentInline + carriedInline / scale.x;
        if (edge)
          position.y =
            "foot" in edge
              ? line + edge.foot / scale.y - state.rects.floating.height
              : line + edge.top / scale.y;
        // Where the rule stands it before the boundary shifts it in, which a carried
        // surface's attachment limit takes in.
        const spot = Object.assign({ x: state.x, y: state.y }, position);
        return { ...position, data: { ...data, spot } };
      },
    };
    const size = ui.size((state) => ({
      ...overflow(state),
      apply(state) {
        const { scale, line } = measure(state);
        // The height a held surface caps no lower than: the tallest it has stood
        // while its line stood where it stands now, else the height it last stood.
        const stood = held
          ? Math.max(
              held.foot - held.top,
              tallest && Math.abs(tallest.line - line) < 0.5 ? tallest.height : 0,
            ) / scale.y
          : 0;
        const lane =
          carriedInline !== null
            ? boundary.right - (column ?? clear.left) - carriedInline
            : across
              ? boundary.right - (inlineStart + (inline ?? 0) * scale.x)
              : side === "right"
                ? boundary.right - box.right - COMMENT_GAP
                : clear.left - boundary.left - COMMENT_GAP;
        fit({
          side,
          width: Math.max(
            Math.min(minimumWidth, boundary.width) / scale.x,
            Math.min(state.availableWidth, lane / scale.x),
          ),
          height: rises ? shown.height / scale.y : state.availableHeight,
          room: shown,
          stood,
          scale,
        });
      },
    }));
    // A fresh surface may slide into the complete clipping rectangle: size after
    // shift. A held edge grows toward the opposite boundary: size before shift,
    // reading that edge as its sizing direction without changing its attachment.
    // Drop the preceding pass's shift data when size resets the measurements;
    // its permission to shift must not widen a held edge's available height.
    const sizing = heldEdge
      ? {
          ...size,
          /** @param {MiddlewareState} state */
          fn(state) {
            const { shift, ...middlewareData } = state.middlewareData;
            const foot = "foot" in heldEdge;
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
        const edge = across && heldEdge;
        // Declare the held separation to offset itself, so the attachment limiter
        // follows the same edge instead of pulling a shorter card toward its target.
        let mainAxis = COMMENT_GAP / (across ? scale.y : scale.x);
        if (edge) {
          const top =
            measure(state).line -
            state.rects.reference.y +
            ("foot" in edge
              ? edge.foot / scale.y - state.rects.floating.height
              : edge.top / scale.y);
          mainAxis =
            side === "top"
              ? -top - state.rects.floating.height
              : top - state.rects.reference.height;
        }
        return {
          mainAxis,
          crossAxis: across
            ? measure(state).column - state.rects.reference.x + (inline ?? 0)
            : (row - COMMENT_GAP - box.top) / scale.y,
        };
      }),
      holding,
      heldEdge && sizing,
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
      !heldEdge && sizing,
    ].filter((middleware) => !!middleware);
    return {
      reference: box,
      placement: `${side}-start`,
      middleware,
      plane: ({ middlewareData }) => {
        if (unanchored) return "window";
        const shift = middlewareData.shift?.y ?? 0;
        if (!heldIn || Math.abs(shift) < 0.5) return "page";
        // Held in, it stands in the plane of the edge holding it, which floating.js
        // finds from that edge's client line: the boundary's, less its gap.
        return shift > 0
          ? { edge: "top", at: shown.top - COMMENT_GAP }
          : { edge: "bottom", at: shown.bottom + COMMENT_GAP };
      },
    };
  }

  return {
    // Mechanical handoff between the editor's frame and its sent card.
    capture() {
      return { side, boundary: input?.boundary ?? null, moved };
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
    /** @param {{clear: Extent | null, extent?: Extent | null, boundary: Boundary, row?: number, column?: number | null, scroller: Element, coarse: boolean}} request */
    choose({
      clear,
      extent = clear,
      boundary,
      row = clear?.top ?? boundary.top,
      column = null,
      scroller,
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
        ({ side, moved } = frame.placement);
        if (side !== "left" || moved)
          carriedInline = frame.box.left - (column ?? clear?.left ?? boundary.left);
        const line =
          column !== null
            ? row
            : side === "bottom"
              ? (clear?.bottom ?? row)
              : side === "top"
                ? (clear?.top ?? row)
                : row;
        const top = frame.box.top - line;
        initialHold = { top, foot: top + frame.box.height };
      } else if (
        input &&
        (key.unanchored !== input.unanchored ||
          !sameBoundary(key.boundary, input.boundary) ||
          Math.abs(key.left - input.left) > 0.5 ||
          Math.abs(key.right - input.right) > 0.5)
      ) {
        forget();
      }
      input = key;
      // A choice is fresh where it picks the side. The surface is opening until it
      // first lands: a placement a newer one supersedes before it fits never opened it,
      // and a card opened while Floating UI first loads is placed again before that, so
      // only `opening` says it has yet to make room clear of its target. A choice after
      // the first keeps what that one began, such as the transcript's reading.
      const fresh = side === null;
      const opening = held === null && initialHold === null;
      side ??= unanchored
        ? "bottom"
        : commentSide({
            clear,
            extent,
            boundary,
            width: cardMinimum(),
            scroller,
            coarse,
          });
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
      const { scale, column, attachmentInline, line } = middlewareData.scaled;
      // A left-side surface grows toward the boundary, keeping its right edge beside
      // the target. Holding its compact left edge would widen it over the target.
      if (vertical(side)) inline ??= x - column;
      else if (side !== "left") carriedInline ??= (x - attachmentInline) * scale.x;
      const top = (y - (middlewareData.shift?.y ?? 0) - line) * scale.y;
      const height = middlewareData.held.height * scale.y;
      tallest = {
        height:
          tallest && Math.abs(tallest.line - line) < 0.5
            ? Math.max(tallest.height, height)
            : height,
        line,
      };
      held = { top, foot: top + height };
      return { scale };
    },
  };
}
