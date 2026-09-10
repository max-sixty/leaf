/* Synchronous anchor paint and its readonly placement record.
 *
 * One pass resolves every thread and draft, writes every anchor highlight/outline, and
 * records exactly what it drew. Consumers ask this instance for marks and placement;
 * they never re-resolve a thread independently. Controls, commands, conversation state,
 * and frame invalidation are supplied above this module.
 */

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
  containsAcross,
  elementFromPointAcross,
  inChrome,
  pageText,
  pageWords,
  rangeOf,
} from "./passages.js";
import { bareReaction } from "./conversation/model.js";

const MARK = "lf-mark";
const PENDING = "lf-pending";
const REACT = "lf-react";
const HOVER = "lf-mark-hover";
const HERE = "lf-mark-here";

export function createAnchorPaint({
  targetPaint,
  pointer,
  focusedAnchorThreadId,
  hoveredPanelThreadId,
  panelThreadForId,
}) {
  const reacted = new Map();
  const marked = new Map();
  const placed = new Map();
  const visualTargets = new Map();
  let pendingPlaced = null;
  let pendingMarks = [];
  let pendingOutline = [];
  let actionOutline = [];
  let hovering = null;
  let hoverParts = [];
  let hoverThread = null;
  let hereParts = [];
  let hoverFrame = 0;
  let mounted = false;

  const marksFor = (id) => marked.get(id) ?? [];
  const allMarks = () => [...marked.values()].flat();
  const elementMarks = (where) =>
    [...where].flat().filter((mark) => mark instanceof Element);

  const rememberVisual = (resolved) => {
    const element = targetElement(resolved);
    const surface = targetSurface(resolved);
    if (element && surface) visualTargets.set(element, surface);
  };

  function paintVisualStates() {
    const comments = new Set(elementMarks(marked.values()));
    const reactions = new Set(elementMarks(reacted.values()));
    const pending = new Set(pendingOutline);
    const action = new Set(actionOutline);
    const hover = new Set(elementMarks(hoverParts));
    const here = new Set(elementMarks(hereParts));
    // Paint every element state in the chrome plane. A declared visual substitutes its
    // registered surface so compound pictures keep their contour.
    const elements = new Set(
      [comments, reactions, pending, action, hover, here]
        .flatMap((states) => [...states])
        .filter((element) => element instanceof Element),
    );
    const focus = new Set(
      [...elements].filter((element) =>
        element.matches(":focus-visible, .lf-focus-visible"),
      ),
    );
    const sources = [
      ["comment", comments],
      ["reaction", reactions],
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

  function panelThread(id) {
    return id ? panelThreadForId(id) : null;
  }

  function paintHover(id, repaintVisuals = true) {
    hovering = id;
    const thread = panelThread(id);
    if (hoverThread !== thread) {
      hoverThread?.classList.remove(HOVER);
      thread?.classList.add(HOVER);
      hoverThread = thread;
    }
    const where = marksFor(id);
    const parts = where.filter((mark) => mark instanceof Element);
    for (const part of hoverParts)
      if (!parts.includes(part)) part.classList.remove(HOVER);
    for (const part of parts)
      if (!part.classList.contains(HOVER)) part.classList.add(HOVER);
    hoverParts = parts;
    CSS.highlights.set(
      HOVER,
      Object.assign(new Highlight(...where.filter((mark) => mark instanceof Range)), {
        priority: 1,
      }),
    );
    if (repaintVisuals) paintVisualStates();
  }

  // Standing follows focus, rather than the last travel. Every route into a thread then
  // paints the same fact and leaving it clears the mark without another command path.
  function paintStanding(repaintVisuals = true) {
    const where = marksFor(focusedAnchorThreadId());
    const parts = where.filter((mark) => mark instanceof Element);
    for (const part of hereParts)
      if (!parts.includes(part)) part.classList.remove(HERE);
    for (const part of parts)
      if (!part.classList.contains(HERE)) part.classList.add(HERE);
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
  // so their client rects are the only exact hit test.
  function markAt(x, y) {
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
            : containsAcross(where, deep);
        if (hit) return id;
      }
    return null;
  }

  // Hover reads both the pointer and panel :hover inside the scheduled frame. Capturing
  // a node at event time would leave reconciliation able to replace it before paint.
  function refreshHover() {
    if (hoverFrame || (!marked.size && !hovering && !hoverThread)) return;
    hoverFrame = requestAnimationFrame(() => {
      hoverFrame = 0;
      const at = pointer();
      const onMark = markAt(at.x, at.y);
      document.body.classList.toggle("lf-over-mark", Boolean(onMark));
      const id = hoveredPanelThreadId() ?? onMark;
      if (id !== hovering || panelThread(id) !== hoverThread) paintHover(id);
    });
  }

  function paint({ threads, draft, actionAnchor }) {
    // A refused pass is distinct from a ready pass that resolved nothing. The caller must
    // not build durable controls from an empty-looking result before presentation has made
    // the page's anchor reading authoritative.
    if (!anchoringIsReady()) return null;

    for (const where of allMarks())
      if (where instanceof Element) where.classList.remove("lf-mark-el");
    for (const where of [...reacted.values()].flat())
      if (where instanceof Element) where.classList.remove("lf-react-el");
    for (const element of pendingOutline)
      element.classList.remove("lf-mark-el", PENDING);
    for (const element of actionOutline) element.classList.remove("lf-action-target");
    marked.clear();
    reacted.clear();
    placed.clear();
    pendingOutline = [];
    actionOutline = [];
    visualTargets.clear();

    const text = pageText();
    const posted = [];
    const reactions = [];
    const reactionSeats = new Map();
    const notes = new Map();

    for (const thread of threads) {
      if (!thread.anchor) continue;
      const found = resolveAnchor(thread.anchor, text);
      if (!found) continue;
      // Placement includes resolved threads and remains distinct from paint. The panel
      // orders from this record instead of resolving the same coordinate again.
      placed.set(thread.root.id, {
        datumElement: null,
        exact: true,
        status: "exact",
        ...found,
        target: targetElement(found) ?? found.place,
        element: found.place,
      });
      if (found.status === "outdated" || thread.resolved) continue;

      if (bareReaction(thread)) {
        let at;
        let before;
        if (targetElement(found)) {
          const parts = targetParts(found);
          for (const part of parts) part.classList.add("lf-react-el");
          rememberVisual(found);
          reacted.set(thread.root.id, parts);
          [at, before] = [found.place, true];
        } else {
          const segments = targetSegments(found);
          const ranges = segments.map((segment) => rangeOf([segment]));
          reacted.set(thread.root.id, ranges);
          reactions.push(...ranges);
          const block = annotationAt(segments[0].node);
          const root = block?.getRootNode();
          [at, before] =
            root instanceof ShadowRoot ? [root.host, true] : [block, false];
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
          const parts = targetParts(found);
          for (const part of parts) part.classList.add("lf-mark-el");
          marked.set(thread.root.id, parts);
        }
      } else if (!thread.root.drawing) {
        const ranges = targetSegments(found).map((segment) => rangeOf([segment]));
        marked.set(thread.root.id, ranges);
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
          notes.set(holder, [...(notes.get(holder) ?? []), thread.root.id]);
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
    if (targetElement(resolvedDraft)) {
      const taken = allMarks();
      for (const part of pendingMarks)
        if (!taken.includes(part)) {
          part.classList.add("lf-mark-el", PENDING);
          pendingOutline.push(part);
        }
    }
    if (targetSegments(resolvedDraft).length) pending.push(...pendingMarks);

    const active = draft.open ? null : actionAnchor;
    const action = active && !active.quote ? resolveAnchor(active, text) : null;
    actionOutline = targetElement(action) ? targetParts(action) : [];
    if (action) rememberVisual(action);
    for (const part of actionOutline) part.classList.add("lf-action-target");

    CSS.highlights.set(MARK, new Highlight(...posted));
    CSS.highlights.set(REACT, new Highlight(...reactions));
    CSS.highlights.set(
      PENDING,
      Object.assign(new Highlight(...pending), { priority: 3 }),
    );
    paintStanding(false);
    // This pass creates new Range objects. Rebind hover even when the semantic id did
    // not change, then update the shared visual projection once.
    if (hovering || hoverThread || hoverParts.length) paintHover(hovering, false);
    paintVisualStates();

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
    if (hoverFrame) cancelAnimationFrame(hoverFrame);
    hoverFrame = 0;
    for (const where of allMarks())
      if (where instanceof Element) where.classList.remove("lf-mark-el");
    for (const where of [...reacted.values()].flat())
      if (where instanceof Element) where.classList.remove("lf-react-el");
    for (const element of pendingOutline)
      element.classList.remove("lf-mark-el", PENDING);
    for (const element of actionOutline) element.classList.remove("lf-action-target");
    for (const element of hoverParts) element.classList.remove(HOVER);
    for (const element of hereParts) element.classList.remove(HERE);
    hoverThread?.classList.remove(HOVER);
    for (const name of [MARK, REACT, PENDING, HOVER, HERE]) CSS.highlights.delete(name);
    targetPaint.setTargets([]);
    marked.clear();
    reacted.clear();
    placed.clear();
    pendingPlaced = null;
    pendingMarks = [];
    pendingOutline = [];
    actionOutline = [];
    visualTargets.clear();
    hovering = null;
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
