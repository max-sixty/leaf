/* Native selection endpoints and the provenance of programmatic writes. Passage
 * capture, view restoration and control activation share the same composed range;
 * none reads Chromium's retargeted light-DOM endpoints as the selected words. */
import { declaredRoot } from "./shadow.js";
import { holdingElement, isElement, isText } from "../lib/shadow-tree.js";

// The range the user actually drew. Chrome keeps the legacy Range in the light DOM: a
// drag wholly inside a widget's shadow tree comes back with `commonAncestorContainer` at
// BODY and its ends clamped to the host, so `sel.toString()` says the right words while
// every node the capture would index says the wrong place. That is the one failure mode
// worth naming twice — not a refusal, which the fence rule turns into a message to the
// author, but a quote anchored somewhere the user never pointed.
//
// `getComposedRanges` is the only thing that answers truthfully, and it answers only
// for the roots it is handed, which is why the declaration (`shadow`) and not a
// sweep decides what is passed. An end in any other root moves out to its host's edge,
// past the host where the selection ends, as the page's reading reads that host by its
// light children: a drag from prose into a typeset formula (readings/formulas.js) takes the
// whole formula. Firefox's legacy Range is wrong there: a drag across a formula came
// back holding only the words after it. A caret in such a root moves out as a range
// round its host, so it is collapsed again: as a range it read as words the user had
// selected, and a click on a formula in a label opened a comment rather than pressing
// the label. A selection that starts in one tree and ends in another is left to the
// light-DOM range on purpose: a Range cannot hold ends in two roots, and a quote
// running from the page's prose into a widget's shadow is exactly what the fences
// already refuse.
//
// The roots handed over are the declared ones whose hosts stand in the document's tree,
// and of those only the roots the selection's ends stand in, which the platform names
// by the hosts it moves the ends out to when handed none (`declaredRootAt`). So the
// capture, which runs on every key, wheel step and press, costs two answers from the
// platform however many stages the page holds.
export function pageRange(sel: Selection) {
  const plain = sel.getRangeAt(0);
  const [outer] = sel.getComposedRanges({ shadowRoots: [] });
  if (!outer) return plain;
  const shadowRoots = [
    ...new Set([
      declaredRootAt(outer.startContainer, outer.startOffset, false),
      declaredRootAt(outer.endContainer, outer.endOffset, true),
    ]),
  ].filter((root) => root !== null);
  const [composed] = shadowRoots.length
    ? sel.getComposedRanges({ shadowRoots })
    : [outer];
  if (!composed) return plain;
  const { startContainer, startOffset, endContainer, endOffset } = composed;
  if (startContainer.getRootNode() !== endContainer.getRootNode()) return plain;
  const range = document.createRange();
  range.setStart(startContainer, startOffset);
  range.setEnd(endContainer, endOffset);
  if (sel.type === "Caret") range.collapse(true);
  return range;
}

// The element a boundary point stands against, which is where the platform leaves a
// selection's end in a root it was not handed: a start just before the root's host, and
// an end just after it.
const edgeAt = (node: Node, offset: number, end: boolean) => {
  const edge = isText(node) ? null : node.childNodes[end ? offset - 1 : offset];
  return isElement(edge) ? edge : null;
};
// The declared root the platform moved such a point out of, or null.
const declaredRootAt = (node: Node, offset: number, end: boolean) => {
  const host = edgeAt(node, offset, end);
  return host && declaredRoot(host);
};

