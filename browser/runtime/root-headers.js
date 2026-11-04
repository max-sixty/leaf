/* The headers over the document, which this owner alone reads: those packages declare
 * (`registerRootHeader`), whose heights the root landing inset clears, and the page's
 * own heads, which the sticky-header slot starts below. CSS cannot sum heights across
 * independent header owners. Read the actual border boxes so typography and theme
 * changes need no second height declaration. Positioning and local sticky-content
 * offsets remain the package's.
 *
 * A page's head is a header it fixes at the window's top, or sticks there over the
 * whole page, as a site header beside `main` does (page-layout.md). No package declares
 * it, and Leaf's chrome stands above every page box, so unread it left Leaf's sticky
 * boxes sticking under it, a landing arriving under it, and a margin pin or a block's
 * Copy scrolled under it drawn over it. How far down the window the heads reach
 * (`--lf-page-head`) raises the slot (base.css, at `--lf-top`) for everything in the
 * page but the heads, so every reading of the slot counts them as it counts a header
 * Leaf declares: a landing's margin (surfaces.css), what the user sees (geometry.js,
 * `headerInset`), and the frames Leaf's marks and controls pass under (css-anchors.js,
 * `headerLevels`). A head's reach is its foot where it is fixed, and its height below
 * where it sticks where it sticks, so a header floating a gap below the window's top
 * covers the gap too, and a sticky head reads the same before it sticks. Where several
 * heads stand, as a reading-progress bar fixed over a header does, the deepest counts.
 *
 * A head stands, or sticks, at the window's top across the middle of the page's column,
 * and reaches less than halfway down the window, which an overlay or a sidebar fixed
 * there does not. The browser's hit test at the window's top finds every fixed one
 * touching it, wherever the markup nests it. A sticky head stands there only once
 * stuck, and a landing made before then still arrives under it, so it is found by its
 * place instead, as a fixed head floating below the top is: in the page's frame
 * rather than its content (`leadingBoxes`). What stands above a sticky head, such as a banner over a sticky
 * nav, keeps the root's slot, since by the time the nav sticks it has scrolled away. A
 * header over one section or a widget's stands in no such place.
 *
 * Heads are read with the document's layout (content-layout.js), and again when one
 * resizes, when a scroll of the document ends, where a page's script may have moved,
 * hidden or shown its header, and when the transitions or animations running on them
 * then finish, since a header sliding in or out is read mid-slide otherwise. Each
 * reading is one hit test and the leading children of each box from `body` to the
 * Layout's.
 *
 * Rejected: an author declaration, which a page written as an ordinary website lacks;
 * and reading the page's own `scroll-padding-top`, which states the landing only and
 * which Leaf's root rule would have to give up its own room to read. */
import { afterScript, nextRender, sizeObserver } from "./rendering.js";
import { watchScrollEnds, whileConnected } from "./arrivals.js";
import { removeRuntimeRootStyle, setRuntimeRootStyle } from "./root-state.js";
import { inWindow, layoutWindow, scrollContainer, slotTop } from "./geometry.js";
import { inPage, layoutBox, pageDocument } from "./passages.js";
import { renderedParent } from "./shadow-tree.js";
import { PAGE_PAINT_ATTRIBUTE } from "./page-paint.js";
import { layoutChanged } from "./widget-upgrade.js";
import { repaintPage } from "./repaint.js";
import { restandControls } from "./block-controls.js";

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

/** @typedef {"fixed" | "sticky"} Stance */
/** @type {Map<Element, Stance>} */
let heads = new Map();
// What stands above a sticky head, such as a banner over a sticky nav, which keeps the
// root's slot (base.css), since nothing stands over it when the head has stuck.
/** @type {Element[]} */
let over = [];
let reach = 0;
let readFrame = 0;
/** @type {ReturnType<typeof sizeObserver> | null} */
let headSizes = null;
/** @type {Set<Animation>} */
const awaited = new Set();
const HEAD = PAGE_PAINT_ATTRIBUTE.pageHead;
const scheduleRead = () => (readFrame ||= nextRender(settle));
/** @param {Element} box */
const slot = (box) =>
  Number.parseFloat(getComputedStyle(box).getPropertyValue("--lf-top")) || 0;
