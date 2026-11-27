/* Mechanical scroll ancestry, with a host's reading-region lookup where installed.
   A plain document names its native overflow boxes; Leaf substitutes its declared
   reading regions without changing the landing arithmetic or fixed-box boundary. An
   edge is read and put back across that ancestry (`edgeAt`, `returnTo`), for a hold
   and a landing alike. Native input chains its scroll along it (`scrollChainOf`), so
   the box an input scrolls is read here too (`inputScroller`). A box Leaf anchors also
   moves with every scroll that moves its anchor, which a reading of the motions under
   way counts (`carriersOf`), and how far the glides under way still carry a node
   across both is read here too (`glideTravel`, `glideGap`), with what the user sees of
   it where they leave it (`seenGlided`, `seenAhead`).

   Where the glides under way leave a node is read, not modelled: each box a glide
   moves is scrolled to its goal, the node read there, and the box put back, in one
   task (dom/scrolling.js, `whereGlidesLand`). A sticky box rides a glide until it reaches
   its line, comes back off it with its own place, and is pushed on by its holder's
   end, through transforms and nested scrollers, and the browser's layout says where
   each leaves it in Chromium and Firefox alike, where a model needs a stuck box's own
   place, which Firefox can't read. That rests on both engines laying a box's content
   out as a scroll write lands, and costs a write and a write back for each box a glide
   moves, whose events fold into those the glide sends every frame. */
import { inputs } from "../base/inputs.js";
import { isElement, renderedParent } from "../lib/shadow-tree.js";
import { anchorHolder, anchorNamed } from "../dom/css-anchors.js";
import { scrollAxes } from "../dom/element-axes.js";
import {
  aimedTop,
  aimScroll,
  carriedToward,
  moveScrollerBy,
  pageScroller,
  SCROLL_SLACK,
  scrollGoal,
  scrollLimit,
  scrollsFor,
  whereGlidesLand,
} from "../dom/scrolling.js";
import {
  clippedPlace,
  fixedInWindow,
  inFront,
  placeBox,
  placeHolder,
  seenRect,
  shownBox,
  shownWindow,
  userScrollport,
} from "../dom/geometry.js";
import { shifted } from "../dom/rect.js";

/** @typedef {import("../dom/css-anchors.js").Anchor} Anchor
 * @typedef {import("../base/box.js").Box} Box */

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
// content; one a transformed box holds rides with it (dom/geometry.js, `fixedInWindow`).
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
// that walk ends at a fixed box Leaf anchors (dom/css-anchors.js), as the thread card, the
// comment box and the margin's rows are, every box whose scroll moves that anchor. A
// scroller's own scroll carries the start of its content, but not the scroller's own
// box, which a box held at a reading region's edge is anchored to. A reading of the
// motions under way that carry the node walks these; a landing or hold on the node
// moves only `scrollersOf`'s.
/** @param {Element | null} node @returns {Generator<Element>} */
export function* carriersOf(node) {
  for (const { boxes } of carrying(node)) yield* boxes;
}
// The same walk in its parts: the boxes `scrollersOf` gives from `base`, and the fixed
// box Leaf anchors that ends them (`fixed`), then the same from the element holding
// that box's anchor, which none of those boxes holds, the anchor itself left out.
/** @typedef {{base: Element, fixed: Element | null, boxes: Element[]}} Carrying */
/** @param {Element | null} node @returns {Generator<Carrying>} */
function* carrying(node) {
  if (!node) return;
  const boxes = [...scrollersOf(node)];
  /** @type {Element | null} */
  let fixed = boxes.at(-1) ?? node;
  if (fixed === pageScroller) fixed = null;
  while (fixed && !fixedInWindow(fixed)) fixed = renderedParent(fixed);
  const anchor = fixed && anchorNamed(getComputedStyle(fixed).positionAnchor);
  yield { base: node, fixed: anchor ? fixed : null, boxes };
  if (!anchor) return;
  for (const part of carrying(anchorHolder(anchor)))
    yield { ...part, boxes: part.boxes.filter((box) => box !== anchor) };
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
// where it lands, the first that can still move the wheel's way, or that its gesture has
// already carried that way (`carriedToward`), since a wheel the browser scrolled before
// the page heard it finds the box at the end it reached. So a pane at its end passes the
// wheel to the page around it, unless it contains its overscroll. A wheel nothing can
// follow, and every other input, aims at the innermost box.
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
    chain.find(
      (box) =>
        (down
          ? box.scrollTop < scrollLimit(box) - SCROLL_SLACK
          : box.scrollTop > SCROLL_SLACK) || carriedToward(box, down),
    ) ?? innermost
  );
};
// An input the browser scrolls for starts the scroll of the box it moves (dom/scrolling.js,
// `scrollsFor`, `aimScroll`), a frame or more before that box's first scroll event. The
// input lands on an element: the one under the pointer, or the one holding focus, the
// body where nothing does.
inputs.observe((event) => {
  if (!scrollsFor(event)) return;
  const [at] = event.composedPath();
  if (at instanceof Element) aimScroll(inputScroller(at, event), event);
});

