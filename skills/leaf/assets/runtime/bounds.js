/* A block bounded at its end (x-bound or data-bound="end", painted as data-lf-bound)
   follows its newest entry: it opens at the end, and what arrives there stays in view
   while the reader is at the end. A reader who scrolls back stays where they stopped,
   since a log that pulls them down while they are reading an earlier line is a log they
   cannot read; returning to the end resumes following.

   Whether the reader is at the end is read from their scroll, not from the content: by
   the time content has changed, the box's scroll height has already moved past a
   reader who was at the end a moment ago. A scroll event can also trail the change it
   answers by a frame, so a box standing above where this module last put it has been
   scrolled back even before its event arrives. The theme bounds the box; this module
   only holds its place, so a copy with no script keeps the bound and opens at the top.

   The box that scrolls is the one holding the bound's height: the bounded element, or
   the one box inside it a widget's theme bounds instead — a captured document scrolls
   its listing under a caption that stays put. Each bounded block is watched on its own,
   for what it holds and for its size, so nothing here runs for a change elsewhere on
   the page; `followBounds` runs after every install and patch to pick up new ones. */
import { PAGE_PAINT_ATTRIBUTE } from "./presentation.js";

const FOLLOWING = `[${PAGE_PAINT_ATTRIBUTE.bound}="end"]`;
// A box scrolled to within this of its end is at its end: fractional scroll positions
// on scaled displays leave a pinned box a pixel short.
const SLACK = 2;
const followed = new WeakMap();

const atEnd = (box) => box.scrollHeight - box.scrollTop - box.clientHeight <= SLACK;
const holdsBound = (box) => getComputedStyle(box).maxHeight !== "none";

function scrollerOf(bounded) {
  if (holdsBound(bounded)) return bounded;
  for (const box of bounded.querySelectorAll("*")) if (holdsBound(box)) return box;
  return null;
}

function follow(bounded) {
  const state = { box: null, pinned: null, left: false };
  const pin = () => {
    if (!bounded.isConnected) return;
    const box = scrollerOf(bounded);
    if (box !== state.box) {
      state.box?.removeEventListener("scroll", onScroll);
      box?.addEventListener("scroll", onScroll, { passive: true });
      if (box) resize.observe(box);
      state.box = box;
      state.left = false;
    }
    if (!box) return;
    if (state.pinned !== null && box.scrollTop < state.pinned - SLACK && !atEnd(box))
      state.left = true;
    if (state.left) return;
    box.scrollTop = box.scrollHeight;
    state.pinned = box.scrollTop;
  };
  const onScroll = () => {
    state.left = !atEnd(state.box);
    if (!state.left) state.pinned = state.box.scrollTop;
  };
  const resize = new ResizeObserver(pin);
  new MutationObserver(pin).observe(bounded, {
    childList: true,
    characterData: true,
    subtree: true,
  });
  followed.set(bounded, pin);
  pin();
}

export function followBounds() {
  for (const bounded of document.querySelectorAll(FOLLOWING))
    if (!followed.has(bounded)) follow(bounded);
}
