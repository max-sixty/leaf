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
   The editing surface uses this solver for its initial attachment, then retains
   browser-owned following (`composing/floating-response.js`).

   Both stand in one boundary (`commentBoundary`): the part of the window the page shows,
   within the reading region where that holds a card, else within the page shell.

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
   reaches past `clear` and the room beyond it holds the card's minimum measure
   (`--thread-card-min`), so the row its thread has or will have stays usable. Where
   it cannot hold the minimum, the surface stands over the row: the card carries its
   own close and step controls, and the row shows again once it closes. Neither
   choice reads the surface's own width or height, so the box
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

   A surface may hold one edge at an offset of its own choosing (`hold`), in client
   pixels from its line: `row` beside, and under or over the edge of `clear` it stands
   clear of, so a reflow of what it is about carries it. The card keeps its reply row
   still that way while a turn joins the transcript above it.

   Send hands the editor's frame to the card (`adopt`). Its next choice keeps the
   frame's side and inline start where the boundary still matches, and returns its
   block offsets for the card to hold. The attachment is then the card's current one:
   scrolling retains it, while a boundary or target-width change chooses afresh.

   Which edge a growing surface holds is this module's for both surfaces, so neither
   can drift from the other. A surface whose content grows by turns holds the edge the
   user is working at (`holding`): its top while they read or type, its foot, with the
   reply row on it, once a turn joins the transcript as they draft or send, keyed to
   that turn so the next one releases it, and its foot where it stands over what it is
   about and is read. The caller reports the transcript's extent, whether the user is
   drafting, the latest turn and the draft's words; a surface with no turns, the
   comment box, never asks, and its free edges grow as floating.js holds them. The held
   edge is also the one floating.js stands the surface by, so the browser grows it from
   there.

   Every box here is a client rectangle. Floating UI works in the surface's positioning
   space, which a transformed ancestor scales, so each length crosses by the reference's
   scale, and `fit` is handed lengths in that space, as CSS sizes the surface in it. */

import {
  scrollAxes,
  shellRight,
  shownWindow,
  shownExtent,
  shownParts,
  shownRect,
} from "/runtime/geometry.js";
import { clamp, union } from "/runtime/rect.js";
import { moveScrollerBy } from "/runtime/scrolling.js";

import {
  containingReadingRegionFor,
  effectiveScroller,
  shownRegionBounds,
} from "/runtime/reading-regions.js";
import { pointBand } from "/runtime/pointed-place.js";
import { marginSpot } from "./margin-layout.js";
import { floatingGeometry, positioningScale } from "./floating.js";

// One fresh mechanical reading for the editor and the card it becomes. Resolving the
// durable subject or passage remains with the caller; both surfaces read its boxes here.
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
      region: null,
      scroller: effectiveScroller(element),
    };
  }
  const context = point ?? passage?.contextNode ?? target;
  const element = point ?? target;
  const geometry = floatingGeometry([element, context]);
  const clips = new Map();
  const shown = union(
    shownParts(target)
      .map((part) => shownRect(part, clips))
      .filter(Boolean),
  );
  const whole = shownExtent(target) ?? target.getBoundingClientRect();
  const extent = point ? pointBand(whole, point) : whole;
  const clear = point ? extent : (shown ?? whole);
  const region = containingReadingRegionFor(element);
  return {
    element,
    contextNode: context,
    geometry,
    clear,
    extent,
    row: (passage?.attachment ?? extent).top,
    lastRow: passage?.attachment ? passage.attachment.top : extent.bottom,
    column: passage?.attachment?.left ?? null,
    margin: marginSpot(target, point),
    region,
    scroller: effectiveScroller(region ?? element),
  };
}

