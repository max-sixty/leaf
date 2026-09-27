/* Where a thread lands in the scroller that shows it: the geometry every route into a
   thread shares, whichever surface draws it.

   A thread that fits lands whole. A longer one lands its reply area, Send and Resolve
   with it, or the focused control alone where the editor is too tall for both. A reply
   row pinned to its transcript's foot (the margin card's) reads as shown wherever the
   transcript stands, so a landing on it lands the thread's end instead. A thread too
   tall to show, landed as a whole, stays where it is when any of it is on screen: the
   nearest edge of a box taller than the window is a jump to its top.

   A send lands the turn it adds, and a box growing under the user's keystrokes keeps its
   controls in the band and the words just above it beside it. Every box a thread or a
   seat holds answers both, whichever owner built it. The climbs cross shadow roots,
   since a widget may draw a thread inside its own tree and still be scrolled by the
   page. */
import { landingBand, shownBox } from "../geometry.js";
import { focused } from "../keyboard/scopes.js";
import { scrollBehavior } from "../motion.js";
import { whenDocumentPresented } from "../semantic-state.js";
import { renderedParent } from "../shadow.js";
import { retainUserIntent } from "../user-intent.js";
import { SAYS_IN } from "./selectors.js";

const REPLY_ROW = ".lf-compose, .lf-say";
const replyRowOf = (held, control) => {
  const reply =
    control === held
      ? held.querySelector(":scope > .lf-compose, :scope > .lf-say")
      : control.closest(REPLY_ROW);
  return reply?.parentElement === held ? reply : null;
};
// A reply row pinned to its scroller's foot (the margin card's) always stands in the band,
// so aiming a scroll at it moves nothing: its place in the transcript is the thread's end.
const pinned = (reply) => reply && getComputedStyle(reply).position === "sticky";

const ancestors = function* (node) {
  for (let parent = renderedParent(node); parent; parent = renderedParent(parent))
    yield parent;
};
const scrollBox = (node) => /auto|scroll/.test(getComputedStyle(node).overflowY);
// The box a pinned row sticks inside, whether or not it has anything to scroll yet.
const stickyScroller = (node) => {
  for (const parent of ancestors(node)) if (scrollBox(parent)) return parent;
  return document.scrollingElement;
};
// The box whose scrolling moves the node: the nearest that overflows, or the page's. A
// sideways scroller, such as a diff's code, computes `overflow-y: auto` too and has
// nothing to scroll that way. Nothing scrolls a node inside a fixed box, such as the
// margin card, from outside it: moving the page moves only what the box stands beside.
const scrollerOf = (node) => {
  for (const parent of ancestors(node)) {
    if (scrollBox(parent) && parent.scrollHeight > parent.clientHeight) return parent;
    if (getComputedStyle(parent).position === "fixed") return null;
  }
  return document.scrollingElement;
};
const landingRoom = (held) => {
  let room = Infinity;
  for (const parent of ancestors(held)) {
    const band = landingBand(parent);
    if (band) room = Math.min(room, band.bottom - band.top);
  }
  return room;
};
const onScreen = (node) => {
  const scroller = scrollerOf(node);
  const band = scroller && landingBand(scroller);
  const box = shownBox(node);
  return !band || (box.bottom > band.top && box.top < band.bottom);
};

export const fitsWhole = (held) => shownBox(held).height <= landingRoom(held);
// Keep a whole thread in view when it fits. A long thread reveals its reply
// area, including Send and Resolve; an oversized editor reveals only its control.
// scrollIntoView(nearest) on a card spanning both edges otherwise moves nothing, and
// so does one aimed at a pinned reply row, so a long thread with one lands its end.
export const landingTarget = (held, control) => {
  const room = landingRoom(held);
  if (shownBox(held).height <= room) return { node: held };
  const reply = replyRowOf(held, control);
  // The thread itself, landed as a whole, is not a way into its pinned reply.
  if (pinned(reply))
    return control === held ? { node: null } : { node: held, block: "end" };
  if (reply && shownBox(reply).height <= room) return { node: reply };
  if (control === held && onScreen(held)) return { node: null };
  return { node: control };
};

export function scrollThreadIntoView(
  held,
  control,
  behavior = scrollBehavior(),
  block = "nearest",
) {
  const target = landingTarget(held, control);
  target.node?.scrollIntoView({ behavior, block: target.block ?? block });
}

// Taken as the user sends, before the send's own render: once the page has drawn the new
// turn above the box, land the thread around the control the user sent from, so the
// turn's end shows with that control, unless a newer gesture has taken the user
// elsewhere. A control the send removed has handed the user on already.
export function sendLanding(input, send) {
  const held = input.closest(SAYS_IN);
  const control = focused();
  if (!held || (control !== input && control !== send)) return () => {};
  const mayLand = retainUserIntent({ source: held, available: () => held.isConnected });
  return () =>
    void whenDocumentPresented()
      .then(() => {
        if (mayLand() && control.isConnected) scrollThreadIntoView(held, control);
      })
      .catch(() => {});
}

// A box growing or shrinking under the user's own keystrokes keeps two things: its
// controls in the band, and the words just above it where they stood beside it. A row in
// flow grows downward, so the words above stay put and only its foot can leave the band,
// which the landing brings back. A pinned row keeps its foot and grows upward over the
// transcript, so the transcript moves by what the row now covers. Reading the row's top in
// its scroller, rather than its height, leaves out growth the scroller took itself (a
// card with room to grow) and any scroll the user made between keystrokes.
const pinnedTops = new WeakMap();
const pinnedTop = (reply) =>
  reply.getBoundingClientRect().top - stickyScroller(reply).getBoundingClientRect().top;
export function followBoxGrowth(input) {
  const held = input.closest(SAYS_IN);
  if (!held) return;
  const reply = replyRowOf(held, input);
  if (!pinned(reply)) return scrollThreadIntoView(held, input, "instant");
  const top = pinnedTop(reply);
  const was = pinnedTops.get(input);
  pinnedTops.set(input, top);
  if (was !== undefined && was !== top)
    stickyScroller(reply).scrollBy({ top: was - top, behavior: "instant" });
}
// Where a pinned row stood when the user came into its box, so the first keystroke's
// growth is measured from there rather than from a reading taken before a landing.
export function readBoxPlace(input) {
  const held = input.closest(SAYS_IN);
  const reply = held && replyRowOf(held, input);
  if (pinned(reply)) pinnedTops.set(input, pinnedTop(reply));
}

// A render that inserts above the box the user is writing in, such as a turn arriving,
// moves the box by what it inserted. `holdBox` reads where the focused box stands and
// returns the step that puts it back, so news moves no control under the user's hands.
// A pinned row stands still by itself, and a box the render replaced has nothing to hold.
export function holdBox(input) {
  const held = input?.closest?.(SAYS_IN);
  if (!held || pinned(replyRowOf(held, input))) return () => {};
  const top = input.getBoundingClientRect().top;
  return () => {
    if (focused() !== input || !input.isConnected) return;
    const moved = input.getBoundingClientRect().top - top;
    if (Math.abs(moved) >= 1)
      scrollerOf(input)?.scrollBy({ top: moved, behavior: "instant" });
  };
}
