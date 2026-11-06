/* Decoration of the canonical current anchor reading.
 *
 * Anchor placement resolves conversations and composition before this optional paint.
 * This instance owns highlights, outlines and pointer hit testing; its marks never
 * supply target existence, surface admission, drawing placement or travel. Its one hit
 * test answers which mark the pointer rests on, for a press (`markAt`) and for the
 * preview owner (`pointMark`).
 */

import { ringBox, visibleFocus } from "../focus.js";
import { shownParts } from "../geometry.js";
import { cancelRender, nextRender } from "../rendering.js";
import {
  readingOrder,
  readingPlace,
  targetElement,
  targetParts,
  targetSegments,
  targetSurface,
} from "../resolved-target.js";
import {
  closestAcross,
  elementFromPointAcross,
  pageWords,
  rangeOf,
} from "../passages.js";
import { presentDocument } from "../semantic-state.js";
import { WORKS } from "../control-selectors.js";
import { bareReaction } from "../thread/model.js";
import { threadNamed } from "../thread/state.js";
import { threadPreview } from "../thread/messages.js";
import { pointRange } from "../preview.js";
import { renderedParent, shadowHost } from "../shadow.js";
import { annotationsHidden } from "./annotation-layer.js";
import { keepsOnOne } from "../keeps.js";
import { RUNTIME_PAINT_ATTRIBUTE } from "../page-paint.js";

const MARK = "lf-mark";
const PENDING = "lf-pending";
const REACT = "lf-react";
const HOVER = "lf-mark-hover";
const HERE = "lf-mark-here";

// A text node's pieces as a centred interval tree: each node holds the pieces covering
// its centre character, sorted by start and by end, with those wholly before and after
// it below. `piecesAt` finds every piece covering a character by one walk down, reading
// only the pieces it finds beside the tree's depth, which grows with the logarithm of
// the pieces the node holds; it is built in the order of the pieces times that.
/** @typedef {{start: number, end: number}} Span */
/** @template {Span} P @typedef {{centre: number, byStart: P[], byEnd: P[],
 * before: PieceTree<P> | null, after: PieceTree<P> | null}} PieceTree */
/** @template {Span} P @param {readonly P[]} pieces sorted by start, none empty
 * @returns {PieceTree<P> | null} */
function treeOf(pieces) {
  const middle = pieces[pieces.length >> 1];
  if (!middle) return null;
  const centre = middle.start;
  /** @type {P[]} */
  const before = [];
  /** @type {P[]} */
  const after = [];
  /** @type {P[]} */
  const here = [];
  for (const piece of pieces)
    (piece.end <= centre ? before : piece.start > centre ? after : here).push(piece);
  return {
    centre,
    byStart: here,
    byEnd: [...here].sort((a, b) => b.end - a.end),
    before: treeOf(before),
    after: treeOf(after),
  };
}
/** @template {Span} P @param {PieceTree<P> | null} tree @param {number} at */
function piecesAt(tree, at) {
  /** @type {P[]} */
  const found = [];
  for (let node = tree; node;) {
    if (at < node.centre) {
      for (const piece of node.byStart) {
        if (piece.start > at) break;
        found.push(piece);
      }
      node = node.before;
    } else {
      for (const piece of node.byEnd) {
        if (piece.end <= at) break;
        found.push(piece);
      }
      node = node.after;
    }
  }
  return found;
}

// `rowThread(under)` names the thread whose row in the floating panel's Threads holds the
// element under the pointer, `threadRow(id)` is the row Threads draws for a thread, and
// `marginThread()` names
// the thread whose margin entry the pointer is on; each is null where there is none.
/** @typedef {Element | Range} Mark */
/** @param {{targetPaint: ReturnType<typeof import("./visual-mark-paint.js").createVisualMarkPaint>,
 * pointer: typeof import("../pointer.js").pointerAt,
 * currentLocationThreadId: () => string | null,
 * currentLocationObligation: () => Element | null,
 * rowThread: (under: Element | null) => string | null, threadRow: (id: string) => Element | null,
 * marginThread: () => string | null,
 * placedAt: ReturnType<typeof import("../anchor-placement.js").createAnchorPlacement>["placedAt"],
 * pendingAt: ReturnType<typeof import("../anchor-placement.js").createAnchorPlacement>["pendingAt"],
 * settle: () => void}} capabilities */