// Where the user's caret stands, or null with no selection. The caret is the
// selection's moving end, wherever a click, caret browsing or Shift and an arrow put it
// (`selectionBackward` says which end that is). The answer is its boundary point,
// `node` and `offset`, the element holding it, `element`, and the letter it stands
// before, `letter`. That element is the text's parent, a shadow root's host, or, for a
// point between an element's children, that element. The letter is the first one after
// the point in its text that draws (`UNDRAWN`), or the last one at the text's end, and
// null at a point between elements; a reader that keeps the caret in place, or asks
// whether the user sees it, reads that letter. Each reader of the caret decides for
// itself whether the caret counts where it stands, as inside what focus is on, in a
// thread or on screen. A reader of the selected words asks `pageRange` instead.
//
// The point is where the page draws the caret, however deep in open shadow trees, so a
// caret in an age's words stands in the age's own text in every engine, where the
// selection's own `focusNode` names a node beside the age in Chromium. The platform
// names an end inside a shadow tree only once it is handed that tree's root
// (`getComposedRanges`). Otherwise it moves the start out before the host holding it
// and the end past that host, so a caret there comes back as a range round the host. So
// each host found at the moving end has its root handed over in turn, once for each
// level of nesting, and an end that stays at the edge once the host's root is handed
// over stands beside the host, not in it. Every open root counts, declared or not,
// since this asks where the caret is drawn, as a pointer's composed path does. A caret
// inside a closed root stays at its host's edge, so its element is the host's container.
export function userCaret(): {
  node: Node;
  offset: number;
  element: Element | null;
  letter: Range | null;
} | null {
  const sel = getSelection();
  if (!sel?.rangeCount) return null;
  const forward = !selectionBackward(sel);
  const shadowRoots: ShadowRoot[] = [];
  for (;;) {
    const [range] = sel.getComposedRanges({ shadowRoots });
    if (!range) return null;
    const node = forward ? range.endContainer : range.startContainer;
    const offset = forward ? range.endOffset : range.startOffset;
    const root = edgeAt(node, offset, forward)?.shadowRoot ?? null;
    if (!root || shadowRoots.includes(root))
      return {
        node,
        offset,
        element: holdingElement(node),
        letter: letterAt(node, offset),
      };
    shadowRoots.push(root);
  }
}
// Characters that draw nothing, so a letter made of one has no box to measure or keep:
// the zero-width space, the joiners, the word joiner and the zero-width no-break space
// that leads an age's words (age.js).
const UNDRAWN = /[\u200b-\u200d\u2060\ufeff]/;
function letterAt(node: Node, offset: number) {
  if (!isText(node) || !node.length) return null;
  let from = Math.min(offset, node.length - 1);
  while (from < node.length - 1 && UNDRAWN.test(node.data.charAt(from))) from += 1;
  const letter = document.createRange();
  letter.setStart(node, from);
  letter.setEnd(node, from + 1);
  return letter;
}

// Native page selections share one endpoint writer, including their provenance.
// Native selectionchange arrives asynchronously, so its endpoints say whether it is
// still the programmatic write or a later user adjustment (including touch handles).
let writtenSelection: ReturnType<typeof selectionEnds> | null = null;
let writtenBackward = false;
// Each end is a boundary point, `[node, offset]`.
export type SelectionEnd = [node: Node, offset: number];
// Its ends may stand in different trees, as a passage's run from the page into a
// shadow stage, which the selection holds as one composed range and the platform orders
// (`direction`), where comparing them as two ranges' bounds throws.
export function selectEnds(anchor: SelectionEnd, focus: SelectionEnd) {
  const selection = getSelection();
  if (!selection) return;
  selection.setBaseAndExtent(...anchor, ...focus);
  writtenBackward = selection.direction === "backward";
  writtenSelection = selectionEnds(selection);
}
// The selection's ends as the platform holds them and as the composed range reads them,
// so two selections compare equal only where they hold the same words.
export const selectionEnds = (selection: Selection) => {
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
export function holdSelection(placed: Iterable<Node>): (() => void) | null {
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
  const inside = (node: Node) => {
    for (let at = node as Node | null; at; at = at.parentNode)
      if (moving.has(at)) return true;
    return false;
  };
  if (!inside(anchorNode) && !inside(focusNode)) return null;
  const stands = (node: Node, offset: number) =>
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

export function programmaticSelection(selection: Selection | null) {
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

// Whether the selection's moving end is its start. Where the platform reports a
// direction, as every engine does for a selection the keyboard or setBaseAndExtent
// made, the direction answers, since the legacy anchor can stand at the wrong end: a
// selection from inside an age to the words after it can report its anchor at the far
// end, in Chromium and Firefox alike. Where the platform reports "none", as Chromium and WebKit
// do on macOS for every selection a mouse makes, the anchor's place against the
// composed range's start answers, and an anchor in another tree than the range keeps
// the direction Leaf's own write recorded.
export function selectionBackward(
  selection: Selection,
  range: Range = pageRange(selection),
) {
  if (selection.direction !== "none") return selection.direction === "backward";
  const anchor = selection.anchorNode;
  if (!anchor) return false;
  if (anchor.getRootNode() !== range.commonAncestorContainer.getRootNode())
    return programmaticSelection(selection) && writtenBackward;
  const probe = document.createRange();
  probe.setStart(anchor, selection.anchorOffset);
  return probe.compareBoundaryPoints(Range.START_TO_START, range) > 0;
}
