// The element the document scrolls: body, not the viewport (see the stylesheet in the
// entry module, and Scrolling in its module header). Anything that reads a reading
// position, sets one, or hands a scroll container to a library uses this — window.scrollY
// is always 0 here, and document.scrollingElement still names the html element, which no
// longer scrolls. Vendored libraries that resolve the scroller themselves are the trap:
// SortableJS walks up from the dragged card and, on reaching body, hands back
// document.scrollingElement, so lf-board passes this in rather than letting it guess.
export const pageScroller = document.body;

// Apply a relative movement to the scroller the caller resolved. Keeping the box explicit
// lets document reading continuity and anchor travel share the operation without either
// owning the other's default destination.
export const moveScrollerBy = (box, top, behavior = "instant") =>
  box.scrollBy({ top, behavior });

// A wheel that begins in a fixed surface does not reach body's non-root scroller in
// Chromium, even when the surface has no overflow left to consume. Fixed page furniture
// calls this bridge rather than each restating delta modes, modified gestures, and the
// page lock. The caller prevents the native event only when this moved the destination.
export function moveScrollerFromWheel(box, event, fraction = 1) {
  if (
    event.ctrlKey ||
    event.metaKey ||
    event.shiftKey ||
    !event.deltaY ||
    Math.abs(event.deltaY) <= Math.abs(event.deltaX) ||
    getComputedStyle(box).overflowY === "hidden"
  )
    return false;
  const unit =
    event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? box.clientHeight : 1;
  const before = box.scrollTop;
  box.scrollTo({
    top: before + event.deltaY * unit * fraction,
    behavior: "instant",
  });
  return box.scrollTop !== before;
}

// The room the scroller's own bar takes out of the page, which is a fact about the
// scroller and so belongs beside it: every geometry reading that starts from the window
// owes it, and each of them differs in what the gutter is coming off rather than in how it
// is found. The difference between the scroller's two boxes is the only way to ask — no
// platform states the width, and the window states nothing about a bar drawn inside it.
// Constant through a panel's slide, both boxes moving with the margin together, and
// invariant under the strip veto's own padding, which is inside both. Constant over the
// page's life as well, and that is the stylesheet's doing rather than this line's: the
// rule that makes body the scroller gives it scrollbar-gutter: stable, so the room is
// reserved whether or not a bar is drawn in it and a document that stops overflowing
// keeps it. A caller reading this off a stale occasion is therefore not a way to be
// wrong. Overlay scrollbars are 0, which is why one platform never sees any of this.
export const scrollerGutter = () => pageScroller.offsetWidth - pageScroller.clientWidth;
