// The element the document scrolls: body, not the viewport (see the stylesheet in the
// entry module, and Scrolling in its module header). Anything that reads a reading
// position, sets one, or hands a scroll container to a library uses this — window.scrollY
// is always 0 here, and document.scrollingElement still names the html element, which no
// longer scrolls. Vendored libraries that resolve the scroller themselves are the trap:
// SortableJS walks up from the dragged card and, on reaching body, hands back
// document.scrollingElement, so lf-board passes this in rather than letting it guess.
export const pageScroller = document.body;
