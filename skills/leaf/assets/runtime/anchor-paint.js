/* Synchronous anchor paint and its readonly placement record.
 *
 * One pass resolves every thread and draft, writes every anchor highlight/outline, and
 * records exactly what it drew. Consumers ask this instance for marks and placement;
 * they never re-resolve a thread independently. Controls, commands, thread state,
 * and frame invalidation are supplied above this module.
 */

import { cancelRender, nextRender } from "./rendering.js";
import {
  anchoringIsReady,
  annotationAt,
  resolveAnchor,
  sectionOf,
} from "./anchor-resolution.js";
import {
  targetElement,
  targetParts,
  targetSegments,
  targetSurface,
} from "./resolved-target.js";
import {
  elementFromPointAcross,
  inChrome,
  pageText,
  pageWords,
  rangeOf,
} from "./passages.js";
import { bareReaction, threadKey } from "./thread/model.js";
import { placePoints } from "./pointed-place.js";
import { shadowHost, under } from "./shadow.js";
import { annotationsHidden } from "./annotation-layer.js";

const MARK = "lf-mark";
const PENDING = "lf-pending";
const REACT = "lf-react";
const HOVER = "lf-mark-hover";
const HERE = "lf-mark-here";

export function createAnchorPaint({
  targetPaint,
  pointer,
  standingThreadId,
  hoveredPanelThreadId,
  panelThreadForId,
}) {
  const marked = new Map();
  const placed = new Map();
  const visualTargets = new Map();
  let pendingPlaced = null;
  let pendingMarks = [];
  let pendingOutline = [];
  let actionOutline = [];
  let hovering = null;
  let hoverFromPanel = false;
  let hoverParts = [];
  let hoverThread = null;
  let hereParts = [];
  let hoverFrame = 0;
  let mounted = false;

  const marksFor = (id) => marked.get(id) ?? [];
  const elementMarks = (where) =>
    [...where].flat().filter((mark) => mark instanceof Element);

  const rememberVisual = (resolved) => {
    const element = targetElement(resolved);
    const surface = targetSurface(resolved);
    if (element && surface) visualTargets.set(element, surface);
  };

  // An element's threads and reactions draw nothing on it at rest: its margin entry
  // already says it holds them, and a contour means "this, now". Only a moment projects
  // one — a draft, an action, the pointer on the thread's row in Threads, the thread the
  // user stands in.
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
    const focus = new Set(
      [...elements].filter((element) =>
        element.matches(":focus-visible, .lf-focus-visible"),
      ),
    );
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

  function panelThread(id) {
    return id ? panelThreadForId(id) : null;
  }

  // The pointer on a thread lights its row in Threads and its words on the page. Its
  // element is lit only from the row: on the page the pointer is inside the element
  // anywhere in it, so the contour would stand round a section for as long as the user
  // read with the mouse resting in it. The hand still says a press opens the thread.
  function paintHover(id, fromPanel, repaintVisuals = true) {
    hovering = id;
    hoverFromPanel = fromPanel;
    const thread = panelThread(id);
    if (hoverThread !== thread) {
      hoverThread?.classList.toggle(HOVER, false);
      thread?.classList.toggle(HOVER, true);
      hoverThread = thread;
    }
    const where = marksFor(id);
    const parts = fromPanel ? where.filter((mark) => mark instanceof Element) : [];
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

  // Standing follows focus, rather than the last travel (thread/focus.js,
  // `standingThreadId`). Every route into a thread then paints the same fact and leaving
  // it clears the mark without another command path.
  function paintStanding(repaintVisuals = true) {
    const where = marksFor(standingThreadId());
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

  // Which thread's painted mark lies under a point. Text highlights have no DOM node,
  // so their client rects are the only exact hit test. With the annotation layer hidden
  // there is no mark to be under: an unseen passage shows no hand and opens nothing.
  function markAt(x, y) {
    if (annotationsHidden()) return null;
    const over = document.elementFromPoint(x, y);
    if (!pageWords(over)) return null;
    const deep = elementFromPointAcross(x, y);
    for (const [id, marks] of marked)
      for (const where of marks) {
        const hit =
          where instanceof Range
            ? [...where.getClientRects()].some(
                (rect) =>
                  x >= rect.left &&
                  x <= rect.right &&
                  y >= rect.top &&
                  y <= rect.bottom,
              )
            : under(deep, where);
        if (hit) return id;
      }
    return null;
  }

  // Hover reads both the pointer and panel :hover inside the scheduled frame. Capturing
  // a node at event time would leave reconciliation able to replace it before paint.
  function refreshHover() {
    if (hoverFrame || (!marked.size && !hovering && !hoverThread)) return;
    hoverFrame = nextRender(() => {
      hoverFrame = 0;
      const at = pointer();
      const onMark = markAt(at.x, at.y);
      document.body.classList.toggle("lf-over-mark", Boolean(onMark));
      const row = hoveredPanelThreadId();
      const id = row ?? onMark;
      const fromPanel = Boolean(row);
      if (
        id !== hovering ||
        fromPanel !== hoverFromPanel ||
        panelThread(id) !== hoverThread
      )
        paintHover(id, fromPanel);
    });
  }

  function paint({ threads, draft, actionAnchor }) {
    // A refused pass is distinct from a ready pass that resolved nothing. The caller must
    // not build durable controls from an empty-looking result before presentation has made
    // the page's anchor reading authoritative.
    if (!anchoringIsReady()) return null;

    const before = outlined();
    marked.clear();
    placed.clear();
    pendingOutline = [];
    actionOutline = [];
    visualTargets.clear();

    const text = pageText();
    const posted = [];
    const reactions = [];
    const reactionSeats = new Map();
    const notes = new Map();

    const pointable = [];
    for (const thread of threads) {
      if (!thread.anchor) continue;
      const found = resolveAnchor(thread.anchor, text);
      if (!found) continue;
      // Placement includes resolved threads and remains distinct from paint. The panel
      // orders from this record instead of resolving the same coordinate again. A
      // pointed thread's record also carries the row it stands by (`point`), the key of
      // the margin row it shares with others pointed there (`pointRow`), and the row's
      // words as the page reads them (`pointWords`), below.
      const target = targetElement(found) ?? found.place;
      placed.set(thread.id, {
        datumElement: null,
        exact: true,
        status: "exact",
        ...found,
        target,
        element: found.place,
        point: null,
        pointRow: null,
        pointWords: null,
      });
      // A drawing's part names where on the picture it is; a point is for a target that
      // names no place inside itself.
      if (!thread.resolved && !thread.anchor.quote && !thread.anchor.visual && target)
        pointable.push({ id: thread.id, key: threadKey(thread), target });
      if (found.status === "outdated" || thread.resolved) continue;

      if (bareReaction(thread)) {
        let at;
        let before;
        if (targetElement(found)) {
          [at, before] = [found.place, true];
        } else {
          const segments = targetSegments(found);
          const ranges = segments.map((segment) => rangeOf([segment]));
          reactions.push(...ranges);
          const block = annotationAt(segments[0].node);
          const host = shadowHost(block?.getRootNode());
          [at, before] = host ? [host, true] : [block, false];
        }
        if (at && !inChrome(at)) {
          const held = reactionSeats.get(at) ?? { before: [], inside: [] };
          held[before ? "before" : "inside"].push(thread.root);
          reactionSeats.set(at, held);
        }
        continue;
      }

      if (targetElement(found)) {
        rememberVisual(found);
        if (!thread.root.drawing) {
          marked.set(thread.id, targetParts(found));
        }
      } else if (!thread.root.drawing) {
        const ranges = targetSegments(found).map((segment) => rangeOf([segment]));
        marked.set(thread.id, ranges);
        posted.push(...ranges);
      }

      const blocks = targetElement(found)
        ? [found.place]
        : [
            ...new Set(
              targetSegments(found).map((segment) => annotationAt(segment.node)),
            ),
          ].filter(Boolean);
      for (const holder of blocks.length ? blocks : [sectionOf(thread.anchor)])
        if (holder && !inChrome(holder))
          notes.set(holder, [...(notes.get(holder) ?? []), thread.id]);
    }
    // Where each open thread a pointing gesture stood at a row inside its target stands
    // in this reading (pointed-place.js), found with the anchors it lies inside. Every
    // thread the log holds, settled ones too, keeps its point.
    const pointed = placePoints(pointable, new Set(threads.map(threadKey)), text);
    for (const { id, key } of pointable) {
      const point = pointed.get(key);
      if (point)
        Object.assign(placed.get(id), {
          point: point.element,
          pointRow: point.row,
          pointWords: point.words,
        });
    }

    const resolvedDraft =
      draft.open && draft.anchor ? resolveAnchor(draft.anchor, text) : null;
    pendingPlaced = resolvedDraft
      ? {
          ...resolvedDraft,
          target: targetElement(resolvedDraft) ?? resolvedDraft.place,
          element: resolvedDraft.place,
        }
      : null;
    const draftMarked = Boolean(resolvedDraft && resolvedDraft.status !== "outdated");
    pendingMarks =
      draftMarked && !draft.drawing
        ? targetElement(resolvedDraft)
          ? targetParts(resolvedDraft)
          : targetSegments(resolvedDraft).map((segment) => rangeOf([segment]))
        : [];
    if (resolvedDraft) rememberVisual(resolvedDraft);
    const pending = [];
    if (targetElement(resolvedDraft)) pendingOutline = pendingMarks;
    if (targetSegments(resolvedDraft).length) pending.push(...pendingMarks);

    const active = draft.open ? null : actionAnchor;
    const action = active && !active.quote ? resolveAnchor(active, text) : null;
    actionOutline = targetElement(action) ? targetParts(action) : [];
    if (action) rememberVisual(action);
    paintOutlines(before);

    CSS.highlights.set(MARK, new Highlight(...posted));
    CSS.highlights.set(REACT, new Highlight(...reactions));
    CSS.highlights.set(
      PENDING,
      Object.assign(new Highlight(...pending), { priority: 3 }),
    );
    paintStanding(false);
    // This pass creates new Range objects. Rebind hover even when the semantic id did
    // not change, then update the shared visual projection once.
    if (hovering || hoverThread || hoverParts.length)
      paintHover(hovering, hoverFromPanel, false);
    paintVisualStates();
    refreshHover();

    return {
      notes,
      reactionSeats,
      draft: {
        open: draft.open,
        anchor: draft.anchor,
        about: draft.about,
        marked: draftMarked,
      },
    };
  }

  function mount() {
    if (mounted) return;
    mounted = true;
    document.addEventListener("pointermove", refreshHover);
  }

  function destroy() {
    if (mounted) document.removeEventListener("pointermove", refreshHover);
    mounted = false;
    if (hoverFrame) cancelRender(hoverFrame);
    hoverFrame = 0;
    const before = outlined();
    marked.clear();
    pendingOutline = [];
    actionOutline = [];
    paintOutlines(before);
    for (const element of hoverParts) element.classList.toggle(HOVER, false);
    for (const element of hereParts) element.classList.toggle(HERE, false);
    hoverThread?.classList.toggle(HOVER, false);
    for (const name of [MARK, REACT, PENDING, HOVER, HERE]) CSS.highlights.delete(name);
    targetPaint.setTargets([]);
    placed.clear();
    pendingPlaced = null;
    pendingMarks = [];
    visualTargets.clear();
    hovering = null;
    hoverFromPanel = false;
    hoverParts = [];
    hoverThread = null;
    hereParts = [];
  }

  return {
    mount,
    destroy,
    paint,
    paintStanding,
    refreshHover,
    markAt,
    marksFor,
    isMarked: (id) => marked.has(id),
    pendingAt: () => pendingPlaced,
    placedAt: (id) => placed.get(id),
  };
}
