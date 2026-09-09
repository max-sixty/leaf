/* One frame for repainting the reader's standing and chrome geometry. Boot supplies the
   fixed phases after every module has evaluated; callers only invalidate the frame.

   Pending work is cleared before the phases run. An invalidation raised by a phase
   therefore schedules another frame instead of being lost in the frame being flushed. */

let phases = null;
let frame = 0;
let movePage = false;

export function wireRepaint({
  reflectFirstScopes,
  paintStandingContent,
  syncLayout,
  pageShifted,
  paintStandingGeometry,
}) {
  phases = {
    reflectFirstScopes,
    paintStandingContent,
    syncLayout,
    pageShifted,
    paintStandingGeometry,
  };
}

function requestFrame() {
  if (frame) return;
  frame = requestAnimationFrame(() => {
    frame = 0;
    const shiftPage = movePage;
    movePage = false;
    if (!phases)
      throw new Error("leaf: leaf.js did not boot; nothing owns the repaint frame");
    phases.reflectFirstScopes();
    phases.paintStandingContent();
    phases.syncLayout();
    if (shiftPage) phases.pageShifted();
    phases.paintStandingGeometry();
  });
}

export function repaint() {
  requestFrame();
}

export function repaintPage() {
  movePage = true;
  requestFrame();
}