// The clear box chooses the initial seat; quoted words carry that seat through
// scrolling on every side, including under or over their stationary scrollport.
// The physical attachment point accompanies the solver's clear-box proxy; the
// mechanical selection retains that point with the scroll reading that measured it.
export function commentReference(place, reference) {
  return {
    contextElement: place.element,
    contextNode: place.contextNode,
    geometry: place.geometry,
    attachmentPoint: { left: place.column ?? place.extent.left, top: place.row },
    getBoundingClientRect: () => reference,
  };
}

export const COMMENT_GAP = 8;
// The least room a surface stands in: a floor chosen to hold the comment box's words
// and its controls over a few lines, which the room under the words must reach for a
// touch screen to prefer it, and a reading region must show for a surface to stand in it.
export const LEAST_HEIGHT = 96;

// The room both surfaces stand in: the part of the window the page shows, within the
// reading region's shown bounds where those hold the card's minimum width and the least
// height, else within the page shell, whose right edge stops short of the root
// scrollport's gutter and, for the comment box, an open panel's left edge (`right`). A
// pane a resize narrowed, or a short strip of one a scroll left, so yields to the window,
// which carries the surface rather than withdrawing a draft the user is writing. The
// boundary names the region's shown bounds it stands in (`inRegion`), which then cut the
// surface. Its `key` is what holds the side (`choose`): the window's edges, or the
// region's whole box size and the window's, since a scroll of the page moves and clips a
// region's shown bounds without changing the room it has, and a resize changes it.
export function commentBoundary({ region = null, right = Infinity } = {}) {
  const shown = (within) => shownWindow({ within, gap: COMMENT_GAP });
  const bounds = region && shownRegionBounds(region);
  const inRegion = bounds && shown(bounds);
  if (
    inRegion &&
    Math.ceil(inRegion.width) >= Math.ceil(cardMinimum()) &&
    inRegion.height >= LEAST_HEIGHT
  ) {
    const whole = region.body.getBoundingClientRect();
    return Object.assign(inRegion, {
      inRegion: bounds,
      key: [
        whole.width,
        whole.height,
        window.visualViewport.width,
        window.visualViewport.height,
      ],
    });
  }
  const shell = shown({ right: Math.min(shellRight(), right) });
  return Object.assign(shell, {
    inRegion: null,
    key: [shell.left, shell.top, shell.right, shell.bottom],
  });
}

const vertical = (side) => side === "top" || side === "bottom";

// Vertical room is read in viewport pixels, while the browser scrolls in local CSS
// pixels. Project available travel through the scroller's actual transformed axis;
// an inverted axis reverses which local end can expose room on the requested side.
function roomTravel(side, scroller) {
  const projection = scrollAxes(scroller).y.y;
  const direction = side === "top" ? -1 : 1;
  const localDirection = direction * Math.sign(projection);
  const local =
    localDirection < 0
      ? scroller.scrollTop
      : Math.max(0, scroller.scrollHeight - scroller.clientHeight - scroller.scrollTop);
  return { projection, direction, available: local * Math.abs(projection) };
}

// The room on `side` of `extent` the page can make: what shows there plus the scroll
// travel `scroller` has left that way, never more than the boundary holds.
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
export function commentSide({ clear, extent, boundary, width, scroller, coarse }) {
  const fits = (room) => Math.ceil(room) >= Math.ceil(width);
  if (fits(boundary.right - clear.right - COMMENT_GAP)) return "right";
  if (fits(clear.left - boundary.left - COMMENT_GAP)) return "left";
  const below = reachableRoom("bottom", extent, boundary, scroller);
  const above = reachableRoom("top", extent, boundary, scroller);
  // Opening an overlay cannot spend scroll travel. Prefer a side that can already
  // show the compact surface; reachable room then decides where it can grow.
  const fitsBelow = below.shown >= LEAST_HEIGHT;
  const fitsAbove = above.shown >= LEAST_HEIGHT;
  if (fitsBelow !== fitsAbove) return fitsBelow ? "bottom" : "top";
  if (coarse && below.reachable >= LEAST_HEIGHT) return "bottom";
  return below.reachable > above.reachable ||
    (below.reachable === above.reachable && below.shown > above.shown)
    ? "bottom"
    : "top";
}

