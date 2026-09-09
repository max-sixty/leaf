/* One frame for repainting the reader's standing and chrome geometry. Boot supplies the
   fixed phases after every module has evaluated; callers only invalidate the frame.

   Pending work is cleared before the phases run. An invalidation raised by a phase
   therefore schedules another frame instead of being lost in the frame being flushed. */

let phases = null;
let frame = 0;
let movePage = false;

export function mountRepaint({
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
  requestFrame();
}

function requestFrame() {
  // A capability can invalidate while its importing application is still being
  // constructed. Mount owns the first frame; until then only the page-shift bit is
  // recorded. The initial full paint reads the latest standing when it can run.
  if (!phases || frame) return;
  frame = requestAnimationFrame(() => {
    frame = 0;
    const shiftPage = movePage;
    movePage = false;
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
