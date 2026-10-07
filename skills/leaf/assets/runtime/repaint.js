/* One frame for repainting the user's standing and chrome geometry. Boot supplies the
   phases after every module has evaluated, in this fixed order; callers only invalidate
   the frame. A document supplies the phases it has: a live page paints standing,
   layout and keys; an interactive export, which attaches no chrome, paints only its
   widgets' standing geometry and keys.

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

let phases = null;
let frame = 0;
let movePage = false;

export function mountRepaint({
  reflectFirstScopes,
  reflectKeys,
  paintStandingContent,
  syncLayout,
  pageShifted,
  paintStandingGeometry,
}) {
  phases = {
    reflectFirstScopes,
    reflectKeys,
    paintStandingContent,
    syncLayout,
    pageShifted,
    paintStandingGeometry,
  };
  onStanding(requestFrame);
  requestFrame();
}

function requestFrame() {
  // A capability can invalidate while its importing application is still being
  // constructed. Mount owns the first frame; until then only the page-shift bit is
  // recorded. The initial full paint reads the latest standing when it can run.
  if (!phases || frame) return;
  frame = nextRender(() => {
    frame = 0;
    const shiftPage = movePage;
    movePage = false;
    phases.reflectFirstScopes?.();
    phases.paintStandingContent?.();
    phases.syncLayout?.();
    if (shiftPage) phases.pageShifted?.();
    phases.paintStandingGeometry?.();
    phases.reflectKeys?.();
  });
}

export function repaint() {
  requestFrame();
}

export function repaintPage() {
  movePage = true;
  requestFrame();
}
