/* Keyboard reachability, containment, the sticky-header slot, and continuation paint for
   scrollable page and shadow content. */

import { watchArrivals, watchScrolls } from "./arrivals.js";
import { tabStops, wearsLentStop } from "./focus.js";
import { LENT_REACH_STOP, TEXT_BOX } from "./control-selectors.js";
import { scrollsBy, userScrollport } from "./geometry.js";
import { skipped } from "./shown-box.js";
import { afterScript, nextRender, sizeObserver } from "./rendering.js";
import { PAGE_PAINT_ATTRIBUTE } from "./page-paint.js";
import { SCROLL_SLACK, atScrollEnd } from "./scrolling.js";
import { shadowRootsIn, upFrom } from "./shadow.js";
import { LAYOUT } from "./widget-upgrade.js";
import { keeps } from "./keeps.js";

// Scroll owners opt into reach with `scroll`. Their CSS owns overflow, including
// changes at breakpoints; the shared rule contains positioned descendants.
// Style discovery measures only these surfaces. Stop eligibility still checks the
// rendered controls inside them. Reading-region registration opts its body in.
const SCROLL_SURFACE = ".scroll";
const seenDeclarations = new WeakMap();
const scrollAncestors = new WeakSet();
const styleRoots = new WeakSet();
const ancestorStyles = new MutationObserver((records) => {
  for (const { target } of records) if (scrollAncestors.has(target)) reread(target);
});
function watchAncestorStyles(scope) {
  const tree = scope.getRootNode();
  const root = tree.nodeType === Node.DOCUMENT_NODE ? tree.documentElement : tree;
  if (!root || styleRoots.has(root) || !root.isConnected) return;
  styleRoots.add(root);
  ancestorStyles.observe(root, {
    subtree: true,
    attributes: true,
    attributeFilter: ["class", "style", "dir"],
  });
}
let watchingSurfaces = false;
// until-found retains its own box, unlike its skipped descendants. That hidden
// box cannot be inspected, so its apparent overflow earns no keyboard stop.
const overflows = (el) =>
  !el.hasAttribute("hidden") &&
  (el.scrollWidth > el.clientWidth || el.scrollHeight > el.clientHeight);
const holdsOwnStop = (el) => tabStops(el).length > 0;
// Each candidate with the `tabindex` its author gave it, or null for none. The pass
// writes only the stop it lends, `0`, and takes back only that, to the author's value:
// a box that stops scrolling is the box it was before, not one a click can now focus.
// A box focus.js has lent a `-1` for an arrival goes back to that `-1`, which focus.js
// takes back on the blur.
const mayScroll = new Map();
// A control beside a scroller can require its stop even when its contents fit.
// Keep that request with the owner of the stop so a later layout pass cannot
// take it back as though it were a stop this pass had lent for overflow.
const claimedStops = new WeakSet();
// Keep the borrowed state with the lending owner. Consumers of authored working
// regions must never infer a region from this layout-dependent keyboard stop.
function lendStop(el) {
  keeps(el, LENT_REACH_STOP, "");
  keeps(el, "tabindex", 0);
}
export function claimReachStop(el) {
  if (claimedStops.has(el)) return;
  const authored = mayScroll.has(el) ? mayScroll.get(el) : el.getAttribute("tabindex");
  if (authored !== null) return;
  claimedStops.add(el);
  lendStop(el);
}

