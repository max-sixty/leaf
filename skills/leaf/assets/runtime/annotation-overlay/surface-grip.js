/* The grip a floating comment surface is carried by: the comment box
   (composing/floating-response.js) and the thread card (thread-preview.js).

   While the pointer is down the surface follows it by a CSS `translate`, held inside the
   window, and no placement is asked for. On release the surface's moved box is handed to
   its placement as a frame to adopt (comment-placement.js, `adopt`), the same handoff a
   sent comment's box makes to its card, so from then on the surface stands where the user
   put it relative to what it is about, and scrolling carries it there. The move lasts as
   long as that placement holds its side: a resize, another thread, or closing the
   surface chooses afresh.

   A press on the grip takes no focus, so the comment being written keeps its caret. The
   move is presentation, not a decision, so nothing reaches the log. */
import { el } from "../widget-elements.js";
import { clamp } from "../rect.js";
import { commentBoundary } from "./comment-placement.js";

// Below this travel a press is not a move, and the surface stays where it stood.
const SLOP = 3;

export function surfaceGrip({ surface, dropped }) {
  const grip = el("div", "lf-ui lf-surface-grip");
  grip.title = "Drag to move";
  let held = null;
  grip.addEventListener("pointerdown", (event) => {
    if (held || !event.isPrimary || event.button !== 0) return;
    event.preventDefault();
    grip.setPointerCapture(event.pointerId);
    const box = surface.getBoundingClientRect();
    held = {
      pointerId: event.pointerId,
      x: event.clientX,
      y: event.clientY,
      box,
      bounds: commentBoundary(),
      scale: box.width / surface.offsetWidth || 1,
      moved: false,
    };
    surface.toggleAttribute("data-lf-carried", true);
  });
  grip.addEventListener("pointermove", (event) => {
    if (held?.pointerId !== event.pointerId) return;
    const { box, bounds, scale } = held;
    // How far the pointer has carried the surface along one axis, short of the window.
    const travel = (from, start, end) =>
      clamp(
        from,
        Math.min(0, bounds[start] - box[start]),
        Math.max(0, bounds[end] - box[end]),
      );
    const dx = travel(event.clientX - held.x, "left", "right");
    const dy = travel(event.clientY - held.y, "top", "bottom");
    held.moved ||= Math.hypot(dx, dy) >= SLOP;
    if (held.moved) surface.style.translate = `${dx / scale}px ${dy / scale}px`;
  });
  // Pressing the grip is not an outside press on the page's open composer.
  grip.addEventListener("mousedown", (event) => event.stopPropagation());
  const finish = (event) => {
    if (held?.pointerId !== event.pointerId) return;
    const { moved } = held;
    held = null;
    const box = surface.getBoundingClientRect();
    surface.style.removeProperty("translate");
    surface.removeAttribute("data-lf-carried");
    if (moved && event.type === "pointerup") dropped(box);
  };
  for (const ending of ["pointerup", "pointercancel", "lostpointercapture"])
    grip.addEventListener(ending, finish);
  return grip;
}
