// `syncLayout` derives floating chrome placement and reservations from current chrome
// boxes, and asks which residents stand in the page's margin (`scheduleResidency`,
// content-layout.js), the one posture JavaScript decides for the document: it reads the
// room beside `main`, which the page's own CSS sets. CSS owns the rest of the shell:
// `body` is the named `lf-shell` inline-size container, and a query on it may answer a
// narrow column's facts. `layoutSizes` schedules `syncLayout` and page repaint after a
// width change. No auxiliary surface changes the shell: each stands over
// the page. A height-only change sends `pageShifted` directly so a content reflow
// re-places document-attached paint without re-running chrome reservation.
//
// `syncLayout` measures only chrome whose placement or reservation depends on rendered
// chrome, and writes only chrome boxes. A window resize lays the chrome out synchronously,
// after restating the edges and auxiliary modality, so they follow a live drag in the same
// frame. `layoutSizes` watches `document.body`'s content-box size without deriving a
// posture from it. A width change also schedules `syncLayout` and page repaint in the
// following frame; a height-only content reflow calls `pageShifted` during observer delivery so
// page paint follows targets that moved. That direct path may write only unobserved paint
// hosts and state or queue work for a frame. A `ResizeObserver` callback must not resize
// the box it observes, directly or through a class or attribute that changes that box.
//
// The browser's root is the document scrollport. `pageScroller` is the shared answer for
// reading position and paging; native fragments, history restoration, wheel/touch input,
// and browser UI all use that same root. Root scroll events are reported on `document`,
// while nested scrollports report on their elements. Use `scrollerFor(el)` where a widget
// may be one an agent sent, since a widget in a message is scrolled by the panel's own
// list and by nothing else. Threads and drawers are alternate auxiliary surfaces, so only
// one stands at a time, over the page and taking no width from it. Leaves always covers
// the page. Threads and the On panel, which share the right edge and its width, cover it
// only where they would leave less than a usable page beside them, one rule for both
// (`standsBeside`, auxiliary-surfaces.js; `--lf-auxiliary-beside`, theme.css); elsewhere
// the page beside them stays live.
// The selected auxiliary surface shares one native dialog envelope outside this
// geometry owner; the reference and Page Map retain their own native layers. `--lf-room` and
// `--lf-sidebar-posture` are CSS-owned readings resolved on `main`, which is the named
// `lf-content-frame` style container a margin resident asks for them. The bottom bar is
// a stated height (`--lf-bottom-bar-h`, theme.css) rather than a reading, so whatever has to
// end above it reads that token.

// Application composition supplies feature-local geometry. This owner cannot open
// auxiliary surfaces, send commands, or reconcile thread DOM.
import { sizeObserver } from "./rendering.js";
import { landEdgesWith, restateEdges, sideEdge } from "./drawn-edge.js";
import { standsBeside } from "./auxiliary-surfaces.js";
import { rightCover } from "./geometry.js";
import { scheduleResidency } from "./content-layout.js";
import { syncLayoutRegion } from "./reading-regions.js";

