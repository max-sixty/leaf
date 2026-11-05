/* Mechanical scroll ancestry, with a host's reading-region lookup where installed.
   A plain document names its native overflow boxes; Leaf substitutes its declared
   reading regions without changing the landing arithmetic or fixed-box boundary. An
   edge is read and put back across that ancestry (`edgeAt`, `returnTo`), for a hold
   and a landing alike. */
import { renderedParent } from "./shadow-tree.js";
import { aimedTop, moveScrollerBy, pageScroller } from "./scrolling.js";
import { fixedInWindow, userScrollport } from "./geometry.js";

/** @type {(node: Node | null | undefined) => Element} */
let lookup = (node) => {
  for (
    let at = node instanceof Element ? node : node?.parentElement;
    at;
    at = renderedParent(at)
  ) {
    if (at === pageScroller || userScrollport(getComputedStyle(at).overflowY))
      return at;
  }
  return pageScroller;
};
/** @param {typeof lookup} read */
export function installScrollerLookup(read) {
  lookup = read;
}

// Every box whose scroll moves a node, innermost first: its region's scroller, then the
// box scrolling that one, out to the page. A move the inner box cannot take whole is
// the next one's to finish: a bounded block not yet full grows in the page rather than
// scrolling, and a region scrolled to its end moves no further. A box fixed in the
// window between a node and a scroller stands still while that scroller moves, so the
// walk ends there; one a transformed box holds rides with it (geometry.js,
// `fixedInWindow`).
/** @param {Element | null} node @returns {Generator<Element>} */
export function* scrollersOf(node) {
  for (let box = lookup(node); ; box = lookup(renderedParent(box))) {
    for (let at = node; at !== box; at = renderedParent(at))
      if (!at || fixedInWindow(at)) return;
    yield box;
    if (box === pageScroller) return;
    node = box;
  }
}

// The element whose scrollers move `node`: the node itself, or for a range over
// words, the element holding them.
/** @param {Element | Range} node */
export const holderOf = (node) =>
  node instanceof Range ? node.startContainer.parentElement : node;

// Where `node`'s `edge` stands on screen, read as though each box scrolling it stood
// where Leaf last aimed it (scrolling.js, `aimedTop`): a hold read after a hold then
// carries no rounding of the first.
/** @param {Element | Range} node @param {"top" | "bottom"} edge */
export const edgeAt = (node, edge) => {
  let at = node.getBoundingClientRect()[edge];
  for (const box of scrollersOf(holderOf(node))) at += box.scrollTop - aimedTop(box);
  return at;
};

// Put `node`'s `edge` at `at` (`edgeAt`). The box scrolling it takes the move first and
// the boxes around it whatever it cannot: a bounded block not yet full grows in the
// page instead.
/** @param {Element | Range} node @param {"top" | "bottom"} edge @param {number} at */
export function returnTo(node, edge, at) {
  for (const box of scrollersOf(holderOf(node))) {
    const moved = edgeAt(node, edge) - at;
    if (Math.abs(moved) < 0.5) return;
    moveScrollerBy(box, moved);
  }
}
