/* The grip a floating comment surface is carried by, a band along its edge: the comment
   box (composing/floating-response.js) and the thread card (thread-preview.js).
   annotation-chrome.css draws the band and bounds where it takes a press.

   While the pointer is down the surface stays under it by a CSS `translate`, held
   inside the boundary its placement would stand it in now (`bounds`). Its owner places
   it afresh only once the carry ends (`data-lf-carried`); the browser's anchoring still
   carries it through a scroll, so each frame of the carry measures the translate
   against where it stands then, and the surface stays under the pointer. On release
   the owner is told (`dropped`), with the surface's moved box where it moved, which it
   hands to its placement as a frame to adopt (comment-placement.js, `adopt`), the same
   handoff a sent comment's box makes to its card, so from then on the surface stands
   where the user put it relative to what it is about, and scrolling carries it there.
   The move lasts as long as that placement holds its side: a resize, another thread, or
   closing the surface chooses afresh.

   A press on the grip takes no focus, so the comment being written keeps its caret. The
   move is presentation, not a decision, so nothing reaches the log. */
import { el } from "../widget-elements.js";
import { clamp } from "../rect.js";
import { cancelAnimation, nextAnimation } from "../rendering.js";

// Below this travel a press is not a move, and the surface goes back to where its
// placement stands it.
const SLOP = 3;

export function surfaceGrip({ surface, bounds, dropped }) {
  const grip = el("div", "lf-ui lf-surface-grip");
  grip.title = "Drag to move";
  let held = null;
  // Stands the surface at its grabbed box plus the pointer's travel, inside the
  // boundary as far as it fits, from wherever its placement has it now.
  function follow() {
    const { box, travel, offset } = held;
    const boundary = bounds();
    held.moved ||= Math.hypot(travel.x, travel.y) >= SLOP;
    const now = surface.getBoundingClientRect();
    const within = (at, start, end, length) =>
      clamp(at, boundary[start], Math.max(boundary[start], boundary[end] - length));
    const spot = {
      x: within(box.left + travel.x, "left", "right", now.width),
      y: within(box.top + travel.y, "top", "bottom", now.height),
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
    held.offset = {
      x: (spot.x - placed.x) / scale.x,
      y: (spot.y - placed.y) / scale.y,
    };
    const translate = `${held.offset.x}px ${held.offset.y}px`;
    if (surface.style.translate !== translate) surface.style.translate = translate;
  }
  // Each frame of the carry, since anchoring moves the surface with no event to say so.
  const frame = () => {
    follow();
    held.frame = nextAnimation(frame);
  };
  grip.addEventListener("pointerdown", (event) => {
    if (held || !event.isPrimary || event.button !== 0) return;
    event.preventDefault();
    grip.setPointerCapture(event.pointerId);
    held = {
      pointerId: event.pointerId,
      start: { x: event.clientX, y: event.clientY },
      travel: { x: 0, y: 0 },
      offset: { x: 0, y: 0 },
      box: surface.getBoundingClientRect(),
      moved: false,
    };
    surface.toggleAttribute("data-lf-carried", true);
    held.frame = nextAnimation(frame);
  });
  grip.addEventListener("pointermove", (event) => {
    if (held?.pointerId !== event.pointerId) return;
    held.travel = { x: event.clientX - held.start.x, y: event.clientY - held.start.y };
  });
  // Pressing the grip is not an outside press on the page's open composer.
  grip.addEventListener("mousedown", (event) => event.stopPropagation());
  const finish = (event) => {
    if (held?.pointerId !== event.pointerId) return;
    // The pointer's last travel may not have had its frame yet.
    follow();
    const { moved } = held;
    cancelAnimation(held.frame);
    held = null;
    const box = surface.getBoundingClientRect();
    surface.style.removeProperty("translate");
    surface.removeAttribute("data-lf-carried");
    dropped(moved && event.type === "pointerup" ? box : null);
  };
  for (const ending of ["pointerup", "pointercancel", "lostpointercapture"])
    grip.addEventListener(ending, finish);
  return grip;
}