export function releaseReachStop(el) {
  if (!claimedStops.has(el)) return;
  claimedStops.delete(el);
  if (el.getAttribute("tabindex") !== "0") {
    keeps(el, LENT_REACH_STOP, null);
    return;
  }
  if (mayScroll.has(el) && overflows(el) && !holdsOwnStop(el)) lendStop(el);
  else returnStop(el, null);
}
// Takes back the stop this pass lent: to `-1` where focus.js has lent one for an
// arrival, which it takes back on the blur, and otherwise to the author's value.
function returnStop(el, authored) {
  keeps(el, LENT_REACH_STOP, null);
  if (el.getAttribute("tabindex") === "0")
    keeps(el, "tabindex", wearsLentStop(el) ? -1 : authored);
}
// The same measurement spent on the eye. Scrolling is the layer's honest degrade for a
// box whose content is wider than the room it was given — a diagram at the size it was
// drawn, a board's columns, a line of code — and on a platform that draws overlay
// scrollbars the only sign of it is a bar the platform hides until it is used. Measured:
// a twelve-node flowchart in a tab panel showed seven, cut 356px of 1026 at every window
// width from 1200 to 1920, with nothing on the page saying so. A user can guess that a
// line of code continues; nobody can guess a graph does.
//
// `paintReach` already asks whether each candidate has something out of sight whenever
// layout moves it. The scroll listener adds which side still has content beyond it. The
// marks sit on the composed box like the stop above, so authored, package, and theme
// scrollers follow the same rule without separate declarations.
//
// Across the box and not down it, which is the axis every reading of a cut takes: a box
// cut off below its container is usually cut on purpose — a collapsed disclosure, a
// draft's box, a shot's frame are all a height with the rest hidden — where one cut at
// the side never is. The page itself is the down direction and the window's own bar
// answers for it.
//
// The marks are paint (base.css, [data-lf-more-before/after]). Writing them from a
// resize observation moves nothing and cannot feed itself. Among declared surfaces,
// computed `overflow-x` decides which can scroll sideways. `overflow-x: visible`
// computes to `auto` beside vertical scrolling, but the mark still requires measured
// horizontal overflow. A board reached through its controls needs no container stop,
// but still needs the cue when its columns are cut.
const sideways = new Map();
// A reading region is the narrower vertical case. Ordinary vertical overflow is often
// intentional and self-explanatory (a text box, disclosure, or the document itself),
// so `reachScrollers` must not infer this mark from overflow-y. Reading-region owners
// opt their bounded body in when they register it. The cue follows remaining content,
// because the pane's fixed lower edge would otherwise keep promising another part of
// the reading after the user reaches the end.
const downwards = new Map();
watchScrolls((box) => {
  if (downwards.has(box)) paintReadingReach(box);
  if (sideways.has(box)) paintSidewaysReach(box, true);
});
export function reachReadingScroller(el, paintContinuation) {
  el.classList.toggle("scroll", true);
  downwards.set(el, paintContinuation);
  sweep(el);
  paintReach();
  watchReach(el);
  paintReadingReach(el);
  // A host moved in one script lets go of its body and registers it again before the
  // script ends, so the cue leaves when the script does, and only a body nobody reached again
  // by then loses it.
  return () => {
    downwards.delete(el);
    if (!watched(el)) unwatchReach(el);
    afterScript(() => {
      if (!downwards.has(el)) {
        keeps(el, PAGE_PAINT_ATTRIBUTE.moreBelow, null);
        paintContinuation?.(false);
      }
    });
  };
}

const readingPaints = new Set();
function paintReadingReach(el) {
  // End-following owners finish their scroll after registering or resizing the
  // region. Read its final position after this script, including resize delivery,
  // so the cue paints with the content.
  readingPaints.add(el);
  afterScript(paintReadingReachNow);
}
function paintReadingReachNow() {
  const pending = [...readingPaints];
  readingPaints.clear();
  for (const el of pending) {
    if (!downwards.has(el) || unpainted(el)) continue;
    const style = getComputedStyle(el);
    const scrolling = userScrollport(style.overflowY);
    // A region with covering chrome paints its upper continuation at the chrome's
    // actual edge. Share the scroll/resize pass rather than watch the same body twice.
    downwards.get(el)?.(scrolling && el.scrollTop > SCROLL_SLACK);
    keeps(
      el,
      PAGE_PAINT_ATTRIBUTE.moreBelow,
      scrolling && !atScrollEnd(el) ? "" : null,
    );
  }
}

// Hidden surfaces wait for a size delivery. Only a surface's ancestors can be
// containers whose queries change its overflow; its contents need no style reading.
const waiting = new Set();

export function reachScrollers(root) {
  sweep(root);
  paintReach();
  if (watchingSurfaces) return;
  watchingSurfaces = true;
  watchArrivals(SCROLL_SURFACE, ["class", "style"], {
    arriveBatch(surfaces) {
      for (const el of surfaces) {
        const classes = el.getAttribute("class");
        const style = el.getAttribute("style");
        const previous = seenDeclarations.get(el);
        if (previous?.classes === classes && previous?.style === style) continue;
        seenDeclarations.set(el, { classes, style });
        reread(el);
      }
    },
    leave: forgetSurface,
  });
}

