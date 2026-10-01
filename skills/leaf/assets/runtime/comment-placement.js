/* Where a comment's surfaces stand: the comment box the user types in
   (composing/surface.js) and the thread card the sent comment becomes
   (margin-projection.js). They are one comment at two moments, so one rule places
   both, and Send changes the surface without moving the place. Floating UI does the
   placing (floating.js): this module chooses the side and names the boxes, and
   Floating UI's offset, size and shift do the rest.

   A comment stands by what it is about, read four ways. `clear` is the box it keeps
   clear of, as the page shows it: the paragraph holding a passage, the element, or the
   row a pointing gesture named in it (pointed-place.js). `extent` is that box whole,
   however much of it a scroll has clipped, which is what the room around it is measured
   from. `row` is the line it stands level with beside `clear`: a passage's first line,
   else `clear`'s top. `margin` is where across the page the margin row for it stands,
   or would stand in the rail once its thread is sent (margin-layout.js, `marginSpot`),
   or nothing where no row stands and its rows would be pins.

   Both stand in one boundary (`commentBoundary`): the part of the window the page shows,
   within the reading region where that holds a card, else within the page shell.

   The side is chosen once, for the thread's footprint rather than the box's, so the box
   stands where its card can: right of `clear` where that room holds the card's minimum
   width (`--thread-card-min`), else left of it where that room does, else under or over
   it, whichever side the page can make more room on. That room is what shows there plus
   what the reading region can still scroll there, so the side is a fact of where the
   comment is in the document, not of how far the page is scrolled; only where both
   sides can make all the room the boundary has does the one showing more take it. A
   touch screen takes under wherever the page can make the least room a surface stands
   in there (`LEAST_HEIGHT`), since the platform's selection menu stands over the words
   and Leaf cannot read where. The side is held until the boundary or `extent`'s width
   changes (a resize, a pane that narrows, a reflow), which chooses afresh; a scroll
   clipping `clear` does not.

   Beside, the surface's top stands level with `row`, and past its margin row where that
   reaches past `clear` and the room beyond it holds the card's minimum, so the row its
   thread has or will have stays in view, at the cost of the card's width; where it
   does not, the surface stands over the row. Neither choice reads the surface's own
   width or height, so the box and the card make the same one. Under or over, its inline
   start is where the card's minimum width would end on `clear`'s right edge, and it
   keeps that start as it widens.

   It grows away from what it is about, down beside or under and up over it (floating.js,
   `held`), and the boundary holds it in only while what it stands by is in the window:
   Floating UI's shift keeps it inside, and its limiter lets it leave with `row` beside,
   or with `clear` under or over, once a scroll carries that away. Once wholly outside
   that boundary, a seen reference keeps the surface's unshifted attachment: CSS anchor
   positioning carries it back in the compositor before a scroll event re-places it,
   so shifting offscreen would paint a stale attachment on its first returning frame.
   A surface whose
   `clear` has not stood in the boundary since its side was chosen, as after a resize
   that left what it is about out of the window, stays in the window until it has.
   Under or over, a surface taller than the room shown there first has the reading
   region scroll to make it (`makeRoom`), as far as it can, so it stands clear of what
   it is about rather than sliding across it.

   A surface may hold one edge at an offset of its own choosing (`hold`), in client
   pixels from its line: `row` beside, and under or over the edge of `clear` it stands
   clear of, so a reflow of what it is about carries it. The card keeps its reply row
   still that way while a turn joins the transcript above it.

   Every box here is a client rectangle. Floating UI works in the surface's positioning
   space, which a transformed ancestor scales, so each length crosses by the reference's
   scale, and `fit` is handed lengths in that space, as CSS sizes the surface in it. */

import { shellRight, shownWindow } from "./geometry.js";
import { clamp } from "./rect.js";
import { moveScrollerBy } from "./scrolling.js";

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
// boundary names the region it stands in (`inRegion`), which then cuts the surface.
export function commentBoundary({ region = null, right = Infinity } = {}) {
  const shown = (within) => shownWindow({ within, gap: COMMENT_GAP });
  const inRegion = region && shown(region);
  return inRegion &&
    Math.ceil(inRegion.width) >= Math.ceil(cardMinimum()) &&
    inRegion.height >= LEAST_HEIGHT
    ? Object.assign(inRegion, { inRegion: region })
    : Object.assign(shown({ right: Math.min(shellRight(), right) }), {
        inRegion: null,
      });
}

