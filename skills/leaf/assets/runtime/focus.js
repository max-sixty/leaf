/* Putting the reader on an element: the focus, and the caret inside it. */

// Put the reader on an element that may not be a tab stop: focus it, and where it will
// not take focus, lend it the tab stop a control has for exactly as long as it holds it —
// the lend leaves with the first blur, so a paragraph the Go-to sequence landed on is a
// paragraph again once the reader moves off it, and `tabindex` never becomes a thing the
// runtime leaves behind on an author's element. An element that already declares a stop
// keeps its own. What wants this is an arrival at an element nobody owns — a go-to hint
// completing on a fold, a heading or a link's fragment; the reference handing a reader
// back to the block they were reading; the skip link landing on the banner when none of
// its controls will take them. Each is "the reader is now here", and each needs the
// browser's sequential focus navigation starting point to move with them, which is what
// `focus()` does and what nothing else does.
//
// A caret is where the reader is inside the element they are on, so it arrives with them.
// An arrival that is a return — a bar moved between two parents, a seat re-rendered, a
// thread reconciled, a replaced document handing back the place the reader stood in —
// reads the caret with `readCaret` before its element goes away and passes it here, so
// that the focus and the place inside it land in one act rather than in two. Passing no
// caret leaves the platform's, which is what a first arrival wants.
export function focusDestination(destination, caret = null) {
  destination.focus({ preventScroll: true });
  if (!destination.matches(":focus")) lendStop(destination);
  if (caret && holdsCaret(destination)) destination.setSelectionRange(...caret);
}

function lendStop(destination) {
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

// The input types whose selection the platform will answer for. Reading `selectionStart`
// on any other throws rather than returning null.
const CARETED = new Set(["text", "search", "url", "tel", "password"]);
const holdsCaret = (node) =>
  node.tagName === "TEXTAREA" || (node.tagName === "INPUT" && CARETED.has(node.type));

// Where the reader is inside an element, or null where the element holds no caret. The
// reading is a plain triple so that it can be stored and read back in another document.
export function readCaret(node) {
  if (!node || !holdsCaret(node) || node.selectionStart === null) return null;
  return [node.selectionStart, node.selectionEnd, node.selectionDirection];
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

// Landing the reader in the document. One act at both ends of the ladder, and for every
// step that would otherwise leave them on Leaf's own apparatus, because standing on an
// Ask out on the page and standing on a banner button are the same state — the reader
// holding something — reached from either side of the chrome. What those rungs do not
// share is the word, and neither word is the other's: leaving the chrome names where the
// reader lands, since that is the whole of what the rung is for, and letting go of an Ask
// names the act, since they were on the page all along.
//
// Where they land is the block they are reading, which is a reading of the current scroll
// rather than a place remembered from before the press: a surface closing moves the page
// under them, and what they can see when it has gone is the answer. Nothing is stored, so
// no revision, repaint or reflow can strand it.
//
// Focus and then blur, which is the pair and not either half. The focus moves the
// browser's sequential focus navigation starting point to the block, so the reader's next
// Tab carries on from what they are reading rather than from the top of the document,
// which is where `document.body.focus()` puts it. The blur hands Space, PageDown, arrows,
// Home and End back to the page's own scroll box, which a focused block would keep.
//
// `releaseFocus` is the other half of the pair and the top of the document is the point of
// it: a page that has just arrived is not a page anybody has read yet, so its first Tab
// belongs at the skip link rather than part-way through the prose that happens to be on
// screen. It is also the fallback here, for a viewport holding nothing to land on — a
// tall bounded region, a run of figures — where the honest answer is that the reader has
// no reading position for the browser to continue from.
let readingBlock = () => null;
export function declareReading(read) {
  readingBlock = read;
}
export function releaseFocus() {
  document.body.focus({ preventScroll: true });
}
export function letGo() {
  const block = readingBlock();
  if (!block?.isConnected) {
    releaseFocus();
    return;
  }
  focusDestination(block);
  block.blur();
}
