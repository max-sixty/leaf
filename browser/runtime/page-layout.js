// `syncLayout` places what floats over the page against the room the page has now, and
// asks which margin elements stand in the page's margin (`scheduleMarginContentLayout`,
// content-layout.js), the one posture JavaScript decides for the document: it reads the
// room beside `main`, which the page's own CSS sets. CSS owns the rest of the shell:
// `body` is the named `lf-shell` inline-size container, and a query on it may answer a
// narrow column's facts. Nothing Leaf draws changes the shell: the floating panel stands
// over the page.
//
// `layoutSizes` watches `document.body`'s content-box size without deriving a posture
// from it. A width change schedules `syncLayout` and page repaint in the following
// frame; a height-only content reflow calls `pageShifted` during observer delivery so
// page paint follows targets that moved. That direct path may write only unobserved
// paint hosts and state or queue work for a frame. A `ResizeObserver` callback must not
// resize the box it observes, directly or through a class or attribute that changes
// that box. A window resize lays the floats out synchronously, so they follow a live
// drag in the same frame.
//
// The browser's root is the document scrollport. `pageScroller` is the shared answer for
// reading position and paging; native fragments, history restoration, wheel/touch input,
// and browser UI all use that same root. Root scroll events are reported on `document`,
// while nested scrollports report on their elements. Use `scrollerFor(el)` where a widget
// may be one an agent sent, since a widget in a message is scrolled by the view that
// draws it. `--lf-room` and `--lf-sidebar-placement` are CSS-owned readings resolved on
// the box the page's Layout arranges (`main` or a child of it; layouts.css), which is
// the named `lf-content-frame` style container whose values margin content reads.

// Application composition supplies feature-local geometry. This owner cannot open
// surfaces, send commands, or reconcile thread DOM.
import { afterScript, sizeObserver } from "./rendering.js";
import { whileConnected } from "./arrivals.js";
import { removeRuntimeRootStyle, setRuntimeRootStyle } from "./root-state.js";
import { scheduleMarginContentLayout } from "./content-layout.js";

// Packages declare the headers they place over the document; this owner alone writes
// the root landing inset. CSS cannot sum heights across independent header owners.
// Read the actual border boxes so typography and theme changes need no second height
// declaration. Positioning and local sticky-content offsets remain the package's.
const rootHeaders = new Set();
const paintRootHeaders = () => {
  const height = [...rootHeaders]
    .filter((header) => header.isConnected)
    .reduce((total, header) => total + header.getBoundingClientRect().height, 0);
  const root = document.documentElement;
  if (height) setRuntimeRootStyle(root, "--lf-root-headers", `${height}px`);
  else removeRuntimeRootStyle(root, "--lf-root-headers");
};
const syncRootHeaders = () => afterScript(paintRootHeaders);

/** Reserve a header's height in document landings while it is connected. Independent
 * headers add their heights. Call the returned stop when a header changes to local
 * navigation; removing and reconnecting the node otherwise withdraws and restores it. */
export function registerRootHeader(header) {
  return whileConnected(header, () => {
    rootHeaders.add(header);
    const size = sizeObserver(syncRootHeaders);
    size.observe(header, { box: "border-box" });
    syncRootHeaders();
    return () => {
      size.disconnect();
      rootHeaders.delete(header);
      syncRootHeaders();
    };
  });
}

export function createPageLayout({
  scheduleThreadPreviewPosition,
  syncReactLayout,
  refreshFab,
  pageShifted,
  repaintPage,
}) {
  // The response bar lives in the viewport plane, and this is where its usable reading
  // boundary changes shape: a resize moves every rect. It is re-placed against its
  // durable anchor so it cannot overhang the shell.
  function syncLayout() {
    scheduleMarginContentLayout();
    scheduleThreadPreviewPosition?.();
    if (syncReactLayout()) return;
    refreshFab();
  }
  // Body's own box: width observation hears a window resize, which has no gesture to
  // repaint from, and the page repaint door follows content landing, which can move a
  // target without emitting a pointer or scroll event.
  //
  // A height-only body resize is repaint-only. An image or font can move a later target
  // without resizing that target or mutating the DOM, and that ordinary page growth
  // changes nothing syncLayout writes. A width change repaints the page in the following
  // animation frame, outside ResizeObserver delivery, so a placement changing another
  // watched box cannot create an undelivered-notification loop.
  let bodyContentWidth = 0;
  let bodyContentHeight = 0;
  const layoutSizes = sizeObserver(([{ contentRect }]) => {
    const widthChanged = contentRect.width !== bodyContentWidth;
    const moved = widthChanged || contentRect.height !== bodyContentHeight;
    bodyContentWidth = contentRect.width;
    bodyContentHeight = contentRect.height;
    if (widthChanged) repaintPage();
    else if (moved) pageShifted();
  });
  // Mount only after the chrome is attached. Constructors perform no observation or
  // listener installation, so importing the public widget API cannot start layout.
  function mountLayoutObservers() {
    addEventListener("resize", syncLayout);
    layoutSizes.observe(document.body);
  }

  return { syncLayout, mountLayoutObservers };
}