// How `box` stands at the window's top, and how far down the window it then covers: its
// foot where it is fixed in the window, and its height below where it sticks where it
// sticks in the document's scroller; null where it does neither.
/** @param {Element} box @param {CSSStyleDeclaration} [style] @returns {{stance: Stance, down: number} | null} */
function standing(box, style = getComputedStyle(box)) {
  const { top, height } = box.getBoundingClientRect();
  if (inWindow(box, style)) return { stance: "fixed", down: top + height };
  if (style.position !== "sticky" || style.top === "auto") return null;
  let scroller = renderedParent(box);
  while (scroller && !scrollContainer(scroller)) scroller = renderedParent(scroller);
  return scroller === document.scrollingElement
    ? { stance: "sticky", down: Number.parseFloat(style.top) + height }
    : null;
}
// The fixed and sticky boxes that stand in the page's frame rather than its content,
// where a head is found by its place, in document order through each box from `body` in
// to the one the page's Layout arranges (`boxes`), and what stands above them (`above`).
// In the boxes around the Layout's, what comes before it is the site's own frame, so a
// banner there stands above a sticky nav after it, and a box fixed in the window after
// it stands over it all the same, as a header a framework renders at the end of `body`
// does; in the Layout's box the content starts at the first child that takes room in its
// flow, standing neither fixed nor sticky. A skip link moved off screen, an empty anchor
// or a hidden sprite takes no room.
/** @param {Element} arranged */
function leadingBoxes(arranged) {
  /** @type {Element[]} */
  const holders = [];
  /** @type {Element | null} */
  let at = arranged;
  for (; at && at !== document.documentElement; at = at.parentElement)
    holders.unshift(at);
  /** @type {Element[]} */
  const boxes = [];
  /** @type {Element[]} */
  const above = [];
  for (const [depth, holder] of holders.entries()) {
    const inner = holders[depth + 1];
    let after = false;
    for (const child of holder.children) {
      if (child === inner) {
        after = true;
        continue;
      }
      if (!inPage(child)) continue;
      const style = getComputedStyle(child);
      if (after) {
        if (style.position === "fixed") boxes.push(child);
        continue;
      }
      if (/^(fixed|sticky)$/.test(style.position)) boxes.push(child);
      else if (
        !/^(none|contents)$/.test(style.display) &&
        style.position !== "absolute" &&
        child.getBoundingClientRect().height > 0
      ) {
        if (!inner) return { boxes, above };
        above.push(child);
      }
    }
  }
  return { boxes, above };
}
// The page's heads now, by how each stands and how far down it reaches, what stands
// above a sticky one, and every box that might have been one, whose motion a reading
// waits out. A head spans the column's middle and reaches less than halfway down the
// window, and is no header Leaf already counts: one a package registers, or one whose
// holder passes its height on through the slot, as a Layout's does (layouts.css,
// "Workspace"), so Leaf's own headers stack below the page's in the slot.
function findHeads() {
  const arranged = layoutBox() ?? document.body;
  const column = arranged.getBoundingClientRect();
  const window = layoutWindow();
  const x = Math.min(Math.max((column.left + column.right) / 2, 0), window.right - 1);
  const top = slotTop(document.documentElement);
  const leading = leadingBoxes(arranged);
  const candidates = new Set([
    ...document
      .elementsFromPoint(x, top + 1)
      .filter((el) => inPage(el) && inWindow(el)),
    ...leading.boxes,
  ]);
  /** @type {Map<Element, {stance: Stance, down: number}>} */
  const found = new Map();
  for (const box of candidates) {
    const stands = standing(box);
    if (!stands || rootHeaders.has(box)) continue;
    const { left, right } = box.getBoundingClientRect();
    if (left > x || right < x || 2 * stands.down >= window.bottom) continue;
    const next = box.nextElementSibling;
    const holder = box.parentElement;
    if (next && holder && slot(next) > slot(holder)) continue;
    found.set(box, stands);
  }
  // Only a sticky head has anything above it: a fixed one stands over all of the page.
  const sticky = [...found].filter(([, { stance }]) => stance === "sticky");
  const above = leading.above.filter((box) =>
    sticky.some(
      ([head]) => box.compareDocumentPosition(head) & Node.DOCUMENT_POSITION_FOLLOWING,
    ),
  );
  return { found, above, candidates, top };
}
// Read the page's heads now, and where what they cover changed, write it and lay out
// again what the slot cuts: that change comes with no resize or mutation of its own.
export function readPageHead() {
  if (!headSizes) {
    headSizes = sizeObserver(scheduleRead);
    watchScrollEnds((box) => {
      if (box === document.scrollingElement) scheduleRead();
    });
  }
  const { found, above, candidates, top } = findHeads();
  let deepest = 0;
  for (const { down } of found.values()) deepest = Math.max(deepest, down - top);
  // A header sliding in or out of the window is read again once it has arrived.
  const moving = [...candidates, ...heads.keys()]
    .flatMap((box) => box.getAnimations())
    .filter((motion) => motion.playState === "running" && !awaited.has(motion));
  for (const motion of moving) {
    awaited.add(motion);
    motion.finished.then(
      () => (awaited.delete(motion), scheduleRead()),
      () => (awaited.delete(motion), scheduleRead()),
    );
  }
  for (const [box] of heads) if (!found.has(box)) headSizes.unobserve(box);
  for (const box of [...heads.keys(), ...over])
    if (!found.has(box) && !above.includes(box)) box.removeAttribute(HEAD);
  for (const [box, { stance }] of found) {
    if (!heads.has(box)) headSizes.observe(box, { box: "border-box" });
    if (box.getAttribute(HEAD) !== stance) box.setAttribute(HEAD, stance);
  }
  for (const box of above)
    if (box.getAttribute(HEAD) !== "above") box.setAttribute(HEAD, "above");
  heads = new Map([...found].map(([box, { stance }]) => [box, stance]));
  over = above;
  if (deepest === reach) return;
  reach = deepest;
  const root = document.documentElement;
  if (deepest > 0) setRuntimeRootStyle(root, "--lf-page-head", `${deepest}px`);
  else removeRuntimeRootStyle(root, "--lf-page-head");
  const page = pageDocument();
  if (page) layoutChanged(page);
  repaintPage();
  restandControls();
}
const settle = () => {
  readFrame = 0;
  readPageHead();
};
/** The page's own heads over the document (see the header), by how each stands. */
export const pageHeads = () => /** @type {ReadonlyMap<Element, Stance>} */ (heads);