const wait = (el) => {
  waiting.add(el);
  reachSizes.observe(el);
};
function sweep(root) {
  const scopes = [root];
  for (const scope of scopes) scopes.push(...shadowRootsIn(scope));
  for (const scope of scopes) watchAncestorStyles(scope);
  const surfaces = scopes.flatMap((scope) => [
    ...(scope.nodeType === Node.ELEMENT_NODE && scope.matches(SCROLL_SURFACE)
      ? [scope]
      : []),
    ...scope.querySelectorAll(SCROLL_SURFACE),
  ]);
  const read = [];
  const containers = new Set();
  for (const el of surfaces) {
    seenDeclarations.set(el, {
      classes: el.getAttribute("class"),
      style: el.getAttribute("style"),
    });
    if (skipped(el)) {
      wait(el);
      continue;
    }
    const style = getComputedStyle(el);
    read.push([
      el,
      {
        overflowX: style.overflowX,
        overflowY: style.overflowY,
        position: style.position,
        direction: style.direction,
      },
    ]);
    for (let node = el; node?.nodeType === Node.ELEMENT_NODE; node = upFrom(node)) {
      scrollAncestors.add(node);
      if (containers.has(node)) break;
      containers.add(node);
    }
  }
  // Finish all style readings before slot marks invalidate descendants' styles.
  const queriesRead = [...containers].map((el) => [
    el,
    { containerType: getComputedStyle(el).containerType },
  ]);
  for (const [el, style] of queriesRead) noteQueries(el, style);
  for (const [el, style] of read) {
    const waited = waiting.delete(el);
    classify(el, style);
    if (waited) release(el);
  }
  asked.add(root);
}

function forgetSurface(el) {
  seenDeclarations.delete(el);
  if (mayScroll.has(el)) {
    const authored = mayScroll.get(el);
    mayScroll.delete(el);
    if (!claimedStops.has(el)) returnStop(el, authored);
  }
  sideways.delete(el);
  waiting.delete(el);
  keeps(el, PAGE_PAINT_ATTRIBUTE.scrolls, null);
  keeps(el, PAGE_PAINT_ATTRIBUTE.scrollDirection, null);
  keeps(el, PAGE_PAINT_ATTRIBUTE.moreBefore, null);
  keeps(el, PAGE_PAINT_ATTRIBUTE.moreAfter, null);
  if (!watched(el)) unwatchReach(el);
}

// Responsive overflow determines whether the surface restarts the sticky slot.
// Sideways surfaces preserve covering headers for landings inside them. Sticky
// owners set their focus inset beside their position declaration in CSS.
function paintSlot(el, style) {
  const sticks = style.position === "sticky";
  const scrolls = scrollsBy(style) && !sticks && !el.matches(TEXT_BOX);
  const across = userScrollport(style.overflowX) && !userScrollport(style.overflowY);
  keeps(el, PAGE_PAINT_ATTRIBUTE.scrolls, scrolls ? (across ? "across" : "") : null);
}

