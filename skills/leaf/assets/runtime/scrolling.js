// The browser's document scrollport. Keeping the platform's root as the one page
// scroller lets fragment links, history restoration, wheel/touch input, and browser UI
// all describe the same reading position. Auxiliary workspaces still own their nested
// scrollports; scrollerFor is the shared answer when a caller may stand in either.
export const pageScroller = document.scrollingElement;

// Apply a relative movement to the scroller the caller resolved. Keeping the box explicit
// lets document reading continuity and anchor travel share the operation without either
// owning the other's default destination.
export const moveScrollerBy = (box, top, behavior = "instant") =>
  box.scrollBy({ top, behavior });
