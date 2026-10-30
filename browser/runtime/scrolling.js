/* Scroll positions, and whose each one is.

   A box stands where the reader chose, or where layout put it. The reader chooses with
   a wheel, a key or a scrollbar, through a Leaf landing (landing-scroll.js), and through
   the browser's own navigation, such as find-in-page opening a closed disclosure onto
   its match. Layout puts a box where a clamp leaves it as content shrinks, where scroll
   anchoring adjusts it, and at the offset it kept while it did not scroll. Continuity's
   shift restore (version.js) undoes only layout's moves, so it asks which boxes the
   reader has chosen for since its reading (`chosenSince`).

   A scroll sequence ends with `scrollend`, whoever started it, and Chromium, Firefox and
   WebKit also end one at once where layout moves the box, by anchoring or a clamp, one
   sequence for each move (measured in Chromium 156, Firefox 157 and WebKit 27). So a
   sequence of several scroll events is a glide someone drove, and a single move is a
   choice unless layout explains it: the box's extent changed while it moved
   (`watchLayout`). A script's jump in the frame of a layout change therefore reads as
   layout's, and the reader's input aimed at the box, which continuity records itself
   (version.js, `inputSince`), settles those. The browser's travel into hidden content,
   as find-in-page opening a fold onto its match, fires `beforematch` first, so its end
   is a choice whatever the opening did to the layout. An end that leaves the box where
   its last one did, as Firefox sends after a layout move, chose nothing. A place
   keeper's write returns the reader to a place they already had (reading-place.js,
   `restorePlace`; user-place.js, `placeKeeper`; continuity's move of the page with its
   band), so it says where it left each box (`placeKept`), and a sequence ending there
   is the keeper's. A landing in motion counts from its start (`startScroll`), since
   layout it caused can be announced before its sequence ends. A sequence can end frames
   after its last `scroll` event, as WebKit's do, so continuity takes a reading at the
   end too. Like that record, this listens on the document, which a scroll inside a
   shadow root does not reach. */

import { nextFrame, sizeObserver } from "./rendering.js";
import { setScroll, watchOwner } from "./arrivals.js";
import { skipped } from "./shown-box.js";

// The browser's document scrollport. Keeping the platform's root as the one page
// scroller lets fragment links, history restoration, wheel/touch input, and browser UI
// all describe the same reading position. The chrome's views still own their nested
// scrollports; scrollerFor is the shared answer when a caller may stand in either.
export const pageScroller = document.scrollingElement;

const moving = new WeakMap();
// Where each box's last sequence ended, the boxes layout has moved since, and each box's
// extent where its layout last settled. A box is watched from its first scroll, through
// its own size and its children's, where content grows, so content that grew between
// sequences doesn't make the next one layout's.
const ended = new WeakMap();
const scrollSteps = new WeakMap();
const layoutMoved = new WeakSet();
const watchedLayout = new WeakSet();
const extents = new WeakMap();
const extentOf = (box) => [box.scrollHeight, box.clientWidth, box.clientHeight];
const changedExtent = (before, after) =>
  before?.some((value, index) => value !== after[index]);
function watchLayout(box) {
  if (watchedLayout.has(box)) return;
  watchedLayout.add(box);
  extents.set(box, extentOf(box));
  const root = box === pageScroller ? document.documentElement : box;
  const sizes = new WeakMap();
  // Observe skipped children too, so revealing them supplies their first reading.
  const measure = (node) =>
    skipped(node) ? null : [node.clientWidth, node.clientHeight, node.scrollHeight];
  const observer = sizeObserver(
    (entries) => {
      let changed = false;
      for (const { target } of entries) {
        const next = measure(target);
        const before = sizes.get(target);
        sizes.set(target, next);
        if (next && (!before || before.some((value, index) => value !== next[index])))
          changed = true;
      }
      if (changed) {
        if (ended.has(box) && box.scrollTop !== ended.get(box)) layoutMoved.add(box);
        else extents.set(box, extentOf(box));
      }
    },
    { counted: false },
  );
  const observe = (node) => {
    sizes.set(node, measure(node));
    observer.observe(node);
  };
  observe(root);
  if (box !== pageScroller) {
    for (const child of box.children) observe(child);
    const mutation = new MutationObserver((entries) => {
      for (const entry of entries) {
        for (const node of entry.addedNodes) if (node instanceof Element) observe(node);
        for (const node of entry.removedNodes)
          if (node instanceof Element) observer.unobserve(node);
      }
    });
    mutation.observe(box, { childList: true });
    watchOwner(box, {
      disconnect() {
        observer.disconnect();
        mutation.disconnect();
        watchedLayout.delete(box);
      },
    });
  }
}
// The page is watched from the start, so where it stands now counts as its last end.
watchLayout(pageScroller);
ended.set(pageScroller, pageScroller.scrollTop);

