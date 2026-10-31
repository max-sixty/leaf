/* CSS owns document tracks, wrapping sidebars and exhibit containment. This
 * document owner reads the sticky header height shared with landing geometry and
 * notifies annotation geometry after the document's native layout has changed. */
import { setRuntimeRootStyle, removeRuntimeRootStyle } from "./root-state.js";
import { nextFrame, nextRender, sizeObserver } from "./rendering.js";
import { repaintPage } from "./repaint.js";
import { layoutChanged } from "./widget-upgrade.js";
import { layoutBox, pageDocument } from "./passages.js";
import { pageControlsChanged } from "./page-controls.js";
import { elementFrame } from "./element-frame.js";
import { shellRight } from "./geometry.js";
import { union } from "./rect.js";
import { syncLayoutRegion } from "./reading-regions.js";

let documentLayoutOpen = false;
let readFinished = null;
let pending = 0;
let lastRead = -1;
let headSizes = null;
let watchedHead = null;
let railAvailable = null;
function readDocumentLayout() {
  const { changed } = readDocumentHeaders();
  syncLayoutRegion();
  const header = layoutBox()?.querySelector(":scope > header") ?? null;
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
function readFrame(time) {
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
export function openDocumentLayout({ onRead }) {
  readFinished = onRead;
  documentLayoutOpen = true;
  document.addEventListener("toggle", scheduleDocumentLayout, { capture: true });
  window.addEventListener("resize", scheduleDocumentLayout);
  readDocumentLayout();
}

// Annotations read the browser's resolved prose track, never allocate it. A
// sidebar's body may own that track; otherwise a custom page's actual box is its
// reading region. Named lines keep this independent of Layout classes.
export function proseRect(main = layoutBox()) {
  if (!main) return null;
  const grid = [main, ...main.children].find((node) =>
    getComputedStyle(node).gridTemplateColumns.includes("prose-start"),
  );
  if (!grid) return main.getBoundingClientRect();
  const style = getComputedStyle(grid);
  const frame = elementFrame(grid);
  if (!frame) return grid.getBoundingClientRect();
  const gap = parseFloat(style.columnGap) || 0;
  let offset = 0;
  let start;
  let end;
  for (const match of style.gridTemplateColumns.matchAll(
    /\[([^\]]*)\]|(-?[\d.]+)px/g,
  )) {
    if (match[1] !== undefined) {
      const names = match[1].split(/\s+/);
      if (names.includes("prose-start")) start = offset;
      if (names.includes("prose-end")) end = offset - gap;
    } else offset += Number(match[2]) + gap;
  }
  const edge = (side) =>
    parseFloat(style[`border${side}Width`]) + parseFloat(style[`padding${side}`]);
  const left =
    style.direction === "rtl"
      ? frame.width - edge("Right") - end
      : edge("Left") + start;
  const right =
    style.direction === "rtl"
      ? frame.width - edge("Right") - start
      : edge("Left") + end;
  return union(
    [
      [left, 0],
      [right, 0],
      [left, frame.height],
      [right, frame.height],
    ].map(([x, y]) => {
      const point = frame.matrix.transformPoint({ x, y });
      return { left: point.x, right: point.x, top: point.y, bottom: point.y };
    }),
  );
}
export const railStands = (main = layoutBox()) => {
  if (
    !main ||
    (document.body.dataset.annotations ?? "overlay") !== "overlay" ||
    document.body.dataset.rail === "none"
  )
    return false;
  const width = parseFloat(getComputedStyle(main).getPropertyValue("--rail")) || 0;
  return shellRight() - proseRect(main).right >= width;
};

// A page of parts' title scrolls within its fixed column. Declare that
// surface alongside the layout, so reach need not discover it by scanning content.
// CSS anchors its list below the title (layouts.css, "A page of parts").
const title = () => {
  const main = document.querySelector("body > main");
  const parts =
    main && getComputedStyle(main).getPropertyValue("--lf-layout-box").trim() !== "1"
      ? main.querySelector(':scope > [data-lf-views="parts"]')
      : null;
  let marked = false;
  for (
    let node = parts?.previousElementSibling;
    node;
    node = node.previousElementSibling
  ) {
    if (!node.classList.contains("scroll")) {
      node.classList.add("scroll");
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
const head = () => {
  const body = document.body;
  if (!body) return false;
  const header = layoutBox()?.querySelector(":scope > header");
  const value =
    header && getComputedStyle(header).position === "sticky"
      ? `${Math.ceil(header.getBoundingClientRect().height)}px`
      : "";
  if (body.style.getPropertyValue(HEAD) === value) return false;
  if (value) setRuntimeRootStyle(body, HEAD, value);
  else removeRuntimeRootStyle(body, HEAD);
  return true;
};
export const readDocumentHeaders = () => {
  const titled = title();
  const headed = head();
  return { changed: titled || headed };
};
