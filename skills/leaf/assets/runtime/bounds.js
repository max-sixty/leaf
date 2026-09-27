/* A block Leaf bounds (x-bound, or data-bound on an occurrence, painted as
   data-lf-bound) holds its own height and scrolls inside it. The theme bounds the box;
   this module makes the box a reading region and keeps an `end` bound's place.

   Every bounded block is a registered reading region (`reading-regions.js`), so every
   question that names the box scrolling a node gets the block rather than the page:
   where a send lands its thread and which box holds a control still, where anchor
   travel reveals a passage, which margin lane clips a marker, and whose place
   continuity records and restores. A scroller page CSS makes is none of these: Leaf
   keeps no place in it, and `version check` advises bounding the block instead.

   A region needs an id that names it in the next document too, since that is where a
   revision restores its place. A block of the page's own document with an id takes one
   from it. Any other block, an anonymous one or one in a message's frozen markup, whose
   ids repeat the page's, takes an id that names this element in this document alone:
   it answers every geometry question and keeps its place while it stands, and a
   replacement document starts it afresh rather than guess which block it was.

   A block bounded at its end follows its newest entry: it opens at the end, and what
   arrives there stays in view while the user is at the end. A user who scrolls back
   stays where they stopped, since a log that pulls them down while they are reading an
   earlier line is a log they cannot read; returning to the end resumes following. The
   place continuity records for a following block is its end (`followingItsEnd`), so a
   revision that restores places leaves it following rather than on the line that was
   at its top.

   Whether the user is at the end is read from their scroll, not from the content: by
   the time content has changed, the box's scroll height has already moved past a
   user who was at the end a moment ago. A scroll event can also trail the change it
   answers by a frame, so a box standing above where this module last put it has been
   scrolled back even before its event arrives.

   The box that scrolls is the bounded element, unless its widget's theme moves the
   bound to a box inside it and says so there with `--lf-bound-box: 1` — a captured
   document scrolls its listing under a caption that stays put. The outermost box
   declaring it is the scroller, and it is the region's body.

   A block is held from the pass that paints its bound (`markDeclared` calls
   `holdBounds`), in the page or in a message's markup, whether it stands in the
   document yet or not. From then each block is watched on its own, for what it holds
   and for its size, so nothing here runs for a change elsewhere on the page. Its size
   answers for its connection too: a block entering the document gets a box and is
   registered, and one leaving it loses its box and is let go, so what is registered is
   what stands in the document. */
import { sizeObserver } from "./rendering.js";
import { PAGE_PAINT_ATTRIBUTE, elementsIn } from "./presentation.js";
import { authoredScope, pageDocument } from "./passages.js";
import { compoundReadingRegionId, registerReadingRegion } from "./reading-regions.js";

const BOUNDED = `[${PAGE_PAINT_ATTRIBUTE.bound}]`;
const FOLLOWING = `[${PAGE_PAINT_ATTRIBUTE.bound}="end"]`;
// A box scrolled to within this of its end is at its end: fractional scroll positions
// on scaled displays leave a pinned box a pixel short.
const SLACK = 2;
// Each block's hold, for the element's life, and the holds registered now.
const holds = new WeakMap();
const registered = new Set();
const byBox = new WeakMap();
const THIS_DOCUMENT = `lf-region:bound:${performance.timeOrigin}`;
let unnamed = 0;

const atEnd = (box) => box.scrollHeight - box.scrollTop - box.clientHeight <= SLACK;
const declaresBound = (box) =>
  getComputedStyle(box).getPropertyValue("--lf-bound-box").trim() === "1";

function scrollerOf(bounded) {
  // A bound nested inside this one owns its own scroller, so the search stops at it.
  for (const box of bounded.querySelectorAll("*"))
    if (declaresBound(box) && box.closest(BOUNDED) === bounded) return box;
  return bounded;
}

const regionId = (bounded) =>
  bounded.id && authoredScope(bounded) === pageDocument()
    ? compoundReadingRegionId(bounded, "bound")
    : `${THIS_DOCUMENT}:${(unnamed += 1)}`;

// Whether the box's bounded block follows its end and the user is there: the user
// has not scrolled back since this module last pinned it.
const following = (hold) =>
  hold.bounded.matches(FOLLOWING) &&
  !hold.left &&
  !(
    hold.pinned !== null &&
    hold.box.scrollTop < hold.pinned - SLACK &&
    !atEnd(hold.box)
  );

const heldBy = (box) => {
  const hold = byBox.get(box);
  return hold?.box === box && registered.has(hold) ? hold : null;
};

export const followingItsEnd = (box) => {
  const hold = heldBy(box);
  return Boolean(hold && following(hold));
};

// The bounded block a registered region body scrolls, or null for any other box.
export const boundedBlockOf = (box) => heldBy(box)?.bounded ?? null;

function holdBlock(bounded) {
  const hold = { bounded, id: regionId(bounded), box: null, pinned: null, left: false };
  let stopRegion = null;
  const onScroll = () => {
    hold.left = !atEnd(hold.box);
    if (!hold.left) hold.pinned = hold.box.scrollTop;
  };
  const letGo = () => {
    hold.box?.removeEventListener("scroll", onScroll);
    if (hold.box && hold.box !== bounded) resize.unobserve(hold.box);
    stopRegion?.();
    stopRegion = null;
    hold.box = null;
    registered.delete(hold);
  };
  hold.sync = () => {
    if (!bounded.isConnected || !bounded.matches(BOUNDED)) return letGo();
    const box = scrollerOf(bounded);
    if (box !== hold.box) {
      letGo();
      box.addEventListener("scroll", onScroll, { passive: true });
      resize.observe(box);
      byBox.set(box, hold);
      hold.box = box;
      hold.left = false;
      hold.pinned = null;
      stopRegion = registerReadingRegion({ id: hold.id, host: bounded, body: box });
      registered.add(hold);
    }
    if (!bounded.matches(FOLLOWING)) return;
    if (!following(hold)) {
      hold.left = true;
      return;
    }
    box.scrollTop = box.scrollHeight;
    hold.pinned = box.scrollTop;
  };
  const resize = sizeObserver(hold.sync);
  resize.observe(bounded);
  new MutationObserver(hold.sync).observe(bounded, {
    childList: true,
    characterData: true,
    subtree: true,
  });
  return hold;
}

// Hold every bounded block in `root`, and let go of any block that has left the document
// or lost its bound without its size saying so.
export function holdBounds(root) {
  for (const hold of registered)
    if (!hold.bounded.isConnected || !hold.bounded.matches(BOUNDED)) hold.sync();
  for (const bounded of elementsIn(root, BOUNDED)) {
    if (!holds.has(bounded)) holds.set(bounded, holdBlock(bounded));
    holds.get(bounded).sync();
  }
}
