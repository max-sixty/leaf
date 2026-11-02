/* Mechanical scroll ancestry, with a host's reading-region lookup where installed.
   A plain document names its native overflow boxes; Leaf substitutes its declared
   reading regions without changing the landing arithmetic or fixed-box boundary. */
import { renderedParent } from "./shadow-tree.js";
import { pageScroller } from "./scrolling.js";

/** @type {(node: Node | null | undefined) => Element} */
let lookup = (node) => {
  for (
    let at = node instanceof Element ? node : node?.parentElement;
    at;
    at = renderedParent(at)
  ) {
    if (at === pageScroller || /^(auto|scroll)$/.test(getComputedStyle(at).overflowY))
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
// scrolling, and a region scrolled to its end moves no further. A fixed box between a
// node and a scroller stands still while that scroller moves, so the walk ends there.
/** @param {Element | null} node @returns {Generator<Element>} */
export function* scrollersOf(node) {
  for (let box = lookup(node); ; box = lookup(renderedParent(box))) {
    for (let at = node; at !== box; at = renderedParent(at))
      if (!at || getComputedStyle(at).position === "fixed") return;
    yield box;
    if (box === pageScroller) return;
    node = box;
  }
}