function classify(el, style) {
  asked.add(el);
  paintSlot(el, style);
  if (!userScrollport(style.overflowX) && sideways.delete(el)) {
    keeps(el, PAGE_PAINT_ATTRIBUTE.scrollDirection, null);
    keeps(el, PAGE_PAINT_ATTRIBUTE.moreBefore, null);
    keeps(el, PAGE_PAINT_ATTRIBUTE.moreAfter, null);
  }
  // The rest is for a box the user can scroll. One that no longer is gives back the
  // stop this pass lent it.
  if (
    el.hasAttribute("hidden") ||
    (!userScrollport(style.overflowX) && !userScrollport(style.overflowY))
  ) {
    if (!mayScroll.has(el)) return;
    const authored = mayScroll.get(el);
    mayScroll.delete(el);
    if (!claimedStops.has(el)) returnStop(el, authored);
    if (!watched(el)) unwatchReach(el);
    return;
  }
  // A text box is out of the continuation marks for its own reason: it scrolls a
  // value its user is writing and already knows continues.
  if (userScrollport(style.overflowX) && !el.matches(TEXT_BOX)) {
    if (!sideways.has(el)) {
      watchReach(el);
    }
    sideways.set(el, style.direction);
  }
  // A box that already carries a stop of its own is somewhere the user can be put,
  // whoever put it there; this pass neither adds to it nor takes it away.
  if (!mayScroll.has(el)) {
    if (el.tabIndex >= 0 && !claimedStops.has(el)) return;
    mayScroll.set(
      el,
      wearsLentStop(el) || claimedStops.has(el) ? null : el.getAttribute("tabindex"),
    );
  }
  // The box itself, not the page's: a candidate's own resize is exactly the moment
  // its answer can change, and asking it there is one observation per candidate
  // rather than a sweep per layout pass. Watching body instead read the old width —
  // the observation arrives after the frame that resized, and axe was already
  // looking.
  watchReach(el);
}
// What a box holds moves its overflow as much as its own size does, and can move
// without it: text rewrapping at a new width inside a pane of fixed height, frames a
// widget sizes a pass after its host. So a candidate's children are watched beside it,
// whichever children it holds: one a widget swaps in is watched from its arrival, which
// is itself a change to what the box holds, and one it takes out is let go.
const childrenWatched = new WeakSet();
const childLists = new MutationObserver((records) => {
  for (const { target, addedNodes, removedNodes } of records) {
    if (!childrenWatched.has(target)) continue;
    for (const node of removedNodes)
      if (node.nodeType === Node.ELEMENT_NODE) release(node);
    for (const node of addedNodes)
      if (node.nodeType === Node.ELEMENT_NODE)
        reachSizes.observe(/** @type {Element} */ (node));
  }
});
function watchReach(el) {
  reachSizes.observe(el);
  if (childrenWatched.has(el)) return;
  childrenWatched.add(el);
  for (const child of el.children) reachSizes.observe(child);
  childLists.observe(el, { childList: true });
}
// A MutationObserver lets go of no single target, so a box no longer watched is only
// left out of what its deliveries do.
function unwatchReach(el) {
  const heldChildren = childrenWatched.delete(el);
  release(el);
  if (heldChildren) for (const child of el.children) release(child);
}
// One observation serves every reason to watch a box: a candidate in its own right,
// and the child of one. It ends only when neither holds, so a nested scroller moved
// out of its parent keeps the watch it has as a candidate.
function release(node) {
  if (!watched(node) && !childrenWatched.has(node.parentElement))
    reachSizes.unobserve(node);
}
const depth = (el) => {
  let levels = 0;
  for (let node = el; node; node = upFrom(node)) levels++;
  return levels;
};
const watched = (el) =>
  mayScroll.has(el) || sideways.has(el) || downwards.has(el) || waiting.has(el);
// Re-read each candidate after layout moves it. A user who widens the window is owed
// the stop's removal as much as its arrival: a box that fits carries nothing to scroll
// to, and a tab stop on it is a press that goes nowhere. The candidate sets keep the
// pass to the boxes that scroll, about a hundred of the corpus's ten thousand elements.
// `tabIndex` and the paint attributes move no box, which keeps the pass safe inside
// syncLayout.
const reachSizes = sizeObserver(() => paintReach());
// A pixel of tolerance, where the stop takes any overflow at all: the stop is owed
// wherever the keyboard cannot reach something, and a fade drawn for sub-pixel rounding
// is a promise of more with nothing behind it. scrollLeft follows the inline direction:
// it starts at zero and becomes negative in a right-to-left scroller.
function paintSidewaysReach(el, readStyle = false) {
  // An allocating owner can resize a pane before its image or table owner fits the
  // contents. Like vertical reading cues, read the completed layout for this script.
  afterScript(() => {
    if (!sideways.has(el) || unpainted(el)) return;
    const direction = readStyle ? getComputedStyle(el).direction : sideways.get(el);
    if (readStyle) sideways.set(el, direction);
    const scrolling = el.scrollWidth > el.clientWidth + 1;
    const maximum = Math.max(0, el.scrollWidth - el.clientWidth);
    const raw = Math.abs(el.scrollLeft);
    const position = Math.min(maximum, Math.max(0, raw));
    keeps(el, PAGE_PAINT_ATTRIBUTE.scrollDirection, scrolling ? direction : null);
    el.toggleAttribute(
      PAGE_PAINT_ATTRIBUTE.moreBefore,
      scrolling && position > SCROLL_SLACK,
    );
    el.toggleAttribute(
      PAGE_PAINT_ATTRIBUTE.moreAfter,
      scrolling && position < maximum - SCROLL_SLACK,
    );
  });
}
function gone(el) {
  if (el.isConnected) return false;
  mayScroll.delete(el);
  sideways.delete(el);
  downwards.delete(el);
  waiting.delete(el);
  if (queried.delete(el)) queries.unobserve(el);
  unwatchReach(el);
  return true;
}
// A box that stands in skipped content keeps what it last wore until it is drawn: measuring
// it would force that content's style, and a box on no screen is no stop and shows no
// edge. The reading and sideways edge paints ask it themselves, since a reading region
// is painted as it registers, and a block can register in a hidden panel (bounds.js).
const unpainted = (el) => gone(el) || skipped(el);
function paintReach() {
  // A retained widget can resize its scroller through several intermediate boxes in
  // one script. Lend or return its keyboard stop from the final box only.
  afterScript(paintReachNow);
}
function paintReachNow() {
  for (const el of waiting) if (!unpainted(el)) sweep(el);
  // A box holding a scroller that takes a stop holds a stop, so an outer box's answer
  // waits on its inner boxes': the deepest are asked first, and each box is written once.
  const levels = new Map([...mayScroll.keys()].map((el) => [el, depth(el)]));
  for (const [el, authored] of [...mayScroll].sort(
    ([a], [b]) => levels.get(b) - levels.get(a),
  )) {
    if (unpainted(el)) continue;
    if (claimedStops.has(el)) continue;
    if (overflows(el) && !holdsOwnStop(el)) lendStop(el);
    else returnStop(el, authored);
  }
  for (const el of sideways.keys()) paintSidewaysReach(el);
  for (const el of downwards.keys()) paintReadingReach(el);
}