// A new landing or return takes over the old native placement, even if its target
// is already visible. Chromium can deliver one last compositor scroll after this
// instant cancellation, so its rendering update must finish before the caller reads
// geometry and places the new destination. Two callbacks enclose that whole update.
export function stopScroll(boxes) {
  const stopped = [...boxes]
    .filter((box) => moving.has(box))
    .map((box) => [box, moving.get(box)]);
  if (!stopped.length) return null;
  for (const [box] of stopped)
    setScroll(box, {
      left: box.scrollLeft,
      top: box.scrollTop,
      behavior: "instant",
    });
  return new Promise((resolve) =>
    nextFrame(() =>
      nextFrame(() => {
        for (const [box, sequence] of stopped)
          if (moving.get(box) === sequence) moving.delete(box);
        resolve(undefined);
      }),
    ),
  );
}

let choices = 0;
const chosen = new WeakMap();
const kept = new WeakMap();
// How many choices the reader has made so far, for a keeper to note with a reading.
export const scrollChoices = () => choices;
// Whether the reader chose where `box` stands after the `count`th choice.
export const chosenSince = (box, count) => (chosen.get(box) ?? 0) > count;
const chooseScroll = (box) => chosen.set(box, ++choices);
// Record a native glide before its first compositor frame; scroll events alone
// cannot report an outgoing placement a new gesture interrupts that early.
export function startScroll(box) {
  moving.set(box, { glide: true });
  chooseScroll(box);
}
// The browser's travel into hidden content, until the sequence it starts has ended,
// which is before the second frame after.
let travel = null;
document.addEventListener(
  "beforematch",
  () => {
    const mark = (travel = {});
    nextFrame(() =>
      nextFrame(() => {
        if (travel === mark) travel = null;
      }),
    );
  },
  { capture: true },
);
const eventScroller = (target) => (target === document ? pageScroller : target);
document.addEventListener(
  "scroll",
  ({ target }) => {
    const box = eventScroller(target);
    if (skipped(box)) return;
    watchLayout(box);
    scrollSteps.set(box, (scrollSteps.get(box) ?? 0) + 1);
    if (moving.get(box)?.glide) return;
    // Native input keeps sending scroll while it moves; a sequence that has gone quiet
    // expires after an update.
    const sequence = { glide: false };
    moving.set(box, sequence);
    nextFrame(() =>
      nextFrame(() => {
        if (moving.get(box) === sequence) moving.delete(box);
      }),
    );
  },
  {
    capture: true,
    passive: true,
  },
);
export function placeKept(...boxes) {
  for (const box of boxes) kept.set(box, box.scrollTop);
}
document.addEventListener(
  "scrollend",
  ({ target }) => {
    const box = eventScroller(target);
    if (skipped(box)) {
      moving.delete(box);
      scrollSteps.delete(box);
      layoutMoved.delete(box);
      return;
    }
    watchLayout(box);
    const wasMoving = moving.get(box);
    moving.delete(box);
    const extent = extentOf(box);
    const repeated = (scrollSteps.get(box) ?? 0) > 1;
    scrollSteps.delete(box);
    const chosenHere =
      wasMoving?.glide ||
      repeated ||
      travel !== null ||
      (ended.get(box) !== box.scrollTop &&
        !layoutMoved.has(box) &&
        !changedExtent(extents.get(box), extent));
    if (chosenHere && kept.get(box) !== box.scrollTop) chooseScroll(box);
    ended.set(box, box.scrollTop);
    layoutMoved.delete(box);
    extents.set(box, extent);
    kept.delete(box);
  },
  { capture: true, passive: true },
);