export function createChromeLayout({
  elements: { panel, closeBtn, panelFoot, shortcutBarEl, bottomStatusEl },
  scheduleThreadPreviewPosition,
  syncAuxiliarySurfaces,
  syncReactLayout,
  refreshFab,
  pageShifted,
  repaint,
  repaintPage,
}) {
  // The edges restated, then the chrome laid out. The restatement runs on every pass
  // because the side panel's default width is the page stylesheet's to change. A change of
  // an edge's width or of the window's restates the edges itself, then the auxiliary
  // modality that reads them, then calls `layOut` alone.
  function syncLayout() {
    restateEdges();
    layOut();
  }
  // Every writer here is a writer of the chrome, so nothing this function does resizes the
  // box it reads.
  function layOut() {
    syncLayoutRegion();
    scheduleResidency();
    scheduleThreadPreviewPosition?.();
    // Over a live page the right edge's surface, Threads or On, stands over the
    // page's right margin at any window short of about 1700px, and over the pins at the
    // column's edge at the same widths. The markers are still drawn, under the surface;
    // what says the user lost them is a margin row the surface's edge reaches. Where one
    // does, the banner offers the Page Map in their place, as it does where the markers
    // are pins (chrome.css). Where the surface stands, not where its slide has carried
    // it this frame: offsetLeft ignores the slide's transform.
    const panelLeft = standsBeside() ? rightCover() : Infinity;
    const railCovered = [
      ...document.querySelectorAll(".lf-margin-projection .lf-margin-cluster"),
    ].some(
      (row) =>
        !row.classList.contains("lf-withheld") &&
        row.getBoundingClientRect().right > panelLeft,
    );
    panel.closest(".lf-chrome")?.toggleAttribute("data-lf-rail-covered", railCovered);
    syncFloats();
  }
  // The response bar lives in the viewport plane, and syncLayout is where its usable
  // reading boundary changes shape — a resize moves every rect. Re-place it against the
  // durable anchor so it cannot overhang the shell.
  function syncFloats() {
    if (syncReactLayout()) return;
    refreshFab();
  }
  // Field sizing and every other chrome-size change feed the one layout pass.
  // The document shell's size also feeds the page repaint door: content landing can move
  // a target without emitting a pointer or scroll event.
  const scheduleLayout = (shellChanged = false, chromeChanged = false) => {
    if (shellChanged) repaintPage();
    else if (chromeChanged) repaint();
  };
  // Body's own box is the first of them: width observation hears a window resize, which has
  // no gesture to repaint from.
  //
  // A height-only body resize is repaint-only. An image or font can move a later target
  // without resizing that target or mutating the DOM, and that ordinary page growth
  // changes nothing syncLayout writes.
  // A width change schedules syncLayout and its page repaint in the following animation
  // frame, outside ResizeObserver delivery, so a reservation changing another watched
  // chrome box cannot create an undelivered-notification loop. A height-only change calls
  // pageShifted during delivery; its direct geometry write belongs to the unobserved aim
  // box, while hover, legend, and action placement defer their work to frames.
  let bodyContentWidth = 0;
  let bodyContentHeight = 0;
  const layoutSizes = sizeObserver((entries) => {
    let shellWidthChanged = false;
    let shellMoved = false;
    let chromeMoved = false;
    for (const { contentRect, target } of entries) {
      if (target !== document.body) {
        chromeMoved = true;
        continue;
      }
      const widthChanged = contentRect.width !== bodyContentWidth;
      if (widthChanged) shellWidthChanged = true;
      if (widthChanged || contentRect.height !== bodyContentHeight) shellMoved = true;
      bodyContentWidth = contentRect.width;
      bodyContentHeight = contentRect.height;
    }
    if (shellWidthChanged || chromeMoved) scheduleLayout(shellMoved, chromeMoved);
    else if (shellMoved) pageShifted();
  });
  // Mount only after chrome is attached. Constructors perform no observation or
  // listener installation, so importing the public widget API cannot start layout.
  function mountLayoutObservers() {
    sideEdge.handle(panel, () => closeBtn);
    // A window resize restates both edges' caps, then the auxiliary modality that reads
    // them, then layout, during the event rather than a frame later, so a live window
    // drag clamps an edge and turns a beside surface into a covering one in the same
    // frame. page-geometry.js's resize door re-places page paint for the same event.
    addEventListener("resize", () => {
      restateEdges();
      syncAuxiliarySurfaces();
      layOut();
    });
    layoutSizes.observe(document.body);
    layoutSizes.observe(panelFoot);
    layoutSizes.observe(shortcutBarEl);
    layoutSizes.observe(bottomStatusEl);
  }

  // An edge's new width, from a drag or an arrow, lands the same way.
  landEdgesWith((state) => {
    state();
    syncAuxiliarySurfaces();
    layOut();
  });

  return {
    syncLayout,
    mountLayoutObservers,
  };
}
