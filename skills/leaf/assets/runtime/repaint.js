/* One frame for repainting the user's standing and chrome geometry. Boot supplies the
   painters after every module has evaluated, each a named slot, and this owner calls
   them in its fixed order; callers only invalidate the frame. Chrome layout splits the
   frame: the painters before it draw content whose boxes it measures, and those after
   it read the laid-out result. A document supplies the painters it has: a live page
   paints standing, layout and keys; an interactive export, which attaches no chrome,
   paints only its widgets' boxes and keys. Keys are both of their slots, since a new
   declaration is read only at the frame's head and the page-wide pass at its tail.
   No painter imports a feature's commands or schedules the full presenter while
   drawing its own geometry.

   Pending work is cleared before the phases run. An invalidation raised by a phase
   therefore queues another repaint, which the rendering loop runs before this frame
   paints, instead of being lost in the repaint being flushed.

   A focus move is the one change in where the user is standing that no state writer
   sees, so this owner asks for the frame itself, in every document that mounts it, on
   every change where they stand publishes (focus.js, `onStanding`), a move inside a
   widget's shadow tree included: the ring, the line, and a box's focus hint all answer
   it. A chrome placement that puts the user back where they stood publishes nothing:
   the margin moves a row between lanes when its target's scroller changes, and
   answering that as a move would paint the standing chrome, whose layout pass asks for
   the next placement. */

import { onStanding } from "./focus.js";
import { nextRender } from "./rendering.js";

let painters = null;
let frame = 0;
let movePage = false;

export function mountRepaint(slots) {
  painters = slots;
  onStanding(requestFrame);
  requestFrame();
}

function requestFrame() {
  // A capability can invalidate while its importing application is still being
  // constructed. Mount owns the first frame; until then only the page-shift bit is
  // recorded. The initial full paint reads the latest standing when it can run.
  if (!painters || frame) return;
  frame = nextRender(() => {
    frame = 0;
    const shiftPage = movePage;
    movePage = false;
    const p = painters;
    p.reflectFirstScopes?.();
    // Content whose resulting boxes chrome layout must measure.
    p.markHere?.();
    p.paintStanding?.();
    // The page and its compact Page Map projection read the same standing after both
    // feature painters have settled it. Selection changes only the entry representing
    // that reading; focus, open state, and agent work keep their separate contours.
    p.paintSelectedMarginEntries?.();
    // A finger's stand-ins for the keys, whose step on the banner's row is a box chrome
    // layout measures, as the shortcut bar's words are.
    p.paintTouchControls?.();
    // The shortcut bar is geometry for every Go-to and target-picker hint painted around
    // it. Render its new words first, then let chrome-layout.js place that resulting box
    // before any consumer reads it. ResizeObserver remains the door for font, window, and
    // other size changes; state-driven content changes complete in this frame rather than
    // leaving placement and hints one observer frame behind.
    p.renderShortcutBar?.();
    p.syncLayout?.();
    if (shiftPage) p.pageShifted?.();
    // Controls and geometry that depend on the laid-out content above. Text boxes paint
    // first: their contextual hints read which box is shown, and the Go-to chips below
    // read each send button's aria-disabled to decide whether it is a destination.
    // Nothing a box paints changes geometry, a placeholder never widens its box and a
    // disabled send keeps its size, so chrome layout above measures the composer first.
    p.paintInputs?.();
    // The chips are where the user can go, beside the ring saying where they are and the
    // line saying what the next press does: one paint, because a chip repainted by its
    // own door alone went stale on the door it did not have, as when a poll that retires
    // a Question moves the list under an armed window.
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