// The card's minimum width chooses the side and whether both surfaces stand past the
// margin row. Its preferred measure caps the card's width. `commentPlacement` reads
// the minimum itself, so the comment box and its card share one placement threshold.
const rootLength = (name) =>
  parseFloat(getComputedStyle(document.documentElement).getPropertyValue(name));
export const cardMinimum = () => rootLength("--thread-card-min");
export const cardMeasure = () => rootLength("--thread-card");

/* One surface's placement: the side it holds and its inline attachment.

   `choose` holds a side, choosing one where none is held or the boundary or `extent`'s
   width has changed, and says whether it chose afresh. `options` then gives
   `computePosition` the reference to stand by, its placement and its middleware.
   `landed` takes the answer's inline start and where the rule stood the surface's top
   and foot before the boundary shifted it in, from the rule's line, which `heldAt`
   then offers a `hold` to keep it there; it returns the surface's `scale`. `plane` names
   the constraint that bound the answer (floating.js): `"page"` where the rule's line
   holds the surface, and where the boundary shifted it in, the edge it stands against
   and that edge's client line. `line` is where, in client pixels, the held side's line
   stands now.
   `forget` drops the side so the next placement chooses again, and `scrolled` keeps it
   across the scroll the surface itself asked for (`makeRoom`).

   `capture` is an opaque reading carried inside the editor's frame, whose `box` is a
   client rectangle. `adopt(frame)` queues that handoff for the next `choose`, which
   returns its initial `{ top, foot }` as `hold` until `landed` confirms a position.
   A superseded computation retains that hold. The placement owns its carried inline
   offset from the passage's column, else `clear`'s left edge. That column moves with
   quoted words even when their scrollport stays still. A normal beside landing owns
   the same offset, so renewing placement follows the attachment native motion carries.
   `hold` supplied to `options` names only a block edge, relative to the passage's
   line when quoted, else the initial side's clearance edge. Without an explicit
   edge, the landed seat holds its growing surface by its foot above and top elsewhere,
   so an editor needs no transcript reading to keep its attachment while typing.

   `fit({ side, width, height, scale })` sizes the surface for the room its side gives, in its
   positioning space. Its declared minimum is limited only by the boundary, never by
   its passage's column.
   The intended inline start caps growth, before a restored draft's own width can
   shift it. On the left, the surface instead holds its right edge clear of the
   target and grows toward the boundary; keeping its initial left edge would let
   a longer draft grow across the words it comments on. */
