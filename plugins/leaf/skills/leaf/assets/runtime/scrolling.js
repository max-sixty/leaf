// The element the document scrolls: body, not the viewport (see the stylesheet in the
// entry module, and Scrolling in its module header). Anything that reads a reading
// position, sets one, or hands a scroll container to a library uses this — window.scrollY
// is always 0 here, and document.scrollingElement still names the html element, which no
// longer scrolls. Vendored libraries that resolve the scroller themselves are the trap:
// SortableJS walks up from the dragged card and, on reaching body, hands back
// document.scrollingElement, so lf-board passes this in rather than letting it guess.
export const pageScroller = document.body;
// The room the scroller's own bar takes out of the page, which is a fact about the
// scroller and so belongs beside it: every geometry reading that starts from the window
// owes it, and each of them differs in what the gutter is coming off rather than in how it
// is found. The difference between the scroller's two boxes is the only way to ask — no
// platform states the width, and the window states nothing about a bar drawn inside it.
// Constant through a panel's slide, both boxes moving with the margin together, and
// invariant under the strip veto's own padding, which is inside both. Overlay scrollbars
// are 0, which is why one platform never sees any of this.
export const scrollerGutter = () => pageScroller.offsetWidth - pageScroller.clientWidth;
