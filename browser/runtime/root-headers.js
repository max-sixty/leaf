/* The headers over the document, which this owner alone reads: those packages declare
 * (`registerRootHeader`), whose heights the root landing inset clears, and the page's
 * own head, which the sticky-header slot starts below. CSS cannot sum heights across
 * independent header owners. Read the actual border boxes so typography and theme
 * changes need no second height declaration. Positioning and local sticky-content
 * offsets remain the package's.
 *
 * The page's head is the box the page fixes at the window's top, or sticks there over
 * the whole page, as a site header beside `main` does (page-layout.md). No package
 * declares it, and Leaf's chrome stands above every page box, so unread it left Leaf's
 * sticky boxes sticking under it, a landing arriving under it, and a margin pin or a
 * block's Copy scrolled under it drawn over it. How far down the window it covers,
 * below the head room (`--lf-page-head`), raises the slot (base.css, at `--lf-top`) for
 * everything in the page but the head, so every reading of what the slot covers counts
 * it as it counts a header Leaf declares: a landing's band, what the user sees
 * (geometry.js, `headerInset`), and the frames Leaf's marks and controls pass under
 * (css-anchors.js, `headerLevels`). That reach is the head's foot where it stands, or
 * for a sticky head where it sticks, so a header floating a gap below the window's top
 * covers the gap too, and a sticky head reads the same before it sticks.
 *
 * The head stands, or sticks, at the window's top across the middle of the page's
 * column, and reaches less than halfway down the window, which an overlay or a sidebar
 * fixed there does not. A sticky head stands there only once stuck, and a landing made
 * before then still arrives under it, so a head is found by its place: the fixed or
 * sticky box leading one that holds the box the page's Layout arranges, from `body` in.
 * A header over one section or a widget's holds no Layout's box, and a header below a
 * banner leads nothing, so neither is the head. A fixed head may stand anywhere in the
 * page's markup, so the browser's hit test at the window's top finds one first: the
 * box fixed in the window around what stands there. A header Leaf already counts is not
 * the head: one a package registers, or one whose holder passes its height on through
 * the slot, as a Layout's does (layouts.css, "Workspace"), so Leaf's own headers stack
 * below the page's in the slot. Only one head is read, so a second the page stacks
 * below its first is not.
 *
 * It is read with the document's layout (content-layout.js, which reads a Layout's own
 * header first), and again when the head resizes and when a scroll of the document
 * ends, where a page's script may have moved or hidden its header. Each reading is a
 * hit test and a walk up from it, and the leading box of each box from `body` to the
 * Layout's.
 *
 * Rejected: an author declaration, which a page written as an ordinary website lacks;
 * and reading the page's own `scroll-padding-top`, which states the landing only and
 * which Leaf's root rule would have to give up its own room to read. */
import { afterScript, nextRender, sizeObserver } from "./rendering.js";
import { watchScrollEnds, whileConnected } from "./arrivals.js";
import { removeRuntimeRootStyle, setRuntimeRootStyle } from "./root-state.js";
import { fixedInWindow, layoutWindow, scrollContainer, slotTop } from "./geometry.js";
import { inPage, layoutBox, pageDocument } from "./passages.js";
import { renderedParent } from "./shadow-tree.js";
import { PAGE_PAINT_ATTRIBUTE } from "./page-paint.js";
import { layoutChanged } from "./widget-upgrade.js";
import { repaintPage } from "./repaint.js";

/** @type {Set<Element>} */
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
/** @param {Element} header */
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

/** @type {Element | null} */
let head = null;
let headReach = 0;
let readFrame = 0;
/** @type {ReturnType<typeof sizeObserver> | null} */
let headSize = null;
const HEAD = PAGE_PAINT_ATTRIBUTE.pageHead;
/** @param {Element} box */
const slot = (box) =>
  Number.parseFloat(getComputedStyle(box).getPropertyValue("--lf-top")) || 0;
// How far down the window `box` covers, standing as a head (see the header): its foot
// where it is fixed in the window, and its height below where it sticks where it
// sticks in the document's scroller; null where it does neither.
/** @param {Element} box */
function reach(box) {
  const style = getComputedStyle(box);
  const { top, height } = box.getBoundingClientRect();
  if (fixedInWindow(box, style)) return top + height;
  if (style.position !== "sticky" || style.top === "auto") return null;
  let scroller = renderedParent(box);
  while (scroller && !scrollContainer(scroller)) scroller = renderedParent(scroller);
  return scroller === document.scrollingElement
    ? Number.parseFloat(style.top) + height
    : null;
}
// Whether `box`, standing or sticking at the window's top, is the page's head: across
// `x`, the column's middle, reaching less than halfway down the window, and not a
// header Leaf already counts.
/** @param {Element} box @param {number} x */
function heads(box, x) {
  const { left, right } = box.getBoundingClientRect();
  const down = reach(box);
  if (down === null || left > x || right < x || 2 * down >= layoutWindow().bottom)
    return false;
  const next = box.nextElementSibling;
  const holder = box.parentElement;
  return !rootHeaders.has(box) && !(next && holder && slot(next) > slot(holder));
}
// The box `holder` leads: its first child the page shows.
/** @param {Element} holder */
function leading(holder) {
  for (const child of holder.children)
    if (inPage(child) && getComputedStyle(child).display !== "none") return child;
  return null;
}
function findHead() {
  const arranged = layoutBox() ?? document.body;
  const column = arranged.getBoundingClientRect();
  const { right } = layoutWindow();
  const x = Math.min(Math.max((column.left + column.right) / 2, 0), right - 1);
  const top = slotTop(document.documentElement);
  const hit = document.elementsFromPoint(x, top + 1).find((el) => inPage(el)) ?? null;
  for (let box = hit; box && box !== document.body; box = renderedParent(box))
    if (fixedInWindow(box)) return heads(box, x) ? box : null;
  /** @type {Element[]} */
  const holders = [];
  /** @type {Element | null} */
  let at = arranged;
  for (; at && at !== document.documentElement; at = at.parentElement)
    holders.unshift(at);
  for (const holder of holders) {
    const lead = leading(holder);
    if (lead && reach(lead) !== null) return heads(lead, x) ? lead : null;
  }
  return null;
}
// Read the page's head now, and where it changed, write it and lay out again what the
// slot cuts: a change of what it covers comes with no resize or mutation of its own.
export function readPageHead() {
  if (!headSize) {
    headSize = sizeObserver(() => (readFrame ||= nextRender(settle)));
    watchScrollEnds((box) => {
      if (box === document.scrollingElement) readFrame ||= nextRender(settle);
    });
  }
  const found = findHead();
  const down = found
    ? Math.max(0, (reach(found) ?? 0) - slotTop(document.documentElement))
    : 0;
  if (found !== head) {
    if (head) {
      headSize.unobserve(head);
      head.removeAttribute(HEAD);
    }
    if (found) {
      headSize.observe(found, { box: "border-box" });
      found.setAttribute(HEAD, "");
    }
    head = found;
  }
  if (down === headReach) return;
  headReach = down;
  const root = document.documentElement;
  if (down) setRuntimeRootStyle(root, "--lf-page-head", `${down}px`);
  else removeRuntimeRootStyle(root, "--lf-page-head");
  const page = pageDocument();
  if (page) layoutChanged(page);
  repaintPage();
}
const settle = () => {
  readFrame = 0;
  readPageHead();
};
/** The page's own head over the document (see the header), or null. */
export const pageHead = () => (head?.isConnected ? head : null);
