/* One frame for repainting the user's current location and chrome geometry. Boot supplies the
   painters after every module has evaluated, each a named slot, and this owner calls
   them in its fixed order; callers only invalidate the frame. Chrome layout splits the
   frame: the painters before it draw content whose boxes it measures, and those after
   it read the laid-out result. A document supplies the painters it has: a live page
   paints current location, layout and keys; an interactive export, which attaches no chrome,
   paints only its widgets' boxes and keys. Keys are both of their slots, since a new
   declaration is read only at the frame's head and the page-wide pass at its tail.
   No painter imports a feature's commands or schedules the full presenter while
   drawing its own geometry.

   Pending work is cleared before the phases run. An invalidation raised by a phase
   therefore queues another repaint, which the rendering loop runs before this frame
   paints, instead of being lost in the repaint being flushed.

   A focus move is the one change in where the user is that no state writer
   sees, so this owner asks for the frame itself, in every document that mounts it, on
   every change where they are publishes (focus.js, `onCurrentLocation`), a move inside a
   widget's shadow tree included: the ring, the line, and a box's focus hint all answer
   it. A chrome placement that puts the user back where they were publishes nothing:
   the margin moves a row between lanes when its target's scroller changes, and
   answering that as a move would paint the fixed chrome, whose layout pass asks for
   the next placement. */

import { onCurrentLocation, onFocusVisibility } from "./focus.js";
import { nextRender } from "./rendering.js";

let painters = null;
let frame = 0;
let movePage = false;

export function mountRepaint(slots) {
  painters = slots;
  onCurrentLocation(requestFrame);
  onFocusVisibility(requestFrame);
  requestFrame();
}

function requestFrame() {
  // A capability can invalidate while its importing application is still being
  // constructed. Mount owns the first frame; until then only the page-shift bit is
  // recorded. The initial full paint reads the latest current location when it can run.
  if (!painters || frame) return;
  frame = nextRender(() => {
    frame = 0;
    const shiftPage = movePage;
    movePage = false;
    const p = painters;
    p.reflectFirstScopes?.();
    // Content whose resulting boxes chrome layout must measure.
    p.markHere?.();
    p.paintCurrentLocation?.();
    // The page and its compact Page Map projection read the same current location after both
    // feature painters have settled it. Selection changes only the entry representing
    // that reading; focus, open state, and agent work keep their separate contours.
    p.paintSelectedMarginEntries?.();
    // A finger's stand-ins for the keys, read where the register is read.
    p.paintTouchControls?.();
    // A close request takes the step Escape would (close-requests.js).
    p.paintCloseRequests?.();
    // What the panel says between notices about where the keyboard has the user.
    p.paintStatusContext?.();
    p.syncLayout?.();
    if (shiftPage) p.pageShifted?.();
    // Contextual entry hints read the destination after chrome layout. Lit fields
    // follow this reading; their committed controls invalidate the key projection.
    p.publishInputHint?.();
    // The chips are where the user can go, beside the ring saying where they are and the
    // line saying what the next press does: one paint, because a chip repainted by its
    // own door alone went stale on the door it did not have, as when a poll that retires
    // an obligation moves the list under an armed window.
    p.paintGoToHints?.();
    p.paintTargetPickerHints?.();
    p.paintCommandHints?.();
    p.paintCoreControls?.();
    p.paintVersionShortcuts?.();
    p.reflectKeys?.();
  });
}

export function repaint() {
  requestFrame();
}

export function repaintPage() {
  movePage = true;
  requestFrame();
}
