/* Mechanical scroll ancestry, with a host's reading-region lookup where installed.
   A plain document names its native overflow boxes; Leaf substitutes its declared
   reading regions without changing the landing arithmetic or fixed-box boundary. An
   edge is read and put back across that ancestry (`edgeAt`, `returnTo`), for a hold
   and a landing alike. Native input chains its scroll along it (`scrollChainOf`), so
   the box an input scrolls is read here too (`inputScroller`). A box Leaf anchors also
   moves with every scroll that moves its anchor, which a reading of the motions under
   way counts (`carriersOf`), and the distance the glides under way have still to
   scroll across both is read here too (`glideTravel`, `glideGap`), with what the user
   sees of a node where they leave it (`seenGlided`, `seenAhead`). */
import { inputs } from "./inputs.js";
import { isElement, renderedParent, renderedUnder } from "./shadow-tree.js";
import { anchorHolder, anchorNamed } from "./css-anchors.js";
import { scrollAxes } from "./element-axes.js";
import {
  aimedTop,
  aimScroll,
  moveScrollerBy,
  pageScroller,
  SCROLL_SLACK,
  scrollGoal,
  scrollLimit,
  scrollsFor,
} from "./scrolling.js";
import {
  clippedPlace,
  fixedInWindow,
  inFront,
  placeHolder,
  seenRect,
  shownWindow,
  stuckBox,
  userScrollport,
} from "./geometry.js";
import { shifted } from "./rect.js";

/** @typedef {import("./css-anchors.js").Anchor} Anchor
 * @typedef {import("./rect.js").Box} Box */

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

// The distance the glides under way have still to scroll the boxes that carry `node`
// (`carriersOf`), each from where it stands to its glide's goal (scrolling.js,
// `scrollGoal`), summed as a vector in client pixels through each box's transforms
// (element-axes.js, `scrollAxes`), with the outermost box that glides; null where no
// glide carries it. An element's own scroll moves what it holds and not its box
// (`heldTravel` asks for what it holds), and a box's scroll leaves what sticks in it
// where it stands, as a page's sticky header holding the focused tab (geometry.js,
// `stuckBox`), asked of the boxes between that box and the one inside it; a sticky box
// rides a scroll only until it sticks, and this counts it ridden by none. A scroll the
// browser runs, as a wheel's, has no goal Leaf knows, so it adds nothing. Where a box
// Leaf anchors will stand also depends on its placement, which solves again after a
// scroll (floating.js), and this reads only the scrolls.
/** @param {Element | Range | Anchor} node */
export const glideTravel = (node) =>
  travelFrom(
    node instanceof Range ? holderOf(node) : isElement(node) ? node : node.scroller,
    node,
  );
// The distance the glides under way have still to scroll what `box` holds: its own
// glide's, and those of the boxes carrying it (`glideTravel`).
/** @param {Element} box */
export const heldTravel = (box) => travelFrom(box, null);
/** @param {Element | null} holder @param {unknown} own */
function travelFrom(holder, own) {
  let x = 0;
  let y = 0;
  /** @type {Element | null} */
  let outer = null;
  let inner = holder;
  for (const box of carriersOf(holder)) {
    const from = inner;
    inner = box;
    if (box === own) continue;
    const left = scrollGoal(box) - box.scrollTop;
    if (!left || (from && stuckBox(from, box))) continue;
    const axis = scrollAxes(box).y;
    x -= left * axis.x;
    y -= left * axis.y;
    outer = box;
  }
  return outer && { x, y, outer };
}

// How far `node`'s box stands outside the part of the window the page shows
// (geometry.js, `shownWindow`), now (`now`) and once moved by the glides under way
// (`glideTravel`, `after`), summed across the two axes, 0 where it is in it; null where
// no glide carries it. It reads the window alone, not what the scrollers between will
// show, and the box as it stands now, which for a box Leaf anchors can trail its
// placement (css-anchors.js).
/** @param {Element | Range} node */
export function glideGap(node) {
  const travel = glideTravel(node);
  if (!travel) return null;
  const box = node.getBoundingClientRect();
  const view = shownWindow();
  /** @param {number} x @param {number} y */
  const gap = (x, y) =>
    Math.max(view.top - box.bottom - y, box.top + y - view.bottom, 0) +
    Math.max(view.left - box.right - x, box.left + x - view.right, 0);
  return { now: gap(0, 0), after: gap(travel.x, travel.y) };
}

// What the user will see of `box`, a box of `node` already cut by what clips it inside
// the outermost box that glides (`travel.outer`), where the glides under way leave it:
// `box` moved by their travel (`glideTravel`) and cut where they leave that box and the
// boxes around it (geometry.js, `seenRect`), or null where none of it is seen there.
// The cuts of the boxes inside that one are read as they stand now, which holds unless
// one of them glides too. A box Leaf anchors stands in no box the anchor's glide moves,
// so the window alone cuts it there (`inFront`).
/** @param {Element | Range} node @param {Box} box @param {{x: number, y: number, outer: Element}} travel */
export function seenGlided(node, box, travel) {
  const holder = placeHolder(node);
  if (!holder) return null;
  const moved = shifted(box, travel.x, travel.y);
  if (!renderedUnder(holder, travel.outer)) return inFront(moved, holder);
  const inside = document.createRange();
  inside.selectNodeContents(travel.outer);
  return seenRect(inside, new Map(), moved);
}

// Whether any of `node` is in front of the user (geometry.js, `seenRect`) where the
// glides under way leave it (`seenGlided`), since a key pressed while one runs acts as
// though it had landed (user-place.js, `focusPlace`), or whether they carry it toward
// the window (`glideGap`); with none, whether it is in front now. Toward as well: the
// box of a card the walk is gliding in trails its placement, and read where the glide
// would carry it, it could stand a pixel past the window the walk is bringing it into.
/** @param {Element} node */
export const seenAhead = (node) => {
  const travel = glideTravel(node);
  if (!travel) return Boolean(seenRect(node, new Map()));
  const inner = clippedPlace(node, new Map(), undefined, travel.outer);
  if (inner && seenGlided(node, inner, travel)) return true;
  const gap = glideGap(node);
  return Boolean(gap && gap.after < gap.now);
};

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