// The distance the glides under way have still to carry `node`, through the boxes that
// carry it (`carriersOf`), read where they leave it, all landed at once
// (dom/scrolling.js, `whereGlidesLand`): a page's sticky header holding the focused tab
// rides a glide of the page only until it sticks, and comes back down with a glide
// that takes its own place back past its line. Each part of the walk (`carrying`) is
// read by how far its glides move the element its boxes carry, less how far they move
// the fixed box ending it, which takes a scroll only at the next frame in Chromium and
// may take it at once elsewhere. A vector in client pixels, with the outermost box
// that glides, whatever the vector, since glides that carry a node nowhere can still
// move what clips it; null where no glide carries it. Where glides past a fixed box
// Leaf anchors carry it, `held` names that box and how far the glides inside it carry
// the node within it. An element's own scroll moves what it holds and not its box:
// `heldTravel` asks for what it holds, which rides its own glide whole, through its
// transforms (dom/element-axes.js, `scrollAxes`). A scroll the browser runs, as a wheel's,
// has no goal Leaf knows, so it adds nothing. Where a box Leaf anchors will stand also
// depends on its placement, which solves again after a scroll (floating.js), and this
// reads only the scrolls.
/** @param {Element | Range | Anchor} node */
export const glideTravel = (node) =>
  travelFrom(
    node instanceof Range ? placeHolder(node) : isElement(node) ? node : node.scroller,
    node,
  );
// The distance the glides under way have still to scroll what `box` holds: its own
// glide's, and those of the boxes carrying it (`glideTravel`).
/** @param {Element} box */
export const heldTravel = (box) => travelFrom(box, null);
/** @param {Element | null} holder @param {unknown} own */
function travelFrom(holder, own) {
  const parts = [...carrying(holder)];
  const gliding = parts
    .flatMap(({ boxes }) => boxes)
    .filter((box) => box !== own && scrollGoal(box) !== box.scrollTop);
  const outer = gliding.at(-1);
  if (!holder || !outer) return null;
  // Where each part's element stands in the fixed box ending the part, if any.
  const stand = () =>
    parts.map(({ base, fixed }) => {
      const at = shownBox(base);
      const frame = fixed ? shownBox(fixed) : { left: 0, top: 0 };
      return { x: at.left - frame.left, y: at.top - frame.top };
    });
  const from = stand();
  const moves = whereGlidesLand(gliding, stand).map((to, at) => ({
    x: to.x - (from[at]?.x ?? 0),
    y: to.y - (from[at]?.y ?? 0),
  }));
  const [inside = { x: 0, y: 0 }] = moves;
  if (holder === parts[0]?.boxes[0] && holder !== own) {
    const axis = scrollAxes(holder).y;
    const by = scrollGoal(holder) - holder.scrollTop;
    inside.x -= by * axis.x;
    inside.y -= by * axis.y;
  }
  const fixed = parts[0]?.fixed;
  const anchored = parts
    .slice(1)
    .some(({ boxes }) => boxes.some((box) => gliding.includes(box)));
  return {
    x: moves.reduce((sum, move) => sum + move.x, 0),
    y: moves.reduce((sum, move) => sum + move.y, 0),
    outer,
    held: fixed && anchored ? { fixed, ...inside } : null,
  };
}

// How far `node`'s box stands outside the part of the window the page shows
// (dom/geometry.js, `shownWindow`), now (`now`) and once moved by the glides under way
// (`glideTravel`, `after`), summed across the two axes, 0 where it is in it; null where
// no glide carries it. It reads the window alone, not what the scrollers between will
// show, and the box as it stands now, which for a box Leaf anchors can trail its
// placement (dom/css-anchors.js).
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