// Boxes whose content is drawn away from where its layout stands it. A send's stream
// (box-motion.js) draws a scroller's content where it stood, below where its layout now
// stands it, and the browser counts that drawing in the box's scroll height while the
// content rides (`contentRides`, false when the ride ends). Meanwhile the box's height
// is read from its layout each time it is asked, so its end stays where its layout puts
// it, content arriving mid-ride included, and a landing at the end doesn't chase the
// ride.
const riding = new WeakSet();
export const contentRides = (box, rides) =>
  rides ? riding.add(box) : riding.delete(box);
// A box's scroll height as its layout gives it: from where its children stand, which
// offsets read without any transform, and its own end padding. A child placed against
// something other than the box leaves the browser's reading.
function laidOutHeight(box) {
  let end = 0;
  for (const child of box.children) {
    if (!child.checkVisibility()) continue;
    if (child.offsetParent !== box) return box.scrollHeight;
    end = Math.max(
      end,
      child.offsetTop +
        child.offsetHeight +
        Number.parseFloat(getComputedStyle(child).marginBottom),
    );
  }
  const padding = Number.parseFloat(getComputedStyle(box).paddingBottom);
  return Math.min(box.scrollHeight, end + padding);
}
// The furthest a box scrolls down: its scroll height less what its scrollport shows.
export const scrollLimit = (box) =>
  Math.max(
    0,
    (riding.has(box) ? laidOutHeight(box) : box.scrollHeight) - box.clientHeight,
  );

// How far short of a scroll edge a box still stands at it: fractional layout and scaled
// displays leave the browser a pixel short of where a scroll was aimed.
export const SCROLL_SLACK = 2;
// The end is a reading destination, rather than the pixel offset it occupies before
// a box is resized.
export const atScrollEnd = (box) => scrollLimit(box) - box.scrollTop <= SCROLL_SLACK;
/** @param {Element} box @param {ScrollBehavior} behavior */
export const scrollToEnd = (box, behavior = "instant") => {
  if (behavior !== "instant" && !atScrollEnd(box)) startScroll(box);
  setScroll(box, { top: scrollLimit(box), behavior });
};

// Apply a relative movement to the scroller the caller resolved. Keeping the box explicit
// lets document reading continuity and anchor travel share the operation without either
// owning the other's default destination. A move of less than a pixel is none: written,
// it would still stop a smooth scroll under way in the box.
//
// A box stores a whole-pixel offset, rounding a fractional one (Chromium to the nearest,
// WebKit down: measured in both, at device pixel ratios 1 and 2), and words stand at
// fractions of a pixel. So an instant move lands less than a pixel off its aim,
// and the box remembers its aim while it stands where the move left it (`aimedTop`).
// A place read there, and a keeper's next correction, start from the aim: started
// from where the box landed, each move's rounding would add to the last, and a line
// would creep across the screen revision by revision, or frame by frame of a fold.
const aims = new WeakMap();
/** @param {Element} box @param {number} top @param {ScrollBehavior} behavior */
export const moveScrollerBy = (box, top, behavior = "instant") => {
  const aim = box.scrollTop + top;
  if (Math.abs(top) >= 0.5) {
    if (behavior !== "instant" && reachable(box, top)) startScroll(box);
    setScroll(box, { top: aim, behavior });
  }
  if (behavior === "instant" && Math.abs(aim - box.scrollTop) < 1)
    aims.set(box, { aim, at: box.scrollTop });
  else aims.delete(box);
};
// Where Leaf last aimed `box`, while it stands where that move left it, else its offset.
// A move that landed a pixel or more off was cut off by the box's range, and names no
// position the box stands at.
export const aimedTop = (box) => {
  const kept = aims.get(box);
  return kept?.at === box.scrollTop ? kept.aim : box.scrollTop;
};

// How much of a move a box can make from where it stands: a box at its end moves no
// further, whatever it is asked.
export const reachable = (box, top) =>
  Math.max(-box.scrollTop, Math.min(scrollLimit(box) - box.scrollTop, top));