export function createAnchorPaint({
  targetPaint,
  pointer,
  currentLocationThreadId,
  currentLocationObligation,
  rowThread,
  threadRow,
  marginThread,
  placedAt,
  pendingAt,
  settle,
}) {
  /** @type {Map<string, Mark[]>} */
  const marked = new Map();
  // Each marked thread's place in the page's reading order, as the last paint put them.
  /** @type {Map<string, number>} */
  const orderOf = new Map();
  // Where the hit test finds each mark (`markHit`), with its thread's place in reading
  // order: for each text node a passage's segments stand in, the pieces they cover there
  // and, read as the hit test first asks, their tree (`piecesAt`); an element's mark by
  // the element; and the shadow trees holding a passage's text, which the caret lookup
  // looks into. It is read from anchor placement's segments, the one record of where a
  // passage stands, which placement reads again for the anchors a change to the page's
  // words touches (anchor-placement.js, `settle`); the index then reads again only those
  // threads' pieces, in the text nodes they left and the ones they stand in (`replace`).
  /** @typedef {{id: string, where: Mark, order: number}} Findable */
  /** @typedef {Findable & Span & {where: Range}} Piece */
  /** @type {Map<Node, {pieces: Piece[], tree: PieceTree<Piece> | null}>} */
  const inText = new Map();
  // Each passage painted, by its thread: its place in reading order, and the segments
  // and ranges placement gave it.
  /** @typedef {{order: number, segments: readonly import("../passages.js").Segment[], ranges: readonly Range[]}} Painted */
  /** @type {Map<string, Painted>} */
  const passages = new Map();
  /** @type {Map<string, readonly Range[]>} */
  const reacted = new Map();
  // The threads the last paint marks nothing for by their own state: resolved, or
  // drawn rather than marked.
  /** @type {Set<string>} */
  const unmarked = new Set();
  /** @type {Map<Element, Findable[]>} */
  const onElement = new Map();
  /** @type {Set<ShadowRoot>} */
  const markedRoots = new Set();
  /** @type {Map<Element, Element>} */
  const visualTargets = new Map();
  /** @type {Element[]} */
  let pendingOutline = [];
  /** @type {Element[]} */
  let actionOutline = [];
  /** @type {string | null} */
  let hovering = null;
  let hoverFromRow = false;
  /** @type {Element[]} */
  let hoverParts = [];
  /** @type {Element | null} */
  let hoveredRow = null;
  /** @type {Element[]} */
  let hereParts = [];
  let hoverFrame = 0;
  let mounted = false;
  // Whether the hover pass reads the pointer where the user's own input put it, whether
  // it rests there rather than carrying a press, as selecting words does, and whether
  // the preview owner was last told it rests on a thread's words (`pointMark`).
  let aimed = false;
  let resting = false;
  let pointed = false;

  /** @param {string | null} id */
  const marksFor = (id) => (id === null ? [] : (marked.get(id) ?? []));
  /** @param {Iterable<Mark | readonly Mark[]>} where */
  const elementMarks = (where) =>
    [...where].flat().filter((mark) => mark instanceof Element);

  /** @param {Parameters<typeof targetElement>[0]} resolved */
  const rememberVisual = (resolved) => {
    const element = targetElement(resolved);
    const surface = targetSurface(resolved);
    if (element && surface) visualTargets.set(element, surface);
  };

  // An element's threads and reactions draw nothing on it at rest: its margin entry
  // already says it holds them, and a contour means "this, now". Only a moment projects
  // one — a draft, an action, the pointer on the thread's row in Threads, the thread the
  // user is in.
  function paintVisualStates() {
    const pending = new Set(pendingOutline);
    const action = new Set(actionOutline);
    const hover = new Set(elementMarks(hoverParts));
    const here = new Set(elementMarks(hereParts));
    // Paint every element state in the chrome plane. A declared visual substitutes its
    // registered surface so compound pictures keep their contour.
    const elements = new Set(
      [pending, action, hover, here]
        .flatMap((states) => [...states])
        .filter((element) => element instanceof Element),
    );
    // Read focus itself, not attributes a later paint reflects. Escape can return
    // to an element after its draft (and thus its last annotation) has disappeared.
    const active = visibleFocus();
    // Page controls need the same cue whether or not an author gave them an id.
    // Private controls and a face wearing another control's ring keep that paint. An
    // obligation the user arrived at needs none: its location ring (target-paint.js) is
    // its focus cue.
    // Read that owner's current location too: its reflected attribute may still
    // describe the previous location until the mechanical repaint.
    const obligation = currentLocationObligation();
    const obligationRing =
      active &&
      obligation &&
      (active === obligation || shownParts(obligation).includes(active));
    const ownsRing = active && ringBox(active) === active && !obligationRing;
    if (ownsRing && active.getRootNode() === document && pageWords(active))
      elements.add(active);
    const focus = new Set(ownsRing && elements.has(active) ? [active] : []);
    /** @type {[string, Set<Element>][]} */
    const sources = [
      ["pending", pending],
      ["action", action],
      ["hover", hover],
      ["focus", focus],
      ["here", here],
    ];
    targetPaint.setTargets(
      [...elements].map((element) => ({
        element,
        surface: visualTargets.get(element) ?? element,
        states: new Set(
          sources.filter(([, members]) => members.has(element)).map(([state]) => state),
        ),
      })),
    );
  }

  const outlined = () =>
    new Set([...elementMarks(marked.values()), ...pendingOutline, ...actionOutline]);

  // Each element's outline classes follow the current record. Toggling the last pass's
  // elements with this one's writes only the classes that moved.
  /** @param {Set<Element>} before */
  function paintOutlines(before) {
    const marks = new Set(elementMarks(marked.values()));
    const pending = new Set(pendingOutline);
    const action = new Set(actionOutline);
    for (const element of new Set([...before, ...outlined()])) {
      element.classList.toggle(
        "lf-mark-el",
        marks.has(element) || pending.has(element),
      );
      element.classList.toggle(PENDING, pending.has(element));
      element.classList.toggle("lf-action-target", action.has(element));
    }
  }

  // The pointer on a thread's words, or on its row in Threads, lights the words. Its
  // element is lit only from the row: on the page the pointer is inside the element
  // anywhere in it, so the contour would stand round a section for as long as the user
  // read with the mouse resting in it. The hand still says a press opens the thread.
  /** @param {string | null} id @param {boolean} fromRow @param {boolean} [repaintVisuals] */
  function paintHover(id, fromRow, repaintVisuals = true) {
    hovering = id;
    hoverFromRow = fromRow;
    const where = marksFor(id);
    const parts = fromRow ? where.filter((mark) => mark instanceof Element) : [];
    for (const part of hoverParts)
      if (!parts.includes(part)) part.classList.toggle(HOVER, false);
    for (const part of parts) part.classList.toggle(HOVER, true);
    hoverParts = parts;
    CSS.highlights.set(
      HOVER,
      Object.assign(new Highlight(...where.filter((mark) => mark instanceof Range)), {
        priority: 1,
      }),
    );
    if (repaintVisuals) paintVisualStates();
  }

  // The other half of the link: the row of the thread the pointer is on, on its words,
  // its margin entry or the row itself, is marked in Threads while Threads is open. A
  // thread with nothing lit on the page marks no row, so a marked row always has its
  // passage lit.
  /** @param {string | null} id */
  function markRow(id) {
    const row = id && marksFor(id).length ? threadRow(id) : null;
    if (row === hoveredRow) return;
    hoveredRow?.classList.toggle(HOVER, false);
    row?.classList.toggle(HOVER, true);
    hoveredRow = row;
  }

  // Current location follows focus, rather than the last travel (thread/focus.js,
  // `currentLocationThreadId`). Every route into a thread then paints the same fact and leaving
  // it clears the mark without another command path.
  function paintCurrentLocation(repaintVisuals = true) {
    const where = marksFor(currentLocationThreadId());
    const parts = where.filter((mark) => mark instanceof Element);
    for (const part of hereParts)
      if (!parts.includes(part)) part.classList.toggle(HERE, false);
    for (const part of parts) part.classList.toggle(HERE, true);
    hereParts = parts;
    CSS.highlights.set(
      HERE,
      Object.assign(new Highlight(...where.filter((mark) => mark instanceof Range)), {
        priority: 2,
      }),
    );
    if (repaintVisuals) paintVisualStates();
  }

  // Which thread's painted mark lies under a point, and the mark: of those the point
  // lies in, the first thread's in reading order, which a press opens; and every thread
  // marking what that mark marks, the character under the point or the element, in
  // reading order, which the mark previews, as its margin entry does. The element under
  // the point is the platform's hit test (`elementFromPointAcross`), so the chrome over
  // the page's words holds no mark, an image whose element is marked is its mark's, and
  // a point past a marked inline element is not that element's; an element's mark is
  // found by climbing from it. A passage's piece is found by the character under the
  // point: the caret lookup names a text node and an offset, one or two characters'
  // boxes say whether the point is over the one before or after it, and that text
  // node's tree names the pieces covering that character. So a pointer move reads no
  // mark's geometry, and what it reads besides grows only with the threads it finds and
  // the logarithm of the marks the page, a paragraph or one run of words holds (root
  // AGENTS.md, "Responsiveness"): reading the rects of the marks in the element pointed
  // at cost 512 reads at the last of 512 marks in one paragraph, and the platform's own
  // `highlightsFromPoint` walks every range a highlight holds (notes/browser-support.md,
  // "Highlight hit testing"). With the annotation layer hidden there is no mark to be
  // under: an unseen passage shows no hand and opens nothing.
  /** @param {number} x @param {number} y @param {Element | null} [under] the element
   * under the point, where the caller has hit-tested it already
   * @returns {{id: string, where: Mark, alike: readonly Findable[]} | null} */
  function markHit(x, y, under = elementFromPointAcross(x, y)) {
    if (annotationsHidden() || !under || !pageWords(under)) return null;
    // Changes to the page's words not yet placed are placed now, ahead of the reading.
    settle();
    /** @type {Findable[]} */
    let words = [];
    const caret = inText.size
      ? document.caretPositionFromPoint(x, y, { shadowRoots: [...markedRoots] })
      : null;
    const text = caret && inText.get(caret.offsetNode);
    if (caret && text) {
      text.tree ??= treeOf([...text.pieces].sort((a, b) => a.start - b.start));
      for (const at of [caret.offset, caret.offset - 1]) {
        if (at < 0 || !overCharacter(caret.offsetNode, at, x, y)) continue;
        words = piecesAt(text.tree, at);
        break;
      }
    }
    /** @param {readonly Findable[]} marks */
    const first = (marks) =>
      marks.reduce(
        (/** @type {Findable | null} */ least, mark) =>
          !least || mark.order < least.order ? mark : least,
        null,
      );
    let hit = first(words);
    let alike = words;
    for (let at = /** @type {Element | null} */ (under); at; at = renderedParent(at)) {
      const marks = onElement.get(at) ?? [];
      const least = first(marks);
      if (least && (!hit || least.order < hit.order)) {
        hit = least;
        alike = marks;
      }
    }
    return hit && { id: hit.id, where: hit.where, alike };
  }
  // Whether the point lies over the character at `at` in a text node.
  /** @param {Node} node @param {number} at @param {number} x @param {number} y */
  function overCharacter(node, at, x, y) {
    if (at >= (node.textContent?.length ?? 0)) return false;
    const character = document.createRange();
    character.setStart(node, at);
    character.setEnd(node, at + 1);
    return [...character.getClientRects()].some(
      (rect) => x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom,
    );
  }
  /** @param {number} x @param {number} y */
  const markAt = (x, y) => markHit(x, y)?.id ?? null;

  // Index the marks where the hit test finds them (`inText`, `onElement`).
  function index() {
    inText.clear();
    onElement.clear();
    markedRoots.clear();
    for (const [id, marks] of marked) {
      const order = orderOf.get(id) ?? 0;
      const passage = passages.get(id);
      if (passage) indexPassage(id, passage);
      else
        for (const where of marks) {
          if (where instanceof Range) continue;
          const standing = onElement.get(where) ?? [];
          standing.push({ id, where, order });
          onElement.set(where, standing);
        }
    }
  }
  // A passage's pieces, one in the text node each of its segments stands in, and the
  // shadow trees holding them, every level of them, which the caret lookup must look
  // into to land inside them.
  /** @param {string} id @param {Painted} passage */
  function indexPassage(id, { order, segments, ranges }) {
    segments.forEach((segment, at) => {
      const where = ranges[at];
      if (!where || segment.end <= segment.start) return;
      const text = inText.get(segment.node) ?? { pieces: [], tree: null };
      text.pieces.push({ id, where, order, start: segment.start, end: segment.end });
      text.tree = null;
      inText.set(segment.node, text);
      for (let root = segment.node.getRootNode(); root instanceof ShadowRoot;) {
        markedRoots.add(root);
        root = shadowHost(root)?.getRootNode() ?? document;
      }
    });
  }
  // The draft's marks: its passage's words, or the element it stands on, unless the
  // draft draws (`draftDraws`) or its anchor stands on an outdated datum.
  let draftDraws = false;
  /** @param {ReturnType<typeof pendingAt>} resolved */
  function paintPending(resolved) {
    const marked = Boolean(resolved && resolved.status !== "outdated") && !draftDraws;
    pendingOutline = marked && targetElement(resolved) ? targetParts(resolved) : [];
    const ranges = marked
      ? targetSegments(resolved).map(
          /** @param {Parameters<typeof rangeOf>[0][number]} segment */ (segment) =>
            rangeOf([segment]),
        )
      : [];
    if (resolved) rememberVisual(resolved);
    CSS.highlights.set(
      PENDING,
      Object.assign(new Highlight(...ranges), { priority: 3 }),
    );
  }
  // Placement read again the threads `ids` a change to the page's words touched
  // (anchor-placement.js, `settle`): their passages' marks are its new ranges, painted
  // in place of the old ones, and the index reads again only the text nodes they left
  // and stand in, each once, however many of their pieces it holds. A thread whose
  // anchor now stands on an element, or on nothing it marks, is painted again whole, and
  // so is one placed where the last paint marked nothing for it and chose not to mark it
  // for nothing, as a resolved thread, since only a paint of the page knows where it
  // falls among the marks.
  /** @param {import("../anchor-placement.js").Placed} placed */
  function replace({ threads: ids, pending }) {
    if (pending) {
      const before = outlined();
      paintPending(pendingAt());
      paintOutlines(before);
      paintVisualStates();
    }
    const arrived = ids.some((id) => {
      if (passages.has(id) || reacted.has(id) || unmarked.has(id)) return false;
      const found = placedAt(id);
      return Boolean(found && found.status !== "outdated");
    });
    if (arrived) return void presentDocument();
    const affected = new Set(ids.filter((id) => passages.has(id) || reacted.has(id)));
    if (!affected.size) return;
    const mark = CSS.highlights.get(MARK);
    const react = CSS.highlights.get(REACT);
    /** @type {Set<Node>} */
    const nodes = new Set();
    let whole = false;
    for (const id of affected) {
      const found = placedAt(id);
      const segments = targetSegments(found);
      const ranges =
        found?.kind === "passage" && found.status !== "outdated" ? found.ranges : null;
      const was = reacted.get(id);
      if (was) {
        for (const range of was) react?.delete(range);
        reacted.set(id, ranges ?? []);
        for (const range of ranges ?? []) react?.add(range);
        continue;
      }
      const old = /** @type {Painted} */ (passages.get(id));
      for (const segment of old.segments) nodes.add(segment.node);
      for (const range of old.ranges) mark?.delete(range);
      if (!found || !ranges) {
        passages.delete(id);
        marked.delete(id);
        whole ||= Boolean(found && targetElement(found));
        continue;
      }
      passages.set(id, { order: old.order, segments, ranges });
      marked.set(id, [...ranges]);
      for (const range of ranges) mark?.add(range);
      for (const segment of segments) nodes.add(segment.node);
    }
    if (whole) return void presentDocument();
    for (const node of nodes) {
      const text = inText.get(node);
      if (!text) continue;
      text.pieces = text.pieces.filter((piece) => !affected.has(piece.id));
      text.tree = null;
      if (!text.pieces.length) inText.delete(node);
    }
    for (const id of affected) {
      const passage = passages.get(id);
      if (passage) indexPassage(id, passage);
    }
    if (hovering && affected.has(hovering)) paintHover(hovering, hoverFromRow, false);
    paintCurrentLocation(false);
    paintVisualStates();
    refreshHover();
  }

  // A thread's mark previews the thread, as its margin entry does (`threadPreview`),
  // from the one hit a press reads too (`markHit`), on a passage's words and on an
  // element's mark alike, wherever the hand stands. The preview owner hears only where
  // the user's own input put the pointer, so a mark a scroll or a repaint carries under
  // a still pointer shows nothing, as the owner holds for elements, and a pointer
  // carrying a press, as in selecting words, rests on no mark.
  // The owner is told the piece the preview stands by: the passage's segment, or the
  // element marked, the pointer came onto the thread's marks over, held while it stays
  // on them, so the preview stands once by the line first pointed at as the pointer
  // crosses the pieces an inline element or a shadow root splits a passage into
  // (preview.js, `pointRange`). One range from the first piece to the last collapsed
  // where a passage ran into a shadow tree (passages.js, `rangeOf`). The owner reads a
  // standing preview again each time it is told its range, so it is told again only
  // when the threads under the pointer change: telling it on each move drew 512
  // threads' lines on every move over a word 512 threads mark.
  /** @type {{id: string, where: Mark, piece: Range} | null} */
  let standing = null;
  /** @type {Set<string> | null} */
  let told = null;
  /** @param {{id: string, where: Mark, alike: readonly Findable[]} | null} hit
   * @param {{x: number, y: number}} at */
  function pointMark(hit, at) {
    const id = resting && hit ? hit.id : null;
    if (!hit || !id) {
      standing = null;
      told = null;
      pointed = false;
      return void pointRange(null);
    }
    if (standing?.id !== id || !marksFor(id).includes(standing.where)) {
      const { where } = hit;
      const piece = where instanceof Range ? where : document.createRange();
      if (!(where instanceof Range)) piece.selectNode(where);
      standing = { id, where, piece };
      told = null;
    }
    pointed = true;
    const { alike } = hit;
    if (told?.size === alike.length && alike.every((mark) => told?.has(mark.id)))
      return;
    told = new Set(alike.map((mark) => mark.id));
    // A thread the user is in is in front of them already, as an entry standing open
    // previews nothing (preview.js). The threads are put in reading order as the
    // preview reads them.
    const { piece } = standing;
    pointRange(
      piece,
      () => {
        const here = currentLocationThreadId();
        if (here && alike.some((mark) => mark.id === here)) return null;
        return threadPreview(
          [...alike]
            .sort((a, b) => a.order - b.order)
            .flatMap((mark) => threadNamed(mark.id) ?? []),
        );
      },
      at,
    );
  }
  // The user moved the pointer, or pressed a finger, which may rest on a mark.
  /** @param {PointerEvent} event */
  function pointerAimed(event) {
    aimed = true;
    resting = event.pointerType === "touch" || !event.buttons;
    // A press is a new input the owner reads afresh, as a finger's hold after one it
    // let go of or cancelled, even where it lands on the threads it was last told.
    if (event.type === "pointerdown") told = null;
    refreshHover();
  }

  // The hand over a mark is a paint on the document's element under the pointer (a
  // shadow tree's host, whose cursor its tree inherits), which the margin's page
  // observer does not hear (page-paint.js) and whose cursor reaches only what it holds.
  // A class on `body` ran a margin pass at each change and restyled the whole body. It
  // stands only where a press opens the thread: a control or editing region keeps its
  // own press there (composing/surface.js, the page's click), and so its own cursor.
  const paintHand = keepsOnOne(RUNTIME_PAINT_ATTRIBUTE.overMark);

  // Hover reads the pointer, and the rows and margin entries it is on, inside the
  // scheduled frame. Capturing a node at event time would leave reconciliation able to
  // replace it before paint. The frame asks first where the marks stand, so a change to
  // the page's words placement has yet to place, which may have made the page's only
  // mark or taken it, is placed before the hover reads them, once a frame however many
  // moves it holds.
  function refreshHover() {
    if (hoverFrame) return;
    hoverFrame = nextRender(() => {
      hoverFrame = 0;
      settle();
      if (!marked.size && !hovering && !hoveredRow && !pointed) return;
      const at = pointer();
      const under = elementFromPointAcross(at.x, at.y);
      const hit = markHit(at.x, at.y, under);
      const onMark = hit?.id ?? null;
      if (aimed) pointMark(hit, at);
      aimed = false;
      const presses = onMark && !closestAcross(under, WORKS);
      paintHand(presses ? document.elementFromPoint(at.x, at.y) : null);
      const row = rowThread(under);
      const id = row ?? onMark;
      if (id !== hovering || Boolean(row) !== hoverFromRow)
        paintHover(id, Boolean(row));
      markRow(id ?? marginThread());
    });
  }

  // Whether a thread's element marks are the elements this pass would mark.
  /** @param {readonly Mark[]} marks @param {readonly Element[]} parts */
  const sameParts = (marks, parts) =>
    marks.length === parts.length && marks.every((mark, at) => mark === parts[at]);

  // A passage's marks are the live ranges anchor placement keeps of it, the one record
  // of where it is (resolved-target.js, `targetSegments`), which a reading that moves
  // nothing keeps; an element's are its parts, kept while they are the same elements.
  // So a presentation that changes no mark keeps its ranges, the index of them (`index`)
  // and the highlight painting them as they stand, and the hover stays bound to them;
  // only a pass that changes a mark, or the order of the threads marked, builds them
  // again.
  /** @param {NonNullable<ReturnType<ReturnType<typeof import("../anchor-placement.js").createAnchorPlacement>["read"]>>} reading */
  function paint({ readings, draft, action }) {
    const before = outlined();
    const last = new Map(marked);
    marked.clear();
    passages.clear();
    reacted.clear();
    unmarked.clear();
    orderOf.clear();
    pendingOutline = [];
    actionOutline = [];
    visualTargets.clear();

    const posted = [];
    const reactions = [];

    // In the page's reading order, as the margin lists its entries, which names the
    // thread a press on overlapping passages opens and the order a mark's preview lists
    // them in (resolved-target.js, `readingOrder`).
    const inOrder = [...readings].sort((left, right) =>
      readingOrder(readingPlace(left.placement), readingPlace(right.placement)),
    );
    for (const { thread, placement: found } of inOrder) {
      if (thread.resolved || thread.root.drawing) unmarked.add(thread.id);
      if (found.status === "outdated" || thread.resolved) continue;

      const ranges = found.kind === "passage" ? (found.ranges ?? []) : [];
      if (bareReaction(thread)) {
        reacted.set(thread.id, ranges);
        reactions.push(...ranges);
        continue;
      }

      const kept = last.get(thread.id);
      orderOf.set(thread.id, orderOf.size);
      if (targetElement(found)) {
        rememberVisual(found);
        if (!thread.root.drawing) {
          const parts = targetParts(found);
          marked.set(thread.id, kept && sameParts(kept, parts) ? kept : parts);
        }
      } else if (!thread.root.drawing && found.kind === "passage") {
        const order = orderOf.get(thread.id) ?? 0;
        passages.set(thread.id, { order, segments: targetSegments(found), ranges });
        marked.set(
          thread.id,
          kept?.length === ranges.length &&
            kept.every((mark, at) => mark === ranges[at])
            ? kept
            : [...ranges],
        );
        posted.push(...ranges);
      }
    }
    const order = [...last.keys()];
    const remarked =
      marked.size !== last.size ||
      [...marked].some(([id, marks], at) => order[at] !== id || last.get(id) !== marks);
    if (remarked) index();
    draftDraws = Boolean(draft.drawing);
    paintPending(draft.resolved);

    actionOutline = targetElement(action) ? targetParts(action) : [];
    if (action) rememberVisual(action);
    paintOutlines(before);

    if (remarked) CSS.highlights.set(MARK, new Highlight(...posted));
    CSS.highlights.set(REACT, new Highlight(...reactions));
    paintCurrentLocation(false);
    // A pass that made new marks rebinds the hover to them even when the semantic id
    // did not change, then updates the shared visual projection once.
    if (remarked && hovering) paintHover(hovering, hoverFromRow, false);
    paintVisualStates();
    refreshHover();
  }

  function mount() {
    if (mounted) return;
    mounted = true;
    document.addEventListener("pointermove", pointerAimed);
    document.addEventListener("pointerdown", pointerAimed);
  }

  function destroy() {
    if (mounted) {
      document.removeEventListener("pointermove", pointerAimed);
      document.removeEventListener("pointerdown", pointerAimed);
    }

    mounted = false;
    if (pointed) pointRange(null);
    pointed = false;
    standing = null;
    told = null;
    if (hoverFrame) cancelRender(hoverFrame);
    hoverFrame = 0;
    paintHand(null);
    const before = outlined();
    marked.clear();
    passages.clear();
    reacted.clear();
    unmarked.clear();
    index();
    pendingOutline = [];
    actionOutline = [];
    paintOutlines(before);
    for (const element of hereParts) element.classList.toggle(HERE, false);
    for (const element of [...hoverParts, hoveredRow])
      element?.classList.toggle(HOVER, false);
    for (const name of [MARK, REACT, PENDING, HOVER, HERE]) CSS.highlights.delete(name);
    targetPaint.setTargets([]);
    visualTargets.clear();
    hovering = null;
    hoverFromRow = false;
    hoverParts = [];
    hoveredRow = null;
    hereParts = [];
  }

  return {
    mount,
    destroy,
    paint,
    replace,
    paintCurrentLocation,
    refreshHover,
    markAt,
    marksFor,
  };
}