export function commentPlacement() {
  let side = null;
  let inline = null;
  let input = null;
  let pending = null;
  let carriedInline = null;
  let initialHold = null;
  let quoted = false;
  // The edge held at the last landing and the reading it answered (`holding`), and the
  // reading the placement in flight answers, which its landing records.
  let held = null;
  let reading = null;
  const forget = () => {
    side = null;
    inline = null;
    input = null;
    pending = null;
    carriedInline = null;
    initialHold = null;
    held = null;
    reading = null;
  };
  const line = (clear, row) =>
    quoted
      ? row
      : side === "bottom"
        ? (clear?.bottom ?? row)
        : side === "top"
          ? (clear?.top ?? row)
          : row;
  return {
    get side() {
      return side;
    },
    // Mechanical handoff between the editor's transparent frame and its sent card.
    capture() {
      return { side, boundary: input?.slice(1, 5) ?? null };
    },
    adopt(frame) {
      forget();
      pending = frame;
    },
    forget,
    // Which edge this placement holds, `top` or `foot`, from what the caller reports:
    // the transcript's extent, whether the user is drafting, the latest turn
    // (`{ key, author }`) and the draft's words. `fresh` and `hold` are `choose`'s.
    holding({ fresh, hold, transcript, drafting, latest = null, draftText = "" }) {
      if (hold) held = { ...hold, transcript };
      if (fresh) held = null;
      const turned = held && Math.abs(transcript - held.transcript) > 0.5;
      // A turn changes the transcript on one pass, then the card's own size changes
      // its measurement on the next. Borrow the reply's line for that turn, keyed by
      // the projected message's stable key so admitting a Send keeps the same hold. A
      // later reading turn or a new edit releases it; an arriving turn while drafting
      // borrows it anew, and a Send borrows it through the handoff out of the reply row.
      const newDraft = drafting && !held?.drafting;
      const continuedDraft = drafting && draftText && draftText !== held?.draftText;
      const keepReplyLine = Boolean(
        latest &&
        !newDraft &&
        !continuedDraft &&
        ((held?.replyTurn && held.replyTurn === latest.key) ||
          (turned && (drafting || (held?.drafting && latest.author === "user")))),
      );
      reading = {
        transcript,
        drafting,
        replyTurn: keepReplyLine ? latest.key : null,
        draftText,
      };
      // Adoption holds the message's start: expanded composer choices may add a row
      // below it that the thread does not carry. Later placements use the surface's own
      // top/foot reading, including the normal above-side and reply-line holds.
      return !hold && (keepReplyLine || (!drafting && side === "top")) ? "foot" : "top";
    },
    // The held edge's offset for `options`' `hold`, and the height between the held
    // top and foot, which caps a held surface no shorter than it last stood.
    heldAt: (edge) => held && { [edge]: held[edge] },
    heldHeight: () => (held ? held.foot - held.top : 0),
    scrolled() {
      input = null;
    },
    line,
    choose({
      clear,
      extent = clear,
      boundary,
      row = clear?.top ?? boundary.top,
      column = null,
      scroller,
      coarse,
    }) {
      quoted = column !== null;
      // No visible attachment puts the editor in the window. The authored subject
      // remains its semantic anchor; no rectangle here pretends to represent it.
      const unanchored = !clear;
      extent ??= boundary;
      const key = [Number(unanchored), ...boundary.key, extent.left, extent.right];
      const frame = pending;
      pending = null;
      const adopted =
        frame?.placement.boundary &&
        key
          .slice(1, 5)
          .every(
            (value, index) => Math.abs(value - frame.placement.boundary[index]) <= 0.5,
          );
      if (adopted) {
        // A draft can have lost its visible attachment before Send. Its card still
        // starts at that frame, then follows the card's attachment from this choice.
        ({ side } = frame.placement);
        if (side !== "left")
          carriedInline = frame.box.left - (column ?? clear?.left ?? boundary.left);
        const top = frame.box.top - line(clear, row);
        initialHold = { top, foot: top + frame.box.height };
      } else if (
        input &&
        key.some((value, index) => Math.abs(value - input[index]) > 0.5)
      ) {
        forget();
      }
      input = key;
      const fresh = side === null;
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
        ...(initialHold ? { hold: initialHold } : {}),
      };
    },
    options(
      ui,
      {
        clear,
        row,
        lastRow = row,
        column = null,
        margin = null,
        boundary,
        fit,
        hold = null,
      },
    ) {
      const minimumWidth = cardMinimum();
      const across = vertical(side);
      const unanchored = !clear;
      // Floating UI reads a window attachment point for the unanchored posture,
      // sharing the same sizing, shift and coordinate conversion as an anchored box.
      clear ??= new DOMRect(boundary.left, boundary.top, minimumWidth, 0);
      // Beside on the right, keep the margin row usable when the room past it
      // holds the card's minimum; otherwise the surface stands over it.
      const past =
        side === "right" &&
        margin &&
        margin.right > clear.right + 0.5 &&
        boundary.right - margin.right - COMMENT_GAP >= minimumWidth
          ? margin.right
          : null;
      const box =
        past === null
          ? clear
          : new DOMRect(clear.left, clear.top, past - clear.left, clear.height);
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
      const overflow = { boundary: [], rootBoundary: boundary, padding: 0 };
      let heldIn = false;
      const attachment = ui.limitShift(() => ({
        mainAxis: !across,
        crossAxis: across,
      }));
      // Client pixels per positioning-space pixel, the rule's line there, and beside, the
      // last line the surface may still stand level with.
      const scaled = {
        name: "scaled",
        async fn(state) {
          const { rects } = state;
          const scale = await positioningScale(state);
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
      const measure = (state) => state.middlewareData.scaled;
      const heldEdge = hold
        ? hold()
        : held && (side === "top" ? { foot: held.foot } : { top: held.top });
      // It also names the block edge it keeps still, which floating.js stands the
      // surface by, so growth moves the other edge in the layout that grows it.
      const holding = (heldEdge || carriedInline !== null) && {
        name: "hold",
        fn(state) {
          const edge = !across && heldEdge;
          const data = { edge: heldEdge && ("foot" in heldEdge ? "bottom" : "top") };
          const { line, attachmentInline, scale } = measure(state);
          const position = {};
          if (carriedInline !== null)
            position.x = attachmentInline + carriedInline / scale.x;
          if (edge)
            position.y =
              "foot" in edge
                ? line + edge.foot / scale.y - state.rects.floating.height
                : line + edge.top / scale.y;
          return { ...position, data };
        },
      };
      const size = ui.size({
        ...overflow,
        apply(state) {
          const { scale } = measure(state);
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
            height: state.availableHeight,
            scale,
          });
        },
      });
      // A fresh surface may slide into the complete clipping rectangle: size after
      // shift. A held edge grows toward the opposite boundary: size before shift,
      // reading that edge as its sizing direction without changing its attachment.
      // Drop the preceding pass's shift data when size resets the measurements;
      // its permission to shift must not widen a held edge's available height.
      const sizing = heldEdge
        ? {
            ...size,
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
          const top =
            edge &&
            measure(state).line -
              state.rects.reference.y +
              ("foot" in edge
                ? edge.foot / scale.y - state.rects.floating.height
                : edge.top / scale.y);
          return {
            mainAxis: edge
              ? side === "top"
                ? -top - state.rects.floating.height
                : top - state.rects.reference.height
              : COMMENT_GAP / (across ? scale.y : scale.x),
            crossAxis: across
              ? measure(state).column - state.rects.reference.x + (inline ?? 0)
              : (row - COMMENT_GAP - box.top) / scale.y,
          };
        }),
        holding,
        heldEdge && sizing,
        ui.shift({
          ...overflow,
          mainAxis: true,
          crossAxis: true,
          limiter: {
            ...attachment,
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
              heldIn = Math.abs(limited.y - state.y) < 0.5;
              return limited;
            },
          },
        }),
        !heldEdge && sizing,
      ].filter(Boolean);
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
            ? { edge: "top", at: boundary.top - COMMENT_GAP }
            : { edge: "bottom", at: boundary.bottom + COMMENT_GAP };
        },
      };
    },
    landed({ x, y, middlewareData }) {
      initialHold = null;
      const { scale, column, attachmentInline, line } = middlewareData.scaled;
      // A left-side surface grows toward the boundary, keeping its right edge beside
      // the target. Holding its compact left edge would widen it over the target.
      if (vertical(side)) inline ??= x - column;
      else if (side !== "left") carriedInline ??= (x - attachmentInline) * scale.x;
      const top = (y - (middlewareData.shift?.y ?? 0) - line) * scale.y;
      const spot = { top, foot: top + middlewareData.held.height * scale.y };
      // The reading this placement answered, so a turn that joined while it was worked
      // out is one the next placement still sees join.
      held = { ...spot, ...reading };
      return { scale };
    },
  };
}
