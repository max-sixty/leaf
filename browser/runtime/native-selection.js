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
/** @param {Selection} sel */
export function pageRange(sel) {
  const plain = sel.getRangeAt(0);
  const shadowRoots = pageShadowRoots();
  if (!shadowRoots.length) return plain;
  const [composed] = sel.getComposedRanges({ shadowRoots });
  if (!composed) return plain;
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
/** @type {ReturnType<typeof selectionEnds> | null} */
let writtenSelection = null;
let writtenBackward = false;
// Each end is a boundary point, `[node, offset]`.
/** @typedef {[node: Node, offset: number]} SelectionEnd */
/** @param {SelectionEnd} anchor @param {SelectionEnd} focus */
export function selectEnds(anchor, focus) {
  const selection = getSelection();
  if (!selection) return;
  const from = document.createRange(),
    to = document.createRange();
  from.setStart(...anchor);
  to.setStart(...focus);
  writtenBackward = from.compareBoundaryPoints(Range.START_TO_START, to) > 0;
  selection.setBaseAndExtent(...anchor, ...focus);
  writtenSelection = selectionEnds(selection);
}
/** @param {Selection} selection */
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

// The page selection where moving `placed` would reset it, and what puts it back.
// Moving a node resets any live range with an end inside it, `moveBefore` included,
// as the DOM's move algorithm runs the live range pre-remove steps. So a selection
// with an end inside one of the nodes about to move is read before they move, and its
// ends go back through `selectEnds` once both stand again. An end inside a shadow tree
// lies outside every placed node, and stays its editor's to keep (`connectedMoveCallback`).
/** @param {Iterable<Node>} placed @returns {(() => void) | null} */
export function holdSelection(placed) {
  // The selection's ends stand in the document, so only a connected node can hold one.
  // Reading the selection lays the page out in Chromium, so a placement of nodes not yet
  // in the document, as a renderer's first paint makes, does not read it: a first paint
  // per widget would otherwise lay out the whole page once per widget.
  const moving = new Set([...placed].filter((node) => node.isConnected));
  if (!moving.size) return null;
  const selection = getSelection();
  if (!selection?.rangeCount) return null;
  const { anchorNode, anchorOffset, focusNode, focusOffset } = selection;
  if (!anchorNode || !focusNode) return null;
  /** @param {Node} node */
  const inside = (node) => {
    for (let at = /** @type {Node | null} */ (node); at; at = at.parentNode)
      if (moving.has(at)) return true;
    return false;
  };
  if (!inside(anchorNode) && !inside(focusNode)) return null;
  /** @param {Node} node @param {number} offset */
  const stands = (node, offset) =>
    node.isConnected &&
    offset <= (node instanceof CharacterData ? node.length : node.childNodes.length);
  return () => {
    const kept =
      selection.anchorNode === anchorNode &&
      selection.anchorOffset === anchorOffset &&
      selection.focusNode === focusNode &&
      selection.focusOffset === focusOffset;
    if (kept || !stands(anchorNode, anchorOffset) || !stands(focusNode, focusOffset))
      return;
    selectEnds([anchorNode, anchorOffset], [focusNode, focusOffset]);
  };
}

/** @param {Selection | null} selection */
export function programmaticSelection(selection) {
  if (!selection) {
    writtenSelection = null;
    return false;
  }
  const written = writtenSelection;
  if (!written) return false;
  if (selectionEnds(selection).every((end, i) => end === written[i])) return true;
  writtenSelection = null;
  return false;
}

// Boundary points retain the working end even where the platform reports "none"
// after setBaseAndExtent. A composed selection clamped in light DOM instead uses
// the platform's direction for the range inside its declared shadow tree.
/** @param {Selection} selection @param {Range} range */
export function selectionBackward(selection, range = pageRange(selection)) {
  const anchor = selection.anchorNode;
  if (!anchor) return false;
  if (anchor.getRootNode() !== range.commonAncestorContainer.getRootNode())
    return programmaticSelection(selection)
      ? writtenBackward
      : selection.direction === "backward";
  const probe = document.createRange();
  probe.setStart(anchor, selection.anchorOffset);
  return probe.compareBoundaryPoints(Range.START_TO_START, range) > 0;
}
