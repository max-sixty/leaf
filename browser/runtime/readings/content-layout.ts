/* CSS owns the document's flow, wrapping sidebars and exhibit containment. This
 * document owner reads the sticky header height shared with landing geometry and
 * notifies annotation geometry after the document's native layout has changed. */
import { setRuntimeRootStyle, removeRuntimeRootStyle } from "../state/root-state.js";
import { nextFrame, nextRender, sizeObserver } from "../lib/frame-pass.js";
import { repaintPage } from "../dom/repaint.js";
import { layoutChanged } from "../lib/widget-events.js";
import { layoutBox, layoutParts, pageDocument } from "./passages.js";
import { pageControlsChanged } from "../base/page-controls.js";
import { elementFrame } from "../dom/element-frame.js";
import { carriedBox } from "../dom/element-axes.js";
import { layoutWindow, shellRight } from "../dom/geometry.js";
import { syncLayoutRegion } from "./reading-regions.js";
import { PAGE_PAINT_ATTRIBUTE } from "../base/page-paint.js";
import { inChrome } from "../base/ui-marks.js";

let documentLayoutOpen = false;
let readFinished: ((changed: boolean) => unknown) | null | undefined = null;
let pending = 0;
let lastRead = -1;
let headSizes: ReturnType<typeof sizeObserver> | null = null;
let watchedHead: Element | null = null;
let railAvailable: boolean | null = null;
function readDocumentLayout() {
  const { changed } = readDocumentHeaders();
  syncLayoutRegion();
  const header = layoutHeader();
  if (header !== watchedHead) {
    headSizes ??= sizeObserver(scheduleDocumentLayout);
    if (watchedHead) headSizes.unobserve(watchedHead);
    if (header) headSizes.observe(header);
    watchedHead = header;
  }
  readFinished?.(changed);
  const available = railStands();
  if (available !== railAvailable) {
    railAvailable = available;
    pageControlsChanged();
  }
  if (changed) {
    layoutChanged(pageDocument());
    repaintPage();
  }
}
function readFrame(time: number) {
  pending = 0;
  if (time === lastRead) {
    pending = nextFrame(readFrame);
    return;
  }
  lastRead = time;
  readDocumentLayout();
}
export function scheduleDocumentLayout() {
  if (documentLayoutOpen) pending ||= nextRender(readFrame);
}
export function settleDocumentLayout() {
  if (documentLayoutOpen) readDocumentLayout();
}
export function openDocumentLayout({
  onRead,
}: {
  onRead?: (changed: boolean) => unknown;
}) {
  readFinished = onRead;
  documentLayoutOpen = true;
  // A disclosure or popover the page opens can move its prose; one in Leaf's chrome,
  // such as a preview standing over the page (annotations/preview.js), moves none of it.
  document.addEventListener(
    "toggle",
    (event) => {
      if (!inChrome(event.target as Node | null)) scheduleDocumentLayout();
    },
    { capture: true },
  );
  window.addEventListener("resize", scheduleDocumentLayout);
  readDocumentLayout();
}

// Annotations read the browser's resolved prose, never allocate it. The box that
// holds the prose declares its measure (`--lf-prose-measure`, layouts.css): the prose
// starts at that box's content edge and runs the measure, or the content box where it
// is narrower. A sidebar's body may hold it; otherwise a custom page's actual box is
// its reading region. The declaration keeps this independent of Layout classes.
export const proseMeasure = (node: Element) =>
  parseFloat(getComputedStyle(node).getPropertyValue("--lf-prose-measure")) || 0;
type ProseBox = ReturnType<typeof carriedBox>;
export function proseRect(main: Element): ProseBox;
export function proseRect(main?: Element | null | undefined): ProseBox | null;
export function proseRect(
  main: Element | null | undefined = layoutBox(),
): ProseBox | null {
  if (!main) return null;
  const holder = [main, ...main.children].find((node) => proseMeasure(node) > 0);
  if (!holder) return main.getBoundingClientRect();
  const style = getComputedStyle(holder);
  const frame = elementFrame(holder);
  if (!frame) return holder.getBoundingClientRect();
  const edge = (side: "Left" | "Right") =>
    parseFloat(style[`border${side}Width`]) + parseFloat(style[`padding${side}`]);
  const width = Math.min(
    proseMeasure(holder),
    frame.width - edge("Left") - edge("Right"),
  );
  const left =
    style.direction === "rtl" ? frame.width - edge("Right") - width : edge("Left");
  return carriedBox(frame.matrix, {
    left,
    top: 0,
    right: left + width,
    bottom: frame.height,
  });
}
export const railStands = (main: Element | null = layoutBox()) => {
  if (
    !main ||
    (document.body.dataset.annotations ?? "overlay") !== "overlay" ||
    document.body.dataset.rail === "none"
  )
    return false;
  const width = parseFloat(getComputedStyle(main).getPropertyValue("--lf-rail")) || 0;
  return shellRight() - proseRect(main).right >= width;
};
// Whether the window has room for the rail: as wide as the column with a rail on either
// side (`--lf-rail-room`, styles/tokens.css), the width at which a column page's rail stands
// (`railStands`), whatever this page's own Layout or body does with the room. A
// workspace keeps no rail at any width, and still has this room on a desktop's window.
export const windowHoldsRail = () =>
  layoutWindow().right >=
  (parseFloat(
    getComputedStyle(document.documentElement).getPropertyValue("--lf-rail-room"),
  ) || 0);

// A page of parts' title scrolls within its fixed column. Declare that
// surface alongside the layout, so reach need not discover it by scanning content.
// CSS anchors its list below the title (layouts.css, "A page of parts").
const title = () => {
  const parts = layoutParts();
  let marked = false;
  for (
    let node = parts?.previousElementSibling;
    node;
    node = node.previousElementSibling
  ) {
    if (!node.hasAttribute(PAGE_PAINT_ATTRIBUTE.scrollSurface)) {
      node.toggleAttribute(PAGE_PAINT_ATTRIBUTE.scrollSurface, true);
      marked = true;
    }
  }
  return marked;
};
// The header a Layout sticks over its body, as a workspace does where the window is
// too small to be its screen (layouts.css, "Workspace"): what the body stands under is
// the header's height, which no CSS can read, so it is written here for the body's
// sticky-header slot (`--lf-top`, theme.css) to add. Which header sticks is the
// stylesheet's to say; this reads its computed position.
const HEAD = "--lf-layout-head-h";
// Read off the box's children rather than by `:scope >`, which walks every element under
// the box to find one of its children (passages.js, `partsOf`).
const layoutHeader = () =>
  [...(layoutBox()?.children ?? [])].find((child) => child.localName === "header") ??
  null;
const head = () => {
  const body = document.body;
  const header = layoutHeader();
  const value =
    header && getComputedStyle(header).position === "sticky"
      ? `${Math.ceil(header.getBoundingClientRect().height)}px`
      : "";
  if (body.style.getPropertyValue(HEAD) === value) return false;
  if (value) setRuntimeRootStyle(body, HEAD, value);
  else removeRuntimeRootStyle(body, HEAD);
  return true;
};
const readDocumentHeaders = () => {
  const titled = title();
  const headed = head();
  return { changed: titled || headed };
};