// What the user will see of `box`, a box of `node`, where the glides under way leave
// it: `box` moved by their travel (`glideTravel`) and cut by every box clipping it, the
// chrome's covers included, as they stand once the glides land (dom/geometry.js,
// `seenRect`; dom/scrolling.js, `whereGlidesLand`), or null where none of it is seen
// there. So an inner glide that brings a node into its box's view while an outer glide
// brings that box into the window shows the node, which the box's clip as it stood
// would hide. A box Leaf anchors takes its anchor's glides only at the next frame
// (`held`): the node is cut by the clips inside that box where the glides inside it
// leave it, and the box then rides its anchor's glides, which the window and the
// chrome's covers alone cut there (`inFront`). `rest` reads the covers where they come
// to rest too (dom/geometry.js, `seenRect`).
/** @param {Element | Range} node @param {Box} box @param {{x: number, y: number, held?: {fixed: Element, x: number, y: number} | null}} travel @param {boolean} [rest] */
export function seenGlided(node, box, travel, rest = false) {
  const holder = placeHolder(node);
  if (!holder) return null;
  const { held } = travel;
  if (!held)
    return whereGlidesLand(scrollersOf(holder), () =>
      seenRect(node, new Map(), shifted(box, travel.x, travel.y), rest),
    );
  const stop = renderedParent(held.fixed) ?? undefined;
  const inside = whereGlidesLand(scrollersOf(holder), () =>
    clippedPlace(node, new Map(), shifted(box, held.x, held.y), stop),
  );
  return (
    inside &&
    inFront(shifted(inside, travel.x - held.x, travel.y - held.y), holder, rest)
  );
}

// Whether any of `node`, or of `box` measured through it, is in front of the user
// (dom/geometry.js, `seenRect`) where the glides under way leave it (`seenGlided`), since a
// key pressed while one runs acts as though it had landed (user-place.js, `focusPlace`);
// with none, whether it is in front now. `rest` reads the covers where they come to rest
// too. This is where the reading of the page finds the block the user reads
// (reading-place.js, `blocksOnScreen`), so a stop judged beside that block is judged
// here too (`seenWhereRead`).
/** @param {Element} node @param {Box} [box] @param {boolean} [rest] */
export const seenLanded = (node, box = placeBox(node), rest = false) =>
  landed(node, glideTravel(node), box, rest);
/** @param {Element} node @param {ReturnType<typeof glideTravel>} travel @param {Box} [box] @param {boolean} [rest] */
function landed(node, travel, box = placeBox(node), rest = false) {
  return Boolean(
    travel ? seenGlided(node, box, travel, rest) : seenRect(node, new Map(), box, rest),
  );
}
// Whether `node` is seen where the motion under way leaves it, or the glides carry it
// toward the window (`glideGap`). Seen means seen where the glides land
// (`seenLanded`), with the chrome's covers where their own motion ends, since a key
// pressed during either acts as though it had ended. Toward as well: the box of a card
// the walk is gliding in trails its placement, and read where the glide would carry
// it, it could stand a pixel past the window the walk is bringing it into.
/** @param {Element} node */
export const seenAhead = (node) => {
  const travel = glideTravel(node);
  if (landed(node, travel, placeBox(node), true)) return true;
  if (!travel) return false;
  const gap = glideGap(node);
  return Boolean(gap && gap.after < gap.now);
};

// Where `node`'s `edge` stands on screen, read as though each box scrolling it stood
// where Leaf last aimed it (dom/scrolling.js, `aimedTop`): a hold read after a hold then
// carries no rounding of the first.
/** @param {Element | Range} node @param {"top" | "bottom"} edge */
export const edgeAt = (node, edge) => {
  let at = node.getBoundingClientRect()[edge];
  for (const box of scrollersOf(placeHolder(node))) at += box.scrollTop - aimedTop(box);
  return at;
};

// Put `node`'s `edge` at `at` (`edgeAt`). The box scrolling it takes the move first and
// the boxes around it whatever it cannot: a bounded block not yet full grows in the
// page instead.
/** @param {Element | Range} node @param {"top" | "bottom"} edge @param {number} at */
export function returnTo(node, edge, at) {
  for (const box of scrollersOf(placeHolder(node))) {
    const moved = edgeAt(node, edge) - at;
    if (Math.abs(moved) < 0.5) return;
    moveScrollerBy(box, moved);
  }
}
