/* Scroll positions, and whose each one is.

   A box stands where the reader chose, or where layout put it. The reader chooses with
   a wheel, a key or a scrollbar, through a Leaf landing (landing-scroll.js), and through
   the browser's own navigation, such as find-in-page opening a closed disclosure onto
   its match. Layout puts a box where a clamp leaves it as content shrinks, where scroll
   anchoring adjusts it, and at the offset it kept while it did not scroll. Continuity's
   shift restore (version.js) undoes only layout's moves, so it asks which boxes the
   reader has chosen for since its reading (`chosenSince`).

   The platform draws the line: a scroll sequence ends with `scrollend`, whoever started
   it, and layout's moves start none (measured in Chromium and WebKit). So a `scrollend`
   on a box is a choice, with two exceptions. A place keeper's write returns the reader
   to a place they already had (reading-place.js, `restorePlace`; user-place.js,
   `placeKeeper`; continuity's move of the page with its band), so it says where it
   left each box (`placeKept`), and a sequence ending there is the keeper's. A landing
   in motion counts from its start (`chooseScroll`), since layout it caused can be
   announced before its sequence ends. A sequence can end frames after its last
   `scroll` event, as WebKit's do, so continuity takes a reading at the end too. Like
   that record, this listens on the document, which a scroll inside a shadow root does
   not reach. */

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
    const box = target === document ? pageScroller : /** @type {Element} */ (target);
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
export const moveScrollerBy = (box, top, behavior = "instant") => {
  const aim = box.scrollTop + top;
  if (Math.abs(top) >= 0.5) box.scrollBy({ top, behavior });
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