const vertical = (side) => side === "top" || side === "bottom";

// The room on `side` of `extent` the page can make: what shows there plus the scroll
// travel `scroller` has left that way, never more than the boundary holds.
export function reachableRoom(side, extent, boundary, scroller) {
  const shown =
    side === "top"
      ? extent.top - boundary.top - COMMENT_GAP
      : boundary.bottom - extent.bottom - COMMENT_GAP;
  const travel =
    side === "top"
      ? scroller.scrollTop
      : Math.max(0, scroller.scrollHeight - scroller.clientHeight - scroller.scrollTop);
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
// and the least room a surface stands in cannot show together, no scroll makes that
// room, and the surface stands over what it is about where it is.
export function makeRoom(side, clear, extent, height, boundary, scroller) {
  if (extent.height + COMMENT_GAP + LEAST_HEIGHT > boundary.height) return false;
  const overflow =
    side === "top"
      ? boundary.top - (clear.top - COMMENT_GAP - height)
      : clear.bottom + COMMENT_GAP + height - boundary.bottom;
  const travel =
    side === "top"
      ? scroller.scrollTop
      : Math.max(0, scroller.scrollHeight - scroller.clientHeight - scroller.scrollTop);
  const movement = Math.max(0, Math.min(overflow, travel));
  if (movement <= 0.5) return false;
  const before = scroller.scrollTop;
  moveScrollerBy(scroller, side === "top" ? -movement : movement);
  return Math.abs(scroller.scrollTop - before) > 0.5;
}

// The side a comment's surface takes, as a Floating UI side.
export function commentSide({ clear, extent, boundary, width, scroller, coarse }) {
  const fits = (room) => Math.ceil(room) >= Math.ceil(width);
  if (fits(boundary.right - clear.right - COMMENT_GAP)) return "right";
  if (fits(clear.left - boundary.left - COMMENT_GAP)) return "left";
  const below = reachableRoom("bottom", extent, boundary, scroller);
  const above = reachableRoom("top", extent, boundary, scroller);
  if (coarse && below.reachable >= LEAST_HEIGHT) return "bottom";
  return below.reachable > above.reachable ||
    (below.reachable === above.reachable && below.shown > above.shown)
    ? "bottom"
    : "top";
}

// The card's minimum width, which chooses the side for both surfaces and whether they
// stand past the margin row, and its preferred measure.
const rootLength = (name) =>
  parseFloat(getComputedStyle(document.documentElement).getPropertyValue(name));
export const cardMinimum = () => rootLength("--thread-card-min");
export const cardMeasure = () => rootLength("--thread-card");

/* One surface's placement: the side it holds and its inline start under or over.

   `choose` holds a side, choosing one where none is held or the boundary or `extent`'s
   width has changed, and says whether it chose afresh. `options` then gives
   `computePosition` the reference to stand by, its placement and its middleware.
   `landed` takes the answer's inline start, and returns what the answer says about the
   surface: its `scale` and where the rule stood its held edge before the boundary
   shifted it in (`spot`, `{ top }` and `{ foot }` from the rule's line), which is what a
   `hold` returns to keep it there. `heldIn` reads from the answer whether the boundary
   rather than `clear` holds it on the block axis, which stands it in the window's plane
   (floating.js). `line` is where, in client pixels, the held side's line stands now.
   `forget` drops the side so the next placement chooses again, and `scrolled` keeps it
   across the scroll the surface itself asked for (`makeRoom`).

   `fit({ side, width, scale })` sizes the surface for the room its side gives: the width
   of its lane, in its positioning space, with the scale that space has. */
export function commentPlacement() {
  let side = null;
  let inline = null;
  let input = null;
  // Whether `clear` has stood in the boundary since the side was chosen.
  let seen = false;
  return {
    get side() {
      return side;
    },
    forget() {
      side = null;
      inline = null;
      input = null;
      seen = false;
    },
    scrolled() {
      input = null;
    },
    line(clear, row) {
      return side === "bottom" ? clear.bottom : side === "top" ? clear.top : row;
    },
    choose({ clear, extent = clear, boundary, minimum, scroller, coarse }) {
      const key = [
        boundary.left,
        boundary.top,
        boundary.right,
        boundary.bottom,
        extent.left,
        extent.right,
      ];
      if (input && key.some((value, index) => Math.abs(value - input[index]) > 0.5)) {
        side = null;
        inline = null;
        seen = false;
      }
      input = key;
      const fresh = side === null;
      side ??= commentSide({
        clear,
        extent,
        boundary,
        width: minimum.width,
        scroller,
        coarse,
      });
      return { side, fresh };
    },
    options(ui, { clear, row, margin = null, boundary, minimum, fit, hold = null }) {
      const across = vertical(side);
      // Once seen, a reference wholly outside the boundary keeps its declared attachment.
      // Native scrolling carries its CSS anchor back before this middleware runs again.
      const visible = clear.bottom > boundary.top && clear.top < boundary.bottom;
      seen ||= visible;
      // Beside on the right, the margin row is kept clear too where the room past it
      // holds the card's minimum; where it does not, the surface stands over it.
      const past =
        side === "right" &&
        margin &&
        margin.right > clear.right + 0.5 &&
        boundary.right - margin.right - COMMENT_GAP >= minimum.width
          ? margin.right
          : null;
      const box =
        past === null
          ? clear
          : new DOMRect(clear.left, clear.top, past - clear.left, clear.height);
      const overflow = { boundary: [], rootBoundary: boundary, padding: 0 };
      let heldIn = false;
      const attachment = ui.limitShift(() => ({
        mainAxis: !across,
        crossAxis: across,
      }));
      // Client pixels per positioning-space pixel, and the rule's line there.
      const scaled = {
        name: "scaled",
        fn({ rects }) {
          const scale = {
            x: box.width / rects.reference.width || 1,
            y: box.height / rects.reference.height || 1,
          };
          return {
            data: {
              scale,
              reference: rects.reference,
              line:
                side === "bottom"
                  ? rects.reference.y + rects.reference.height
                  : side === "top"
                    ? rects.reference.y
                    : rects.reference.y + (row - box.top) / scale.y,
            },
          };
        },
      };
      const measure = (state) => state.middlewareData.scaled;
      const holding = hold && {
        name: "hold",
        fn(state) {
          const edge = hold();
          if (!edge) return {};
          const { line, scale } = measure(state);
          return {
            y:
              "foot" in edge
                ? line + edge.foot / scale.y - state.rects.floating.height
                : line + edge.top / scale.y,
          };
        },
      };
      const middleware = [
        scaled,
        ui.offset((state) => {
          const { scale } = measure(state);
          return {
            mainAxis: COMMENT_GAP / (across ? scale.y : scale.x),
            crossAxis: across
              ? state.rects.reference.width + (inline ?? -minimum.width / scale.x)
              : (row - COMMENT_GAP - box.top) / scale.y,
          };
        }),
        holding,
        ui.size({
          ...overflow,
          apply(state) {
            const { scale } = measure(state);
            const lane =
              side === "right"
                ? boundary.right - box.right - COMMENT_GAP
                : side === "left"
                  ? clear.left - boundary.left - COMMENT_GAP
                  : boundary.right -
                    (box.right + (inline ?? -minimum.width / scale.x) * scale.x);
            fit({
              side,
              width: Math.max(0, Math.min(state.availableWidth, lane / scale.x)),
              scale,
            });
          },
        }),
        (!seen || visible) &&
          ui.shift({
            ...overflow,
            mainAxis: true,
            crossAxis: true,
            limiter: {
              ...attachment,
              fn(state) {
                if (!seen) {
                  heldIn = true;
                  return { x: state.x, y: state.y };
                }
                // Beside, it goes with the line it stands level with, overlapping it by
                // no less than an edge; under or over, with the box it keeps clear of.
                const limited = across
                  ? attachment.fn(state)
                  : {
                      x: state.x,
                      y: clamp(
                        state.y,
                        measure(state).line - state.rects.floating.height,
                        measure(state).line,
                      ),
                    };
                heldIn = Math.abs(limited.y - state.y) < 0.5;
                return limited;
              },
            },
          }),
      ].filter(Boolean);
      return {
        reference: box,
        placement: `${side}-start`,
        middleware,
        heldIn: ({ middlewareData }) =>
          heldIn && Math.abs(middlewareData.shift?.y ?? 0) >= 0.5,
      };
    },
    landed({ x, y, middlewareData }) {
      const { scale, reference, line } = middlewareData.scaled;
      if (vertical(side)) inline ??= x - (reference.x + reference.width);
      const top = (y - (middlewareData.shift?.y ?? 0) - line) * scale.y;
      return {
        scale,
        spot: { top, foot: top + middlewareData.held.height * scale.y },
      };
    },
  };
}
