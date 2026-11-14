/* Mechanical scroll ancestry, with a host's reading-region lookup where installed.
   A plain document names its native overflow boxes; Leaf substitutes its declared
   reading regions without changing the landing arithmetic or fixed-box boundary. An
   edge is read and put back across that ancestry (`edgeAt`, `returnTo`), for a hold
   and a landing alike. Native input chains its scroll along it (`scrollChainOf`), so
   the box an input scrolls is read here too (`inputScroller`). A box Leaf anchors also
   moves with every scroll that moves its anchor, which a reading of the motions under
   way counts (`carriersOf`). */
import { inputs } from "./inputs.js";
import { renderedParent } from "./shadow-tree.js";
import { anchorHolder, anchorNamed } from "./css-anchors.js";
import {
  aimedTop,
  aimScroll,
  moveScrollerBy,
  pageScroller,
  SCROLL_SLACK,
  scrollLimit,
  scrollsFor,
} from "./scrolling.js";
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

// Every box that scrolls a node as part of its content, innermost first: its region's
// scroller, then the box scrolling that one, out to the page. A move the inner box
// cannot take whole is the next one's to finish: a bounded block not yet full grows in
// the page rather than scrolling, and a region scrolled to its end moves no further.
// The walk ends at a box fixed in the window, which no box around it scrolls as
// content; one a transformed box holds rides with it (geometry.js, `fixedInWindow`).
//
// A fixed box Leaf anchors, such as the thread card, rides the scrolls that carry its
// anchor (`carriersOf`) and still ends this walk, so a landing or hold on what the box
// holds never scrolls the page to move it. The box's placement decides where it stands,
// and a surface carried out of view comes back by a landing on what it stands by
// (off-flow.js). Rejected: following the anchor here, for every caller. A scroll moves
// an anchored box only at the browser's next rendering update, in Chromium, Firefox and
// WebKit alike, and the card's placement solves again after it, holding the card at the
// window's edge once its words come in (floating.js). A landing therefore aimed the page
// at where the card no longer stood: `t` then Tab, pressed before the walk's glide
// ended, left the card wholly above the window, with focus on a control in it.
// A wheel spent in the card also passes to the window's scroller, not to the one
// carrying its anchor (`scrollChainOf`).
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

// Every box whose scroll moves `node`, innermost first: `scrollersOf`'s, then, where
// that walk ends at a fixed box Leaf anchors (css-anchors.js), as the thread card, the
// comment box and the margin's rows are, every box whose scroll moves that anchor. A
// scroller's own scroll carries the start of its content, but not the scroller's own
// box, which a box held at a reading region's edge is anchored to. A reading of the
// motions under way that carry the node walks these; a landing or hold on the node
// moves only `scrollersOf`'s.
/** @param {Element | null} node @returns {Generator<Element>} */
export function* carriersOf(node) {
  /** @type {Node | null} */
  let fixed = node;
  for (const box of scrollersOf(node)) {
    yield box;
    fixed = box;
  }
  if (fixed === pageScroller) return;
  while (fixed instanceof Element && !fixedInWindow(fixed))
    fixed = renderedParent(fixed);
  const anchor =
    fixed instanceof Element && anchorNamed(getComputedStyle(fixed).positionAnchor);
  if (!anchor) return;
  for (const box of carriersOf(anchorHolder(anchor))) if (box !== anchor) yield box;
}

// The boxes a scroll passes to once each inner one is spent, as native input chains it
// at a box whose overscroll-behavior lets it go: `scrollersOf`'s, then the page's. A
// fixed box ends `scrollersOf`, but its scroll still chains to the page, the box its
// containing block, the viewport, scrolls, wherever its anchor stands.
/** @param {Element | null} node @returns {Generator<Element>} */
export function* scrollChainOf(node) {
  let last = null;
  for (last of scrollersOf(node)) yield last;
  if (last !== pageScroller) yield pageScroller;
}

// The box an input at `element` scrolls: along the chain native scrolling follows from
// where it lands, the first that can still move the wheel's way, so a pane at its end
// passes the wheel to the page around it, unless it contains its overscroll. A wheel
// nothing can follow, and every other input, aims at the innermost box.
/** @param {Element | null | undefined} element @param {Event} event */
export const inputScroller = (element, event) => {
  if (!element) return pageScroller;
  const chain = [];
  for (const box of scrollChainOf(element)) {
    chain.push(box);
    // The browser's own chaining rule: a box that contains its overscroll passes
    // nothing on.
    if (getComputedStyle(box).overscrollBehaviorY !== "auto") break;
  }
  const innermost = chain[0] ?? pageScroller;
  if (!(event instanceof WheelEvent) || !event.deltaY) return innermost;
  const down = event.deltaY > 0;
  return (
    chain.find((box) =>
      down
        ? box.scrollTop < scrollLimit(box) - SCROLL_SLACK
        : box.scrollTop > SCROLL_SLACK,
    ) ?? innermost
  );
};
// An input the browser scrolls for starts the scroll of the box it moves (scrolling.js,
// `scrollsFor`, `aimScroll`), a frame or more before that box's first scroll event. The
// input lands on an element: the one under the pointer, or the one holding focus, the
// body where nothing does.
inputs.observe((event) => {
  if (!scrollsFor(event)) return;
  const [at] = event.composedPath();
  if (at instanceof Element) aimScroll(inputScroller(at, event), event);
});

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
