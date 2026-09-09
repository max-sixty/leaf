/* Focus placement for destinations that may not already be tab stops. */

// Put the reader on an element that may not be a tab stop: focus it, and where it will
// not take focus, lend it the tab stop a control has for exactly as long as it holds it —
// the lend leaves with the first blur, so a paragraph the address sequence landed on is a
// paragraph again once the reader moves off it, and `tabindex` never becomes a thing the
// runtime leaves behind on an author's element. An element that already declares a stop
// keeps its own. Four arrivals want this and none owns the element: a go-to hint
// completing on a fold, a heading or a link's fragment; a document swap handing back the
// place the reader stood in; the reference handing a reader back to the block they were
// reading; and the skip link landing on the banner when none of its controls will take
// them. Each is "the reader is now here", and each needs the browser's sequential focus
// navigation starting point to move with them, which is what `focus()` does and what
// nothing else does.
export function focusDestination(destination) {
  destination.focus({ preventScroll: true });
  if (destination.matches(":focus")) return;
  if (destination.hasAttribute("tabindex")) return;
  destination.tabIndex = -1;
  destination.focus({ preventScroll: true });
  if (!destination.matches(":focus")) {
    destination.removeAttribute("tabindex");
    return;
  }
  destination.addEventListener("blur", () => destination.removeAttribute("tabindex"), {
    once: true,
  });
}