// Overflow may change at a breakpoint without changing a surface's own dimensions.
// Re-read declared surfaces after a window/container resize or an owner's layout
// signal. This work scales with scroll surfaces, so it needs no quiet-time scheduler.
const rereads = new Set();
let rereadQueued = false;
function reread(root) {
  rereads.add(root);
  if (rereadQueued) return;
  rereadQueued = true;
  nextRender(() => {
    rereadQueued = false;
    const roots = [...rereads];
    rereads.clear();
    const due = new Set(roots);
    for (const root of roots) {
      if (!root.isConnected) continue;
      let covered = false;
      for (let ancestor = upFrom(root); ancestor; ancestor = upFrom(ancestor))
        if (due.has(ancestor)) {
          covered = true;
          break;
        }
      if (covered) continue;
      sweep(root);
    }
    paintReach();
  });
}

// Each container is held with the size its queries last read, an inline size or both,
// taken from its first observation. It is observed from the next frame, not as the
// sweep finds it, since a sweep of a waiting box runs inside a size delivery (above).
const queried = new Map();
const unobserved = new Set();
function noteQueries(el, { containerType }) {
  const kinds = containerType.split(" ");
  const both = kinds.includes("size");
  if (!both && !kinds.includes("inline-size")) {
    if (queried.delete(el)) queries.unobserve(el);
    return;
  }
  if (queried.get(el)?.both === both) return;
  queried.set(el, { both, size: null });
  if (!unobserved.size) nextRender(observeQueried);
  unobserved.add(el);
}
function observeQueried() {
  for (const el of unobserved) if (queried.has(el)) queries.observe(el);
  unobserved.clear();
}
const queries = sizeObserver(
  (entries) => {
    for (const { target, contentBoxSize } of entries) {
      const query = queried.get(target);
      if (!query || gone(target)) continue;
      const [{ inlineSize, blockSize }] = contentBoxSize;
      const size = query.both ? `${inlineSize} ${blockSize}` : `${inlineSize}`;
      if (query.size !== null && query.size !== size) reread(target);
      query.size = size;
    }
  },
  { counted: false },
);
addEventListener("resize", () => reread(document.body));
// A widget can rearrange descendants without changing its outer box. ResizeObserver
// cannot hear that case; the layer's shared geometry signal can. One repaint updates
// every candidate and registered reading region after the new layout is stated, and
// what was rearranged is read again, since a box in it may scroll now. A box no sweep
// has reached yet, itself or through what holds it, is left to the sweep the page's
// install runs, which a widget rearranging itself as it upgrades would otherwise run
// early.
const asked = new WeakSet();
const reached = (el) => {
  for (let node = el; node; node = upFrom(node)) if (asked.has(node)) return true;
  return false;
};
document.addEventListener(LAYOUT, (event) => {
  const [changed] = /** @type {Node[]} */ (event.composedPath());
  if (changed?.nodeType === Node.ELEMENT_NODE && reached(changed)) reread(changed);
  paintReach();
});
