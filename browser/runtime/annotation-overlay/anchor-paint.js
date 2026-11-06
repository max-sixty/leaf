/* Decoration of the canonical current anchor reading.
 *
 * Anchor placement resolves conversations and composition before this optional paint.
 * This instance owns highlights, outlines and pointer hit testing; its marks never
 * supply target existence, surface admission, drawing placement or travel. Its hit
 * test tells the preview owner which passage the pointer rests on (`pointMark`).
 */

import { ringBox, visibleFocus } from "../focus.js";
import { shownParts } from "../geometry.js";
import { cancelRender, nextRender } from "../rendering.js";
import {
  targetElement,
  targetParts,
  targetSegments,
  targetSurface,
} from "../resolved-target.js";
import { pageWords, rangeOf } from "../passages.js";
import { bareReaction } from "../thread/model.js";
import { threadNamed } from "../thread/state.js";
import { threadPreview } from "../thread/messages.js";
import { pointRange } from "../preview.js";
import { declaredRoot, renderedParent, shadowHost } from "../shadow.js";
import { isElement } from "../shadow-tree.js";
import { annotationsHidden } from "./annotation-layer.js";
import { keeps } from "../keeps.js";
import { RUNTIME_PAINT_ATTRIBUTE } from "../page-paint.js";

const MARK = "lf-mark";
const PENDING = "lf-pending";
const REACT = "lf-react";
const HOVER = "lf-mark-hover";
const HERE = "lf-mark-here";

// `rowThread()` names the thread whose row in the floating panel's Threads the pointer is
// on, `threadRow(id)` is the row Threads draws for a thread, and `marginThread()` names
// the thread whose margin entry the pointer is on; each is null where there is none.
/** @typedef {Element | Range} Mark */
/** @param {{targetPaint: ReturnType<typeof import("./visual-mark-paint.js").createVisualMarkPaint>,
 * pointer: typeof import("../pointer.js").pointerAt,
 * currentLocationThreadId: () => string | null,
 * currentLocationObligation: () => Element | null,
 * rowThread: () => string | null, threadRow: (id: string) => Element | null,
 * marginThread: () => string | null}} capabilities */
