/* Decoration of the canonical current anchor reading.
 *
 * Anchor placement resolves conversations and composition before this optional paint.
 * This instance owns highlights, outlines and pointer hit testing; its marks never
 * supply target existence, surface admission, drawing placement or travel.
 */

import { cancelRender, nextRender } from "/runtime/rendering.js";
import {
  targetElement,
  targetParts,
  targetSegments,
  targetSurface,
} from "/runtime/resolved-target.js";
import { elementFromPointAcross, pageWords, rangeOf } from "/runtime/passages.js";
import { bareReaction } from "/runtime/thread/model.js";
import { under } from "/runtime/shadow.js";
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
  const visualTargets = new Map();
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
        reactions.push(...targetSegments(found).map((segment) => rangeOf([segment])));
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
    }
    const resolvedDraft = draft.resolved;
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
  };
}
