/* CSS owns the document's flow, wrapping sidebars and exhibit containment. This
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
/** @type {((changed: boolean) => unknown) | null | undefined} */
let readFinished = null;
let pending = 0;
let lastRead = -1;
/** @type {ReturnType<typeof sizeObserver> | null} */
let headSizes = null;
/** @type {Element | null} */
let watchedHead = null;
/** @type {boolean | null} */
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
    const main = pageDocument();
    if (main) layoutChanged(main);
    repaintPage();
  }
}
/** @param {number} time */
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
/** @param {{onRead?: (changed: boolean) => unknown}} options */
export function openDocumentLayout({ onRead }) {
  readFinished = onRead;
  documentLayoutOpen = true;
  document.addEventListener("toggle", scheduleDocumentLayout, { capture: true });
  window.addEventListener("resize", scheduleDocumentLayout);
  readDocumentLayout();
}

// Annotations read the browser's resolved prose, never allocate it. The box that
// holds the prose declares its measure (`--lf-prose-measure`, layouts.css): the prose
// starts at that box's content edge and runs the measure, or the content box where it
// is narrower. A sidebar's body may hold it; otherwise a custom page's actual box is
// its reading region. The declaration keeps this independent of Layout classes.
/** @param {Element} node */
export const proseMeasure = (node) =>
  parseFloat(getComputedStyle(node).getPropertyValue("--lf-prose-measure")) || 0;
/** @typedef {NonNullable<ReturnType<typeof union>>} ProseBox */
/** @overload @param {Element} main @returns {ProseBox} */
/** @overload @param {Element | null | undefined} [main] @returns {ProseBox | null} */
/** @param {Element | null | undefined} [main] @returns {ProseBox | null} */
export function proseRect(main = layoutBox()) {
  if (!main) return null;
  const holder = [main, ...main.children].find((node) => proseMeasure(node) > 0);
  if (!holder) return main.getBoundingClientRect();
  const style = getComputedStyle(holder);
  const frame = elementFrame(holder);
  if (!frame) return holder.getBoundingClientRect();
  /** @param {"Left" | "Right"} side */
  const edge = (side) =>
    parseFloat(style[`border${side}Width`]) + parseFloat(style[`padding${side}`]);
  const width = Math.min(
    proseMeasure(holder),
    frame.width - edge("Left") - edge("Right"),
  );
  const left =
    style.direction === "rtl" ? frame.width - edge("Right") - width : edge("Left");
  const right = left + width;
  /** @param {number} x @param {number} y */
  const corner = (x, y) => {
    const point = frame.matrix.transformPoint({ x, y });
    return { left: point.x, right: point.x, top: point.y, bottom: point.y };
  };
  return union([
    corner(left, 0),
    corner(right, 0),
    corner(left, frame.height),
    corner(right, frame.height),
  ]);
}
/** @param {Element | null} [main] */
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
