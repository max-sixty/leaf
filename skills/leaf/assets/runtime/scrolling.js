// The browser's document scrollport. Keeping the platform's root as the one page
// scroller lets fragment links, history restoration, wheel/touch input, and browser UI
// all describe the same reading position. Auxiliary surfaces still own their nested
// scrollports; scrollerFor is the shared answer when a caller may stand in either.
export const pageScroller = document.scrollingElement;

// The end is a reading destination, rather than the pixel offset it occupies before
// a box is resized. Fractional layout can leave the browser a pixel short.
export const atScrollEnd = (box) =>
  box.scrollHeight - box.clientHeight - box.scrollTop <= 2;
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
  Math.max(
    -box.scrollTop,
    Math.min(box.scrollHeight - box.clientHeight - box.scrollTop, top),
  );
