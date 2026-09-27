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
   declaring it is the scroller, and it is the region's body. Each bounded block is
   watched on its own, for what it holds and for its size, so nothing here runs for a
   change elsewhere on the page; `holdBounds` runs after every install and patch to pick
   up new blocks and let go of removed ones. */
import { sizeObserver } from "./rendering.js";
import { PAGE_PAINT_ATTRIBUTE } from "./presentation.js";
import { authoredScope, pageDocument } from "./passages.js";
import { compoundReadingRegionId, registerReadingRegion } from "./reading-regions.js";

const BOUNDED = `[${PAGE_PAINT_ATTRIBUTE.bound}]`;
const FOLLOWING = `[${PAGE_PAINT_ATTRIBUTE.bound}="end"]`;
// A box scrolled to within this of its end is at its end: fractional scroll positions
// on scaled displays leave a pinned box a pixel short.
const SLACK = 2;
const held = new Map();
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
const following = (state) =>
  state.bounded.matches(FOLLOWING) &&
  !state.left &&
  !(
    state.pinned !== null &&
    state.box.scrollTop < state.pinned - SLACK &&
    !atEnd(state.box)
  );

export const followingItsEnd = (box) => {
  const state = byBox.get(box);
  return Boolean(state?.box === box && state.bounded.isConnected && following(state));
};

function hold(bounded) {
  const state = { bounded, box: null, pinned: null, left: false, stopRegion: null };
  const id = regionId(bounded);
  const onScroll = () => {
    state.left = !atEnd(state.box);
    if (!state.left) state.pinned = state.box.scrollTop;
  };
  const sync = () => {
    if (!bounded.isConnected) return;
    const box = scrollerOf(bounded);
    if (box !== state.box) {
      state.box?.removeEventListener("scroll", onScroll);
      state.stopRegion?.();
      box.addEventListener("scroll", onScroll, { passive: true });
      resize.observe(box);
      byBox.set(box, state);
      state.box = box;
      state.left = false;
      state.pinned = null;
      state.stopRegion = registerReadingRegion({ id, host: bounded, body: box });
    }
    if (!bounded.matches(FOLLOWING)) return;
    if (!following(state)) {
      state.left = true;
      return;
    }
    box.scrollTop = box.scrollHeight;
    state.pinned = box.scrollTop;
  };
  const resize = sizeObserver(sync);
  const contents = new MutationObserver(sync);
  contents.observe(bounded, { childList: true, characterData: true, subtree: true });
  state.sync = sync;
  state.release = () => {
    contents.disconnect();
    resize.disconnect();
    state.box?.removeEventListener("scroll", onScroll);
    state.stopRegion?.();
  };
  return state;
}

export function holdBounds() {
  for (const [bounded, state] of held)
    if (!bounded.isConnected || !bounded.matches(BOUNDED)) {
      state.release();
      held.delete(bounded);
    }
  for (const bounded of document.querySelectorAll(BOUNDED)) {
    if (!held.has(bounded)) held.set(bounded, hold(bounded));
    held.get(bounded).sync();
  }
}
