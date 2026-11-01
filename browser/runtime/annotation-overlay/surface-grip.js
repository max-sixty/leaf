/* The grip a floating comment surface is carried by, a band along its edge: the comment
   box (composing/floating-response.js) and the thread card (thread-preview.js).
   annotation-chrome.css draws the band and bounds where it takes a press.

   While the pointer is down the surface stays under it by a CSS `translate`, held
   inside the boundary its placement would stand it in now (`bounds`), down to the room
   across the columns it is carried to (comment-placement.js, `commentBoundary`). Its owner places
   it afresh only once the carry ends (`data-lf-carried`); the browser's anchoring still
   carries it through a scroll, so each frame of the carry measures the translate
   against where it stands then, and the surface stays under the pointer. On release
   the owner is told (`dropped`), with the surface's moved box where it moved, which it
   hands to its placement as a frame to adopt (comment-placement.js, `adopt`), the same
   handoff a sent comment's box makes to its card, so from then on the surface stands
   where the user put it relative to what it is about, and scrolling carries it there.
   The carry stays in place until the owner commits that placement and calls `placed`;
   clearing it before the asynchronous solve returns briefly restores the old box and
   loses the grip's hover. The move lasts as long as that placement holds its side:
   a resize, another thread, or closing the surface chooses afresh.

   A press on the grip takes no focus, so the comment being written keeps its caret. The
   move is presentation, not a decision, so nothing reaches the log. */
import { el } from "../widget-elements.js";
import { clamp } from "../rect.js";
import { cancelAnimation, nextAnimation } from "../rendering.js";
import { layoutPx } from "../keeps.js";

// Below this travel a press is not a move, and the surface goes back to where its
// placement stands it.
const SLOP = 3;

/** @typedef {{pointerId: number, start: {x: number, y: number},
 * travel: {x: number, y: number}, box: DOMRect, moved: boolean, frame: number}} Carry */
/** @param {{surface: HTMLElement,
 * bounds: () => import("../rect.js").Box & {across: (span: {left: number, right: number}) => import("../rect.js").Box},
 * dropped: (box: DOMRect | null) => void}} options */
export function surfaceGrip({ surface, bounds, dropped }) {
  const grip = el("div", "lf-ui lf-surface-grip");
  grip.title = "Drag to move";
  /** @type {Carry | null} */
  let held = null;
  let offset = { x: 0, y: 0 };
  const placed = () => {
    if (held) return;
    if (surface.style.translate) surface.style.removeProperty("translate");
    surface.removeAttribute("data-lf-carried");
    offset = { x: 0, y: 0 };
  };
  // Stands the surface at its grabbed box plus the pointer's travel, inside the
  // boundary as far as it fits, from wherever its placement has it now.
  /** @param {Carry} carry */
  function follow(carry) {
    const { box, travel } = carry;
    const boundary = bounds();
    carry.moved ||= Math.hypot(travel.x, travel.y) >= SLOP;
    const now = surface.getBoundingClientRect();
    /** @param {import("../rect.js").Box} room @param {number} at
     * @param {"left" | "top"} start @param {"right" | "bottom"} end @param {number} length */
    const within = (room, at, start, end, length) =>
      clamp(at, room[start], Math.max(room[start], room[end] - length));
    const x = within(boundary, box.left + travel.x, "left", "right", now.width);
    // Down, it is held in the room across the columns it now stands in.
    const room = boundary.across({ left: x, right: x + now.width });
    const spot = {
      x,
      y: within(room, box.top + travel.y, "top", "bottom", now.height),
    };
    const scale = {
      x: now.width / surface.offsetWidth || 1,
      y: now.height / surface.offsetHeight || 1,
    };
    // Where the placement stands it, without the carry's own translate.
    const placed = {
      x: now.left - offset.x * scale.x,
      y: now.top - offset.y * scale.y,
    };
    offset = {
      x: (spot.x - placed.x) / scale.x,
      y: (spot.y - placed.y) / scale.y,
    };
    const xShift = layoutPx(offset.x);
    const yShift = layoutPx(offset.y);
    const translate = xShift === "0px" && yShift === "0px" ? "" : `${xShift} ${yShift}`;
    if (surface.style.translate !== translate) surface.style.translate = translate;
  }
  // Each frame of the carry, since anchoring moves the surface with no event to say so.
  /** @param {Carry} carry */
  const frame = (carry) => {
    follow(carry);
    carry.frame = nextAnimation(() => frame(carry));
  };
  grip.addEventListener(
    "pointerdown",
    /** @param {PointerEvent} event */ (event) => {
      if (held || !event.isPrimary || event.button !== 0) return;
      event.preventDefault();
      grip.setPointerCapture(event.pointerId);
      held = {
        pointerId: event.pointerId,
        start: { x: event.clientX, y: event.clientY },
        travel: { x: 0, y: 0 },
        box: surface.getBoundingClientRect(),
        moved: false,
        frame: 0,
      };
      surface.toggleAttribute("data-lf-carried", true);
      const carry = held;
      carry.frame = nextAnimation(() => frame(carry));
    },
  );
  grip.addEventListener(
    "pointermove",
    /** @param {PointerEvent} event */ (event) => {
      if (held?.pointerId !== event.pointerId) return;
      held.travel = {
        x: event.clientX - held.start.x,
        y: event.clientY - held.start.y,
      };
    },
  );
  // Pressing the grip is not an outside press on the page's open composer.
  grip.addEventListener(
    "mousedown",
    /** @param {MouseEvent} event */ (event) => event.stopPropagation(),
  );
  /** @param {PointerEvent} event */
  const finish = (event) => {
    if (held?.pointerId !== event.pointerId) return;
    // The pointer's last travel may not have had its frame yet.
    follow(held);
    const { moved } = held;
    cancelAnimation(held.frame);
    held = null;
    const box = surface.getBoundingClientRect();
    if (!moved || event.type !== "pointerup") placed();
    dropped(moved && event.type === "pointerup" ? box : null);
  };
  grip.addEventListener("pointerup", finish);
  grip.addEventListener("pointercancel", finish);
  grip.addEventListener("lostpointercapture", finish);
  return { grip, placed };
}
