// The browser's document scrollport. Keeping the platform's root as the one page
// scroller lets fragment links, history restoration, wheel/touch input, and browser UI
// all describe the same reading position. Auxiliary surfaces still own their nested
// scrollports; scrollerFor is the shared answer when a caller may stand in either.
export const pageScroller = document.scrollingElement;

// Apply a relative movement to the scroller the caller resolved. Keeping the box explicit
// lets document reading continuity and anchor travel share the operation without either
// owning the other's default destination.
export const moveScrollerBy = (box, top, behavior = "instant") =>
  box.scrollBy({ top, behavior });

// An instant move that puts back what a change moved lands on the whole pixel nearest its
// exact target. A fractional write can land short: in CI's Chrome, a follow meant to keep
// a reply box still left it 0.875px lower.
export const restoreScrollerBy = (box, top) =>
  box.scrollTo({ top: Math.round(box.scrollTop + top), behavior: "instant" });

// How much of a move a box can make from where it stands: a box at its end moves no
// further, whatever it is asked.
export const reachable = (box, top) =>
  Math.max(
    -box.scrollTop,
    Math.min(box.scrollHeight - box.clientHeight - box.scrollTop, top),
  );
