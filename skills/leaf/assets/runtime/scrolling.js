/* Scroll positions, and whose each one is.

   A box stands where the reader chose, or where layout forced it. The reader chooses
   with a wheel, a key or a scrollbar, through a Leaf landing (landing-scroll.js), and
   through the browser's own navigation, such as find-in-page opening a closed
   disclosure onto its match. Layout forces a clamp as content shrinks, scroll
   anchoring's adjustment, and the offset a box keeps when it starts to scroll again. A
   place keeper that restores a reading after layout moved the words (reading-place.js,
   `restorePlace`; user-place.js, `placeKeeper`) undoes only layout's moves, so it asks
   which boxes the reader has chosen for since its reading (`chosenSince`).

   The platform draws this line: a scroll sequence ends with `scrollend`, whoever
   started it, and layout's moves start none. So a `scrollend` on a box is a choice,
   with two exceptions. A keeper's restore is a scroll sequence too but returns the reader
   to a place they already had, so it says where it left each box (`placeKept`), and a
   sequence that ends there is the keeper's. A landing in motion is counted when it
   starts (`chooseScroll`), since a layout it caused can be announced before its
   sequence ends. A scroll in a shadow root reaches no listener here, as it reaches
   continuity's record of the reader's place (version.js) none. */

// The browser's document scrollport. Keeping the platform's root as the one page
// scroller lets fragment links, history restoration, wheel/touch input, and browser UI
// all describe the same reading position. Auxiliary surfaces still own their nested
// scrollports; scrollerFor is the shared answer when a caller may stand in either.
export const pageScroller = document.scrollingElement;

let choices = 0;
const chosen = new WeakMap();
const kept = new WeakMap();
// How many choices the reader has made so far, for a keeper to note with a reading.
export const scrollChoices = () => choices;
// Whether the reader chose where `box` stands after the `count`th choice.
export const chosenSince = (box, count) => (chosen.get(box) ?? 0) > count;
export const chooseScroll = (box) => chosen.set(box, ++choices);
export function placeKept(...boxes) {
  for (const box of boxes) kept.set(box, box.scrollTop);
}
document.addEventListener(
  "scrollend",
  ({ target }) => {
    const box = target === document ? pageScroller : target;
    if (kept.get(box) !== box.scrollTop) chooseScroll(box);
    kept.delete(box);
  },
  { capture: true, passive: true },
);

// The furthest a box scrolls down: its scroll height less what its scrollport shows.
export const scrollLimit = (box) => Math.max(0, box.scrollHeight - box.clientHeight);

// How far short of a scroll edge a box still stands at it: fractional layout and scaled
// displays leave the browser a pixel short of where a scroll was aimed.
export const SCROLL_SLACK = 2;
// The end is a reading destination, rather than the pixel offset it occupies before
// a box is resized.
export const atScrollEnd = (box) => scrollLimit(box) - box.scrollTop <= SCROLL_SLACK;
export const scrollToEnd = (box, behavior = "instant") =>
  box.scrollTo({ top: box.scrollHeight, behavior });

// Apply a relative movement to the scroller the caller resolved. Keeping the box explicit
// lets document reading continuity and anchor travel share the operation without either
// owning the other's default destination.
export const moveScrollerBy = (box, top, behavior = "instant") =>
  box.scrollBy({ top, behavior });

// How much of a move a box can make from where it stands: a box at its end moves no
// further, whatever it is asked.
export const reachable = (box, top) =>
  Math.max(-box.scrollTop, Math.min(scrollLimit(box) - box.scrollTop, top));
