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

const TYPED_TYPES = new Set([
  "text",
  "search",
  "url",
  "tel",
  "email",
  "password",
  "number",
  "date",
  "time",
  "datetime-local",
  "month",
  "week",
]);

export function takesLetters(node) {
  return (
    Boolean(node) &&
    (node.tagName === "TEXTAREA" ||
      node.tagName === "SELECT" ||
      node.isContentEditable ||
      (node.tagName === "INPUT" && TYPED_TYPES.has(node.type)))
  );
}

// Letting go of what the reader is standing on. One act at both ends of the ladder, and
// one line of code, because standing on an Ask out on the page and standing on a banner
// button are the same state — the reader holding something — reached from either side of
// the chrome. What the two rungs do not share is the word, and neither word is the other's:
// leaving the chrome names where the reader lands, since that is the whole of what the
// rung is for, and letting go of an Ask names the act, since they were on the page all
// along.
//
// Focus rather than blur, because the two differ in what Space does next: a focused
// control owns the key, while body hands it back to the browser's root scrollport. A blur
// names no deliberate destination even when activeElement subsequently reads as body.
//
// Body therefore needs to be somewhere a reader can be put even on a short page. The
// explicit tab stop is programmatic only and gives every Escape handoff the same stable
// page destination without adding a visible stop to the Tab order.
document.body.tabIndex = -1;

export function letGo() {
  return document.body.focus({ preventScroll: true });
}
