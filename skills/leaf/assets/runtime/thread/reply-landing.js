/* Where a thread lands in the scroller that shows it: the geometry every route into a
   thread shares, whichever surface draws it.

   A thread that fits lands whole. A longer one lands its reply area, Send and Resolve
   with it, or the focused control alone where the editor is too tall for both. A reply
   row pinned to its transcript's foot (the margin card's) reads as shown wherever the
   transcript stands, so a landing on it lands the thread's end instead. The same rows
   answer growth: a box growing under the user's keystrokes keeps its controls in the
   band and the words just above it beside it. */
import { landingBand, shownBox } from "../geometry.js";
import { scrollBehavior } from "../motion.js";
import { SAYS_IN } from "./selectors.js";

const REPLY_ROW = ".lf-compose, .lf-say";
const replyRowOf = (held, control) => {
  const reply = control.closest(REPLY_ROW);
  return reply?.parentElement === held ? reply : null;
};
// A reply row pinned to its scroller's foot (the margin card's) always stands in the band,
// so aiming a scroll at it moves nothing: its place in the transcript is the thread's end.
const pinned = (reply) => reply && getComputedStyle(reply).position === "sticky";

// Keep a whole thread in view when it fits. A long thread reveals its reply
// area, including Send and Resolve; an oversized editor reveals only its control.
// scrollIntoView(nearest) on a card spanning both edges otherwise moves nothing, and
// so does one aimed at a pinned reply row, so a long thread with one lands its end.
const landingRoom = (held) => {
  let room = Infinity;
  for (let parent = held.parentElement; parent; parent = parent.parentElement) {
    const band = landingBand(parent);
    if (band) room = Math.min(room, band.bottom - band.top);
  }
  return room;
};
export const fitsWhole = (held) => shownBox(held).height <= landingRoom(held);
export const landingTarget = (held, control) => {
  const room = landingRoom(held);
  if (shownBox(held).height <= room) return { node: held };
  const reply = replyRowOf(held, control);
  if (pinned(reply)) return { node: held, block: "end" };
  return { node: reply && shownBox(reply).height <= room ? reply : control };
};

export function scrollThreadIntoView(
  held,
  control,
  behavior = scrollBehavior(),
  block = "nearest",
) {
  const target = landingTarget(held, control);
  target.node.scrollIntoView({ behavior, block: target.block ?? block });
}

// The box's scroll container: the one a pinned row sticks inside.
const scrollerOf = (node) => {
  for (let parent = node.parentElement; parent; parent = parent.parentElement)
    if (/auto|scroll/.test(getComputedStyle(parent).overflowY)) return parent;
  return document.scrollingElement;
};

// A reply box growing or shrinking under the user's own keystrokes keeps two things: its
// controls in the band, and the words just above it where they stood beside it. A row in
// flow grows downward, so the words above stay put and only its foot can leave the band,
// which the landing brings back. A pinned row keeps its foot and grows upward over the
// transcript, so the transcript moves by what the row now covers. Reading the row's top in
// its scroller, rather than its height, leaves out growth the scroller took itself (a
// card with room to grow) and any scroll the user made between keystrokes.
const pinnedTops = new WeakMap();
const pinnedTop = (reply) =>
  reply.getBoundingClientRect().top - scrollerOf(reply).getBoundingClientRect().top;
export function followReplyGrowth(input) {
  const held = input.closest(SAYS_IN);
  if (!held) return;
  const reply = replyRowOf(held, input);
  if (!pinned(reply)) return scrollThreadIntoView(held, input, "instant");
  const top = pinnedTop(reply);
  const was = pinnedTops.get(input);
  pinnedTops.set(input, top);
  if (was !== undefined && was !== top)
    scrollerOf(reply).scrollBy({ top: was - top, behavior: "instant" });
}
// Where a pinned row stood when the user came into its box, so the first keystroke's
// growth is measured from there rather than from a reading taken before a landing.
export function readReplyPlace(input) {
  const held = input.closest(SAYS_IN);
  const reply = held && replyRowOf(held, input);
  if (pinned(reply)) pinnedTops.set(input, pinnedTop(reply));
}