export function createAnchorPaint({
  targetPaint,
  pointer,
  currentLocationThreadId,
  currentLocationObligation,
  rowThread,
  threadRow,
  marginThread,
}) {
  /** @type {Map<string, Mark[]>} */
  const marked = new Map();
  // Where the hit test finds each mark (`markHit`), with its thread's place in reading
  // order: a passage's piece by the text node it lies in, sorted by where it starts there
  // and carrying the furthest end of the pieces up to it (`reach`), so a search back from
  // an offset passes only pieces that may still cover it; an element's mark by the
  // element; and the shadow trees holding any of them, which the caret lookup looks into.
  /** @typedef {{id: string, where: Mark, order: number}} Findable */
  /** @type {Map<Node, (Findable & {start: number, end: number, reach: number})[]>} */
  const inText = new Map();
  /** @type {Map<Element, Findable[]>} */
  const onElement = new Map();
  /** @type {ShadowRoot[]} */
  let markedRoots = [];
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
  // lies in, the first thread's in reading order. One caret lookup says which text node,
  // and where in it, the point is over, looking into the shadow trees that hold marks;
  // the test then reads the geometry only of the pieces on that node that cover that
  // offset, since a text highlight has no DOM node and its client rects are its only
  // exact hit test, and climbs from the node for an element's mark. So a pointer move
  // costs the same however many marks the page or the paragraph holds (root AGENTS.md,
  // "Responsiveness"): reading every mark's rects in the element pointed at cost 512
  // reads at the last of 512 marks in one paragraph. What the lookup finds outside the
  // page's words, as the chrome over them, holds no mark. With the annotation layer
  // hidden there is no mark to be under: an unseen passage shows no hand and opens
  // nothing.
  /** @param {number} x @param {number} y @returns {{id: string, where: Mark} | null} */
  function markHit(x, y) {
    if (annotationsHidden()) return null;
    const caret = document.caretPositionFromPoint(x, y, { shadowRoots: markedRoots });
    const node = caret?.offsetNode;
    const holder = node && (isElement(node) ? node : node.parentElement);
    if (!caret || !node || !holder || !pageWords(holder)) return null;
    /** @type {Findable | null} */
    let hit = null;
    const pieces = inText.get(node) ?? [];
    const { offset } = caret;
    // The last piece starting at or before the offset, then back over every piece whose
    // run may still reach it.
    let low = 0;
    for (let high = pieces.length; low < high;) {
      const mid = (low + high) >> 1;
      if ((pieces[mid]?.start ?? Infinity) <= offset) low = mid + 1;
      else high = mid;
    }
    for (let at = low - 1; at >= 0; at--) {
      const piece = pieces[at];
      if (!piece || piece.reach < offset) break;
      if (
        piece.end >= offset &&
        (!hit || piece.order < hit.order) &&
        [...piece.where.getClientRects()].some(
          (rect) =>
            x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom,
        )
      )
        hit = piece;
    }
    for (let at = /** @type {Element | null} */ (holder); at; at = renderedParent(at))
      for (const mark of onElement.get(at) ?? [])
        if (!hit || mark.order < hit.order) hit = mark;
    return hit && { id: hit.id, where: hit.where };
  }
  /** @param {number} x @param {number} y */
  const markAt = (x, y) => markHit(x, y)?.id ?? null;

  // Index the marks where the hit test finds them (`inText`, `onElement`), and gather
  // the shadow trees they stand in, every level of them, and those of an element's mark
  // that hosts its own, which the caret lookup must look into to land inside them.
  function index() {
    inText.clear();
    onElement.clear();
    /** @type {Set<ShadowRoot>} */
    const roots = new Set();
    /** @param {Node} node */
    const within = (node) => {
      for (let root = node.getRootNode(); root instanceof ShadowRoot;) {
        roots.add(root);
        root = shadowHost(root)?.getRootNode() ?? document;
      }
    };
    let order = 0;
    for (const [id, marks] of marked) {
      for (const where of marks) {
        if (where instanceof Range) {
          const node = where.startContainer;
          const end = where.endContainer === node ? where.endOffset : Infinity;
          const pieces = inText.get(node) ?? [];
          pieces.push({ id, where, order, start: where.startOffset, end, reach: end });
          inText.set(node, pieces);
          within(node);
        } else {
          const standing = onElement.get(where) ?? [];
          standing.push({ id, where, order });
          onElement.set(where, standing);
          within(where);
          const own = declaredRoot(where);
          if (own) roots.add(own);
        }
      }
      order++;
    }
    for (const pieces of inText.values()) {
      pieces.sort((a, b) => a.start - b.start);
      let reach = -Infinity;
      for (const piece of pieces) piece.reach = reach = Math.max(reach, piece.end);
    }
    markedRoots = [...roots];
  }

  // A thread's words preview the thread, as its margin entry does (`threadPreview`).
  // An element's thread previews nothing on the page, for the reason its contour stands
  // only from the row (`paintHover`): the pointer is inside the element wherever the
  // user reads in it. The preview owner hears only where the user's own input put the
  // pointer, so a mark a scroll or a repaint carries under a still pointer shows
  // nothing, as the owner holds for elements, and a pointer carrying a press, as in
  // selecting words, rests on no mark.
  // The owner is told the whole passage, from its first piece's start to its last's
  // end, which keeps its bounds as the pointer crosses the pieces an inline element
  // splits it into, or a repaint makes it again, so its preview stands once (preview.js,
  // `pointRange`) by the line the pointer is on.
  /** @param {{id: string, where: Mark} | null} hit @param {{x: number, y: number}} at */
  function pointMark(hit, at) {
    const id = resting && hit?.where instanceof Range ? hit.id : null;
    const pieces = marksFor(id).filter((mark) => mark instanceof Range);
    const [first] = pieces;
    const last = pieces.at(-1);
    pointed = Boolean(first && last);
    if (!id || !first || !last) return void pointRange(null);
    const passage = document.createRange();
    passage.setStart(first.startContainer, first.startOffset);
    passage.setEnd(last.endContainer, last.endOffset);
    // The thread the user is in is in front of them already, as an entry standing
    // open previews nothing (preview.js).
    pointRange(
      passage,
      () => {
        const thread = id === currentLocationThreadId() ? null : threadNamed(id);
        return thread ? threadPreview([thread]) : null;
      },
      at,
    );
  }
  // The user moved the pointer, or pressed a finger, which may rest on a mark.
  /** @param {PointerEvent} event */
  function pointerAimed(event) {
    aimed = true;
    resting = event.pointerType === "touch" || !event.buttons;
    refreshHover();
  }

  // Hover reads the pointer, and the rows and margin entries it is on, inside the
  // scheduled frame. Capturing a node at event time would leave reconciliation able to
  // replace it before paint.
  function refreshHover() {
    if (hoverFrame || (!marked.size && !hovering && !hoveredRow && !pointed)) return;
    hoverFrame = nextRender(() => {
      hoverFrame = 0;
      const at = pointer();
      const hit = markHit(at.x, at.y);
      const onMark = hit?.id ?? null;
      if (aimed) pointMark(hit, at);
      aimed = false;
      keeps(document.body, RUNTIME_PAINT_ATTRIBUTE.overMark, onMark ? "" : null);
      const row = rowThread();
      const id = row ?? onMark;
      if (id !== hovering || Boolean(row) !== hoverFromRow)
        paintHover(id, Boolean(row));
      markRow(id ?? marginThread());
    });
  }

  /** @param {NonNullable<ReturnType<ReturnType<typeof import("../anchor-placement.js").createAnchorPlacement>["read"]>>} reading */
  function paint({ readings, draft, action }) {
    const before = outlined();
    marked.clear();
    pendingOutline = [];
    actionOutline = [];
    visualTargets.clear();

    const posted = [];
    const reactions = [];

    for (const { thread, placement: found } of readings) {
      if (found.status === "outdated" || thread.resolved) continue;

      if (bareReaction(thread)) {
        reactions.push(
          ...targetSegments(found).map(
            /** @param {Parameters<typeof rangeOf>[0][number]} segment */ (segment) =>
              rangeOf([segment]),
          ),
        );
        continue;
      }

      if (targetElement(found)) {
        rememberVisual(found);
        if (!thread.root.drawing) {
          marked.set(thread.id, targetParts(found));
        }
      } else if (!thread.root.drawing) {
        const ranges = targetSegments(found).map(
          /** @param {Parameters<typeof rangeOf>[0][number]} segment */ (segment) =>
            rangeOf([segment]),
        );
        marked.set(thread.id, ranges);
        posted.push(...ranges);
      }
    }
    index();
    const resolvedDraft = draft.resolved;
    const draftMarked = Boolean(resolvedDraft && resolvedDraft.status !== "outdated");
    pendingOutline =
      draftMarked && !draft.drawing && targetElement(resolvedDraft)
        ? targetParts(resolvedDraft)
        : [];
    const pending =
      draftMarked && !draft.drawing
        ? targetSegments(resolvedDraft).map(
            /** @param {Parameters<typeof rangeOf>[0][number]} segment */ (segment) =>
              rangeOf([segment]),
          )
        : [];
    if (resolvedDraft) rememberVisual(resolvedDraft);

    actionOutline = targetElement(action) ? targetParts(action) : [];
    if (action) rememberVisual(action);
    paintOutlines(before);

    CSS.highlights.set(MARK, new Highlight(...posted));
    CSS.highlights.set(REACT, new Highlight(...reactions));
    CSS.highlights.set(
      PENDING,
      Object.assign(new Highlight(...pending), { priority: 3 }),
    );
    paintCurrentLocation(false);
    // This pass creates new Range objects. Rebind hover even when the semantic id did
    // not change, then update the shared visual projection once.
    if (hovering) paintHover(hovering, hoverFromRow, false);
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
    if (hoverFrame) cancelRender(hoverFrame);
    hoverFrame = 0;
    const before = outlined();
    marked.clear();
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
    paintCurrentLocation,
    refreshHover,
    markAt,
    marksFor,
  };
}
