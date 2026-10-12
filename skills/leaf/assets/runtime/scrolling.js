// The browser's document scrollport. Keeping the platform's root as the one page
// scroller lets fragment links, history restoration, wheel/touch input, and browser UI
// all describe the same reading position. Auxiliary surfaces still own their nested
// scrollports; scrollerFor is the shared answer when a caller may stand in either.
export const pageScroller = document.scrollingElement;

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
