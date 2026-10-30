/* Native selection endpoints and the provenance of programmatic writes. Passage
 * capture, view restoration and control activation share the same composed range;
 * none reads Chromium's retargeted light-DOM endpoints as the selected words. */
import { pageShadowRoots } from "./shadow.js";

// The range the user actually drew. Chrome keeps the legacy Range in the light DOM: a
// drag wholly inside a widget's shadow tree comes back with `commonAncestorContainer` at
// BODY and its ends clamped to the host, so `sel.toString()` says the right words while
// every node the capture would index says the wrong place. That is the one failure mode
// worth naming twice — not a refusal, which the fence rule turns into a message to the
// author, but a quote anchored somewhere the user never pointed.
//
// `getComposedRanges` is the only thing that answers truthfully, and it answers only for
// the roots it is handed, which is why the declaration (x-shadow) and not a sweep decides
// what is passed. A selection that starts in one tree and ends in another is left to the
// light-DOM range on purpose: a Range cannot hold ends in two roots, and a quote running
// from the page's prose into a widget's shadow is exactly what the fences already refuse.
export function pageRange(sel) {
  const plain = sel.getRangeAt(0);
  const shadowRoots = pageShadowRoots();
  if (!shadowRoots.length) return plain;
  const [composed] = sel.getComposedRanges({ shadowRoots });
  const { startContainer, startOffset, endContainer, endOffset } = composed;
  if (startContainer.getRootNode() !== endContainer.getRootNode()) return plain;
  const range = document.createRange();
  range.setStart(startContainer, startOffset);
  range.setEnd(endContainer, endOffset);
  return range;
}

// Native page selections share one endpoint writer, including their provenance.
// Native selectionchange arrives asynchronously, so its endpoints say whether it is
// still the programmatic write or a later user adjustment (including touch handles).
let writtenSelection = null;
let writtenBackward = false;
// Each end is a boundary point, `[node, offset]`.
export function selectEnds(anchor, focus) {
  const selection = getSelection();
  const from = document.createRange(),
    to = document.createRange();
  from.setStart(.../** @type {[Node, number]} */ (anchor));
  to.setStart(.../** @type {[Node, number]} */ (focus));
  writtenBackward = from.compareBoundaryPoints(Range.START_TO_START, to) > 0;
  selection.setBaseAndExtent(
    .../** @type {[Node, number]} */ (anchor),
    .../** @type {[Node, number]} */ (focus),
  );
  writtenSelection = selectionEnds(selection);
}
const selectionEnds = (selection) => {
  const range = selection.rangeCount ? pageRange(selection) : null;
  return [
    selection.anchorNode,
    selection.anchorOffset,
    selection.focusNode,
    selection.focusOffset,
    range?.startContainer,
    range?.startOffset,
    range?.endContainer,
    range?.endOffset,
  ];
};
export function programmaticSelection(selection) {
  if (!writtenSelection) return false;
  if (selectionEnds(selection).every((end, i) => end === writtenSelection[i]))
    return true;
  writtenSelection = null;
  return false;
}

// Boundary points retain the working end even where the platform reports "none"
// after setBaseAndExtent. A composed selection clamped in light DOM instead uses
// the platform's direction for the range inside its declared shadow tree.
export function selectionBackward(selection, range = pageRange(selection)) {
  if (
    selection.anchorNode.getRootNode() !== range.commonAncestorContainer.getRootNode()
  )
    return programmaticSelection(selection)
      ? writtenBackward
      : selection.direction === "backward";
  const probe = document.createRange();
  probe.setStart(selection.anchorNode, selection.anchorOffset);
  return probe.compareBoundaryPoints(Range.START_TO_START, range) > 0;
}
